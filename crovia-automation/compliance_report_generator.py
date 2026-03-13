#!/usr/bin/env python3
"""
CROVIA Compliance Report Generator
====================================

Generates per-model compliance mappings (20 NEC# × 11 jurisdictions)
and exports them as JSON + Markdown for the public registry.

Usage:
    python compliance_report_generator.py google/gemma-3-12b-it
    python compliance_report_generator.py --all-outreach
    python compliance_report_generator.py --batch models.txt

Copyright (c) 2026 Crovia / CroviaTrust
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add pro-engine to path
_SCRIPT_DIR = Path(__file__).resolve().parent
_PRO_ROOT = _SCRIPT_DIR.parent / "crovia-pro-engine"
if _PRO_ROOT.exists():
    sys.path.insert(0, str(_PRO_ROOT))

from croviapro.compliance.mapper import ComplianceMapper


def _load_token() -> str:
    """Load HF token from environment or tpr.env."""
    token = os.environ.get("HF_TOKEN", "")
    if token:
        return token

    env_paths = [
        Path("/etc/crovia/tpr.env"),
        _SCRIPT_DIR.parent / ".env",
    ]
    for p in env_paths:
        if p.exists():
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("HF_TOKEN="):
                        return line.split("=", 1)[1].strip('"').strip("'")
    return ""


def _output_dir() -> Path:
    """Get the compliance reports output directory (public/redacted)."""
    webroot = Path(os.environ.get("CROVIA_WEBROOT", "/var/www/registry"))
    out = webroot / "data" / "compliance"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _full_output_dir() -> Path:
    """Get the full (PRO) reports directory — not web-accessible."""
    out = Path(os.environ.get("CROVIA_COMPLIANCE_FULL", "/opt/crovia/data/compliance_full"))
    out.mkdir(parents=True, exist_ok=True)
    return out


def redact_for_public(report: dict) -> dict:
    """Strip PRO-tier detail from a compliance report for public display.

    Public version keeps:
      - summary (score, label, counts)
      - observations: nec_id, name, description, status, severity (NO evidence, confidence, jurisdictions_affected)
      - jurisdiction_scores: code, name, score_pct, present, absent, partial, total_elements (NO missing_articles, missing_necs, severity_weighted_score)
      - top_gaps: first 3 only, nec_id, name, severity, status, jurisdictions_count (NO articles)
      - recommendations: REMOVED (replaced with PRO CTA flag)
    """
    pub = {
        "schema": report.get("schema", "crovia.compliance_map.v1"),
        "generated_at": report.get("generated_at"),
        "model_id": report.get("model_id"),
        "card_length": report.get("card_length", 0),
        "summary": report.get("summary", {}),
        "tier": "open",
    }

    # Observations — strip evidence & jurisdiction detail
    pub["observations"] = [
        {
            "nec_id": o["nec_id"],
            "name": o["name"],
            "description": o["description"],
            "status": o["status"],
            "severity": o["severity"],
        }
        for o in report.get("observations", [])
    ]

    # Jurisdiction scores — strip article-level detail
    pub["jurisdiction_scores"] = [
        {
            "code": j["code"],
            "name": j["name"],
            "total_elements": j["total_elements"],
            "present": j["present"],
            "absent": j["absent"],
            "partial": j["partial"],
            "score_pct": j["score_pct"],
        }
        for j in report.get("jurisdiction_scores", [])
    ]

    # Top gaps — first 3 only, empty articles for backward-compat with cached JS
    pub["top_gaps"] = [
        {
            "nec_id": g["nec_id"],
            "name": g["name"],
            "severity": g["severity"],
            "status": g["status"],
            "jurisdictions_count": g["jurisdictions_count"],
            "articles": [],
        }
        for g in report.get("top_gaps", [])[:3]
    ]
    pub["total_gaps"] = len(report.get("top_gaps", []))

    # Empty recommendations for backward-compat with cached JS
    pub["recommendations"] = []

    return pub


def generate_report(model_id: str, mapper: ComplianceMapper, token: str,
                    output_dir: Path, full_dir: Path | None = None) -> dict:
    """Generate and save a compliance report for one model.

    Saves redacted (public) JSON to output_dir and full JSON to full_dir.
    """
    print(f"  Analyzing: {model_id} ...", end=" ", flush=True)

    try:
        report = mapper.analyze_from_url(model_id, hf_token=token)
    except Exception as e:
        print(f"FAILED: {e}")
        return None

    report_dict = report.to_dict()
    markdown = mapper.to_markdown(report)

    # Safe filename: google/gemma-3-12b-it → google__gemma-3-12b-it
    safe_name = model_id.replace("/", "__")

    # Save FULL report to private directory
    if full_dir:
        full_json = full_dir / f"{safe_name}.json"
        full_md = full_dir / f"{safe_name}.md"
        with open(full_json, "w") as f:
            json.dump(report_dict, f, indent=2)
        with open(full_md, "w") as f:
            f.write(markdown)

    # Save REDACTED report to public web directory
    pub_dict = redact_for_public(report_dict)
    json_path = output_dir / f"{safe_name}.json"
    with open(json_path, "w") as f:
        json.dump(pub_dict, f, indent=2)

    # Markdown stays in full dir only; public gets JSON
    if not full_dir:
        md_path = output_dir / f"{safe_name}.md"
        with open(md_path, "w") as f:
            f.write(markdown)

    score = report_dict["summary"]["overall_score_pct"]
    label = report_dict["summary"]["severity_label"]
    present = report_dict["summary"]["present"]
    total = report_dict["summary"]["total_nec_elements"]
    print(f"{score}% ({label}) — {present}/{total} present")

    return report_dict


def generate_index(output_dir: Path, reports: list):
    """Generate an index JSON of all compliance reports."""
    index = {
        "schema": "crovia.compliance_index.v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "total_reports": len(reports),
        "reports": [],
    }

    for r in reports:
        if r is None:
            continue
        index["reports"].append({
            "model_id": r["model_id"],
            "overall_score_pct": r["summary"]["overall_score_pct"],
            "severity_label": r["summary"]["severity_label"],
            "present": r["summary"]["present"],
            "absent": r["summary"]["absent"],
            "partial": r["summary"]["partial"],
            "total_elements": r["summary"]["total_nec_elements"],
            "generated_at": r["generated_at"],
        })

    index["reports"].sort(key=lambda x: x["overall_score_pct"])

    index_path = output_dir / "index.json"
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
    print(f"\nIndex: {index_path} ({len(index['reports'])} reports)")


def main():
    parser = argparse.ArgumentParser(description="Generate CROVIA compliance reports")
    parser.add_argument("model_ids", nargs="*", help="Model IDs to analyze")
    parser.add_argument("--all-outreach", action="store_true",
                        help="Generate reports for all outreach targets")
    parser.add_argument("--batch", type=str, help="File with model IDs (one per line)")
    parser.add_argument("--output", type=str, help="Output directory override")
    args = parser.parse_args()

    token = _load_token()
    if not token:
        print("WARNING: No HF_TOKEN found. Gated models will fail.")

    output_dir = Path(args.output) if args.output else _output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    full_dir = _full_output_dir()

    mapper = ComplianceMapper()
    model_ids = list(args.model_ids)

    if args.batch:
        with open(args.batch) as f:
            model_ids.extend(line.strip() for line in f if line.strip() and not line.startswith("#"))

    if args.all_outreach:
        # Load from sent_discussions.jsonl
        sent_path = _SCRIPT_DIR / "sent_discussions.jsonl"
        if sent_path.exists():
            with open(sent_path) as f:
                for line in f:
                    rec = json.loads(line.strip())
                    tid = rec.get("target_id", "")
                    if tid and tid not in model_ids:
                        model_ids.append(tid)

        # Also load from targets_unified.json (discovery targets)
        targets_path = _SCRIPT_DIR / "targets_unified.json"
        if targets_path.exists():
            try:
                with open(targets_path) as f:
                    tdata = json.load(f)
                    for t in tdata:
                        tid = t.get("target_id", "") if isinstance(t, dict) else str(t)
                        if tid and tid not in model_ids:
                            model_ids.append(tid)
            except Exception:
                pass

    if not model_ids:
        parser.print_help()
        sys.exit(1)

    print(f"CROVIA Compliance Report Generator")
    print(f"{'='*50}")
    print(f"Models: {len(model_ids)}")
    print(f"Output: {output_dir}")
    print()

    import time as _time
    RATE_DELAY = 6.0   # 600 req/h max — compliance makes 1-2 HF calls per model
    SKIP_DAYS  = 6     # skip models whose report is < 6 days old (regenerate weekly)
    reports = []
    skipped = 0
    for i, mid in enumerate(model_ids):
        safe_name = mid.replace("/", "__")
        pub_path  = output_dir / f"{safe_name}.json"
        if pub_path.exists():
            try:
                age_s = _time.time() - os.path.getmtime(pub_path)
                if age_s < SKIP_DAYS * 86400:
                    skipped += 1
                    reports.append(None)
                    continue
            except Exception:
                pass
        t0 = _time.time()
        r  = generate_report(mid, mapper, token, output_dir, full_dir)
        reports.append(r)
        wait = RATE_DELAY - (_time.time() - t0)
        if wait > 0 and i < len(model_ids) - 1:
            _time.sleep(wait)
    print(f"Skipped (recent <{SKIP_DAYS}d): {skipped}/{len(model_ids)}")

    generate_index(output_dir, reports)

    ok = sum(1 for r in reports if r is not None)
    print(f"\nDone: {ok}/{len(model_ids)} reports generated")


if __name__ == "__main__":
    main()
