#!/usr/bin/env python3
# make_payout_charts.py: genera 2 PNG + HHI/Gini e li append al README_PAYOUT_<YYYY-MM>.md

import argparse, csv, os, json
import matplotlib.pyplot as plt

def read_payouts(csv_path):
    rows=[]
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append({"provider_id": r["provider_id"], "amount": float(r["amount"])})
    rows.sort(key=lambda x: -x["amount"])
    return rows

def top10_chart(rows, out_png):
    xs=[r["provider_id"] for r in rows[:10]]
    ys=[r["amount"] for r in rows[:10]]
    plt.figure(figsize=(10,5))
    plt.bar(xs, ys)
    plt.xticks(rotation=30, ha="right")
    plt.ylabel("Amount")
    plt.title("Top-10 providers by payout")
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()

def cumulative_chart(rows, out_png):
    amounts=[r["amount"] for r in rows]
    s=sum(amounts) or 1.0
    props=[a/s for a in amounts]
    cum=[0.0]
    for p in props: cum.append(cum[-1]+p)
    xs=list(range(len(cum)))
    plt.figure(figsize=(10,5))
    plt.plot(xs, cum)
    plt.xlabel("Providers (sorted)")
    plt.ylabel("Cumulative share")
    plt.title("Cumulative payout curve")
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()

def hhi_gini(rows):
    amounts=[r["amount"] for r in rows]
    s=sum(amounts) or 1.0
    shares=[a/s for a in amounts]
    hhi=sum(p*p for p in shares)
    # Gini discreto
    n=len(shares) or 1
    cum=0.0
    for i,a in enumerate(sorted(amounts)):
        cum += (i+1)*a
    gini= (2*cum)/(n*sum(amounts)) - (n+1)/n if sum(amounts)>0 else 0.0
    return hhi, gini

def append_to_readme(readme, period, top_png, cum_png, hhi, gini):
    block=f"""
## Charts ({period})

![Top10]({top_png})
![Cumulative]({cum_png})

**Concentration**
- HHI: {hhi:.4f}
- Gini: {gini:.4f}
"""
    with open(readme, "a", encoding="utf-8") as f:
        f.write("\n"+block+"\n")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--period", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--readme", required=True)
    args=ap.parse_args()

    rows=read_payouts(args.csv)
    os.makedirs("charts", exist_ok=True)
    top_png=f"charts/payout_top10_{args.period}.png"
    cum_png=f"charts/payout_cumulative_{args.period}.png"
    top10_chart(rows, top_png)
    cumulative_chart(rows, cum_png)
    hhi,gini=hhi_gini(rows)
    append_to_readme(args.readme, args.period, top_png, cum_png, hhi, gini)
    print("[CHARTS] ok:", top_png, cum_png, f"HHI={hhi:.4f} Gini={gini:.4f}")

if __name__=="__main__":
    main()
