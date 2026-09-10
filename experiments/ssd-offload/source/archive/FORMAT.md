# MBF16Z1 archive format and recovery

This archive preserves the complete original GGUF byte stream. It is not a quantized model and is not directly loadable as GGUF.

Each `.bfz` frame consists of:

- Bytes 0–7: `MBF16Z1` followed by a zero byte.
- Bytes 8–15: original byte length as little-endian uint64 (1 through 536870912).
- Bytes 16–47: SHA-256 of original uncompressed bytes.
- Remaining bytes: a standard Zstandard frame with its checksum enabled.

Before Zstandard compression, original bytes at even offsets are concatenated, followed by original bytes at odd offsets. For original length N, split decoded payload at ceil(N/2) and interleave the two parts to recover the original. This operation is byte-exact; it makes no floating-point conversions.

`state.json` entries record each frame offset and length in the original file and both raw and compressed SHA-256. Sort entries by offset and concatenate restored raw frames. Full verification must reproduce 629689477760 bytes with SHA-256 `c921b7afb7fb8b5b5d90ff719e945a16988f696b8353e22bebcad2b6254362aa`.

Build codec on the current DGX host:

```sh
g++ -O3 -std=c++17 codec-fast.cpp -I/opt/motif-work/motif3-tokenizer-runtime-baseline-v1/vendor -lzstd -ldl -o codec-fast
```

Dependencies are the C++ standard library, nlohmann/json.hpp, libzstd development files, and runtime libcrypto.so.3. The source uses the host byte order for uint64; DGX aarch64 and Mac arm64 are little-endian. Porting to a big-endian system requires explicit little-endian conversion of bytes 8–15.

Use `restore.py` for full reconstruction or `archive_read` / `ArchiveReader` for validated range access to a complete archive. Preserve codec source and this format description alongside the archive. See RECOVERY.md for an interrupted migration.

`codec-parallel.cpp` uses the same frame format and adds bounded parallel decoding for the `hash` command. Build it with the same command plus `-pthread`, substituting codec-parallel for codec-fast. Ordered, repeated, and shuffled frame-list tests match Python hashlib; damaged frames reject the hash without a success receipt.
