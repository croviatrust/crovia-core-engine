# Copyright 2025  Tarik En Nakhai
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROOFS_DIR = BASE_DIR / "proofs"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="CROVIA period orchestration (trust + payouts + bundle + floors)."
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

    # Always use the current Python interpreter (whatever venv is active)
    venv_python = sys.executable

    # 1) QA receipts
    run_step(
        "QA receipts",
        [venv_python, "qa_receipts.py", str(receipts_path)],
    )

    # 2) CROVIA trust (aggregate providers)
    run_step(
        "CROVIA trust",
        [
            venv_python,
            "crovia_trust.py",
            "--input",
            str(receipts_path),
            "--min-appear",
            str(args.min_appear),
            "--out-provider",
            str(DATA_DIR / "trust_providers.csv"),
            "--out-report",
            "trust_summary.md",
        ],
    )

    # 3) Validate schema + business (non-blocking, optional script)
    validate_script = BASE_DIR / "crovia_validate.py"
    if validate_script.exists():
        run_step(
            "Validate schema+business",
            [
                venv_python,
                "crovia_validate.py",
                "--out-md",
                str(receipts_path),
                "--out-report",
                "validate_report.md",
                "--out-bad",
                "validate_sample_bad.jsonl",
            ],
            required=False,
        )
    else:
        print("[SKIP] Validate schema+business (crovia_validate.py not present in this edition)")

    # 4) Compliance AI Act (non-blocking, optional script)
    compliance_script = BASE_DIR / "compliance_ai_act.py"
    if compliance_script.exists():
        run_step(
            "Compliance AI Act",
            [
                venv_python,
                "compliance_ai_act.py",
                str(receipts_path),
                "--out-summary",
                "compliance_summary.md",
                "--out-gaps",
                str(DATA_DIR / "compliance_gaps.csv"),
                "--out-pack",
                str(DATA_DIR / "compliance_pack.json"),
            ],
            required=False,
        )
    else:
        print("[SKIP] Compliance AI Act (compliance_ai_act.py not present in this edition)")

    # 5) Payouts calculation
    payouts_ndjson = DATA_DIR / f"payouts_{period}.ndjson"
    payouts_csv = DATA_DIR / f"payouts_{period}.csv"
    assumptions_json = DATA_DIR / f"assumptions_{period}.json"
    payouts_log = DATA_DIR / f"payouts_{period}.log"

    run_step(
        "Payouts calculation",
        [
            venv_python,
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

    # 6) Payout charts (non-blocking)
    readme_payout = BASE_DIR / f"README_PAYOUT_{period}.md"
    run_step(
        "Payout charts",
        [
            venv_python,
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

    # 7) Hashchain writer (non-blocking)
    PROOFS_DIR.mkdir(parents=True, exist_ok=True)
    chain_path = PROOFS_DIR / f"hashchain_royalty_from_faiss.ndjson__{period_compact}_chunk1000.txt"
    run_step(
        "Hashchain writer",
        [
            venv_python,
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

    # 8) Hashchain verify (non-blocking)
    run_step(
        "Hashchain verify",
        [
            venv_python,
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

    # 9) Trust bundle (optional in open_core; governance layer can be closed-source)
    make_bundle_script = BASE_DIR / "make_trust_bundle.py"
    if make_bundle_script.exists():
        run_step(
            "Trust bundle",
            [
                venv_python,
                "make_trust_bundle.py",
                "--period",
                period,
                "--receipts",
                str(receipts_path),
            ],
            required=False,
        )
    else:
        print("[SKIP] Trust bundle (make_trust_bundle.py not present in this edition)")

    # 10) Crovian Floors (from trust_providers.csv + eur_total)
    run_step(
        "Crovian Floors",
        [
            venv_python,
            "crovia_floor.py",
            "--period",
            period,
            "--eur-total",
            str(eur_total),
            "--trust-csv",
            str(DATA_DIR / "trust_providers.csv"),
        ],
        required=False,
    )

    # 11) Augment trust bundle (optional in open_core)
    augment_script = BASE_DIR / "augment_trust_bundle.py"
    if augment_script.exists():
        run_step(
            "Augment trust bundle",
            [
                venv_python,
                "augment_trust_bundle.py",
                "--period",
                period,
            ],
            required=False,
        )
    else:
        print("[SKIP] Augment trust bundle (augment_trust_bundle.py not present in this edition)")

    print("\n=== CROVIA PERIOD RUN COMPLETED ===")


if __name__ == "__main__":
    main()
