#!/usr/bin/env python3
"""
C-LINE v1.0 — Crovia Command Line

High-level command-line front-end for the CROVIA Core Engine.

Supported commands:

- validate  → wraps crovia_validate.py
- period    → wraps run_period.py
- ai-act    → wraps compliance_ai_act.py
- demo      → end-to-end demo pipeline (validate + period + ai-act + ZIP + QR)

Design goals:
- Be easy to use for non-experts (single command for the full demo).
- Never hide what is being executed (always show the underlying commands).
- Optionally produce a compact evidence ZIP and a QR code for quick sharing.
"""

import argparse
import subprocess
import sys
import os

import zipfile
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
ENGINE_ROOT = ROOT / "core"
PRO_ENGINE_ROOT = ROOT / "crovia-pro-engine"



# Optional: Rich for nicer output
try:
    from rich.console import Console  # type: ignore
    console: Optional["Console"] = Console()
except Exception:
    console = None

# Optional: qrcode for QR PNG generation
try:
    import qrcode  # type: ignore
except Exception:
    qrcode = None  # type: ignore


# ---------------- generic helpers ----------------

def log(msg: str) -> None:
    """Standard C-LINE log message."""
    if console:
        console.print(f"[bold cyan][C-LINE][/bold cyan] {msg}")
    else:
        print(f"[C-LINE] {msg}")


def log_cmd(cmd: List[str]) -> None:
    """Show the command that is about to be executed."""
    if console:
        console.print(f"[bold green][C-LINE][/bold green] cwd={ROOT}")
        console.print(f"[bold green][C-LINE][/bold green] $ {' '.join(cmd)}")
    else:
        print(f"[C-LINE] cwd={ROOT}")
        print(f"[C-LINE] $ {' '.join(cmd)}")


def run_cmd(cmd: List[str]) -> int:
    env = dict(**os.environ)
    env["PYTHONPATH"] = str(ENGINE_ROOT.parent)

    """Run a subprocess command and return its exit code."""
    log_cmd(cmd)
    try:
        result = subprocess.run(cmd, cwd=ROOT, env=env)
        return result.returncode
    except KeyboardInterrupt:
        log("Interrupted by user (Ctrl+C).")
        return 130


def collect_artifacts_for_period(period: str) -> List[Path]:
    """
    Collect potential evidence artifacts for a given period.

    Strategy:
    - Look into ROOT, docs/, data/, proofs/
    - Match several glob patterns, e.g. *{period}*, AI_ACT_*, trust_bundle*, hashchain*, payouts_*
    """
    roots = [
        ROOT,
        ROOT / "docs",
        ROOT / "data",
        ROOT / "proofs",
    ]
    patterns = [
        f"*{period}*",
        "VALIDATE_report*",
        "VALIDATE_bad_sample*",
        "AI_ACT_*",
        "trust_bundle*",
        "hashchain*",
        "payouts_*",
        "trust_*",
    ]

    found: List[Path] = []
    seen = set()

    for r in roots:
        if not r.exists():
            continue
        for pat in patterns:
            for p in r.glob(pat):
                if p.is_file():
                    rp = p.resolve()
                    if rp not in seen:
                        found.append(p)
                        seen.add(rp)

    return found


def make_evidence_zip(period: str, artifacts: List[Path]) -> Path:
    """
    Create a ZIP with all given artifacts.
    Returns the path to the ZIP.
    """
    out_dir = ROOT / "evidence"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"CROVIA_evidence_{period}.zip"

    if console:
        console.print(
            f"[bold magenta][C-LINE][/bold magenta] Packing {len(artifacts)} files into {zip_path}"
        )
    else:
        print(f"[C-LINE] Packing {len(artifacts)} files into {zip_path}")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in artifacts:
            try:
                arcname = p.relative_to(ROOT)
            except ValueError:
                arcname = p.name
            zf.write(p, arcname)

    log(f"Evidence pack written: {zip_path}")
    return zip_path


