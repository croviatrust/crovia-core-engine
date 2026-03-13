#!/usr/bin/env python3
"""
CROVIA Outreach Data Bridge
============================

Generates outreach_status.json for the public registry/outreach.html page.
Aggregates data from:
- sent_discussions.jsonl (HF discussions sent)
- github_issues_sent.jsonl (GitHub issues sent)
- model_card_analyzer cache (completeness scores)

Output: webroot/registry/data/outreach_status.json

Author: Crovia Engineering
"""

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# Paths (relative to script location, overridable via env)
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent

# Input files
HF_SENT_LOG = Path(os.environ.get("OUTREACH_HF_LOG", str(SCRIPT_DIR / "sent_discussions.jsonl")))
LEGACY_HF_SENT_LOG = Path(os.environ.get("OUTREACH_HF_LEGACY_LOG", str(REPO_ROOT / "sent_discussions.jsonl")))
_hf_logs_env = os.environ.get("OUTREACH_HF_LOGS", "")
if _hf_logs_env:
    HF_SENT_LOGS = [Path(p.strip()) for p in _hf_logs_env.split(",") if p.strip()]
else:
    HF_SENT_LOGS = [HF_SENT_LOG, LEGACY_HF_SENT_LOG]
GITHUB_SENT_LOG = Path(os.environ.get("OUTREACH_GH_LOG", str(SCRIPT_DIR / "github_issues_sent.jsonl")))
LEGACY_GITHUB_SENT_LOG = Path(os.environ.get("OUTREACH_GH_LEGACY_LOG", str(REPO_ROOT / "github_issues_sent.jsonl")))
_gh_logs_env = os.environ.get("OUTREACH_GH_LOGS", "")
if _gh_logs_env:
    GITHUB_SENT_LOGS = [Path(p.strip()) for p in _gh_logs_env.split(",") if p.strip()]
else:
    GITHUB_SENT_LOGS = [GITHUB_SENT_LOG, LEGACY_GITHUB_SENT_LOG]
GITHUB_TARGETS_FILE = Path(os.environ.get("OUTREACH_GH_TARGETS", str(SCRIPT_DIR / "targets_github.json")))
GITHUB_LINK_OVERRIDES_FILE = Path(os.environ.get("OUTREACH_GH_LINK_OVERRIDES", str(SCRIPT_DIR / "github_target_links_overrides.json")))
OVERRIDE_LOG = Path(os.environ.get("OUTREACH_OVERRIDE_LOG", str(SCRIPT_DIR / "outreach_status_overrides.jsonl")))
# TPA data — try multiple paths (server vs local)
_TPA_CANDIDATES = [
    Path("/var/www/registry/data/tpa_latest.json"),
    REPO_ROOT / "webroot" / "registry" / "data" / "tpa_latest.json",
]
_tpa_env = os.environ.get("TPA_DATA_FILE", "")
if _tpa_env:
    _TPA_CANDIDATES.insert(0, Path(_tpa_env))
TPA_DATA_FILE = next((p for p in _TPA_CANDIDATES if p.exists()), _TPA_CANDIDATES[-1])

# Compliance data directory
COMPLIANCE_DIR = Path(os.environ.get("COMPLIANCE_DIR", "/var/www/registry/data/compliance"))

# Output — try server path first, then local
_OUT_CANDIDATES = [
    Path("/var/www/registry/data"),
    REPO_ROOT / "webroot" / "registry" / "data",
]
_out_env = os.environ.get("OUTREACH_OUTPUT_DIR", "")
if _out_env:
    _OUT_CANDIDATES.insert(0, Path(_out_env))
OUTPUT_DIR = next((p for p in _OUT_CANDIDATES if p.exists()), _OUT_CANDIDATES[-1])
OUTPUT_FILE = OUTPUT_DIR / "outreach_status.json"


