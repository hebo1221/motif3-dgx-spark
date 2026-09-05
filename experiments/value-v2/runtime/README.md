# Q8 batch-consistency probes

`q8_kernel_probe.cpp` constructs three deterministic Q8_0 matrices and eight
distinct F32 input columns. Each column has its own single-column reference,
so an accidental column offset cannot pass just because inputs are identical.
It compares widths 2, 4, and 8 with and without the explicit hint and checks a
single-column repeat control. No model weights are needed.

`batch_probe.cpp` generates or accepts a fixed continuation and replays its
tokens at different batch widths. It compares full float32 logits and argmax
IDs, then repeats single-token execution. It does not implement speculative
sampling and is not a quality benchmark.

## Small reference patch

`q8-single-column-reference.patch` adds an explicit hint and routes supported
Q8_0 operations through the existing one-column path. Its scope is one GB10,
2–4 columns, a single channel/sample, and an available single-column MMVQ path.
Default execution is unchanged. Recorded matrices used contiguous F32 inputs.
Width 3, arbitrary strides, other types/devices, and full model graphs are not
validated by the six supported test combinations.

In the recorded tests, all 147,456 values at widths 2 and 4 matched the scalar
column reference. Width 8 retained the original differences. Default and
restored output fingerprints matched in all nine combinations. The reference
path took 1.92–5.18 times as long as the ordinary path in this compute-only
microbenchmark. It is a conservative correctness reference, not a default
performance patch.

## Reproduction setup

Use the public base commit `cc3f13b3f172978d7b3c215780d4cc98bb0e1c80` from
`https://github.com/hebo1221/llama.cpp`. Start from a separate clean checkout.
The new reference patch and the larger existing MTP patch are alternative
experiments and must not be stacked.

```bash
git clone --branch motif3-dgx-spark-v1 --single-branch \
  https://github.com/hebo1221/llama.cpp.git q8-runtime
git -C q8-runtime checkout cc3f13b3f172978d7b3c215780d4cc98bb0e1c80
git -C q8-runtime apply --check \
  /absolute/path/to/value-v2/runtime/q8-single-column-reference.patch
git -C q8-runtime apply \
  /absolute/path/to/value-v2/runtime/q8-single-column-reference.patch
```

The publication check fetched the exact public files, applied this patch, and
matched both candidate source digests to the measured build. The **recorded
build reused existing objects and recompiled one CUDA translation unit**.
A fresh full CMake build is not claimed. To attempt an independent full build:

```bash
cmake -S q8-runtime -B q8-runtime/build \
  -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES=121a-real \
  -DGGML_CUDA_FA=ON -DGGML_CUDA_GRAPHS=ON \
  -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF
cmake --build q8-runtime/build --target ggml ggml-cuda llama -j 12
```

The measured environment was ARM64, GCC 13.3 and CUDA 13.0.88. Another build
configuration is a new experiment. Compile the probes against the matching
headers and libraries:

```bash
llama_src=/absolute/path/to/q8-runtime
probe_src=/absolute/path/to/value-v2/runtime
g++ -std=c++17 -O2 -I"$llama_src/ggml/include" -I"$llama_src/vendor" \
  "$probe_src/q8_kernel_probe.cpp" -L"$llama_src/build/bin" \
  -Wl,-rpath,"$llama_src/build/bin" -lggml -lggml-base -o q8-kernel-probe
g++ -std=c++17 -O2 -I"$llama_src/include" -I"$llama_src/ggml/include" \
  -I"$llama_src/vendor" "$probe_src/batch_probe.cpp" \
  -L"$llama_src/build/bin" -Wl,-rpath,"$llama_src/build/bin" \
  -lllama -lggml -lggml-base -o batch-probe
```

With the GPU otherwise idle and a new output filename:

```bash
backend=/absolute/path/to/q8-runtime/build/bin
LD_LIBRARY_PATH="$backend" ./q8-kernel-probe "$backend" /tmp/q8-result.json
./batch-probe --self-test
```

The trace probe uses `batch-probe MODEL INPUT.json OUTPUT.json BACKEND_DIRECTORY`.
Use `probe_cases.json` to generate synthetic traces, or a recorded fixed
`input.json` under `../evidence/qwen-batch-transfer-v1/` to replay token arrays.
Set `LD_LIBRARY_PATH` to the same backend directory passed as the argument and
inspect actual loaded mappings. Output FNV-1a-64 values are diagnostic float
fingerprints, not cryptographic file hashes.

## Recorded scope and limitations

Raw matrix cases and runtime receipts are under
`../evidence/q8-kernel-comparison-v1/`. They compare original → existing optimized
Motif → minimal reference → restored original. The original maximum absolute
differences were about 7.63e-6 or 1.53e-5. Timings average 25 graph computes after
one warmup, excluding allocation, input transfer and output copy.

The separate Qwen trace campaign compares original → existing Motif → restored
original. At each tested width, all 144 replay positions had changed logits
but zero argmax changes. This does not reproduce an output-divergence issue or
establish a general quantized-speculation fix. It does not evaluate the small
reference patch as a whole-model quality improvement.

The first isolated build failed from mixing copied and original headers. The
second used a coherent copied ggml source tree and succeeded. The initial
failure receipt and redacted error log remain included.
