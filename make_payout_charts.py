#!/usr/bin/env python3
# make_payout_charts.py
# Generate 2 PNG charts + HHI/Gini metrics and append them to README_PAYOUT_<YYYY-MM>.md

import argparse
import csv
import os

import matplotlib.pyplot as plt


def read_payouts(csv_path: str):
    """Read payouts CSV and return a list of {provider_id, amount}, sorted by amount desc."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            try:
                amount = float(r["amount"])
            except (KeyError, ValueError):
                continue
            rows.append({"provider_id": r.get("provider_id", ""), "amount": amount})
    rows.sort(key=lambda x: -x["amount"])
    return rows


def top10_chart(rows, out_png: str) -> None:
    """Bar chart for top-10 providers by payout amount."""
    if not rows:
        return

    xs = [r["provider_id"] for r in rows[:10]]
    ys = [r["amount"] for r in rows[:10]]

    plt.figure(figsize=(10, 5))
    plt.bar(xs, ys)
    plt.xticks(rotation=30, ha="right")
    plt.ylabel("Amount (EUR)")
    plt.title("Top-10 providers by payout")
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()


def cumulative_chart(rows, out_png: str) -> None:
    """Cumulative payout curve (Lorenz-style)."""
    if not rows:
        return

    amounts = [r["amount"] for r in rows]
    total = sum(amounts) or 1.0
    props = [a / total for a in amounts]

    cum = [0.0]
    for p in props:
        cum.append(cum[-1] + p)

    xs = list(range(len(cum)))

    plt.figure(figsize=(10, 5))
    plt.plot(xs, cum)
    plt.xlabel("Providers (sorted by payout)")
    plt.ylabel("Cumulative share of payouts")
    plt.title("Cumulative payout curve")
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()


def hhi_gini(rows):
    """Compute HHI and Gini index from payout amounts."""
    amounts = [r["amount"] for r in rows]
    total = sum(amounts)
    if total <= 0:
        return 0.0, 0.0

    shares = [a / total for a in amounts]
    hhi = sum(p * p for p in shares)

    n = len(shares) or 1
    cum = 0.0
    for i, a in enumerate(sorted(amounts)):
        cum += (i + 1) * a
    gini = (2 * cum) / (n * total) - (n + 1) / n if total > 0 else 0.0

    return hhi, gini


def interpret_concentration(hhi: float, gini: float) -> str:
    """
    Provide a short textual label for concentration based on HHI and Gini.

    Rough thresholds (not legal advice):
      - HHI < 0.15  -> low concentration
      - 0.15–0.25   -> moderate concentration
      - > 0.25      -> high concentration
    """
    if hhi < 0.15:
        level = "low concentration"
    elif hhi < 0.25:
        level = "moderate concentration"
    else:
        level = "high concentration"

    return f"{level} (HHI={hhi:.4f}, Gini={gini:.4f})"


def append_to_readme(readme: str, period: str, top_png: str, cum_png: str, hhi: float, gini: float) -> None:
    """Append charts and concentration metrics to the payout README."""
    concentration_hint = interpret_concentration(hhi, gini)
    block = f"""
## Charts ({period})

![Top10]({top_png})
![Cumulative]({cum_png})

**Concentration metrics**

- HHI: {hhi:.4f}
- Gini: {gini:.4f}
- Interpretation: {concentration_hint}
"""
    # Append (create file if not present)
    with open(readme, "a", encoding="utf-8") as f:
        f.write("\n" + block + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate payout charts (top-10 and cumulative) and append HHI/Gini to README."
    )
    ap.add_argument("--period", required=True, help="Settlement period (YYYY-MM)")
    ap.add_argument("--csv", required=True, help="Input payouts CSV file")
    ap.add_argument("--readme", required=True, help="README file to append charts/metrics to")
    args = ap.parse_args()

    rows = read_payouts(args.csv)
    if not rows:
        print("[CHARTS] No payout rows found; nothing to plot.")
        return

    os.makedirs("charts", exist_ok=True)
    top_png = f"charts/payout_top10_{args.period}.png"
    cum_png = f"charts/payout_cumulative_{args.period}.png"

    top10_chart(rows, top_png)
    cumulative_chart(rows, cum_png)

    hhi, gini = hhi_gini(rows)
    append_to_readme(args.readme, args.period, top_png, cum_png, hhi, gini)

    print("[CHARTS] ok:", top_png, cum_png, f"HHI={hhi:.4f} Gini={gini:.4f}")


if __name__ == "__main__":
    main()


