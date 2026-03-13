#!/usr/bin/env python3
"""
CROVIA Enhancement Tracker
==========================

Tracks the status of sent enhancement discussions:
- Who received suggestions
- Who accepted (merged/acknowledged)
- Who declined (closed without action)
- Response rates over time

Integrates with the Open Plane data structure.

Author: Crovia Engineering
"""

import json
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict

try:
    from huggingface_hub import HfApi
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False


@dataclass
class EnhancementRecord:
    """Record of a single enhancement suggestion."""
    target_id: str
    repo_id: str
    discussion_num: Optional[int]
    sent_at: str
    status: str  # pending, accepted, declined, no_response
    checked_at: Optional[str] = None
    response_type: Optional[str] = None  # merged, acknowledged, closed, none
    days_since_sent: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _load_hf_token() -> Optional[str]:
    """Load HF token from env or tpr.env file."""
    token = os.getenv("HF_TOKEN")
    if token:
        return token
    for p in ["/etc/crovia/tpr.env", os.path.join(os.path.dirname(__file__), "..", ".env")]:
        if os.path.exists(p):
            with open(p) as f:
                for line in f:
                    if line.strip().startswith("HF_TOKEN="):
                        return line.strip().split("=", 1)[1].strip('"').strip("'")
    return None


class EnhancementTracker:
    """
    Tracks enhancement suggestion outcomes.
    
    Checks HuggingFace discussions to determine if suggestions
    were accepted, declined, or ignored.
    """
    
    def __init__(self, hf_token: Optional[str] = None):
        self.hf_token = hf_token or _load_hf_token()
        self.api = HfApi(token=self.hf_token) if HF_AVAILABLE and self.hf_token else None
        if self.api:
            print(f"  HF API: authenticated (token ...{self.hf_token[-4:]})")
        else:
            print(f"  HF API: NOT available (no token or huggingface_hub missing)")
        self.records: Dict[str, EnhancementRecord] = {}
    
    def load_sent_log(self, log_path: str):
        """Load sent discussions from log file."""
        if not os.path.exists(log_path):
            return
        
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                if data.get("status") in ("sent", "acknowledged", "closed", "merged", "accepted") and data.get("discussion_num"):
                    repo_id = data.get("repo_id") or data.get("target_id", "")
                    record = EnhancementRecord(
                        target_id=data.get("target_id", ""),
                        repo_id=repo_id,
                        discussion_num=data.get("discussion_num"),
                        sent_at=data.get("sent_at", ""),
                        status="pending",
                    )
                    key = f"{repo_id}#{record.discussion_num}"
                    self.records[key] = record
    
    def check_discussion_status(self, repo_id: str, discussion_num: int) -> tuple:
        """
        Check the current status of a discussion.
        
        Returns: (status, response_type)
        - status: pending, accepted, declined, no_response
        - response_type: merged, acknowledged, closed, none
        """
        if not self.api:
            return "pending", "none"
        
        try:
            # Get discussion details
            discussion = self.api.get_discussion_details(
                repo_id=repo_id,
                discussion_num=discussion_num,
            )
            
            # Check status
            if discussion.status == "merged":
                return "accepted", "merged"
            elif discussion.status == "closed":
                # Check if there were positive comments before closing
                # For now, assume closed = declined
                return "declined", "closed"
            else:  # open
                # Check for acknowledgment comments
                if hasattr(discussion, 'events') and len(discussion.events) > 1:
                    return "pending", "acknowledged"
                return "pending", "none"
                
        except Exception as e:
            return "pending", "none"
    
    def update_all_statuses(self, delay: float = 1.5) -> Dict[str, int]:
        """Update status for all tracked discussions with rate limiting."""
        stats = {"pending": 0, "accepted": 0, "declined": 0, "no_response": 0}
        now = datetime.now(timezone.utc)
        checked = 0
        total_to_check = sum(1 for r in self.records.values() if r.status not in ["accepted", "declined"])
        
        for key, record in self.records.items():
            if record.status in ["accepted", "declined"]:
                stats[record.status] += 1
                continue
            
            # Calculate days since sent
            try:
                sent_dt = datetime.fromisoformat(record.sent_at.replace("Z", "+00:00"))
                record.days_since_sent = (now - sent_dt).days
            except Exception:
                record.days_since_sent = 0
            
            # Check current status (with rate limiting)
            status, response_type = self.check_discussion_status(
                record.repo_id, 
                record.discussion_num
            )
            checked += 1
            if checked < total_to_check:
                time.sleep(delay)
            
            # If no response after 14 days, mark as no_response
            if status == "pending" and record.days_since_sent > 14 and response_type == "none":
                status = "no_response"
            
            record.status = status
            record.response_type = response_type
            record.checked_at = now.isoformat().replace("+00:00", "Z")
            
            stats[status] += 1
            if checked % 10 == 0 or checked == total_to_check:
                print(f"  Checked {checked}/{total_to_check}...", flush=True)
        
        return stats
    
    def get_acceptance_rate(self) -> Dict[str, Any]:
        """Calculate acceptance statistics."""
        total = len(self.records)
        if total == 0:
            return {"total": 0, "acceptance_rate": 0}
        
        accepted = sum(1 for r in self.records.values() if r.status == "accepted")
        declined = sum(1 for r in self.records.values() if r.status == "declined")
        pending = sum(1 for r in self.records.values() if r.status == "pending")
        no_response = sum(1 for r in self.records.values() if r.status == "no_response")
        
        responded = accepted + declined
        acceptance_rate = (accepted / responded * 100) if responded > 0 else 0
        response_rate = (responded / total * 100) if total > 0 else 0
        
        return {
            "total_sent": total,
            "accepted": accepted,
            "declined": declined,
            "pending": pending,
            "no_response": no_response,
            "acceptance_rate_pct": round(acceptance_rate, 1),
            "response_rate_pct": round(response_rate, 1),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a full tracking report."""
        stats = self.get_acceptance_rate()
        
        # Group by organization
        by_org = defaultdict(lambda: {"sent": 0, "accepted": 0, "declined": 0})
        for record in self.records.values():
            org = record.repo_id.split("/")[0] if "/" in record.repo_id else "unknown"
            by_org[org]["sent"] += 1
            if record.status == "accepted":
                by_org[org]["accepted"] += 1
            elif record.status == "declined":
                by_org[org]["declined"] += 1
        
        # Top acceptors
        top_acceptors = sorted(
            [(org, data["accepted"]) for org, data in by_org.items() if data["accepted"] > 0],
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return {
            "summary": stats,
            "by_organization": dict(by_org),
            "top_acceptors": top_acceptors,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    
    def save_records(self, path: str):
        """Save all records to JSON."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "records": {k: v.to_dict() for k, v in self.records.items()},
                "report": self.generate_report(),
            }, f, indent=2, ensure_ascii=False)
    
    def load_records(self, path: str):
        """Load records from JSON."""
        if not os.path.exists(path):
            return
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for key, rec_data in data.get("records", {}).items():
                self.records[key] = EnhancementRecord(**rec_data)

    def sync_back_to_jsonl(self, jsonl_path: str):
        """
        Write updated statuses back to sent_discussions.jsonl.
        
        This ensures the outreach_data_bridge reads the correct statuses
        (acknowledged, closed, etc.) instead of stale 'sent' values.
        """
        if not os.path.exists(jsonl_path):
            return 0

        # Read current JSONL
        lines = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(json.loads(line))

        # Map tracker statuses to JSONL statuses
        STATUS_MAP = {
            ("accepted", "merged"): "acknowledged",
            ("accepted", "acknowledged"): "acknowledged",
            ("pending", "acknowledged"): "acknowledged",
            ("declined", "closed"): "closed",
        }

        # Build lookup by repo_id#discussion_num (exact match per discussion)
        by_key = {}
        for rec in self.records.values():
            key = f"{rec.repo_id}#{rec.discussion_num}"
            by_key[key] = rec

        updated = 0
        for entry in lines:
            repo_id = entry.get("repo_id", entry.get("target_id", ""))
            disc_num = entry.get("discussion_num")
            if not disc_num:
                continue
            key = f"{repo_id}#{disc_num}"
            rec = by_key.get(key)
            if not rec:
                continue

            new_status = STATUS_MAP.get(
                (rec.status, rec.response_type or "none"),
                entry.get("status", "sent"),  # keep current if no mapping
            )

            if new_status != entry.get("status"):
                entry["status"] = new_status
                updated += 1

        # Write back
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for entry in lines:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return updated


