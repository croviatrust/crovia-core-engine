#!/usr/bin/env python3
"""Weekly Silence Report: the shareable face of TACET, built only from published files.

Replaces the retired "Transparency Index" daily card (/card/, /index/, grades), which ranked labs with
letter grades the observations could not support. This report states counts and durations that every
reader can recompute from the files it links: epoch sheets, proofs, anchors.

Outputs (WEB_ROOT = /var/www/crovia):
    /report/<YYYY-Www>/index.html      the week's report (regenerated daily until the week closes)
    /report/<YYYY-Www>.png              1200x630 Open Graph card for that week
    /report/latest.png                  same card, stable URL
    /report/index.html                  latest report + archive
    /report/report.json                 machine-readable facts for the current week
    /feed.xml                           RSS 2.0, one item per week (the legacy feed URL, new content)

Run daily (cron 07:20 UTC) after the hourly TACET epoch has closed.
"""
from __future__ import annotations

import datetime as dt
import glob
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

WEB_ROOT = Path(os.environ.get("CROVIA_WEB_ROOT", "/var/www/crovia"))
DATA_ROOT = Path(os.environ.get("CROVIA_DATA_ROOT", "/var/www/registry/data"))
SITE = "https://croviatrust.com"
SHELL_V = "20260919g"
KEEP_WEEKS = 104


# ----------------------------------------------------------------------------- data

