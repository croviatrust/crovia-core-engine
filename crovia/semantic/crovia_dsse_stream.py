"""
CROVIA – DSSE Streaming Utilities

Allows applying DSSE v2.1 to arbitrarily large datasets using
chunked streaming (avoids memory blow-up).
"""

import numpy as np
from crovia_dsse_v2 import dsse_v21, dsse_compare, normalize_rows

def dsse_streaming(F_source, B_source, W, chunk=5000):
    """
    Generator-based streaming DSSE processing.

    F_source, B_source must yield chunks of arrays (n, dF) and (n, dB).

    Returns:
        aggregated cosine and angle vectors.
    """
    cos_all = []
    angle_all = []

    for F, B in zip(F_source, B_source):
        rec, tgt = dsse_v21(F, B, W)
        stats = dsse_compare(rec, tgt)

        cos_all.append(stats["cos_mean"])
        angle_all.append(stats["angle_mean"])

        yield stats  # per-chunk report

    return cos_all, angle_all

