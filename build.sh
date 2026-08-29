#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

OUTPUT_PATH="${1:-"$SCRIPT_DIR/dist/fastfx.zip"}"
ADDON_DIRECTORY="$SCRIPT_DIR/fastfx"

if [[ ! -d "$ADDON_DIRECTORY" ]]; then
    echo "FastFX add-on directory was not found: $ADDON_DIRECTORY" >&2
    exit 1
fi

OUTPUT_DIRECTORY="$(dirname -- "$OUTPUT_PATH")"
mkdir -p "$OUTPUT_DIRECTORY"

# Remove an existing archive, since zip doesn't have PowerShell's -Force equivalent.
rm -f "$OUTPUT_PATH"

# Package the fastfx directory itself, matching Compress-Archive -Path behavior.
(
    cd -- "$SCRIPT_DIR"
    zip -r "$OUTPUT_PATH" "fastfx"
)

echo "Built Blender add-on ZIP: $OUTPUT_PATH"