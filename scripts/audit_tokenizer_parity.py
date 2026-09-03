#!/usr/bin/env python3
"""Check a final Motif-3 GGUF's embedded tokenizer against the official one.

The script reads vocabulary metadata only. ``llama-tokenize`` is invoked in
offline, CPU-only, vocab-only mode and the model tensor payload is not loaded.
The Motif path is never supplied through ``--override-kv``: a passing result
therefore exercises the GGUF's own ``tokenizer.ggml.pre`` value. The receipt
contains aggregate counts and hashes, never corpus text or token IDs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_TOKENIZER_BYTES = 64 * 1024 * 1024
MAX_CORPUS_BYTES = 16 * 1024 * 1024
MAX_TOKEN_OUTPUT_BYTES = 64 * 1024 * 1024
SEPARATOR = "<|endoftext|>"


class AuditError(RuntimeError):
    pass


@dataclass(frozen=True)
class Snapshot:
    path: Path
    data: bytes
    size: int
    sha256: str
    device: int
    inode: int
    mtime_ns: int


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _write_new(path: Path, raw: bytes) -> None:
    requested = Path(os.path.abspath(os.fspath(path)))
    parent = requested.parent.resolve(strict=True)
    if requested.parent != parent or requested.exists() or requested.is_symlink():
        raise AuditError(f"refusing non-new output: {requested}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(requested, flags, 0o600)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise AuditError("short write while creating parity receipt")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _snapshot(path: Path, *, max_bytes: int) -> Snapshot:
    resolved = path.resolve(strict=True)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(resolved, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise AuditError(f"not a regular file: {resolved}")
        if before.st_size > max_bytes:
            raise AuditError(f"file exceeds {max_bytes} bytes: {resolved}")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                raise AuditError(f"short read: {resolved}")
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after:
        raise AuditError(f"file changed while reading: {resolved}")
    data = b"".join(chunks)
    return Snapshot(
        path=resolved,
        data=data,
        size=len(data),
        sha256=_sha256(data),
        device=before.st_dev,
        inode=before.st_ino,
        mtime_ns=before.st_mtime_ns,
    )


def _stat_receipt(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    info = resolved.stat()
    if not stat.S_ISREG(info.st_mode):
        raise AuditError(f"not a regular file: {resolved}")
    return {
        "path": str(resolved),
        "size_bytes": info.st_size,
        "device": info.st_dev,
        "inode": info.st_ino,
        "mtime_ns": info.st_mtime_ns,
    }


def _dynamic_dependency_receipts(
    executable: Path, *, timeout_seconds: int
) -> dict[str, Any]:
    ldd = shutil.which("ldd")
    if ldd is None:
        raise AuditError("ldd is required to bind the runtime dynamic-library closure")
    try:
        completed = subprocess.run(
            [ldd, str(executable)],
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise AuditError("ldd timed out") from exc
    if completed.returncode != 0:
        raise AuditError(
            f"ldd failed: rc={completed.returncode}, stderr_sha256={_sha256(completed.stderr)}"
        )
    try:
        lines = completed.stdout.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise AuditError("ldd output was not UTF-8") from exc
    paths: set[Path] = set()
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("linux-vdso"):
            continue
        candidate: str | None = None
        if "=>" in line:
            right = line.split("=>", 1)[1].strip()
            if right == "not found" or right.startswith("not found "):
                raise AuditError(f"unresolved dynamic dependency: {line}")
            candidate = right.split(" ", 1)[0]
        elif line.startswith("/"):
            candidate = line.split(" ", 1)[0]
        if candidate is not None and candidate.startswith("/"):
            paths.add(Path(candidate).resolve(strict=True))
    if not paths:
        raise AuditError("ldd returned no filesystem-backed dependencies")
    receipts: list[dict[str, Any]] = []
    local_dir = executable.parent.resolve(strict=True)
    for path in sorted(paths, key=str):
        if path.parent == local_dir:
            snapshot = _snapshot(path, max_bytes=512 * 1024 * 1024)
            receipts.append(
                {
                    "path": str(snapshot.path),
                    "size_bytes": snapshot.size,
                    "sha256": snapshot.sha256,
                    "exact_bytes_bound": True,
                }
            )
        else:
            item = _stat_receipt(path)
            item["sha256"] = None
            item["exact_bytes_bound"] = False
            receipts.append(item)
    _require_local = [item for item in receipts if item["exact_bytes_bound"]]
    if not _require_local:
        raise AuditError("no local llama.cpp dynamic dependencies were bound")
    return {
        "resolved": receipts,
        "local_exact_count": len(_require_local),
        "external_stat_only_count": len(receipts) - len(_require_local),
        "local_llama_cpp_dependencies_exact": True,
        "external_system_dependencies_exact": False,
    }


def _ids_sha256(ids: list[int]) -> str:
    payload = json.dumps(ids, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return _sha256(payload)


def _parse_ids(raw: bytes) -> list[int]:
    if len(raw) > MAX_TOKEN_OUTPUT_BYTES:
        raise AuditError("llama-tokenize output exceeded the safety limit")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError(
            "llama-tokenize did not return one JSON token-ID array"
        ) from exc
    if not isinstance(value, list) or any(
        isinstance(item, bool) or not isinstance(item, int) or item < 0
        for item in value
    ):
        raise AuditError("llama-tokenize returned an invalid token-ID array")
    return value


def _run_llama_tokenize(
    executable: Path,
    model: Path,
    prompt: bytes,
    *,
    pre_type: str | None,
    timeout_seconds: int,
) -> tuple[list[int], dict[str, Any]]:
    argv = [
        str(executable),
        "--offline",
        "--device",
        "none",
        "-m",
        str(model),
    ]
    if pre_type is not None:
        argv.extend(
            [
                "--override-kv",
                f"tokenizer.ggml.pre=str:{pre_type}",
            ]
        )
    argv.extend(["--stdin", "--no-escape", "--ids"])
    try:
        completed = subprocess.run(
            argv,
            input=prompt,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        mode = pre_type if pre_type is not None else "embedded"
        raise AuditError(f"llama-tokenize timed out for pre={mode}") from exc
    if completed.returncode != 0:
        raise AuditError(
            f"llama-tokenize failed for pre={pre_type or 'embedded'}: rc={completed.returncode}, "
            f"stderr_sha256={_sha256(completed.stderr)}"
        )
    ids = _parse_ids(completed.stdout)
    return ids, {
        "argv": argv,
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256": _sha256(completed.stdout),
        "stderr_bytes": len(completed.stderr),
        "stderr_sha256": _sha256(completed.stderr),
    }


def _fuzz_cases(count: int, seed: int) -> list[str]:
    fixed = [
        "and P",
        "Guide to",
        "The AIA Guide to New York City",
        "The state of the art is a moving target.",
        "I'M sure we'll test Motif's tokenizer.",
        "서울 AI 연구소 and PyTorch Tools",
        "Aǅb ǈC ῼmega αBeta",
        "e\u0301 E\u0301 한글 English 123 4567",
        "tool_call arguments JSON and URL paths /a/b",
        "UPPER lower TitleCase McDONALD'S",
        "line one\r\nline TWO\n\n끝",
    ]
    if count < len(fixed):
        raise AuditError(f"fuzz case count must be at least {len(fixed)}")
    rng = random.Random(seed)
    upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZΓΔЖǅῼ"
    lower = "abcdefghijklmnopqrstuvwxyzαβжǆ한글"
    marks = "\u0301\u0308"
    punct = " .,:;!?/_-()[]{}'\""
    digits = "0123456789"
    pieces = [upper, lower, marks, punct, digits]
    cases = list(fixed)
    while len(cases) < count:
        groups = rng.randint(1, 12)
        parts: list[str] = []
        for _ in range(groups):
            alphabet = rng.choice(pieces)
            parts.append(
                "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 9)))
            )
            if rng.random() < 0.45:
                parts.append(rng.choice([" ", "  ", "\n", "\r\n"]))
        cases.append("".join(parts))
    return cases


def _corpus_result(
    tokenizer: Any,
    snapshot: Snapshot,
    executable: Path,
    model: Path,
    timeout_seconds: int,
    prefix_tokens: int,
    runtime_pre_type: str | None,
) -> dict[str, Any]:
    text = snapshot.data.decode("utf-8")
    official = tokenizer.encode(text, add_special_tokens=False).ids
    runtime, runtime_call = _run_llama_tokenize(
        executable,
        model,
        snapshot.data,
        pre_type=runtime_pre_type,
        timeout_seconds=timeout_seconds,
    )
    legacy, legacy_call = _run_llama_tokenize(
        executable,
        model,
        snapshot.data,
        pre_type="gpt-2",
        timeout_seconds=timeout_seconds,
    )
    official_sha = _ids_sha256(official)
    runtime_sha = _ids_sha256(runtime)
    legacy_sha = _ids_sha256(legacy)
    if len(official) < prefix_tokens or len(runtime) < prefix_tokens:
        raise AuditError(
            f"corpus {snapshot.path} has fewer than {prefix_tokens} tokens"
        )
    official_prefix = official[:prefix_tokens]
    runtime_prefix = runtime[:prefix_tokens]
    return {
        "source": {
            "path": str(snapshot.path),
            "size_bytes": snapshot.size,
            "sha256": snapshot.sha256,
        },
        "official": {
            "token_count": len(official),
            "token_ids_sha256": official_sha,
            "evaluation_prefix": {
                "token_count": prefix_tokens,
                "token_ids_sha256": _ids_sha256(official_prefix),
            },
        },
        "runtime_motif3": {
            "token_count": len(runtime),
            "token_ids_sha256": runtime_sha,
            "evaluation_prefix": {
                "token_count": prefix_tokens,
                "token_ids_sha256": _ids_sha256(runtime_prefix),
            },
            "call": runtime_call,
        },
        "runtime_legacy_gpt2": {
            "token_count": len(legacy),
            "token_ids_sha256": legacy_sha,
            "excess_tokens_vs_official": len(legacy) - len(official),
            "excess_percent_vs_official": (len(legacy) / len(official) - 1.0) * 100.0,
            "call": legacy_call,
        },
        "exact_match": official == runtime,
        "mismatch_count": 0 if official == runtime else 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-tokenizer", type=Path, required=True)
    parser.add_argument("--llama-tokenize", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument(
        "--corpus",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="named UTF-8 corpus; may be supplied more than once",
    )
    parser.add_argument("--fuzz-cases", type=int, default=12011)
    parser.add_argument(
        "--fuzz-seed", type=lambda value: int(value, 0), default=0x4D4F54494633
    )
    parser.add_argument("--prefix-tokens", type=int, default=49152)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.timeout_seconds <= 0:
        raise AuditError("timeout must be positive")
    if args.prefix_tokens <= 0:
        raise AuditError("prefix token count must be positive")
    named_corpora: list[tuple[str, Path]] = []
    seen_names: set[str] = set()
    for spec in args.corpus:
        if "=" not in spec:
            raise AuditError(f"invalid --corpus value: {spec!r}")
        name, raw_path = spec.split("=", 1)
        if not name or name in seen_names:
            raise AuditError(f"empty or duplicate corpus name: {name!r}")
        seen_names.add(name)
        named_corpora.append((name, Path(raw_path)))
    if not named_corpora:
        raise AuditError("at least one --corpus is required")

    auditor_snapshot = _snapshot(Path(__file__), max_bytes=4 * 1024 * 1024)
    tokenizer_snapshot = _snapshot(
        args.official_tokenizer, max_bytes=MAX_TOKENIZER_BYTES
    )
    executable_snapshot = _snapshot(args.llama_tokenize, max_bytes=128 * 1024 * 1024)
    dynamic_dependencies = _dynamic_dependency_receipts(
        executable_snapshot.path, timeout_seconds=args.timeout_seconds
    )
    model_receipt = _stat_receipt(args.model)
    try:
        from tokenizers import Tokenizer
        from tokenizers import __version__ as tokenizers_version
    except ImportError as exc:
        raise AuditError("the pinned Python 'tokenizers' package is required") from exc
    tokenizer = Tokenizer.from_str(tokenizer_snapshot.data.decode("utf-8"))

    corpus_results: dict[str, Any] = {}
    for name, path in named_corpora:
        snapshot = _snapshot(path, max_bytes=MAX_CORPUS_BYTES)
        corpus_results[name] = _corpus_result(
            tokenizer,
            snapshot,
            executable_snapshot.path,
            Path(model_receipt["path"]),
            args.timeout_seconds,
            args.prefix_tokens,
            None,
        )

    fuzz_cases = _fuzz_cases(args.fuzz_cases, args.fuzz_seed)
    if any(SEPARATOR in case for case in fuzz_cases):
        raise AuditError("fuzz case unexpectedly contains the separator special token")
    fuzz_prompt = SEPARATOR.join(fuzz_cases).encode("utf-8")
    # Encode the exact joined byte sequence with both engines. The special-token
    # separator prevents a BPE merge from spanning cases while retaining each
    # implementation's own byte-level boundary semantics.
    official_fuzz = tokenizer.encode(
        fuzz_prompt.decode("utf-8"), add_special_tokens=False
    ).ids
    runtime_fuzz, fuzz_call = _run_llama_tokenize(
        executable_snapshot.path,
        Path(model_receipt["path"]),
        fuzz_prompt,
        pre_type=None,
        timeout_seconds=args.timeout_seconds,
    )
    fuzz_result = {
        "seed": args.fuzz_seed,
        "case_count": len(fuzz_cases),
        "joined_input_bytes": len(fuzz_prompt),
        "separator": SEPARATOR,
        "official_token_count": len(official_fuzz),
        "runtime_token_count": len(runtime_fuzz),
        "official_token_ids_sha256": _ids_sha256(official_fuzz),
        "runtime_token_ids_sha256": _ids_sha256(runtime_fuzz),
        "exact_match": official_fuzz == runtime_fuzz,
        "mismatch_count": 0 if official_fuzz == runtime_fuzz else 1,
        "call": fuzz_call,
    }

    all_exact = (
        all(item["exact_match"] for item in corpus_results.values())
        and fuzz_result["exact_match"]
    )
    receipt = {
        "schema_version": "motif3-official-tokenizer-parity-receipt-v1",
        "status": "pass" if all_exact else "fail",
        "authority": "offline_token_id_comparison",
        "auditor": {
            "path": str(auditor_snapshot.path),
            "size_bytes": auditor_snapshot.size,
            "sha256": auditor_snapshot.sha256,
        },
        "official_tokenizer": {
            "path": str(tokenizer_snapshot.path),
            "size_bytes": tokenizer_snapshot.size,
            "sha256": tokenizer_snapshot.sha256,
            "python_package": "tokenizers",
            "python_package_version": tokenizers_version,
        },
        "runtime": {
            "required_pre_type": "motif3",
            "override_applied_for_audit": False,
            "embedded_pre_type_exercised": True,
            "executable": {
                "path": str(executable_snapshot.path),
                "size_bytes": executable_snapshot.size,
                "sha256": executable_snapshot.sha256,
            },
            "dynamic_dependencies": dynamic_dependencies,
            "model": model_receipt,
            "model_payload_loaded": False,
        },
        "corpora": corpus_results,
        "adversarial_fuzz": fuzz_result,
        "all_official_runtime_token_ids_exact": all_exact,
        "limitations": [
            "The runtime was exercised without a tokenizer.ggml.pre override; parity therefore depends on the GGUF's embedded tokenizer metadata.",
            "This receipt proves tokenizer parity only; it is not model-quality or runtime-performance evidence.",
        ],
    }
    raw_receipt = _canonical_bytes(receipt)
    if args.output is None:
        sys.stdout.buffer.write(raw_receipt)
    else:
        _write_new(args.output, raw_receipt)
        print(f"PASS_MOTIF3_TOKENIZER_PARITY {args.output.absolute()}")
    return 0 if all_exact else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
