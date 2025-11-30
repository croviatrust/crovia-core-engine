import argparse
import csv
import json
from dataclasses import dataclass, field
from typing import Dict, Any, List, Set


@dataclass
class ProviderStats:
    """Aggregati di trust per un provider."""
    appear_topk: int = 0           # volte nel top_k
    appear_top1: int = 0           # volte rank == 1
    total_share: float = 0.0       # somma share attribuite
    outputs_with_share: int = 0    # output in cui appare almeno una volta
    conf_pos: int = 0              # volte con share_ci95_low > 0
    low_conf_top1: int = 0         # volte top1 con low_confidence=True
    dp_eps_top1: Set[float] = field(default_factory=set)
    max_share: float = 0.0         # share massima in un singolo output

    # per sapere se in un certo output è già stato visto (per outputs_with_share)
    last_output_id: str = ""


def iter_ndjson(path: str):
    """Iteratore streaming su un file NDJSON."""
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception as e:
                print(f"[WARN] linea {lineno}: JSON non valido, skip ({e})")
                continue
            yield lineno, obj


def process_file(path: str, min_appear: int):
    providers: Dict[str, ProviderStats] = {}
    total_outputs = 0
    all_dp_eps: Set[float] = set()

    print(f"[trust] lettura file: {path}")

    for lineno, obj in iter_ndjson(path):
        if obj.get("schema") != "royalty_receipt.v1":
            continue

        top_k = obj.get("top_k") or []
        if not top_k:
            continue

        total_outputs += 1
        output_id = str(obj.get("output_id", f"lineno-{lineno}"))

        epsilon_dp = obj.get("epsilon_dp", None)
        low_conf = bool(obj.get("low_confidence", False))

        eps_val = None
        if epsilon_dp is not None:
            try:
                eps_val = float(epsilon_dp)
                all_dp_eps.add(eps_val)
            except Exception:
                eps_val = None

        # unifica per provider dentro allo stesso output (multi-shard -> singolo provider)
        share_by_provider: Dict[str, float] = {}

        for alloc in top_k:
            if not isinstance(alloc, dict):
                continue
            pid = alloc.get("provider_id")
            if not pid:
                continue
            share = alloc.get("share")
            if share is None:
                continue
            try:
                s = float(share)
            except Exception:
                print(f"[WARN] linea {lineno}: share non numerica {share!r} per {pid!r}")
                continue
            if s < 0:
                print(f"[WARN] linea {lineno}: share negativa {s} per {pid!r}")
                continue

            share_by_provider[pid] = share_by_provider.get(pid, 0.0) + s

        if not share_by_provider:
            continue

        # aggiorna aggregati per provider
        for alloc in top_k:
            if not isinstance(alloc, dict):
                continue
            pid = alloc.get("provider_id")
            if not pid:
                continue
            rank = alloc.get("rank")
            ci_low = alloc.get("share_ci95_low")

            st = providers.get(pid)
            if st is None:
                st = ProviderStats()
                providers[pid] = st

            # apparizioni nel top_k (conteggio allocazioni, utile come metrica raw)
            st.appear_topk += 1

            # top1 & low_conf & dp_eps_top1
            if isinstance(rank, int) and rank == 1:
                st.appear_top1 += 1
                if low_conf:
                    st.low_conf_top1 += 1
                if eps_val is not None:
                    st.dp_eps_top1.add(eps_val)

            # conf_pos: share_ci95_low > 0 (a livello di allocazione)
            if isinstance(ci_low, (int, float)) and ci_low is not None and ci_low > 0:
                st.conf_pos += 1

        # somma share unificate per provider e conta una sola volta l'output
        for pid, ssum in share_by_provider.items():
            st = providers[pid]
            st.total_share += ssum
            if ssum > st.max_share:
                st.max_share = ssum
            if st.last_output_id != output_id:   # garantisce 1 conteggio per output
                st.outputs_with_share += 1
                st.last_output_id = output_id

    # filtro su numero di output distinti in cui compaiono
    filtered = {
        pid: st for pid, st in providers.items()
        if st.outputs_with_share >= min_appear
    }

    print(f"[trust] output totali considerati: {total_outputs}")
    print(f"[trust] provider totali (prima del filtro): {len(providers)}")
    print(f"[trust] provider dopo filtro min_appear={min_appear}: {len(filtered)}")

    return filtered, total_outputs, all_dp_eps


