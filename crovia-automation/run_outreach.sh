#!/bin/bash
# CROVIA Outreach Runner
# Generates enhancement packages, then sends discussions.
# Skips targets already in sent_discussions.jsonl.
# Called by crovia-outreach.timer (Monday 06:00 UTC)

set -e

WORK_DIR="/opt/crovia/hf_datasets/global-ai-training-omissions"
AUTO_DIR="${WORK_DIR}/crovia-automation"
LOG="/var/log/crovia-outreach.log"
TIMESTAMP=$(date -Iseconds)

echo "[${TIMESTAMP}] ═══════════════════════════════════════" >> "${LOG}"
echo "[${TIMESTAMP}] CROVIA OUTREACH RUN STARTED" >> "${LOG}"

cd "${WORK_DIR}"

# Step 1: Generate enhancement packages for unsent targets
ENHANCE_LIMIT="${CROVIA_OUTREACH_LIMIT:-20}"
echo "[$(date -Iseconds)] Step 1: Generating enhancements (limit: ${ENHANCE_LIMIT})..." >> "${LOG}"

python3 -u "${AUTO_DIR}/model_card_enhancement.py" \
    --input "${AUTO_DIR}/targets_unified.json" \
    --output "${AUTO_DIR}/enhancements" \
    --limit "${ENHANCE_LIMIT}" \
    >> "${LOG}" 2>&1

# Step 2: Send discussions
echo "[$(date -Iseconds)] Step 2: Sending discussions (limit: ${ENHANCE_LIMIT})..." >> "${LOG}"

python3 -u "${AUTO_DIR}/discussion_sender.py" \
    --input "${AUTO_DIR}/targets_unified.json" \
    --enhancements "${AUTO_DIR}/enhancements" \
    --limit "${ENHANCE_LIMIT}" \
    --log "${AUTO_DIR}/sent_discussions.jsonl" \
    >> "${LOG}" 2>&1

# Step 3: Track discussion acceptance/rejection
echo "[$(date -Iseconds)] Step 3: Tracking discussion responses..." >> "${LOG}"

python3 -u "${AUTO_DIR}/enhancement_tracker.py" \
    --log "${AUTO_DIR}/sent_discussions.jsonl" \
    --state "${AUTO_DIR}/tracker_state.json" \
    --update --report \
    --public-json "${WORK_DIR}/webroot/registry/data/outreach_tracker.json" \
    >> "${LOG}" 2>&1

# Step 4: Update outreach status for public page
echo "[$(date -Iseconds)] Step 4: Updating outreach status..." >> "${LOG}"

python3 -u "${AUTO_DIR}/outreach_data_bridge.py" >> "${LOG}" 2>&1

# Step 5: Sync registry data
echo "[$(date -Iseconds)] Step 5: Syncing registry..." >> "${LOG}"

if [ -f "/opt/crovia/scripts/sync_registry.sh" ]; then
    /opt/crovia/scripts/sync_registry.sh >> "${LOG}" 2>&1
fi

echo "[$(date -Iseconds)] CROVIA OUTREACH RUN COMPLETE" >> "${LOG}"
echo "[$(date -Iseconds)] ═══════════════════════════════════════" >> "${LOG}"
