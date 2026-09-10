# Source snapshot and reproduction boundaries

This is an inspectable research snapshot, not a portable installation package.
The existing IQ2 [download-and-run guide](../../README.md#download-and-run) remains
the supported documented entry point. Q4 weights and the BF16 archive are not uploaded.

## Runtime and layout

The measured runtime base was
`cc3f13b3f172978d7b3c215780d4cc98bb0e1c80` from the public
[Motif runtime fork](https://github.com/hebo1221/llama.cpp).
`source/runtime-measured.patch` records the current local source diff at closeout.
It is included for inspection; this release does not claim a new clean rebuild
or prove that every existing library was rebuilt from the closeout snapshot.
The tested binaries' hashes are retained in `evidence/q4/preflight.json`.

`source/q4/` preserves the converters, graph replacement loader variants, probe,
and launch/analysis scripts. Private home paths are replaced by `/opt/motif-work`.
The export receipt records source and published hashes; path edits were not rerun
on the GPU. Scripts retain campaign-layout assumptions and are not one-command
fresh-checkout instructions.

Dependencies: Linux aarch64, compatible CUDA/GB10 runtime, C++17, ggml/llama headers
and libraries from the matching runtime, nlohmann/json.hpp, libzstd, libcrypto.so.3,
Python 3 and Jinja2. The codec uses a little-endian host. `build.py` builds the
loader and probe; it does not build the archive converter or create weights.
The C++ converter and shell builder expose their arguments in their `main` functions.

The recorded campaign layout is:

- `motif3-tokenizer-runtime-baseline-v1/`: runtime source and `build/bin` libraries;
- `motif3-storage/original-bf16-lossless-v1/`: completed archive and `state.json`;
- `motif3-quant/campaigns/q4-all-layers-20260910-v1/`: sources, 51 packs and sparse shell;
- sibling `bf16-overnight-20260909-v1/`: shared worker lock and `tensors.txt`;
- sibling `bf16-lossless-archive-20260910-v1/`: `gguf-layout.json`.

The last two metadata files are included as `source/tensors.txt` and
`evidence/archive/gguf-layout.json`. Historical launchers also assume the local
project chat template and Python environment; adapt those paths explicitly.

## Conversion and storage

`source/archive/FORMAT.md` documents the lossless frame format. The decoder and
restore tool are included; the destructive in-place migration writer is not part
of this public package. A reconstructed original needs about 630 GB of separate
space. Preserve the archive and verify the whole reconstructed hash before use.

The Q4 converter reads a completed archive and writes expert-major gate/up/down
packs, one 3,397,386,240-byte pack per MoE layer. All 51 packs occupy
173,266,698,240 bytes. Ordinary tensors and GGUF header add 13,630,106,240 bytes.
The sparse shell retains original offsets and apparent file size; its expert
ranges are holes. **Never pass this shell to an ordinary GGUF runner.** It requires
the matching graph-replacement loader and all 51 packs. Copying it without sparse
file support can expand it to about 630 GB.

`prepare.py` is the historical first-generation launcher. It requires four earlier
verified packs and a regenerated layer-2 comparison, then creates the other 47.
Those weight inputs are not distributed. It intentionally refuses existing output
directories; do not treat rerunning it as a recovery procedure. The converter itself
accepts a layer list, but a clean all-51-from-scratch workflow was not validated in
this release. Whole-layer hash equality was checked for regenerated layer 2, not
an independent BF16 conversion of every layer.

## Inference and evaluation

`run.py` verifies all pack and ordinary-range hashes, acquires the shared lock,
and runs the short ABBA cache experiment and 16-case JSON canary. `run_long.py`
contains the read/cache variants. `run_sustained.py` records the 1,024-token run.
Existing output directories must not be overwritten. The probe writes full logits
and is a benchmark program, not a production overnight job queue.

The archive is not read during Q4 inference. Routed BF16 fetches abort in the Q4
loader, and callback checks cover all 51 layers. All public timing numbers refer
to the recorded machine and settings. Reproducing those speeds on a new setup,
BF16/Q4 quality parity, and production operation remain unverified.

The earlier four-choice report is historical evidence. Its original local links
are not a public reproduction interface; the two score files and cases are included.