def load_jsonl(path: Path) -> List[Dict]:
    """Load records from JSONL file."""
    records = []
    if not path.exists():
        return records

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def load_github_target_map(path: Path) -> Dict[str, str]:
    """Map GitHub repo_full_name -> linked HF model_id (from targets_github.json)."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(data, dict) and "targets" in data:
        targets = data.get("targets", [])
    elif isinstance(data, list):
        targets = data
    else:
        return {}
    mapping: Dict[str, str] = {}
    for t in targets:
        name = t.get("name") or t.get("target_id", "")
        if name.startswith("gh:"):
            name = name[3:]
        linked = (t.get("metadata", {}) or {}).get("linked_model_id")
        if name and linked:
            mapping[name] = linked
    return mapping


def load_github_link_overrides(path: Path) -> Dict[str, str]:
    """Load GitHub-to-HF linked model overrides."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def load_overrides(path: Path) -> Dict[str, Dict[str, Any]]:
    """Load manual overrides keyed by target_id/repo_id/repo_full_name."""
    overrides: Dict[str, Dict[str, Any]] = {}
    for rec in load_jsonl(path):
        key = rec.get("target_id") or rec.get("repo_id") or rec.get("repo_full_name")
        if not key:
            continue
        overrides[key] = rec
    return overrides


def calculate_days_pending(sent_at: str) -> int:
    """Calculate days since sent."""
    if not sent_at:
        return 0
    
    try:
        sent_date = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - sent_date
        return max(0, delta.days)
    except:
        return 0


