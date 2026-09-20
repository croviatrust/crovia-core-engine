#!/usr/bin/env python3
"""Model records: one honest public page, badge and JSON per observed model.

Replaces build_model_dossiers.py and badge_model.py (2026-09-19). Those scripts
graded models A-F from wall-clock days, read a `top_100` key that no longer
exists, and advertised /badge/m/ embeds that nginx never served.

Inputs (all public files, so anyone can reproduce the pages):
  tacet/targets.json            live TACET per-target summary (observations, negatives, anchors)
  tacet/latest.json             latest epoch sheet summary (map id, epoch number)
  tacet/proofs/*.seal.json      featured level-2 proofs (link when one exists for the model)
  substrate/lacuna_candidates.json   2026 archive: observation-bounded silence per model

Outputs:
  <web>/m/<org>/<model>/index.html    the record
  <web>/m/index.html                  browsable index of every record
  <web>/badge/m/<org>/<model>.svg     grade-free badge
  <web>/badge/m/<org>/<model>.json    shields.io endpoint schema
  <data>/model_records.json           machine-readable list of every record

Records that are not regenerated are deleted, so a model never keeps a stale
page after it leaves every input. Canon: observation facts only, no grades,
silence is observation-bounded.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import sys
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Optional

WEB_ROOT = Path(os.environ.get("CROVIA_WEB_ROOT", "/var/www/crovia"))
DATA_ROOT = Path(os.environ.get("CROVIA_DATA_ROOT", "/var/www/registry/data"))
SITE = "https://croviatrust.com"
SHELL_V = "20260919g"
PREDICATE = "crovia.pred.hf-card-training-data 1.0.0"
ARCHIVE_PAUSED = "2026-06-01"

_TEST_MARKERS = ("test-", "-test", "direct-insert", "dummy", "fixture", "example/")


def slug(target_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", target_id)


def load_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def parse_ts(s: Optional[str]) -> Optional[dt.datetime]:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def short_ts(s: Optional[str]) -> str:
    t = parse_ts(s)
    return t.strftime("%Y-%m-%d %H:%M UTC") if t else "n/a"


def short_day(s: Optional[str]) -> str:
    t = parse_ts(s)
    return t.strftime("%Y-%m-%d") if t else "n/a"


def valid_target(tid: str) -> bool:
    if not tid or "/" not in tid:
        return False
    org, _, model = tid.partition("/")
    if not org or not model or "/" in model:
        return False
    low = tid.lower()
    return not any(m in low for m in _TEST_MARKERS)


# --------------------------------------------------------------------------- data

def collect_records() -> Dict[str, Dict[str, Any]]:
    records: Dict[str, Dict[str, Any]] = {}

    targets = load_json(DATA_ROOT / "tacet" / "targets.json") or {}
    latest = load_json(DATA_ROOT / "tacet" / "latest.json") or {}
    proofs_dir = DATA_ROOT / "tacet" / "proofs"
    proof_slugs = {p.name[: -len(".seal.json")] for p in proofs_dir.glob("*.seal.json")} if proofs_dir.is_dir() else set()

    for t in targets.get("targets") or []:
        tid = t.get("target_id", "")
        if not valid_target(tid):
            continue
        s = slug(tid)
        records[tid] = {
            "target_id": tid,
            "live": {
                "observations": int(t.get("observations") or 0),
                "negative": int(t.get("negative") or 0),
                "anchored": int(t.get("negative_anchored_epochs") or 0),
                "last_result": t.get("last_result"),
                "first_seen": t.get("first_seen"),
                "last_seen": t.get("last_seen"),
                "surface": t.get("last_surface"),
                "proof_url": f"{SITE}/registry/data/tacet/proofs/{s}.seal.json" if s in proof_slugs else None,
            },
            "archive": None,
        }

    lac = load_json(DATA_ROOT / "substrate" / "lacuna_candidates.json") or {}
    for c in lac.get("candidates") or []:
        tid = c.get("target_id", "")
        if not valid_target(tid):
            continue
        first, last = c.get("first_seen"), c.get("last_seen")
        if not first or not last:
            continue
        t0, t1 = parse_ts(first), parse_ts(last)
        observed_days = int(c.get("days_monitored") or (max(0, (t1 - t0).days) if t0 and t1 else 0))
        arch = {
            "first_seen": first,
            "last_seen": last,
            "observations": int(c.get("observation_count") or 0),
            "observed_days": observed_days,
            "collector": c.get("source_collector") or "autonomous_observer",
            "axiom_id": c.get("axiom_id"),
        }
        rec = records.setdefault(tid, {"target_id": tid, "live": None, "archive": None})
        rec["archive"] = arch

    meta = {
        "map_id": targets.get("map_id") or latest.get("map_id"),
        "epoch": latest.get("latest_epoch"),
        "targets_count": int(targets.get("count") or 0),
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    for r in records.values():
        r["_meta"] = meta
    return records


# --------------------------------------------------------------------------- verdicts

def live_verdict(live: Dict[str, Any]) -> Dict[str, str]:
    if live["observations"] == 0:
        return {"key": "pending", "short": "not yet observed", "color": "6c7988",
                "headline": "In the watch list, not yet observed.",
                "sentence": "This model is in the current TACET watch list but no epoch has fetched its card yet."}
    if live["last_result"] is True:
        return {"key": "found", "short": "disclosure found", "color": "3ddc84",
                "headline": "A training-data disclosure was found on the model card.",
                "sentence": "At the last check the published predicate returned true: the card names its training data."}
    return {"key": "absent", "short": f"not found \u00b7 {live['observations']} checks", "color": "1ec5ff",
            "headline": "No training-data disclosure found on the model card.",
            "sentence": "At every check so far the published predicate returned false: the card does not name its training data."}


# --------------------------------------------------------------------------- badge

def _text_w(s: str) -> int:
    return int(len(s) * 6.4) + 20


BADGE_TPL = Template("""<svg xmlns="http://www.w3.org/2000/svg" width="$tw" height="20" role="img" aria-label="$label: $msg">
  <title>$title</title>
  <linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
  <clipPath id="r"><rect width="$tw" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)"><rect width="$lw" height="20" fill="#0b1220"/><rect x="$lw" width="$rw" height="20" fill="#$color"/><rect width="$tw" height="20" fill="url(#s)"/></g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="$lcx" y="15" fill="#000" fill-opacity=".3">$label</text><text x="$lcx" y="14">$label</text>
    <text x="$rcx" y="15" fill="#000" fill-opacity=".3">$msg</text><text x="$rcx" y="14">$msg</text>
  </g>
  <metadata><crovia xmlns="https://croviatrust.com/ns/badge/v2" target="$target" kind="$kind" generated="$ts" record="$record"/></metadata>
