#!/usr/bin/env sh
set -eu

# Resolve repository directory (this script lives at repo root)
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

# Optional overrides:
#   PYTHON_BIN=python3 sh extract.sh <input_dir> <output_dir>
PYTHON_BIN="${PYTHON_BIN:-python3}"
INPUT_DIR="${1:-../books}"
OUTPUT_DIR="${2:-./SkillBank}"

"$PYTHON_BIN" "$SCRIPT_DIR/batch_legal_extraction.py" \
    --folder "$INPUT_DIR" \
    --output "$OUTPUT_DIR"