def parse_sent_at(sent_at: str) -> float:
    """Parse sent_at into a unix timestamp for ordering."""
    if not sent_at:
        return 0
    try:
        return datetime.fromisoformat(sent_at.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0


def status_rank(status: str) -> int:
    """Rank outreach status for dedupe preference."""
    return {"access_restricted": 4, "blocked": 4, "acknowledged": 3, "closed": 2, "pending": 1}.get(status, 0)


def determine_status(record: Dict) -> str:
    """Determine status based on record data."""
    # Check BOTH the 'status' field (from sent_discussions.jsonl)
    # AND 'response_type' (from tracker)
    raw = record.get("status", "")
    if raw in ("access_restricted", "blocked", "restricted"):
        return "access_restricted"
    if raw in ("acknowledged", "merged", "accepted", "replied"):
        return "acknowledged"
    if raw in ("closed", "not_planned"):
        return "closed"
    if record.get("response_type") in ("access_restricted", "blocked", "restricted"):
        return "access_restricted"
    if record.get("response_type") in ("merged", "acknowledged", "accepted"):
        return "acknowledged"
    if record.get("response_type") in ("closed", "not_planned"):
        return "closed"
    return "pending"


def build_discussion_url(record: Dict) -> Optional[str]:
    """Build discussion URL from record."""
    explicit_url = record.get("discussion_url") or record.get("issue_url")
    if explicit_url:
        return explicit_url
    
    repo_id = record.get("repo_id", "")
    discussion_num = record.get("discussion_num")
    
    if repo_id and discussion_num:
        return f"https://huggingface.co/{repo_id}/discussions/{discussion_num}"
    
    # For GitHub
    repo_full = record.get("repo_full_name", "")
    issue_num = record.get("issue_number")
    
    if repo_full and issue_num:
        return f"https://github.com/{repo_full}/issues/{issue_num}"
    
    return explicit_url


def load_tpa_index() -> Dict[str, Dict]:
    """Load TPA data and build index by model_id for completeness lookup."""
    tpa_index = {}
    if not TPA_DATA_FILE.exists():
        return tpa_index
    try:
        with open(TPA_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for tpa in data.get("tpas", []):
            mid = tpa.get("model_id", "")
            absent = tpa.get("absent_count", 0)
            present = tpa.get("present_count", 0)
            total = absent + present
            score = int((present / total) * 100) if total > 0 else 0
            observations = tpa.get("observations") or []
            nec1_present = None
            for obs in observations:
                if obs.get("necessity_id") == "NEC#1":
                    nec1_present = obs.get("is_present")
                    break
            top_missing_nec = [
                (o.get("necessity_name") or o.get("necessity_id"))
                for o in observations
                if o.get("is_present") is False
            ][:3]
            if nec1_present is True:
                provenance_status = "present"
            elif nec1_present is False:
                provenance_status = "missing"
            else:
                provenance_status = "unknown"
            if total > 0 and absent == 0:
                documentation_status = "complete"
            elif total > 0:
                documentation_status = "partial"
            else:
                documentation_status = "unknown"
            tpa_index[mid] = {
                "completeness_score": score,
                "absent_count": absent,
                "present_count": present,
                "highest_severity": tpa.get("highest_severity", ""),
                "total_jurisdictions_exposed": tpa.get("total_jurisdictions_exposed", 0),
                "provenance_status": provenance_status,
                "documentation_status": documentation_status,
                "top_missing_nec": top_missing_nec,
                "observed_at": tpa.get("observation_timestamp") or tpa.get("observed_at"),
                "has_tpa": True,
            }
    except Exception as e:
        print(f"  Warning: could not load TPA data: {e}")
    return tpa_index


def load_compliance_index() -> Dict[str, float]:
    """Load compliance report scores for completeness."""
    scores = {}
    index_path = COMPLIANCE_DIR / "index.json"
    if not index_path.exists():
        return scores
    try:
        with open(index_path) as f:
            data = json.load(f)
        for rep in data.get("reports", []):
            mid = rep.get("model_id", "")
            if mid:
                scores[mid] = rep.get("overall_score_pct", 0)
    except Exception as e:
        print(f"  Warning: could not load compliance index: {e}")
    return scores


def generate_outreach_status() -> Dict[str, Any]:
    """Generate the outreach status JSON."""
    now = datetime.now(timezone.utc)
    
    # Load TPA index for completeness cross-reference
    tpa_index = load_tpa_index()
    print(f"  TPA index: {len(tpa_index)} models with TPA data")
    
    # Load compliance scores (more accurate than TPA)
    compliance_scores = load_compliance_index()
    print(f"  Compliance scores: {len(compliance_scores)} models")
    
    # Load sent logs + overrides
    hf_records = []
    for path in HF_SENT_LOGS:
        hf_records.extend(load_jsonl(path))
    github_records = []
    for path in GITHUB_SENT_LOGS:
        github_records.extend(load_jsonl(path))
    overrides = load_overrides(OVERRIDE_LOG)
    github_target_map = load_github_target_map(GITHUB_TARGETS_FILE)
    github_target_map.update(load_github_link_overrides(GITHUB_LINK_OVERRIDES_FILE))
    
    # Deduplicate by target_id (prefer acknowledged/closed, then newest)
    best_by_target: Dict[str, Dict[str, Any]] = {}
    
    # Process records
    def process_record(r, platform, target_key):
        target_id = r.get(target_key, r.get("target_id", "unknown"))
        if target_id in overrides:
            merged = r.copy()
            merged.update(overrides[target_id])
            r = merged

        days = calculate_days_pending(r.get("sent_at", ""))
        status = determine_status(r)
        
        # Get completeness: compliance report > TPA data > record > 0
        tpa_lookup_id = target_id
        if platform == "github":
            tpa_lookup_id = github_target_map.get(target_id, target_id)
        tpa = tpa_index.get(tpa_lookup_id, {})
        linked_model_id = tpa_lookup_id if platform == "github" and tpa_lookup_id != target_id else ""
        compliance_lookup_id = tpa_lookup_id if platform == "github" else target_id
        score = compliance_scores.get(compliance_lookup_id,
                    tpa.get("completeness_score",
                        r.get("completeness_score", 0)))
        if score is None:
            score = 0
        
        rec = {
            "target_id": target_id,
            "platform": platform,
            "completeness_score": score,
            "offer_date": r.get("sent_at", "")[:10] if r.get("sent_at") else "",
            "days_pending": days,
            "status": status,
            "discussion_url": build_discussion_url(r),
            "has_tpa": tpa.get("has_tpa", False),
            "provenance_status": tpa.get("provenance_status", "unknown"),
            "documentation_status": tpa.get("documentation_status", "unknown"),
            "top_missing_nec": tpa.get("top_missing_nec", []),
            "observed_at": tpa.get("observed_at", ""),
            "public_note": r.get("public_note", ""),
            "event_type": r.get("event_type", ""),
        }
        if linked_model_id:
            rec["linked_model_id"] = linked_model_id
        if tpa:
            rec["highest_severity"] = tpa.get("highest_severity", "")
            rec["absent_count"] = tpa.get("absent_count", 0)
            rec["jurisdictions_exposed"] = tpa.get("total_jurisdictions_exposed", 0)
        elif platform == "github":
            if linked_model_id:
                rec["tpa_reason"] = "A linked Hugging Face model exists, but no public TPA snapshot is available yet."
            else:
                rec["tpa_reason"] = "No linked Hugging Face model is mapped for this GitHub repository yet."

        priority = (status_rank(status), parse_sent_at(r.get("sent_at", "")))
        existing = best_by_target.get(target_id)
        if (not existing) or priority > existing["priority"]:
            best_by_target[target_id] = {"priority": priority, "record": rec}
    
    # Process HF records
    VALID_STATUSES = {"sent", "acknowledged", "merged", "accepted", "closed", "replied", "not_planned", "blocked", "access_restricted", "restricted"}
    for r in hf_records:
        if r.get("status") not in VALID_STATUSES:
            continue
        process_record(r, "huggingface", "repo_id")
    
    # Process GitHub records
    for r in github_records:
        if r.get("status") not in VALID_STATUSES:
            continue
        process_record(r, "github", "repo_full_name")
    
    processed = [item["record"] for item in best_by_target.values()]

    # Sort by days pending (oldest first shows who hasn't responded)
    processed.sort(key=lambda x: (-x["days_pending"], -x["completeness_score"]))
    
    # Calculate stats
    total_offered = len(processed)
    total_days = sum(r["days_pending"] for r in processed)
    total_score = sum(r["completeness_score"] for r in processed)
    acknowledged_count = sum(1 for r in processed if r["status"] == "acknowledged")
    closed_count = sum(1 for r in processed if r["status"] == "closed")
    avg_days = round(total_days / total_offered, 1) if total_offered > 0 else 0
    avg_score = round(total_score / total_offered, 1) if total_offered > 0 else 0
    with_tpa = sum(1 for r in processed if r.get("has_tpa"))
    
    return {
        "schema": "crovia.outreach_status.v2",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "stats": {
            "total_offered": total_offered,
            "acknowledged": acknowledged_count,
            "closed": closed_count,
            "avg_days_pending": avg_days,
            "avg_completeness": avg_score,
            "with_tpa": with_tpa,
            "platforms": {
                "huggingface": len([r for r in processed if r["platform"] == "huggingface"]),
                "github": len([r for r in processed if r["platform"] == "github"]),
            }
        },
        "records": processed[:100],  # Limit to 100 most relevant
    }


def main():
    """Main entry point."""
    print("=" * 60)
    print("CROVIA Outreach Data Bridge")
    print("=" * 60)
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate status
    print("\nLoading sent logs...")
    for path in HF_SENT_LOGS:
        print(f"  HF log: {path} ({path.exists()})")
    for path in GITHUB_SENT_LOGS:
        print(f"  GitHub log: {path} ({path.exists()})")
    print(f"  GitHub link overrides: {GITHUB_LINK_OVERRIDES_FILE} ({GITHUB_LINK_OVERRIDES_FILE.exists()})")
    print(f"  Overrides: {OVERRIDE_LOG} ({OVERRIDE_LOG.exists()})")
    print(f"  TPA data: {TPA_DATA_FILE} ({TPA_DATA_FILE.exists()})")
    print(f"  Output: {OUTPUT_FILE}")
    
    status = generate_outreach_status()
    
    print(f"\n📊 Stats:")
    print(f"   Total offered: {status['stats']['total_offered']}")
    print(f"   Acknowledged: {status['stats']['acknowledged']}")
    print(f"   Avg days pending: {status['stats']['avg_days_pending']}")
    print(f"   Avg completeness: {status['stats']['avg_completeness']}%")
    
    # Write output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Output written to: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
