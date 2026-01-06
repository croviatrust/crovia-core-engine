#!/usr/bin/env bash
set -euo pipefail

ROOT="/opt/crovia/hf_datasets/global-ai-training-omissions"
STATUS_FILE="$ROOT/open/README_STATUS.md"
README="$ROOT/README.md"

START="<!-- CROVIA_LEDGER_STATUS_START -->"
END="<!-- CROVIA_LEDGER_STATUS_END -->"

if [ ! -f "$STATUS_FILE" ]; then
  echo "❌ missing $STATUS_FILE"
  exit 1
fi

STATUS_BLOCK=$(sed '1,200p' "$STATUS_FILE")

awk -v start="$START" -v end="$END" -v block="$STATUS_BLOCK" '
BEGIN {print_block=1}
/start/ {
  print start
  print ""
  print block
  print ""
  print end
  print_block=0
  skip=1
  next
}
/end/ {skip=0; next}
skip==1 {next}
{if (print_block) print}
' "$README" > "$README.tmp"

mv "$README.tmp" "$README"