# ========== CLI ==========

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CROVIA Enhancement Tracker")
    parser.add_argument("--log", type=str, default="sent_discussions.jsonl", help="Sent log file")
    parser.add_argument("--state", type=str, default="tracker_state.json", help="Tracker state file")
    parser.add_argument("--update", action="store_true", help="Update statuses from HuggingFace")
    parser.add_argument("--report", action="store_true", help="Generate report")
    parser.add_argument("--public-json", type=str, default=None, help="Save public report JSON")
    args = parser.parse_args()
    
    print("=" * 60)
    print("CROVIA Enhancement Tracker")
    print("=" * 60)
    
    tracker = EnhancementTracker()
    
    # Load existing state
    tracker.load_records(args.state)
    print(f"\nLoaded {len(tracker.records)} existing records")
    
    # Load new entries from log
    tracker.load_sent_log(args.log)
    print(f"Total records: {len(tracker.records)}")
    
    if args.update:
        print("\nUpdating statuses from HuggingFace...")
        stats = tracker.update_all_statuses()
        print(f"  Pending: {stats['pending']}")
        print(f"  Accepted: {stats['accepted']}")
        print(f"  Declined: {stats['declined']}")
        print(f"  No response: {stats['no_response']}")
        
        tracker.save_records(args.state)
        print(f"\nSaved to {args.state}")

        # Sync statuses back to JSONL so bridge reads correct data
        synced = tracker.sync_back_to_jsonl(args.log)
        if synced:
            print(f"  Synced {synced} status updates back to {args.log}")
    
    if args.report:
        report = tracker.generate_report()
        print("\n📊 ENHANCEMENT REPORT")
        print("-" * 40)
        print(f"Total sent: {report['summary']['total_sent']}")
        print(f"Accepted: {report['summary']['accepted']}")
        print(f"Declined: {report['summary']['declined']}")
        print(f"Acceptance rate: {report['summary']['acceptance_rate_pct']}%")
        print(f"Response rate: {report['summary']['response_rate_pct']}%")
        
        if report['top_acceptors']:
            print("\nTop Acceptors:")
            for org, count in report['top_acceptors'][:5]:
                print(f"  {org}: {count}")
    
    if args.public_json:
        report = tracker.generate_report()
        with open(args.public_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nPublic report saved to {args.public_json}")
    
    print("=" * 60)
