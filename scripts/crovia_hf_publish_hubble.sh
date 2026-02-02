#!/usr/bin/env bash
set -eu
set -o pipefail

ROOT="/opt/crovia/hf_datasets/global-ai-training-omissions"
LOG="/opt/crovia/logs/hf_publish_hubble.log"

cd "$ROOT"

echo "=== Crovia Hubble publish $(date -Is) ===" | tee -a "$LOG"

# --- Allowlist: SOLO evidenza osservabile ---
ALLOWLIST=(
  "EVIDENCE.json"
  "snapshot_latest.json"
  "global_ranking.jsonl"
  "v0.1/EVIDENCE.json"
  "v0.1/snapshot_latest.json"
  "v0.1/global_ranking.jsonl"
  "open/README.md"
  "open/README_STATUS.md"
  "open/README_PRO_SHADOW.md"
  "open/signal/presence_latest.jsonl"
  "open/signal/verdict_matrix_latest.jsonl"
  "open/signal/ledger_status_latest.json"
  "open/signal/pro_shadow_pressure_latest.json"
  "open/drift/ddf_snapshots_latest.jsonl"
  "open/drift/ddf_drift_events_30d.jsonl"
  "open/forensic/absence_receipts_7d.jsonl"
  "open/temporal/temporal_pressure_30d.jsonl"
)

# --- 1) Verifica hash dichiarati in EVIDENCE.json ---
echo "[check] verifying declared sha256 hashes" | tee -a "$LOG"

if jq -e '.integrity.sha256 and (.integrity.sha256|type=="object")' EVIDENCE.json >/dev/null 2>&1; then
  jq -r '.integrity.sha256 | to_entries[] | "\(.key) \(.value)"' EVIDENCE.json | while read -r file hash; do
    if [ ! -f "$file" ]; then
      echo "❌ MISSING FILE: $file" | tee -a "$LOG"
      exit 1
    fi

    calc=$(sha256sum "$file" | awk '{print $1}')
    if [ "$calc" != "$hash" ]; then
      echo "❌ HASH MISMATCH: $file" | tee -a "$LOG"
      echo "expected=$hash" | tee -a "$LOG"
      echo "actual  =$calc" | tee -a "$LOG"
      exit 1
    fi
  done
  echo "✅ hash verification OK" | tee -a "$LOG"
else
  echo "[check] no integrity.sha256 map found in EVIDENCE.json — skip hash verification" | tee -a "$LOG"
fi

# --- 2) Stage SOLO allowlist ---
git reset >/dev/null

for f in "${ALLOWLIST[@]}"; do
  [ -f "$f" ] && git add "$f"
done

# --- 3) Verifica cambiamenti reali ---
if git diff --cached --quiet; then
  echo "No evidence change detected — skip publish" | tee -a "$LOG"
  exit 0
fi

# --- 4) Commit & push ---
git commit -m "crovia(hubble): publish verified observable evidence $(date -Is)" | tee -a "$LOG"
git push | tee -a "$LOG"

echo "=== Hubble publish OK ===" | tee -a "$LOG"