</svg>
""")


def badge_parts(rec: Dict[str, Any]) -> Dict[str, str]:
    live, arch = rec["live"], rec["archive"]
    if rec["target_id"] == "unknown/unknown":
        return {"label": "crovia", "msg": "no record", "color": "6c7988", "kind": "none"}
    if live:
        v = live_verdict(live)
        label, msg, color, kind = "training data on card", v["short"], v["color"], "tacet-live"
    else:
        label, msg, color, kind = "crovia 2026 archive", f"silent {arch['observed_days']} observed days", "6c7988", "archive"
    return {"label": label, "msg": msg, "color": color, "kind": kind}


def badge_svg(rec: Dict[str, Any]) -> str:
    p = badge_parts(rec)
    lw, rw = _text_w(p["label"]), _text_w(p["msg"])
    return BADGE_TPL.substitute(
        tw=lw + rw, lw=lw, rw=rw, lcx=lw // 2, rcx=lw + rw // 2,
        label=html.escape(p["label"]), msg=html.escape(p["msg"]), color=p["color"],
        title=html.escape(f"Crovia \u00b7 {rec['target_id']} \u00b7 {p['label']}: {p['msg']}"),
        target=html.escape(rec["target_id"], quote=True), kind=p["kind"],
        ts=rec["_meta"]["generated_at"], record=f"{SITE}/m/{html.escape(rec['target_id'], quote=True)}/",
    )


def badge_json(rec: Dict[str, Any]) -> Dict[str, Any]:
    p = badge_parts(rec)
    return {"schemaVersion": 1, "label": p["label"], "message": p["msg"], "color": p["color"],
            "target": rec["target_id"], "kind": p["kind"], "record": f"{SITE}/m/{rec['target_id']}/",
            "generated_at": rec["_meta"]["generated_at"], "schema": "crovia.badge.v2"}


# --------------------------------------------------------------------------- page

HEAD_TPL = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>$title</title>
<meta name="description" content="$desc">
<link rel="canonical" href="$canonical">
<link rel="icon" type="image/png" href="$site/logo.png">
<link rel="alternate" type="application/json" href="$site/badge/m/$tid.json">
<meta property="og:title" content="$title">
<meta property="og:description" content="$desc">
<meta property="og:type" content="article">
<meta property="og:url" content="$canonical">
<meta property="og:image" content="$site/og-card.png?v=20260919">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="$site/og-card.png?v=20260919">
<link rel="stylesheet" href="$site/assets/crovia.css?v=20260919c">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<script type="application/ld+json">$jsonld</script>
<style>
  .mr-wrap{max-width:1040px;margin:0 auto;padding:0 24px}
  .mr-hero{padding:64px 0 26px}
  .mr-eyebrow{font:500 11px var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--accent);display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .mr-eyebrow .st{color:var(--text-faint);letter-spacing:.06em}
  .mr-eyebrow .st.live{color:#3ddc84}
  .mr-hero h1{font:700 clamp(28px,4.2vw,44px)/1.08 var(--sans);letter-spacing:-.03em;margin:14px 0 6px;word-break:break-word}
  .mr-hero h1 .org{color:var(--text-muted);font-weight:500}
  .mr-verdict{font:600 clamp(18px,2.3vw,24px)/1.3 var(--sans);color:#fff;margin:18px 0 10px;max-width:820px}
  .mr-verdict.absent{color:var(--accent)}.mr-verdict.found{color:#3ddc84}
  .mr-lead{font-size:15.5px;color:var(--text-soft);max-width:780px;line-height:1.6}
  .mr-lead a{color:var(--accent)}
  .mr-strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--border);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-top:30px}
  .mr-stat{background:var(--bg-card);padding:16px 18px}
  .mr-stat .n{font:600 24px var(--mono);color:#fff;line-height:1;letter-spacing:-.02em;word-break:break-all}
  .mr-stat .l{font:400 11px var(--mono);color:var(--text-muted);margin-top:8px;letter-spacing:.04em}
  .mr-stat .s{font:400 10px var(--mono);color:var(--text-faint);margin-top:5px}
  .mr-head{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;flex-wrap:wrap;border-bottom:1px solid var(--border);padding-bottom:12px;margin:52px 0 16px}
  .mr-head h2{font:700 22px/1.15 var(--sans);letter-spacing:-.02em}
  .mr-head .meta{font:400 11.5px var(--mono);color:var(--text-muted)}
  .mr-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
  .mr-card{background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:20px 22px}
  .mr-card .k{font:600 10px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin-bottom:10px}
  .mr-card h3{font:600 16px/1.25 var(--sans);color:#fff;margin-bottom:8px}
  .mr-card p{font-size:13.5px;color:var(--text-soft);line-height:1.55}
  .mr-card p a{color:var(--accent)}
  .mr-card pre{margin-top:12px;background:#070b12;border:1px solid var(--border);border-radius:8px;padding:12px 14px;font:12px/1.6 var(--mono);color:var(--text);overflow-x:auto;white-space:pre}
  .mr-btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
  .mr-btn{display:inline-block;font:600 12px var(--mono);letter-spacing:.04em;padding:9px 14px;border-radius:8px;border:1px solid var(--border);color:var(--text);text-decoration:none}
  .mr-btn.pri{background:var(--accent);color:#001b27;border-color:var(--accent)}
  .mr-btn:hover{border-color:var(--accent-line);color:#fff}.mr-btn.pri:hover{color:#001b27}
  .mr-list{list-style:none;padding:0;margin:0}
  .mr-list li{font-size:13.5px;color:var(--text-soft);line-height:1.55;padding:8px 0 8px 22px;position:relative;border-bottom:1px solid var(--border)}
  .mr-list li:last-child{border-bottom:0}
  .mr-list li::before{content:"\\2013";position:absolute;left:4px;color:var(--accent)}
  .mr-list b{color:#fff;font-weight:600}
  .mr-kv{width:100%;border-collapse:collapse;font-size:13px}
  .mr-kv td{padding:9px 10px;border-bottom:1px solid var(--border);vertical-align:top}
  .mr-kv td.k{font:500 10.5px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--text-faint);white-space:nowrap;width:190px}
  .mr-kv td.v{font:500 12.5px var(--mono);color:var(--text);word-break:break-all}
  .mr-kv td.v a{color:var(--accent)}
  .mr-end{margin:26px 0 72px;font-size:12.5px;color:var(--text-faint)}
  .mr-end a{color:var(--accent)}
  @media (max-width:640px){.mr-kv td.k{width:120px}}
</style>
</head>
<body>
<nav class="cv-topbar">
  <div class="cv-topbar-inner">
    <a href="$site/" class="cv-brand-link"><img src="$site/logo.png" alt="" class="cv-brand-mark"><span class="cv-brand-name">CROVIA</span></a>
    <button class="cv-nav-burger" data-cv-burger aria-label="Menu"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M3 12h18M3 18h18"/></svg></button>
    <div class="cv-nav-links" id="cv-nav-links"></div>
    <div class="cv-nav-status" id="cv-nav-status"><span class="dot"></span><span data-cv-status>connecting</span></div>
  </div>
</nav>
<main class="mr-wrap">
""")

