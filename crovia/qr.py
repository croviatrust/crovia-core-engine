# crovia/qr.py
"""
Crovia QR Generator

Generates a QR code for:
- crovia_id
- bundle hash
- local or remote URI (future-proof)

QR payload is JSON, not a bare string.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

try:
    import qrcode
except Exception as e:
    raise RuntimeError(
        "Missing dependency: qrcode\n"
        "Install with: pip install qrcode[pil]"
    ) from e


def generate_qr(
    *,
    payload: Dict[str, Any],
    out_png: Path,
) -> Path:
    out_png.parent.mkdir(parents=True, exist_ok=True)

    data = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    img = qrcode.make(data)
    img.save(out_png)

    return out_png