def finalize_scores(
    providers: Dict[str, ProviderStats],
    total_outputs: int,
    all_dp_eps: Set[float],
):
    rows: List[Dict[str, Any]] = []
    total = float(total_outputs or 1)
    have_dp = len(all_dp_eps) >= 2

    total_share_overall = sum(st.total_share for st in providers.values()) or 1.0

    for provider_id, st in providers.items():
        appear_alloc = st.appear_topk                 # allocazioni nel top_k (multi-shard)
        appear_outputs = st.outputs_with_share        # output distinti in cui compare
        top1 = st.appear_top1
        conf_pos = st.conf_pos
        low_conf_top1 = st.low_conf_top1

        top1_rate = top1 / total
        topk_rate = appear_outputs / total            # <-- fix: per output, non per allocazione
        den = float(appear_outputs) if appear_outputs > 0 else 1.0
        conf_rate = conf_pos / den                    # <-- consigliato: per output
        low_conf_rate = (low_conf_top1 / float(top1)) if top1 > 0 else 0.0

        trust_core = 0.5 * top1_rate + 0.3 * topk_rate + 0.2 * conf_rate
        penalty_low_conf = max(0.0, 1.0 - low_conf_rate)

        if have_dp:
            dp_span = len(st.dp_eps_top1)
            if dp_span >= 2:
                dp_robust = 1.05
            elif dp_span == 1:
                dp_robust = 0.95
            else:
                dp_robust = 1.0
        else:
            dp_robust = 1.0

        trust = trust_core * penalty_low_conf * dp_robust
        risk = 0.5 * low_conf_rate + 0.5 * (1.0 - conf_rate)

        priority_raw = (0.4 * trust + 0.2 * conf_rate + 0.2 * topk_rate - 0.2 * risk)
        priority_score = max(0.0, min(1.0, priority_raw))

        global_share_fraction = st.total_share / total_share_overall

        rows.append({
            "provider_id": provider_id,
            "trust": trust,
            "risk": risk,
            "priority_score": priority_score,
            "top1_rate": top1_rate,
            "topk_rate": topk_rate,
            "conf_pos_rate": conf_rate,
            "low_conf_rate": low_conf_rate,
            "dp_eps_top1": sorted(st.dp_eps_top1),
            "n_appear_topk": appear_alloc,
            "n_appear_top1": top1,
            "n_conf_pos": conf_pos,
            "n_low_conf_top1": low_conf_top1,
            "total_share": st.total_share,
            "outputs_with_share": appear_outputs,
            "avg_share_per_output": (st.total_share / float(max(1, st.outputs_with_share))
            ),
            "global_share_fraction": global_share_fraction,
            "max_share_single_output": st.max_share,
        })

    rows.sort(key=lambda r: r["trust"], reverse=True)

    n = len(rows)
    if n > 0:
        for idx, r in enumerate(rows):
            frac = (idx + 1) / n
            r["priority_band"] = "HIGH" if frac <= 0.20 else ("MED" if frac <= 0.50 else "LOW")

    return rows



