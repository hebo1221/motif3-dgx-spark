# Runtime and reproduction

## Runtime status

Motif-3 support is not present in stock upstream llama.cpp at the time of this
release candidate. The public starting points are:

- <https://github.com/timkhronos/llama.cpp/tree/Motif3>
- <https://github.com/ggml-org/llama.cpp/pull/26404>

The measured local build was based on commit
`7e6b0d32d6a42aba7431e334a8848e4fd10711f6` and included additional local
changes. Until an exact clean runtime branch is published, the performance
figures should be read as bound experimental observations rather than a claim
that any current checkout reproduces them bit-for-bit.

## Representative benchmark settings

With a compatible build:

```bash
llama-bench \
  -m /path/to/motif3-direct-iq2xxs.gguf \
  -ngl 99 \
  -fa on \
  -ctk f16 \
  -ctv f16 \
  -b 2048 \
  -ub 512 \
  -t 20 \
  -p 512,2048 \
  -n 128 \
  -r 5 \
  -o jsonl
```

Run model-load benchmarks only during a maintenance window. One loaded model
uses roughly 86 GiB of the DGX Spark unified memory pool, so a second concurrent
load is unsafe.

## Representative server settings

```bash
llama-server \
  -m /path/to/motif3-direct-iq2xxs.gguf \
  -ngl 99 \
  -fa on \
  -ctk f16 \
  -ctv f16 \
  -b 2048 \
  -ub 512 \
  -c 32768 \
  -np 1 \
  --jinja \
  --chat-template-file /path/to/motif3-llama.cpp.jinja
```

Check `/props` or `/slots` after startup. `-c` is a total context budget and is
split among parallel slots.

## Tool calling

The included template can render tools, but the model is unreliable in `auto`
mode at this quantization. Use deterministic schema validation and treat
`required` or named-tool forcing as a downstream policy decision, not as a
substitute for tool applicability classification.

## Verification

Verify the model before loading it:

```bash
sha256sum motif3-direct-iq2xxs.gguf
```

Expected digest:

```text
9d6f7aee57f0271223f51d69c63d8576a259809e9f05e2ac596512e940c80c5a
```