FOOT = Template("""
</main>
<footer class="cv-foot">
  <div class="cv-foot-inner">
    <div class="cv-foot-links">
      <a href="/registry/tacet/">TACET</a>
      <a href="/registry/lacuna/">LACUNA</a>
      <a href="/registry/seal/">Seal</a>
      <a href="/registry/seal/verify/">Verify</a>
      <a href="/m/">Model records</a>
      <a href="/registry/api/">Data &amp; API</a>
      <a href="mailto:info@croviatrust.com">Contact</a>
    </div>
    <div class="cv-foot-meta">&copy; 2026 Crovia Trust · observation facts only · all observation data CC-BY-4.0</div>
  </div>
</footer>
<script src="$site/assets/crovia-shell.js?v=$shell_v" defer></script>
</body>
</html>
""")


def stat(n: Any, label: str, sub: str = "") -> str:
    return (f'<div class="mr-stat"><div class="n">{html.escape(str(n))}</div><div class="l">{html.escape(label)}</div>'
            + (f'<div class="s">{html.escape(sub)}</div>' if sub else "") + "</div>")


def kv(rows: List[tuple]) -> str:
    out = ['<table class="mr-kv">']
    for k, v in rows:
        out.append(f'<tr><td class="k">{html.escape(k)}</td><td class="v">{v}</td></tr>')
    out.append("</table>")
    return "".join(out)


