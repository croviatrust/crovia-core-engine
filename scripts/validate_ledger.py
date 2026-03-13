#!/usr/bin/env python3
"""
Ledger Validator
================

Compares the SQLite ledger against the filesystem to ensure:
- No missing files
- No orphan records in SQL
- Payload hashes match (integrity check)
"""

import sys
import json
import hashlib
from pathlib import Path

# Add pro-engine to path
sys.path.insert(0, str(Path(__file__).parent.parent / "crovia-pro-engine"))

from croviapro.database.ledger import get_connection

def validate_ledger():
    repo_root = Path(__file__).parent.parent
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Check SQL records against filesystem
        cursor.execute("SELECT id, artifact_hash, target_id, source_file, payload_hash, signal_type FROM evidence_ledger")
        records = cursor.fetchall()
        
        missing_on_disk = 0
        hash_mismatch = 0
        total = len(records)
        
        print(f"Validating {total} ledger entries against filesystem...")
        
        for row in records:
            source_file = repo_root / row["source_file"]
            
            if not source_file.exists():
                missing_on_disk += 1
                continue
                
            if row["signal_type"] == "sonar_report_v2":
                try:
                    with open(source_file, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                    
                    payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
                    disk_hash = hashlib.sha256(payload_str.encode('utf-8')).hexdigest()
                    
                    if disk_hash != row["payload_hash"]:
                        hash_mismatch += 1
                except Exception:
                    missing_on_disk += 1
                    
        # 2. Check filesystem against SQL (Sonar Reports)
        sonar_dir = repo_root / "sonar_runs_v2"
        orphan_files = 0
        if sonar_dir.exists():
            for json_file in sonar_dir.glob("*.json"):
                if json_file.name == "run_summaries.json":
                    continue
                rel_path = json_file.relative_to(repo_root).as_posix()
                cursor.execute("SELECT 1 FROM evidence_ledger WHERE source_file = ?", (rel_path,))
                if not cursor.fetchone():
                    orphan_files += 1
                    
        print("\n--- VALIDATION REPORT ---")
        print(f"Total Ledger Records: {total}")
        print(f"Missing Files on Disk: {missing_on_disk}")
        print(f"Payload Integrity Mismatch: {hash_mismatch}")
        print(f"Unindexed Sonar Files (Orphans): {orphan_files}")
        print("-------------------------")
        
        if missing_on_disk == 0 and hash_mismatch == 0 and orphan_files == 0:
            print("STATUS: PERFECT SYNC")
        else:
            print("STATUS: DRIFT DETECTED")

if __name__ == "__main__":
    validate_ledger()
