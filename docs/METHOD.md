# Method

## Source binding

The conversion used the official `Motif-Technologies/Motif-3` BF16 repository
at commit `883d5c441fe3bb994c7b57e60f49e26147f85512`:

- 155 safetensors shards;
- 629,683,797,740 source-weight bytes;
- 2,236 source tensors;
- shard-set SHA-256
  `ea2f2ba268bd5e92d267777f8de67d017ec0a15d38a4eb0f1952b38d9526c6f9`.

The repository's separate NVFP4 activation-scale file was excluded. The MTP
layer was intentionally excluded from the GGUF target and should be treated as
a possible future sidecar, not as part of this release.

## Conversion and quantization

The route was:

```text
official BF16 safetensors
  -> 629,689,477,760-byte BF16 GGUF
  -> direct IQ2_XXS quantization with an importance matrix
  -> 89,720,474,560-byte GGUF
```

This was a direct BF16 quantization. It did not requantize a Q5 checkpoint.
`llama-quantize` used:

- target type `IQ2_XXS`;
- Q8_0 token embeddings;
- Q8_0 output tensor;
- an official-tokenizer calibration importance matrix;
- no `--allow-requantize` path.

## Final GGUF structure

| Stored type | Tensors | Payload bytes |
|---|---:|---:|
| IQ2_XXS | 306 | 78,631,821,312 |
| BF16 | 424 | 7,252,475,904 |
| Q8_0 | 2 | 1,916,272,640 |
| Q2_K | 6 | 1,357,676,544 |
| F32 | 1,424 | 552,591,880 |

The file contains 2,162 tensors and 314,701,772,930 logical elements. Routed
experts account for most parameters and use 2.0699 effective bits per element;
the whole tensor payload uses 2.2805 effective bits per element.

## Tokenizer

The final GGUF embeds `tokenizer.ggml.pre=motif3`. That matters: treating the
vocabulary as ordinary GPT-2 BPE changes word-run and whitespace boundaries.

The v1.1.0 Motif-only tokenizer patch was checked without a command-line
metadata override. Applied to the pinned public-runtime base, it matched the
official Motif tokenizer on 61,548 calibration tokens, 54,070 held-out tokens,
and 318,951 token IDs from a fixed 12,011-case fuzz set using the final GGUF.

Regex splitting and added-token selection were treated as separate mechanisms.
A source-identical extended candidate covered every Unicode 16 letter, mark,
and number in boundary-sensitive contexts, all 160 added tokens across a
whitespace matrix, random compositions, and `parse_special=false`. Across
591,984 generated cases plus the two corpora, all 4,164,390 official token IDs
matched. The patch identity, hashes, and claim limits are in
[`../evidence/tokenizer_exact_v1.json`](../evidence/tokenizer_exact_v1.json).
This is tokenization evidence only; it does not change or improve the IQ2
weights.

## A packaging blemish I am keeping explicit

Two passive provenance fields, `quantize.imatrix.file` and
`quantize.imatrix.dataset`, still contain local source-side paths from the
conversion machine. They are not used during inference and contain no model
weights or credentials, but they should have been normalized before upload.

Changing them would also change the 89.72 GB artifact's SHA-256. I am therefore
not silently rewriting the published file: the digest in this release binds
the bytes that are actually on the Hub. A metadata-clean revision, if made,
will get a new digest and an explicit migration note.

## Model architecture relevant to deployment

- 53 blocks: 2 dense and 51 MoE;
- 384 routed experts, 8 active per token, plus one shared expert;
- 80 query heads and 16 KV heads;
- 4 residual streams;
- 220,160-token vocabulary;
- nominal 262,144-token context in the parent model.

## Evaluation design

The evidence is split into three categories:

1. **Structural:** complete GGUF descriptor scan and full-file SHA-256.
2. **Distributional:** BF16-vs-IQ2 perplexity ratio and KL on 49,152 held-out
   tokens produced with the official tokenizer contract.
3. **Behavioral/system:** deterministic diagnostic task sets and controlled
   five-repeat llama-bench sessions with UMA telemetry.

Raw evaluation prompts and responses are not redistributed. Only aggregates
and cryptographic bindings are public, avoiding dataset-license leakage and
accidental publication of local infrastructure identifiers.
