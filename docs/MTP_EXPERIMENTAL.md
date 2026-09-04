# Experimental native MTP follow-up

This is a source-and-evidence release for Motif-3's one-layer multi-token
prediction (MTP) head. It is separate from the downloadable 83.56 GiB GGUF:
the public model file is unchanged, and no MTP weights are redistributed here.

On one NVIDIA DGX Spark, an isolated build on the pinned runtime base produced
the same 5,120 greedy target tokens with MTP enabled and disabled. A fresh
target-only recovery arm reproduced the same 5,120 tokens again. Across those
five workloads, server-reported decode rose from a counterbalanced target mean
of 14.5872 tok/s to 17.5565 tok/s, or **1.2036x**.

This is encouraging, but deliberately narrow evidence. The target used for
this experiment has SHA-256
`dff7f7db077364a3eb0164224f7384b5fbb36d11f9e905d921f15874f6ffcab9`.
It is not byte-identical to the GGUF currently downloadable from this project's
Hugging Face repository. The result therefore does not establish MTP speed or
compatibility for that public GGUF.

## What had to be fixed

The patch is more than a converter switch. It adds the model graph and closes
several runtime mismatches that appeared only when Motif's MTP head met a
quantized sparse-MoE target on GB10:

- converts the official one-layer head into a linked 19-tensor BF16 sidecar;
- reuses the target embedding, output norm, and language-model head instead of
  duplicating about 3.6 GB of BF16 tensors;
- fuses the main model's post-final-norm hidden state with the normalized next
  token embedding, matching Motif's published implementation;
- keeps the Motif sidecar's sliding-window cache independent from the target
  cache and removes a stale draft row before the next step;
- requires exact target/draft vocabulary size, token text, and token
  attributes; and
- keeps multi-token speculative verification on arithmetic paths that match
  ordinary one-token decode for the tested IQ2_XXS, Q2_K, Q8_0, GQA-5, and
  GQA-80 GB10 shapes.

The last point matters here: target verification is mathematically equivalent
at the model level, but different CUDA reduction shapes can still select a
different top token when logits are close. The guarded batch-invariance work is
what made the frozen target tokens recover exactly in this environment.

## Result

The fixed arm order was target-only, target plus MTP, then a new target-only
process. Five Korean prompts were rendered to input depths 128, 512, 2,048,
8,192, and 16,000. Every arm generated 1,024 greedy tokens per prompt.

| Metric | Result |
|---|---:|
| Target/MTP token agreement | 5,120 / 5,120 |
| Fresh target recovery | 5,120 / 5,120 |
| Target before | 14.5966 tok/s |
| MTP | 17.5565 tok/s |
| Target after | 14.5778 tok/s |
| Counterbalanced target mean | 14.5872 tok/s |
| MTP / target mean | **1.2036x** |
| Target-baseline absolute drift | 0.129% |
| Draft acceptance | 2,993 / 6,353 (47.11%) |

The aggregate-only receipt is
[`../evidence/mtp_full_aba_v1/summary.public.json`](../evidence/mtp_full_aba_v1/summary.public.json).
Its bundle manifest is
[`../evidence/mtp_full_aba_v1/bundle_manifest.json`](../evidence/mtp_full_aba_v1/bundle_manifest.json),
and exact build inputs and focused test counts are in
[`../evidence/mtp_runtime_build_receipt_v1.json`](../evidence/mtp_runtime_build_receipt_v1.json).
The raw receipt is withheld because it contains prompts, token arrays, local
paths, ports, and process identifiers.

## Apply and build

Both patches apply to runtime commit
`cc3f13b3f172978d7b3c215780d4cc98bb0e1c80`. The tokenizer patch can be
applied first; the three-patch sequence was checked together from a fresh
worktree.

