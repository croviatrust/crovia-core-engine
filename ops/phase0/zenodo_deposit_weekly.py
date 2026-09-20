#!/usr/bin/env python3
"""Weekly Zenodo deposit of Crovia's verifiable-silence observations (DOI per week, one Concept DOI).

Zenodo (CERN/OpenAIRE) issues DOIs without an endorsement gate and is indexed by Google Scholar,
OpenAIRE and DataCite: each weekly snapshot is a permanent, citable copy of what TACET published,
and all versions roll up to the Concept DOI 10.5281/zenodo.20111130, the citation for the series.

What is deposited (all files are public on croviatrust.com; the deposit is a dated, hashed copy):
    tacet/index.json, targets.json, latest.json, trust_root.json, proofs/index.json
    tacet/sheets/*.json           every signed epoch sheet
    tacet/proofs/*.seal.json      every published silence proof (crovia.seal.v1)
    substrate/ots_anchors.json    Bitcoin anchors of the substrate ledger
    silence_index.json            observation-bounded silence per target
    report/<week>/facts.json      the week's Silence Report facts
    MANIFEST.json                 sha256 of every deposited file
    DATASHEET.md, METHODS.md      generated here, aligned with CANON.md

Runs Tuesday 03:00 UTC from cron with ZENODO_TOKEN in the environment (/etc/crovia/zenodo.env).
Idempotent per ISO week; --revise publishes an additional version for the current week.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ZENODO_API = os.environ.get("ZENODO_API", "https://zenodo.org/api")
TOKEN = os.environ.get("ZENODO_TOKEN", "")
STATE = Path("/opt/crovia/state/zenodo_deposit_state.json")
DATA = Path("/var/www/registry/data")
WEB = Path("/var/www/crovia")
SITE = "https://croviatrust.com"
CONCEPT_DOI = "10.5281/zenodo.20111130"

KEYWORDS = [
    "TACET", "verifiable silence", "verifiable absence", "non-inclusion proof", "sparse Merkle tree",
    "Crovia Seal", "cryptographic receipt", "drand", "OpenTimestamps", "Bitcoin anchoring",
    "AI training data disclosure", "model card", "EU AI Act Article 53", "GPAI", "Hugging Face",
    "Ed25519", "AI transparency", "provenance",
]


def http(method: str, url: str, headers: dict | None = None, data: bytes | None = None, timeout: int = 180):
    req = urllib.request.Request(url, method=method, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")[:1000]}


def auth() -> dict:
    return {"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"}


def load_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def iso_week(d: dt.date | None = None) -> str:
    d = d or dt.datetime.now(dt.timezone.utc).date()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def gather(week: str) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    t = DATA / "tacet"
    for name in ("index.json", "targets.json", "latest.json", "trust_root.json"):
        if (t / name).exists():
            out[f"tacet/{name}"] = (t / name).read_bytes()
    if (t / "proofs" / "index.json").exists():
        out["tacet/proofs/index.json"] = (t / "proofs" / "index.json").read_bytes()
    for fp in sorted(glob.glob(str(t / "sheets" / "*.json"))):
        out[f"tacet/sheets/{Path(fp).name}"] = Path(fp).read_bytes()
    for fp in sorted(glob.glob(str(t / "proofs" / "*.seal.json"))):
        out[f"tacet/proofs/{Path(fp).name}"] = Path(fp).read_bytes()
    for rel in ("substrate/ots_anchors.json", "silence_index.json"):
        if (DATA / rel).exists():
            out[rel.replace("/", "_") if rel.startswith("substrate") else rel] = (DATA / rel).read_bytes()
    facts = WEB / "report" / week / "facts.json"
    if facts.exists():
        out[f"report_{week}_facts.json"] = facts.read_bytes()
    return out


def stats(files: dict[str, bytes]) -> dict:
    latest = json.loads(files.get("tacet/latest.json", b"{}") or b"{}")
    targets = json.loads(files.get("tacet/targets.json", b"{}") or b"{}")
    proofs = json.loads(files.get("tacet/proofs/index.json", b"{}") or b"{}")
    anchors = json.loads(files.get("substrate_ots_anchors.json", b"{}") or b"{}")
    return {
        "epochs": int(latest.get("epochs") or 0),
        "epochs_anchored": int(latest.get("anchored_epochs") or 0),
        "negative_snapshots": int(latest.get("negative_snapshots_total") or 0),
        "snapshots": int(latest.get("snapshots_total") or 0),
        "targets": int(targets.get("count") or len(targets.get("targets", []))),
        "proofs": len(proofs.get("proofs", [])),
        "sheets": sum(1 for k in files if k.startswith("tacet/sheets/")),
        "bitcoin_anchors_confirmed": int(anchors.get("bitcoin_confirmed") or 0),
        "map_id": latest.get("map_id"),
    }


def datasheet(week: str, s: dict) -> str:
    return f"""# Datasheet — Crovia verifiable-silence observations, snapshot {week}