def write_provider_csv(rows: List[Dict[str, Any]], path: str) -> None:
    """Scrive un CSV con tutte le metriche per provider."""
    if not rows:
        print("[trust] Nessun provider, CSV non scritto.")
        return

    print(f"[trust] scrittura CSV provider: {path}")
    fieldnames = [
        "provider_id",
        "trust",
        "risk",
        "priority_score",
        "priority_band",
        "top1_rate",
        "topk_rate",
        "conf_pos_rate",
        "low_conf_rate",
        "n_appear_topk",
        "n_appear_top1",
        "n_conf_pos",
        "n_low_conf_top1",
        "total_share",
        "outputs_with_share",
        "avg_share_per_output",
        "global_share_fraction",
        "max_share_single_output",
        "dp_eps_top1",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            row = r.copy()
            # formattiamo alcune colonne come stringhe numeriche
            row["trust"] = f"{row['trust']:.6f}"
            row["risk"] = f"{row['risk']:.6f}"
            row["priority_score"] = f"{row['priority_score']:.6f}"
            row["top1_rate"] = f"{row['top1_rate']:.6f}"
            row["topk_rate"] = f"{row['topk_rate']:.6f}"
            row["conf_pos_rate"] = f"{row['conf_pos_rate']:.6f}"
            row["low_conf_rate"] = f"{row['low_conf_rate']:.6f}"
            row["total_share"] = f"{row['total_share']:.6f}"
            row["avg_share_per_output"] = f"{row['avg_share_per_output']:.6f}"
            row["global_share_fraction"] = f"{row['global_share_fraction']:.6f}"
            row["max_share_single_output"] = f"{row['max_share_single_output']:.6f}"
            row["dp_eps_top1"] = ";".join(str(x) for x in row["dp_eps_top1"])
            w.writerow(row)

    print("[trust] CSV provider scritto.")


def write_report(
    rows: List[Dict[str, Any]],
    total_outputs: int,
    path: str,
    top_n: int,
) -> None:
    """Scrive un report markdown sintetico."""
    print(f"[trust] scrittura report: {path}")
    lines: List[str] = []
    lines.append("# CROVIA – Trust & Priority summary")
    lines.append("")
    lines.append(f"- Output totali considerati: {total_outputs}")
    lines.append(f"- Provider totali (dopo filtro): {len(rows)}")
    lines.append("")

    if not rows or total_outputs <= 0:
        lines.append("Nessun dato sufficiente per calcolare il trust.")
    else:
        lines.append(f"## Top {min(top_n, len(rows))} provider per trust")
        lines.append("")
        lines.append("| Rank | Provider | Trust | Risk | Priority | Band | Top1% | TopK% | Conf+% | LowConf% | Global share % |")
        lines.append("|------|----------|-------|------|----------|------|-------|-------|--------|----------|----------------|")

        def fmt_pct(x: float) -> str:
            return f"{x*100:5.1f}%"

        for rank, r in enumerate(rows[:top_n], start=1):
            lines.append(
                "| {rank} | {pid} | {trust:.3f} | {risk:.3f} | {prior:.3f} | {band} | "
                "{top1} | {topk} | {conf} | {lowc} | {gshare:6.2f}% |".format(
                    rank=rank,
                    pid=r["provider_id"],
                    trust=r["trust"],
                    risk=r["risk"],
                    prior=r["priority_score"],
                    band=r["priority_band"],
                    top1=fmt_pct(r["top1_rate"]),
                    topk=fmt_pct(r["topk_rate"]),
                    conf=fmt_pct(r["conf_pos_rate"]),
                    lowc=fmt_pct(r["low_conf_rate"]),
                    gshare=r["global_share_fraction"] * 100.0,
                )
            )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("[trust] Report scritto.")


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Aggregatore di trust & priority per CROVIA "
            "su ricevute royalty_receipt.v1"
        )
    )
    p.add_argument(
        "--input",
        "-i",
        dest="input",
        required=False,
        default="data/royalty_receipts.ndjson",
        help="File NDJSON di input (schema=royalty_receipt.v1, una riga per ricevuta).",
    )
    p.add_argument(
        "--min-appear",
        dest="min_appear",
        type=int,
        default=5,
        help="Minimo numero di apparizioni nel top_k per includere il provider.",
    )
    p.add_argument(
        "--top-n",
        dest="top_n",
        type=int,
        default=50,
        help="Numero massimo di provider da mostrare nel report.",
    )
    p.add_argument(
        "--out-provider",
        dest="out_provider_csv",
        required=False,
        default="data/trust_providers.csv",
        help="Percorso CSV output con metriche di trust per provider.",
    )
    p.add_argument(
        "--out-report",
        dest="out_report",
        required=False,
        default="trust_summary.md",
        help="Percorso report markdown sintetico.",
    )

    args = p.parse_args()

    providers, total_outputs, all_dp_eps = process_file(
        path=args.input,
        min_appear=args.min_appear,
    )

    rows = finalize_scores(
        providers=providers,
        total_outputs=total_outputs,
        all_dp_eps=all_dp_eps,
    )

    if not rows:
        print("Nessun provider con apparizioni sufficienti.")
        return

    write_provider_csv(rows, args.out_provider_csv)
    write_report(rows, total_outputs, args.out_report, args.top_n)

    # stampa riassunto a console (stile vecchio script)
    print(
        f"# CROVIA trust summary  |  total_outputs={total_outputs}  "
        f"|  providers={len(rows)}  (min_appear={args.min_appear})"
    )
    print(
        f"{'rank':>4}  {'provider':<20}  {'trust':>7}  {'risk':>7}  "
        f"{'prior':>7}  {'band':>5}  {'top1':>6}  {'topk':>6}  "
        f"{'conf+':>6}  {'lowc':>6}"
    )

    def fmt_pct_short(x: float) -> str:
        return f"{x*100:5.1f}%"

    for idx, r in enumerate(rows[: args.top_n], start=1):
        print(
            f"{idx:4d}  {r['provider_id']:<20}  "
            f"{r['trust']:7.3f}  {r['risk']:7.3f}  "
            f"{r['priority_score']:7.3f}  {r['priority_band']:<5}  "
            f"{fmt_pct_short(r['top1_rate'])}  {fmt_pct_short(r['topk_rate'])}  "
            f"{fmt_pct_short(r['conf_pos_rate'])}  {fmt_pct_short(r['low_conf_rate'])}"
        )


if __name__ == "__main__":
    main()
