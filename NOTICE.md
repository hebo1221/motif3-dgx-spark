# Notice and attribution

## Motif-3

The model artifact documented here is derived from
`Motif-Technologies/Motif-3`, pinned at commit
`883d5c441fe3bb994c7b57e60f49e26147f85512`.

Upstream project: <https://huggingface.co/Motif-Technologies/Motif-3>

Upstream license: MIT License, Copyright (c) 2026 Motif Technologies Corp.

The complete upstream license must accompany redistributed model weights. It
is included in the corresponding Hugging Face model repository as
`LICENSE.md`.

## llama.cpp

Runtime work builds on llama.cpp and the public Motif-3 port maintained by
Chrono:

- <https://github.com/ggml-org/llama.cpp>
- <https://github.com/timkhronos/llama.cpp/tree/Motif3>
- GQA-5 Flash Attention PR: <https://github.com/ggml-org/llama.cpp/pull/26404>

The exact tested community runtime is published at:

- <https://github.com/hebo1221/llama.cpp>
- tag `motif3-dgx-spark-runtime-v1.0.0`
- commit `cc3f13b3f172978d7b3c215780d4cc98bb0e1c80`

That commit adds Motif-3 tokenizer handling and regression coverage on top of
the cited model port and GQA-5 work.

Project release v1.1.0 also distributes the Motif-only tokenizer-exact patch
`patches/motif3-tokenizer-exact-v1.patch`, SHA-256
`5eba842cd63731e3ee39c60c43134ef59a3a64c9d28c2aa58c3073225c6545cf`,
to be applied to that pinned runtime commit. The patch is source code derived
from llama.cpp and remains under llama.cpp's MIT License.

Project release v1.2.0 additionally distributes the experimental Motif-3 MTP
runtime and optional diagnostic patches, SHA-256
`9568454b651e43dcfd784b37a21364fb6f2d6d3420ae308581acd377eb315629`
and
`a3da8979eea172ae650da6e87953c3327f6b786b3c067c80e077e28da3d1cd6c`.
They are source changes derived from llama.cpp and remain under llama.cpp's
MIT License. No MTP model weights are redistributed here.

llama.cpp is distributed under the MIT License. No llama.cpp binary is
redistributed in this bundle.

## Independence

This is an independent community quantization and engineering report. It is
not an official Motif Technologies, NVIDIA, or llama.cpp release.

The v1.3.0-rc.1 experimental probes, agent client, and redacted evidence have
additional [attribution](experiments/value-v2/NOTICE.md) and
[publication provenance](experiments/value-v2/PUBLICATION.md).
