# Fitting 315B parameters into one DGX Spark

[한국어](CASE_STUDY.ko.md) · [Recorded answer tour](RECORDED_DEMO.md) · [Repository](../README.md)

**83.56 GiB · 16.49 tokens/s generation · one 128 GB DGX Spark.**

The first goal was to run Motif-3's 314.7B-parameter sparse-MoE core on one
128 GB Spark. The mixed-precision GGUF fits, with all 54 layers on the GPU.
The speeds above come from the pinned runtime before the tokenizer-exact patch;
83.56 GiB is the model file size.

Getting it to load left more to investigate. The tokenizer needed corrections,
batched verification could change selected tokens, and a document agent could
quote the right passage while giving the wrong number. The quant also failed
its BF16 quality-retention gates.

This is a record of those problems and the code used to check them. To try the
model, use the [pinned build](../README.md#download-and-run). To inspect an answer
first, open the [recorded examples](RECORDED_DEMO.md).

## 1. Make the memory budget real

The source contained 155 official BF16 shards totaling 629.68 GB. The chosen
route was BF16 → BF16 GGUF → mixed IQ2_XXS, avoiding an intermediate lower-
precision model. Most routed-expert storage uses IQ2_XXS; other tensor families
retain higher precision. Effective storage is 2.2805 bits per element.

The final 89,720,474,560-byte file is 83.56 GiB. All 54 layers loaded on the GPU,
the server passed its health and slot checks, and a real Korean chat request
completed. Five repetitions per benchmark shape on the clean published runtime
averaged 316.71 tokens/s for pp512 and 16.49 tokens/s for tg128.

These speeds belong to the pinned runtime base before the tokenizer-exact
patch. The file size is not total process memory. The earlier three-session
campaign recorded peak GPU/UMA allocation of 85,713 MiB, separately from the
clean-build speed measurements.

Inspect: [conversion method](METHOD.md), [raw benchmark rows](../evidence/clean_runtime_benchmark.jsonl),
[load and request receipt](../evidence/clean_runtime_verification.json),
[metrics and tensor inventory](../evidence/public_metrics.json).

## 2. Correct the input before interpreting the output

A model that loads can still receive the wrong token IDs. Motif's multi-word
splitting rules, Unicode categories, and added-token whitespace handling needed
explicit treatment in the runtime. The Motif-only patch implements those rules
and supplies regression coverage.

The final public GGUF matched **434,569 official token IDs** across two corpora
and deterministic fuzz cases. A source-identical tokenizer candidate matched
**4,164,390 IDs** in extended tests. The final patched public-runtime build also
passed all 16 regression tests. These are distinct verification scopes; the
extended count is not presented as another run of the final executable.

This removed an input-correctness gap. The IQ2 weight bytes did not change.

Inspect: [tokenizer patch](../patches/motif3-tokenizer-exact-v1.patch),
[verification receipt and scope](../evidence/tokenizer_exact_v1.json),
[parity audit tool](../scripts/audit_tokenizer_parity.py).

## 3. Measure acceleration against its own control

The native multi-token prediction experiment required a linked sidecar graph,
correct hidden-state handling, separate cache state, and exact vocabulary
checks. On GB10, batched speculative verification could also choose different
tokens because its arithmetic differed from ordinary one-token decoding.

A target → MTP → fresh target run tested both acceleration and recovery.
Across five workloads, all **5,120 generated tokens** matched in the MTP arm
and again in the recovery arm. Server-reported decode rose from **14.5872 to
17.5565 tokens/s (1.2036×)**.

This experiment used a target with different bytes from the downloadable GGUF.
The sidecar weights are not redistributed. Its speed numbers cannot be joined
to the 16.49 tokens/s headline as one before/after comparison.

The later model-free Q8 probe makes the arithmetic question easier to study:
147,456 values matched the single-column reference at tested widths 2 and 4.
The small opt-in reference patch took **1.92–5.18× longer** than the ordinary
path. Its value is a checkable correctness reference, with a measured cost.

Inspect: [MTP implementation and limitations](MTP_EXPERIMENTAL.md),
[MTP aggregate](../evidence/mtp_full_aba_v1/summary.public.json),
[reusable Q8 probe and patch](../experiments/value-v2/runtime/README.md).

## 4. Keep the failures visible

On a fixed 49,152-token held-out comparison, perplexity relative to BF16 was
**1.4115×** against a ≤1.10 gate, and mean KL was **0.4541** against a ≤0.10
gate. Both failed. Larger precision-restoration experiments consumed memory
and speed without enough task gain; a small correction regressed tool use.
None replaced the released baseline.

The document agent supplied another useful failure. It produced a complete
answer calling the BF16 source **89.72 GB**, even while quoting a passage that
said **629.69 GB**. It also attributed that passage to the wrong document.
Project matching, valid structured output, and authentic quotations did not
make the conclusion correct.

The [recorded answer tour](RECORDED_DEMO.md) shows this failure beside a useful
answer. Its offline verifier checks the record and source bindings; answer
correctness still requires reading the content. The small exploratory task
sets do not establish a general ranking of Motif against other models.

Inspect: [quality results](RESULTS.md), [rejected repairs](ENGINEERING_FINDINGS.md),
[agent evaluation and limitations](../experiments/value-v2/README.md).

## Contribution and reuse

Motif Technologies trained Motif-3. This project builds on llama.cpp,
Chrono's Motif port, and the cited GQA-5 work. The community contribution here
is the direct quantization release, Motif tokenizer correction, experimental
runtime patches, numerical probes, bounded agent client, and their evidence.
Development and analysis were assisted by Codex. Upstream work is credited in
[NOTICE](../NOTICE.md).

The reusable skills demonstrated are memory-constrained deployment, tokenizer
correctness, CUDA numerical diagnosis, controlled performance comparisons,
and evaluation that preserves failed outcomes. Each has a linked artifact
that can be inspected without trusting the headline.

For a quick review, start with [recorded answers](RECORDED_DEMO.md). For a
reproduction, use the [pinned build and download instructions](../README.md#download-and-run).
The research phase is complete. Reproduction fixes and independent results
follow the [maintenance and reopening criteria](PROJECT_STATUS.md).
