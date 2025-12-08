"""
CROVIA – Semantic Engine (SCE)
--------------------------------

High-level conceptual engine built on top of DSSE v2.1.

The SCE exposes:
- conceptual compression
- dual-space reconstruction
- capsule generation (Crovia-style)
- batch and streaming APIs
- model-agnostic embedding processing

All computations remain interpretable, stable, and reproducible.
"""

import numpy as np

from crovia_dsse_v2 import (
    dsse_v21,
    dsse_compare,
    fast_W,
    normalize_rows
)

# --------------------------------------------------------------
# Semantic Capsule object
# --------------------------------------------------------------

class SemanticCapsule:
    """
    A Crovia conceptual capsule.
    
    Holds:
    - input forward vector
    - reconstructed conceptual vector
    - target backward vector (normalized)
    - metrics (cos, angle)
    """

    def __init__(self, f_raw, f_norm, b_hat, recon, metrics):
        self.f_raw  = f_raw
        self.f_norm = f_norm
        self.b_hat  = b_hat
        self.recon  = recon
        self.metrics = metrics

    def as_dict(self):
        return {
            "f_raw": self.f_raw.tolist(),
            "f_norm": self.f_norm.tolist(),
            "target_concept_b": self.b_hat.tolist(),
            "reconstructed": self.recon.tolist(),
            "metrics": self.metrics
        }


# --------------------------------------------------------------
# Semantic Engine core
# --------------------------------------------------------------

class CroviaSemanticEngine:
    """
    High-level Crovia semantic engine (SCE).

    Handles:
    - initialization of projection matrix W
    - conceptual reconstruction via DSSE v2.1
    - capsule generation
    - batch processing
    - streaming mode
    """

    def __init__(self, dF: int, dB: int, seed: int = 0):
        """
        Initialize engine with a DSSE projection matrix W.
        """
        self.dF = dF
        self.dB = dB
        self.W = fast_W(dF, dB, seed=seed)

    # ----------------------------------------------------------
    # Single-pass conceptual reconstruction
    # ----------------------------------------------------------
    def encode(self, F: np.ndarray, B: np.ndarray):
        """
        Apply DSSE v2.1 to an entire batch.
        Returns reconstructed B★ and normalized B★.
        """
        reconstructed, b_hat = dsse_v21(F, B, self.W)
        stats = dsse_compare(reconstructed, b_hat)
        return reconstructed, b_hat, stats

    # ----------------------------------------------------------
    # Create Crovia semantic capsules
    # ----------------------------------------------------------
    def make_capsules(self, F: np.ndarray, B: np.ndarray):
        """
        Produce Crovia Semantic Capsules from arrays F and B.
        """
        reconstructed, b_hat, stats = self.encode(F, B)
        F_norm = normalize_rows(F)

        capsules = []
        for i in range(F.shape[0]):
            metrics = {
                "cos": float(np.sum(
                    reconstructed[i] / (np.linalg.norm(reconstructed[i]) + 1e-12)
                    *
                    b_hat[i]
                )),
                "angle": float(
                    np.degrees(
                        np.arccos(
                            np.clip(metrics["cos"], -1, 1)
                        )
                    )
                )
            }

            cap = SemanticCapsule(
                f_raw = F[i],
                f_norm = F_norm[i],
                b_hat = b_hat[i],
                recon = reconstructed[i],
                metrics = metrics
            )
            capsules.append(cap)

        return capsules, stats

    # ----------------------------------------------------------
    # Streaming processing
    # ----------------------------------------------------------
    def encode_stream(self, F_source, B_source, chunk=5000):
        """
        Generator that yields per-chunk semantic stats.
        """
        for F, B in zip(F_source, B_source):
            reconstructed, b_hat = dsse_v21(F, B, self.W)
            stats = dsse_compare(reconstructed, b_hat)
            yield stats


# --------------------------------------------------------------
# Convenience API
# --------------------------------------------------------------

def load_engine(dF: int, dB: int, seed: int = 0) -> CroviaSemanticEngine:
    """
    One-line convenience loader for the engine.
    """
    return CroviaSemanticEngine(dF=dF, dB=dB, seed=seed)

