#!/usr/bin/env python3
"""
CROVIA Global Ranking Generator
=================================
Builds global_ranking.json from compliance reports + lineage_graph.json.
Outputs:
  - /var/www/registry/data/global_ranking.json  (public, stripped)
  - /opt/crovia/hf_datasets/.../global_ranking.json  (HF dataset copy)

Run daily after compliance generation (Step 1).
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

COMP_DIR   = Path("/var/www/registry/data/compliance")
LINEAGE    = Path("/var/www/registry/data/lineage_graph.json")
OUT_PUBLIC = Path("/var/www/registry/data/global_ranking.json")
OUT_HF     = Path("/opt/crovia/hf_datasets/global-ai-training-omissions/global_ranking.json")

SEV_ORDER  = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3, "EXCELLENT": 4, "unknown": 5}

def load_lineage_index():
    """Build model_id → {org, downloads, severity} from lineage graph."""
    idx = {}
    if not LINEAGE.exists():
        return idx
    try:
        d = json.loads(LINEAGE.read_text())
        for n in d.get("nodes", []):
            if n.get("type") == "model":
                mid = n.get("id", "")
                idx[mid] = {
                    "org": n.get("org", mid.split("/")[0] if "/" in mid else "unknown"),
                    "downloads": n.get("downloads", 0) or 0,
                    "severity_lineage": n.get("severity", "unknown"),
                }
    except Exception as e:
        print(f"[WARN] lineage load failed: {e}", file=sys.stderr)
    return idx

def build_ranking():
    lineage = load_lineage_index()

    reports = []
    comp_files = [f for f in COMP_DIR.iterdir() if f.suffix == ".json" and f.name != "index.json"]
    print(f"[RANKING] Loading {len(comp_files)} compliance reports...", flush=True)

    for fpath in comp_files:
        try:
            d = json.loads(fpath.read_text())
            model_id = d.get("model_id", "")
            if not model_id:
                continue
            s = d.get("summary", {})
            score = s.get("overall_score_pct", 0) or 0
            severity = s.get("severity_label", "unknown")
            present = s.get("present", 0)
            total   = s.get("total_nec_elements", 20)
            absent  = s.get("absent", 0)
            top_gaps = [g.get("nec_id", g) if isinstance(g, dict) else str(g)
                        for g in (d.get("top_gaps") or [])[:5]]
            jur_scores = d.get("jurisdiction_scores", {})
            gen_at = d.get("generated_at", "")

            lin = lineage.get(model_id, {})
            org = lin.get("org") or (model_id.split("/")[0] if "/" in model_id else "unknown")

            reports.append({
                "model_id":    model_id,
                "org":         org,
                "score":       round(score, 1),
                "severity":    severity,
                "present":     present,
                "absent":      absent,
                "total_nec":   total,
                "top_gaps":    top_gaps,
                "downloads":   lin.get("downloads", 0),
                "jur_scores":  jur_scores,
                "generated_at": gen_at,
            })
        except Exception as e:
            print(f"[WARN] skip {fpath.name}: {e}", file=sys.stderr)

    # Sort: score desc, then severity asc, then downloads desc
    reports.sort(key=lambda r: (
        -r["score"],
        SEV_ORDER.get(r["severity"], 5),
        -r["downloads"],
    ))
    for i, r in enumerate(reports):
        r["rank"] = i + 1

    # Org aggregates
    org_map = {}
    for r in reports:
        org = r["org"]
        if org not in org_map:
            org_map[org] = {"org": org, "models": 0, "score_sum": 0.0,
                            "sev": {}, "downloads": 0}
        o = org_map[org]
        o["models"]    += 1
        o["score_sum"] += r["score"]
        o["sev"][r["severity"]] = o["sev"].get(r["severity"], 0) + 1
        o["downloads"] += r["downloads"]

    org_ranking = []
    for o in org_map.values():
        avg = round(o["score_sum"] / o["models"], 1) if o["models"] else 0
        worst = min(o["sev"].keys(), key=lambda s: SEV_ORDER.get(s, 5))
        org_ranking.append({
            "org":          o["org"],
            "models":       o["models"],
            "avg_score":    avg,
            "worst_severity": worst,
            "sev_breakdown": o["sev"],
            "total_downloads": o["downloads"],
        })
    org_ranking.sort(key=lambda o: (-o["avg_score"], SEV_ORDER.get(o["worst_severity"], 5)))
    for i, o in enumerate(org_ranking):
        o["rank"] = i + 1

    # Global stats
    scores = [r["score"] for r in reports]
    sev_global = {}
    for r in reports:
        sev_global[r["severity"]] = sev_global.get(r["severity"], 0) + 1

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    output = {
        "schema":        "crovia.global_ranking.v2",
        "generated_at":  now,
        "total_models":  len(reports),
        "total_orgs":    len(org_ranking),
        "methodology_note": (
            "Scores computed by ComplianceMapper v2.0 (corrected Feb 24 2026). "
            "v1 had a case-sensitivity bug inflating scores; v2 uses word-boundary regex matching. "
            "TPA oracle updated to v1.1.0 (corrected Feb 25 2026): "
            "section detection now uses flexible heading regex (h1-h4) and fetches full README text. "
            "All compliance reports regenerated with v2 mapper. "
            "See https://registry.croviatrust.com for public correction notice."
        ),
        "stats": {
            "avg_score":        round(sum(scores) / len(scores), 1) if scores else 0,
            "median_score":     round(sorted(scores)[len(scores)//2], 1) if scores else 0,
            "zero_score":       sum(1 for s in scores if s == 0),
            "perfect_score":    sum(1 for s in scores if s >= 95),
            "severity_breakdown": sev_global,
        },
        "org_ranking":   org_ranking,
        "model_ranking": reports,
    }

    # Write public (strip recommendations/jur_scores to keep size reasonable)
    public = dict(output)
    public["model_ranking"] = [
        {k: v for k, v in r.items() if k != "jur_scores"}
        for r in reports
    ]

    OUT_PUBLIC.write_text(json.dumps(public, ensure_ascii=False))
    print(f"[RANKING] Written {OUT_PUBLIC}  ({OUT_PUBLIC.stat().st_size//1024}KB)", flush=True)

    OUT_HF.write_text(json.dumps(public, ensure_ascii=False))
    print(f"[RANKING] Written {OUT_HF}  ({OUT_HF.stat().st_size//1024}KB)", flush=True)

    # Keep ranking.html in sync with ranking/index.html
    ranking_html = Path("/var/www/registry/ranking.html")
    ranking_idx  = Path("/var/www/registry/ranking/index.html")
    if ranking_idx.exists() and ranking_html.exists():
        import shutil
        shutil.copy2(ranking_idx, ranking_html)
        print(f"[RANKING] Synced ranking.html", flush=True)

    print(f"[RANKING] Done: {len(reports)} models, {len(org_ranking)} orgs, avg={public['stats']['avg_score']}%", flush=True)
    return public

if __name__ == "__main__":
    build_ranking()
