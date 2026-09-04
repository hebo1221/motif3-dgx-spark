#!/usr/bin/env python3
"""Fail-closed structural receipt for the experimental Motif-3 MTP sidecar."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


# GGUF/ggml dimension order, not source PyTorch order.  This is the exact
# pinned Motif-3 one-layer private MTP contract.  The target embedding, global
# norm, and output head are deliberately absent and are shared through
# llama.cpp's ctx_other link.
EXPECTED_TENSOR_CONTRACT: dict[str, tuple[tuple[int, ...], str]] = {
    "blk.53.nextn.enorm.weight": ((4096,), "F32"),
    "blk.53.nextn.eh_proj.weight": ((8192, 4096), "BF16"),
    "blk.53.nextn.shared_head_norm.weight": ((4096,), "F32"),
    "blk.53.attn_norm.weight": ((4096,), "F32"),
    "blk.53.ffn_norm.weight": ((4096,), "F32"),
    "blk.53.attn_q_a.weight": ((4096, 1024), "BF16"),
    "blk.53.attn_q_a_norm.weight": ((1024,), "F32"),
    "blk.53.attn_q_b.weight": ((1024, 15360), "BF16"),
    "blk.53.attn_gate.weight": ((1024, 8192), "BF16"),
    "blk.53.attn_kv_a_mqa.weight": ((4096, 576), "BF16"),
    "blk.53.attn_kv_a_norm.weight": ((512,), "F32"),
    "blk.53.attn_kv_b.weight": ((512, 4096), "BF16"),
    "blk.53.attn_lambda.weight": ((4096, 64), "F32"),
    "blk.53.attn_output.weight": ((8192, 4096), "BF16"),
    "blk.53.ffn_gate.weight": ((4096, 12288), "BF16"),
    "blk.53.ffn_up.weight": ((4096, 12288), "BF16"),
    "blk.53.ffn_down.weight": ((12288, 4096), "BF16"),
    "blk.53.ffn_poly.weight": ((3,), "F32"),
    "blk.53.ffn_poly.bias": ((1,), "F32"),
}
EXPECTED_TENSORS = frozenset(EXPECTED_TENSOR_CONTRACT)
EXPECTED_TARGET_SHARED_TENSORS: dict[str, tuple[int, ...]] = {
    "token_embd.weight": (4096, 220160),
    "output_norm.weight": (4096,),
    "output.weight": (4096, 220160),
}
EXPECTED_VOCAB_SIZE = 220160
EXPECTED_MERGES_COUNT = 219773

EXPECTED_METADATA: dict[str, Any] = {
    "motif3.block_count": 54,
    "motif3.nextn_predict_layers": 1,
    "motif3.context_length": 262144,
    "motif3.embedding_length": 4096,
    "motif3.feed_forward_length": 12288,
    "motif3.attention.head_count": 80,
    "motif3.attention.head_count_kv": 16,
    "motif3.attention.key_length": 192,
    "motif3.attention.value_length": 128,
    "motif3.attention.q_lora_rank": 1024,
    "motif3.attention.kv_lora_rank": 512,
    "motif3.attention.noise_head_count": 16,
    "motif3.attention.sliding_window": 129,
    "motif3.attention.sliding_window_pattern": 4,
    "motif3.rope.dimension_count": 64,
    "motif3.rope.freq_base": 10000.0,
    "motif3.rope.freq_base_swa": 10000.0,
    "motif3.attention.layer_norm_rms_epsilon": 1e-5,
    "motif3.polynorm.epsilon": 1e-6,
    "motif3.polynorm.output_scale": 0.5,
    "motif3.polynorm.bias_clamp": 0.5,
    "motif3.polynorm.hidden_clamp": 1_000_000.0,
    "motif3.polynorm.sigmoid_weight": True,
    "motif3.mtp.shared_tensors_from_target": True,
    "tokenizer.ggml.model": "gpt2",
    "tokenizer.ggml.pre": "motif3",
    "tokenizer.ggml.bos_token_id": 1,
    "tokenizer.ggml.eos_token_id": 0,
    "tokenizer.ggml.padding_token_id": 0,
}

PAIR_METADATA_KEYS = tuple(
    key for key in EXPECTED_METADATA
    if key not in {
        "motif3.block_count",
        "motif3.nextn_predict_layers",
        "motif3.mtp.shared_tensors_from_target",
    }
)
PAIR_VOCAB_ARRAY_KEYS = (
    "tokenizer.ggml.tokens",
    "tokenizer.ggml.token_type",
    "tokenizer.ggml.merges",
)


class SidecarValidationError(ValueError):
    """The GGUF is not the exact experimental Motif-3 BF16 MTP sidecar shape."""


def _field(reader: Any, key: str) -> Any:
    field = reader.fields.get(key)
    if field is None:
        raise SidecarValidationError(f"missing GGUF metadata key: {key}")
    value = field.contents()
    return value.item() if hasattr(value, "item") else value


def _equal_value(actual: Any, expected: Any) -> bool:
    if isinstance(expected, float):
        return isinstance(actual, (int, float)) and math.isclose(
            float(actual), expected, rel_tol=1e-6, abs_tol=1e-9
        )
    return actual == expected


def _sequence_sha256(value: Any) -> str:
    if not isinstance(value, (list, tuple)):
        raise SidecarValidationError("tokenizer array metadata is not an array")
    digest = hashlib.sha256()
    for item in value:
        encoded = json.dumps(
            item, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "little"))
        digest.update(encoded)
    return digest.hexdigest()


def validate_reader(reader: Any) -> dict[str, Any]:
    """Validate an already-open GGUFReader without reading tensor payloads."""

    version = int(_field(reader, "GGUF.version"))
    architecture = str(_field(reader, "general.architecture"))
    block_count = int(_field(reader, "motif3.block_count"))
    nextn_layers = int(_field(reader, "motif3.nextn_predict_layers"))
    tensor_count = int(_field(reader, "GGUF.tensor_count"))

    errors: list[str] = []
    if version != 3:
        errors.append(f"GGUF version is {version}, expected 3")
    if architecture != "motif3":
        errors.append(f"architecture is {architecture!r}, expected 'motif3'")
    if block_count != 54:
        errors.append(f"motif3.block_count is {block_count}, expected 54")
    if nextn_layers != 1:
        errors.append(
            f"motif3.nextn_predict_layers is {nextn_layers}, expected 1"
        )

    for key, expected in EXPECTED_METADATA.items():
        actual_value = _field(reader, key)
        if not _equal_value(actual_value, expected):
            errors.append(f"{key} is {actual_value!r}, expected {expected!r}")

    tokens = _field(reader, "tokenizer.ggml.tokens")
    token_types = _field(reader, "tokenizer.ggml.token_type")
    merges = _field(reader, "tokenizer.ggml.merges")
    if not isinstance(tokens, (list, tuple)) or len(tokens) != EXPECTED_VOCAB_SIZE:
        errors.append(
            f"tokenizer.ggml.tokens must contain exactly {EXPECTED_VOCAB_SIZE} entries"
        )
    if not isinstance(token_types, (list, tuple)) or len(token_types) != EXPECTED_VOCAB_SIZE:
        errors.append(
            f"tokenizer.ggml.token_type must contain exactly {EXPECTED_VOCAB_SIZE} entries"
        )
    if not isinstance(merges, (list, tuple)) or len(merges) != EXPECTED_MERGES_COUNT:
        errors.append(
            f"tokenizer.ggml.merges must contain exactly {EXPECTED_MERGES_COUNT} entries"
        )

    names = [str(tensor.name) for tensor in reader.tensors]
    actual = set(names)
    if len(names) != len(actual):
        errors.append("tensor table contains duplicate names")
    missing = sorted(EXPECTED_TENSORS - actual)
    extra = sorted(actual - EXPECTED_TENSORS)
    if tensor_count != 19 or len(names) != 19:
        errors.append(
            f"tensor count metadata/table is {tensor_count}/{len(names)}, expected 19/19"
        )
    if missing:
        errors.append(f"missing tensors: {missing}")
    if extra:
        errors.append(f"unexpected tensors: {extra}")

    tensor_types: dict[str, str] = {}
    for tensor in reader.tensors:
        tensor_type = getattr(tensor.tensor_type, "name", str(tensor.tensor_type))
        tensor_type = str(tensor_type)
        tensor_types[str(tensor.name)] = tensor_type
        if int(tensor.n_elements) <= 0 or int(tensor.n_bytes) <= 0:
            errors.append(f"empty tensor payload: {tensor.name}")
        contract = EXPECTED_TENSOR_CONTRACT.get(str(tensor.name))
        if contract is None:
            continue
        expected_shape, expected_type = contract
        actual_shape = tuple(int(value) for value in tensor.shape)
        if actual_shape != expected_shape:
            errors.append(
                f"tensor shape {tensor.name} is {actual_shape}, expected {expected_shape}"
            )
        if tensor_type != expected_type:
            errors.append(
                f"tensor type {tensor.name} is {tensor_type}, expected {expected_type}"
            )
        expected_elements = math.prod(expected_shape)
        expected_bytes = expected_elements * (2 if expected_type == "BF16" else 4)
        if int(tensor.n_elements) != expected_elements:
            errors.append(
                f"tensor element count {tensor.name} is {tensor.n_elements}, "
                f"expected {expected_elements}"
            )
        if int(tensor.n_bytes) != expected_bytes:
            errors.append(
                f"tensor byte count {tensor.name} is {tensor.n_bytes}, expected {expected_bytes}"
            )

    if errors:
        raise SidecarValidationError("; ".join(errors))
    return {
        "valid": True,
        "gguf_version": version,
        "architecture": architecture,
        "block_count": block_count,
        "nextn_predict_layers": nextn_layers,
        "tensor_count": tensor_count,
        "tensor_types": dict(sorted(tensor_types.items())),
        "exact_tensor_set": True,
        "exact_tensor_shapes": True,
        "exact_tensor_types": True,
        "exact_runtime_metadata": True,
        "tokenizer_token_count": len(tokens),
        "tokenizer_tokens_sha256": _sequence_sha256(tokens),
        "tokenizer_token_types_sha256": _sequence_sha256(token_types),
        "tokenizer_merges_count": len(merges),
        "tokenizer_merges_sha256": _sequence_sha256(merges),
        "shared_tensors_from_target": True,
        "tensor_payload_read": False,
    }


def validate_target_pair(sidecar_reader: Any, target_reader: Any) -> dict[str, Any]:
    """Bind the sidecar to the exact tokenizer and runtime metadata of its target."""

    errors: list[str] = []
    if str(_field(target_reader, "general.architecture")) != "motif3":
        errors.append("target general.architecture is not 'motif3'")
    if int(_field(target_reader, "motif3.block_count")) != 53:
        errors.append("target motif3.block_count is not 53")

    for key in PAIR_METADATA_KEYS:
        sidecar_value = _field(sidecar_reader, key)
        target_value = _field(target_reader, key)
        if not _equal_value(sidecar_value, target_value):
            errors.append(
                f"target-pair metadata mismatch for {key}: "
                f"sidecar={sidecar_value!r}, target={target_value!r}"
            )

    vocab_hashes: dict[str, str] = {}
    for key in PAIR_VOCAB_ARRAY_KEYS:
        sidecar_value = _field(sidecar_reader, key)
        target_value = _field(target_reader, key)
        sidecar_hash = _sequence_sha256(sidecar_value)
        target_hash = _sequence_sha256(target_value)
        if sidecar_hash != target_hash:
            errors.append(f"target-pair tokenizer mismatch for {key}")
        vocab_hashes[key] = sidecar_hash

    sidecar_globals = {
        str(tensor.name): tuple(int(value) for value in tensor.shape)
        for tensor in sidecar_reader.tensors
        if str(tensor.name) in EXPECTED_TARGET_SHARED_TENSORS
    }
    if sidecar_globals:
        errors.append(f"linked sidecar duplicates target tensors: {sidecar_globals}")
    target_globals = {
        str(tensor.name): tuple(int(value) for value in tensor.shape)
        for tensor in target_reader.tensors
        if str(tensor.name) in EXPECTED_TARGET_SHARED_TENSORS
    }
    if target_globals != EXPECTED_TARGET_SHARED_TENSORS:
        errors.append(
            f"target shared tensor shapes differ: "
            f"actual={target_globals}, expected={EXPECTED_TARGET_SHARED_TENSORS}"
        )

    if errors:
        raise SidecarValidationError("; ".join(errors))
    return {
        "valid": True,
        "target_block_count": 53,
        "runtime_metadata_exact": True,
        "tokenizer_arrays_exact": True,
        "shared_tensors_from_target": True,
        "target_shared_tensor_shapes_exact": True,
        "tokenizer_array_sha256": vocab_hashes,
        "tensor_payload_read": False,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_sidecar(
    path: Path,
    *,
    full_sha256: bool,
    target_gguf: Path | None = None,
) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise SidecarValidationError(f"not a regular file: {resolved}")
    try:
        from gguf import GGUFReader
    except ImportError as exc:
        raise SidecarValidationError(
            "gguf-py is unavailable; set PYTHONPATH to the pinned llama.cpp/gguf-py"
        ) from exc
    try:
        reader = GGUFReader(resolved, mode="r")
        receipt = validate_reader(reader)
    except (OSError, ValueError) as exc:
        if isinstance(exc, SidecarValidationError):
            raise
        raise SidecarValidationError(f"cannot inspect GGUF: {exc}") from exc
    target_pair = None
    if target_gguf is not None:
        target_resolved = target_gguf.resolve(strict=True)
        if not target_resolved.is_file():
            raise SidecarValidationError(f"target is not a regular file: {target_resolved}")
        try:
            target_reader = GGUFReader(target_resolved, mode="r")
            target_pair = validate_target_pair(reader, target_reader)
        except (OSError, ValueError) as exc:
            if isinstance(exc, SidecarValidationError):
                raise
            raise SidecarValidationError(f"cannot inspect target GGUF: {exc}") from exc
        target_pair.update(
            {
                "path": str(target_resolved),
                "size_bytes": target_resolved.stat().st_size,
                "sha256": None,
                "sha256_status": "not_computed_by_sidecar_checker",
            }
        )

    receipt.update(
        {
            "path": str(resolved),
            "size_bytes": resolved.stat().st_size,
            "sha256": _sha256(resolved) if full_sha256 else None,
            "sha256_status": "computed" if full_sha256 else "not_requested",
            "target_pair": target_pair,
            "sidecar_structure_gate_ready": full_sha256 and target_pair is not None,
        }
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gguf", type=Path, required=True)
    parser.add_argument(
        "--target-gguf",
        type=Path,
        help=(
            "target GGUF to bind by exact runtime metadata, tokenizer arrays, "
            "and target-shared tensor shapes (no target tensor payload is read)"
        ),
    )
    parser.add_argument(
        "--full-sha256",
        action="store_true",
        help="sequentially read the full sidecar and include its SHA-256",
    )
    args = parser.parse_args()
    try:
        receipt = inspect_sidecar(
            args.gguf,
            full_sha256=args.full_sha256,
            target_gguf=args.target_gguf,
        )
    except (OSError, SidecarValidationError) as exc:
        parser.error(str(exc))
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