def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def parse_ts(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except ValueError:
        return None


def week_bounds(day: dt.date) -> tuple[dt.datetime, dt.datetime, str]:
    monday = day - dt.timedelta(days=day.weekday())
    start = dt.datetime(monday.year, monday.month, monday.day, tzinfo=dt.timezone.utc)
    end = start + dt.timedelta(days=7)
    iso = monday.isocalendar()
    return start, end, f"{iso[0]}-W{iso[1]:02d}"


def fmt_int(n: int) -> str:
    return f"{n:,}"


def short_ts(s: str | None) -> str:
    t = parse_ts(s)
    return t.strftime("%Y-%m-%d %H:%MZ") if t else "—"


def collect(now: dt.datetime) -> dict[str, Any]:
    start, end, label = week_bounds(now.date())
    tacet = DATA_ROOT / "tacet"
    index = load(tacet / "index.json", {})
    targets = load(tacet / "targets.json", {})
    proofs = load(tacet / "proofs" / "index.json", {})
    latest = load(tacet / "latest.json", {})
    anchors = load(DATA_ROOT / "substrate" / "ots_anchors.json", {})

    epochs = [e for e in index.get("epochs", []) if isinstance(e, dict)]
    closed = [e for e in epochs if e.get("closed") not in (None, "pending")]
    in_week = [e for e in closed if (t := parse_ts(e.get("epoch_end"))) and start <= t < end]
    anchored_week = [e for e in in_week if e.get("block_height")]
    heights = sorted(int(e["block_height"]) for e in anchored_week)

    tlist = [t for t in targets.get("targets", []) if isinstance(t, dict)]
    observed_week = [t for t in tlist if (ts := parse_ts(t.get("last_seen"))) and start <= ts < end]
    negative_week_targets = [t for t in observed_week if t.get("last_result") is False]

    plist = [p for p in proofs.get("proofs", []) if isinstance(p, dict)]
    for p in plist:
        try:
            p["_days"] = float(p.get("silence_days") or 0)
        except (TypeError, ValueError):
            p["_days"] = 0.0
    plist.sort(key=lambda p: p["_days"], reverse=True)
    new_proofs_week = [p for p in plist if (ts := parse_ts(p.get("observed_to"))) and start <= ts < end]

    return {
        "week": label,
        "week_start": start.strftime("%Y-%m-%d"),
        "week_end_exclusive": end.strftime("%Y-%m-%d"),
        "closed_week": now >= end,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "epochs_week": len(in_week),
        "epochs_anchored_week": len(anchored_week),
        "block_range": [heights[0], heights[-1]] if heights else None,
        "snapshots_week": sum(int(e.get("snapshots") or 0) for e in in_week),
        "negative_week": sum(int(e.get("negative") or 0) for e in in_week),
        "targets_observed_week": len(observed_week),
        "targets_negative_week": len(negative_week_targets),
        "proofs_total": len(plist),
        "proofs_new_week": len(new_proofs_week),
        "top_proofs": [
            {"target_id": p.get("target_id"), "silence_days": p.get("silence_days"), "observed_from": p.get("observed_from"),
             "observed_to": p.get("observed_to"), "observed_epochs": p.get("observed_epochs"), "url": p.get("url"), "seal_id": p.get("seal_id")}
            for p in plist[:8]
        ],
        "totals": {
            "epochs": int(latest.get("epochs") or len(closed)),
            "epochs_anchored": int(latest.get("anchored_epochs") or 0),
            "negative_snapshots": int(latest.get("negative_snapshots_total") or 0),
            "snapshots": int(latest.get("snapshots_total") or 0),
            "targets": int(targets.get("count") or len(tlist)),
            "map_size": int(latest.get("map_size") or 0),
            "bitcoin_anchors_confirmed": int(anchors.get("bitcoin_confirmed") or 0),
        },
        "first_epoch_start": min((e.get("epoch_start") for e in closed if e.get("epoch_start")), default=None),
        "latest_epoch": latest.get("latest_epoch"),
        "map_id": latest.get("map_id") or index.get("map_id"),
    }


def headline(f: dict[str, Any]) -> str:
    top = f["top_proofs"][0] if f["top_proofs"] else None
    parts = [f"{fmt_int(f['targets_observed_week'])} models observed across {fmt_int(f['epochs_week'])} hourly epochs"]
    if f["epochs_anchored_week"]:
        parts.append(f"{fmt_int(f['epochs_anchored_week'])} anchored in Bitcoin")
    parts.append(f"{fmt_int(f['proofs_total'])} signed silence proofs")
    s = "; ".join(parts) + "."
    if top:
        s += f" Longest verifiable silence: {top['silence_days']} days ({top['target_id']})."
    return s


# ----------------------------------------------------------------------------- card (PIL)

def font(size: int, weight: str = "Regular"):
    from PIL import ImageFont
    candidates = [
        f"/usr/share/fonts/opentype/inter/Inter-{weight}.otf",
        f"/usr/share/fonts/truetype/inter/Inter-{weight}.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if weight in ("Bold", "SemiBold") else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def mono(size: int):
    from PIL import ImageFont
    for c in ("/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Medium.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"):
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def render_card(f: dict[str, Any], out: Path) -> None:
    from PIL import Image, ImageDraw
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(im)
    accent, dim, white = (30, 197, 255), (108, 121, 136), (255, 255, 255)
    # vertical fade from deep navy to black, then a hairline of accent at the very top
    for y in range(300):
        k = 1 - y / 300
        d.line((0, y, W, y), fill=(int(7 * k), int(18 * k), int(28 * k)))
    d.line((0, 0, W, 0), fill=accent, width=3)
    d.text((64, 52), "CROVIA  ·  SILENCE REPORT  ·  " + f["week"].upper(), font=mono(20), fill=accent)
    d.text((64, 100), fmt_int(f["targets_observed_week"]), font=font(128, "Bold"), fill=white)
    d.text((64, 250), "models observed this week, hour by hour", font=font(38, "Medium"), fill=(217, 228, 238))
    line2 = f"{fmt_int(f['epochs_week'])} epochs  ·  {fmt_int(f['epochs_anchored_week'])} anchored in Bitcoin  ·  {fmt_int(f['proofs_total'])} signed silence proofs"
    d.text((64, 312), line2, font=font(30, "Regular"), fill=dim)
    y = 392
    d.line((64, y, W - 64, y), fill=(30, 60, 80), width=1)
    top = f["top_proofs"][0] if f["top_proofs"] else None
    if top:
        d.text((64, y + 26), "LONGEST VERIFIABLE SILENCE", font=mono(18), fill=accent)
        d.text((64, y + 56), f"{top['silence_days']} days", font=font(60, "Bold"), fill=white)
        tid = str(top["target_id"])
        d.text((64 + 24 + d.textlength(f"{top['silence_days']} days", font=font(60, "Bold")), y + 82),
               tid if len(tid) < 42 else tid[:40] + "…", font=font(32, "Medium"), fill=(217, 228, 238))
        d.text((64, y + 132), f"observed {short_ts(top['observed_from'])} → {short_ts(top['observed_to'])} · {top.get('observed_epochs') or '?'} epochs, none disclosed", font=font(22), fill=dim)
    d.text((64, H - 52), "croviatrust.com/report   ·   observation facts only   ·   every number links to a signed file", font=mono(17), fill=dim)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "PNG", optimize=True)


# ----------------------------------------------------------------------------- html

def shell_head(title: str, desc: str, url: str, image: str, jsonld: dict[str, Any], extra_css: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{url}">
<link rel="icon" type="image/png" href="{SITE}/logo.png">
<link rel="alternate" type="application/rss+xml" title="Crovia Silence Report" href="{SITE}/feed.xml">
<meta property="og:type" content="article">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{image}">
<link rel="stylesheet" href="{SITE}/assets/crovia.css?v=20260919c">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False).replace('</', '<\\/')}</script>
<style>
  .rp-wrap{{max-width:1040px;margin:0 auto;padding:0 24px}}
  .rp-hero{{padding:64px 0 28px}}
  .rp-eyebrow{{font:500 11px var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--accent)}}
  .rp-hero h1{{font:700 clamp(30px,4.4vw,48px)/1.08 var(--sans);letter-spacing:-.03em;color:#fff;margin:14px 0 14px}}
  .rp-lead{{font-size:16.5px;color:var(--text-soft);line-height:1.6;max-width:820px}}
  .rp-lead a{{color:var(--accent)}}
  .rp-strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:1px;background:var(--border);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-top:28px}}
  .rp-stat{{background:var(--bg-card);padding:18px 18px;text-decoration:none;display:block}}
  .rp-stat .n{{font:700 30px var(--sans);color:#fff;letter-spacing:-.03em;line-height:1}}
  .rp-stat .l{{font:400 11.5px var(--mono);color:var(--text-muted);margin-top:8px}}
  a.rp-stat:hover{{background:var(--bg-card-hi)}}
  .rp-head{{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;flex-wrap:wrap;border-bottom:1px solid var(--border);padding-bottom:12px;margin:52px 0 16px}}
  .rp-head h2{{font:700 22px/1.15 var(--sans);letter-spacing:-.02em}}
  .rp-head .meta{{font:400 11.5px var(--mono);color:var(--text-muted)}}
  .rp-head .meta a{{color:var(--accent)}}
  table.rp{{width:100%;border-collapse:collapse;font-size:13.5px}}
  table.rp th{{text-align:left;font:500 10.5px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--text-faint);padding:8px 10px;border-bottom:1px solid var(--border)}}
  table.rp td{{padding:10px;border-bottom:1px solid var(--border);vertical-align:top}}
  table.rp td.m{{font:500 12.5px var(--mono)}}
  table.rp a{{color:var(--accent)}}
  .rp-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}}
  .rp-card{{background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:20px 22px}}
  .rp-card .k{{font:600 10px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin-bottom:10px}}
  .rp-card h3{{font:600 16px/1.25 var(--sans);color:#fff;margin-bottom:8px}}
  .rp-card p{{font-size:13.5px;color:var(--text-soft);line-height:1.55}}
  .rp-card p a{{color:var(--accent)}}
  .rp-card pre{{margin-top:12px;background:#070b12;border:1px solid var(--border);border-radius:8px;padding:12px 14px;font:12px/1.6 var(--mono);color:var(--text);overflow-x:auto;white-space:pre-wrap;word-break:break-all}}
  .rp-cardimg{{width:100%;border:1px solid var(--border);border-radius:12px;display:block;margin-top:24px}}
  .rp-end{{margin:28px 0 72px;font-size:12.5px;color:var(--text-faint)}}
  .rp-end a{{color:var(--accent)}}
  .rp-pill{{display:inline-block;font:500 11px var(--mono);border:1px solid var(--border);border-radius:999px;padding:3px 10px;color:var(--text-muted);margin-left:8px;vertical-align:middle}}
  {extra_css}
</style>
</head>
<body>
<nav class="cv-topbar">
  <div class="cv-topbar-inner">
    <a href="{SITE}/" class="cv-brand-link"><img src="{SITE}/logo.png" alt="" class="cv-brand-mark"><span class="cv-brand-name">CROVIA</span></a>
    <button class="cv-nav-burger" data-cv-burger aria-label="Menu"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M3 12h18M3 18h18"/></svg></button>
    <div class="cv-nav-links" id="cv-nav-links"></div>
    <div class="cv-nav-status" id="cv-nav-status"><span class="dot"></span><span data-cv-status>connecting</span></div>
  </div>
</nav>
"""


FOOT = f"""<footer class="cv-foot">
  <div class="cv-foot-inner">
    <div class="cv-foot-links">
      <a href="/registry/tacet/">TACET</a>
      <a href="/registry/lacuna/">LACUNA</a>
      <a href="/registry/seal/">Seal</a>
      <a href="/registry/seal/verify/">Verify</a>
      <a href="/m/">Model records</a>
      <a href="/report/">Silence Report</a>
      <a href="/registry/api/">Data &amp; API</a>
      <a href="mailto:info@croviatrust.com">Contact</a>
    </div>
    <div class="cv-foot-meta">&copy; 2026 Crovia Trust · observation facts only · all observation data CC-BY-4.0</div>
  </div>
</footer>
<script src="{SITE}/assets/crovia-shell.js?v={SHELL_V}" defer></script>
</body>
</html>
"""


def proof_rows(f: dict[str, Any]) -> str:
    rows = []
    for p in f["top_proofs"]:
        tid = str(p["target_id"])
        purl = p.get("url") or ""
        vurl = f"/registry/seal/verify/?url={html.escape(purl, quote=True).replace('&', '%26')}"
        rows.append(
            f'<tr><td class="m"><a href="/m/{html.escape(tid)}/">{html.escape(tid)}</a></td>'
            f'<td class="m">{html.escape(str(p["silence_days"]))} d</td>'
            f'<td class="m">{html.escape(short_ts(p["observed_from"]))} → {html.escape(short_ts(p["observed_to"]))}</td>'
            f'<td class="m">{p.get("observed_epochs") or "?"}</td>'
            f'<td class="m"><a href="{html.escape(purl)}">.seal.json</a> · <a href="{vurl}">verify</a></td></tr>')
    return "".join(rows)


def render_week(f: dict[str, Any]) -> str:
    wk = f["week"]
    url = f"{SITE}/report/{wk}/"
    img = f"{SITE}/report/{wk}.png?v={f['generated_at'][:13].replace('T', '').replace('-', '')}"
    title = f"Silence Report {wk}: {fmt_int(f['targets_observed_week'])} models observed, {fmt_int(f['proofs_total'])} signed silence proofs"
    desc = headline(f)
    status = "closed week" if f["closed_week"] else "week in progress, updated daily"
    br = f["block_range"]
    block_txt = f"blocks {fmt_int(br[0])}–{fmt_int(br[1])}" if br and br[0] != br[1] else (f"block {fmt_int(br[0])}" if br else "anchors pending confirmation")
    jsonld = {
        "@context": "https://schema.org", "@type": "Report", "name": title, "headline": desc, "url": url,
        "datePublished": f["week_start"], "dateModified": f["generated_at"], "inLanguage": "en",
        "author": {"@type": "Organization", "name": "Crovia Trust", "url": SITE},
        "publisher": {"@type": "Organization", "name": "Crovia Trust", "url": SITE, "logo": {"@type": "ImageObject", "url": f"{SITE}/logo.png"}},
        "image": img, "license": "https://creativecommons.org/licenses/by/4.0/",
        "about": {"@type": "Dataset", "name": "TACET observation map", "url": f"{SITE}/registry/data/tacet/index.json"},
        "isBasedOn": [f"{SITE}/registry/data/tacet/index.json", f"{SITE}/registry/data/tacet/targets.json", f"{SITE}/registry/data/tacet/proofs/index.json"],
    }
    top = f["top_proofs"][0] if f["top_proofs"] else None
    top_card = ""
    if top:
        top_card = f"""
    <div class="rp-card"><div class="k">Longest verifiable silence</div><h3>{html.escape(str(top['silence_days']))} days · {html.escape(str(top['target_id']))}</h3>
      <p>Observed from {html.escape(short_ts(top['observed_from']))} to {html.escape(short_ts(top['observed_to']))} across {top.get('observed_epochs') or '?'} hourly epochs; in none of them did a training-data disclosure matching the <a href="/registry/lacuna/#predicate">published predicate</a> appear on the model's monitored surfaces. The duration is bounded by the observations, not by the calendar. <a href="/m/{html.escape(str(top['target_id']))}/">Model record</a> · <a href="{html.escape(top.get('url') or '')}">proof</a>.</p></div>"""
    body = f"""<main class="rp-wrap">
  <section class="rp-hero">
    <div class="rp-eyebrow">Silence Report · {html.escape(wk)} · {html.escape(f['week_start'])} → {html.escape(f['week_end_exclusive'])} <span class="rp-pill">{status}</span></div>
    <h1>{fmt_int(f['targets_observed_week'])} models observed, hour by hour. {fmt_int(f['proofs_total'])} carry a signed proof that nothing was disclosed.</h1>
    <p class="rp-lead">{html.escape(desc)} Every figure below is computed from files you can download and re-check: the <a href="/registry/data/tacet/index.json">epoch index</a>, the <a href="/registry/data/tacet/targets.json">target list</a>, the <a href="/registry/data/tacet/proofs/index.json">proof index</a>. Crovia records what was observed and what was not; it does not grade, rank or accuse.</p>
    <div class="rp-strip">
      <a class="rp-stat" href="/registry/data/tacet/index.json"><div class="n">{fmt_int(f['epochs_week'])}</div><div class="l">hourly epochs closed this week</div></a>
      <a class="rp-stat" href="/registry/data/tacet/index.json"><div class="n">{fmt_int(f['epochs_anchored_week'])}</div><div class="l">anchored in Bitcoin · {html.escape(block_txt)}</div></a>
      <a class="rp-stat" href="/registry/data/tacet/targets.json"><div class="n">{fmt_int(f['targets_observed_week'])}</div><div class="l">models observed · {fmt_int(f['targets_negative_week'])} with no disclosure found</div></a>
      <a class="rp-stat" href="/registry/data/tacet/index.json"><div class="n">{fmt_int(f['negative_week'])}</div><div class="l">negative snapshots of {fmt_int(f['snapshots_week'])} taken</div></a>
      <a class="rp-stat" href="/registry/data/tacet/proofs/index.json"><div class="n">{fmt_int(f['proofs_total'])}</div><div class="l">signed silence proofs · {fmt_int(f['proofs_new_week'])} extended this week</div></a>
    </div>
    <img class="rp-cardimg" src="/report/{html.escape(wk)}.png?v={html.escape(f['generated_at'][:13])}" alt="Silence Report card {html.escape(wk)}" width="1200" height="630">
  </section>

  <div class="rp-head"><h2>Longest verifiable silences</h2><div class="meta">from <a href="/registry/data/tacet/proofs/index.json">proofs/index.json</a> · each proof verifies in the browser, Bitcoin anchor included</div></div>
  <table class="rp"><thead><tr><th>model</th><th>silence</th><th>observed window</th><th>epochs</th><th>proof</th></tr></thead><tbody>{proof_rows(f)}</tbody></table>

  <div class="rp-head"><h2>What these numbers mean</h2><div class="meta">definitions in <a href="https://github.com/croviatrust/countersign/blob/main/CANON.md">CANON.md</a></div></div>
  <div class="rp-grid">
    {top_card}
    <div class="rp-card"><div class="k">Silence</div><h3>Observation-bounded, never wall-clock</h3><p>A model is "silent" for the hours in which Crovia looked at its public surfaces and found no disclosure matching the predicate. Hours not observed do not count. The figure is a lower bound on what was checked, not a statement about what the provider did elsewhere.</p></div>
    <div class="rp-card"><div class="k">Epoch</div><h3>One hour, one sparse Merkle root</h3><p>Every hour the operator commits the set of negative observations to a depth-256 sparse Merkle tree, signs the sheet, opens it with a drand round and closes it with an OpenTimestamps receipt. <a href="/registry/tacet/">How TACET works</a>.</p></div>
    <div class="rp-card"><div class="k">Proof</div><h3>A Crovia Seal you can verify offline</h3><p>Each proof wraps the non-inclusion paths for one model across its observed epochs in a <a href="/registry/seal/">crovia.seal.v1</a> object. <code>pip install crovia-tacet-operator crovia-seal</code>, then <code>tacet-operator verify file.seal.json</code>; or <a href="/registry/seal/verify/">paste it in the browser</a>.</p></div>
    <div class="rp-card"><div class="k">Since launch</div><h3>{fmt_int(f['totals']['epochs'])} epochs · {fmt_int(f['totals']['negative_snapshots'])} negative snapshots</h3><p>{fmt_int(f['totals']['targets'])} models on the map since {html.escape(short_ts(f['first_epoch_start']))}; {fmt_int(f['totals']['epochs_anchored'])} epochs anchored; {fmt_int(f['totals']['bitcoin_anchors_confirmed'])} Bitcoin-confirmed substrate anchors in the <a href="/registry/data/substrate/ots_anchors.json">anchor list</a>.</p></div>
    <div class="rp-card"><div class="k">Reuse</div><h3>CC-BY-4.0 · embed the card · subscribe</h3><p>Cite as "Crovia Trust, Silence Report {html.escape(wk)}, {html.escape(url)}". The card is <a href="/report/{html.escape(wk)}.png">{html.escape(wk)}.png</a>; the weekly feed is <a href="/feed.xml">/feed.xml</a>; the same facts as JSON: <a href="/report/report.json">report.json</a>.</p>
    <pre>&lt;a href="{html.escape(url)}"&gt;&lt;img src="{SITE}/report/latest.png" width="600" alt="Crovia Silence Report"&gt;&lt;/a&gt;</pre></div>
  </div>
  <p class="rp-end">Generated {html.escape(f['generated_at'])} from published files only; regenerated daily until the week closes. Errors: <a href="mailto:info@croviatrust.com">info@croviatrust.com</a> or <a href="https://github.com/croviatrust/countersign/issues">open an issue</a>. <a href="/report/">All reports</a>.</p>
</main>
"""
    return shell_head(title, desc, url, img, jsonld) + body + FOOT


def render_index(current: dict[str, Any], archive: list[dict[str, Any]]) -> str:
    url = f"{SITE}/report/"
    title = "Crovia Silence Report — weekly, verifiable, from published files"
    desc = "Every week: how many models Crovia observed hour by hour, how many hourly epochs were anchored in Bitcoin, and the longest verifiable silences, each backed by a signed proof."
    jsonld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": url, "description": desc,
              "publisher": {"@type": "Organization", "name": "Crovia Trust", "url": SITE},
              "hasPart": [{"@type": "Report", "name": f"Silence Report {a['week']}", "url": f"{SITE}/report/{a['week']}/"} for a in archive[:20]]}
    rows = "".join(
        f'<tr><td class="m"><a href="/report/{html.escape(a["week"])}/">{html.escape(a["week"])}</a></td><td class="m">{html.escape(a["week_start"])}</td>'
        f'<td class="m">{fmt_int(a["targets_observed_week"])}</td><td class="m">{fmt_int(a["epochs_week"])} / {fmt_int(a["epochs_anchored_week"])}</td><td class="m">{fmt_int(a["proofs_total"])}</td>'
        f'<td class="m">{html.escape(str(a["top_proofs"][0]["silence_days"]) + " d · " + str(a["top_proofs"][0]["target_id"])) if a["top_proofs"] else "—"}</td></tr>'
        for a in archive)
    body = f"""<main class="rp-wrap">
  <section class="rp-hero">
    <div class="rp-eyebrow">Silence Report · weekly · RSS at /feed.xml</div>
    <h1>What Crovia saw this week, and what it verifiably did not.</h1>
    <p class="rp-lead">{html.escape(desc)} No grades, no rankings: counts and durations that anyone can recompute from the <a href="/registry/api/">public files</a>. Latest: <a href="/report/{html.escape(current['week'])}/">{html.escape(current['week'])}</a> — {html.escape(headline(current))}</p>
    <a href="/report/{html.escape(current['week'])}/"><img class="rp-cardimg" src="/report/latest.png?v={html.escape(current['generated_at'][:13])}" alt="Latest Silence Report card" width="1200" height="630"></a>
  </section>
  <div class="rp-head"><h2>Archive</h2><div class="meta">{len(archive)} weeks · <a href="/feed.xml">RSS</a> · <a href="/report/report.json">report.json</a></div></div>
  <table class="rp"><thead><tr><th>week</th><th>from</th><th>models observed</th><th>epochs / anchored</th><th>proofs</th><th>longest silence</th></tr></thead><tbody>{rows}</tbody></table>
  <p class="rp-end">The report replaced the "Transparency Index" cards in September 2026: letter grades were retired because observations of public surfaces can establish what was and was not found, not how well a provider behaves. <a href="/report/{html.escape(current['week'])}/">Current week</a>.</p>
</main>
"""
    return shell_head(title, desc, url, f"{SITE}/report/latest.png", jsonld) + body + FOOT


def render_feed(archive: list[dict[str, Any]]) -> str:
    def rfc822(s: str) -> str:
        t = parse_ts(s) or dt.datetime.now(dt.timezone.utc)
        return t.strftime("%a, %d %b %Y %H:%M:%S +0000")
    items = []
    for a in archive[:52]:
        u = f"{SITE}/report/{a['week']}/"
        t = f"Silence Report {a['week']}: {fmt_int(a['targets_observed_week'])} models observed, {fmt_int(a['proofs_total'])} signed silence proofs"
        items.append(f"""    <item>
      <title>{html.escape(t)}</title>
      <link>{u}</link>
      <guid isPermaLink="true">{u}</guid>
      <pubDate>{rfc822(a['week_start'] + 'T07:00:00Z')}</pubDate>
      <description>{html.escape(headline(a))} Every figure links to a signed file; proofs verify in the browser, Bitcoin anchor included. CC-BY-4.0.</description>
      <enclosure url="{SITE}/report/{a['week']}.png" type="image/png" length="0"/>
    </item>""")
    now = dt.datetime.now(dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Crovia — Silence Report</title>
    <link>{SITE}/report/</link>
    <atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>
    <description>Weekly: how many AI models Crovia observed hour by hour, how many hourly epochs were anchored in Bitcoin, and the longest verifiable silences, each backed by a signed, offline-verifiable proof. Observation facts only; no grades.</description>
    <language>en</language>
    <copyright>CC-BY-4.0 Crovia Trust</copyright>
    <lastBuildDate>{now}</lastBuildDate>
    <ttl>720</ttl>
    <image><url>{SITE}/logo.png</url><title>Crovia — Silence Report</title><link>{SITE}/report/</link></image>
{chr(10).join(items)}
  </channel>
</rss>
"""


# ----------------------------------------------------------------------------- main

def write_week(facts: dict[str, Any], root: Path) -> None:
    wk = facts["week"]
    (root / wk).mkdir(parents=True, exist_ok=True)
    (root / wk / "facts.json").write_text(json.dumps(facts, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    render_card(facts, root / f"{wk}.png")
    (root / wk / "index.html").write_text(render_week(facts), encoding="utf-8")


def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    facts = collect(now)
    if facts["epochs_week"] == 0 and facts["targets_observed_week"] == 0 and not facts["top_proofs"]:
        print("silence_report: no data for this week yet; nothing written", file=sys.stderr)
        return 0
    root = WEB_ROOT / "report"
    write_week(facts, root)
    (root / "latest.png").write_bytes((root / f"{facts['week']}.png").read_bytes())

    # the previous week is closed now: recompute it once more so its numbers are final
    prev = collect(now - dt.timedelta(days=7))
    prev_out = None
    if prev["epochs_week"] or prev["targets_observed_week"]:
        write_week(prev, root)
        prev_out = prev

    (root / "report.json").write_text(json.dumps({"schema": "crovia.silence_report.v1", "latest": facts["week"], "url": f"{SITE}/report/{facts['week']}/",
                                                  "previous": prev_out, **facts}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    archive: list[dict[str, Any]] = []
    for fp in glob.glob(str(root / "*-W*" / "facts.json")):
        a = load(Path(fp), None)
        if isinstance(a, dict) and re.fullmatch(r"\d{4}-W\d{2}", str(a.get("week", ""))):
            archive.append(a)
    archive.sort(key=lambda a: a["week"], reverse=True)
    archive = archive[:KEEP_WEEKS]
    (root / "index.html").write_text(render_index(facts, archive), encoding="utf-8")
    (WEB_ROOT / "feed.xml").write_text(render_feed(archive), encoding="utf-8")
    print(f"silence_report: {facts['week']} · {facts['targets_observed_week']} models · {facts['epochs_week']} epochs ({facts['epochs_anchored_week']} anchored) · {facts['proofs_total']} proofs · previous week {'finalized' if prev_out else 'absent'} · {len(archive)} weeks in feed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
