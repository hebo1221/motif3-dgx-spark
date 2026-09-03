# Runtime notes

## Use this commit, not stock llama.cpp

As of this release, upstream llama.cpp does not contain the complete path this
GGUF needs. A stock checkout stops while reading the vocabulary with
`unknown pre-tokenizer type: 'motif3'`.

The runtime I tested is:

- repository: <https://github.com/hebo1221/llama.cpp>;
- branch: `motif3-dgx-spark-v1`;
- tag: `motif3-dgx-spark-runtime-v1.0.0`;
- commit:
  [`cc3f13b3f172978d7b3c215780d4cc98bb0e1c80`](https://github.com/hebo1221/llama.cpp/commit/cc3f13b3f172978d7b3c215780d4cc98bb0e1c80).

That commit sits on top of the public Motif-3 model port and the GQA-5 Flash
Attention merge used during the project. It adds the missing official Motif-3
tokenizer behavior and its Unicode regression tests.

The related upstream work is still visible here:

- <https://github.com/timkhronos/llama.cpp/tree/Motif3>
- <https://github.com/ggml-org/llama.cpp/pull/26404>

## Build

```bash
git clone --branch motif3-dgx-spark-v1 --single-branch \
  https://github.com/hebo1221/llama.cpp.git runtime

git -C runtime checkout cc3f13b3f172978d7b3c215780d4cc98bb0e1c80

cmake -S runtime -B runtime/build \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_CUDA=ON \
  -DGGML_CUDA_FA=ON \
  -DGGML_CUDA_GRAPHS=ON \
  -DGGML_NATIVE=ON \
  -DLLAMA_BUILD_UI=OFF \
  -DLLAMA_USE_PREBUILT_UI=OFF

cmake --build runtime/build --target llama-server llama-bench -j 12
```

The verified build was a native aarch64 Release build on DGX Spark with CUDA
13.0.88 and NVIDIA driver 580.126.09. `GGML_NATIVE=ON` means a binary built on
another CPU is not expected to be byte-identical.

## Server command

```bash
runtime/build/bin/llama-server \
  -m model/motif3-direct-iq2xxs.gguf \
  -ngl 99 \
  -fa on \
  -ctk f16 \
  -ctv f16 \
  -b 2048 \
  -ub 512 \
  -c 32768 \
  -np 1 \
  --host 127.0.0.1 \
  --port 8080 \
  --no-ui \
  --jinja \
  --chat-template-file model/motif3-llama.cpp.jinja
```

The first load takes time because the file is nearly 90 GB. Do not call that a
cold-start benchmark unless the OS page cache and storage state were actually
controlled.

Wait for the server to report that the model is loaded, then check:

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/slots
```

The clean-build smoke test used one slot and a small 1,024-token context to
keep the test narrow. It returned HTTP 200, reported
`b10498-cc3f13b3f`, and completed a real Korean Chat Completions request. The
receipt is
[`../evidence/clean_runtime_verification.json`](../evidence/clean_runtime_verification.json).

## Context is shared between slots

`-c` is the total context budget, not a promise for every request. For example,
a 65,536-token launch with three slots produced about 22K tokens per slot.

For one long request, use `-np 1`. For throughput, increase `-np`, then inspect
`/slots` and make sure each slot still has enough room for its prompt and
output. Do not infer 256K quality from a successful allocation alone.

## Memory

The controlled campaign observed 85,713 MiB peak NVIDIA process allocation for
the baseline configuration. On DGX Spark, GPU and system memory share the same
pool. Process RSS by itself badly undercounts the loaded model, and the usual
discrete-GPU free-VRAM number is not enough either.

Before loading the model:

- stop any other process using a large part of the unified pool;
- leave room for KV cache, CUDA graphs, and temporary buffers;
- avoid starting a second `llama-bench` while the server already holds the
  model.

## Benchmark command

```bash
runtime/build/bin/llama-bench \
  -m model/motif3-direct-iq2xxs.gguf \
  -ngl 99 -fa on \
  -ctk f16 -ctv f16 \
  -b 2048 -ub 512 -t 20 \
  --delay 3 \
  -p 512,2048 \
  -n 128 \
  -pg 2048,128 \
  -r 5 \
  -o jsonl
```

The `tg128` result measures shallow generation. It is not the decode rate at
32K, 64K, or 164K context depth. Report the prompt depth whenever comparing
decode numbers.

## Tokenizer check

The final GGUF embeds `tokenizer.ggml.pre=motif3`; no command-line override is
needed. Using this exact runtime and the embedded metadata, token IDs matched
the official tokenizer for:

- 61,548 calibration tokens;
- 54,070 held-out tokens;
- 318,951 tokens from 12,011 deterministic Unicode and formatting cases.

That is strong evidence for the tested inputs, but not a mathematical proof for
every Unicode string. The aggregate receipt is
[`../evidence/tokenizer_parity.json`](../evidence/tokenizer_parity.json).
The audit code itself is also included as
[`../scripts/audit_tokenizer_parity.py`](../scripts/audit_tokenizer_parity.py);
the private evaluation text is not redistributed.

## Tool calling

The included template renders tools and parallel calls. At this quantization,
however, `auto` tool choice remains unreliable. A strict schema can catch bad
JSON; it cannot tell whether the model should have called a tool in the first
place.

If tools matter to your application, keep the decision and validation layers
separate:

1. decide whether a tool is applicable;
2. validate the selected tool name and arguments;
3. reject or ask for clarification when required fields are missing;
4. treat parser repair as recovery, not as evidence that the original call was
   correct.

## Troubleshooting

`unknown pre-tokenizer type: 'motif3'`
: You built the wrong llama.cpp revision. Check that `git rev-parse HEAD` is
  `cc3f13b3f172978d7b3c215780d4cc98bb0e1c80`.

The server runs out of memory during load
: Stop other GPU workloads, lower `-c`, keep `-np 1`, and confirm all paths
  point to the same single model process.

The template fails to render
: Use the companion `motif3-llama.cpp.jinja` from the pinned model revision and
  keep `--jinja` enabled.

Generation becomes slower at long context
: That is expected. The headline `tg128` figure is a shallow decode result, not
  a long-context guarantee.
