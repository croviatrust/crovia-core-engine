#!/usr/bin/env python3
"""
Convert Crovia Spider output → data_receipt.v1 NDJSON (OPEN CORE)

Purpose:
- Normalize dataset-origin evidence
- NO attribution
- NO royalty logic
- Suitable for public audit & validation
"""

import argparse
import json
import uuid
from urllib.parse import urlparse
from datetime import datetime, timezone


def extract_provider(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host or "unknown_provider"
    except Exception:
        return "unknown_provider"


def convert_line(item: dict, period: str) -> dict:
    sha = (
        item.get("sha256")
        or item.get("url_sha256")
        or item.get("digest")
        or "unknown_sha256"
    )

    url = item.get("url", "")
    license_hint = item.get("license_hint", "unknown")
    title = item.get("title", "")[:200] if item.get("title") else ""

    provider = extract_provider(url)

    return {
        "schema": "data_receipt.v1",
        "id": str(uuid.uuid4()),
        "provider_id": provider,
        "provider_type": "domain" if "." in provider else "entity",
        "content_id": f"cid:{sha}",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "period": period,
        "meta": {
            "license": license_hint,
            "source_url": url,
            "title": title,
            "purpose": "training",
            "region": item.get("region", "unknown"),
            "extracted_from": item.get("source", "crovia_spider")
        }
    }


def main():
    ap = argparse.ArgumentParser(description="Spider → data_receipt.v1 converter")
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--period", required=True)
    args = ap.parse_args()

    total = 0
    with open(args.input, "r", encoding="utf-8") as fin, open(args.out, "w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            item = json.loads(line)
            rec = convert_line(item, args.period)
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            total += 1

    print(f"[OK] Converted {total} records → {args.out}")
    print(f"[TIP] Validate with: python3 crovia_validate.py {args.out}")


if __name__ == "__main__":
    main()
