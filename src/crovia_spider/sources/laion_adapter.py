from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterator, Optional, Any

import pandas as pd

from ..core.receipts import create_spider_receipt


def _safe_get(row: Dict[str, Any], *keys: str, default=None):
    """
    Try multiple key variants (e.g. URL / url / image_url).
    """
    for k in keys:
        if k in row and row[k] is not None:
            return row[k]
    return default


def _row_to_spider_receipt(
    row: Dict[str, Any],
    period: str,
    dataset_origin: str,
) -> Dict[str, Any]:
    """
    Convert a single LAION-style metadata row into a spider_receipt.v1 dict.

    Philosophy: **purely documentary**.
    We only record what the metadata declares, we don't fetch or verify URLs.
    """
    url = _safe_get(row, "URL", "url", "image_url")
    if not url:
        # No usable URL → we skip this row at the caller level
        raise ValueError("Missing URL in LAION row")

    license_hint = _safe_get(row, "LICENSE", "license", default="unknown")

    # Confidence + original metadata, as discussed in option A
    metadata = {
        "data_source_type": "metadata_only",
        "confidence": {
            "license": "low",                 # based only on metadata
            "url_status": "unknown",          # we do NOT fetch
            "content_availability": "unknown" # we do NOT fetch
        },
        "original_source": "laion_metadata",
        "original_fields": dict(row),         # full original row for audit
    }

    receipt = create_spider_receipt(
        source_url=str(url),
        dataset_origin=dataset_origin,
        period=period,
        license_hint=str(license_hint) if license_hint is not None else None,
        metadata=metadata,
    )

    return receipt


def iter_laion_spider_receipts(
    metadata_path: Path,
    period: str,
    dataset_origin: str,
    sample: Optional[int] = None,
) -> Iterator[Dict[str, Any]]:
    """
    Yield spider_receipt.v1 dicts from a LAION-style Parquet metadata file.

    - **Purely documentary**: we only parse metadata, no HTTP fetches.
    - Skips rows without a valid URL.
    """
    df = pd.read_parquet(metadata_path)

    if sample is not None and sample > 0:
        df = df.head(sample)

    for _, row in df.iterrows():
        row_dict = row.to_dict()
        try:
            receipt = _row_to_spider_receipt(
                row=row_dict,
                period=period,
                dataset_origin=dataset_origin,
            )
        except Exception:
            # Skip rows that cannot be converted (e.g. missing URL)
            continue
        else:
            yield receipt
