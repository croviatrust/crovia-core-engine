#!/usr/bin/env bash
set -euo pipefail

ROOT="/opt/crovia"
LOG="$ROOT/logs/hf_publish.log"

REPOS=(
  "hf_datasets/global-ai-training-omissions"
  "hf_datasets/cep-capsules"
  "hf_dsse_1m"
  "laion_dsse"
)

echo "=== Crovia HF publish $(date -Is) ===" | tee -a "$LOG"

for repo in "${REPOS[@]}"; do
  echo "--- repo: $repo" | tee -a "$LOG"
  cd "$ROOT/$repo" || { echo "MISSING: $repo" | tee -a "$LOG"; continue; }

  git status -sb | tee -a "$LOG"
  git add -A

  if ! git diff --cached --quiet; then
    git commit -m "crovia: automated evidence publish $(date -Is)" | tee -a "$LOG"
    git push | tee -a "$LOG"
  else
    echo "nothing to commit" | tee -a "$LOG"
  fi
done

echo "=== publish done ===" | tee -a "$LOG"
