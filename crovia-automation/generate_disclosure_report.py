#!/usr/bin/env python3
"""
CROVIA Disclosure Report Generator
===================================

Generates a human-readable Markdown report from the Disclosure Index JSON.
This is observational data only - no judgment, no accusation.

Author: Crovia Engineering
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _fmt_num(n: Any) -> str:
    """Format number with K/M suffix for readability."""
    if n is None:
        return "N/A"
    try:
        n = int(n)
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)
    except:
        return str(n)


def generate_report(index: Dict[str, Any]) -> str:
    """Generate human-readable Markdown report from Disclosure Index."""
    
    week_id = index.get("week_id", "Unknown")
    generated_at = index.get("generated_at", "")[:19].replace("T", " ")
    
    coverage = index.get("coverage", {})
    targets = coverage.get("targets_monitored", 0)
    models = coverage.get("models", 0)
    datasets = coverage.get("datasets", 0)
    
    obs = index.get("disclosure_observations", {})
    training = obs.get("training_section", {})
    declared = obs.get("declared_datasets", {})
    license_obs = obs.get("license", {})
    readme = obs.get("readme_access", {})
    
    drift = index.get("drift_observations", {})
    pop = index.get("popularity_observations", {})
    orgs = index.get("by_organization", [])
    
    # Build the report
    lines = [
        "# 📊 Crovia Disclosure Transparency Report",
        "",
        f"> **Week {week_id}** | Generated {generated_at} UTC",
        ">",
        "> *This is observational data only. No inference, judgment, or accusation.*",
        "",
        "---",
        "",
        "## 📈 Coverage",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| **Targets Monitored** | {targets} |",
        f"| Models | {models} |",
        f"| Datasets | {datasets} |",
        "",
        "---",
        "",
        "## 🔍 Disclosure Observations",
        "",
        "| Field | Present | Absent | % Present |",
        "|-------|---------|--------|-----------|",
        f"| **Training Section** | {training.get('present', 0)} | {training.get('absent', 0)} | **{training.get('present_pct', 0)}%** |",
        f"| **Declared Datasets** | {declared.get('with_declaration', 0)} | {declared.get('without_declaration', 0)} | **{declared.get('with_declaration_pct', 0)}%** |",
        f"| **License** | {license_obs.get('declared', 0)} | {license_obs.get('not_declared', 0)} | **{license_obs.get('declared_pct', 0)}%** |",
        f"| **README Accessible** | {readme.get('ok', 0)} | {readme.get('not_found', 0) + readme.get('forbidden', 0)} | **{readme.get('ok_pct', 0)}%** |",
        "",
        "---",
        "",
        "## 📥 Popularity Observations",
        "",
        f"- **Targets with download data:** {pop.get('targets_with_download_data', 0)}",
        f"- **Gated targets:** {pop.get('gated_targets', 0)} ({pop.get('gated_pct', 0)}%)",
        "",
    ]
    
    # Top by downloads
    top_downloads = pop.get("top_by_downloads", [])
    if top_downloads:
        lines.extend([
            "### Top Targets by Downloads",
            "",
            "| Target | Type | Downloads | Training Section | Declared Datasets |",
            "|--------|------|-----------|------------------|-------------------|",
        ])
        for t in top_downloads[:10]:
            lines.append(
                f"| `{t.get('target_id', '')}` | {t.get('tipo_target', '')} | **{_fmt_num(t.get('downloads'))}** | {t.get('training_section_presence', '')} | {t.get('declared_datasets_count', 0)} |"
            )
        lines.append("")
    
    # High download without training section
    high_no_training = pop.get("high_download_training_absent", [])
    if high_no_training:
        lines.extend([
            "### High-Download Targets Without Training Section",
            "",
            "*Factual observation: these targets have >10K downloads and no detected training section.*",
            "",
            "| Target | Downloads | README |",
            "|--------|-----------|--------|",
        ])
        for t in high_no_training[:10]:
            lines.append(
                f"| `{t.get('target_id', '')}` | **{_fmt_num(t.get('downloads'))}** | {t.get('readme_access', '')} |"
            )
        lines.append("")
    
    lines.extend([
        "---",
        "",
        "## 🏢 By Organization",
        "",
        "| Organization | Targets | Training Section | Declared Datasets | License |",
        "|--------------|---------|------------------|-------------------|---------|",
    ])
    
    for org in orgs[:15]:
        org_name = org.get("organization", "")
        org_targets = org.get("targets_monitored", 0)
        org_training = org.get("training_section_present", 0)
        org_declared = org.get("declared_datasets_present", 0)
        org_license = org.get("license_present", 0)
        
        training_pct = round(100 * org_training / org_targets, 0) if org_targets > 0 else 0
        declared_pct = round(100 * org_declared / org_targets, 0) if org_targets > 0 else 0
        license_pct = round(100 * org_license / org_targets, 0) if org_targets > 0 else 0
        
        lines.append(
            f"| **{org_name}** | {org_targets} | {org_training} ({training_pct:.0f}%) | {org_declared} ({declared_pct:.0f}%) | {org_license} ({license_pct:.0f}%) |"
        )
    
    lines.extend([
        "",
        "---",
        "",
        "## 📉 Drift Observations",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| **Changes (7 days)** | {drift.get('events_7d', 0)} |",
        f"| **Changes (30 days)** | {drift.get('events_30d', 0)} |",
        f"| **Targets with changes** | {drift.get('targets_with_change_30d', 0)} |",
        "",
        "---",
        "",
        "## ℹ️ Methodology",
        "",
        "This report aggregates publicly observable data from HuggingFace:",
        "",
        "- **Training Section**: Detected via `## Training` heading in README",
        "- **Declared Datasets**: From `cardData.datasets` in model/dataset card",
        "- **License**: From `cardData.license`",
        "- **Downloads/Likes**: From HuggingFace API",
        "",
        "**What this report does NOT do:**",
        "- Make accusations",
        "- Infer compliance or non-compliance",
        "- Judge quality or intent",
        "- Assign scores or rankings",
        "",
        "---",
        "",
        f"*Report fingerprint: `{index.get('index_fingerprint', 'N/A')[:16]}...`*",
        "",
        "*Source: [Crovia Training Provenance Registry](https://registry.croviatrust.com)*",
    ])
    
    return "\n".join(lines)


def main() -> int:
    if sys.version_info < (3, 6):
        raise SystemExit("Requires Python 3.6+")
    
    dataset_root = os.getenv("CROVIA_OPEN_DATASET_DIR") or os.getenv("CROVIA_DATASET_DIR") or os.getcwd()
    
    index_path = os.path.join(dataset_root, "open", "reports", "disclosure_index_latest.json")
    index = _load_json(index_path)
    
    if not index:
        print(f"[ERROR] Could not load {index_path}")
        return 1
    
    report = generate_report(index)
    
    # Write report
    reports_dir = os.path.join(dataset_root, "open", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    report_path = os.path.join(reports_dir, "DISCLOSURE_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(report)
    print(f"\n[CROVIA] Report written to: {report_path}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
