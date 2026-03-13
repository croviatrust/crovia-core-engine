#!/usr/bin/env python3

import json
import os
import sys
import hashlib
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests


TPR_API_URL_DEFAULT = "https://registry.croviatrust.com"


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fetch_json(url: str, timeout: int = 15) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    import time as _time
    meta: Dict[str, Any] = {"url": url}
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=timeout)
            meta["http_status"] = r.status_code
            meta["fetched_at"] = _now_iso()
            if r.status_code == 429:
                wait = 60 * (attempt + 1)  # 60s, 120s, 180s
                meta["error"] = f"HTTP 429 (retry {attempt+1}, wait {wait}s)"
                _time.sleep(wait)
                continue
            if r.status_code != 200:
                meta["error"] = f"HTTP {r.status_code}"
                return None, meta
            return r.json(), meta
        except Exception as e:
            meta["error"] = f"{type(e).__name__}: {e}"
            meta["fetched_at"] = _now_iso()
            return None, meta
    return None, meta


def _fetch_text(url: str, timeout: int = 15) -> Tuple[Optional[str], Dict[str, Any]]:
    import time as _time
    meta: Dict[str, Any] = {"url": url}
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=timeout)
            meta["http_status"] = r.status_code
            meta["fetched_at"] = _now_iso()
            if r.status_code == 429:
                wait = 60 * (attempt + 1)
                meta["error"] = f"HTTP 429 (retry {attempt+1}, wait {wait}s)"
                _time.sleep(wait)
                continue
            if r.status_code != 200:
                meta["error"] = f"HTTP {r.status_code}"
                return None, meta
            return r.text, meta
        except Exception as e:
            meta["error"] = f"{type(e).__name__}: {e}"
            meta["fetched_at"] = _now_iso()
            return None, meta
    return None, meta


def _readme_access(readme_meta: Dict[str, Any]) -> str:
    try:
        status = int(readme_meta.get("http_status")) if readme_meta.get("http_status") is not None else None
        if status == 200:
            return "ok"
        if status in (401, 403):
            return "forbidden"
        if status == 404:
            return "not_found"
        if status is not None:
            return "error"
    except Exception:
        return "error"
    return "unknown"


