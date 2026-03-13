#!/usr/bin/env python3
"""
CROVIA Disclosure Transparency Index Generator
===============================================

Generates weekly aggregated statistics from DDF snapshots, drift events,
and statement timeline data. Output is purely observational - no judgments,
no accusations, no causal deductions.

All percentages and counts are factual observations only.

Author: Crovia Engineering
License: Open
"""

import json
import os
import sys
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _week_id(dt: datetime) -> str:
    """Return ISO week identifier YYYY-WNN"""
    return f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def generate_disclosure_index(dataset_root: str) -> Dict[str, Any]:
    """
    Generate the Disclosure Transparency Index from existing artifacts.
    
    This is purely observational data aggregation. No inference, no judgment.
    """
    
    now = datetime.now(timezone.utc)
    week_id = _week_id(now)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)
    
    # Load artifacts
    snapshots_path = os.path.join(dataset_root, "open", "drift", "ddf_snapshots_latest.jsonl")
    events_path = os.path.join(dataset_root, "open", "drift", "ddf_drift_events_30d.jsonl")
    timeline_path = os.path.join(dataset_root, "open", "temporal", "statement_timeline_30d.jsonl")
    timeline_index_path = os.path.join(dataset_root, "open", "temporal", "statement_timeline_index.json")
    
    snapshots = _load_jsonl(snapshots_path)
    drift_events = _load_jsonl(events_path)
    timeline_events = _load_jsonl(timeline_path)
    timeline_index = _load_json(timeline_index_path) or {}
    
    # Basic counts
    total_targets = len(snapshots)
    models = [s for s in snapshots if s.get("tipo_target") == "model"]
    datasets = [s for s in snapshots if s.get("tipo_target") == "dataset"]
    
    # Disclosure completeness metrics (observational only)
    def extract_field(snap: Dict, field: str) -> Any:
        extracted = snap.get("extracted") if isinstance(snap.get("extracted"), dict) else {}
        return extracted.get(field)
    
    # Training section presence
    training_present = sum(1 for s in snapshots if extract_field(s, "has_training_section") is True)
    training_absent = sum(1 for s in snapshots if extract_field(s, "has_training_section") is False)
    
    # Declared datasets
    with_declared = sum(1 for s in snapshots if extract_field(s, "declared_datasets") and len(extract_field(s, "declared_datasets") or []) > 0)
    
    # License declared
    with_license = sum(1 for s in snapshots if extract_field(s, "license"))
    
    # README accessibility
    readme_ok = sum(1 for s in snapshots if str(extract_field(s, "readme_access") or "").lower() == "ok")
    readme_not_found = sum(1 for s in snapshots if str(extract_field(s, "readme_access") or "").lower() == "not_found")
    readme_forbidden = sum(1 for s in snapshots if str(extract_field(s, "readme_access") or "").lower() == "forbidden")
    
    # Drift metrics (30d window)
    drift_30d = len(drift_events)
    targets_with_drift = len(set(e.get("target_id") for e in drift_events if e.get("target_id")))
    
    # Weekly drift (last 7 days)
    drift_7d = [e for e in drift_events if _parse_iso(str(e.get("observed_at") or "")) and _parse_iso(str(e.get("observed_at") or "")) >= cutoff_7d]
    drift_7d_count = len(drift_7d)
    
    # Top movers (targets with most drift events in 30d)
    drift_by_target: Dict[str, List[Dict]] = defaultdict(list)
    for e in drift_events:
        tid = e.get("target_id")
        if tid:
            drift_by_target[tid].append(e)
    
    top_movers = sorted(
        [(tid, len(events)) for tid, events in drift_by_target.items()],
        key=lambda x: -x[1]
    )[:10]
    
    # Recent changes (last 7 days) with direction
    recent_changes: List[Dict[str, Any]] = []
    for e in sorted(drift_7d, key=lambda x: str(x.get("observed_at") or ""), reverse=True)[:20]:
        recent_changes.append({
            "target_id": e.get("target_id"),
            "tipo_target": e.get("tipo_target"),
            "observed_at": e.get("observed_at"),
            "prev_ddf_hash": e.get("prev_ddf_hash"),
            "new_ddf_hash": e.get("new_ddf_hash"),
        })
    
    # Popularity metrics (observational only - no ranking/judgment)
    def get_popularity(snap: Dict) -> Dict[str, Any]:
        pop = snap.get("popularity") if isinstance(snap.get("popularity"), dict) else {}
        return pop
    
    # Top by downloads (factual observation)
    with_downloads = [(s, get_popularity(s).get("downloads") or 0) for s in snapshots if get_popularity(s).get("downloads")]
    top_by_downloads = sorted(with_downloads, key=lambda x: -x[1])[:15]
    
    # Gated targets (factual observation)
    def get_access(snap: Dict) -> Dict[str, Any]:
        acc = snap.get("access") if isinstance(snap.get("access"), dict) else {}
        return acc
    
    gated_targets = [s for s in snapshots if get_access(s).get("gated")]
    gated_count = len(gated_targets)
    
    # High-download targets without training section (factual intersection, no judgment)
    high_download_no_training = [
        (s, get_popularity(s).get("downloads") or 0)
        for s in snapshots
        if (get_popularity(s).get("downloads") or 0) > 10000
        and extract_field(s, "has_training_section") is False
    ]
    high_download_no_training_sorted = sorted(high_download_no_training, key=lambda x: -x[1])[:15]
    
    # Organization aggregation (extract org from target_id)
    def get_org(target_id: str) -> str:
        if "/" in target_id:
            return target_id.split("/")[0]
        return "unknown"
    
    targets_by_org: Dict[str, List[Dict]] = defaultdict(list)
    for s in snapshots:
        org = get_org(s.get("target_id") or "")
        targets_by_org[org].append(s)
    
    # Per-org disclosure stats
    org_stats: List[Dict[str, Any]] = []
    for org, org_snaps in sorted(targets_by_org.items(), key=lambda x: -len(x[1]))[:25]:
        org_total = len(org_snaps)
        org_training = sum(1 for s in org_snaps if extract_field(s, "has_training_section") is True)
        org_declared = sum(1 for s in org_snaps if extract_field(s, "declared_datasets") and len(extract_field(s, "declared_datasets") or []) > 0)
        org_license = sum(1 for s in org_snaps if extract_field(s, "license"))
        
        org_stats.append({
            "organization": org,
            "targets_monitored": org_total,
            "training_section_present": org_training,
            "declared_datasets_present": org_declared,
            "license_present": org_license,
        })
    
    # Calculate percentages safely
    def pct(num: int, denom: int) -> Optional[float]:
        if denom == 0:
            return None
        return round(100.0 * num / denom, 1)
    
    # Build the index document
    index: Dict[str, Any] = {
        "schema": "crovia.open.disclosure_index.v1",
        "generated_at": _now_iso(),
        "week_id": week_id,
        "note": "This is observational data only. No inference, judgment, or accusation.",
        
        "coverage": {
            "targets_monitored": total_targets,
            "models": len(models),
            "datasets": len(datasets),
            "period_days": 30,
        },
        
        "disclosure_observations": {
            "training_section": {
                "present": training_present,
                "absent": training_absent,
                "present_pct": pct(training_present, total_targets),
            },
            "declared_datasets": {
                "with_declaration": with_declared,
                "without_declaration": total_targets - with_declared,
                "with_declaration_pct": pct(with_declared, total_targets),
            },
            "license": {
                "declared": with_license,
                "not_declared": total_targets - with_license,
                "declared_pct": pct(with_license, total_targets),
            },
            "readme_access": {
                "ok": readme_ok,
                "not_found": readme_not_found,
                "forbidden": readme_forbidden,
                "ok_pct": pct(readme_ok, total_targets),
            },
        },
        
        "drift_observations": {
            "events_30d": drift_30d,
            "events_7d": drift_7d_count,
            "targets_with_change_30d": targets_with_drift,
            "avg_changes_per_changed_target": round(drift_30d / max(targets_with_drift, 1), 2),
        },
        
        "top_movers_30d": [
            {"target_id": tid, "change_count": cnt}
            for tid, cnt in top_movers
        ],
        
        "recent_changes_7d": recent_changes,
        
        "popularity_observations": {
            "targets_with_download_data": len(with_downloads),
            "gated_targets": gated_count,
            "gated_pct": pct(gated_count, total_targets),
            "top_by_downloads": [
                {
                    "target_id": s.get("target_id"),
                    "tipo_target": s.get("tipo_target"),
                    "downloads": dl,
                    "training_section_presence": "PRESENT" if extract_field(s, "has_training_section") else "ABSENT",
                    "declared_datasets_count": len(extract_field(s, "declared_datasets") or []) if extract_field(s, "declared_datasets") else 0,
                }
                for s, dl in top_by_downloads
            ],
            "high_download_training_absent": [
                {
                    "target_id": s.get("target_id"),
                    "tipo_target": s.get("tipo_target"),
                    "downloads": dl,
                    "readme_access": str(extract_field(s, "readme_access") or "").upper(),
                }
                for s, dl in high_download_no_training_sorted
            ],
            "note": "Factual observation: intersection of download count and training section status. No inference about compliance or quality.",
        },
        
        "by_organization": org_stats,
    }
    
    # Compute fingerprint of this index (for verification)
    canonical = json.dumps(index, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    index["index_fingerprint"] = _sha256_hex(canonical)
    
    return index


def main() -> int:
    if sys.version_info < (3, 6):
        raise SystemExit("generate_disclosure_index.py requires Python 3.6+")
    
    dataset_root = os.getenv("CROVIA_OPEN_DATASET_DIR") or os.getenv("CROVIA_DATASET_DIR") or os.getcwd()
    
    reports_dir = os.path.join(dataset_root, "open", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    index = generate_disclosure_index(dataset_root)
    
    # Write weekly snapshot
    week_id = index.get("week_id", "unknown")
    weekly_path = os.path.join(reports_dir, f"disclosure_index_{week_id}.json")
    with open(weekly_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(index, ensure_ascii=False, indent=2))
    
    # Write latest (always overwritten)
    latest_path = os.path.join(reports_dir, "disclosure_index_latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(index, ensure_ascii=False, indent=2))
    
    # Print summary
    obs = index.get("disclosure_observations", {})
    drift = index.get("drift_observations", {})
    
    print(f"[CROVIA] Disclosure Index generated: {week_id}")
    print(f"[CROVIA] Targets monitored: {index.get('coverage', {}).get('targets_monitored', 0)}")
    print(f"[CROVIA] Training section present: {obs.get('training_section', {}).get('present_pct')}%")
    print(f"[CROVIA] Declared datasets present: {obs.get('declared_datasets', {}).get('with_declaration_pct')}%")
    print(f"[CROVIA] README accessible: {obs.get('readme_access', {}).get('ok_pct')}%")
    print(f"[CROVIA] Drift events (7d): {drift.get('events_7d', 0)}")
    print(f"[CROVIA] Drift events (30d): {drift.get('events_30d', 0)}")
    print(f"[CROVIA] Output: {weekly_path}")
    print(f"[CROVIA] Output: {latest_path}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
