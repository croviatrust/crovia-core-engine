from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROOFS_DIR = BASE_DIR / "proofs"
DOCS_DIR = BASE_DIR / "docs"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="CROVIA period orchestration (trust + payouts + floors + proofs)."
    )
    p.add_argument(
        "--period",
        required=True,
        help="Period in YYYY-MM (e.g. 2025-11).",
    )
    p.add_argument(
        "--eur-total",
        type=float,
        required=True,
        help="Total EUR budget to distribute in this period.",
    )
    p.add_argument(
        "--receipts",
        default=str(DATA_DIR / "royalty_from_faiss.ndjson"),
        help="Input NDJSON receipts file (default: data/royalty_from_faiss.ndjson).",
    )
    p.add_argument(
        "--min-appear",
        type=int,
        default=1,
        help="Minimum appearances per provider to be included (default: 1).",
    )
    return p.parse_args()


def run_step(label: str, cmd: List[str], required: bool = True) -> int:
    print(f"\n>>> [{label}] {' '.join(cmd)}")
    proc = subprocess.run(cmd)
    if proc.returncode != 0 and required:
        raise SystemExit(f"[ERROR] Step '{label}' failed with code {proc.returncode}")
    return proc.returncode


def main() -> None:
    args = parse_args()
    period = args.period
    eur_total = float(args.eur_total)
    receipts_path = Path(args.receipts)

    if not receipts_path.exists():
        raise SystemExit(f"[RUN] receipts file not found: {receipts_path}")

    period_compact = period.replace("-", "")

    print(f"=== CROVIA RUN (Period={period}) ===")

    # Usa sempre lo stesso interprete con cui è stato lanciato run_period.py
    python_exe = sys.executable

    # 1) QA receipts
    run_step(
        "QA receipts",
        [python_exe, "qa_receipts.py", str(receipts_path)],
    )

    # 2) CROVIA trust (aggregate providers)
    trust_csv = DATA_DIR / "trust_providers.csv"
    trust_report = DOCS_DIR / "trust_summary.md"
    run_step(
        "CROVIA trust",
        [
            python_exe,
            "crovia_trust.py",
            "--input",
            str(receipts_path),
            "--min-appear",
            str(args.min_appear),
            "--out-provider",
            str(trust_csv),
            "--out-report",
            str(trust_report),
        ],
    )

    # 3) Payouts calculation
    payouts_ndjson = DATA_DIR / f"payouts_{period}.ndjson"
    payouts_csv = DATA_DIR / f"payouts_{period}.csv"
    assumptions_json = DATA_DIR / f"assumptions_{period}.json"
    payouts_log = DATA_DIR / f"payouts_{period}.log"

    run_step(
        "Payouts calculation",
        [
            python_exe,
            "payouts_from_royalties.py",
            "--input",
            str(receipts_path),
            "--period",
            period,
            "--eur-total",
            str(eur_total),
            "--out-ndjson",
            str(payouts_ndjson),
            "--out-csv",
            str(payouts_csv),
            "--out-assumptions",
            str(assumptions_json),
            "--out-log",
            str(payouts_log),
        ],
    )

    # 4) Payout charts (non-blocking)
    readme_payout = DOCS_DIR / f"README_PAYOUT_{period}.md"
    run_step(
        "Payout charts",
        [
            python_exe,
            "make_payout_charts.py",
            "--period",
            period,
            "--csv",
            str(payouts_csv),
            "--readme",
            str(readme_payout),
        ],
        required=False,
    )

    # 5) Hashchain writer (non-blocking) – basato sul nome del file di ricevute
    PROOFS_DIR.mkdir(parents=True, exist_ok=True)
    source_stem = receipts_path.name.replace(".ndjson", "")
    chain_path = PROOFS_DIR / f"hashchain_{source_stem}__{period_compact}_chunk1000.txt"
    run_step(
        "Hashchain writer",
        [
            python_exe,
            "hashchain_writer.py",
            "--source",
            str(receipts_path),
            "--chunk",
            "1000",
            "--out",
            str(chain_path),
        ],
        required=False,
    )

    # 6) Hashchain verify (non-blocking)
    run_step(
        "Hashchain verify",
        [
            python_exe,
            "verify_hashchain.py",
            "--source",
            str(receipts_path),
            "--chain",
            str(chain_path),
            "--chunk",
            "1000",
        ],
        required=False,
    )

    # 7) Crovian Floors (from trust_providers.csv + eur_total)
    run_step(
        "Crovian Floors",
        [
            python_exe,
            "crovia_floor.py",
            "--period",
            period,
            "--eur-total",
            str(eur_total),
            "--trust-csv",
            str(trust_csv),
        ],
        required=False,
    )

    print("\n=== CROVIA PERIOD RUN COMPLETED ===")


if __name__ == "__main__":
    main()
