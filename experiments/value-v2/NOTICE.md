# Attribution

This release extends the user's Motif-3 DGX Spark project with AI-assisted
implementation, documentation, and review. The answer-review judgments were
made by the same assistant that authored the exploratory questions; they are
not independent human or blind evaluation results.

The project does not claim to invent Motif-3, Qwen, quantization, MTP, or the
existing tokenizer/MTP runtime work. The small CUDA reference derives from
llama.cpp and earlier batch-invariant Motif work. The included parser patches
also derive from llama.cpp. MIT notices and model attribution are retained in
`licenses/`; model terms remain separate. No weights or runtime binaries are
redistributed here.

Final client and probe sources preserve the measured bytes. Publication edits,
the limited Qwen parser cleanup, original-to-public hashes, and evidence
redactions are disclosed in PUBLICATION.md and PUBLIC-PROVENANCE.json.
