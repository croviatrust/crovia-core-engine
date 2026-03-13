#!/usr/bin/env python3
"""
rebuild_compliance_index.py — Rebuild compliance index.json from existing report files
======================================================================================
Scans /var/www/registry/data/compliance/*.json, extracts summary fields,
and writes a complete index.json for the Compliance Mapping UI.

Safety: read-only on report files, writes only index.json.
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone


def severity_label(score):
    if score >= 80:
        return "EXCELLENT"
    elif score >= 60:
        return "LOW"
    elif score >= 40:
        return "MODERATE"
    elif score >= 20:
        return "HIGH"
    else:
        return "CRITICAL"


def main():
    comp_dir = Path(os.environ.get("COMPLIANCE_DIR", "/var/www/registry/data/compliance"))
    print(f"Scanning compliance reports in: {comp_dir}")

    reports = []
    errors = 0

    for fp in sorted(comp_dir.glob("*.json")):
        if fp.name == "index.json":
            continue
        try:
            with open(fp) as f:
                data = json.load(f)

            model_id = data.get("model_id", "")
            if not model_id:
                stem = fp.stem
                model_id = stem.replace("__", "/", 1) if "__" in stem else stem

            # Extract from summary block (primary) or top-level (fallback)
            summary = data.get("summary", {})
            overall = summary.get("overall_score_pct",
                      data.get("overall_score_pct",
                      data.get("overall_score", 0)))
            if isinstance(overall, dict):
                overall = overall.get("score_pct", 0)

            sev = summary.get("severity_label", "")

            # Count present/absent from summary (fast) or observations (fallback)
            present = summary.get("present", 0)
            absent = summary.get("absent", 0)
            partial_count = summary.get("partial", 0)
            total = summary.get("total_nec_elements", 20)

            if present == 0 and absent == 0:
                observations = data.get("observations", [])
                present = sum(1 for o in observations if o.get("status") == "present")
                absent = sum(1 for o in observations if o.get("status") == "absent")
                partial_count = sum(1 for o in observations if o.get("status") == "partial")
                total = len(observations) if observations else 20

            generated_at = data.get("generated_at", data.get("report_date", ""))

            reports.append({
                "model_id": model_id,
                "overall_score_pct": round(overall) if isinstance(overall, (int, float)) else 0,
                "present": present,
                "absent": absent,
                "partial": partial_count,
                "total_elements": total,
                "severity_label": sev if sev else severity_label(round(overall) if isinstance(overall, (int, float)) else 0),
                "generated_at": generated_at,
            })
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  WARN: {fp.name}: {e}")

    # Sort by severity (worst first), then by model name
    sev_order = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3, "EXCELLENT": 4}
    reports.sort(key=lambda r: (sev_order.get(r["severity_label"], 5), r["model_id"]))

    index = {
        "schema": "crovia.compliance_index.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_reports": len(reports),
        "reports": reports,
    }

    out_path = comp_dir / "index.json"
    with open(out_path, "w") as f:
        json.dump(index, f, indent=2)

    print(f"\nIndex rebuilt: {len(reports)} reports ({errors} errors)")
    print(f"  CRITICAL: {sum(1 for r in reports if r['severity_label'] == 'CRITICAL')}")
    print(f"  HIGH:     {sum(1 for r in reports if r['severity_label'] == 'HIGH')}")
    print(f"  MODERATE: {sum(1 for r in reports if r['severity_label'] == 'MODERATE')}")
    print(f"  LOW:      {sum(1 for r in reports if r['severity_label'] == 'LOW')}")
    print(f"  EXCELLENT:{sum(1 for r in reports if r['severity_label'] == 'EXCELLENT')}")
    print(f"  Output: {out_path} ({os.path.getsize(out_path)} bytes)")


if __name__ == "__main__":
    main()
