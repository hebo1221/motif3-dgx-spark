# Batch-consistency probes and a bounded document agent

**Experimental source and evidence release · v1.3.0-rc.1 · one NVIDIA GB10**

This follow-up makes two parts of the Motif work reusable: a model-free Q8_0
matrix probe with a small reference patch, and a local document agent that
binds the question to a project and shows the actual source passages.
The recorded failures are included. This is not a new model upload, a BF16
quality-preservation result, or an autonomous-agent qualification.

## Start here

- [Numerical probes and build instructions](runtime/README.md): investigate
  differences between single-column and batched execution without downloading
  Motif. The optional reference path favors comparable arithmetic over speed.
- [Document agent usage](USAGE.md): use a local native-tool endpoint, index
  Markdown documents, and render an answer alongside its source passages.
- [Case-by-case review](REVIEW.ko.md), [method](EVALUATION.ko.md), and
  [actual answer examples](examples/README.ko.md): inspect both useful answers
  and failures.
- [Publication provenance](PUBLICATION.md): understand which hashes describe
  original records and which describe the public, redacted copies.

## What was measured

| Scope | Observation |
|---|---|
| Q8_0 matrices, 3 shapes × widths 2 and 4 | Both the small opt-in reference and existing optimized Motif paths matched all **147,456** single-column reference values bit for bit |
| Small reference patch, ordinary path | Output fingerprints unchanged in all 9 shape/width combinations; restored original library also matched |
| Small reference patch, compute microbenchmark | **1.92–5.18× longer** than the ordinary batched path in supported cases; not a speed optimization |
| Width 8 control | Outside the patch's supported scope; original numerical differences remain |
| Qwen3-8B Q8_0, 3 fixed traces × 48 positions | Batched logits differed, but **zero argmax differences** at widths 2, 4, and 8 in each runtime arm |
| Final Python client | **30 boundary tests** passed on Mac and Spark; 17 completed prior tasks replayed unchanged without new model calls |

The Qwen trace experiment compares the original runtime, the existing Motif
runtime, and the restored original. It does not run MTP and does not establish
a whole-model fix from the new small reference patch. Matrix timings exclude
allocation and input/output copies. See the raw JSON under `evidence/`.

## Tool validity is not answer correctness

Eight questions about five real project reports were frozen before the v3
comparison. An assistant authored the questions and reviewed the answers
against the frozen criteria. The aggregation into PASS/PARTIAL/FAIL was made
after reading the responses; it was not a blind or independent human study.

| Exploratory v3 review, 8 questions | Motif IQ2 + MTP 1 | Qwen3-8B Q8_0 |
|---|---:|---:|
| Valid reports produced | 7 | 8 |
| All requested explanation criteria met | 4 | 0 |
| Partial coverage | 3 | 3 |
| Failure | 1, step budget exhausted | 5, materially wrong or unsupported conclusions |
| Median task time, excluding model startup | 70.04 s | 16.52 s |

Zero full passes does **not** mean every Qwen statement was false. Several
answers omitted requested details. Other answers made substantive errors,
including confusing within-runtime token parity with equality between two
different models. Motif distinguished several of these limits more accurately,
but missed details and failed to finish one task. These closely related
questions are not a general model ranking or a population success estimate.

The final v4 client reserves its last step for a report or an honest lack-of-
evidence response. In known-case rechecks, both models answered the previously
confused project correctly. Motif still repeated an unfinished report in
another task and confused the 629.69 GB BF16 reference with the 89.72 GB IQ2
file in a completed answer. Those failures remain FAIL. The v3 scores and the
older 99/100 Motif result are not rewritten after repairs.

## Release scope

The agent and numerical probe source bytes match the recorded versions. The
two-file Q8 reference patch reproduces the measured candidate source on the
pinned public base. The optional parser patches are included separately; one
unrelated historical thinking-flag hunk was removed from the Qwen patch, while
its Qwen function and registration remain source-identical.

The recorded CUDA build reused existing objects and recompiled one translation
unit. A fresh full CMake build, different GPUs, arbitrary tensor strides,
general speculative decoding, and BF16 task-quality preservation are not
validated by this release. The model weights and MTP sidecar are not included.

Private paths, device UUIDs, and task IDs were redacted. Public document indexes
bind the redacted copies. Historical hashes inside imported receipts still
identify the original recorded bytes; they are not checksums for the redacted
files. A new run on these public documents is a new experiment, not a replay
guaranteed to reproduce the recorded model answers.

[한국어 결과](README.ko.md) · [한국어 사용법](USAGE.ko.md)
