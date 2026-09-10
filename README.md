# Motif-3 315B on one DGX Spark

[English](README.md) | [한국어](README.ko.md)

**Active research closed — September 10, 2026.** The final follow-up tested
higher-precision weights on internal NVMe: routed-expert Q4_K generated 1,024
tokens at 2.81 tok/s, below the sustained target. BF16/Q4 behavioral parity remains
unverified. The IQ2 download and its historical measurements below are unchanged.

**[Final report](docs/FINAL_REPORT.md) · [한국어 최종 회고](docs/FINAL_REPORT.ko.md) ·
[Q4 source and recorded results](experiments/ssd-offload/README.md)**

![Motif-3 315B on one DGX Spark: 83.56 GiB, 316.71 tok/s prompt processing, and 16.49 tok/s generation](assets/motif3-dgx-spark-result-card.png)

This project runs the 314.7B-parameter core of
[Motif-3](https://huggingface.co/Motif-Technologies/Motif-3) entirely on one
128 GB NVIDIA DGX Spark. The model is packaged as an 83.56 GiB mixed
IQ2_XXS GGUF, with all model layers loaded on the GPU.

The repository includes the exact model revision, a pinned Motif-capable
llama.cpp runtime, a tokenizer correction, benchmark data, checksums, and the
notes needed to reproduce the setup.

**[Download the GGUF](https://huggingface.co/jhkim55/Motif-3-Direct-IQ2-XXS-DGX-Spark)**
· **[Runtime notes](docs/RUNTIME.md)**
· **[Results](docs/RESULTS.md)**
· **[Case study](docs/CASE_STUDY.md)**

## At a glance

| Item | Result |
|---|---:|
| Source | official BF16 at `883d5c441fe3bb994c7b57e60f49e26147f85512` |
| Parameters | 314,701,772,930 |
| Final file | 89,720,474,560 bytes / 83.56 GiB |
| BF16-to-GGUF reduction | 7.02x smaller |
| Effective storage | 2.2805 bits per element |
| pp512 | 316.71 tok/s |
| pp2048 | 312.76 tok/s |
| tg128 | 16.49 tok/s |
| pp2048 + tg128 | 149.33 tok/s |

The performance rows are means from five repetitions on one clean public
build. Full results and the earlier three-session stability runs are in
[Results](docs/RESULTS.md).

> [!IMPORTANT]
> This GGUF was validated with the pinned Motif-capable runtime and tokenizer
> patch below. Compatibility with stock upstream llama.cpp has not been
> established.

> [!NOTE]
> This is a single-Spark feasibility release, not a BF16-equivalent quant. It
> fits and runs at useful speed, but it did not pass the prespecified BF16
> quality-preservation gates.

## Inspect the work without a GPU

The [recorded answer tour](docs/RECORDED_DEMO.md) pairs document-agent answers
with the passages they cite, including an answer that quotes the right number
and reaches the wrong conclusion. You can verify the published records without
downloading the model:

```bash
git clone --depth 1 https://github.com/hebo1221/motif3-dgx-spark.git
cd motif3-dgx-spark
python3 experiments/value-v2/verify_public.py
```

The verifier runs offline, checks hashes and cited passages, and makes no model
requests. The follow-up release also includes a
[model-free Q8 numerical probe](experiments/value-v2/runtime/README.md) for
CUDA builds.

## Quick start

### Requirements

The tested system was one NVIDIA DGX Spark. Allow for:

- about 90 GB for the model;
- at least 110 GB of free disk while downloading and building;
- the Spark's full 128 GB unified-memory pool, with other large GPU workloads
  stopped;
- Git, CMake, a C++ compiler, the CUDA toolkit, and the `hf` CLI.

Other 128 GB NVIDIA systems may work, but they have not been measured here.

### 1. Download the model and template

```bash
mkdir -p model

hf download jhkim55/Motif-3-Direct-IQ2-XXS-DGX-Spark \
  motif3-direct-iq2xxs.gguf \
  motif3-llama.cpp.jinja \
  --revision 3511f72d7ceac63e2931b27e1666766f2ad18d54 \
  --local-dir model

sha256sum model/motif3-direct-iq2xxs.gguf
```

Expected SHA-256:

```text
9d6f7aee57f0271223f51d69c63d8576a259809e9f05e2ac596512e940c80c5a
```

You can also run the read-only verifier after downloading:

```bash
git clone --branch v1.2.0 --depth 1 \
  https://github.com/hebo1221/motif3-dgx-spark.git release-files

release-files/scripts/verify_download.sh model
```

### 2. Build the runtime

```bash
git clone --branch motif3-dgx-spark-v1 --single-branch \
  https://github.com/hebo1221/llama.cpp.git runtime

git -C runtime checkout cc3f13b3f172978d7b3c215780d4cc98bb0e1c80

sha256sum release-files/patches/motif3-tokenizer-exact-v1.patch
git -C runtime apply --check --unidiff-zero \
  ../release-files/patches/motif3-tokenizer-exact-v1.patch
git -C runtime apply --unidiff-zero \
  ../release-files/patches/motif3-tokenizer-exact-v1.patch

git -C runtime diff --binary --no-ext-diff | sha256sum

cmake -S runtime -B runtime/build \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_CUDA=ON \
  -DGGML_CUDA_FA=ON \
  -DGGML_CUDA_GRAPHS=ON \
  -DGGML_NATIVE=ON \
  -DLLAMA_BUILD_UI=OFF \
  -DLLAMA_USE_PREBUILT_UI=OFF

cmake --build runtime/build --target llama-server llama-bench -j 12
```

The tokenizer patch must have SHA-256
`5eba842cd63731e3ee39c60c43134ef59a3a64c9d28c2aa58c3073225c6545cf`.
After applying it, the normal Git diff must hash to
`09abc52c2f7ff9f2cb3e9b8edd3af03684840969d0cdc7f24fd7aa63ca3207f3`.
The patch only changes Motif tokenizer handling; it does not modify the model
weights or other tokenizer families.

### 3. Start the server

```bash
runtime/build/bin/llama-server \
  -m model/motif3-direct-iq2xxs.gguf \
  -ngl 99 \
  -fa on \
  -ctk f16 \
  -ctv f16 \
  -b 2048 \
  -ub 512 \
  -c 32768 \
  -np 1 \
  --host 127.0.0.1 \
  --port 8080 \
  --no-ui \
  --jinja \
  --chat-template-file model/motif3-llama.cpp.jinja
```

Keep the server on `127.0.0.1` unless you have added authentication. Once the
model is ready:

```bash
curl -fsS http://127.0.0.1:8080/health

curl -fsS http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "messages": [
      {"role": "user", "content": "한국의 수도는 어디인가요? 한 문장으로 답해주세요."}
    ],
    "temperature": 0,
    "max_tokens": 24,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

The clean-build smoke test returned `한국의 수도는 서울입니다.` and reported
`b10498-cc3f13b3f`. That smoke test and the published speed rows predate the
v1.1.0 tokenizer patch.

## Reproduce the benchmark

Run this only when no other process has the model loaded:

```bash
runtime/build/bin/llama-bench \
  -m model/motif3-direct-iq2xxs.gguf \
  -ngl 99 -fa on \
  -ctk f16 -ctv f16 \
  -b 2048 -ub 512 -t 20 \
  --delay 3 \
  -p 512,2048 \
  -n 128 \
  -pg 2048,128 \
  -r 5 \
  -o jsonl
```

The normalized rows are in
[`evidence/clean_runtime_benchmark.jsonl`](evidence/clean_runtime_benchmark.jsonl).
Build details and the server smoke test are in
[`evidence/clean_runtime_verification.json`](evidence/clean_runtime_verification.json).

## Quantization details

This is a mixed-precision file, not a pure 2-bit model. Routed-expert tensors
carry most of the compression, while embeddings, output, attention, routing,
and control tensors keep more precision.

| Stored type | Tensors | Payload bytes |
|---|---:|---:|
| IQ2_XXS | 306 | 78,631,821,312 |
| BF16 | 424 | 7,252,475,904 |
| Q8_0 | 2 | 1,916,272,640 |
| Q2_K | 6 | 1,357,676,544 |
| F32 | 1,424 | 552,591,880 |

The conversion path was:

```text
official BF16 -> BF16 GGUF -> IQ2_XXS
```

There was no Q5 intermediate and no `--allow-requantize` step. See
[Method](docs/METHOD.md) for the complete source and tensor inventory.

## Validation

The public evidence covers:

- all 54 model layers loaded on the GPU;
- the exact 89.72 GB GGUF loaded by the pinned runtime;
- successful `/health`, `/slots`, and Chat Completions requests;
- exact agreement with the official tokenizer on 115,618 corpus token IDs and
  318,951 deterministic fuzz token IDs;
- exact agreement on 4,164,390 token IDs in the extended tokenizer campaign;
- 16 passing tokenizer regression tests;
- SHA-bound model, template, source-shard, tensor, and benchmark records.

Tokenizer evidence is in
[`evidence/tokenizer_exact_v1.json`](evidence/tokenizer_exact_v1.json). The
tokenizer patch fixes input token IDs only; it does not improve the IQ2 model
weights.

## Quality and known limitations

On a fixed 49,152-token held-out comparison, the quant measured a 1.4115x
perplexity ratio and 0.4541 mean KL against BF16. Both missed the prespecified
limits of 1.10 and 0.10. Treat this as a local systems and research model, not
as a drop-in BF16 replacement.

Other limits:

- The downloadable GGUF does not include Motif-3's native MTP head.
- The parent model advertises 256K context, but retained 256K retrieval and
  generation quality have not been established here.
- Tool calling is fragile at this bit rate. JSON validation can fix formatting,
  not a wrong call/no-call decision.
- In server mode, `-c` is divided across parallel slots. Check `/slots` before
  assuming each request receives the full value.
- Internal task sets are diagnostics, not public leaderboard scores.
- Two passive quantization-provenance fields contain local build paths. They do
  not affect inference; the published SHA binds the file as it is.
- The throughput rows were measured on the pinned v1.0.0 runtime base, before
  the tokenizer patch, and remain labeled accordingly.

## Project status

The active research phase is complete. The released model, tokenizer patch,
numerical probes, and recorded agent failures remain available as a systems
case study and a starting point for local experiments. There is no scheduled
model-training or general-purpose agent roadmap.

Reproducible defects, independent Spark measurements, or a concrete user task
with a bounded evaluation can justify follow-up work. See
[project status](docs/PROJECT_STATUS.md) and the existing
[evidence discussion](https://github.com/hebo1221/motif3-dgx-spark/discussions/1).
The missing MTP head in the downloadable file concerns speculative speed;
it does not explain the measured BF16-to-IQ2 distribution shift.

The open attribution question—what comes from the parent model and what comes
from quantization—is tracked in
[Discussion #1](https://github.com/hebo1221/motif3-dgx-spark/discussions/1).
Paired BF16/Q5 results, mixed-precision proposals, and independent Spark
reproductions are welcome.

## Reusable experiments

[v1.3.0-rc.1](https://github.com/hebo1221/motif3-dgx-spark/releases/tag/v1.3.0-rc.1)
contains a model-free Q8 batch-consistency probe, a two-file opt-in reference
patch, and a bounded document agent with project matching and exact source
passages. The reference path is slower; the agent still makes factual errors.
The release includes both outcomes and their public provenance.

See [the follow-up](experiments/value-v2/README.md) and
[한국어 결과](experiments/value-v2/README.ko.md).

## Experimental native MTP follow-up

Release v1.2.0 adds an optional source patch for Motif-3's one-layer MTP head.
On a separate, byte-distinct target, the fixed target/MTP/target A-B-A run
matched 5,120/5,120 greedy tokens in both comparison arms and improved
server-reported decode from a 14.5872 tok/s counterbalanced target mean to
17.5565 tok/s (**1.2036x**). Draft acceptance was 47.11%.

This is not a replacement model upload. The 512 MB sidecar is not
redistributed, the downloadable GGUF is unchanged, and the result must not be
attributed to that public GGUF. See
[Experimental native MTP](docs/MTP_EXPERIMENTAL.md) for the patch, build
recipe, evidence, and limits.

## Documentation

- [Engineering case study](docs/CASE_STUDY.md) · [한국어 회고](docs/CASE_STUDY.ko.md)
- [Recorded answers and offline verification](docs/RECORDED_DEMO.md)
- [Project status and completion criteria](docs/PROJECT_STATUS.md)
- [Method and source binding](docs/METHOD.md)
- [Results and limitations](docs/RESULTS.md)
- [Engineering findings](docs/ENGINEERING_FINDINGS.md)
- [Runtime and troubleshooting](docs/RUNTIME.md)
- [Experimental native MTP](docs/MTP_EXPERIMENTAL.md)
- [Machine-readable metrics](evidence/public_metrics.json)

## Share a result

If you run the model on another DGX Spark or a similar 128 GB NVIDIA system,
open a [benchmark report](https://github.com/hebo1221/motif3-dgx-spark/issues/new?template=benchmark.yml).
Please include the full command and raw `llama-bench` JSONL rather than only a
headline number. Setup questions and early results belong in
[Discussions](https://github.com/hebo1221/motif3-dgx-spark/discussions).

## License

Repository code and original documentation are MIT licensed. The derived model
retains the upstream Motif-3 license and attribution. The work builds on
Motif Technologies' model, llama.cpp, Chrono's Motif port, and the cited GQA-5
work; development and analysis were assisted by Codex. See [NOTICE](NOTICE.md)
for details. This is an independent community project, not an official Motif
Technologies, NVIDIA, or llama.cpp release.
