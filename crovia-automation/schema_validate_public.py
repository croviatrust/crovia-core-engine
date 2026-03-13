#!/usr/bin/env python3
"""
Validate core public registry artifacts with strict-required / forward-compatible schemas.

Usage:
  python schema_validate_public.py --data-dir /var/www/registry/data
  python schema_validate_public.py --data-dir /var/www/registry/data --report-out /tmp/schema_report.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


SCHEMAS: Dict[str, Dict[str, Any]] = {
    "tpa_latest.json": {
        "root_type": dict,
        "required": ["generated_at", "total_tpas", "chain_height", "tpas"],
    },
    "global_ranking.json": {
        "root_type": dict,
        "required": ["generated_at", "total_models", "total_orgs", "model_ranking", "org_ranking"],
    },
    "lineage_graph.json": {
        "root_type": dict,
        "required": ["generated_at", "metrics", "nodes", "edges"],
    },
    "forensic_report.json": {
        "root_type": dict,
        "required": ["generated_at"],
    },
    "gdna_results.json": {
        "root_type": dict,
        "required": ["runs"],
    },
    "warranty/index.json": {
        "root_type": dict,
        "required": ["generated_at", "total_packs", "states", "packs"],
    },
}


def _validate_file(path: Path, schema: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    errs: List[str] = []
    metrics: Dict[str, Any] = {}

    if not path.exists():
        return False, ["file_not_found"], metrics

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, [f"json_parse_error: {e}"], metrics

    root_type = schema["root_type"]
    if not isinstance(data, root_type):
        errs.append(f"root_type_mismatch: expected={root_type.__name__}")
        return False, errs, metrics

    for key in schema.get("required", []):
        if key not in data:
            errs.append(f"missing_required_key: {key}")

    # Small metrics for quick health visibility
    if isinstance(data, dict):
        if "tpas" in data and isinstance(data["tpas"], list):
            metrics["tpas_len"] = len(data["tpas"])
        if "model_ranking" in data and isinstance(data["model_ranking"], list):
            metrics["model_ranking_len"] = len(data["model_ranking"])
        if "nodes" in data and isinstance(data["nodes"], list):
            metrics["nodes_len"] = len(data["nodes"])
        if "edges" in data and isinstance(data["edges"], list):
            metrics["edges_len"] = len(data["edges"])
        if "runs" in data and isinstance(data["runs"], list):
            metrics["runs_len"] = len(data["runs"])

    return len(errs) == 0, errs, metrics


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate public Crovia JSON artifacts")
    ap.add_argument("--data-dir", required=True, help="Directory containing public JSON artifacts")
    ap.add_argument("--report-out", help="Optional path to write JSON report")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    report: Dict[str, Any] = {
        "ok": True,
        "data_dir": str(data_dir),
        "artifacts": {},
    }

    for filename, schema in SCHEMAS.items():
        path = data_dir / filename
        ok, errors, metrics = _validate_file(path, schema)
        report["artifacts"][filename] = {
            "ok": ok,
            "errors": errors,
            "metrics": metrics,
            "path": str(path),
        }
        if not ok:
            report["ok"] = False

    output = json.dumps(report, indent=2, ensure_ascii=False)
    print(output)

    if args.report_out:
        Path(args.report_out).write_text(output, encoding="utf-8")

    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
