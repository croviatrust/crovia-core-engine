#!/usr/bin/env python3
"""
Aggregate pipeline health artifacts into a single public JSON.

Inputs (optional):
- pipeline_health_schema_latest.json
- pipeline_health_parity_latest.json

Output:
- pipeline_health_latest.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _read_json(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Aggregate schema/parity health artifacts")
    ap.add_argument("--data-dir", required=True, help="Public data directory")
    ap.add_argument("--out-file", default="pipeline_health_latest.json", help="Output filename")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    schema_path = data_dir / "pipeline_health_schema_latest.json"
    parity_path = data_dir / "pipeline_health_parity_latest.json"

    schema = _read_json(schema_path)
    parity = _read_json(parity_path)

    schema_ok = bool(schema and schema.get("ok") is True)
    parity_ok = bool(parity and parity.get("ok") is True)

    status = "ok"
    if schema is None:
        status = "degraded"
    elif parity is None:
        status = "partial"
    elif not (schema_ok and parity_ok):
        status = "degraded"

    artifact: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "checks": {
            "schema": {
                "available": schema is not None,
                "ok": schema_ok,
            },
            "parity": {
                "available": parity is not None,
                "ok": parity_ok,
            },
        },
        "sources": {
            "schema": str(schema_path.name),
            "parity": str(parity_path.name),
        },
    }

    # carry concise metrics if present
    if schema and isinstance(schema.get("artifacts"), dict):
        metrics = {}
        for name, info in schema["artifacts"].items():
            if isinstance(info, dict) and isinstance(info.get("metrics"), dict):
                metrics[name] = info["metrics"]
        artifact["schema_metrics"] = metrics

    out_path = data_dir / args.out_file
    out_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(artifact, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