## Motivation
Crovia Trust records what AI providers disclose about training data on their public model
surfaces, and the absence of such disclosure, as signed, Bitcoin-anchored observations. This
dataset lets anyone re-check those observations without trusting Crovia's servers.

## Composition
- `tacet/index.json`, `tacet/sheets/*.json`: {s['sheets']} hourly epoch sheets ({s['epochs']} epochs, {s['epochs_anchored']} with a Bitcoin anchor). Each sheet is the signed root of a depth-256 sparse Merkle tree over the negative snapshots of that hour, opened with a drand round and closed with an OpenTimestamps receipt.
- `tacet/targets.json`: {s['targets']} observed models (Hugging Face ids), first/last observation, negative counts.
- `tacet/proofs/*.seal.json`: {s['proofs']} silence proofs, each a `crovia.seal.v1` object wrapping the non-inclusion paths of one model across its observed epochs.
- `silence_index.json`: observation-bounded silence per target (days between first and last negative observation; hours not observed do not count).
- `substrate_ots_anchors.json`: {s['bitcoin_anchors_confirmed']} Bitcoin-confirmed anchors of the substrate ledger.
- `report_{week}_facts.json`: the Silence Report of the week ({SITE}/report/{week}/).
- `MANIFEST.json`: sha256 of every file above.

## Collection process
Hourly, the operator fetches each target's public model card and README and evaluates the published
predicate (a disclosure of training data sources). A negative result becomes a signed snapshot; the set of
the hour's negatives is committed to the epoch sheet. Nothing is inferred about hours not observed.

## What this dataset does not say
It does not grade or rank providers, does not assert intent, and does not claim a provider made no
disclosure anywhere: it states which surfaces were checked, when, and what was not found there.

## Verification
`pip install crovia-tacet-operator crovia-seal` then `tacet-operator verify <proof>.seal.json`, or open a
proof in the browser verifier at {SITE}/registry/seal/verify/. Specification: {SITE}/registry/tacet/,
`https://github.com/croviatrust/countersign/blob/main/tacet/SPEC.md`.

## Licence and citation
CC-BY-4.0. Cite the series by its Concept DOI {CONCEPT_DOI}, or this week's DOI for a fixed snapshot.
"""


def methods(week: str, s: dict) -> str:
    return f"""# Methods — snapshot {week}

Map: `{s['map_id']}`. Epoch: one hour (UTC). Commitment: depth-256 sparse Merkle tree, key = sha256 of
the canonical target id, value = sha256 of the negative snapshot. Beacon: drand quicknet round recorded
at epoch open. Anchor: OpenTimestamps receipt of the sheet hash, upgraded once confirmed in a Bitcoin
block. Signatures: Ed25519 (operator key in `tacet/trust_root.json`). Canonicalization: CSC-1, a strict
RFC 8785 subset (no floats). Receipt format: `crovia.seal.v1` (IETF draft-crovia-seal-01).

Silence for a target is the sum of durations of the epochs in which it was observed and no disclosure
matched the predicate; it is a lower bound over observed hours, never a calendar interval.

