# When the model no longer fits: Motif-3 on internal NVMe

The downloadable IQ2 model fits in Spark memory. I then tried a different constraint:
keep more precision, leave the weights on the internal SSD, and fetch the selected
experts during inference. This directory closes that experiment.

**Result: 51 MoE layers running routed experts in Q4_K, 186.90 GB of weight data,
and 2.81 generated tokens/s in one 1,024-token run.** The 3–5 tok/s sustained
target was not reached. The run stopped at the token limit without a confirmed
finished answer. Generated-token throughput is not useful-answer throughput.

[한국어 최종 회고](../../docs/FINAL_REPORT.ko.md) ·
[Final report](../../docs/FINAL_REPORT.md) · [Source notes](SOURCE_NOTES.md)

## Three separate results

| Path | Recorded result | Boundary |
|---|---|---|
| Existing downloadable mixed IQ2 | 83.56 GiB; tg128 16.49 tok/s | Historical public-build benchmark; BF16 preservation gates failed |
| Lossless BF16 storage | 629.69 GB → 447.84 GB; whole reconstructed SHA-256 matched | Storage compression, not quantization or a faster inference result |
| Experimental routed-expert Q4_K | 186.90 GB; 2.81 tok/s over 1,024 generated tokens | Internal-NVMe offload; custom loader; no same-test BF16 quality comparison |

These are different artifacts and workloads, not a head-to-head speed ranking.
There is no new Q4 model download in this release.

## The useful finding

A bigger explicit expert cache did not help this workload. Two 128-token requests
with an 8,192-expert cache ran at 2.256 and 2.267 tok/s. A 128-expert cache ran at
2.774 and 2.903 tok/s. Returning ordinary-weight file pages after GPU upload gave
2.912 and 2.912 tok/s. The smaller cache left more memory available elsewhere;
duplication with the OS file cache is a plausible explanation, not an isolated
causal finding. Runs were ordered, with no forced cold-cache reset.

Persistent read workers, random read advice, and grouped reads did not yield a
clear improvement. Requested CUDA Graphs gave 2.920 and 2.930 tok/s, but graph
launches were not instrumented. I do not attribute that small difference to graphs.
All variants and their limitations are retained in [the outcome](evidence/q4/outcome.json).

## What the quality test actually says

Q4 passed 10 of 16 exact-JSON synthetic cases. The six failures were two key/array
shape mismatches, two code fences, and two extra-field cases. The requested values
were present in the extra-field answers; the prompts did not explicitly prohibit
additional keys. The historical strict score is unchanged. This is a limitation
of the test as well as a distinction between reasoning and interface compliance.

BF16 did **not** take these 16 cases. An earlier four-choice probe scored BF16 3/4
and IQ2 3/4, with the same wrong item. That probe compared four next-token choice
scores after a fixed prefix, not freely generated answers. It does not qualify
BF16 for practical use or prove that Q4 preserved quality.

The 18 tested input renderings matched the upstream revision's template byte for
byte. Cache/read variants also passed 2,144 full-logit-file comparisons. Neither
check is a BF16-versus-Q4 quality comparison. The original model, quantization,
and runtime remain possible contributors to the observed output behavior.

## Verify the published records without a GPU

From the repository root:

```sh
python3 experiments/ssd-offload/verify.py
```

This replays the strict JSON score, checks the exported-file hashes, and checks
that the summary matches the stored timing rows. It makes no model requests and
does not independently reproduce the GPU computation. Binary logits and weights
are not included. The checksum manifest protects this export, not the truth of
every experimental interpretation.

## Project closure

Active research ends with this source-and-evidence release. No further model
training, broad agent development, or automatic benchmark campaign is scheduled.
The BF16/Q4 behavioral comparison and a production-ready Q4 overnight queue are
unfinished; they are recorded limitations, not promised follow-up work.
Reproduction defects and factual corrections can be handled as small maintenance
changes. The model bytes and original local experiment records remain preserved.