def generate_qr_for_uri(target_uri: str, out_png: Path) -> Optional[Path]:
    """
    Generate a QR code PNG pointing to target_uri (file:// or https://).

    If qrcode is not available, log a message and return None.
    """
    if qrcode is None:
        log("QR generation skipped (Python package 'qrcode' is not installed).")
        return None

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img = qrcode.make(target_uri)
    img.save(out_png)
    log(f"QR code written: {out_png}")
    return out_png


# ---------------- core commands ----------------

def cmd_validate(args: argparse.Namespace) -> int:
    """
    Example:
      c-line validate data/royalty_from_faiss.ndjson

    NOTE: crovia_validate.py currently expects:
      crovia_validate.py [--out-md OUT_MD] [--out-bad OUT_BAD] [--max-bad MAX_BAD] input
    So we pass the input as positional + --out-md / --out-bad.
    """
    cmd = [
        sys.executable,
        str(ENGINE_ROOT / "crovia_validate.py"),
        args.input,              # positional 'input'
        "--out-md",
        args.out_report,         # mapped to --out-md
        "--out-bad",
        args.out_bad,            # mapped to --out-bad
    ]
    return run_cmd(cmd)


def cmd_period(args: argparse.Namespace) -> int:
    """
    Example:
      c-line period --period 2025-11 --eur-total 1000000 --receipts data/royalty_from_faiss.ndjson
    """
    cmd = [
        sys.executable,
        str(ENGINE_ROOT / "run_period.py"),
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
    Example:
      c-line ai-act data/royalty_from_faiss.ndjson

    NOTE: compliance_ai_act.py expects:
      compliance_ai_act.py input [--out-summary ...] [--out-gaps ...] [--out-pack ...]
    So we pass the input as positional, then the optional flags.
    """
    cmd = [
        sys.executable,
        str(ENGINE_ROOT / "compliance_ai_act.py"),
        args.input,              # positional 'input'
        "--out-summary",
        args.out_summary,
        "--out-gaps",
        args.out_gaps,
        "--out-pack",
        args.out_pack,
    ]
    return run_cmd(cmd)


def cmd_demo(args: argparse.Namespace) -> int:
    """
    End-to-end demo pipeline for a given period and receipts file.

    Steps:
      1) Validate receipts     (crovia_validate.py)
      2) Run period pipeline   (run_period.py)
      3) Generate AI Act docs  (compliance_ai_act.py)
      4) Build evidence ZIP    (evidence/CROVIA_evidence_{period}.zip)
      5) Generate QR PNG       (proofs/QR_evidence_{period}.png, if possible)
    """
    period = args.period
    receipts = args.receipts
    eur_total = args.eur_total

    log(f"=== CROVIA DEMO STARTED (period={period}, eur_total={eur_total}, receipts={receipts}) ===")

    # Step 1/5: validate
    log("Step 1/5: validating receipts file...")
    rc = run_cmd([
        sys.executable,
        str(ENGINE_ROOT / "crovia_validate.py"),
        receipts,                             # positional input
        "--out-md",
        f"docs/VALIDATE_report_{period}.md",
        "--out-bad",
        f"data/VALIDATE_bad_sample_{period}.ndjson",
    ])
    if rc != 0:
        log(f"Validation failed with exit code {rc}. Aborting demo.")
        return rc

    # Step 2/5: period
    log("Step 2/5: running period pipeline (trust, payouts, floors, etc.)...")
    rc = run_cmd([
        sys.executable,
        str(ENGINE_ROOT / "run_period.py"),
        "--period",
        period,
        "--eur-total",
        str(eur_total),
        "--receipts",
        receipts,
        "--min-appear",
        str(args.min_appear),
    ])
    if rc != 0:
        log(f"run_period.py failed with exit code {rc}. Aborting demo.")
        return rc

    # Step 3/5: AI Act docs
    log("Step 3/5: AI Act compliance (PRO edition only) — skipped in open-core.")
    log("C-LINE OPEN completed successfully (trust + payouts + proofs).")
    return 0
    # Step 4/5: ZIP pack
    log("Step 4/5: collecting artifacts and building evidence ZIP...")
    artifacts = collect_artifacts_for_period(period)
    if not artifacts:
        log("No artifacts found for the selected period. Evidence ZIP will not be created.")
        zip_path = None
    else:
        zip_path = make_evidence_zip(period, artifacts)

    # Step 5/5: QR PNG
    log("Step 5/5: generating QR code for the evidence pack (if possible)...")
    if zip_path is not None:
        uri = zip_path.resolve().as_uri()
        qr_path = ROOT / "proofs" / f"QR_evidence_{period}.png"
        generate_qr_for_uri(uri, qr_path)

    log("=== CROVIA DEMO COMPLETED ===")
    if zip_path is not None:
        log(f"Evidence pack: {zip_path.resolve()}")
        log("You can share the ZIP file or the QR code image with auditors, partners or colleagues.")

    return 0


# ---------------- CLI parser ----------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="c-line",
        description="CROVIA C-LINE — command-line front-end for the CROVIA Core Engine",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # validate
    pv = sub.add_parser(
        "validate",
        help="Validate a royalty_receipt.v1 NDJSON file.",
    )
    pv.add_argument(
        "input",
        help="Path to input NDJSON file (royalty_receipt.v1).",
    )
    pv.add_argument(
        "--out-report",
        default="docs/VALIDATE_report_latest.md",
        help="Markdown report output path (mapped to crovia_validate.py --out-md; default: docs/VALIDATE_report_latest.md).",
    )
    pv.add_argument(
        "--out-bad",
        default="data/VALIDATE_bad_sample_latest.ndjson",
        help="Output path for a sample of invalid lines (mapped to crovia_validate.py --out-bad; default: data/VALIDATE_bad_sample_latest.ndjson).",
    )
    pv.set_defaults(func=cmd_validate)

    # period
    pp = sub.add_parser(
        "period",
        help="Run a full settlement period (trust + payouts + floors + proofs).",
    )
    pp.add_argument(
        "--period",
        required=True,
        help="Period identifier, e.g. 2025-11.",
    )
    pp.add_argument(
        "--eur-total",
        type=float,
        required=True,
        help="Total budget in EUR for the period.",
    )
    pp.add_argument(
        "--receipts",
        required=True,
        help="Path to input NDJSON file (royalty_receipt.v1).",
    )
    pp.add_argument(
        "--min-appear",
        type=int,
        default=1,
        help="Minimum number of appearances required to consider a provider (default: 1).",
    )
    pp.set_defaults(func=cmd_period)

    # ai-act
    pa = sub.add_parser(
        "ai-act",
        help="Generate AI Act artifacts (summary, gaps, pack) from a receipts NDJSON file.",
    )
    pa.add_argument(
        "input",
        help="Path to input NDJSON file (royalty_receipt.v1).",
    )
    pa.add_argument(
        "--out-summary",
        default="docs/AI_ACT_summary_latest.md",
        help="Markdown summary output path (default: docs/AI_ACT_summary_latest.md).",
    )
    pa.add_argument(
        "--out-gaps",
        default="data/AI_ACT_gaps_latest.csv",
        help="CSV gaps output path (default: data/AI_ACT_gaps_latest.csv).",
    )
    pa.add_argument(
        "--out-pack",
        default="data/AI_ACT_pack_latest.json",
        help="JSON pack output path (default: data/AI_ACT_pack_latest.json).",
    )
    pa.set_defaults(func=cmd_ai_act)

    # demo
    pd = sub.add_parser(
        "demo",
        help="Run the full CROVIA demo pipeline (validate + period + ai-act + ZIP + QR).",
    )
    pd.add_argument(
        "--period",
        default="2025-11",
        help="Demo period identifier (default: 2025-11).",
    )
    pd.add_argument(
        "--eur-total",
        type=float,
        default=1_000_000.0,
        help="Demo budget in EUR (default: 1000000.0).",
    )
    pd.add_argument(
        "--receipts",
        default="data/royalty_from_faiss.ndjson",
        help="Path to demo NDJSON receipts file (default: data/royalty_from_faiss.ndjson).",
    )
    pd.add_argument(
        "--min-appear",
        type=int,
        default=1,
        help="Minimum number of appearances required to consider a provider (default: 1).",
    )
    pd.set_defaults(func=cmd_demo)

    return p


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