Reference implementation and conformance vectors: `crovia-tacet`, `crovia-tacet-operator`, `crovia-seal`
on PyPI; `@crovia/seal` on npm; https://github.com/croviatrust/countersign,
https://github.com/croviatrust/crovia-seal. Definitions: https://github.com/croviatrust/countersign/blob/main/CANON.md
"""


def metadata(week: str, version: str, s: dict) -> dict:
    desc = (
        f"<p>Weekly, hashed copy of the verifiable-silence observations Crovia Trust publishes at "
        f"<a href=\"{SITE}/registry/tacet/\">croviatrust.com/registry/tacet/</a>: {s['sheets']} signed hourly epoch sheets "
        f"({s['epochs_anchored']} anchored in Bitcoin), {s['targets']:,} observed AI models, {s['negative_snapshots']:,} negative "
        f"snapshots and {s['proofs']} silence proofs in the <code>crovia.seal.v1</code> receipt format.</p>"
        f"<p>A silence proof shows, for one model, that in every observed hour no training-data disclosure matching the "
        f"published predicate appeared on its public surfaces: a sparse-Merkle non-inclusion path per epoch, the drand round that "
        f"opened the epoch and the OpenTimestamps receipt that closed it. Proofs verify offline with "
        f"<code>pip install crovia-tacet-operator crovia-seal</code> or in the browser at "
        f"<a href=\"{SITE}/registry/seal/verify/\">croviatrust.com/registry/seal/verify/</a>.</p>"
        f"<p>Crovia records what was observed and what was not; it does not grade, rank or attribute intent. Durations are bounded "
        f"by observed hours. Weekly summary: <a href=\"{SITE}/report/{week}/\">Silence Report {week}</a>. "
        f"Definitions: <a href=\"https://github.com/croviatrust/countersign/blob/main/CANON.md\">CANON.md</a>. "
        f"Receipt format: IETF <a href=\"https://datatracker.ietf.org/doc/draft-crovia-seal/\">draft-crovia-seal</a>.</p>"
        f"<p>Licence CC-BY-4.0. Cite the series by the Concept DOI {CONCEPT_DOI}.</p>"
    )
    return {"metadata": {
        "title": f"Crovia — Verifiable silence observations of AI training-data disclosure, weekly snapshot {week}",
        "upload_type": "dataset",
        "description": desc,
        "creators": [{"name": "Crovia Trust", "affiliation": "Crovia Trust"}],
        "keywords": KEYWORDS,
        "license": "cc-by-4.0",
        "access_right": "open",
        "version": version,
        "language": "eng",
        "related_identifiers": [
            {"identifier": f"{SITE}/report/{week}/", "relation": "isDocumentedBy", "resource_type": "publication-report"},
            {"identifier": f"{SITE}/registry/data/tacet/index.json", "relation": "isDerivedFrom", "resource_type": "dataset"},
            {"identifier": "https://github.com/croviatrust/countersign", "relation": "isSupplementTo", "resource_type": "software"},
            {"identifier": "https://github.com/croviatrust/crovia-seal", "relation": "isSupplementTo", "resource_type": "software"},
            {"identifier": "https://datatracker.ietf.org/doc/draft-crovia-seal/", "relation": "isDescribedBy", "resource_type": "publication-other"},
        ],
    }}


def deposit(files: dict[str, bytes], meta: dict, parent_id: int | None):
    if parent_id:
        st, body = http("POST", f"{ZENODO_API}/deposit/depositions/{parent_id}/actions/newversion", auth())
        if st != 201:
            return None, {"step": "newversion", "status": st, "body": body}
        st, dep = http("GET", body["links"]["latest_draft"], auth())
    else:
        st, dep = http("POST", f"{ZENODO_API}/deposit/depositions", auth(), data=b"{}")
    if st not in (200, 201):
        return None, {"step": "create", "status": st, "body": dep}
    dep_id, bucket = dep["id"], dep["links"]["bucket"]
    # a new version inherits the previous files; remove them so the record holds exactly this snapshot
    for f in dep.get("files", []):
        http("DELETE", f"{ZENODO_API}/deposit/depositions/{dep_id}/files/{f['id']}", auth())
    for name, blob in files.items():
        st, r = http("PUT", f"{bucket}/{name.replace('/', '__')}", {"Content-Type": "application/octet-stream", "Authorization": f"Bearer {TOKEN}"}, data=blob)
        if st not in (200, 201):
            return None, {"step": f"upload {name}", "status": st, "body": r}
    st, body = http("PUT", f"{ZENODO_API}/deposit/depositions/{dep_id}", auth(), data=json.dumps(meta).encode())
    if st != 200:
        return None, {"step": "metadata", "status": st, "body": body}
    st, body = http("POST", f"{ZENODO_API}/deposit/depositions/{dep_id}/actions/publish", auth())
    if st not in (200, 202):
        return None, {"step": "publish", "status": st, "body": body}
    return body, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revise", action="store_true", help="publish an additional version for the current week")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not TOKEN and not a.dry_run:
        print(json.dumps({"error": "ZENODO_TOKEN not set"}))
        return 2
    week = iso_week()
    state = load_json(STATE, {"weeks": {}, "concept_id": None})
    prior = state.get("weeks", {}).get(week)
    if prior and not a.revise:
        print(json.dumps({"skipped": True, "week": week, "doi": prior.get("doi")}))
        return 0
    files = gather(week)
    if "tacet/index.json" not in files or "tacet/targets.json" not in files:
        print(json.dumps({"error": "tacet index/targets missing; abort"}))
        return 3
    s = stats(files)
    files["DATASHEET.md"] = datasheet(week, s).encode()
    files["METHODS.md"] = methods(week, s).encode()
    manifest = {"week": week, "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "stats": s,
                "files": [{"path": k, "bytes": len(v), "sha256": hashlib.sha256(v).hexdigest()} for k, v in sorted(files.items())]}
    files["MANIFEST.json"] = (json.dumps(manifest, indent=1) + "\n").encode()
    rev = (prior or {}).get("revision", 1) + 1 if prior else 1
    version = week if rev == 1 else f"{week}-r{rev}"
    meta = metadata(week, version, s)
    if a.dry_run:
        print(json.dumps({"week": week, "version": version, "files": len(files), "bytes": sum(map(len, files.values())), "stats": s, "title": meta["metadata"]["title"]}, indent=1))
        return 0
    pub, err = deposit(files, meta, state.get("concept_id"))
    if err:
        print(json.dumps({"error": err}))
        return 4
    rec = {"doi": pub.get("doi") or pub["metadata"].get("doi"), "concept_doi": pub.get("conceptdoi"), "html": pub["links"].get("html") or pub["links"].get("record_html"),
           "id": pub["id"], "version": version, "revision": rev, "published_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    state.setdefault("weeks", {})[week] = rec
    state["concept_id"] = state.get("concept_id") or rec["id"]
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))
    print(json.dumps({"published": True, "week": week, **rec}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
