#!/usr/bin/env python3
# payouts_from_royalties.py
# Converte royalty_receipt.v1 (NDJSON) in payout mensile (payouts.v1 + CSV)
# Policy ex-ante: exclusions, cap top1/top3; opzionale: reconcile dopo soglia minima
# Requisiti: solo stdlib; usa schema.py per il nome degli schemi (opzionale)

import argparse, csv, json, math, os, sys
from collections import defaultdict, Counter
from datetime import datetime
from typing import Dict, Any, Iterable, Tuple, List, Optional

ROYALTY_SCHEMA = "royalty_receipt.v1"
PAYOUTS_SCHEMA = "payouts.v1"
TOL_SHARE_SUM = 0.02  # tolleranza su somma share per singola riga
EPS = 1e-12

def parse_iso(ts: str) -> Optional[datetime]:
    try:
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return datetime.fromisoformat(ts)
    except Exception:
        return None

def same_period(ts: str, year: int, month: int) -> bool:
    dt = parse_iso(ts) if isinstance(ts, str) else None
    return bool(dt and dt.year == year and dt.month == month)

def iter_ndjson(path: str) -> Iterable[Tuple[int, Dict[str, Any]]]:
    with open(path, "r", encoding="utf-8-sig") as f:
        for lineno, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                yield lineno, json.loads(s)
            except Exception as e:
                yield lineno, {"__parse_error__": str(e), "__raw__": s}

def normalize_weights(w: Dict[str, float]) -> Dict[str, float]:
    tot = sum(v for v in w.values() if v > 0)
    if tot <= 0:
        return {k: 0.0 for k in w}
    return {k: (v / tot if v > 0 else 0.0) for k, v in w.items()}

def apply_exclusions(w: Dict[str, float], excl: set, policies: Dict[str, List[str]]) -> Dict[str, float]:
    for p in excl:
        if p in w and w[p] > 0:
            w[p] = 0.0
            policies[p].append("excluded")
    return normalize_weights(w)

def apply_caps(w: Dict[str, float], cap_top1: Optional[float], cap_top3: Optional[float],
               policies: Dict[str, List[str]]) -> Dict[str, float]:
    # Applica caps congelando i capped e redistribuendo l'eccesso sugli altri pro-rata
    if not w:
        return w.copy()
    w = w.copy()
    capped = set()

    def redistribute(excess_from: Dict[str, float]):
        nonlocal w
        # Rimuovi l'eccesso dagli indicati e redistribuisci sugli altri non capped
        for k, ex in excess_from.items():
            w[k] -= ex
        free = {k: v for k, v in w.items() if k not in capped and v > 0}
        tot_free = sum(free.values())
        if tot_free <= 0:
            # se nessuno libero, rinormalizza su tutti >0 (edge-case)
            pos = {k: v for k, v in w.items() if v > 0}
            tot_pos = sum(pos.values())
            if tot_pos > 0:
                for k in pos:
                    w[k] = pos[k] / tot_pos
            return
        # ridistribuzione pro-rata sui free
        inc_total = sum(excess_from.values())
        for k in free:
            w[k] += (w[k] / tot_free) * inc_total

    # loop max 10 volte per sicurezza
    for _ in range(10):
        changed = False

        # Cap top1
        if cap_top1 is not None:
            # identifica top1 corrente
            top1 = max(w.items(), key=lambda kv: kv[1])[0]
            if w[top1] > cap_top1 + EPS:
                ex = w[top1] - cap_top1
                capped.add(top1)
                policies[top1].append(f"cap_top1_{cap_top1}")
                redistribute({top1: ex})
                changed = True

        # Cap top3
        if cap_top3 is not None and len(w) >= 3:
            top3 = sorted(w.items(), key=lambda kv: kv[1], reverse=True)[:3]
            sum_top3 = sum(v for _, v in top3)
            if sum_top3 > cap_top3 + EPS:
                excess = sum_top3 - cap_top3
                # congela i tre e ridistribuisci l'eccesso pro-rata tra i non top3
                for k, _ in top3:
                    capped.add(k)
                    if f"cap_top3_{cap_top3}" not in policies[k]:
                        policies[k].append(f"cap_top3_{cap_top3}")
                # ridistribuzione: togliamo pro-rata ai tre
                top3_total = sum(v for _, v in top3)
                ex_map = {k: (w[k] / top3_total) * excess for k, _ in top3}
                redistribute(ex_map)
                changed = True

        if not changed:
            break

        # rinormalizza leggero per drift numerico
        w = normalize_weights(w)

    return w

def round_amounts(weights: Dict[str, float], eur_total: float) -> Dict[str, float]:
    # Arrotonda per provider a 2 decimali e riconcilia al centesimo
    raw = {p: weights[p] * eur_total for p in weights}
    rounded = {p: round(raw[p] + 1e-12, 2) for p in raw}  # bias minimo
    diff = round(eur_total - sum(rounded.values()), 2)
    if abs(diff) >= 0.01 - 1e-9:
        # aggiusta il provider con importo massimo in valore assoluto
        if rounded:
            p_adj = max(rounded.items(), key=lambda kv: kv[1])[0]
            rounded[p_adj] = round(rounded[p_adj] + diff, 2)
    return rounded

