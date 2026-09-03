# Motif-3 315B on One DGX Spark

**314.7B total parameters. 83.56 GiB. 16.39 tokens/s generation. One DGX
Spark.**

This repository documents a working single-system deployment of
[Motif-3](https://huggingface.co/Motif-Technologies/Motif-3), a 314.7B
parameter sparse MoE model, on one NVIDIA DGX Spark.

Starting from the official BF16 weights, the full core model was converted
directly to a mixed IQ2_XXS GGUF that fits in the Spark unified-memory budget.
The release includes exact provenance, a Motif-compatible runtime path, and
controlled performance measurements.

## At a glance

| Item | Result |
|---|---:|
| Source | official BF16, commit `883d5c441fe3bb994c7b57e60f49e26147f85512` |
| Parameters | 314,701,772,930 |
| GGUF size | 89,720,474,560 bytes / 83.56 GiB |
| BF16-to-GGUF reduction | 7.02x smaller / 85.75% fewer bytes |
| Effective storage | 2.2805 bits/element |
| DGX Spark pp512 | 313.41 tok/s |
| DGX Spark pp2048 | 310.67 tok/s |
| DGX Spark tg128 | 16.39 tok/s |
| Peak GPU/UMA allocation | 85,713 MiB |

Performance values are medians of three separate session means; each session
used five benchmark repetitions. See [Results](docs/RESULTS.md) for the exact
protocol and limitations.

## Engineering highlights

- **Direct BF16 path:** no Q5 or other lower-precision intermediate.
- **All layers on GPU:** the 83.56 GiB GGUF leaves enough unified-memory room
  for runtime state and a useful context window.
- **Motif-aware mixed precision:** routed experts carry most of the compression
  while embeddings, output, attention, routing, and control tensors retain the
  precision appropriate to their role.
- **GQA-5 Flash Attention path:** measured with the public Motif port plus the
  open GQA-5 Flash Attention work.
- **Reproducible evidence:** full model SHA-256, source-shard binding, tensor
  inventory, five-repeat benchmarks, and UMA telemetry.
- **Actionable research record:** small terminal corrections, causal Q8
  restoration, and expert-level allocation were evaluated against the same
  deployable baseline.

## What is being released

1. A direct-from-BF16 mixed IQ2_XXS GGUF on Hugging Face.
2. Exact size and SHA-256 receipts for that artifact.
3. A llama.cpp-compatible Motif-3 chat template.
4. Aggregate-only evaluation evidence.
5. Engineering findings from three higher-precision repair strategies.

The model file is not "pure 2-bit." Large routed-expert tensors are IQ2_XXS,
while sensitive tensors remain BF16, F32, Q2_K, or Q8_0. The aggregate payload
is 2.2805 bits per element.

## Start here

- [Method](docs/METHOD.md)
- [Results and limitations](docs/RESULTS.md)
- [Engineering findings](docs/ENGINEERING_FINDINGS.md)
- [Runtime and reproduction](docs/RUNTIME.md)
- [Public machine-readable metrics](evidence/public_metrics.json)

## Important boundaries

- This artifact omits the native MTP head and has no measured speculative
  decoding benefit.
- The parent model supports 256K context, but this release does not claim
  retained 256K quality.
- Tool calling is fragile at this quantization level. Parser/schema gating can
  improve formatting but does not restore the model's call/no-call policy.
- Diagnostic task sets are aggregate-only and must not be compared with public
  leaderboard numbers.
- The exact tested llama.cpp build included Motif-3 and GQA-5 Flash Attention
  work that is not yet merged upstream. See the runtime document.

## Evaluation transparency

Ultra-low-bit deployment has real quality trade-offs. A held-out BF16
comparison measured 1.4115x perplexity and 0.4541 mean KL, so this is not
advertised as lossless or BF16-equivalent. The full measurement and task
boundaries are preserved in the results document without displacing the main
systems achievement.

## License and attribution

Repository code and original documentation are MIT licensed. The derived model
follows the upstream Motif-3 MIT license and retains upstream attribution. See
[NOTICE](NOTICE.md). This repository is an independent community effort and is
not affiliated with Motif Technologies or NVIDIA.
