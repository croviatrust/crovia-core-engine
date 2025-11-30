#!/usr/bin/env python3
"""
qa_receipts.py – quick QA over royalty_receipt.v1 NDJSON.

Checks:
  - per-row share sum is within [0.99, 1.01]
  - no negative shares
  - rank field is monotonic increasing within top_k
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
    bad_sum, bad_neg, bad_order = qa_file(args.path)
    print(f"[QA] bad_sum={bad_sum}  bad_neg={bad_neg}  bad_order={bad_order}")


if __name__ == "__main__":
    main()
