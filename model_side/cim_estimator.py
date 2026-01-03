# Copyright 2025  CroviaTrust Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from __future__ import annotations
import numpy as np

def stable_softmax(scores: np.ndarray, alpha: float = 10.0) -> np.ndarray:
    """Softmax numericamente stabile su un vettore 1D."""
    x = np.asarray(scores, dtype=np.float64)
    m = np.max(x)
    z = x - m                      # <= 0
    e = np.exp(alpha * z)          # no overflow
    s = e.sum()
    if s <= 0:
        # tutto -inf? fallback uniforme
        return np.ones_like(x) / x.size
    return (e / s).astype(np.float64)

def _add_pairwise_synergy(shares: np.ndarray, keep_idx: np.ndarray, frac: float) -> np.ndarray:
    """
    Aggiunge una massa di sinergia 'frac' * mass ai contributi individuali in base ai
    prodotti pairwise dei top-K. Non cambia l'ordine: ri-normalizza a 1.
    """
    y = shares.copy().astype(np.float64)
    mass = y.sum()
    if mass <= 0 or frac <= 0:
        return (y / (mass + 1e-12)).astype(np.float64)

    # punteggio pairwise tra i soli indici tenuti
    kept = y[keep_idx]
    if kept.size < 2:
        return (y / (mass + 1e-12)).astype(np.float64)

    # matrice prodotti senza diagonale
    P = np.outer(kept, kept)
    np.fill_diagonal(P, 0.0)
    pair_sum = P.sum()
    if pair_sum <= 0:
        return (y / (mass + 1e-12)).astype(np.float64)

    # quota sinergia destinata a ciascun tenuto = somma dei prodotti con gli altri
    synergy_for_kept = P.sum(axis=1) / (pair_sum + 1e-12)
    extra_mass = frac * mass
    # distribuisci la sinergia solo sui tenuti
    y[keep_idx] += extra_mass * synergy_for_kept
    # rinormalizza
    y /= (y.sum() + 1e-12)
    return y

def _apply_dp_noise(shares: np.ndarray, epsilon: float, rng: np.random.Generator) -> np.ndarray:
    """Aggiunge rumore Laplace a ciascuna share e rinormalizza (epsilon > 0)."""
    if epsilon is None or epsilon <= 0:
        return shares
    scale = 1.0 / float(epsilon)
    noise = rng.laplace(loc=0.0, scale=scale, size=shares.shape)
    y = shares + noise
    y = np.clip(y, 0.0, None)
    if y.sum() <= 0:
        # fallback: tutto uniforme
        y[:] = 1.0 / y.size
        return y
    y /= y.sum()
    return y

def cim_estimate(
    scores: np.ndarray,
    alpha: float = 10.0,
    top_k: int = 3,
    synergy_frac: float = 0.12,
    epsilon_dp: float | None = None,
    seed: int | None = None
):
    """
    Da similarità FAISS -> shares con:
      1) softmax stabile
      2) taglio ai top_k (gli altri a 0)
      3) sinergia 'Shapley-2 lite' tra i top_k
      4) (opz.) rumore DP + rinormalizzazione
    Ritorna: shares_full (stessa lunghezza di scores), keep_idx (indici dei top_k).
    """
    scores = np.asarray(scores, dtype=np.float64)
    base = stable_softmax(scores, alpha=alpha)

    # prendi i top_k sul vettore base
    order = np.argsort(-base)
    keep_idx = order[: max(1, int(top_k))]
    mask = np.zeros_like(base, dtype=bool)
    mask[keep_idx] = True

    # azzera fuori top_k e rinormalizza
    y = np.where(mask, base, 0.0)
    s = y.sum()
    if s > 0:
        y /= s
    else:
        y[keep_idx] = 1.0 / keep_idx.size

    # aggiungi sinergia 2-vie tra i top_k e rinormalizza
    y = _add_pairwise_synergy(y, keep_idx, frac=float(synergy_frac))

    # (opz.) DP noise
    rng = np.random.default_rng(seed)
    y = _apply_dp_noise(y, epsilon=epsilon_dp, rng=rng)

    # rinormalizzazione finale di sicurezza
    y = y / (y.sum() + 1e-12)

    return y.astype(np.float64), keep_idx.astype(int)

