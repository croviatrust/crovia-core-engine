#!/usr/bin/env python3
"""Post the weekly Silence Report to Crovia's own channels (Bluesky; Telegram/Mastodon if configured).

Replaces the daily "Transparency Index" card post (letter grades, retired 2026-09-20). Posts once per
closed ISO week per platform: the report generator finalizes a week on the Monday after it, and this
script, run daily after it, posts that week's card and permalink. Idempotent through a state file.

Reads:   /var/www/crovia/report/report.json      (latest closed week: field "previous")
         /var/www/crovia/report/<week>.png       (card)
Config:  /opt/crovia/broadcast_config.json      {"bluesky": {"handle", "app_password"}, "telegram": {...}, "mastodon": {...}}
State:   /opt/crovia/state/broadcast_state.json {"posted_weeks": {"bluesky": ["2026-W38"]}}
Usage:   crovia_broadcast.py [--dry-run] [--force] [--week 2026-W38]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SITE = "https://croviatrust.com"
REPORT = Path("/var/www/crovia/report/report.json")
CARD_DIR = Path("/var/www/crovia/report")
CONFIG = Path("/opt/crovia/broadcast_config.json")
STATE = Path("/opt/crovia/state/broadcast_state.json")
BSKY_PDS = "https://bsky.social"


def _request(url, *, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def post_json(url, payload, headers=None):
    h = {"Content-Type": "application/json", **(headers or {})}
    body = _request(url, data=json.dumps(payload).encode("utf-8"), headers=h, method="POST")
    return json.loads(body) if body else {}


def load(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def fmt(n) -> str:
    return f"{int(n):,}"


def build(f: dict, first_time: bool) -> tuple[str, str, str]:
    wk = f["week"]
    top = (f.get("top_proofs") or [None])[0]
    lead = (f"Silence Report {wk}: {fmt(f['targets_observed_week'])} AI models observed hour by hour; "
            f"{fmt(f['epochs_anchored_week'])} hourly epochs anchored in Bitcoin; "
            f"{fmt(f['proofs_total'])} signed proofs that nothing was disclosed.")
    parts = [lead]
    if top:
        parts.append(f"Longest verifiable silence: {top['silence_days']} days ({top['target_id']}).")
    tail = "Every number links to a signed file you can verify in your browser."
    if first_time:
        tail = "New weekly format: observation facts with proofs, no grades."
    text = " ".join(parts + [tail])
    if len(text) > 296:
        text = " ".join(parts)
    if len(text) > 296:
        text = parts[0]
    title = f"Crovia Silence Report {wk}"
    desc = f"{fmt(f['targets_observed_week'])} models observed, {fmt(f['epochs_anchored_week'])} epochs anchored, {fmt(f['proofs_total'])} signed silence proofs. Observation facts only."
    return text, title, desc


def post_bluesky(cfg: dict, text: str, permalink: str, title: str, desc: str, png: Path) -> str:
    sess = post_json(f"{BSKY_PDS}/xrpc/com.atproto.server.createSession", {"identifier": cfg["handle"], "password": cfg["app_password"]})
    auth = {"Authorization": f"Bearer {sess['accessJwt']}"}
    thumb = None
    if png.exists():
        try:
            blob = _request(f"{BSKY_PDS}/xrpc/com.atproto.repo.uploadBlob", data=png.read_bytes(), headers={**auth, "Content-Type": "image/png"}, method="POST")
            thumb = json.loads(blob).get("blob")
        except Exception as e:  # noqa: BLE001
            print(f"  bluesky: blob upload failed ({e}), posting without image", file=sys.stderr)
    external = {"uri": permalink, "title": title, "description": desc}
    if thumb:
        external["thumb"] = thumb
    # make the permalink a tappable facet as well as the embed
    facets = []
    idx = text.find(SITE)
    if idx >= 0:
        b = text.encode("utf-8")
        start = len(text[:idx].encode("utf-8"))
        end = start + len(SITE.encode("utf-8"))
        facets = [{"index": {"byteStart": start, "byteEnd": end}, "features": [{"$type": "app.bsky.richtext.facet#link", "uri": permalink}]}]
        del b
    record = {"$type": "app.bsky.feed.post", "text": text, "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
              "embed": {"$type": "app.bsky.embed.external", "external": external}, "langs": ["en"]}
    if facets:
        record["facets"] = facets
    res = post_json(f"{BSKY_PDS}/xrpc/com.atproto.repo.createRecord", {"repo": sess["did"], "collection": "app.bsky.feed.post", "record": record}, headers=auth)
    return res.get("uri", "ok")


def post_telegram(cfg: dict, text: str, permalink: str, png_url: str) -> str:
    res = post_json(f"https://api.telegram.org/bot{cfg['bot_token']}/sendPhoto", {"chat_id": cfg["chat_id"], "photo": png_url, "caption": f"{text}\n\n{permalink}"})
    if not res.get("ok"):
        raise RuntimeError(f"telegram error: {res}")
    return str(res.get("result", {}).get("message_id", "ok"))


def post_mastodon(cfg: dict, text: str, permalink: str) -> str:
    res = post_json(f"{cfg['base_url'].rstrip('/')}/api/v1/statuses", {"status": f"{text}\n\n{permalink}", "language": "en", "visibility": "public"},
                    headers={"Authorization": f"Bearer {cfg['access_token']}"})
    return res.get("url", "ok")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--week", help="post this week's report even if it is not closed")
    a = ap.parse_args()
    cfg = load(CONFIG, {})
    if not cfg:
        print("No broadcast_config.json; nothing to post.", file=sys.stderr)
        return 0
    report = load(REPORT, None)
    if not report:
        print("report.json missing; run silence_report.py first", file=sys.stderr)
        return 1
    if a.week:
        facts = load(CARD_DIR / a.week / "facts.json", None)
    else:
        facts = report.get("previous")  # latest closed week, finalized by the generator
    if not facts:
        print("no closed week to post yet", file=sys.stderr)
        return 0
    wk = facts["week"]
    state = load(STATE, {})
    posted = state.setdefault("posted_weeks", {})
    first_time = not any(posted.values())
    text, title, desc = build(facts, first_time)
    permalink = f"{SITE}/report/{wk}/"
    png = CARD_DIR / f"{wk}.png"
    print(f"Broadcast {wk} -> {permalink}\n  text ({len(text)}): {text}")
    if a.dry_run:
        return 0
    for platform, fn in (("bluesky", lambda c: post_bluesky(c, text, permalink, title, desc, png)),
                         ("telegram", lambda c: post_telegram(c, text, permalink, f"{SITE}/report/{wk}.png")),
                         ("mastodon", lambda c: post_mastodon(c, text, permalink))):
        if platform not in cfg:
            continue
        if wk in posted.get(platform, []) and not a.force:
            print(f"  {platform}: already posted {wk}, skip")
            continue
        try:
            ref = fn(cfg[platform])
            posted.setdefault(platform, []).append(wk)
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(state, indent=2))
            print(f"  {platform}: posted ({ref})")
        except Exception as e:  # noqa: BLE001
            print(f"  {platform}: FAILED {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
