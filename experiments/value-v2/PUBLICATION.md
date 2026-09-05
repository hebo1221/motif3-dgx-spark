# Publication provenance

This public release was prepared from a completed private experiment. No new
model inference was run to create the public copy, and no failed score was
promoted to a pass during publication.

`PUBLIC-PROVENANCE.json` maps each imported file's original SHA-256 to its
public SHA-256. It describes redactions, omitted transport/device logs, and
publication edits. Repository `SHA256SUMS` verifies all final release files.

## Two kinds of hashes

Hashes inside historical run receipts, source receipts, frozen evaluation
manifests, semantic reviews, and recorded replay checks identify the original
recorded bytes. These are retained as historical identifiers. A public copy
that had a path redacted will have a different checksum.

Use `PUBLIC-PROVENANCE.json` to find the original-to-public mapping. Use
`workflows/public-freeze.json` and the public `document-index.json` files to
check or execute the redacted fixtures. The original `workflows/freeze.json`
describes the original experiment and must not be used as the public fixture
manifest. Numerical values, token arrays, model digests, and reported outcomes
were preserved.

Document redactions preserve line boundaries so cited spans can still be
checked, but change input bytes and potentially tokenization. Historical
responses therefore remain recorded observations rather than promised outputs
for rerunning the public fixtures. Some embedded older reports retain links to
earlier private evidence that is not part of this release; the complete new
value-v2 answer records and numerical results are included here.

## Code and patch scope

- Final client v4 and the two numerical C++ probes are byte-identical to the
  recorded sources. Earlier v1/v2/v3 sources and development failures remain
  available for inspection.
- The small Q8 reference patch is byte-identical to the tested patch. It applies
  to the pinned base and produces the two recorded candidate source hashes.
- The earlier Motif parser patch is included unchanged. The public Qwen parser
  patch drops an unrelated thinking-flag change for another handler from the
  historical combined diff. Its Qwen function and registration match the
  measured source exactly. This is recorded in the publication provenance and
  `evidence/public-patch-application.json`.
- Publication checks include patch application and source comparisons, not a
  fresh full runtime build or a new accuracy benchmark.

Documentation was rewritten for public use. The final source package contains
no model weights, runtime binaries, access tokens, personal hostnames, device
UUIDs, or private account filesystem paths. Do not use generic paths such as
`/opt/motif-work` inside historical receipts as an installation recipe.