def _ddf_material(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Return a stable subset used to compute ddf_hash.

    IMPORTANT: exclude volatile fields like observed_at and sources.fetched_at.
    """
    extracted = (snapshot.get("extracted") if isinstance(snapshot, dict) else None) or {}
    hashes = (snapshot.get("hashes") if isinstance(snapshot, dict) else None) or {}
    return {
        "schema": snapshot.get("schema"),
        "target_id": snapshot.get("target_id"),
        "tipo_target": snapshot.get("tipo_target"),
        "extracted": {
            "license": extracted.get("license"),
            "declared_datasets": extracted.get("declared_datasets"),
            "tags_hash": extracted.get("tags_hash"),
            "language_hash": extracted.get("language_hash"),
            "has_training_section": extracted.get("has_training_section"),
            "readme_access": extracted.get("readme_access"),
        },
        "hashes": {
            "card_hash": hashes.get("card_hash"),
            "readme_hash": hashes.get("readme_hash"),
        },
    }


def _hf_api_url(tipo_target: str, target_id: str) -> Optional[str]:
    if tipo_target == "model":
        return f"https://huggingface.co/api/models/{target_id}"
    if tipo_target == "dataset":
        return f"https://huggingface.co/api/datasets/{target_id}"
    return None


def _hf_readme_url(tipo_target: str, target_id: str) -> Optional[str]:
    if tipo_target == "model":
        return f"https://huggingface.co/{target_id}/raw/main/README.md"
    if tipo_target == "dataset":
        return f"https://huggingface.co/datasets/{target_id}/raw/main/README.md"
    return None


def _load_targets_from_registry(tpr_api_url: str, timeout: int = 10) -> List[Dict[str, Any]]:
    url = f"{tpr_api_url}/api/targets/summary"
    data, meta = _fetch_json(url, timeout=timeout)
    if data is None:
        raise RuntimeError(f"Failed to load targets from registry: {meta.get('error') or meta}")
    targets = data.get("targets", []) or []
    out: List[Dict[str, Any]] = []
    for t in targets:
        tid = t.get("target_id")
        ttype = t.get("tipo_target")
        if not tid or not ttype:
            continue
        out.append({"target_id": str(tid), "tipo_target": str(ttype)})
    return out


def _load_targets_from_file(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "targets" in data:
        data = data["targets"]
    if not isinstance(data, list):
        raise ValueError("targets file must be a list or {targets:[...]} JSON")
    out: List[Dict[str, Any]] = []
    for t in data:
        if not isinstance(t, dict):
            continue
        tid = t.get("target_id") or t.get("id") or t.get("name")
        ttype = t.get("tipo_target") or t.get("type")
        if not tid or not ttype:
            continue
        out.append({"target_id": str(tid), "tipo_target": str(ttype)})
    return out


def compute_ddf_snapshot(
    target_id: str,
    tipo_target: str,
    timeout: int = 15,
    prev_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    api_url = _hf_api_url(tipo_target, target_id)
    readme_url = _hf_readme_url(tipo_target, target_id)

    api_json: Optional[Dict[str, Any]] = None
    api_meta: Dict[str, Any] = {}
    if api_url:
        api_json, api_meta = _fetch_json(api_url, timeout=timeout)

    # Incremental mode: if card_hash unchanged, reuse previous README data
    _reused_readme = False
    if prev_snapshot is not None and isinstance(api_json, dict):
        card_data_now = (api_json.get("cardData") or {})
        card_canonical_now = json.dumps(card_data_now, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        card_hash_now = _sha256_hex(card_canonical_now)
        prev_card_hash = ((prev_snapshot.get("hashes") or {}).get("card_hash") or "")
        if card_hash_now and card_hash_now == prev_card_hash:
            prev_sources = prev_snapshot.get("sources") or {}
            readme_meta = prev_sources.get("hf_readme") or {}
            readme_meta["reused_from_prev"] = True
            _reused_readme = True

    readme_text: Optional[str] = None
    if not _reused_readme:
        readme_meta: Dict[str, Any] = {}
        if readme_url:
            readme_text, readme_meta = _fetch_text(readme_url, timeout=timeout)

    readme_access = _readme_access(readme_meta)

    card_data = (api_json.get("cardData") if isinstance(api_json, dict) else None) or {}

    license_val = card_data.get("license") if isinstance(card_data, dict) else None
    declared_datasets = card_data.get("datasets") if isinstance(card_data, dict) else None

    tags_val = api_json.get("tags") if isinstance(api_json, dict) else None
    lang_val = card_data.get("language") if isinstance(card_data, dict) else None

    # Extract popularity/access metrics (observational only)
    downloads = api_json.get("downloads") if isinstance(api_json, dict) else None
    likes = api_json.get("likes") if isinstance(api_json, dict) else None
    gated = api_json.get("gated") if isinstance(api_json, dict) else None
    private = api_json.get("private") if isinstance(api_json, dict) else None

    tags_list: List[str] = []
    if isinstance(tags_val, list):
        tags_list = [str(x) for x in tags_val if x is not None]
    elif isinstance(tags_val, str):
        tags_list = [tags_val]

    lang_list: List[str] = []
    if isinstance(lang_val, list):
        lang_list = [str(x) for x in lang_val if x is not None]
    elif isinstance(lang_val, str):
        lang_list = [lang_val]

    if _reused_readme and prev_snapshot is not None:
        prev_extracted = (prev_snapshot.get("extracted") or {})
        has_training_section = prev_extracted.get("has_training_section", False)
        readme_hash = (prev_snapshot.get("hashes") or {}).get("readme_hash")
    else:
        has_training_section = False
        if readme_text:
            has_training_section = bool(re.search(r"^##\s+training\b", readme_text, flags=re.IGNORECASE | re.MULTILINE))
        readme_hash = _sha256_hex(readme_text) if readme_text else None

    card_canonical = json.dumps(card_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    card_hash = _sha256_hex(card_canonical)

    snapshot: Dict[str, Any] = {
        "schema": "crovia.open.ddf_snapshot.v3",
        "target_id": target_id,
        "tipo_target": tipo_target,
        "observed_at": _now_iso(),
        "sources": {
            "hf_api": api_meta,
            "hf_readme": readme_meta,
        },
        "extracted": {
            "license": license_val,
            "declared_datasets": declared_datasets,
            "tags_count": len(tags_list),
            "tags_sample": tags_list[:25],
            "tags_hash": _sha256_hex(json.dumps(tags_list, sort_keys=True, separators=(",", ":"), ensure_ascii=True)),
            "language_count": len(lang_list),
            "language_sample": lang_list[:25],
            "language_hash": _sha256_hex(json.dumps(lang_list, sort_keys=True, separators=(",", ":"), ensure_ascii=True)),
            "has_training_section": has_training_section,
            "readme_access": readme_access,
        },
        "popularity": {
            "downloads": downloads,
            "likes": likes,
        },
        "access": {
            "gated": gated,
            "private": private,
        },
        "hashes": {
            "card_hash": card_hash,
            "readme_hash": readme_hash,
        },
    }

    canonical = json.dumps(_ddf_material(snapshot), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    snapshot["hashes"]["ddf_hash"] = _sha256_hex(canonical)
    return snapshot


def _load_previous_snapshots(path: str) -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(path):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                tid = row.get("target_id")
                if tid:
                    out[str(tid)] = row
            except Exception:
                continue
    return out


def _load_existing_events(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _load_existing_timeline(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    out.append(row)
            except Exception:
                continue
    return out


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _presence_status(v: Any) -> str:
    if v is True:
        return "PRESENT"
    if v is False:
        return "ABSENT"
    if v is None:
        return "UNKNOWN"
    if isinstance(v, str) and v.strip():
        s = v.strip().upper()
        if s in ("PRESENT", "ABSENT", "UNKNOWN"):
            return s
    return "UNKNOWN"


def _readme_access_status(v: Any) -> str:
    if v is None:
        return "UNKNOWN"
    if isinstance(v, str):
        s = v.strip().lower()
        if s == "ok":
            return "OK"
        if s in ("not_found", "notfound"):
            return "NOT_FOUND"
        if s in ("forbidden", "unauthorized"):
            return "FORBIDDEN"
        if s == "error":
            return "ERROR"
        if s == "unknown":
            return "UNKNOWN"
    return "UNKNOWN"


def _migrate_timeline_row(row: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(row, dict):
        return row

    schema = str(row.get("schema") or "")
    if schema in ("crovia.open.statement_timeline_event.v1", "crovia.open.statement_timeline_event.v2"):
        statements = row.get("statements") if isinstance(row.get("statements"), dict) else {}
        if isinstance(statements, dict):
            if "has_training_section" in statements and "training_section_presence" not in statements:
                statements["training_section_presence"] = _presence_status(statements.get("has_training_section"))
                statements.pop("has_training_section", None)
            if "readme_access" in statements:
                statements["readme_access"] = _readme_access_status(statements.get("readme_access"))
            row["statements"] = statements
        row["schema"] = "crovia.open.statement_timeline_event.v2"

    if schema == "crovia.open.ddf_drift_event.v1":
        coverage = row.get("coverage") if isinstance(row.get("coverage"), dict) else {}
        if isinstance(coverage, dict) and "readme_access" in coverage:
            coverage["readme_access"] = _readme_access_status(coverage.get("readme_access"))
            row["coverage"] = coverage

    return row


def export_ddf(
    dataset_root: str,
    targets: List[Dict[str, Any]],
    limit: Optional[int] = None,
    timeout: int = 15,
) -> Tuple[str, str, str, str, int, int, int]:
    drift_dir = os.path.join(dataset_root, "open", "drift")
    os.makedirs(drift_dir, exist_ok=True)

    temporal_dir = os.path.join(dataset_root, "open", "temporal")
    os.makedirs(temporal_dir, exist_ok=True)

    snapshots_path = os.path.join(drift_dir, "ddf_snapshots_latest.jsonl")
    events_path = os.path.join(drift_dir, "ddf_drift_events_30d.jsonl")

    timeline_path = os.path.join(temporal_dir, "statement_timeline_30d.jsonl")
    timeline_index_path = os.path.join(temporal_dir, "statement_timeline_index.json")

    prev = _load_previous_snapshots(snapshots_path)
    existing_events = _load_existing_events(events_path)
    existing_timeline = _load_existing_timeline(timeline_path)
    existing_timeline = [_migrate_timeline_row(r) for r in existing_timeline]

    targets_sorted = sorted(
        [t for t in targets if t.get("target_id") and t.get("tipo_target")],
        key=lambda x: (str(x.get("tipo_target")), str(x.get("target_id"))),
    )

    if limit is not None:
        targets_sorted = targets_sorted[: int(limit)]

    snapshots: List[Dict[str, Any]] = []
    drift_events: List[Dict[str, Any]] = []
    timeline_events_new: List[Dict[str, Any]] = []

    progress_every_env = os.getenv("CROVIA_DDF_PROGRESS_EVERY")
    progress_every = int(progress_every_env) if progress_every_env and progress_every_env.strip().isdigit() else 10
    total = len(targets_sorted)

    schema_migrated = False
    incremental = os.getenv("CROVIA_DDF_INCREMENTAL", "0").strip() == "1"
    reused_count = 0

    # Build a "last seen" hash map from existing timeline so we only write events on change.
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    last_ddf_by_target: Dict[str, str] = {}
    for ev in existing_timeline:
        tid = str(ev.get("target_id") or "").strip()
        if not tid:
            continue
        ts = _parse_iso(str(ev.get("observed_at") or ""))
        if ts is None or ts < cutoff:
            continue
        ddf_hash = str(ev.get("ddf_hash") or "").strip()
        if ddf_hash:
            last_ddf_by_target[tid] = ddf_hash

    # Rate limiting: stay under HF API quota (default 2000 req/h, leaves room for observer+outreach)
    max_rph = int(os.getenv("CROVIA_DDF_MAX_RPH", "2000"))
    min_delay = 3600.0 / max_rph if max_rph > 0 else 1.0  # seconds between calls
    api_calls = 0
    rate_limit_pauses = 0
    _last_call_time = 0.0
    print(f"[DDF] Rate limit: {max_rph} req/h → min {min_delay:.2f}s between calls", flush=True)

    for i, t in enumerate(targets_sorted, start=1):
        tid = str(t["target_id"]).strip()
        ttype = str(t["tipo_target"]).strip().lower()
        if ttype not in ("model", "dataset"):
            continue

        # Enforce rate limit
        now_mono = time.monotonic()
        elapsed = now_mono - _last_call_time
        if elapsed < min_delay and _last_call_time > 0:
            sleep_for = min_delay - elapsed
            time.sleep(sleep_for)
            rate_limit_pauses += 1
        _last_call_time = time.monotonic()

        prev_snap = prev.get(tid) if incremental else None
        snap = compute_ddf_snapshot(tid, ttype, timeout=timeout, prev_snapshot=prev_snap)
        api_calls += 2 if not ((snap.get("sources") or {}).get("hf_readme") or {}).get("reused_from_prev") else 1
        if prev_snap is not None and ((snap.get("sources") or {}).get("hf_readme") or {}).get("reused_from_prev"):
            reused_count += 1
        snapshots.append(snap)

        # Statement Timeline Registry event (dedup per target by ddf_hash)
        new_ddf_hash = str(((snap.get("hashes") or {}).get("ddf_hash")) or "").strip()
        prev_ddf_hash = last_ddf_by_target.get(tid)
        if new_ddf_hash and new_ddf_hash != prev_ddf_hash:
            extracted = (snap.get("extracted") if isinstance(snap.get("extracted"), dict) else None) or {}
            timeline_events_new.append({
                "schema": "crovia.open.statement_timeline_event.v2",
                "target_id": tid,
                "tipo_target": ttype,
                "observed_at": snap.get("observed_at"),
                "ddf_hash": new_ddf_hash,
                "hashes": {
                    "card_hash": (snap.get("hashes") or {}).get("card_hash"),
                    "readme_hash": (snap.get("hashes") or {}).get("readme_hash"),
                },
                "statements": {
                    "license": extracted.get("license"),
                    "declared_datasets": extracted.get("declared_datasets"),
                    "training_section_presence": _presence_status(extracted.get("has_training_section")),
                    "readme_access": _readme_access_status(extracted.get("readme_access")),
                },
                "coverage": {
                    "hf_api_status": ((snap.get("sources") or {}).get("hf_api") or {}).get("http_status"),
                    "hf_readme_status": ((snap.get("sources") or {}).get("hf_readme") or {}).get("http_status"),
                },
            })
            last_ddf_by_target[tid] = new_ddf_hash

        if progress_every > 0 and (i == 1 or i % progress_every == 0 or i == total):
            api_status = ((snap.get("sources") or {}).get("hf_api") or {}).get("http_status")
            readme_status = ((snap.get("sources") or {}).get("hf_readme") or {}).get("http_status")
            print(f"[CROVIA] progress {i}/{total} {ttype}:{tid} api={api_status} readme={readme_status} [api_calls={api_calls} reused={reused_count}]", flush=True)

        prev_row = prev.get(tid)
        prev_schema = (prev_row or {}).get("schema")
        prev_hash = ((prev_row or {}).get("hashes") or {}).get("ddf_hash")
        new_hash = (snap.get("hashes") or {}).get("ddf_hash")

        # If schema/hash method changed, treat as baseline to avoid mass false drift.
        if prev_schema and prev_schema != snap.get("schema"):
            schema_migrated = True
            prev_hash = None

        if prev_hash and new_hash and prev_hash != new_hash:
            # ANTI-FALSE-POSITIVE: Skip drift if current observation has critical errors
            curr_sources = snap.get("sources", {})
            has_critical_error = False
            for src_name, src_data in curr_sources.items():
                if isinstance(src_data, dict):
                    error = src_data.get("error", "")
                    http_status = src_data.get("http_status")
                    if error and ("timeout" in str(error).lower() or "connection" in str(error).lower()):
                        has_critical_error = True
                        break
                    if src_name == "hf_api" and http_status and http_status != 200:
                        has_critical_error = True
                        break
            
            if has_critical_error:
                # Don't record drift event - data quality issue, not real change
                continue
            
            # Compute direction-of-change for key fields (observational only)
            prev_extracted = (prev_row.get("extracted") if isinstance(prev_row.get("extracted"), dict) else None) or {}
            curr_extracted = (snap.get("extracted") if isinstance(snap.get("extracted"), dict) else None) or {}
            
            changes: Dict[str, Dict[str, Any]] = {}
            
            # Training section change - with README hash for forensic tracing
            prev_ts = prev_extracted.get("has_training_section")
            curr_ts = curr_extracted.get("has_training_section")
            if prev_ts != curr_ts:
                prev_hashes = (prev_row.get("hashes") if isinstance(prev_row.get("hashes"), dict) else None) or {}
                curr_hashes = (snap.get("hashes") if isinstance(snap.get("hashes"), dict) else None) or {}
                changes["training_section"] = {
                    "before": _presence_status(prev_ts),
                    "after": _presence_status(curr_ts),
                    "readme_hash_before": prev_hashes.get("readme_hash"),
                    "readme_hash_after": curr_hashes.get("readme_hash"),
                }
            
            # Tags change - track WHAT tags were added/removed
            prev_tags = prev_extracted.get("tags_sample") or []
            curr_tags = curr_extracted.get("tags_sample") or []
            if prev_tags != curr_tags:
                prev_tags_set = set(prev_tags) if isinstance(prev_tags, list) else set()
                curr_tags_set = set(curr_tags) if isinstance(curr_tags, list) else set()
                tags_added = sorted(list(curr_tags_set - prev_tags_set))
                tags_removed = sorted(list(prev_tags_set - curr_tags_set))
                if tags_added or tags_removed:
                    changes["tags"] = {
                        "before_count": len(prev_tags_set),
                        "after_count": len(curr_tags_set),
                        "added": tags_added if tags_added else None,
                        "removed": tags_removed if tags_removed else None,
                    }
            
            # License change
            prev_lic = prev_extracted.get("license")
            curr_lic = curr_extracted.get("license")
            if prev_lic != curr_lic:
                changes["license"] = {
                    "before": prev_lic,
                    "after": curr_lic,
                }
            
            # Declared datasets change - FULL TRACKING (WHAT was added/removed)
            prev_decl = prev_extracted.get("declared_datasets") or []
            curr_decl = curr_extracted.get("declared_datasets") or []
            if prev_decl != curr_decl:
                prev_set = set(prev_decl) if isinstance(prev_decl, list) else set()
                curr_set = set(curr_decl) if isinstance(curr_decl, list) else set()
                added = sorted(list(curr_set - prev_set))
                removed = sorted(list(prev_set - curr_set))
                changes["declared_datasets"] = {
                    "before_count": len(prev_set),
                    "after_count": len(curr_set),
                    "delta": len(curr_set) - len(prev_set),
                    "before_list": sorted(list(prev_set)) if prev_set else None,
                    "after_list": sorted(list(curr_set)) if curr_set else None,
                    "added": added if added else None,
                    "removed": removed if removed else None,
                }
            
            # README access change
            prev_readme = prev_extracted.get("readme_access")
            curr_readme = curr_extracted.get("readme_access")
            if prev_readme != curr_readme:
                changes["readme_access"] = {
                    "before": _readme_access_status(prev_readme),
                    "after": _readme_access_status(curr_readme),
                }
            
            # Popularity changes (if available in prev snapshot)
            prev_pop = (prev_row.get("popularity") if isinstance(prev_row.get("popularity"), dict) else None) or {}
            curr_pop = (snap.get("popularity") if isinstance(snap.get("popularity"), dict) else None) or {}
            if prev_pop.get("downloads") is not None and curr_pop.get("downloads") is not None:
                dl_delta = (curr_pop.get("downloads") or 0) - (prev_pop.get("downloads") or 0)
                if dl_delta != 0:
                    changes["downloads"] = {
                        "before": prev_pop.get("downloads"),
                        "after": curr_pop.get("downloads"),
                        "delta": dl_delta,
                    }
            
            # Compute data quality score for this event
            api_status = ((snap.get("sources") or {}).get("hf_api") or {}).get("http_status")
            readme_status = ((snap.get("sources") or {}).get("hf_readme") or {}).get("http_status")
            quality_ok = (api_status == 200) and (readme_status in [200, 404])  # 404 is valid (no readme)
            
            drift_events.append({
                "schema": "crovia.open.ddf_drift_event.v3",  # v3: with quality flag
                "target_id": tid,
                "tipo_target": ttype,
                "observed_at": snap.get("observed_at"),
                "prev_ddf_hash": prev_hash,
                "new_ddf_hash": new_hash,
                "changes": changes if changes else None,
                "hashes": {
                    "card_hash": (snap.get("hashes") or {}).get("card_hash"),
                    "readme_hash": (snap.get("hashes") or {}).get("readme_hash"),
                },
                "coverage": {
                    "readme_access": _readme_access_status(((snap.get("extracted") or {}).get("readme_access"))),
                },
                "quality": {
                    "data_quality_ok": quality_ok,
                    "api_status": api_status,
                    "readme_status": readme_status,
                },
                "popularity": snap.get("popularity"),
                "sources": snap.get("sources"),
                "note": "Drift event: public disclosure fingerprint changed (no interpretation).",
            })

    # Write latest snapshots (overwrite)
    with open(snapshots_path, "w", encoding="utf-8") as f:
        for row in snapshots:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    
    # ALSO append to history file (never lose data)
    history_path = os.path.join(drift_dir, "ddf_snapshots_history.jsonl")
    with open(history_path, "a", encoding="utf-8") as f:
        for row in snapshots:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # If schema/hash method changed, drop previous drift events (they may be stale/false under the new method).
    if schema_migrated:
        existing_events = []

    # Merge + prune drift events to 30d window
    merged_events = existing_events + drift_events
    pruned: List[Dict[str, Any]] = []
    for ev in merged_events:
        ts = _parse_iso(str(ev.get("observed_at") or ""))
        if ts is None or ts >= cutoff:
            pruned.append(ev)

    pruned_sorted = sorted(pruned, key=lambda x: str(x.get("observed_at") or ""))

    with open(events_path, "w", encoding="utf-8") as f:
        for row in pruned_sorted:
            f.write(json.dumps(_migrate_timeline_row(row), ensure_ascii=False) + "\n")

    # Merge + prune statement timeline events to 30d window
    merged_timeline = existing_timeline + timeline_events_new
    pruned_timeline: List[Dict[str, Any]] = []
    for ev in merged_timeline:
        ts = _parse_iso(str(ev.get("observed_at") or ""))
        if ts is None or ts >= cutoff:
            pruned_timeline.append(ev)

    pruned_timeline_sorted = sorted(pruned_timeline, key=lambda x: str(x.get("observed_at") or ""))
    with open(timeline_path, "w", encoding="utf-8") as f:
        for row in pruned_timeline_sorted:
            f.write(json.dumps(_migrate_timeline_row(row), ensure_ascii=False) + "\n")

    # Build index for viewer/API
    last_change_at: Dict[str, str] = {}
    for ev in pruned_sorted:
        tid = str(ev.get("target_id") or "").strip()
        if not tid:
            continue
        ts = str(ev.get("observed_at") or "")
        if not ts:
            continue
        # pruned_sorted is chronological, so last assignment wins.
        last_change_at[tid] = ts

    index_targets: List[Dict[str, Any]] = []
    for snap in snapshots:
        tid = str(snap.get("target_id") or "").strip()
        ttype = str(snap.get("tipo_target") or "").strip()
        extracted = (snap.get("extracted") if isinstance(snap.get("extracted"), dict) else None) or {}
        ddf_hash = (snap.get("hashes") or {}).get("ddf_hash")
        decl = extracted.get("declared_datasets")
        decl_count = None
        if isinstance(decl, list):
            decl_count = len([x for x in decl if x is not None])

        index_targets.append({
            "target_id": tid,
            "tipo_target": ttype,
            "last_observed_at": snap.get("observed_at"),
            "last_change_at": last_change_at.get(tid),
            "ddf_hash": ddf_hash,
            "readme_access": _readme_access_status(extracted.get("readme_access")),
            "license": extracted.get("license"),
            "declared_datasets_count": decl_count,
            "training_section_presence": _presence_status(extracted.get("has_training_section")),
        })

    index_doc = {
        "schema": "crovia.open.statement_timeline_index.v2",
        "generated_at": _now_iso(),
        "window_days": 30,
        "targets": sorted(index_targets, key=lambda x: (str(x.get("tipo_target") or ""), str(x.get("target_id") or ""))),
    }
    with open(timeline_index_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(index_doc, ensure_ascii=False, indent=2))

    return (
        snapshots_path,
        events_path,
        timeline_path,
        timeline_index_path,
        len(snapshots),
        len(drift_events),
        len(timeline_events_new),
    )


def main() -> int:
    if sys.version_info < (3, 6):
        raise SystemExit("export_ddf_to_hf.py requires Python 3.6+ (f-strings). Run with python3.")

    dataset_root = os.getenv("CROVIA_OPEN_DATASET_DIR") or os.getenv("CROVIA_DATASET_DIR") or os.getcwd()

    tpr_api_url = os.getenv("TPR_API_URL") or TPR_API_URL_DEFAULT
    targets_file = os.getenv("CROVIA_TARGETS_FILE") or os.getenv("TPR_TARGETS_FILE")

    limit_env = os.getenv("CROVIA_DDF_LIMIT")
    limit = int(limit_env) if limit_env and limit_env.strip().isdigit() else None

    timeout_env = os.getenv("CROVIA_DDF_TIMEOUT")
    timeout = int(timeout_env) if timeout_env and timeout_env.strip().isdigit() else 15

    targets: List[Dict[str, Any]]

    # Use file if specified, otherwise fall back to registry
    if targets_file and os.path.exists(targets_file):
        targets = _load_targets_from_file(targets_file)
        source = f"file:{targets_file}"
    else:
        targets = _load_targets_from_registry(tpr_api_url)
        source = f"registry:{tpr_api_url}"

    snapshots_path, events_path, timeline_path, timeline_index_path, snap_n, drift_n, tl_new_n = export_ddf(
        dataset_root=dataset_root,
        targets=targets,
        limit=limit,
        timeout=timeout,
    )

    print(f"[CROVIA] ddf export source={source}")
    print(f"[CROVIA] snapshots_written={snap_n} -> {snapshots_path}")
    print(f"[CROVIA] drift_events_new={drift_n} -> {events_path}")
    print(f"[CROVIA] statement_timeline_events_new={tl_new_n} -> {timeline_path}")
    print(f"[CROVIA] statement_timeline_index_written -> {timeline_index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
