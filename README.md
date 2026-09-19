# Crovia Core Engine — the Substrate

[![CI](https://github.com/croviatrust/crovia-core-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/croviatrust/crovia-core-engine/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=flat-square)](https://opensource.org/licenses/Apache-2.0)

**Crovia records what AI providers disclose about training data, and the
absence of it, as signed, Bitcoin-anchored facts.** This repository is the
Crovia Substrate: the collectors that observe public surfaces, the observer
that turns fetches into signed envelopes, the sealer that Merkle-seals the
AXIOM ledger every hour, the anchoring job that commits roots to Bitcoin via
OpenTimestamps, and the builders that publish `croviatrust.com/registry/`.

## What the ledger contains

| Envelope | Meaning |
|---|---|
| `AX.OBS` | An observation of a public surface (model card, documentation page, repository) at a point in time. |
| `AX.NEC` | A necessary-disclosure check: what the surface was expected to carry and whether it did. |
| `AX.ABS` | A negative observation: no contemporaneous disclosure satisfying the published predicate was found. |
| `AX.LAC` | A LACUNA record for an AI model: a signed statement over a window of `AX.ABS`. Only model targets (`org/model`) count. |

Every envelope is Ed25519-signed by the observer key in
`registry/data/substrate/trust_root.json`; every hour the ledger's Merkle root
is published in `latest_seal.json`; new roots are stamped with OpenTimestamps
and listed in `ots_anchors.json` once confirmed in Bitcoin.

Headline figures shown on the site are defined in
[CANON.md §4](https://github.com/croviatrust/countersign/blob/main/CANON.md)
and recomputable from the public data files; `ops/phase0/` contains the
post-processors that enforce those definitions.

## Layout

```
crovia/             open-core library and CLIs: `crovia`, `crovia-run`, `crovia-verify`
core/ proofs/       deterministic evidence artefacts, hash-chain writer/verifier
crovia-automation/  automation suite (compliance reports, target builders)
schemas/            JSON schemas for envelopes and public files
ops/registry/       registry maintenance scripts (served-vs-disk checks, sync)
ops/phase0/         post-processors that enforce the canonical headline definitions
tests/              pytest; CI runs on every push (`.github/workflows/ci.yml`)
```

The hourly substrate pipeline (collect → observe → seal → build) currently runs
from `/opt/crovia/scripts` on the production host and is being brought under
this repository step by step; `ops/phase0/README.md` records exactly what is
installed on the server today, including the cron schedule.

Tests under `tests/` that depend on the professional-tier package `croviapro`
are skipped automatically when it is not installed, so the open-core suite is
green on a plain checkout.

## Run locally

```bash
pip install -e .
pytest tests -q
crovia --help
```

## Deployment

Production is one Hetzner host. Server-side edits and hand-copied deployments
have historically overwritten each other; the rule now is that anything
changed on the server is committed here first (`ops/phase0/README.md` lists the
files that were edited in place on 2026-09-19 and must not be redeployed from an
older local copy). Public routes and data files are those listed in the canon;
retired paths return 301.

## Status

- Substrate: live; hourly Merkle seals of the AXIOM ledger, Bitcoin anchoring via OpenTimestamps (new roots only).
- Collectors: several are paused. Silence figures are observation-bounded: they
  stop accruing when a target is no longer observed (`truth_silence_index.py`).
- LACUNA issuance for model targets: 0 records to date; observation paused since 2026-06; resumes on TACET observers
  (`countersign/tacet`), which bind every negative observation to a public
  randomness round and a Bitcoin anchor.

## Crovia surfaces

| Surface | URL |
|---|---|
| Ledger and registry | https://croviatrust.com/registry/ |
| LACUNA (absence records) | https://croviatrust.com/registry/lacuna/ |
| Crovia Seal: spec, verifier, log | https://croviatrust.com/registry/seal/ |
| Issuer trust root | https://seal.croviatrust.com/trust-root.json |
| Machine-readable index | https://croviatrust.com/llms.txt |
| MCP server | https://croviatrust.com/mcp |
| Canon (source of truth for all of the above) | https://github.com/croviatrust/countersign/blob/main/CANON.md |

Repositories: [crovia-seal](https://github.com/croviatrust/crovia-seal) (the standard) ·
[crovia-core-engine](https://github.com/croviatrust/crovia-core-engine) (the substrate) ·
[countersign](https://github.com/croviatrust/countersign) (witnessing and TACET) ·
[crovia-evidence-lab](https://github.com/croviatrust/crovia-evidence-lab) (public data) ·
[causari](https://github.com/croviatrust/causari) (sibling product: code provenance).

Crovia records facts about public surfaces. It does not infer intent, allege
wrongdoing or enforce compliance. Contact: info@croviatrust.com.
