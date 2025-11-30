from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Any, List


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Check that payouts are >= Crovian Floors for a given period."
    )
    p.add_argument(
        "--period",
        required=True,
        help="Period in YYYY-MM (e.g. 2025-11)",
    )
    p.add_argument(
        "--floors-json",
        default=None,
        help="Path to floors_<period>.json (default: data/floors_<period>.json)",
    )
    p.add_argument(
        "--payouts-csv",
        default=None,
        help="Path to payouts_<period>.csv (default: data/payouts_<period>.csv)",
    )
    p.add_argument(
        "--out-report",
        default=None,
        help="Optional CSV report output (default: data/check_floors_vs_payouts_<period>.csv)",
    )
    return p.parse_args()


def load_floors(path: Path) -> Dict[str, float | None]:
    if not path.exists():
        raise SystemExit(f"[CHECK] floors JSON not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    providers = payload.get("providers")
    if not isinstance(providers, list):
        raise SystemExit("[CHECK] floors JSON malformed (no 'providers' list).")

    floors: Dict[str, float | None] = {}
    for entry in providers:
        if not isinstance(entry, dict):
            continue
        pid = (entry.get("provider_id") or "").strip()
        if not pid:
            continue
        floor_val = entry.get("floor_eur")
        if isinstance(floor_val, (int, float)):
            floors[pid] = float(floor_val)
        else:
            floors[pid] = None
    return floors


def detect_provider_column(fieldnames: List[str]) -> str:
    if not fieldnames:
        raise SystemExit("[CHECK] payouts CSV has no header.")

    for cand in ("provider", "provider_id", "id"):
        if cand in fieldnames:
            return cand

    raise SystemExit(
        "[CHECK] No provider column found in payouts CSV "
        "(expected provider/provider_id/id). "
        f"Header: {fieldnames}"
    )


def detect_payout_column(fieldnames: List[str]) -> str:
    """
    Usa una lista di nomi noti per la colonna 'payout'.
    Per il tuo caso userà 'amount'.
    """
    candidates = (
        "payout_eur",
        "amount_eur",
        "eur",
        "payout",
        "amount",
        "gross_revenue",
        "share_agg",
    )
    for cand in candidates:
        if cand in fieldnames:
            print(f"[CHECK] Using '{cand}' as payout column.")
            return cand

    raise SystemExit(
        "[CHECK] No payout-like column found in payouts CSV. "
        f"Header: {fieldnames}"
    )


def load_payouts(path: Path) -> Dict[str, float]:
    if not path.exists():
        raise SystemExit(f"[CHECK] payouts CSV not found: {path}")

    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    provider_col = detect_provider_column(fieldnames)
    payout_col = detect_payout_column(fieldnames)

    payouts: Dict[str, float] = {}
    for row in rows:
        pid = (row.get(provider_col) or "").strip()
        if not pid:
            continue
        raw = row.get(payout_col, "")
        if raw in ("", None):
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            # qualche riga sporca → la saltiamo
            continue
        payouts[pid] = payouts.get(pid, 0.0) + val

    return payouts


def main() -> None:
    args = parse_args()
    period = args.period

    floors_path = (
        Path(args.floors_json)
        if args.floors_json
        else DATA_DIR / f"floors_{period}.json"
    )
    payouts_path = (
        Path(args.payouts_csv)
        if args.payouts_csv
        else DATA_DIR / f"payouts_{period}.csv"
    )
    out_report_path = (
        Path(args.out_report)
        if args.out_report
        else DATA_DIR / f"check_floors_vs_payouts_{period}.csv"
    )

    floors = load_floors(floors_path)
    payouts = load_payouts(payouts_path)

    rows_out: List[List[str]] = []
    below_count = 0

    print(f"[CHECK] Comparing payouts vs floors for period {period}")
    print(f"[CHECK] Floors from:  {floors_path}")
    print(f"[CHECK] Payouts from: {payouts_path}\n")

    header = [
        "provider_id",
        "payout_eur",
        "floor_eur",
        "status",
    ]
    rows_out.append(header)

    # 1) Provider con payout
    for pid, payout_val in sorted(payouts.items()):
        floor_val = floors.get(pid)
        if floor_val is None:
            status = "NO_FLOOR"
        else:
            if payout_val + 1e-9 < floor_val:
                status = "BELOW_FLOOR"
                below_count += 1
            else:
                status = "OK"

        rows_out.append(
            [
                pid,
                f"{payout_val:.6f}",
                "" if floor_val is None else f"{floor_val:.6f}",
                status,
            ]
        )

    # 2) Provider con floor ma nessun payout
    for pid, floor_val in floors.items():
        if pid not in payouts:
            if floor_val is None or floor_val <= 0.0:
                status = "NO_PAYOUT"
            else:
                status = "BELOW_FLOOR_NOPAYOUT"
                below_count += 1
            rows_out.append(
                [
                    pid,
                    "",
                    "" if floor_val is None else f"{floor_val:.6f}",
                    status,
                ]
            )

    with out_report_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows_out)

    print(f"[CHECK] Report written to {out_report_path}")
    print(f"[CHECK] Providers BELOW_FLOOR (incl. no-payout): {below_count}")


if __name__ == "__main__":
    main()
