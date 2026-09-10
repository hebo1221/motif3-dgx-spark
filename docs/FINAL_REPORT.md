# Motif-3 on one Spark: where I stopped

I started by trying to fit a 315B-class model into 128 GB. That worked: the public
mixed-IQ2 artifact is 83.56 GiB and recorded 16.49 tok/s in the published tg128
benchmark. It also missed the BF16 quality-preservation gates. Both facts matter.

The follow-up asked whether keeping more precision on the internal SSD could be
useful. I built a lossless archive of the roughly 630 GB BF16 file, verified the
whole reconstructed hash, and converted routed experts directly from that archive
to Q4_K. Ordinary weights remained unchanged. All 51 MoE layers ran through the
custom loader, using 186.90 GB of weight data on disk.

The best two-request 128-token configuration recorded 2.920 and 2.930 tok/s.
A longer run with graphs disabled recorded **2.81 tok/s over 1,024 generated tokens**,
with about 375 seconds for the request including input processing. It stopped at
the token limit while still drafting and reviewing the answer. The 3–5 tok/s
sustained target and a reliable overnight assistant were not achieved.

## What someone else can use

- A downloadable mixed-IQ2 model, pinned runtime base, tokenizer correction, and measured results.
- MTP experiments and a model-free numerical probe, each with its own limits.
- Recorded document-agent answers, including completed but incorrect answers.
- A lossless archive format and decoder, direct archive-to-Q4 converter, selected-expert loader, and cache experiments.
- [An offline verifier](../experiments/ssd-offload/verify.py) and [inspectable Q4 outputs](../experiments/ssd-offload/evidence/q4/quality-cap8192/answers.jsonl).

The cache result was the most useful surprise: a much smaller explicit cache was
faster in these runs. Storing the same weight data in an application cache and the
OS cache can be expensive. The runs suggest that explanation; they do not isolate
it as the sole cause. More threads and different read advice did not solve it.

## Quality remains a separate question

The Q4 canary scored 10/16 on exact JSON. Six answers differed in keys, array shape,
code fences, or additional fields. BF16 was not run on this canary. An older
four-choice probe scored both BF16 and IQ2 at 3/4; it was not a practical acceptance
test. Therefore this work does not show whether Q4 caused these behavioral failures,
or whether the unquantized parent would pass.

The earlier IQ2 perplexity/KL failure is real evidence for that artifact. It must
not be transferred to Q4. Likewise, byte-exact cache comparisons and lossless
archive hashes verify specific implementation properties, not model quality.

## Why close here

The project now has a working artifact, reusable implementation work, measured
trade-offs, and explicit failure evidence. Another open-ended optimization campaign
would not make those findings more complete. I am closing active research and
keeping the repository available for reproduction and corrections.

There is no new Q4 model upload, no BF16-equivalence claim, and no promised autonomous
agent roadmap. The unfinished BF16/Q4 comparison and production Q4 queue stay listed
as unfinished. The [experiment bundle](../experiments/ssd-offload/README.md) contains
the numbers, source assumptions, and checks needed to inspect this conclusion.

[한국어](FINAL_REPORT.ko.md) · [Original case study](CASE_STUDY.md) · [Project status](PROJECT_STATUS.md)
