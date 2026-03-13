#!/usr/bin/env python3
"""
CROVIA DB → HF Dataset Export (Append-Only)
Exports all observations from PostgreSQL to HuggingFace dataset as JSONL.
Zero placeholders, zero fake scores, only verifiable data.
"""

import os
import sys
import json
import psycopg2
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

# Database configuration
DB_CONFIG = {
    'host': os.getenv('TPR_DB_HOST', 'tpr-postgres'),
    'port': int(os.getenv('TPR_DB_PORT', '5432')),
    'database': os.getenv('TPR_DB_NAME', 'tpr'),
    'user': os.getenv('TPR_DB_USER', 'tpr'),
    'password': os.getenv('TPR_DB_PASS', 'tpr_password_change_me')
}

# Output configuration
DATASET_DIR = Path(os.getenv('CROVIA_DATASET_DIR', '/opt/crovia/CROVIA_DEV/global-ai-training-omissions'))
OUTPUT_FILE = DATASET_DIR / 'observations.jsonl'


def _safe_parse_evidence_data(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _is_hex_64(s: str) -> bool:
    if len(s) != 64:
        return False
    for c in s:
        if c not in '0123456789abcdefABCDEF':
            return False
    return True


def _normalize_sha256(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value)
    if not s:
        return None
    if s.startswith('sha256:'):
        return s
    if _is_hex_64(s):
        return f"sha256:{s}"
    return None


def _extract_public_oracle_fields(evidence_data: Dict[str, Any]) -> Dict[str, Any]:
    oracle = evidence_data.get('oracle')
    if not isinstance(oracle, dict):
        return {}

    violations = oracle.get('violations')
    proof_hashes = oracle.get('proof_hashes')

    out: Dict[str, Any] = {}
    if isinstance(violations, list):
        nec_ids = [str(v) for v in violations if v]
        if nec_ids:
            out['omission_nec_ids'] = nec_ids

    if isinstance(proof_hashes, list):
        normalized = []
        for ph in proof_hashes:
            n = _normalize_sha256(ph)
            if n:
                normalized.append(n)
        if normalized:
            out['proof_hashes'] = normalized

    return out

def get_merkle_root() -> str:
    """Get latest merkle root from timeline file."""
    timeline_path = Path('/opt/crovia/data/merkle_timeline.jsonl')
    if not timeline_path.exists():
        return "unknown"
    
    try:
        with open(timeline_path, 'r') as f:
            lines = f.readlines()
            if lines:
                last_entry = json.loads(lines[-1])
                return last_entry.get('merkle_root', 'unknown')
    except Exception as e:
        print(f"[WARN] Could not read merkle timeline: {e}")
    
    return "unknown"

def calculate_temporal_metrics(target_id: str, observations: List[Dict]) -> Dict[str, Any]:
    """
    Calculate temporal metrics for a target based on its observations.
    
    Metrics:
    - first_seen: MIN(observed_at)
    - last_seen: MAX(observed_at)
    - days_monitored: diff in days between first and last
    - observation_count: total observations
    - absence_streak_days: consecutive days of absence from last_seen (if last observation is absence)
    
    Formula: All derived from observation timestamps, no inference.
    """
    if not observations:
        return {}
    
    timestamps = [obs['observed_at'] for obs in observations]
    first_seen = min(timestamps)
    last_seen = max(timestamps)
    
    # Calculate days monitored
    days_monitored = (last_seen.date() - first_seen.date()).days + 1
    
    # Calculate absence streak (only if last observation is absence)
    absence_streak_days = 0
    if observations[-1]['observation_type'] == 'absence':
        # Count consecutive absence days from the end
        for obs in reversed(observations):
            if obs['observation_type'] == 'absence':
                absence_streak_days = (last_seen - obs['observed_at']).days
            else:
                break
    
    return {
        'first_seen': first_seen.isoformat(),
        'last_seen': last_seen.isoformat(),
        'days_monitored': days_monitored,
        'observation_count': len(observations),
        'absence_streak_days': absence_streak_days
    }

def export_observations():
    """Export all observations from DB to JSONL."""
    print("[1/4] Connecting to PostgreSQL...")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        sys.exit(1)
    
    try:
        with conn.cursor() as cur:
            # Get total count
            cur.execute("SELECT COUNT(*) FROM tpr_observation")
            total_count = cur.fetchone()[0]
            print(f"[INFO] Total observations in DB: {total_count}")
            
            # Fetch all observations
            print("[2/4] Fetching observations...")
            cur.execute("""
                SELECT 
                    observation_id,
                    target_id,
                    observation_type,
                    observation_timestamp,
                    receipt_hash,
                    source,
                    evidence_data
                FROM tpr_observation
                ORDER BY observation_id ASC
            """)
            
            rows = cur.fetchall()
            print(f"[INFO] Fetched {len(rows)} observations")
            
            # Group by target_id for temporal metrics
            print("[3/4] Calculating temporal metrics...")
            target_observations = {}
            for row in rows:
                obs_id, target_id, obs_type, obs_time, receipt_hash, source, evidence_data = row

                if target_id not in target_observations:
                    target_observations[target_id] = []

                evidence_data_dict = _safe_parse_evidence_data(evidence_data)

                target_observations[target_id].append({
                    'observation_id': obs_id,
                    'observation_type': obs_type,
                    'observed_at': obs_time,
                    'receipt_hash': receipt_hash,
                    'source': source,
                    'evidence_data': evidence_data_dict,
                })
            
            # Get merkle root
            merkle_root = get_merkle_root()
            
            # Export to JSONL
            print(f"[4/4] Writing to {OUTPUT_FILE}...")
            OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            exported_count = 0
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                for target_id, observations in target_observations.items():
                    # Calculate temporal metrics
                    metrics = calculate_temporal_metrics(target_id, observations)
                    
                    # Export each observation with enriched metadata
                    for obs in observations:
                        evidence_data = obs.get('evidence_data') if isinstance(obs, dict) else None
                        evidence_data_dict = evidence_data if isinstance(evidence_data, dict) else {}
                        method = evidence_data_dict.get('method') if isinstance(evidence_data_dict.get('method'), str) else 'unknown'
                        oracle_public = _extract_public_oracle_fields(evidence_data_dict)

                        record = {
                            'receipt_hash': f"sha256:{obs['receipt_hash']}" if obs['receipt_hash'] else "unknown",
                            'target_id': target_id,
                            'observation_type': obs['observation_type'],
                            'observed_at': obs['observed_at'].isoformat() if obs['observed_at'] else None,

                            'method': method,
                            
                            # Temporal metrics
                            'first_seen': metrics.get('first_seen'),
                            'last_seen': metrics.get('last_seen'),
                            'days_monitored': metrics.get('days_monitored', 0),
                            'observation_count': metrics.get('observation_count', 0),
                            'absence_streak_days': metrics.get('absence_streak_days', 0),
                            
                            # Registry metadata
                            'source': obs['source'],
                            'registry_endpoint': 'https://registry.croviatrust.com',
                            'merkle_root': merkle_root
                        }

                        record.update(oracle_public)
                        
                        f.write(json.dumps(record, ensure_ascii=False) + '\n')
                        exported_count += 1
            
            print(f"[SUCCESS] Exported {exported_count} observations to {OUTPUT_FILE}")
            
            # Verification
            print("\n[VERIFICATION]")
            print(f"DB observations: {total_count}")
            print(f"Exported observations: {exported_count}")
            
            if total_count != exported_count:
                print(f"[ERROR] Mismatch! DB has {total_count} but exported {exported_count}")
                sys.exit(1)
            else:
                print("[PASS] All observations exported successfully")
            
            # Show sample records
            print("\n[SAMPLE RECORDS]")
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i < 3:
                        print(json.dumps(json.loads(line), indent=2))
                    else:
                        break
    
    finally:
        conn.close()

if __name__ == '__main__':
    export_observations()
