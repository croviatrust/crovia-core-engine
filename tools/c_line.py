#!/usr/bin/env python3
"""
C-LINE v0.1 — Crovia Command Line

Piccolo wrapper per gli script core:
- validate  → crovia_validate.py
- period    → run_period.py
- ai-act    → compliance_ai_act.py
"""

import argparse
import subprocess
import sys
from pathlib import Path

from crovia.sentinel_v0_2 import run_sentinel_v0_2, SentinelConfig
import json


ROOT = Path(__file__).resolve().parent.parent


def run_cmd(cmd: list[str]) -> int:
    """Esegue un comando mostrando chiaramente cosa fa."""
    print(f"[C-LINE] cwd={ROOT}")
    print(f"[C-LINE] $ {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=ROOT)
        return result.returncode
    except KeyboardInterrupt:
        print("\n[C-LINE] Interrotto da tastiera.")
        return 130


def cmd_validate(args: argparse.Namespace) -> int:
    """
    c-line validate data/royalty_from_faiss.ndjson
    """
    cmd = [
        sys.executable,
        "crovia_validate.py",
        args.input,
        "--out-md",
        args.out_md,
        "--out-bad",
        args.out_bad,
    ]
    return run_cmd(cmd)


def cmd_period(args: argparse.Namespace) -> int:
    """
    c-line period --period 2025-11 --eur-total 1000000 --receipts data/royalty_from_faiss.ndjson
    """
    cmd = [
        sys.executable,
        "run_period.py",
        "--period",
        args.period,
        "--eur-total",
        str(args.eur_total),
        "--receipts",
        args.receipts,
        "--min-appear",
        str(args.min_appear),
    ]
    return run_cmd(cmd)


def cmd_ai_act(args: argparse.Namespace) -> int:
    """
    c-line ai-act data/royalty_from_faiss.ndjson
    """
    cmd = [
        sys.executable,
        "compliance_ai_act.py",
        args.input,
        "--out-summary",
        args.out_summary,
        "--out-gaps",
        args.out_gaps,
        "--out-pack",
        args.out_pack,
    ]
    return run_cmd(cmd)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="c-line",
        description="CROVIA C-LINE — front-end a riga di comando per il Crovia Core Engine",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # validate
    pv = sub.add_parser("validate", help="Valida un file royalty_receipt.v1 NDJSON")
    pv.add_argument("input", help="Percorso NDJSON di input (royalty_receipt.v1)")
    pv.add_argument(
        "--out-md",
        default="docs/VALIDATE_report_latest.md",
        help="Report markdown di output (default: docs/VALIDATE_report_latest.md)",
    )
    pv.add_argument(
        "--out-bad",
        default="data/VALIDATE_bad_sample_latest.ndjson",
        help="Campione di righe non valide (default: data/VALIDATE_bad_sample_latest.ndjson)",
    )
    pv.set_defaults(func=cmd_validate)
    
    p_sentinel = sub.add_parser(
        "sentinel",
        help="Run Crovia Sentinel v0.2 drift/transparency analysis",
    )
    p_sentinel.add_argument(
        "--current",
        required=True,
        help="Current snapshot JSON",
    )
    p_sentinel.add_argument(
        "--previous",
        required=True,
        help="Previous snapshot JSON",
    )
    p_sentinel.set_defaults(func=cmd_sentinel)


    # period
    pp = sub.add_parser(
        "period", help="Esegue un run completo di periodo (trust + payout + floors + proofs)"
    )
    pp.add_argument("--period", required=True, help="Periodo es: 2025-11")
    pp.add_argument(
        "--eur-total",
        type=float,
        required=True,
        help="Budget totale in EUR per il periodo",
    )
    pp.add_argument(
        "--receipts",
        required=True,
        help="Percorso NDJSON di input (royalty_receipt.v1)",
    )
    pp.add_argument(
        "--min-appear",
        type=int,
        default=1,
        help="Minimo di apparizioni per considerare un provider (default: 1)",
    )
    pp.set_defaults(func=cmd_period)

    # ai-act
    pa = sub.add_parser(
        "ai-act", help="Genera artefatti AI Act (summary, gaps, pack) da un NDJSON"
    )
    pa.add_argument("input", help="Percorso NDJSON di input (royalty_receipt.v1)")
    pa.add_argument(
        "--out-summary",
        default="docs/AI_ACT_summary_latest.md",
        help="File markdown di summary (default: docs/AI_ACT_summary_latest.md)",
    )
    pa.add_argument(
        "--out-gaps",
        default="data/AI_ACT_gaps_latest.ndjson",
        help="File NDJSON con i gaps (default: data/AI_ACT_gaps_latest.ndjson)",
    )
    pa.add_argument(
        "--out-pack",
        default="data/AI_ACT_pack_latest.json",
        help="JSON pack con i riferimenti (default: data/AI_ACT_pack_latest.json)",
    )
    pa.set_defaults(func=cmd_ai_act)

    return p


def cmd_sentinel(args):
    """
    C-Line: Sentinel v0.2
    Analisi drift + trasparenza tra due snapshot JSON.
    """
    try:
        with open(args.current, "r", encoding="utf-8") as f:
            snap_cur = json.load(f)
        with open(args.previous, "r", encoding="utf-8") as f:
            snap_prev = json.load(f)
    except Exception as e:
        print(f"[FATAL] Cannot read snapshots: {e}")
        return 3

    cfg = SentinelConfig()
    out = run_sentinel_v0_2(
        snapshot_t=snap_cur,
        snapshot_prev=snap_prev,
        group_stats=None,
        state_prev=None,
        config=cfg,
    )

    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