def link(url: str, text: Optional[str] = None) -> str:
    return f'<a href="{html.escape(url, quote=True)}" rel="noopener">{html.escape(text or url)}</a>'


def render_record(rec: Dict[str, Any]) -> str:
    tid = rec["target_id"]
    org, _, model = tid.partition("/")
    live, arch, meta = rec["live"], rec["archive"], rec["_meta"]
    tid_e = html.escape(tid)
    tid_q = html.escape(tid, quote=True)
    canonical = f"{SITE}/m/{tid}/"
    hf_url = f"https://huggingface.co/{tid}"

    if live:
        v = live_verdict(live)
        eyebrow = 'Model record <span class="st live">\u25cf live \u00b7 TACET</span>'
        verdict_cls = v["key"]
        verdict = v["headline"]
        lead = (f"{v['sentence']} Crovia fetches the <a href=\"{html.escape(hf_url, quote=True)}\" rel=\"noopener\">Hugging Face model card</a> "
                f"of <b>{tid_e}</b> in hourly TACET epochs, runs the published predicate "
                f"<code>{PREDICATE}</code> over the exact bytes, signs the result and commits it to a sparse Merkle map that is "
                f"anchored in Bitcoin. Numbers below are observation facts, not a judgement of the model.")
        desc = (f"{tid}: training-data disclosure {v['short']} on the Hugging Face model card. "
                f"{live['observations']} signed TACET observations, {live['anchored']} confirmed in Bitcoin. Verifiable offline.")
        title = f"{tid} \u2014 training-data disclosure on the model card: {v['short'].split(' \u00b7 ')[0]} \u00b7 Crovia"
        strip = (stat(live["observations"], "signed observations", f"since {short_day(live['first_seen'])}")
                 + stat(live["negative"], "returned \u201cnot found\u201d", "predicate false")
                 + stat(live["anchored"], "epochs confirmed in Bitcoin", "only these count")
                 + stat(short_ts(live["last_seen"])[:16], "last check (UTC)", "hourly cadence")
                 + stat(meta.get("epoch") if meta.get("epoch") is not None else "\u2014", "current TACET epoch", "map: " + str(meta.get("map_id") or "").rsplit(":", 1)[-1]))
        claim_text = (f"As of {meta['generated_at']}, the Hugging Face model card of {tid} "
                      + ("contained a training-data disclosure" if v["key"] == "found" else "contained no training-data disclosure")
                      + f" according to predicate {PREDICATE}; {live['observations']} signed observations, {live['anchored']} anchored in Bitcoin.")
    else:
        eyebrow = 'Model record <span class="st">2026 archive \u00b7 read-only</span>'
        verdict_cls = "archive"
        verdict = f"Observed silent for {arch['observed_days']} days in the 2026 archive."
        lead = (f"Between {short_day(arch['first_seen'])} and {short_day(arch['last_seen'])} the first-generation collector "
                f"<code>{html.escape(arch['collector'])}</code> recorded {arch['observations']} signed observations of <b>{tid_e}</b> "
                f"without a training-data disclosure. Observation of the archive paused on {ARCHIVE_PAUSED}; the day count stops there and "
                f"does not grow. This model is not in the current TACET watch list &mdash; you can "
                f'<a href="/registry/lacuna/#request">request a witnessed certificate</a>.')
        desc = (f"{tid}: {arch['observed_days']} observation-bounded days of silence on training data in the Crovia 2026 archive "
                f"({arch['observations']} signed observations, {short_day(arch['first_seen'])} to {short_day(arch['last_seen'])}). Not in the live TACET watch list.")
        title = f"{tid} \u2014 {arch['observed_days']} observed days of silence on training data (2026 archive) \u00b7 Crovia"
        strip = (stat(arch["observed_days"], "observed days of silence", "bounded by observations")
                 + stat(arch["observations"], "signed observations", html.escape(arch["collector"]))
                 + stat(short_day(arch["first_seen"]), "first observation")
                 + stat(short_day(arch["last_seen"]), "last observation", f"archive paused {ARCHIVE_PAUSED}")
                 + stat("archive", "status", "read-only"))
        claim_text = (f"Between {short_day(arch['first_seen'])} and {short_day(arch['last_seen'])}, Crovia recorded {arch['observations']} signed observations of {tid} "
                      f"without a training-data disclosure ({arch['observed_days']} observation-bounded days). Observation paused {ARCHIVE_PAUSED}.")

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Claim", "name": f"Crovia model record for {tid}", "url": canonical,
             "datePublished": meta["generated_at"], "claimReviewed": claim_text,
             "author": {"@type": "Organization", "name": "Crovia Trust", "url": SITE},
             "about": {"@type": "SoftwareApplication", "name": tid, "url": hf_url},
             "isBasedOn": (live or {}).get("proof_url") or f"{SITE}/registry/data/tacet/latest.json",
             "license": "https://creativecommons.org/licenses/by/4.0/"},
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Registry", "item": f"{SITE}/registry/"},
                {"@type": "ListItem", "position": 2, "name": "Model records", "item": f"{SITE}/m/"},
                {"@type": "ListItem", "position": 3, "name": tid, "item": canonical}]},
        ]}, ensure_ascii=False).replace("</", "<\\/")

    parts = [HEAD_TPL.substitute(title=html.escape(title, quote=True), desc=html.escape(desc, quote=True), canonical=canonical,
                                 site=SITE, tid=tid_q, jsonld=jsonld)]
    parts.append(f"""
  <section class="mr-hero">
    <div class="mr-eyebrow">{eyebrow}</div>
    <h1><span class="org">{html.escape(org)} /</span> {html.escape(model)}</h1>
    <div class="mr-verdict {verdict_cls}">{html.escape(verdict)}</div>
    <p class="mr-lead">{lead}</p>
    <div class="mr-strip">{strip}</div>
  </section>
""")

    # ---- verify
    parts.append('<div class="mr-head"><h2>Verify it yourself</h2><div class="meta">no account \u00b7 no Crovia server in the loop</div></div><div class="mr-grid">')
    if live and live.get("proof_url"):
        purl = live["proof_url"]
        vurl = f"/registry/seal/verify/?url={html.escape(purl, quote=True).replace('&', '%26')}"
        parts.append(f"""
  <div class="mr-card"><div class="k">Level-2 silence proof</div><h3>A signed proof exists for this model</h3>
    <p>The proof wraps every negative observation of <b>{tid_e}</b> in a <a href="/registry/seal/">Crovia Seal</a>: sparse-Merkle non-inclusion for each epoch, the drand round that opened it and the OpenTimestamps receipt that closed it. Your browser checks all of it, Bitcoin anchor included.</p>
    <div class="mr-btns"><a class="mr-btn pri" href="{vurl}">Verify in your browser</a><a class="mr-btn" href="{html.escape(purl, quote=True)}">proof .seal.json</a></div>
    <pre>pip install crovia-tacet-operator crovia-seal
curl -sO {html.escape(purl)}
tacet-operator verify {html.escape(slug(tid))}.seal.json</pre>
  </div>""")
    elif live:
        parts.append(f"""
  <div class="mr-card"><div class="k">Epoch sheets</div><h3>Every observation is in the public log</h3>
    <p>Each hourly epoch sheet lists the snapshot of <b>{tid_e}</b> with its signature and its leaf in the sparse Merkle map. Featured models get a wrapped level-2 proof automatically; for any other model you can <a href="/registry/lacuna/#request">request a certificate</a> and receive the same object.</p>
    <div class="mr-btns"><a class="mr-btn pri" href="/registry/data/tacet/latest.json">latest epoch sheet</a><a class="mr-btn" href="/registry/data/tacet/targets.json">targets.json</a><a class="mr-btn" href="/registry/tacet/#verify">how to verify</a></div>
  </div>""")
    else:
        parts.append(f"""
  <div class="mr-card"><div class="k">Archive ledger</div><h3>Signed observations in the AXIOM ledger</h3>
    <p>The 2026 archive is a signed, append-only ledger sealed with Ed25519 and anchored in Bitcoin. The observations of <b>{tid_e}</b> are in it; the seal over the whole ledger verifies in your browser.</p>
    <div class="mr-btns"><a class="mr-btn pri" href="/proof.html">Verify the ledger seal</a><a class="mr-btn" href="/registry/explore/?subject={html.escape(tid.replace('/', '%2F'), quote=True)}">open in Evidence Explorer</a></div>
  </div>""")
    parts.append(f"""
  <div class="mr-card"><div class="k">What this record means</div><h3>Observation facts only</h3>
    <ul class="mr-list">
      <li><b>Surface:</b> the raw model card on Hugging Face{' (' + link(live['surface'], 'last fetched URL') + ')' if live and live.get('surface') else ''}. A disclosure published elsewhere is not seen here.</li>
      <li><b>Predicate:</b> <code>{PREDICATE}</code> &mdash; a pure function of the bytes, published with its hash. It accepts thin disclosures; it never rates quality.</li>
      <li><b>Time:</b> {'each epoch is opened by a drand round and closed by a Bitcoin block, so the window is not chosen by Crovia' if live else 'the day count is bounded by the first and last observation and stopped when observation paused'}.</li>
      <li><b>Not a grade.</b> Crovia does not rank, score or accuse. It records what was observable, signs it, and lets anyone check.</li>
    </ul>
  </div>
</div>""")

    # ---- archive section when both exist
    if live and arch:
        parts.append(f"""
<div class="mr-head"><h2>Also in the 2026 archive</h2><div class="meta">first-generation collector \u00b7 observation paused {ARCHIVE_PAUSED}</div></div>
<div class="mr-card">{kv([
    ("observed days of silence", str(arch["observed_days"]) + " (observation-bounded)"),
    ("signed observations", str(arch["observations"])),
    ("first / last observation", f"{short_ts(arch['first_seen'])} \u2192 {short_ts(arch['last_seen'])}"),
    ("collector", html.escape(arch["collector"])),
    ("axiom id", html.escape(arch["axiom_id"] or "n/a")),
])}</div>""")

    # ---- embed
    badge_svg_url = f"{SITE}/badge/m/{tid}.svg"
    badge_json_url = f"{SITE}/badge/m/{tid}.json"
    parts.append(f"""
<div class="mr-head"><h2>Embed the record</h2><div class="meta">badge regenerates hourly \u00b7 links back here</div></div>
<div class="mr-grid">
  <div class="mr-card"><div class="k">Badge</div><h3><img src="{html.escape(badge_svg_url, quote=True)}" alt="Crovia badge for {tid_q}" style="vertical-align:middle;height:20px"></h3>
    <pre>[![Crovia]({html.escape(badge_svg_url)})]({html.escape(canonical)})</pre>
    <p style="margin-top:10px">shields.io endpoint: <code>{html.escape(badge_json_url)}</code></p>
  </div>
  <div class="mr-card"><div class="k">Machine-readable</div><h3>Same facts, as data</h3>
    {kv([
        ("this model", link(f"/badge/m/{tid}.json", f"/badge/m/{tid}.json")),
        ("every model", link("/registry/data/model_records.json", "/registry/data/model_records.json")),
        ("live per-target summary", link("/registry/data/tacet/targets.json", "/registry/data/tacet/targets.json")),
        ("model card", link(hf_url, f"huggingface.co/{tid}")),
    ])}
  </div>
</div>
<p class="mr-end">Generated {html.escape(short_ts(meta['generated_at']))} from public files under <a href="/registry/data/">/registry/data/</a>. Browse <a href="/m/">all model records</a> or read <a href="/registry/tacet/">how TACET works</a>. Errors: <a href="mailto:info@croviatrust.com">info@croviatrust.com</a>.</p>
""")
    parts.append(FOOT.substitute(site=SITE, shell_v=SHELL_V))
    return "".join(parts)