def main():
    ap = argparse.ArgumentParser(description="CROVIA payouts da royalty_receipt.v1 (mensile)")
    ap.add_argument("--input", "-i", required=True, help="File NDJSON royalty_receipt.v1")
    ap.add_argument("--period", required=True, help="Periodo YYYY-MM")
    ap.add_argument("--eur-total", type=float, required=True, help="Budget totale (EUR) da ripartire")
    ap.add_argument("--currency", default="EUR", help="Valuta (default EUR)")
    ap.add_argument("--min-amount", type=float, default=0.0, help="Soglia minima pagabile (default 0)")
    ap.add_argument("--cap-top1", type=float, default=None, help="Tetto share top1 (es. 0.55)")
    ap.add_argument("--cap-top3", type=float, default=None, help="Tetto share somma top3 (es. 0.80)")
    ap.add_argument("--exclusions", default=None, help="CSV con provider_id da escludere (una colonna)")
    ap.add_argument("--out-ndjson", required=True, help="Output NDJSON payouts.v1")
    ap.add_argument("--out-csv", required=True, help="Output CSV payout")
    ap.add_argument("--out-log", default=None, help="Log testuale")
    ap.add_argument("--out-assumptions", default="assumptions.json", help="Parametri usati")
    ap.add_argument("--out-rollover", default=None, help="CSV provider sotto soglia (se min-amount>0)")
    ap.add_argument("--reconcile-after-min", action="store_true",
                    help="Se attivo, rialloca dopo aver azzerato i sotto-soglia per avere Σ=eur_total")
    args = ap.parse_args()

    # Parse periodo
    try:
        year, month = map(int, args.period.split("-"))
        assert 1 <= month <= 12
    except Exception:
        # Per il sandbox web non facciamo fallire tutto:
        # se il periodo non è valido, usiamo un default sicuro.
        print("[WARN] --period non valido, uso '2025-11' per la demo sandbox", file=sys.stderr)
        args.period = "2025-11"
        year, month = 2025, 11

    if not os.path.exists(args.input):
        print(f"[FATAL] Input NDJSON non trovato: {args.input}", file=sys.stderr)
        sys.exit(2)

    excl = set()
    if args.exclusions:
        try:
            with open(args.exclusions, "r", encoding="utf-8") as fex:
                for row in csv.reader(fex):
                    if row and row[0].strip():
                        excl.add(row[0].strip())
        except Exception as e:
            print(f"[WARN] Esclusioni non caricate: {e}", file=sys.stderr)

    # Aggregazione share per provider nel periodo
    S: Dict[str, float] = defaultdict(float)
    total_receipts = 0
    skipped_bad_sum = 0
    tk_dist = Counter()

    for lineno, rec in iter_ndjson(args.input):
        if "__parse_error__" in rec:
            continue
        if rec.get("schema") != ROYALTY_SCHEMA:
            continue
        ts = rec.get("timestamp")
        if not same_period(ts, year, month):
            continue

        topk = rec.get("top_k")
        if not isinstance(topk, list) or not topk:
            continue

        # somma share per riga e normalizzazione "morbida"
        s = 0.0
        valid_entries = []
        for a in topk:
            sh = a.get("share")
            pid = a.get("provider_id")
            sid = a.get("shard_id")
            if isinstance(sh, (int, float)) and sh >= 0 and isinstance(pid, str) and isinstance(sid, str):
                s += float(sh)
                valid_entries.append((pid, float(sh)))
        if not math.isfinite(s) or s <= 0:
            continue
        if abs(s - 1.0) > TOL_SHARE_SUM:
            skipped_bad_sum += 1
            continue  # scarta la riga fuori tolleranza (preferibile per payout)
        # normalizza a 1.0
        for pid, sh in valid_entries:
            S[pid] += (sh / s)
        total_receipts += 1
        tk_dist[len(valid_entries)] += 1

    if total_receipts == 0 or sum(S.values()) <= 0:
        print("[PAYOUT] Nessuna ricevuta valida nel periodo o share totali nulle.", file=sys.stderr)
        # Scrivi file vuoti di struttura minima
        os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)
        with open(args.out_csv, "w", newline="", encoding="utf-8") as fc:
            w = csv.writer(fc); w.writerow(["provider_id","period","currency","gross_revenue","share_agg","amount","policies_applied"])
        with open(args.out_ndjson, "w", encoding="utf-8") as fn:
            pass
        sys.exit(0)

    # Pesi iniziali per provider
    w = normalize_weights(S)

    # Policy tracking
    policies_applied: Dict[str, List[str]] = defaultdict(list)

    # Esclusioni
    if excl:
        w = apply_exclusions(w, excl, policies_applied)

    # Cap top1/top3
    if args.cap_top1 is not None or args.cap_top3 is not None:
        w = apply_caps(w, args.cap_top1, args.cap_top3, policies_applied)

    # Arrotonda importi e riconcilia Σ=eur_total
    amounts = round_amounts(w, args.eur_total)

    # Soglia minima
    rollover_rows: List[Tuple[str, float]] = []
    if args.min_amount > 0:
        removed_total = 0.0
        for p in list(amounts.keys()):
            if amounts[p] > 0 and amounts[p] < args.min_amount:
                rollover_rows.append((p, amounts[p]))
                amounts[p] = 0.0
                policies_applied[p].append("min_amount")
        removed_total = sum(v for _, v in rollover_rows)

        if args.reconcile_after_min and removed_total > 0:
            # rialloca pro-rata sui provider rimasti con amount>0
            survivors = {k: v for k, v in amounts.items() if v > 0}
            tot_surv = sum(survivors.values())
            if tot_surv > 0:
                for k in survivors:
                    amounts[k] = round(amounts[k] + (survivors[k] / tot_surv) * removed_total, 2)
                # riconcilia un ultimo centesimo
                diff = round(args.eur_total - sum(amounts.values()), 2)
                if abs(diff) >= 0.01 - 1e-9:
                    p_adj = max(amounts.items(), key=lambda kv: kv[1])[0]
                    amounts[p_adj] = round(amounts[p_adj] + diff, 2)

    # Scritture output
    os.makedirs(os.path.dirname(args.out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.out_ndjson) or ".", exist_ok=True)

    # CSV umano
    with open(args.out_csv, "w", newline="", encoding="utf-8") as fc:
        wcsv = csv.writer(fc)
        wcsv.writerow(["provider_id","period","currency","gross_revenue","share_agg","amount","policies_applied"])
        for p in sorted(amounts.keys(), key=lambda k: (-amounts[k], k)):
            wcsv.writerow([
                p, args.period, args.currency,
                f"{args.eur_total:.2f}",
                f"{normalize_weights(S).get(p,0.0):.6f}",
                f"{amounts[p]:.2f}",
                ",".join(policies_applied[p]) if policies_applied[p] else ""
            ])

    # NDJSON payouts.v1
    with open(args.out_ndjson, "w", encoding="utf-8") as fn:
        for p in sorted(amounts.keys(), key=lambda k: (-amounts[k], k)):
            rec = {
                "schema": PAYOUTS_SCHEMA,
                "provider_id": p,
                "period": args.period,
                "currency": args.currency,
                "amount": round(amounts[p], 2),
                "share_agg": round(normalize_weights(S).get(p, 0.0), 8),
                "gross_revenue": round(args.eur_total, 2),
                "policies_applied": policies_applied[p],
            }
            fn.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Rollover CSV (se richiesto)
    if args.out_rollover and rollover_rows:
        os.makedirs(os.path.dirname(args.out_rollover) or ".", exist_ok=True)
        with open(args.out_rollover, "w", newline="", encoding="utf-8") as fr:
            wro = csv.writer(fr)
            wro.writerow(["provider_id","amount"])
            for p, amt in sorted(rollover_rows, key=lambda x: -x[1]):
                wro.writerow([p, f"{amt:.2f}"])

    # Assumptions.json
    with open(args.out_assumptions, "w", encoding="utf-8") as fa:
        json.dump({
            "period": args.period,
            "eur_total": args.eur_total,
            "currency": args.currency,
            "min_amount": args.min_amount,
            "cap_top1": args.cap_top1,
            "cap_top3": args.cap_top3,
            "exclusions": sorted(list(excl)),
            "reconcile_after_min": bool(args.reconcile_after_min)
        }, fa, ensure_ascii=False, indent=2)

    # Log
    if args.out_log:
        os.makedirs(os.path.dirname(args.out_log) or ".", exist_ok=True)
        with open(args.out_log, "w", encoding="utf-8") as flog:
            flog.write(f"[PAYOUT] period={args.period} eur_total={args.eur_total:.2f} currency={args.currency}\n")
            flog.write(f"receipts_period={total_receipts} skipped_bad_sum={skipped_bad_sum}\n")
            flog.write(f"providers={len(S)} topk_dist={dict(tk_dist)}\n")
            flog.write(f"sum_amount={sum(amounts.values()):.2f}\n")
            if args.min_amount > 0:
                roll_sum = sum(a for _, a in rollover_rows)
                flog.write(f"rollover_count={len(rollover_rows)} rollover_sum={roll_sum:.2f}\n")
            if not args.reconcile_after_min and args.min_amount > 0:
                delta = args.eur_total - sum(amounts.values())
                flog.write(f"delta_vs_eur_total_after_min={delta:.2f} (non riallocato per policy)\n")

    print("[PAYOUT] Done.")

if __name__ == "__main__":
    main()
