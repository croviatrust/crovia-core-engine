"""Shared helpers for the Phase 0 post-processors (stdlib only, Python 3.10+)."""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

INTERNAL_TARGET_PATTERNS = [
    r"^spider:", r"^tpa_v1$", r"^autonomous_observer$", r"^forensic_dossier$", r"^oracle_scanner$",
    r"^wayback_hf_collector$", r"^robots_txt_collector$", r"^arxiv_paper_collector$", r"^axiom_ledger",
    r"^/", r"^test-", r"^croviatrust/", r"^Crovia/", r"_collector$",
]
_INTERNAL = [re.compile(p, re.I) for p in INTERNAL_TARGET_PATTERNS]
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")

PAUSE_THRESHOLD_DAYS = 7


def is_model_target(target_id: Any) -> bool:
    """True iff `target_id` looks like an org/model id and is not internal infrastructure."""
    if not isinstance(target_id, str) or not _MODEL_ID.match(target_id):
        return False
    return not any(p.search(target_id) for p in _INTERNAL)


def parse_ts(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or len(value) < 10:
        return None
    v = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        try:
            dt = datetime.fromisoformat(v[:19])
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now() -> datetime:
    return datetime.now(timezone.utc)


def days_between(a: Optional[datetime], b: Optional[datetime]) -> int:
    if a is None or b is None:
        return 0
    return max(0, int((b - a).total_seconds() // 86400))


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(path: Path, obj: Any) -> None:
    """Write via temp file + rename so nginx never serves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def iter_jsonl(path: Path, must_contain: Optional[str] = None) -> Iterator[Dict[str, Any]]:
    """Stream a JSONL file. `must_contain` is a cheap substring prefilter applied before
    json.loads: the production ledger is several GB, and most callers need one axiom type."""
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if must_contain and must_contain not in line:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def envelope_target(env: Dict[str, Any]) -> Any:
    """crovia.axiom.v1 keeps the target under subject.target_id; older shapes at top level."""
    for container in (env.get("subject"), env.get("body"), env):
        if isinstance(container, dict) and container.get("target_id") is not None:
            return container.get("target_id")
    return None


def envelope_time(env: Dict[str, Any]) -> Optional[datetime]:
    subj = env.get("subject") if isinstance(env.get("subject"), dict) else {}
    body = env.get("body") if isinstance(env.get("body"), dict) else {}
    for src, k in ((subj, "observed_at"), (env, "observed_at"), (body, "observed_at"), (env, "emitted_at"),
                   (env, "issued_at"), (env, "sealed_at"), (env, "timestamp")):
        t = parse_ts(src.get(k))
        if t:
            return t
    return None


def observation_status(last_seen: Optional[datetime], reference: Optional[datetime] = None) -> Dict[str, Any]:
    """Canon §4: silence figures always carry the last observation date and a pause flag."""
    ref = reference or now()
    if last_seen is None:
        return {"state": "never_observed", "last_observation_at": None, "paused_since": None}
    gap = (ref - last_seen).total_seconds() / 86400
    if gap > PAUSE_THRESHOLD_DAYS:
        return {"state": "paused", "last_observation_at": iso(last_seen), "paused_since": iso(last_seen),
                "paused_days": int(gap)}
    return {"state": "active", "last_observation_at": iso(last_seen), "paused_since": None}