```bash
git clone --branch motif3-dgx-spark-v1 --single-branch \
  https://github.com/hebo1221/llama.cpp.git runtime
git -C runtime checkout cc3f13b3f172978d7b3c215780d4cc98bb0e1c80

git clone --branch v1.2.0 --depth 1 \
  https://github.com/hebo1221/motif3-dgx-spark.git release-files

git -C runtime apply --check --unidiff-zero \
  ../release-files/patches/motif3-tokenizer-exact-v1.patch
git -C runtime apply --unidiff-zero \
  ../release-files/patches/motif3-tokenizer-exact-v1.patch
git -C runtime apply --check \
  ../release-files/patches/llama-cpp-motif3-mtp-runtime-v1.patch
git -C runtime apply \
  ../release-files/patches/llama-cpp-motif3-mtp-runtime-v1.patch

cmake -S runtime -B runtime/build \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_CUDA=ON \
  -DGGML_CUDA_FA=ON \
  -DGGML_CUDA_GRAPHS=ON \
  -DGGML_NATIVE=ON \
  -DLLAMA_BUILD_UI=OFF \
  -DLLAMA_USE_PREBUILT_UI=OFF
cmake --build runtime/build --target llama-server test-motif3-mtp -j 12
ctest --test-dir runtime/build -R '^test-motif3-mtp$' --output-on-failure
```

The optional
[`batch-invariance diagnostic patch`](../patches/llama-cpp-motif3-mtp-batch-invariance-diagnostic-v1.patch)
adds the investigation executable; it is not required for normal serving.

## Build a sidecar from the official checkpoint

The MTP private tensors are all in shard 104 of the official checkpoint at
revision `883d5c441fe3bb994c7b57e60f49e26147f85512`. Downloading only the model
configuration, tokenizer files, template, and that shard is about 2.20 GiB.

Do not place the full `model.safetensors.index.json` inside this sparse source
directory: the generic loader will then require all 155 shards. Keep the index
separately if you need it as a provenance receipt.

```bash
MOTIF_REV=883d5c441fe3bb994c7b57e60f49e26147f85512
mkdir -p motif-mtp-source

hf download Motif-Technologies/Motif-3 \
  config.json tokenizer.json tokenizer_config.json chat_template.jinja \
  model-00104-of-00155.safetensors \
  --revision "$MOTIF_REV" \
  --local-dir motif-mtp-source \
  --max-workers 2

printf '%s  %s\n' \
  2153498182d0d827f9baea953fa5c3ca4b7ea256ff514c5440cbcf0b2278cd50 \
  motif-mtp-source/model-00104-of-00155.safetensors | sha256sum -c -

PYTHONPATH=runtime/gguf-py python3 runtime/convert_hf_to_gguf.py \
  motif-mtp-source \
  --mtp \
  --outtype bf16 \
  --outfile motif3-mtp-linked-bf16.gguf

PYTHONPATH=runtime/gguf-py python3 \
  release-files/scripts/check_motif3_mtp_sidecar.py \
  --gguf motif3-mtp-linked-bf16.gguf \
  --target-gguf /path/to/exact-target.gguf \
  --full-sha256
```

The checker expects exactly 19 private MTP tensors, 54 total logical blocks,
one next-token layer, the pinned Motif runtime metadata, a 220,160-token
vocabulary, and target-shared tensor shapes. Its JSON output contains local
paths, so redact or sanitize it before sharing.

## Run experimentally

Use a local-only listener and start with one slot. The standard llama.cpp draft
arguments activate the linked sidecar:

```bash
runtime/build/bin/llama-server \
  --model /path/to/exact-target.gguf \
  --model-draft motif3-mtp-linked-bf16.gguf \
  --spec-type draft-mtp \
  --spec-draft-n-max 3 \
  --gpu-layers 99 \
  --gpu-layers-draft 99 \
  --flash-attn on \
  --cache-type-k f16 \
  --cache-type-v f16 \
  --ctx-size 32768 \
  --parallel 1 \
  --host 127.0.0.1 \
  --port 8080
```

Before trusting throughput, compare forced-greedy token IDs with MTP on and off
and confirm that responses include nonzero `draft_n` and
`draft_n_accepted`. A result that merely starts successfully is not a parity or
speed result.

## Boundaries

- The downloadable project GGUF remains unchanged and contains no MTP head.
- The sidecar weights are not redistributed in this release.
- This does not improve the target model's IQ2 quality; accepted draft tokens
  are still verified by the target.
- The 1.2036x value is one GB10, one exact target, five frozen workloads, and
  server-reported decode timing—not HTTP TTFT, tail latency, or concurrency.
- Peak unified-memory overhead and concurrency 3 are not measured yet.
- The MTP-focused tests passed, but this is not a claim that the fork's entire
  historical test matrix is clean or that other GPUs are regression-free.
- The patch has not been submitted upstream and should remain opt-in while its
  CUDA paths receive broader review.
