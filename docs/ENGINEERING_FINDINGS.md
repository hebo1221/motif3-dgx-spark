# Engineering findings

The project produced more than one quantized file. It established a practical
baseline, fixed Motif-specific runtime edge cases, and measured where three
modern repair strategies help or become too expensive.

## 1. Direct BF16 quantization is the clean deployment baseline

The most robust path was also the simplest to reproduce:

- pin all 155 official BF16 shards;
- convert the full core model directly to BF16 GGUF;
- quantize once with an official-tokenizer importance matrix;
- retain embeddings and output at Q8_0 and sensitive control tensors at higher
  precision;
- bind the final 89.72 GB file with a full SHA-256 and tensor inventory.

This removed Q5 double-quantization as a confound and produced the fastest,
smallest universal artifact evaluated in the campaign.

## 2. Expert-aware runtime work reached finite full-model execution

A GEMQ-style compact expert overlay exposed duplicate local expert IDs in the
CUDA routing path. A two-pass occurrence map and corrected fallback handling
removed the non-finite outputs. The real combination then checked 10,968
tensors, reached raw-tensor cosine similarity `0.99997864636`, and generated
finite server output.

That runtime correction is a useful result even though the 14.28 GB overlay
was not selected for the default release: it made compact per-expert overlays
technically viable for future kernel optimization.

## 3. A tiny terminal correction found a promising quality direction

A 16.56 MB terminal logit-curvature adapter was the most efficient quality
experiment:

- Korean diagnostic: +3 / 300;
- general diagnostic: unchanged;
- prefill change: less than 0.6%;
- peak allocation: only +22 MiB.

It was not promoted as universal because tool diagnostics regressed, but it
identified a high-leverage representation worth revisiting with explicit
tool-margin constraints.

## 4. Causal controls separated quality from capacity

A block-40 plus block-52 Q8 restoration improved the general diagnostic by one
item but cost 11.82% on tg128 and 9,270 MiB of peak allocation. The experiment
showed that simply restoring selected late weights is not an efficient path on
unified-memory hardware.

The larger GEMQ overlay similarly traded about 18-20% speed and 13,621 MiB of
peak allocation for no task gain. These controls justified retaining direct
IQ2 as the public default instead of choosing a larger artifact by intuition.

## 5. Tool formatting can be improved without confusing it with policy

Strict schema gating raised the diagnostic tool episode count from 12/30 raw
to 17/30. Separate experiments showed that target-tool proposal was often
strong while null-tool rejection and required-slot state remained weak.

The practical architecture is therefore decomposed:

1. select one declared tool or `none`;
2. extract typed values or mark required fields as missing;
3. normalize Korean dates, numbers, times, units, lists, and names;
4. apply a deterministic call, clarify, or respond rule;
5. validate or conservatively repair JSON only after the policy decision.

## Takeaway

The release demonstrates that a 314.7B MoE can be made usable on one DGX
Spark. The next quality step is not a larger generic-KL overlay; it is a small,
runtime-aware correction trained against Korean, general, and tool-control
margins simultaneously.
