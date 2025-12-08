"""
CROVIA – DSSE v2.1 (Dual-Space Semantic Engine)

This module implements the new DSSE v2.1 engine, a geometric hybrid
projection method used to combine two semantic spaces (F, B) using:

- geometric blending (C, Δ, Σ)
- primary-space corrections
- eco-trace correction
- α multi-term stabilizer
- final reconstruction preserving DSSE topology

DSSE v2.1 is a conceptual compression + reconstruction engine
used in Crovia for capsule generation and dataset semantic analysis.
"""

import numpy as np

# --------------------------------------------------------------
# Helper
# --------------------------------------------------------------

def normalize_rows(X: np.ndarray) -> np.ndarray:
    """Normalize rows to unit L2 norm."""
    return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)


def fast_W(dF: int, dB: int, seed: int = 0) -> np.ndarray:
    """
    Generate an orthonormal projection matrix W (dF x dB).
    """
    rng = np.random.default_rng(seed)
    A = rng.normal(size=(dF, dB))
    Q, _ = np.linalg.qr(A)
    return Q[:, :dB]


# --------------------------------------------------------------
# DSSE v2.1 core
# --------------------------------------------------------------

def dsse_v21(F: np.ndarray, B: np.ndarray, W: np.ndarray,
             lam: float = 0.05,
             mu: float = 0.02) -> tuple[np.ndarray, np.ndarray]:
    """
    DSSE v2.1 reconstruction engine.

    Inputs:
        F : (N, dF)  forward embeddings
        B : (N, dB)  backward embeddings
        W : (dF, dB) projection matrix
        lam : C correction factor
        mu  : Δ correction factor

    Returns:
        reconstructed_B : (N, dB)   reconstructed semantic vectors
        target_B        : (N, dB)   normalized B★ reference vectors
    """

    # ---- Projection ----
    B_star = (W @ B.T).T
    uF = normalize_rows(F)
    uB = normalize_rows(B_star)

    sF = np.linalg.norm(F, axis=1)
    sB = np.linalg.norm(B_star, axis=1)
    r = np.sum(uF * uB, axis=1)

    # ---- DSSE base geometry ----
    C = 0.5 * (uF + uB)
    Delta = uF - uB
    Sigma = np.sum(uF * uB, axis=1)

    # ---- Primary corrections ----
    pC = normalize_rows(C - Sigma[:, None] * uF)
    pSigma = 0.5 * (Sigma + r)

    # ---- ECO (residual orthogonal trace) ----
    u_mix = normalize_rows(uF + uB)
    proj = np.sum(uF * u_mix, axis=1)
    E = normalize_rows(uF - proj[:, None] * u_mix)

    # ---- Corrected geometry ----
    C_prime = normalize_rows(C + lam * pC)
    Delta_prime = Delta + mu * E

    # ---- α multi-term stabilizer ----
    alpha = (1 - pSigma) * (1 - Sigma) * (1 - r**2)

    # ---- Final reconstruction ----
    u_final = normalize_rows(C_prime - alpha[:, None] * Delta_prime)

    s_final = sB * (1 - Sigma) + sF * Sigma
    reconstructed = u_final * s_final[:, None]

    return reconstructed, uB


# --------------------------------------------------------------
# Batch evaluation helper
# --------------------------------------------------------------

def dsse_compare(reconstructed: np.ndarray, target: np.ndarray) -> dict:
    """
    Return cosine + angle statistics between reconstructed and target (B★).
    """
    rec = normalize_rows(reconstructed)
    tgt = normalize_rows(target)

    cos = np.sum(rec * tgt, axis=1)
    cos = np.clip(cos, -1, 1)
    angle = np.degrees(np.arccos(cos))

    return {
        "cos_mean": float(cos.mean()),
        "cos_std": float(cos.std()),
        "angle_mean": float(angle.mean()),
        "angle_std": float(angle.std()),
        "cos_min": float(cos.min()),
        "cos_max": float(cos.max()),
        "angle_min": float(angle.min()),
        "angle_max": float(angle.max()),
    }
