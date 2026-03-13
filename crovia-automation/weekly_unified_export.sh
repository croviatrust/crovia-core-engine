#!/bin/bash
# CROVIA Weekly Unified Export
# Runs every Monday 06:00 UTC via cron
# Multi-source fetch (HF + GitHub + Ollama + PWC) → DDF → Index → Enhancements → Publish

set -e

DATASET_DIR="/opt/crovia/hf_datasets/global-ai-training-omissions"
LOG_DIR="/var/log/crovia"
TIMESTAMP=$(date +%Y-%m-%d_%H%M)
LOG_FILE="${LOG_DIR}/weekly_export_${TIMESTAMP}.log"

# Enhancement settings (conservative start)
ENHANCEMENT_ENABLED="${CROVIA_ENHANCEMENT_ENABLED:-0}"
ENHANCEMENT_LIMIT="${CROVIA_ENHANCEMENT_LIMIT:-50}"
ENHANCEMENT_DRY_RUN="${CROVIA_ENHANCEMENT_DRY_RUN:-1}"

mkdir -p "${LOG_DIR}"

echo "[$(date -Iseconds)] ═══════════════════════════════════════════" | tee -a "${LOG_FILE}"
echo "[$(date -Iseconds)]  CROVIA WEEKLY UNIFIED EXPORT STARTED" | tee -a "${LOG_FILE}"
echo "[$(date -Iseconds)]  Enhancement: ${ENHANCEMENT_ENABLED} (limit: ${ENHANCEMENT_LIMIT})" | tee -a "${LOG_FILE}"
echo "[$(date -Iseconds)] ═══════════════════════════════════════════" | tee -a "${LOG_FILE}"

cd "${DATASET_DIR}"

# Step 1: Fetch multi-source targets (HF + GitHub + Ollama + PWC)
echo "[$(date -Iseconds)] Step 1: Fetching multi-source targets..." | tee -a "${LOG_FILE}"

# Use new multi-source fetcher if available, fallback to old
if [ -f "crovia-automation/multi_source_fetcher.py" ]; then
    python3 crovia-automation/multi_source_fetcher.py \
        --hf-limit 35000 \
        --gh-limit 12000 \
        --ollama-limit 5000 \
        --pwc-limit 8000 \
        --output crovia-automation/multi_source_targets.jsonl \
        2>&1 | tee -a "${LOG_FILE}"
    
    # Also run legacy fetcher for compatibility
    CROVIA_MODELS_LIMIT=1500 \
    CROVIA_DATASETS_LIMIT=500 \
    CROVIA_MIN_DOWNLOADS=100 \
    CROVIA_INCLUDE_REGISTRY=1 \
    python3 crovia-automation/fetch_top_targets.py 2>&1 | tee -a "${LOG_FILE}"
else
    # Fallback to legacy fetcher only
    CROVIA_MODELS_LIMIT=1500 \
    CROVIA_DATASETS_LIMIT=500 \
    CROVIA_MIN_DOWNLOADS=100 \
    CROVIA_INCLUDE_REGISTRY=1 \
    python3 crovia-automation/fetch_top_targets.py 2>&1 | tee -a "${LOG_FILE}"
fi

TARGET_COUNT=$(python3 -c "import json; d=json.load(open('crovia-automation/targets_unified.json')); print(d['stats']['total_unified'])" 2>/dev/null || echo "unknown")
echo "[$(date -Iseconds)] Unified targets: ${TARGET_COUNT}" | tee -a "${LOG_FILE}"

# Step 2: Export DDF snapshots
echo "[$(date -Iseconds)] Step 2: Exporting DDF snapshots..." | tee -a "${LOG_FILE}"
CROVIA_TARGETS_FILE=crovia-automation/targets_unified.json \
CROVIA_DDF_PROGRESS_EVERY=500 \
CROVIA_DDF_INCREMENTAL=1 \
python3 crovia-automation/export_ddf_to_hf.py 2>&1 | tee -a "${LOG_FILE}"

# Step 3: Generate Disclosure Index
echo "[$(date -Iseconds)] Step 3: Generating Disclosure Index..." | tee -a "${LOG_FILE}"
python3 crovia-automation/generate_disclosure_index.py 2>&1 | tee -a "${LOG_FILE}"

