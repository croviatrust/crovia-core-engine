from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, Iterable, IO, Optional


PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")


@dataclass
class SpiderReceipt:
    """
    In-memory representation of a `spider_receipt.v1`.

    Note: `receipt_id` is added after construction via `create_spider_receipt`.
    """

    schema: str
    version: str
    content_id: str
    source_url: str
    retrieved_at: str
    dataset_origin: str
    period: str
    corpus_hint: Optional[str] = None
    license_hint: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    links: Optional[list[Dict[str, str]]] = None
    receipt_id: Optional[str] = None

    def to_dict(self, include_receipt_id: bool = True) -> Dict[str, Any]:
        data = asdict(self)
        if not include_receipt_id:
            data.pop("receipt_id", None)
        # Remove keys that are None for cleaner JSON
        return {k: v for k, v in data.items() if v is not None}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonicalize_url(url: str) -> str:
    """
    Conservative URL canonicalization for `cid:url_sha256`:

    - strip leading/trailing whitespace
    - lower-case
    - remove fragment (#...)
    - strip trailing slash (except for the root '/')
    """
    u = url.strip()
    if not u:
        return u
    u = u.lower()
    if "#" in u:
        u = u.split("#", 1)[0]
    if len(u) > 1 and u.endswith("/"):
        u = u.rstrip("/")
    return u


def make_content_id_from_url(url: str) -> str:
    canonical = canonicalize_url(url)
    digest = sha256(canonical.encode("utf-8")).hexdigest()
    return f"cid:url_sha256:{digest}"


def normalize_json_for_hash(obj: Dict[str, Any]) -> str:
    """
    Normalize JSON object to a deterministic string for hashing:

    - sort keys
    - no extra whitespace
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def compute_receipt_id(payload_without_id: Dict[str, Any]) -> str:
    normalized = normalize_json_for_hash(payload_without_id)
    digest = sha256(normalized.encode("utf-8")).hexdigest()
    return f"sr_sha256:{digest}"


def create_spider_receipt(
    *,
    source_url: str,
    dataset_origin: str,
    period: str,
    retrieved_at: Optional[str] = None,
    license_hint: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    corpus_hint: Optional[str] = None,
    links: Optional[list[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Build a `spider_receipt.v1` dict and attach `receipt_id`.

    This is the canonical entrypoint for building receipts programmatically.
    """

    if not PERIOD_RE.match(period):
        raise ValueError(f"Invalid period format (expected YYYY-MM): {period}")

    if retrieved_at is None:
        retrieved_at = utc_now_iso()

    content_id = make_content_id_from_url(source_url)

    receipt = SpiderReceipt(
        schema="spider_receipt.v1",
        version="1.0.0",
        content_id=content_id,
        source_url=source_url,
        retrieved_at=retrieved_at,
        dataset_origin=dataset_origin,
        period=period,
        corpus_hint=corpus_hint,
        license_hint=license_hint,
        metadata=metadata or None,
        links=links or [],
    )

    payload_no_id = receipt.to_dict(include_receipt_id=False)
    receipt_id = compute_receipt_id(payload_no_id)
    receipt.receipt_id = receipt_id

    return receipt.to_dict(include_receipt_id=True)


def write_ndjson(stream: IO[str], objs: Iterable[Dict[str, Any]]) -> int:
    """
    Write an iterable of dicts as NDJSON to the given stream.
    Returns the number of lines written.
    """
    count = 0
    for obj in objs:
        stream.write(json.dumps(obj, ensure_ascii=False) + "\n")
        count += 1
    return count
