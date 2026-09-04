#!/usr/bin/env bash
set -euo pipefail

readonly EXPECTED_MODEL_NAME="motif3-direct-iq2xxs.gguf"
readonly EXPECTED_MODEL_SIZE="89720474560"
readonly EXPECTED_MODEL_SHA256="9d6f7aee57f0271223f51d69c63d8576a259809e9f05e2ac596512e940c80c5a"
readonly EXPECTED_TEMPLATE_NAME="motif3-llama.cpp.jinja"
readonly EXPECTED_TEMPLATE_SIZE="6759"
readonly EXPECTED_TEMPLATE_SHA256="25877a0b07679b1c1702d9f9211c8f1e8421537113b9dcf993f7e45f7caf3adc"
readonly EXPECTED_RUNTIME_COMMIT="cc3f13b3f172978d7b3c215780d4cc98bb0e1c80"
readonly EXPECTED_TOKENIZER_PATCH_SIZE="43623"
readonly EXPECTED_TOKENIZER_PATCH_SHA256="5eba842cd63731e3ee39c60c43134ef59a3a64c9d28c2aa58c3073225c6545cf"
readonly EXPECTED_RUNTIME_DIFF_SHA256="09abc52c2f7ff9f2cb3e9b8edd3af03684840969d0cdc7f24fd7aa63ca3207f3"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly TOKENIZER_PATCH="$SCRIPT_DIR/../patches/motif3-tokenizer-exact-v1.patch"

usage() {
    printf 'Usage: %s MODEL_DIR [RUNTIME_DIR]\n' "${0##*/}"
    printf '\n'
    printf 'Read-only verification of the released GGUF, chat template, tokenizer patch, and optional patched runtime checkout.\n'
    printf 'The full model SHA-256 reads all 89.72 GB and may take several minutes.\n'
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

require_regular_file() {
    local path="$1"
    [[ ! -L "$path" ]] || die "refusing symlink: $path"
    [[ -f "$path" ]] || die "missing regular file: $path"
}

verify_file() {
    local path="$1"
    local expected_size="$2"
    local expected_sha256="$3"
    local label="$4"
    local actual_size
    local actual_sha256

    require_regular_file "$path"
    actual_size="$(stat -c '%s' -- "$path")"
    [[ "$actual_size" == "$expected_size" ]] || \
        die "$label size mismatch: expected $expected_size, got $actual_size"

    actual_sha256="$(sha256sum -- "$path")"
    actual_sha256="${actual_sha256%% *}"
    [[ "$actual_sha256" == "$expected_sha256" ]] || \
        die "$label SHA-256 mismatch: expected $expected_sha256, got $actual_sha256"

    printf 'PASS %-10s %s bytes  %s\n' "$label" "$actual_size" "$actual_sha256"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

[[ "$#" -ge 1 && "$#" -le 2 ]] || {
    usage >&2
    exit 2
}

readonly MODEL_DIR="$1"
readonly RUNTIME_DIR="${2:-}"

[[ -d "$MODEL_DIR" ]] || die "model directory not found: $MODEL_DIR"
[[ ! -L "$MODEL_DIR" ]] || die "refusing symlinked model directory: $MODEL_DIR"

verify_file \
    "$MODEL_DIR/$EXPECTED_MODEL_NAME" \
    "$EXPECTED_MODEL_SIZE" \
    "$EXPECTED_MODEL_SHA256" \
    "model"
verify_file \
    "$MODEL_DIR/$EXPECTED_TEMPLATE_NAME" \
    "$EXPECTED_TEMPLATE_SIZE" \
    "$EXPECTED_TEMPLATE_SHA256" \
    "template"
verify_file \
    "$TOKENIZER_PATCH" \
    "$EXPECTED_TOKENIZER_PATCH_SIZE" \
    "$EXPECTED_TOKENIZER_PATCH_SHA256" \
    "patch"

if [[ -n "$RUNTIME_DIR" ]]; then
    [[ -d "$RUNTIME_DIR/.git" ]] || die "runtime is not a Git checkout: $RUNTIME_DIR"
    [[ ! -L "$RUNTIME_DIR" ]] || die "refusing symlinked runtime directory: $RUNTIME_DIR"
    actual_runtime_commit="$(git -C "$RUNTIME_DIR" rev-parse --verify HEAD)"
    [[ "$actual_runtime_commit" == "$EXPECTED_RUNTIME_COMMIT" ]] || \
        die "runtime commit mismatch: expected $EXPECTED_RUNTIME_COMMIT, got $actual_runtime_commit"
    runtime_diff_sha256="$(git -C "$RUNTIME_DIR" diff --binary --no-ext-diff | sha256sum)"
    runtime_diff_sha256="${runtime_diff_sha256%% *}"
    [[ "$runtime_diff_sha256" == "$EXPECTED_RUNTIME_DIFF_SHA256" ]] || \
        die "runtime patch mismatch: expected $EXPECTED_RUNTIME_DIFF_SHA256, got $runtime_diff_sha256"
    printf 'PASS %-10s %s + %s\n' "runtime" "$actual_runtime_commit" "$runtime_diff_sha256"
fi

printf 'All requested checks passed. No files were changed.\n'