# Step 4: Generate Disclosure Report
echo "[$(date -Iseconds)] Step 4: Generating Disclosure Report..." | tee -a "${LOG_FILE}"
python3 crovia-automation/generate_disclosure_report.py 2>&1 | tee -a "${LOG_FILE}"

# Step 5: Generate Model Card Enhancements (if enabled)
if [ "${ENHANCEMENT_ENABLED}" = "1" ] && [ -f "crovia-automation/model_card_enhancement.py" ]; then
    echo "[$(date -Iseconds)] Step 5: Generating Model Card Enhancements..." | tee -a "${LOG_FILE}"
    
    python3 crovia-automation/model_card_enhancement.py \
        --input crovia-automation/multi_source_targets.jsonl \
        --output crovia-automation/enhancements \
        --limit ${ENHANCEMENT_LIMIT} \
        2>&1 | tee -a "${LOG_FILE}"
    
    # Step 6: Send Enhancement Discussions (if not dry-run)
    if [ "${ENHANCEMENT_DRY_RUN}" = "0" ] && [ -f "crovia-automation/discussion_sender.py" ]; then
        echo "[$(date -Iseconds)] Step 6: Sending Enhancement Discussions..." | tee -a "${LOG_FILE}"
        
        python3 crovia-automation/discussion_sender.py \
            --input crovia-automation/multi_source_targets.jsonl \
            --enhancements crovia-automation/enhancements \
            --limit ${ENHANCEMENT_LIMIT} \
            --log crovia-automation/sent_discussions.jsonl \
            2>&1 | tee -a "${LOG_FILE}"
    else
        echo "[$(date -Iseconds)] Step 6: Enhancement sending SKIPPED (dry-run mode)" | tee -a "${LOG_FILE}"
    fi
else
    echo "[$(date -Iseconds)] Step 5-6: Enhancement DISABLED" | tee -a "${LOG_FILE}"
fi

# Step 7: Update Enhancement Tracker
if [ -f "crovia-automation/enhancement_tracker.py" ] && [ -f "crovia-automation/sent_discussions.jsonl" ]; then
    echo "[$(date -Iseconds)] Step 7: Updating Enhancement Tracker..." | tee -a "${LOG_FILE}"
    python3 crovia-automation/enhancement_tracker.py \
        --log crovia-automation/sent_discussions.jsonl \
        --state crovia-automation/tracker_state.json \
        --update --report \
        2>&1 | tee -a "${LOG_FILE}"
fi

# Step 7b: Export TPA data for registry and HF
if [ -f "crovia-automation/export_tpa_latest.py" ]; then
    echo "[$(date -Iseconds)] Step 7b: Exporting TPA data..." | tee -a "${LOG_FILE}"
    TPA_INPUT_DIR="/opt/crovia/tpa/open" \
    TPA_WEB_OUTPUT="/var/www/registry/data" \
    TPA_HF_OUTPUT="${DATASET_DIR}/open/tpa" \
    TPA_CHAIN_FILE="/opt/crovia/tpa/chain_state.json" \
    python3 crovia-automation/export_tpa_latest.py 2>&1 | tee -a "${LOG_FILE}"
else
    echo "[$(date -Iseconds)] Step 7b: TPA export SKIPPED (script not found)" | tee -a "${LOG_FILE}"
fi

# Step 8: Publish to HuggingFace
echo "[$(date -Iseconds)] Step 8: Publishing to HuggingFace..." | tee -a "${LOG_FILE}"
/opt/crovia/scripts/crovia_hf_publish_hubble.sh 2>&1 | tee -a "${LOG_FILE}"

echo "[$(date -Iseconds)] ═══════════════════════════════════════════" | tee -a "${LOG_FILE}"
echo "[$(date -Iseconds)]  CROVIA WEEKLY EXPORT COMPLETE" | tee -a "${LOG_FILE}"
echo "[$(date -Iseconds)]  Targets: ${TARGET_COUNT}" | tee -a "${LOG_FILE}"
echo "[$(date -Iseconds)]  Enhancement: ${ENHANCEMENT_ENABLED}" | tee -a "${LOG_FILE}"
echo "[$(date -Iseconds)] ═══════════════════════════════════════════" | tee -a "${LOG_FILE}"
