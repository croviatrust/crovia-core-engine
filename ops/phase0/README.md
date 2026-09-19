# Phase 0 — make the live numbers true

Server-side patches that bring `croviatrust.com` in line with `CANON.md` §4-§5
**without touching the generators or the HTML**. Each script runs after the
existing hourly generators and rewrites the published JSON atomically.
Everything is reversible: the raw values are preserved under `*_raw` keys.

Tested against the live files of 2026-09-19:

| Figure | Live today | After Phase 0 |
|---|---|---|
| LACUNA records (`AX.LAC`) | 1085 (collector heartbeats) | AX.LAC on model targets only, raw kept |
| Llama-3.1-8B silence | 244 days (`first_seen → now`) | 89 days (`first_seen → last_seen`, paused since 2026-04-17) |
| LACUNA candidates | 1363, all from a collector dead since 2026-06-01 | 1363 flagged `stale`, page banner "observation paused since 2026-06-01" |
| Bitcoin anchors | 106, same root 38× in a row, stalled 11 days | `anchors.valid=false` exposed; new roots stamped once each |
| Smoke | 20/39 failing, probing 2025 paths | 42/42 on canon paths; retired paths redirect |

## Installed on CroviaTrust-1 (2026-09-19)

Files live in `/opt/crovia/phase0/` (scripts, `canon/canon.json`, `tools/audit_surfaces.py`,
`state/` with the pre-change copies of every file touched). The generators run every
minute / every 30 minutes, so the post-processors are **chained onto the generator's own
cron line** instead of running on a separate schedule (root crontab, backup in
`/root/crontab.bak_<ts>`):

```cron
* * * * *   /opt/crovia/scripts/home_pulse.py …; cd /opt/crovia/phase0 && python3 truth_pulse.py --pulse /var/www/registry/data/_home_pulse.json --ledger /opt/crovia/substrate/axiom_ledger.jsonl --ots /var/www/registry/data/substrate/ots_anchors.json --cache /opt/crovia/phase0/state/lacuna_count.json
*/30 * * * * /usr/bin/python3 /opt/crovia/scripts/build_silence_index.py …; cd /opt/crovia/phase0 && python3 truth_silence_index.py --ledger /opt/crovia/substrate/axiom_ledger.jsonl --out /var/www/registry/data/silence_index.json
7 * * * *   … substrate_snapshots.py …; cd /opt/crovia/phase0 && python3 truth_lacuna_candidates.py --path /var/www/registry/data/substrate/lacuna_candidates.json
15 */6 * * * cd /opt/crovia/phase0 && DATA=/var/www/registry/data ./ots_stamp_substrate_root.sh
3 * * * *   cd /opt/crovia/phase0 && ./smoke_public_v2.sh --json > …/_smoke.json
*/10 * * * * cd /opt/crovia/phase0 && /opt/crovia/seal-svc/.venv/bin/python seal_public_log.py
```

`truth_pulse.py` scans the 4 GB ledger once an hour (`--cache`, 6 s with the `"AX.LAC"`
prefilter) and reuses the count for the per-minute runs. `ots_stamp_substrate_root.sh`
writes `/opt/crovia/substrate/anchors/<root>.ots` + `<root>.status.json`, the layout
`scripts/ots_refresh.py` rebuilds the public manifest from at 04:30, so new roots are
promoted to `bitcoin` automatically. `seal_public_log.py` republishes the Seal service's
`/v1/wall` as `/registry/data/seal/public_log.jsonl` after re-verifying every Seal.

Also applied on the server the same day:

- `seal-svc` (`/opt/crovia/seal-svc/app.py`) replaced by `integrations/seal-svc/app.py`
  from `crovia-seal` main; reference installed in its venv. Emits `crovia.seal.v1`.
- nginx: `/check.html → /registry/verify/`, `/registry/outreach/ → /registry/compliance/`
  (no double hop), two stray `*.bak` vhosts moved to `/etc/nginx/sites-backup/`.
- `/var/www/crovia/llms.txt` = `drafts/site/llms.txt`; `llms-full.txt` and
  `.well-known/ai-plugin.json` no longer advertise private (403) files or hard-coded figures;
  `/var/www/registry/api/index.html` labels the six private endpoints "professional";
  `/var/www/registry/seal/index.html` shows a real `crovia.seal.v1` example;
  `/var/www/registry/lacuna/index.html` loads `lacuna_banner.js?v=…` (query string busts the
  Cloudflare cache); `/var/www/crovia/index.html` no longer falls back to a hard-coded 492 when
  `by_axiom_type['AX.LAC']` is 0 (JS `|| 492` treated zero as missing).
- Disk: the 37 GB HuggingFace tensor cache (`latent_cache`, unused since 2026-05-13) was
  purged; the data volume went from 100 % to 61 %.

**These are server-side edits.** If the site is redeployed from the original sources,
carry the same changes into the sources first (the exact before/after of each file is in
`/opt/crovia/phase0/state/site_before/`).

## Dry run

```bash
cd /opt/crovia/phase0
python3 truth_pulse.py --pulse /var/www/registry/data/_home_pulse.json --ledger /opt/crovia/substrate/axiom_ledger.jsonl --ots /var/www/registry/data/substrate/ots_anchors.json --dry-run
DRY_RUN=1 DATA=/var/www/registry/data ./ots_stamp_substrate_root.sh
./smoke_public_v2.sh
```

## Rollback

Every rewritten file keeps the previous values (`by_axiom_type_raw`,
`absence_streak_days_raw`); removing the cron lines restores the generators'
output at the next run. `truth_silence_index.py` writes a `v2` schema; keep a
copy of the current `silence_index.json` before the first run if the embed
widget depends on a field that v2 renames (`n_real_targets`,
`total_silence_days`, `top_silent.target_id` are preserved).

## What this does not do

It does not revive the collectors (`autonomous_observer`, `wayback_hf_collector`)
or restart LACUNA issuance. Those come back through TACET's observer (see
`tacet/SPEC.md` §7), which replaces the heartbeat-as-certificate model with
beacon-bound negative snapshots.
