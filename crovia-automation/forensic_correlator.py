#!/usr/bin/env python3
"""
CROVIA Forensic Correlator
============================

Cross-references outreach timestamps with DDF drift events to detect
post-outreach documentation changes. Generates forensic_report.json
for the public registry/forensics page.

Temporal causality chain:
  T0: TPA proves NEC# absence (cryptographic)
  T1: Outreach discussion sent (timestamped)
  T2: Model card change detected (drift event with hash)
  T3: Correlation → evidence of impact

Author: Crovia Engineering
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pathlib import Path
from collections import defaultdict

# Paths (overridable via env)
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent

DRIFT_FILE = Path(os.environ.get(
    "FORENSIC_DRIFT_FILE",
    str(REPO_ROOT / "open" / "drift" / "ddf_drift_events_30d.jsonl"),
))
OUTREACH_FILE = Path(os.environ.get(
    "FORENSIC_OUTREACH_FILE",
    str(SCRIPT_DIR / "sent_discussions.jsonl"),
))
TPA_FILE = Path(os.environ.get(
    "TPA_DATA_FILE",
    str(REPO_ROOT / "webroot" / "registry" / "data" / "tpa_latest.json"),
))
OUTPUT_DIR = Path(os.environ.get(
    "FORENSIC_OUTPUT_DIR",
    str(REPO_ROOT / "webroot" / "registry" / "data"),
))
OUTPUT_FILE = OUTPUT_DIR / "forensic_report.json"


def load_jsonl(path: Path) -> List[Dict]:
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


def parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def load_tpa_index() -> Dict[str, Dict]:
    tpa_index = {}
    if not TPA_FILE.exists():
        return tpa_index
    try:
        with open(TPA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for t in data.get("tpas", []):
            mid = t.get("model_id", "")
            tpa_index[mid] = {
                "absent_count": t.get("absent_count", 0),
                "present_count": t.get("present_count", 0),
                "highest_severity": t.get("highest_severity", ""),
                "total_jurisdictions_exposed": t.get("total_jurisdictions_exposed", 0),
            }
    except Exception:
        pass
    return tpa_index


def format_changes(changes: Optional[Dict]) -> List[Dict[str, Any]]:
    """Convert raw drift changes to human-readable format."""
    if not changes:
        return [{"field": "fingerprint", "description": "Disclosure fingerprint changed"}]
    formatted = []
    for field, detail in changes.items():
        if isinstance(detail, dict):
            before = detail.get("before")
            after = detail.get("after")
            added = detail.get("added")
            delta = detail.get("delta")
            desc = f"{field}"
            if before is not None and after is not None:
                desc = f"{field}: {before} → {after}"
            elif added:
                desc = f"{field}: +{len(added)} items added"
            elif delta is not None:
                desc = f"{field}: delta {delta:+d}"
            formatted.append({
                "field": field,
                "description": desc,
                "before": before,
                "after": after,
            })
        else:
            formatted.append({"field": field, "description": str(detail)})
    return formatted


def generate_forensic_report() -> Dict[str, Any]:
    """Generate the forensic correlation report."""
    now = datetime.now(timezone.utc)

    # Load data
    tpa_index = load_tpa_index()
    print(f"  TPA index: {len(tpa_index)} models")

    # Load outreach
    outreach_raw = load_jsonl(OUTREACH_FILE)
    outreach = {}
    VALID_STATUSES = {"sent", "acknowledged", "merged", "accepted"}
    for r in outreach_raw:
        if r.get("status") not in VALID_STATUSES:
            continue
        tid = r.get("repo_id", r.get("target_id", ""))
        sent = r.get("sent_at", "")
        if tid and sent:
            outreach[tid] = {
                "sent_at": sent,
                "discussion_url": r.get("discussion_url", ""),
                "response_type": r.get("response_type"),
            }
    print(f"  Outreach: {len(outreach)} unique targets")

    # Load drift events
    drift_raw = load_jsonl(DRIFT_FILE)
    drift_by_target = defaultdict(list)
    for ev in drift_raw:
        tid = ev.get("target_id", "")
        drift_by_target[tid].append(ev)
    print(f"  Drift events: {len(drift_raw)} total, {len(drift_by_target)} unique targets")

    # Cross-reference: post-outreach drift
    # STRICT FILTERING to avoid false/misleading correlations:
    # 1. Only declared_datasets and training_section changes count (license alone is often auto-detected)
    # 2. Minimum 24h gap — same-cron-run artifacts show as ~0.5h and are NOT caused by outreach
    # 3. The DDF scanner and outreach ran in the same cron, so any drift detected in that
    #    run will appear as "+0.5h" but those changes accumulated over the previous week.
    MEANINGFUL_FIELDS = {"declared_datasets", "training_section"}
    MIN_HOURS_GAP = 24.0

    correlations = []
    for tid, out in outreach.items():
        sent_dt = parse_dt(out["sent_at"])
        if not sent_dt:
            continue
        events = drift_by_target.get(tid, [])
        for ev in events:
            ev_dt = parse_dt(ev.get("observed_at", ""))
            if not ev_dt or ev_dt <= sent_dt:
                continue

            delta_hours = round((ev_dt - sent_dt).total_seconds() / 3600, 1)

            # Skip same-cron-run artifacts (outreach + DDF ran together)
            if delta_hours < MIN_HOURS_GAP:
                continue

            # Filter: only include if declared_datasets or training_section changed
            raw_changes = ev.get("changes") or {}
            meaningful_changes = {k: v for k, v in raw_changes.items() if k in MEANINGFUL_FIELDS}
            if not meaningful_changes:
                continue
            tpa = tpa_index.get(tid, {})
            correlations.append({
                "target_id": tid,
                "outreach_sent": out["sent_at"],
                "drift_observed": ev["observed_at"],
                "hours_after_outreach": delta_hours,
                "changes": format_changes(meaningful_changes),
                "discussion_url": out.get("discussion_url", ""),
                "response_type": out.get("response_type"),
                "has_tpa": tid in tpa_index,
                "tpa_severity": tpa.get("highest_severity", ""),
                "tpa_absent": tpa.get("absent_count", 0),
                "tpa_jurisdictions": tpa.get("total_jurisdictions_exposed", 0),
                "drift_hashes": {
                    "prev": ev.get("prev_ddf_hash", "")[:16],
                    "new": ev.get("new_ddf_hash", "")[:16],
                },
            })

    correlations.sort(key=lambda x: x["hours_after_outreach"])

    # Stats
    outreach_with_drift = sum(1 for tid in outreach if tid in drift_by_target)
    acknowledged = sum(1 for o in outreach.values() if o.get("response_type") == "acknowledged")

    # Timeline: all outreach events for visualization
    timeline = []
    for tid, out in sorted(outreach.items(), key=lambda x: x[1]["sent_at"]):
        sent_dt = parse_dt(out["sent_at"])
        if not sent_dt:
            continue
        events = drift_by_target.get(tid, [])
        post_drift = [
            ev for ev in events
            if parse_dt(ev.get("observed_at", "")) and parse_dt(ev["observed_at"]) > sent_dt
        ]
        tpa = tpa_index.get(tid, {})
        timeline.append({
            "target_id": tid,
            "outreach_date": out["sent_at"][:10],
            "has_post_drift": len(post_drift) > 0,
            "drift_count": len(post_drift),
            "has_tpa": tid in tpa_index,
            "severity": tpa.get("highest_severity", ""),
            "responded": out.get("response_type") == "acknowledged",
        })

    return {
        "schema": "crovia.forensic_report.v1",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "stats": {
            "total_outreach": len(outreach),
            "total_drift_events": len(drift_raw),
            "outreach_with_drift": outreach_with_drift,
            "post_outreach_correlations": len(correlations),
            "acknowledged_responses": acknowledged,
            "models_with_tpa": sum(1 for tid in outreach if tid in tpa_index),
            "correlation_rate": round(outreach_with_drift / max(len(outreach), 1) * 100, 1),
        },
        "correlations": correlations,
        "timeline": timeline[:100],
    }


def build_verified_findings(report: Dict[str, Any]) -> Dict[str, Any]:
    """Convert forensic correlations into verified_findings.json for the HF Space alert."""
    now = datetime.now(timezone.utc)
    correlations = report.get("correlations", [])

    if not correlations:
        return {
            "schema": "crovia.pro.verified_findings.v1",
            "generated_at": now.isoformat().replace("+00:00", "Z"),
            "engine_version": "v3_observatory",
            "total_events_analyzed": report.get("stats", {}).get("total_drift_events", 0),
            "clean_events": 0,
            "verified_findings_count": 0,
            "verified_findings": [],
        }

    # Group correlations by date
    by_date = defaultdict(list)
    for c in correlations:
        date_str = c.get("drift_observed", "")[:10]
        if date_str:
            by_date[date_str].append(c)

    findings = []
    for date_str, events in sorted(by_date.items(), reverse=True):
        orgs = set()
        license_changes = 0
        dataset_changes = 0
        for ev in events:
            org = ev["target_id"].split("/")[0] if "/" in ev["target_id"] else ""
            if org:
                orgs.add(org)
            for ch in ev.get("changes", []):
                field = ch.get("field", "")
                if "license" in field.lower():
                    license_changes += 1
                if "dataset" in field.lower():
                    dataset_changes += 1

        # Confidence based on temporal proximity
        min_hours = min(ev["hours_after_outreach"] for ev in events)
        if min_hours < 24:
            confidence = "VERIFIED"
            score = 95
        elif min_hours < 72:
            confidence = "HIGH"
            score = 80
        else:
            confidence = "MODERATE"
            score = 60

        findings.append({
            "date": date_str,
            "confidence": confidence,
            "confidence_score": score,
            "orgs_count": len(orgs),
            "event_count": len(events),
            "details": {
                "license_removals": license_changes,
                "dataset_removals": dataset_changes,
            },
        })

    return {
        "schema": "crovia.pro.verified_findings.v1",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "engine_version": "v3_observatory",
        "total_events_analyzed": report.get("stats", {}).get("total_drift_events", 0),
        "clean_events": len(correlations),
        "verified_findings_count": len(findings),
        "verified_findings": findings[:10],
    }


def sync_findings_to_hf(findings: Dict[str, Any]) -> None:
    """Write verified_findings.json to HF dataset repo and push."""
    hf_repo = Path(os.environ.get(
        "HF_REPO_DIR",
        str(REPO_ROOT),
    ))
    findings_path = hf_repo / "open" / "forensic" / "verified_findings.json"
    findings_path.parent.mkdir(parents=True, exist_ok=True)

    with open(findings_path, "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=2, ensure_ascii=False)

    print(f"  Written: {findings_path}")

    # Git commit and push if in a git repo
    import subprocess
    try:
        subprocess.run(
            ["git", "add", str(findings_path)],
            cwd=str(hf_repo), capture_output=True, timeout=10,
        )
        result = subprocess.run(
            ["git", "commit", "-m", f"auto: observatory findings {findings['generated_at'][:10]}"],
            cwd=str(hf_repo), capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            push = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=str(hf_repo), capture_output=True, text=True, timeout=30,
            )
            if push.returncode == 0:
                print("  Pushed to HuggingFace dataset repo")
            else:
                print(f"  Push failed: {push.stderr[:200]}")
        else:
            print(f"  No changes to commit (findings unchanged)")
    except Exception as e:
        print(f"  Git sync skipped: {e}")


def main():
    print("=" * 60)
    print("CROVIA Forensic Correlator")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\nLoading data...")
    print(f"  Drift: {DRIFT_FILE} ({DRIFT_FILE.exists()})")
    print(f"  Outreach: {OUTREACH_FILE} ({OUTREACH_FILE.exists()})")
    print(f"  TPA: {TPA_FILE} ({TPA_FILE.exists()})")

    report = generate_forensic_report()

    print(f"\n📊 Forensic Stats:")
    for k, v in report["stats"].items():
        print(f"   {k}: {v}")

    if report["correlations"]:
        print(f"\n🔍 Post-outreach correlations:")
        for c in report["correlations"][:5]:
            print(f"   {c['target_id']} (+{c['hours_after_outreach']}h)")
            for ch in c["changes"]:
                print(f"     → {ch['description']}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Report: {OUTPUT_FILE}")

    # Generate and sync verified_findings.json to HF
    print("\n📋 Generating findings for HF Space alert...")
    findings = build_verified_findings(report)
    print(f"  Findings: {findings['verified_findings_count']} observation(s)")
    sync_findings_to_hf(findings)

    print("=" * 60)


if __name__ == "__main__":
    main()
