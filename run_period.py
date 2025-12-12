#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

# ----------------------------------------------------------
# Utility
# ----------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROOFS_DIR = BASE_DIR / "proofs"


def run_step(label, cmd, required=True):
    print(f"\n>>> [{label}] {' '.join(str(x) for x in cmd)}")

    try:
        result = subprocess.run(cmd, check=required)
    except subprocess.CalledProcessError:
        if required:
            print(f"[FATAL] Step failed: {label}")
            sys.exit(1)
        else:
            print(f"[SKIP] Step failed (optional): {label}")
            return False
    return True


# ----------------------------------------------------------
# SNAPSHOT HANDLING
# ----------------------------------------------------------

def update_snapshots(period: str):
    snap_prev = DATA_DIR / f"snapshot_prev_{period}.json"
    snap_curr = DATA_DIR / f"snapshot_curr_{period}.json"

    # Move current → prev
    if snap_curr.exists():
        snap_prev.write_text(snap_curr.read_text())

    # Build new "curr" snapshot
    snapshot = {
        "period": period,
        "card_length": 0,
        "missing_fields_fraction": 0.0,
        "legal_ambiguity_level": 0.0,
        "receipts_fraction": 0.0,
    }
    snap_curr.write_text(json.dumps(snapshot, indent=2))

    print(f"[SNAPSHOT] Updated prev/curr snapshots for period {period}")


# ----------------------------------------------------------
# SENTINEL PRO
# ----------------------------------------------------------

def sentinel_pro(period: str):
    try:
        from croviapro.semantic.sentinel_v1 import run_sentinel_pro
    except Exception as e:
        print(f"[SENTINEL PRO] Skipped ({e})")
        return

    snap_prev = DATA_DIR / f"snapshot_prev_{period}.json"
    snap_curr = DATA_DIR / f"snapshot_curr_{period}.json"

    if not (snap_prev.exists() and snap_curr.exists()):
        print("[SENTINEL PRO] Snapshots missing; skipping")
        return

    try:
        s_prev = json.loads(snap_prev.read_text())
        s_curr = json.loads(snap_curr.read_text())

        result = run_sentinel_pro(
            snapshot_t=s_curr,
            snapshot_prev=s_prev,
            state_prev=None,
            cfg=None,
        )

        out_file = DATA_DIR / f"sentinel_pro_report_{period}.json"
        out_file.write_text(json.dumps(result, indent=2))
        print(f"[SENTINEL PRO] Level={result.get('level')}  S_alert={result.get('S_alert')}")
        print(f"[SENTINEL PRO] Wrote {out_file}")

    except Exception as e:
        print(f"[SENTINEL PRO] Error: {e}")


# ----------------------------------------------------------
# MAIN LOGIC
# ----------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", required=True)
    parser.add_argument("--eur-total", required=True, type=float)
    parser.add_argument("--receipts", required=True)
    args = parser.parse_args()

    period = args.period
    eur_total = args.eur_total
    receipts_path = Path(args.receipts)

    venv_python = sys.executable

    print(f"=== CROVIA RUN (Period={period}) ===")

    # ------------------------------------------------------
    # 1. QA
    # ------------------------------------------------------
    run_step(
        "QA receipts",
        [venv_python, "qa_receipts.py", str(receipts_path)],
    )

    # ------------------------------------------------------
    # 2. TRUST BUILD
    # ------------------------------------------------------
    run_step(
        "CROVIA trust",
        [
            venv_python,
            "crovia_trust.py",
            "--input", str(receipts_path),
            "--min-appear", "1",
            "--out-provider", str(DATA_DIR / "trust_providers.csv"),
            "--out-report", "trust_summary.md",
        ],
    )

    # ------------------------------------------------------
    # 3. VALIDATE
    # ------------------------------------------------------
    run_step(
        "Validate schema+business",
        [
            venv_python,
            "crovia_validate.py",
            str(receipts_path),
            "--out-md", "validate_report.md",
            "--out-bad", "validate_sample_bad.jsonl",
        ],
    )

    # ------------------------------------------------------
    # 4. COMPLIANCE
    # ------------------------------------------------------
    run_step(
        "Compliance AI Act",
        [
            venv_python,
            "compliance_ai_act.py",
            str(receipts_path),
            "--out-summary", "compliance_summary.md",
            "--out-gaps", str(DATA_DIR / "compliance_gaps.csv"),
            "--out-pack", str(DATA_DIR / "compliance_pack.json"),
        ],
    )

    # ------------------------------------------------------
    # 5. PAYOUTS
    # ------------------------------------------------------
    run_step(
        "Payouts calculation",
        [
            venv_python,
            "payouts_from_royalties.py",
            "--input", str(receipts_path),
            "--period", period,
            "--eur-total", str(eur_total),
            "--out-ndjson", str(DATA_DIR / f"payouts_{period}.ndjson"),
            "--out-csv", str(DATA_DIR / f"payouts_{period}.csv"),
            "--out-assumptions", str(DATA_DIR / f"assumptions_{period}.json"),
            "--out-log", str(DATA_DIR / f"payouts_{period}.log"),
        ],
    )

    # ------------------------------------------------------
    # 6. CHARTS
    # ------------------------------------------------------
    run_step(
        "Payout charts",
        [
            venv_python,
            "make_payout_charts.py",
            "--period", period,
            "--csv", str(DATA_DIR / f"payouts_{period}.csv"),
            "--readme", str(BASE_DIR / f"README_PAYOUT_{period}.md"),
        ],
        required=False,
    )

    # ------------------------------------------------------
    # 7. HASHCHAIN
    # ------------------------------------------------------
    chain_file = PROOFS_DIR / f"hashchain_royalty_{period}_chunk1000.txt"
    run_step(
        "Hashchain writer",
        [
            venv_python,
            "hashchain_writer.py",
            "--source", str(receipts_path),
            "--chunk", "1000",
            "--out", str(chain_file),
        ],
    )

    run_step(
        "Hashchain verify",
        [
            venv_python,
            "verify_hashchain.py",
            "--source", str(receipts_path),
            "--chain", str(chain_file),
            "--chunk", "1000",
        ],
    )

    # ------------------------------------------------------
    # 8. PRO PAYOUTS ENGINE
    # ------------------------------------------------------
    run_step(
        "PRO payouts",
        [
            venv_python,
            "payouts_pro_run.py",
            "--period", period,
            "--eur-total", str(eur_total),
            "--providers", str(BASE_DIR / "test_providers.json"),
            "--out", str(DATA_DIR / f"payouts_pro_{period}.json"),
        ],
        required=False,
    )

    # ------------------------------------------------------
    # 9. FLOORS
    # ------------------------------------------------------
    run_step(
        "Crovian Floors",
        [
            venv_python,
            "crovia_floor.py",
            "--period", period,
            "--eur-total", str(eur_total),
            "--trust-csv", str(DATA_DIR / "trust_providers.csv"),
        ],
        required=False,
    )

    # ------------------------------------------------------
    # 10. SNAPSHOTS
    # ------------------------------------------------------
    update_snapshots(period)

    # ------------------------------------------------------
    # 11. SENTINEL PRO
    # ------------------------------------------------------
    print("\n>>> [SENTINEL PRO] Running semantic integrity…")
    sentinel_pro(period)

    print("\n=== CROVIA PERIOD RUN COMPLETED ===")


if __name__ == "__main__":
    main()