# --------------------------------------------------------------------------- index page

def render_index(records: Dict[str, Dict[str, Any]], meta: Dict[str, Any]) -> str:
    live = [r for r in records.values() if r["live"]]
    arch_only = [r for r in records.values() if not r["live"]]
    n_absent = sum(1 for r in live if live_verdict(r["live"])["key"] == "absent")
    n_found = sum(1 for r in live if live_verdict(r["live"])["key"] == "found")
    n_anch = sum(1 for r in live if r["live"]["anchored"] > 0)

    def row(r: Dict[str, Any]) -> str:
        tid = r["target_id"]
        if r["live"]:
            v = live_verdict(r["live"])
            state, detail = v["short"], f"{r['live']['anchored']} anchored"
            kind = "live"
        else:
            state, detail, kind = f"silent {r['archive']['observed_days']} observed days", f"{r['archive']['observations']} obs.", "archive"
        return (f'<tr data-k="{kind}" data-t="{html.escape(tid.lower(), quote=True)}"><td class="f"><a href="/m/{html.escape(tid, quote=True)}/">{html.escape(tid)}</a></td>'
                f'<td class="d">{html.escape(state)}</td><td class="t">{html.escape(detail)}</td></tr>')

    live_rows = "".join(row(r) for r in sorted(live, key=lambda r: (-r["live"]["anchored"], r["target_id"].lower())))
    arch_rows = "".join(row(r) for r in sorted(arch_only, key=lambda r: (-r["archive"]["observed_days"], r["target_id"].lower())))
    title = "Model records \u2014 training-data disclosure, model by model \u00b7 Crovia"
    desc = (f"{len(live)} models in the live TACET watch list and {len(arch_only)} more in the 2026 archive. "
            "Per model: signed observations of the Hugging Face card, Bitcoin-anchored epochs, verifiable proofs. No grades.")
    jsonld = json.dumps({"@context": "https://schema.org", "@type": "CollectionPage", "name": "Crovia model records", "url": f"{SITE}/m/",
                         "description": desc, "isPartOf": {"@type": "WebSite", "name": "Crovia", "url": SITE}}, ensure_ascii=False)
    head = HEAD_TPL.substitute(title=html.escape(title, quote=True), desc=html.escape(desc, quote=True), canonical=f"{SITE}/m/",
                               site=SITE, tid="_index", jsonld=jsonld)
    head = head.replace(f'<link rel="alternate" type="application/json" href="{SITE}/badge/m/_index.json">',
                        f'<link rel="alternate" type="application/json" href="{SITE}/registry/data/model_records.json">')
    body = f"""
  <section class="mr-hero">
    <div class="mr-eyebrow">Model records <span class="st live">\u25cf {len(live)} live</span> <span class="st">{len(arch_only)} archive</span></div>
    <h1>Training-data disclosure, <span style="color:var(--accent)">model by model</span>.</h1>
    <p class="mr-lead">One page per observed model: what the Hugging Face card said about its training data at every signed check, how many of those checks are confirmed in Bitcoin, and how to verify it without trusting Crovia. Models in the current <a href="/registry/tacet/">TACET</a> watch list are observed hourly; the rest are read-only records from the 2026 archive.</p>
    <div class="mr-strip">{stat(len(live), "models observed live", "TACET watch list")}{stat(n_absent, "no disclosure found", "at the last check")}{stat(n_found, "disclosure found", "predicate true")}{stat(n_anch, "with Bitcoin-anchored epochs")}{stat(len(arch_only), "archive-only records", f"paused {ARCHIVE_PAUSED}")}</div>
  </section>
  <div class="mr-head"><h2>Find a model</h2><div class="meta">filters both tables \u00b7 <a href="/registry/data/model_records.json" style="color:var(--accent)">model_records.json</a></div></div>
  <input id="q" type="search" placeholder="org/model \u2026" autocomplete="off" style="width:100%;max-width:520px;background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:12px 14px;font:500 14px var(--mono);color:#fff;outline:none">
  <div class="mr-head"><h2>Live \u00b7 TACET watch list</h2><div class="meta">sorted by anchored epochs</div></div>
  <table class="mr-kv" id="t-live"><thead><tr><td class="k">model</td><td class="k">training data on card</td><td class="k">anchored epochs</td></tr></thead><tbody>{live_rows}</tbody></table>
  <div class="mr-head"><h2>2026 archive \u00b7 read-only</h2><div class="meta">observation-bounded days \u00b7 observation paused {ARCHIVE_PAUSED}</div></div>
  <table class="mr-kv" id="t-arch"><thead><tr><td class="k">model</td><td class="k">archive record</td><td class="k">observations</td></tr></thead><tbody>{arch_rows}</tbody></table>
  <p class="mr-end">Generated {html.escape(short_ts(meta['generated_at']))}. A model missing here was never observed by Crovia; <a href="/registry/lacuna/#request">request a witness</a> to add it.</p>
<script>
(function(){{var q=document.getElementById('q');var rows=document.querySelectorAll('tr[data-t]');q.addEventListener('input',function(){{var v=q.value.trim().toLowerCase();rows.forEach(function(r){{r.style.display=(!v||r.getAttribute('data-t').indexOf(v)>=0)?'':'none';}});}});}})();
</script>
"""
    return head + body + FOOT.substitute(site=SITE, shell_v=SHELL_V)


