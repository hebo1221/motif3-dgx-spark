# Contributing

Thanks for taking the time to reproduce or improve this work. The most useful
contributions are small, checkable, and clear about what changed.

The research phase is complete. Maintenance focuses on reproduction defects,
evidence corrections, and independent results; see
[project status](docs/PROJECT_STATUS.md). Larger research proposals should
include a concrete task, comparison, cost limit, and stopping criterion.

## Benchmark reports

Please use the
[benchmark report form](https://github.com/hebo1221/motif3-dgx-spark/issues/new?template=benchmark.yml).
Before reporting a number:

1. Verify the downloaded model and template with
   `scripts/verify_download.sh MODEL_DIR`.
2. Record the GPU, memory size, OS, NVIDIA driver, CUDA version, runtime commit,
   and complete `llama-bench` command.
3. Keep prompt processing and generation results separate.
4. Include every repetition or attach the raw JSONL. Do not report only the
   best run.
5. Say explicitly if you changed Flash Attention, KV precision, batch size,
   micro-batch size, context, thread count, or parallel slots.

Please redact access tokens, hostnames, usernames, and private filesystem paths
before attaching logs. The model itself already has two disclosed passive
local-path metadata values; there is no need to copy additional private paths
into an issue.

## Pull requests

Documentation fixes, safer reproduction steps, and small analysis tools are
welcome here. Runtime implementation changes belong in the
[llama.cpp fork](https://github.com/hebo1221/llama.cpp), where they can be
tested against the exact build.

Keep these claim boundaries intact unless you bring new, reproducible evidence:

- this is a single-DGX-Spark systems result, not a BF16-equivalence result;
- stock upstream llama.cpp compatibility is not established;
- the downloadable GGUF does not include the native MTP head;
- the v1.2.0 experimental MTP result is bound to one byte-distinct target and one
  GB10, not the downloadable v1 GGUF or every CUDA GPU;
- retained 256K-context quality is not established;
- internal diagnostic tasks are not public leaderboard scores.

Before opening a pull request, run:

```bash
sha256sum -c SHA256SUMS
python3 scripts/audit_tokenizer_parity.py --help
python3 experiments/value-v2/verify_public.py
```

If your change modifies a file listed in `SHA256SUMS`, update its digest in the
same commit. Never replace the published GGUF in place: any model-byte change
requires a new filename or revision, digest, evidence receipt, and release note.

## Questions and early results

Use [Discussions](https://github.com/hebo1221/motif3-dgx-spark/discussions) for
questions, setup notes, or results that are not ready to become a benchmark
record. A minimal reproduction belongs in an issue when something is broken.
