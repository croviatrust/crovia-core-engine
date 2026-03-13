#!/bin/bash
# CROVIA DB → JSONL Export Script
# Exports all observations from PostgreSQL to JSONL format
# Run from Hetzner server

set -e

DATASET_DIR="${CROVIA_DATASET_DIR:-/opt/crovia/CROVIA_DEV/global-ai-training-omissions}"
OUTPUT_FILE="$DATASET_DIR/observations.jsonl"
TEMP_CSV="/tmp/crovia_observations_export.csv"

echo "[1/5] Exporting observations from PostgreSQL..."

# Export all observations to CSV
docker exec -i tpr-postgres psql -U tpr -d tpr -c "
COPY (
    SELECT 
        observation_id,
        target_id,
        observation_type,
        observation_timestamp,
        receipt_hash,
        source
    FROM tpr_observation
    ORDER BY observation_id ASC
) TO STDOUT WITH CSV HEADER DELIMITER ','
" > "$TEMP_CSV"

TOTAL_ROWS=$(tail -n +2 "$TEMP_CSV" | wc -l)
echo "[INFO] Exported $TOTAL_ROWS observations from DB"

echo "[2/5] Getting merkle root..."
MERKLE_ROOT=$(tail -1 /opt/crovia/data/merkle_timeline.jsonl | python3 -c "import sys, json; print(json.load(sys.stdin).get('merkle_root', 'unknown'))" 2>/dev/null || echo "unknown")
echo "[INFO] Merkle root: $MERKLE_ROOT"

echo "[3/5] Processing observations and calculating temporal metrics..."

# Create output directory
mkdir -p "$DATASET_DIR"

# Process CSV and generate JSONL with Python
python3 << 'PYTHON_SCRIPT'
import csv
import json
import sys
from datetime import datetime
from collections import defaultdict

# Read CSV
observations_by_target = defaultdict(list)

with open('/tmp/crovia_observations_export.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        target_id = row['target_id']
        observations_by_target[target_id].append({
            'observation_id': int(row['observation_id']),
            'observation_type': row['observation_type'],
            'observed_at': row['observation_timestamp'],
            'receipt_hash': row['receipt_hash'],
            'source': row['source']
        })

# Get merkle root from environment or default
import os
merkle_root = os.getenv('MERKLE_ROOT', 'unknown')
dataset_dir = os.getenv('CROVIA_DATASET_DIR', '/opt/crovia/CROVIA_DEV/global-ai-training-omissions')
output_file = f"{dataset_dir}/observations.jsonl"

# Calculate temporal metrics and write JSONL
exported_count = 0
with open(output_file, 'w') as out:
    for target_id, observations in observations_by_target.items():
        # Sort by timestamp
        observations.sort(key=lambda x: x['observed_at'])
        
        # Calculate temporal metrics
        timestamps = [datetime.fromisoformat(obs['observed_at'].replace('+00', '')) for obs in observations]
        first_seen = min(timestamps)
        last_seen = max(timestamps)
        days_monitored = (last_seen - first_seen).days
        
        # Calculate absence streak (consecutive absence days from end)
        absence_streak_days = 0
        if observations[-1]['observation_type'] == 'absence':
            for obs in reversed(observations):
                if obs['observation_type'] == 'absence':
                    obs_time = datetime.fromisoformat(obs['observed_at'].replace('+00', ''))
                    absence_streak_days = (last_seen - obs_time).days
                else:
                    break
        
        # Export each observation with enriched metadata
        for obs in observations:
            record = {
                'receipt_hash': f"sha256:{obs['receipt_hash']}" if obs['receipt_hash'] else "unknown",
                'target_id': target_id,
                'observation_type': obs['observation_type'],
                'observed_at': obs['observed_at'],
                
                # Temporal metrics (derived mathematically)
                'first_seen': first_seen.isoformat() + 'Z',
                'last_seen': last_seen.isoformat() + 'Z',
                'days_monitored': days_monitored,
                'observation_count': len(observations),
                'absence_streak_days': absence_streak_days,
                
                # Registry metadata
                'source': obs['source'],
                'registry_endpoint': 'https://registry.croviatrust.com',
                'merkle_root': merkle_root
            }
            
            out.write(json.dumps(record, ensure_ascii=False) + '\n')
            exported_count += 1

print(f"[INFO] Exported {exported_count} observations to {output_file}")
PYTHON_SCRIPT

echo "[4/5] Verifying export..."
EXPORTED_COUNT=$(wc -l < "$OUTPUT_FILE")
echo "[INFO] JSONL file contains $EXPORTED_COUNT lines"

if [ "$TOTAL_ROWS" -ne "$EXPORTED_COUNT" ]; then
    echo "[ERROR] Mismatch! DB has $TOTAL_ROWS but exported $EXPORTED_COUNT"
    exit 1
fi

echo "[PASS] All observations exported successfully"

echo "[5/5] Sample records:"
head -3 "$OUTPUT_FILE" | python3 -m json.tool

echo ""
echo "================================================================================"
echo "EXPORT COMPLETED"
echo "================================================================================"
echo "DB observations: $TOTAL_ROWS"
echo "Exported observations: $EXPORTED_COUNT"
echo "Output file: $OUTPUT_FILE"
echo "Merkle root: $MERKLE_ROOT"
echo "================================================================================"

# Cleanup
rm -f "$TEMP_CSV"