# --------------------------------------------------------------------------- main

def write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.read_text() == content:
            return
    except OSError:
        pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    tmp.replace(path)


def prune(root: Path, keep: set, suffix: str) -> int:
    removed = 0
    if not root.is_dir():
        return 0
    for p in root.rglob(f"*{suffix}"):
        if p.name.startswith("_") or p.parent == root and suffix == "index.html":
            continue
        if p not in keep:
            try:
                p.unlink()
                removed += 1
                if suffix == "index.html" and not any(p.parent.iterdir()):
                    p.parent.rmdir()
            except OSError:
                pass
    return removed


def main() -> int:
    records = collect_records()
    if not records:
        print("no records: inputs missing?", file=sys.stderr)
        return 1
    meta = next(iter(records.values()))["_meta"]
    m_root, b_root = WEB_ROOT / "m", WEB_ROOT / "badge" / "m"
    kept_pages, kept_badges = set(), set()

    for tid, rec in records.items():
        org, _, model = tid.partition("/")
        page = m_root / org / model / "index.html"
        write_if_changed(page, render_record(rec))
        kept_pages.add(page)
        svg, js = b_root / org / f"{model}.svg", b_root / org / f"{model}.json"
        write_if_changed(svg, badge_svg(rec))
        write_if_changed(js, json.dumps(badge_json(rec), ensure_ascii=False) + "\n")
        kept_badges.update({svg, js})

    write_if_changed(m_root / "index.html", render_index(records, meta))
    write_if_changed(b_root / "_unknown.svg", badge_svg({"target_id": "unknown/unknown", "live": None, "archive": None, "_meta": meta}))

    out = {"schema": "crovia.model_records.v1", "generated_at": meta["generated_at"], "map_id": meta.get("map_id"),
           "predicate": PREDICATE, "archive_paused": ARCHIVE_PAUSED, "count": len(records),
           "records": [dict({k: v for k, v in r.items() if k != "_meta"}, url=f"{SITE}/m/{r['target_id']}/")
                       for r in sorted(records.values(), key=lambda r: r["target_id"].lower())]}
    write_if_changed(DATA_ROOT / "model_records.json", json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")

    pruned_pages = prune(m_root, kept_pages, "index.html")
    pruned_badges = prune(b_root, kept_badges, ".svg") + prune(b_root, kept_badges, ".json")
    n_live = sum(1 for r in records.values() if r["live"])
    print(f"model records: {len(records)} written ({n_live} live, {len(records) - n_live} archive-only); "
          f"pruned {pruned_pages} stale pages, {pruned_badges} stale badges")
    return 0


if __name__ == "__main__":
    sys.exit(main())
