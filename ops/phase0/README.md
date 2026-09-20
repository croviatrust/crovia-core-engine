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
  `by_axiom_type['AX.LAC']` is 0 (JS `|| 492` treated zero as missing), and shows
  `pulse.anchors.distinct_roots` (39) instead of `ots_anchors.bitcoin_confirmed` (106), per
  CANON §4: re-anchors of an unchanged root do not count. Backup
  `index.html.bak_20260919T1755Z`.
- `crovia-evidence-lab` hourly sync (`/opt/crovia/repos/crovia-evidence-lab`) had been
  failing since 2026-05-17 on an orphaned `.git/index.lock`; lock removed, repo identity set
  to Crovia Trust, backlog (2026-W20…W38) pushed. Watch `/var/log/crovia/evidence_lab_sync.log`.
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

## Server changes of 2026-09-19 (evening): TACET live, access policy, cron cleanup

**Correction to the earlier diagnosis.** The `autonomous_observer` is alive
(`crovia-observer.timer`, hourly, ~120 observations/run into Postgres, exported as
`AX.NEC` envelopes with per-necessity `is_present`). What died in June was only the
`AX.ABS` emission that fed `lacuna_candidates`. TACET now takes over that role with
its own, independently verifiable snapshots.

**TACET operator installed** (`countersign/tacet/operator`, venv `/opt/crovia/tacet/.venv`,
state `/opt/crovia/tacet/state`, public `/var/www/registry/data/tacet/`). Keys created
(seeds 0600); public keys in `trust_root.json` and `canon.json → tacet`. Target list
`/opt/crovia/tacet/targets.txt` = 859 model candidates + 7,301 unified observer models
(datasets removed; `state/target_resolution.json`). Epoch 0 emitted 18:25Z:
69 snapshots, 45 negative, 24 disclosures, sheet stamped with OTS. Cron:

```
5 * * * *     tacet-operator run-epoch --targets /opt/crovia/tacet/targets.txt
40 */2 * * *  tacet-operator refresh-anchors      # was */6; re-issues featured proofs when a sheet closes
50 4 * * *    tacet-operator publish --proofs
```

The packages are editable installs from `/opt/crovia/repos/countersign` (`git pull` there,
no reinstall needed unless `pyproject.toml` changes). First three epochs closed in Bitcoin
blocks 967736 and 967740 at 20:52Z on day one.

**Nginx CSP (2026-09-19 21:18Z).** `connect-src` on `croviatrust.com` gained
`https://api.drand.sh https://mempool.space https://blockstream.info`: the browser
verifier's network checks (drand round bytes, and SPEC §8.6 Bitcoin headers) were being
blocked by the old policy and reported "not reachable" to every visitor. Backup:
`/etc/nginx/sites-backup/croviatrust.com.bak_*_csp`. A stray
`croviatrust.com.bak_20260919T185832Z` was moved out of `sites-enabled/` (nginx includes `*`).

**Access policy applied** (CANON §5): the `$is_bulk_data` referer gate in
`/etc/nginx/snippets/data-protection.conf` is now empty; every data file is fetchable
directly (rate limit stays). Only `forensic_dossiers.json` / `forensic_report.json`
keep the `$pro_gate`. `/registry/api/` marks `global_ranking`, `tpa_latest`,
`tpa_summary`, `sonar_chains` as free links.

**Cron / timer cleanup** (backup: `/opt/crovia/tacet/state/crontab.bak_20260919`):

| unit | action | why |
|---|---|---|
| `crovia-outreach.timer` | `disable --now` | LIVE mode, tried to open 20 HF discussions/week (failing on token); outreach is stopped by decision |
| `outreach_status_checker.py` (07:30) | commented | reads GitHub issue status of a stopped campaign |
| `scripts/ots_anchor.py stamp` (03:05) | commented | re-stamped the same substrate root daily; superseded by `ots_stamp_substrate_root.sh` |
| `scripts/smoke_public.sh` (*/15) | commented | probed retired paths and overwrote `_smoke.json` with false failures |
| `smoke_public_v2.sh` | hourly → `*/15` | single writer of `_smoke.json`; 0/42 failing |

**Disk.** `/opt/crovia/.venv` carried 6.6 GB of CUDA libraries on a GPU-less host;
torch reinstalled as `2.9.1+cpu` (imports verified, `croviatrust.service` healthy).
Root went from 96 % to 80 %.

Left as-is on purpose: `crovia_broadcast.py` (daily card to Bluesky/Telegram/Mastodon,
idempotent), `crovia_broadcast_changes.py` (rare, high-signal only), `wayback_save_submitter.py`
(useful: archived copies let third parties re-run TACET predicates), `zenodo_deposit_weekly.py`.

## What Phase 0 does not do

It does not revive `AX.ABS` emission or the old LACUNA issuance. Absence is now
produced by TACET (beacon-bound negative snapshots, `tacet/SPEC.md` §7) and the
LACUNA page will read from `/registry/data/tacet/`.

## Server changes of 2026-09-20 (Silence Report, retirements)

A second, legacy Crovia was still live and updated hourly: `/index/` ("Transparency Index", letter
grades per lab), `/card/<day>/` (daily OG card "80% of major labs score F"), `/feed.xml` (RSS of the
same), `/registry/data/transparency_index.json`, and `crovia_broadcast.py` posting the card to
Bluesky every day. None of it was in canon or in the audit; all of it contradicted "observation facts
only". Retired and replaced:

| what | action |
|---|---|
| `generate_transparency_index.py` (hourly), `generate_daily_card.py` (hourly) | cron commented; outputs moved to `/opt/crovia/site-backups/legacy-index-20260920/` |
| `/index/`, `/card/` | 301 → `/m/`, `/report/` (`snippets/legacy-freeze.conf`) |
| `/registry/data/transparency_index.json` | 410 with a JSON pointer to `model_records.json` and `/report/report.json`; removed from canon `data_files` |
| `guard_index.sh` (*/5) | cron commented: restored `registry/index.html` from a `.canonical` copy whenever the new file was smaller |
| `scripts/silence_report.py` (07:20 daily, new) | weekly Silence Report: `/report/<YYYY-Www>/`, card PNG, `/report/index.html`, `/report/report.json` (with `previous` = last closed week), `/feed.xml` RSS with one item per week |
| `scripts/crovia_broadcast.py` (07:35 daily, rewritten) | posts each closed week once per platform (Bluesky configured); `/opt/crovia/crovia_broadcast.py` replaced with the same file because `crovia_broadcast_changes.py` imports its helpers |
| `scripts/zenodo_deposit_weekly.py` (Tue 03:00, rewritten) | deposits the TACET files (sheets, proofs, targets, anchors, report facts, MANIFEST, DATASHEET, METHODS) under the existing Concept DOI 10.5281/zenodo.20111130; metadata aligned with canon. `--revise` published 2026-W38-r2 (10.5281/zenodo.22856637) so the concept resolves to canon-conformant content |
| `seo_sitemap_indexnow.py` | `/report/` added to CORE_PAGES |

Kept: `global_ranking.json` and `/registry/compliance/` (model-card checklist coverage: counts of
present/absent items, no grades), `crovia_broadcast_changes.py` (high-signal change posts).
