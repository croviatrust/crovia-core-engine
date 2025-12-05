from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable

PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")


class SpiderValidationError(Exception):
    pass


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise SpiderValidationError(msg)


def validate_spider_receipt(obj: Dict[str, Any]) -> None:
    """
    Validate a `spider_receipt.v1` object according to the spec.

    Raises SpiderValidationError on failure.
    """

    _expect(obj.get("schema") == "spider_receipt.v1", "schema must be 'spider_receipt.v1'")
    _expect(obj.get("version") == "1.0.0", "version must be '1.0.0'")

    receipt_id = obj.get("receipt_id")
    _expect(isinstance(receipt_id, str), "receipt_id must be a string")
    _expect(receipt_id.startswith("sr_sha256:"), "receipt_id must start with 'sr_sha256:'")
    _expect(len(receipt_id.split("sr_sha256:")[-1]) == 64, "receipt_id must have 64 hex chars")

    content_id = obj.get("content_id")
    _expect(isinstance(content_id, str), "content_id must be a string")
    _expect(content_id.startswith("cid:"), "content_id must start with 'cid:'")
    _expect("sha256:" in content_id, "content_id must contain sha256 method suffix")

    source_url = obj.get("source_url")
    _expect(isinstance(source_url, str) and source_url, "source_url must be a non-empty string")

    retrieved_at = obj.get("retrieved_at")
    _expect(isinstance(retrieved_at, str) and retrieved_at, "retrieved_at must be a non-empty string")

    dataset_origin = obj.get("dataset_origin")
    _expect(isinstance(dataset_origin, str) and dataset_origin, "dataset_origin must be a non-empty string")

    period = obj.get("period")
    _expect(isinstance(period, str) and PERIOD_RE.match(period), "period must be 'YYYY-MM'")

    links = obj.get("links")
    _expect(isinstance(links, list), "links must be an array (can be empty)")

    # Optional fields: license_hint, metadata, corpus_hint are free-form in v1


def iter_validate_ndjson(lines: Iterable[str]) -> Dict[str, int]:
    """
    Validate many NDJSON lines and return basic stats:
    { "total": N, "ok": K, "failed": M }
    """
    total = ok = failed = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        total += 1
        try:
            obj = json.loads(line)
            validate_spider_receipt(obj)
            ok += 1
        except Exception:
            failed += 1
    return {"total": total, "ok": ok, "failed": failed}
