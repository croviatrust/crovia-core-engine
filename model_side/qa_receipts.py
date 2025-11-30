#!/usr/bin/env python3
import json, sys, math
path = sys.argv[1]
bad_sum = bad_order = bad_neg = 0
with open(path, "r", encoding="utf-8") as f:
    for ln, line in enumerate(f, 1):
        if not line.strip(): continue
        o = json.loads(line)
        if o.get("schema")!="royalty_receipt.v1": continue
        tk = o.get("top_k") or []
        # somma
        s = sum(float(x.get("share",0)) for x in tk)
        if not (0.99 <= s <= 1.01):
            bad_sum += 1
        # non-negativi
        if any((x.get("share",0) < 0) for x in tk):
            bad_neg += 1
        # ordinamento per rank
        ranks = [x.get("rank") for x in tk if isinstance(x.get("rank"), int)]
        if ranks and ranks != sorted(ranks):
            bad_order += 1
print(f"[QA] bad_sum={bad_sum}  bad_neg={bad_neg}  bad_order={bad_order}")
