# Motif-3 on One DGX Spark

This repository documents an attempt to run
[Motif-3](https://huggingface.co/Motif-Technologies/Motif-3), a 314.7B
parameter sparse MoE model, on one NVIDIA DGX Spark.

The useful outcome is a reproducible deployment point and a well-instrumented
negative result: direct BF16-to-IQ2_XXS makes the model fit and run, but the
measured quality loss is too large to describe the quantization as lossless.

## Headline result

| Item | Result |
|---|---:|
| Source | official BF16, commit `883d5c441fe3bb994c7b57e60f49e26147f85512` |
| Parameters | 314,701,772,930 |
| GGUF size | 89,720,474,560 bytes / 83.56 GiB |
| Effective storage | 2.2805 bits/element |
| DGX Spark pp512 | 313.41 tok/s |
| DGX Spark pp2048 | 310.67 tok/s |
| DGX Spark tg128 | 16.39 tok/s |
| Peak GPU/UMA allocation | 85,713 MiB |
| BF16-relative perplexity | 1.4115x |
| Mean BF16-to-IQ2 KL | 0.4541 |

Performance values are medians of three separate session means; each session
used five benchmark repetitions. See [Results](docs/RESULTS.md) for the exact
protocol and limitations.

## What is being released

1. A direct-from-BF16 mixed IQ2_XXS GGUF on Hugging Face.
2. Exact size and SHA-256 receipts for that artifact.
3. A llama.cpp-compatible Motif-3 chat template.
4. Aggregate-only evaluation evidence.
5. A short account of three higher-precision repair strategies that failed
   task or runtime gates.

The model file is not "pure 2-bit." Large routed-expert tensors are IQ2_XXS,
while sensitive tensors remain BF16, F32, Q2_K, or Q8_0. The aggregate payload
is 2.2805 bits per element.

## Start here

- [Method](docs/METHOD.md)
- [Results and limitations](docs/RESULTS.md)
- [What did not work](docs/NEGATIVE_RESULTS.md)
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

## Why publish a negative result?

The failed experiments narrow the design space. Generic teacher KL did not
predict tool behavior, large expert overlays were expensive at runtime, and a
tiny terminal correction improved Korean MCQ while significantly regressing
tool use. These are useful constraints for anyone attempting ultra-low-bit MoE
deployment on unified-memory hardware.

## License and attribution

Repository code and original documentation are MIT licensed. The derived model
follows the upstream Motif-3 MIT license and retains upstream attribution. See
[NOTICE](NOTICE.md). This repository is an independent community effort and is
not affiliated with Motif Technologies or NVIDIA.
