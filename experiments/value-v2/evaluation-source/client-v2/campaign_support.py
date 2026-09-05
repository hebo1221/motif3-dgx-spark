#!/usr/bin/env python3
"""Small, reproducible single-slot HTTP comparison for an already verified GGUF.

No third-party dependencies. Each arm owns and shuts down its local server.
Streaming latency is measured at the client; MTP can emit several tokens per
event, so event gaps are deliberately not described as inter-token latency.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.request


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def stat_file(path):
    path = Path(path).resolve(strict=True)
    s = path.stat()
    return dict(path=str(path), size_bytes=s.st_size, mtime_ns=s.st_mtime_ns,
                inode=s.st_ino, device=s.st_dev)


def verify_binding(path):
    binding = json.loads(Path(path).read_text())
    if binding.get("status") != "pass" or not binding.get("files_stable_during_check"):
        raise ValueError("Binding is not a successful integrity check")
    for key in ("target", "sidecar"):
        current = stat_file(binding[key]["path"])
        if any(current[k] != binding[key][k] for k in current):
            raise ValueError(f"{key} changed after full-hash binding")
        if len(binding[key].get("sha256", "")) != 64:
            raise ValueError("Missing full SHA-256 in binding")
    return binding


def binary_receipt(path):
    path = Path(path).resolve(strict=True)
    result = dict(stat_file(path), sha256=digest(path))
    linked = subprocess.check_output(["ldd", str(path)], text=True)
    dependencies = []
    for line in linked.splitlines():
        for word in line.split():
            if word.startswith("/") and Path(word).is_file():
                dependencies.append(dict(stat_file(word), sha256=digest(word)))
                break
    result["linked_libraries"] = dependencies
    result["ldd"] = linked
    return result


def request_json(port, route, body=None, timeout=30):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}{route}", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def sse_data(lines):
    """Yield complete SSE data fields, preserving multi-line event boundaries."""
    fields = []
    for raw in lines:
        line = raw.decode("utf-8").rstrip("\r\n")
        if not line:
            if fields:
                yield "\n".join(fields)
                fields = []
        elif line.startswith("data:"):
            value = line[5:]
            fields.append(value[1:] if value.startswith(" ") else value)
    if fields:
        yield "\n".join(fields)


def quantile(values, p):
    if not values:
        return None
    values = sorted(values)
    x = (len(values) - 1) * p
    lo = int(x)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (x - lo)


def collect_stream(port, body, output, timeout):
    request = urllib.request.Request(f"http://127.0.0.1:{port}/completion",
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"})
    start = time.perf_counter()
    tokens, chunks, text, final = [], [], [], None
    first_content_ms = None
    with output.open("w") as log, urllib.request.urlopen(request, timeout=timeout) as response:
        for data in sse_data(response):
            elapsed = (time.perf_counter() - start) * 1000
            if data == "[DONE]":
                continue
            item = json.loads(data)
            log.write(json.dumps({"client_elapsed_ms": elapsed, "data": item},
                                 ensure_ascii=False) + "\n")
            log.flush()
            if "error" in item:
                raise RuntimeError(item["error"])
            ids = item.get("tokens", [])
            content = item.get("content", "")
            if ids or content:
                chunks.append({"elapsed_ms": elapsed, "token_count": len(ids)})
            if content and first_content_ms is None:
                first_content_ms = elapsed
            tokens.extend(ids)
            text.append(content)
            if item.get("stop"):
                final = item
    wall_ms = (time.perf_counter() - start) * 1000
    if final is None or not tokens or final.get("truncated"):
        raise RuntimeError("Incomplete, empty, or context-truncated response")
    gaps = [b["elapsed_ms"] - a["elapsed_ms"] for a, b in zip(chunks, chunks[1:])]
    return dict(tokens=tokens, content="".join(text), stop_type=final.get("stop_type"),
        stopping_word=final.get("stopping_word"), truncated=final.get("truncated"),
        tokens_evaluated=final.get("tokens_evaluated"),
        tokens_predicted=final.get("tokens_predicted"), timings=final.get("timings"),
        generation_settings=final.get("generation_settings"),
        client=dict(request_wall_ms=wall_ms, first_content_ms=first_content_ms,
            first_token_event_ms=chunks[0]["elapsed_ms"] if chunks else None,
            streaming_events=len(chunks), mean_tokens_per_event=len(tokens)/len(chunks),
            max_event_gap_ms=max(gaps) if gaps else None,
            p95_event_gap_ms=quantile(gaps, .95)),
        raw_events={"file": output.name, "sha256": digest(output)})


def gpu_snapshot():
    q = subprocess.check_output(["nvidia-smi", "--query-gpu=name,uuid,temperature.gpu,power.draw",
                                 "--format=csv,noheader,nounits"], text=True, timeout=10)
    processes = subprocess.check_output(["nvidia-smi", "--query-compute-apps=pid,used_gpu_memory,process_name",
                                         "--format=csv,noheader,nounits"], text=True, timeout=10)
    return {"gpu": q.strip(), "compute_processes": processes.strip()}


def available_mib():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024
    raise RuntimeError("MemAvailable is missing")


def telemetry_loop(stop, proc, output, state):
    with output.open("w") as log:
        while not stop.is_set():
            try:
                snapshot = dict(unix_time=time.time(), mem_available_mib=available_mib(),
                                **gpu_snapshot())
                state.append(snapshot)
                log.write(json.dumps(snapshot) + "\n")
                log.flush()
                if snapshot["mem_available_mib"] < 2500:
                    state.append({"abort": "MemAvailable below 2500 MiB"})
                    proc.terminate()
                    return
            except Exception as exc:
                state.append({"telemetry_error": repr(exc)})
            stop.wait(1)


def check_local_port(port):
    # Match the HTTP server's address-reuse behavior after an owned shutdown.
    # TIME_WAIT from the previous arm must not look like a live listener.
    with socket.socket() as check:
        check.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        check.bind(("127.0.0.1", port))


@contextlib.contextmanager
def server(command, output, port, gpu_uuid, startup_timeout):
    check_local_port(port)
    before = gpu_snapshot()
    if gpu_uuid not in before["gpu"]:
        raise RuntimeError("Unexpected GPU")
    if before["compute_processes"]:
        raise RuntimeError("Another GPU compute process is already running")
    if available_mib() < 96000:
        raise RuntimeError("Less than 96000 MiB MemAvailable before model load")
    state = []
    stop = threading.Event()
    env = {k: v for k, v in os.environ.items() if not k.startswith("LLAMA_ARG_")}
    env.update(CUDA_VISIBLE_DEVICES=gpu_uuid, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    start = time.monotonic()
    with (output / "server.log").open("w") as log:
        proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env,
                                start_new_session=True)
        watcher = threading.Thread(target=telemetry_loop,
            args=(stop, proc, output / "telemetry.jsonl", state), daemon=True)
        watcher.start()
        try:
            while time.monotonic() - start < startup_timeout:
                if proc.poll() is not None:
                    raise RuntimeError(f"Server exited {proc.returncode}: {(output/'server.log').read_text()[-2500:]}")
                try:
                    health = request_json(port, "/health", timeout=2)
                    if health.get("status") == "ok":
                        break
                except (urllib.error.URLError, TimeoutError):
                    pass
                time.sleep(1)
            else:
                raise TimeoutError("Server startup deadline exceeded")
            yield dict(pid=proc.pid, startup_seconds=time.monotonic()-start, gpu_before=before)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)
            stop.set()
            watcher.join(timeout=15)
            samples = [s for s in state if "mem_available_mib" in s]
            write_json(output / "server-lifecycle.json", dict(command=command, pid=proc.pid,
                process_exit_code=proc.returncode, owned_process_stopped=proc.poll() is not None,
                min_mem_available_mib=min((s["mem_available_mib"] for s in samples), default=None),
                telemetry_errors=[s for s in state if "telemetry_error" in s or "abort" in s]))


def command_for(config, arm):
    binary = config["baseline_binary"] if arm["runtime"] == "baseline" else config["integrated_binary"]
    cmd = [binary, "--offline", "--model", config["target"], "--gpu-layers", "99",
        "--flash-attn", "on", "--cache-type-k", "f16", "--cache-type-v", "f16",
        "--ctx-size", str(config["ctx_size"]), "--parallel", "1", "--batch-size", "2048",
        "--ubatch-size", "512", "--threads", "20", "--fit", "off", "--no-cache-prompt",
        "--no-warmup", "--metrics", "--slots", "--no-webui", "--host", "127.0.0.1",
        "--port", str(config["port"]), "--jinja", "--chat-template-file", config["template"],
        "--chat-template-kwargs", '{"enable_thinking":false}']
    if arm["draft"]:
        cmd += ["--model-draft", config["sidecar"], "--spec-type", "draft-mtp",
                "--spec-draft-n-max", str(arm["draft"]), "--gpu-layers-draft", "99"]
    return cmd


def rendered_prompt(port, case):
    if "prompt" in case:
        return case["prompt"]
    result = request_json(port, "/apply-template", dict(messages=case["messages"],
                          add_generation_prompt=True, chat_template_kwargs={"enable_thinking":False}))
    return result["prompt"]


def run_case(config, case, folder):
    prompt = rendered_prompt(config["port"], case)
    tokenization = request_json(config["port"], "/tokenize", dict(content=prompt, add_special=False, parse_special=True))
    input_ids = tokenization["tokens"]
    if "expected_input_tokens" in case and len(input_ids) != case["expected_input_tokens"]:
        raise RuntimeError(f"Prompt token count changed for {case['id']}: {len(input_ids)}")
    body = dict(prompt=prompt, n_predict=case.get("max_tokens", 192), temperature=0, top_k=1,
        seed=42, cache_prompt=False, stream=True, return_tokens=True, id_slot=0,
        ignore_eos=case.get("ignore_eos", False), stop=case.get("stop", []))
    write_json(folder / (case["id"] + ".request.json"), body)
    result = collect_stream(config["port"], body, folder / (case["id"] + ".events.jsonl"),
                            config.get("request_timeout", 600))
    result.update(case_id=case["id"], input_tokens=len(input_ids),
        input_ids_sha256=hashlib.sha256(json.dumps(input_ids, separators=(",", ":")).encode()).hexdigest(),
        prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())
    write_json(folder / (case["id"] + ".result.json"), result)
    return result


def compare(reference, candidate):
    same_input = (reference["input_ids_sha256"] == candidate["input_ids_sha256"])
    a, b = reference["tokens"], candidate["tokens"]
    first = next((i for i, (x,y) in enumerate(zip(a,b)) if x != y), None)
    if first is None and len(a) != len(b):
        first = min(len(a), len(b))
    exact = same_input and a == b and reference["content"] == candidate["content"] and reference["stop_type"] == candidate["stop_type"]
    return dict(exact=exact, input_exact=same_input, first_mismatch_index=first,
        reference_token_count=len(a), candidate_token_count=len(b),
        stop_type_exact=reference["stop_type"] == candidate["stop_type"],
        content_exact=reference["content"] == candidate["content"],
        wall_ratio=reference["client"]["request_wall_ms"]/candidate["client"]["request_wall_ms"])


def run_api_case(config, case, folder):
    """Exercise native chat parsing using synthetic requests and mock tool data."""
    body = dict(model="motif3", temperature=0, seed=42, top_k=1, cache_prompt=False,
                max_tokens=case.get("max_tokens", 128), stream=False,
                chat_template_kwargs={"enable_thinking": False}, **case["body"])
    write_json(folder / (case["id"] + ".request.json"), body)
    start = time.perf_counter()
    try:
        response = request_json(config["port"], "/v1/chat/completions", body, config.get("request_timeout", 600))
        choice = response["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""
        canonical = {"content": content, "finish_reason": choice["finish_reason"], "tool_calls": []}
        for call in message.get("tool_calls", []):
            function = call["function"]
            args = function["arguments"]
            if isinstance(args, str):
                args = json.loads(args)
            canonical["tool_calls"].append({"name":function["name"], "arguments":args})
        if case["check"] == "text":
            passed = bool(content.strip()) and choice["finish_reason"] == "stop"
        elif case["check"] == "tool":
            passed = canonical["tool_calls"] == [{"name":"get_weather", "arguments":{"city":"서울"}}] and choice["finish_reason"] == "tool_calls"
        elif case["check"] == "tool_response":
            passed = "13" in content and "서울" in content and choice["finish_reason"] == "stop"
        elif case["check"] == "json":
            passed = json.loads(content) == {"count":3, "active":True} and choice["finish_reason"] == "stop"
        else:
            raise ValueError("Unknown API check")
        result = dict(status="pass" if passed else "fail", response=response, canonical=canonical)
    except Exception as exc:
        result = dict(status="error", error=repr(exc))
        if isinstance(exc, urllib.error.HTTPError):
            result["http_error_body"] = exc.read().decode("utf-8", errors="replace")
    result.update(case_id=case["id"], request_wall_ms=(time.perf_counter()-start)*1000,
                  limitation="API behavior on a synthetic fixture; forced tool choice is not automatic tool-decision quality.")
    write_json(folder / (case["id"] + ".api-result.json"), result)
    return result


def summarize(arms):
    reference = arms[0]
    reports = []
    for arm in arms:
        comparisons = {key: compare(reference["cases"][key], val) for key, val in arm["cases"].items()}
        wall = sum(v["client"]["request_wall_ms"] for v in arm["cases"].values())
        timings = [v["timings"] for v in arm["cases"].values()]
        seconds = sum(t["predicted_ms"] for t in timings)/1000
        reports.append(dict(arm=arm["name"], draft=arm["draft"], runtime=arm["runtime"],
            all_exact_to_first_arm=all(x["exact"] for x in comparisons.values()),
            returned_tokens=sum(len(v["tokens"]) for v in arm["cases"].values()),
            request_wall_ms_sum=wall,
            engine_reported_tokens_per_second=sum(t["predicted_per_second"]*t["predicted_ms"]/1000 for t in timings)/seconds,
            cases=comparisons))
    return dict(arms=reports, reference_arm=reference["name"],
        limitations=["Single GPU, fixed prompts, greedy sampling and one HTTP slot.",
                     "Client stream events may contain multiple tokens; event gaps are not per-token gaps.",
                     "Development selection is not independent confirmation or a quality benchmark."])


def main():
    def terminate(signum, frame):
        raise KeyboardInterrupt(f"Received signal {signum}; stopping owned server")
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGHUP, terminate)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    plan = json.loads(args.plan.read_text())
    if not args.execute:
        print(json.dumps({"commands": {arm["name"]:command_for(config,arm) for arm in plan["arms"]},
                          "case_ids":[c["id"] for c in plan["cases"]]}, indent=2))
        return
    binding = verify_binding(config["binding"])
    if config["target"] != binding["target"]["path"] or config["sidecar"] != binding["sidecar"]["path"]:
        raise ValueError("Configuration differs from verified model pair")
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema_version="motif3-integrated-http-campaign-v1", status="running",
        started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        runner_sha256=digest(__file__), config_sha256=digest(args.config), plan_sha256=digest(args.plan),
        binding_sha256=digest(config["binding"]), binding=binding,
        binaries={kind:binary_receipt(config[kind+"_binary"]) for kind in {a["runtime"] for a in plan["arms"]}},
        template_sha256=digest(config["template"]), config=config, plan=plan, arms=[])
    write_json(args.output/"receipt.json", receipt)
    try:
        for arm in plan["arms"]:
            verify_binding(config["binding"])
            folder = args.output/arm["name"]
            folder.mkdir()
            print(f"Starting {arm['name']}", flush=True)
            with server(command_for(config, arm), folder, config["port"], config["gpu_uuid"], config.get("startup_timeout", 600)) as lifecycle:
                write_json(folder/"props.json", request_json(config["port"], "/props"))
                warm = {"id":"warmup", "prompt":"<|beginoftext|><|startofturn|><|user|>1 더하기 1은?<|endofturn|><|startofturn|><|assistant|><think></think>","max_tokens":16}
                run_case(config, warm, folder)
                record = dict(**arm, lifecycle=lifecycle, cases={})
                for case in plan["cases"]:
                    result = run_case(config, case, folder)
                    record["cases"][case["id"]] = result
                    print(f"  {case['id']}: {len(result['tokens'])} tokens, {result['stop_type']}, {result['client']['request_wall_ms']/1000:.2f}s", flush=True)
                if plan.get("api_cases"):
                    record["api_cases"] = {}
                    for case in plan["api_cases"]:
                        result = run_api_case(config, case, folder)
                        record["api_cases"][case["id"]] = result
                        print(f"  {case['id']}: {result['status']}", flush=True)
                receipt["arms"].append(record)
                write_json(args.output/"receipt.json", receipt)
            verify_binding(config["binding"])
        receipt["status"] = "completed"
        receipt["summary"] = summarize(receipt["arms"])
        write_json(args.output/"summary.json", receipt["summary"])
    except BaseException as exc:
        receipt["status"] = "failed"
        receipt["error"] = repr(exc)
        raise
    finally:
        receipt["ended_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        write_json(args.output/"receipt.json", receipt)


if __name__ == "__main__":
    main()
