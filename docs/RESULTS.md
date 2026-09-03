# Results and limitations

## Artifact

| Field | Value |
|---|---|
| Filename | `motif3-direct-iq2xxs.gguf` |
| Size | 89,720,474,560 bytes (83.56 GiB) |
| SHA-256 | `9d6f7aee57f0271223f51d69c63d8576a259809e9f05e2ac596512e940c80c5a` |
| GGUF | v3, file type 19 / mixed IQ2_XXS |
| Effective bits per element | 2.2805296 |
| Native MTP | not included |

## Distributional quality

The official Motif tokenizer produced a fixed 49,152-token evaluation
sequence. Comparing BF16 teacher logits with the direct IQ2 artifact gave:

| Metric | Value | Prespecified gate | Result |
|---|---:|---:|---|
| Mean perplexity ratio | 1.411541 +/- 0.010497 | <= 1.10 | fail |
| Mean KL divergence | 0.454130 +/- 0.004009 | <= 0.10 | fail |

This is the most important quality statement in the release: fitting in memory
did not preserve the BF16 distribution closely enough.

## Diagnostic task results

These are fixed internal diagnostic sets, not public leaderboard scores. They
are provided only to characterize this artifact.

| Diagnostic | Passed | Rate |
|---|---:|---:|
| Korean knowledge/reasoning | 212 / 300 | 70.67% |
| General knowledge/reasoning | 149 / 180 | 82.78% |
| Raw strict tool episodes | 12 / 30 | 40.00% |
| Schema-gated tool episodes | 17 / 30 | 56.67% |

All stored scores used in the final comparison replayed exactly against their
bound case/scorer sources. The original task processes did not capture a full
runtime-mapped-library receipt, so these rows remain diagnostics rather than a
publication-grade BF16 comparison.

## Controlled DGX Spark performance

Configuration:

- NVIDIA GB10 / DGX Spark unified memory;
- all model layers offloaded to GPU;
- Flash Attention enabled;
- F16 K/V cache;
- batch 2,048 and micro-batch 512;
- 20 CPU threads;
- five repetitions per benchmark session;
- three-second cool-off before each test.

Three separate baseline sessions were embedded in same-protocol candidate A/B
runs. The table reports the median session mean and the range across sessions.

| Shape | Median tok/s | Session range |
|---|---:|---:|
| pp512 | 313.41 | 307.46-314.26 |
| pp2048 | 310.67 | 310.16-310.90 |
| tg128 | 16.39 | 16.28-16.40 |
| pp2048 + tg128 | 148.34 | 147.83-148.53 |

Peak reported GPU/UMA allocation was 85,713 MiB. On DGX Spark, process RSS
alone substantially undercounts model allocation; measurements combined
NVIDIA process allocation with Linux memory telemetry.

## Context and concurrency warning

In llama.cpp server mode, total context is divided between parallel slots. A
launch with total context 65,536 and three slots produced about 22K tokens per
slot, not 65K per request. Use one slot for single-request long-context work
and verify the server's reported per-slot context before testing.

The parent model advertises 256K context. This artifact has been made to run at
large context depths, but this release does not establish retained retrieval
or generation quality at 256K.

## Claims intentionally not made

- lossless or near-lossless quantization;
- pure 2-bit storage;
- SOTA quality or speed;
- BF16-equivalent tool calling;
- native MTP/speculative decoding;
- 256K quality retention;
- portability to unmodified upstream llama.cpp.
