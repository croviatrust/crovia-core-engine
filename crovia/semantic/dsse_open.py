"""
crovia.semantic.dsse_open
-------------------------

Open-core DSSE (Dataset Semantic Signature Engine)

This module provides a lightweight semantic fingerprint for datasets.
It is intentionally simple compared to the PRO DSSE, but keeps the
same spirit: detect semantic consistency, drift, and global signal quality.
"""

from __future__ import annotations
import re
from typing import List, Dict, Any


class DSSEOpenResult:
    def __init__(self, coherence: float, drift: float, signal: str, notes: str):
        self.coherence = coherence
        self.drift = drift
        self.signal = signal
        self.notes = notes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "semantic_coherence": self.coherence,
            "semantic_drift": self.drift,
            "signal_strength": self.signal,
            "notes": self.notes,
        }


class DSSEOpenEngine:
    """
    Open-core semantic engine.
    Works on lists of strings (tokens, lines, samples).
    """

    def analyze(self, samples: List[str]) -> DSSEOpenResult:
        if not samples:
            return DSSEOpenResult(
                coherence=0.0,
                drift=1.0,
                signal="none",
                notes="Empty dataset",
            )

        # word-count per sample
        lengths = [len(re.findall(r"\w+", s)) for s in samples]
        avg = sum(lengths) / len(lengths)

        # coherence: quanto sono simili le lunghezze
        var = sum((l - avg) ** 2 for l in lengths) / len(lengths)
        # normalizziamo var/avg in [0,1] e la invertiamo per la coerenza
        ratio = var / (avg + 1e-9)
        if ratio > 1.0:
            ratio = 1.0
        coherence = max(0.0, 1.0 - ratio)
        drift = ratio

        # segnale semantico "easy"
        if avg > 20 and coherence > 0.7:
            signal = "high"
        elif avg > 10:
            signal = "medium"
        else:
            signal = "low"

        notes = f"DSSE Open: avg_len={avg:.2f}, coherence={coherence:.3f}, drift={drift:.3f}"

        return DSSEOpenResult(coherence, drift, signal, notes)
