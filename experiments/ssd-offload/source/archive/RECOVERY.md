> Historical migration notes. The migration writer is not distributed in this
> snapshot; the resume commands below are records, not supported public instructions.

# BF16 lossless archive migration

The user authorized lossless compressed storage of the original BF16 model. The original bits must remain recoverable. This is storage compression, not quantization.

Actual source before migration:
`/opt/motif-work/motif3-storage/original-bf16/motif3-official-bf16.gguf`

Archive:
`/opt/motif-work/motif3-storage/original-bf16-lossless-v1`

The original path is absent during migration so existing BF16 runners fail closed. Its uncommitted prefix is held in the same directory as `motif3-official-bf16.gguf.lossless-migrating`. Committed suffix ranges are stored in `.bfz` files. Never treat the remaining prefix as a model.

Each frame stores losslessly shuffled original bytes compressed by Zstandard, plus original length and SHA256. The codec writes and fsyncs a temporary frame, reads it back, decompresses it, and compares every byte. Only after publishing the frame and durably committing its receipt does the migration truncate the corresponding source suffix. Parallel jobs prepare independent frames; journal commits and source truncations remain sequential.

`state.json` records the source identity, original length/hash, remaining prefix, frame offsets/lengths/checksums, and phase. A frame not committed in the state is not grounds to remove any original bytes. Uncommitted temporary frames can be rebuilt from the still-present prefix. A source larger than the committed remaining size is handled as an interrupted post-commit truncation, with another verification before truncating.

Create `STOP` in the archive directory to pause at the next committed boundary. Do not kill codec processes unnecessarily. Remove only that STOP file and rerun the migration command to resume. The shared overnight worker lock and the archive writer lock exclude inference and another migration writer.

Resume command on DGX, from the campaign directory:

```sh
python3 migrate.py \
  --source /opt/motif-work/motif3-storage/original-bf16/motif3-official-bf16.gguf \
  --archive /opt/motif-work/motif3-storage/original-bf16-lossless-v1 \
  --codec ./codec-parallel \
  --lock /opt/motif-work/motif3-quant/campaigns/bf16-overnight-20260909-v1/worker.lock \
  --sha256 c921b7afb7fb8b5b5d90ff719e945a16988f696b8353e22bebcad2b6254362aa \
  --jobs 8
```

After all ranges are archived, the codec reconstructs and hashes the complete byte stream in ascending order. Completion requires 629,689,477,760 bytes and SHA256 `c921b7afb7fb8b5b5d90ff719e945a16988f696b8353e22bebcad2b6254362aa`. `phase=verifying`, `paused`, or exit status zero alone is not completion. Check `phase=complete` and its verification receipt.

`restore.py ARCHIVE NEW_OUTPUT --codec CODEC` reconstructs a new output file and checks the same full hash. It also supports a paused partial migration and locks out the writer. It requires enough output storage. A failed restore leaves an incomplete output; do not treat it as valid. The archive itself is not a directly runnable GGUF file.

Tests cover clean completion, interruption after rename/encode/publication/journal commit/truncation, resume, STOP, odd byte lengths, corruption rejection, and codec interoperability. They simulate process interruption, not hardware failure. Original operating BF16 loader/probe binaries were not changed. They require a restored raw model or an archive-aware loader before use again.

Final whole-stream verification uses `codec-parallel`: up to eight frames are decompressed and checked concurrently, then fed to SHA-256 strictly in original offset order. The serial verification was intentionally stopped while read-only; `hash-transition.json` records the switch and `migration-v3.stderr` therefore contains an expected termination exception. Completion evidence belongs to `migration-v4.jsonl`, `state.json`, and `completion-audit.json`.
