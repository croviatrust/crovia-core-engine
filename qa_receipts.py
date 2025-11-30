#!/usr/bin/env python3
"""
qa_receipts.py – quick QA over royalty_receipt.v1 NDJSON.

Checks (per royalty_receipt.v1 row with a non-empty top_k):
  - per-row share sum is within [0.99, 1.01]
  - no negative shares
  - rank field is monotonically non-decreasing within top_k
"""

import argparse
import json
import sys
from typing import Tuple


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Quick QA on royalty_receipt.v1 NDJSON logs."
    )
    p.add_argument(
        "path",
        help="Input NDJSON file containing royalty_receipt.v1 records.",
    )
    return p.parse_args()


def qa_file(path: str) -> Tuple[int, int, int]:
    """
    Scan the NDJSON file and return:
      bad_sum   = rows whose share sum is outside [0.99, 1.01]
      bad_neg   = rows with at least one negative share
      bad_order = rows where rank is not monotonically increasing
    """
    bad_sum = bad_order = bad_neg = 0

    with open(path, "r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            if not line.strip():
                continue

            try:
                o = json.loads(line)
            except Exception:
                # If a line is not valid JSON, we ignore it for QA,
                # since this script focuses on well-formed royalty_receipt.v1.
                continue

            if o.get("schema") != "royalty_receipt.v1":
                continue

            top_k = o.get("top_k") or []
            if not top_k:
                continue

            # 1) Sum of shares
            s = 0.0
            for x in top_k:
                try:
                    s += float(x.get("share", 0.0))
                except (TypeError, ValueError):
                    # Non-numeric shares are treated as 0 for this quick QA
                    continue
            if not (0.99 <= s <= 1.01):
                bad_sum += 1

            # 2) Non-negative shares
            if any((x.get("share", 0) < 0) for x in top_k):
                bad_neg += 1

            # 3) Rank ordering
            ranks = [x.get("rank") for x in top_k if isinstance(x.get("rank"), int)]
            if ranks and ranks != sorted(ranks):
                bad_order += 1

    return bad_sum, bad_neg, bad_order


def main() -> None:
    args = parse_args()
    path = args.path

    print(f"[QA] reading receipts from: {path}")
    bad_sum, bad_neg, bad_order = qa_file(path)
    print(f"[QA] bad_sum={bad_sum}  bad_neg={bad_neg}  bad_order={bad_order}")

    if bad_sum == 0 and bad_neg == 0 and bad_order == 0:
        print("[QA] OK – all royalty_receipt.v1 rows passed basic checks.")
    else:
        print(
            "[QA] WARN – some rows failed QA checks "
            "(see bad_sum / bad_neg / bad_order counters above)."
        )


if __name__ == "__main__":
    main()
