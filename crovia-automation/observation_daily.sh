#!/bin/bash
# observation_daily.sh — Multi-source daily pipeline v3
# 7 steps: discovery, compliance, bridge, drift, forensic, TPA, lineage, sonar
# Created: 2026-02-17 | Updated: 2026-02-17 (added Model Sonar)

set -e

WORK_DIR="/opt/crovia/hf_datasets/global-ai-training-omissions"
AUTO_DIR="${WORK_DIR}/crovia-automation"
PRO_ENGINE="/opt/crovia/CROVIA_DEV/crovia-pro-engine"
LOG="/var/log/crovia/observation_daily.log"

echo "[$(date -Iseconds)] === OBSERVATION DAILY START ===" >> "${LOG}"

cd "${WORK_DIR}"
set -a; source /etc/crovia/tpr.env; set +a

# Step 0: Discover new targets (public API, no auth)
# v3: multi-source — HF + Papers With Code + GitHub + Ollama
echo "[$(date -Iseconds)] Step 0: Discovering new targets (aggressive)..." >> "${LOG}"
python3 -u "${AUTO_DIR}/discover_targets.py" \
    --output "${AUTO_DIR}/targets_unified.json" \
    --existing "${AUTO_DIR}/targets_unified.json" \
    --limit 500 \
    --aggressive \
    >> "${LOG}" 2>&1 || true

# Step 1: Generate compliance reports (needs PYTHONPATH for croviapro)
echo "[$(date -Iseconds)] Step 1: Compliance reports..." >> "${LOG}"
PYTHONPATH="${PRO_ENGINE}" \
python3 -u "${AUTO_DIR}/compliance_report_generator.py" \
    --all-outreach \
    >> "${LOG}" 2>&1 || true

# Step 1b: GitHub outreach (optional)
echo "[$(date -Iseconds)] Step 1b: GitHub outreach (optional)..." >> "${LOG}"
GITHUB_LIMIT="${CROVIA_GITHUB_OUTREACH_LIMIT:-15}"
GITHUB_TARGETS="${AUTO_DIR}/targets_github.json"
if [ -f "${GITHUB_TARGETS}" ]; then
  if [ -n "${GITHUB_TOKEN}" ] || [ "${CROVIA_GITHUB_DRY_RUN}" = "1" ]; then
    echo "[$(date -Iseconds)] Step 1b.1: Generating enhancement packages (limit ${GITHUB_LIMIT})..." >> "${LOG}"
    python3 -u "${AUTO_DIR}/model_card_enhancement.py" \
        --input "${GITHUB_TARGETS}" \
        --output "${AUTO_DIR}/enhancements" \
        --limit "${GITHUB_LIMIT}" \
        >> "${LOG}" 2>&1 || true

    echo "[$(date -Iseconds)] Step 1b.2: Sending GitHub issues (limit ${GITHUB_LIMIT})..." >> "${LOG}"
    python3 -u "${AUTO_DIR}/github_issue_sender.py" \
        --input "${GITHUB_TARGETS}" \
        --enhancements "${AUTO_DIR}/enhancements" \
        --limit "${GITHUB_LIMIT}" \
        --log "${AUTO_DIR}/github_issues_sent.jsonl" \
        >> "${LOG}" 2>&1 || true
  else
    echo "[$(date -Iseconds)] Step 1b skipped: GITHUB_TOKEN not set and CROVIA_GITHUB_DRY_RUN!=1" >> "${LOG}"
  fi
else
  echo "[$(date -Iseconds)] Step 1b skipped: targets_github.json not found" >> "${LOG}"
fi

# Step 2: Outreach data bridge (uses local JSONL, no HF API)
echo "[$(date -Iseconds)] Step 2: Outreach bridge..." >> "${LOG}"
OUTREACH_HF_LOG="${AUTO_DIR}/sent_discussions.jsonl" \
TPA_DATA_FILE="/var/www/registry/data/tpa_latest.json" \
OUTREACH_OUTPUT_DIR="/var/www/registry/data" \
python3 -u "${AUTO_DIR}/outreach_data_bridge.py" >> "${LOG}" 2>&1 || true

# Step 2b: Drift detection (snapshot + compare, pure HTTP, no HfApi)
echo "[$(date -Iseconds)] Step 2b: Drift detection (DDF)..." >> "${LOG}"
CROVIA_DATASET_DIR="${WORK_DIR}" \
CROVIA_DDF_INCREMENTAL=1 \
CROVIA_DDF_MAX_RPH=1200 \
python3 -u "${AUTO_DIR}/export_ddf_to_hf.py" >> "${LOG}" 2>&1 || true

# Step 3: Forensic correlator
echo "[$(date -Iseconds)] Step 3: Forensic correlator..." >> "${LOG}"
FORENSIC_DRIFT_FILE="${WORK_DIR}/open/drift/ddf_drift_events_30d.jsonl" \
FORENSIC_OUTREACH_FILE="${AUTO_DIR}/sent_discussions.jsonl" \
TPA_DATA_FILE="/var/www/registry/data/tpa_latest.json" \
FORENSIC_OUTPUT_DIR="/var/www/registry/data" \
python3 -u "${AUTO_DIR}/forensic_correlator.py" >> "${LOG}" 2>&1 || true

# Step 4: Export TPA latest
echo "[$(date -Iseconds)] Step 4: TPA export..." >> "${LOG}"
python3 -u "${AUTO_DIR}/export_tpa_latest.py" >> "${LOG}" 2>&1 || true

# Step 5: Model Sonar — deep provenance chain analysis (50 models/day)
# Output is PRIVATE (/opt/crovia/data/sonar/) — trade secret, never public
echo "[$(date -Iseconds)] Step 5: Model Sonar provenance scan..." >> "${LOG}"
mkdir -p /opt/crovia/data/sonar
python3 -u "${AUTO_DIR}/model_sonar.py" \
    --targets "${AUTO_DIR}/targets_unified.json" \
    --limit 50 \
    --output /opt/crovia/data/sonar/provenance_chains.json \
    >> "${LOG}" 2>&1 || true

# Step 6: Provenance Graph (Lineage + Sonar fusion)
# Full graph (private) + public graph (stripped, no Sonar data) for D3.js viz
echo "[$(date -Iseconds)] Step 6: Provenance Graph (Lineage + Sonar)..." >> "${LOG}"
python3 -u "${AUTO_DIR}/lineage_builder.py" \
    --output /var/www/registry/data/lineage_graph.json \
    --output-full /opt/crovia/data/sonar/provenance_graph_full.json \
    --compliance-dir /opt/crovia/data/compliance_full \
    --sonar /opt/crovia/data/sonar/provenance_chains.json \
    >> "${LOG}" 2>&1 || true

echo "[$(date -Iseconds)] === OBSERVATION DAILY DONE ===" >> "${LOG}"
