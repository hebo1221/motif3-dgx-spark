# Results and limits

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

This is the result I would not hide behind the systems numbers: the model fits,
but this quant did not stay close enough to the BF16 output distribution to
pass either gate.

## Diagnostic task results

These are fixed internal diagnostic sets, not public leaderboard scores. They
are provided only to characterize this artifact.

| Diagnostic | Passed | Rate |
|---|---:|---:|
| Korean knowledge/reasoning | 212 / 300 | 70.67% |
| General knowledge/reasoning | 149 / 180 | 82.78% |
| Raw strict tool episodes | 12 / 30 | 40.00% |
| Schema-gated tool episodes | 17 / 30 | 56.67% |

All 540 stored responses behind these four rows replayed exactly with the
current v2 scorer and request-binding checks. The aggregate receipt hashes are
in [`public_metrics.json`](../evidence/public_metrics.json). Raw cases and
responses are not redistributed, and the original task processes did not
capture a full runtime-mapped-library receipt, so these remain diagnostics
rather than a publication-grade BF16 comparison.

## DGX Spark performance

### Clean public-runtime run

After publishing the exact runtime commit, I rebuilt from that clean tree and
ran five repetitions per shape. These are means across the five repetitions;
the full arrays are in
[`../evidence/clean_runtime_benchmark.jsonl`](../evidence/clean_runtime_benchmark.jsonl).

| Shape | Mean tok/s | Repetition standard deviation |
|---|---:|---:|
| pp512 | 316.71 | 3.30 |
| pp2048 | 312.76 | 0.96 |
| tg128 | 16.49 | 0.024 |
| pp2048 + tg128 | 149.33 | 0.076 |

The same build also loaded the model through `llama-server`, reported one
healthy slot, and completed a real Korean Chat Completions request. See the
[clean runtime receipt](../evidence/clean_runtime_verification.json).

### Earlier three-session campaign

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
runs before the clean public branch was cut. The table reports the median
session mean and the range across sessions. It is a useful stability check, not
a replacement for the clean-build run above.

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
