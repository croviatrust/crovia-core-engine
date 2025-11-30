from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


@dataclass
class ProviderRow:
    provider_id: str
    coverage_bound: float
    eligible: bool = True
    kyc_tier: Optional[int] = None
    status: Optional[str] = None
    display_name: Optional[str] = None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compute Crovian Floors v1.1 from trust_providers.csv"
    )
    p.add_argument(
        "--period",
        required=True,
        help="Period in YYYY-MM (just for labelling output)",
    )
    p.add_argument(
        "--eur-total",
        type=float,
        required=True,
        help="Total EUR budget for the period (same used in payouts)",
    )
    p.add_argument(
        "--trust-csv",
        default=str(DATA_DIR / "trust_providers.csv"),
        help="Path to trust_providers.csv (default: data/trust_providers.csv)",
    )
    p.add_argument(
        "--registry-json",
        default=str(DATA_DIR / "provider_registry.json"),
        help="Optional provider registry file (default: data/provider_registry.json)",
    )
    p.add_argument(
        "--coverage-csv",
        default=None,
        help=(
            "Optional CSV with coverage_bound overrides per provider_id. "
            "If provided, overrides topk-derived coverage."
        ),
    )
    p.add_argument(
        "--out-json",
        default=None,
        help="Output JSON floors file (default: data/floors_<period>.json)",
    )
    return p.parse_args()


def load_provider_registry(path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Load provider registry from JSON, returning a mapping provider_id -> metadata.
    If file is missing or invalid, returns {}.
    """
    if not path.exists():
        print(f"[FLOOR] No provider_registry.json found at {path}; continuing without registry.")
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[FLOOR] Could not parse provider registry {path}: {e}")
        return {}

    providers = payload.get("providers")
    if not isinstance(providers, list):
        print(f"[FLOOR] provider_registry.json malformed (no 'providers' list); ignoring.")
        return {}

    registry: Dict[str, Dict[str, Any]] = {}
    for entry in providers:
        if not isinstance(entry, dict):
            continue
        pid = (entry.get("provider_id") or "").strip()
        if not pid:
            continue
        registry[pid] = entry

    print(f"[FLOOR] Loaded {len(registry)} providers from registry.")
    return registry


def load_coverage_overrides(path: Optional[Path]) -> Dict[str, float]:
    """
    Optional CSV with explicit coverage_bound per provider_id.

    Expected columns:
      - provider_id (or provider)
      - coverage_bound  (float in [0,1])

    Returns mapping provider_id -> coverage_bound.
    """
    if path is None:
        return {}

    if not path.exists():
        print(f"[FLOOR] coverage CSV not found at {path}; ignoring coverage overrides.")
        return {}

    overrides: Dict[str, float] = {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return overrides

        # detect provider column
        provider_col = None
        for cand in ("provider_id", "provider", "id"):
            if cand in reader.fieldnames:
                provider_col = cand
                break
        if provider_col is None or "coverage_bound" not in reader.fieldnames:
            print(
                f"[FLOOR] coverage CSV {path} missing provider_id/coverage_bound columns; ignoring."
            )
            return overrides

        for row in reader:
            pid = (row.get(provider_col) or "").strip()
            if not pid:
                continue
            raw_cov = row.get("coverage_bound", "")
            try:
                cov = float(raw_cov)
            except (TypeError, ValueError):
                continue
            # clamp to [0,1]
            if cov < 0.0:
                cov = 0.0
            if cov > 1.0:
                cov = 1.0
            overrides[pid] = cov

    print(f"[FLOOR] Loaded {len(overrides)} coverage overrides from {path}.")
    return overrides


def load_providers_from_trust_csv(
    path: Path,
    coverage_overrides: Dict[str, float],
    registry: Dict[str, Dict[str, Any]],
) -> List[ProviderRow]:
    if not path.exists():
        raise SystemExit(f"[FLOOR] trust CSV not found: {path}")

    rows: List[ProviderRow] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return rows

        # find provider column
        provider_col = None
        for cand in ("provider", "provider_id", "id"):
            if cand in reader.fieldnames:
                provider_col = cand
                break
        if provider_col is None:
            raise SystemExit(
                f"[FLOOR] No provider column found in {path} (expected provider/provider_id/id)"
            )

        # detect top-k column (either topk_rate or topk)
        topk_col = None
        for cand in ("topk_rate", "topk"):
            if cand in reader.fieldnames:
                topk_col = cand
                break

        for row in reader:
            pid = (row.get(provider_col) or "").strip()
            if not pid:
                continue

            # 1) coverage_bound from explicit overrides if available
            if pid in coverage_overrides:
                coverage_bound = coverage_overrides[pid]
            # 2) otherwise derive a crude bound from topk_rate/topk if present
            elif topk_col is not None:
                raw = row.get(topk_col, "")
                try:
                    topk_val = float(raw) if raw not in (None, "") else 0.0
                except ValueError:
                    topk_val = 0.0

                # topk_rate is already a fraction in [0,1]
                if topk_col == "topk_rate":
                    cov = topk_val
                else:
                    # topk is interpreted as percentage [0,100]
                    cov = topk_val / 100.0

                if cov < 0.0:
                    cov = 0.0
                if cov > 1.0:
                    cov = 1.0
                coverage_bound = cov
            # 3) fallback: full coverage if nothing else is known
            else:
                coverage_bound = 1.0

            # default metadata
            eligible = True
            kyc_tier = None
            status = None
            display_name = None

            # registry override, if present
            reg_entry = registry.get(pid)
            if reg_entry:
                if "eligible" in reg_entry:
                    eligible = bool(reg_entry["eligible"])
                kyc_tier = reg_entry.get("kyc_tier")
                status = reg_entry.get("status")
                display_name = reg_entry.get("display_name")

            rows.append(
                ProviderRow(
                    provider_id=pid,
                    coverage_bound=coverage_bound,
                    eligible=eligible,
                    kyc_tier=kyc_tier,
                    status=status,
                    display_name=display_name,
                )
            )

    if not rows:
        return rows

    # If no explicit coverage_overrides were provided, we may apply a conservative fallback
    if not coverage_overrides:
        coverage_sum = sum(p.coverage_bound for p in rows if p.eligible)
        if coverage_sum < 1.0 - 1e-9:
            print(
                f"[FLOOR] coverage_sum={coverage_sum:.4f} < 1.0; "
                "applying conservative fallback coverage_bound=1.0 for all eligible providers."
            )
            for p in rows:
                if p.eligible:
                    p.coverage_bound = 1.0

    return rows


def compute_crovian_floors(
    providers: List[ProviderRow], total_budget: float
) -> Dict[str, float | None]:
    """
    Closed-form Crovian Floor v1.1, with constraints:

    - sum(x_i) = B
    - 0 <= x_i <= B * coverage_bound_i
    - non-eligible providers are treated as x_i = 0 and skipped here

    For each eligible provider k:

        Floor_k = max(0, B * (1 - sum_{j!=k} coverage_j))

    with coverage_j = coverage_bound_j, only over eligible providers.

    If the sum of coverage bounds over eligibles is < 1,
    the configuration is marked infeasible and floors are None.
    """
    eligibles = [p for p in providers if p.eligible]
    if not eligibles:
        return {}

    coverage_sum = sum(p.coverage_bound for p in eligibles)
    if coverage_sum < 1.0 - 1e-9:
        print(
            f"[FLOOR] coverage_sum={coverage_sum:.4f} < 1.0; "
            "marking floors as None for all eligible providers."
        )
        return {p.provider_id: None for p in eligibles}

    floors: Dict[str, float | None] = {}
    for p in eligibles:
        sum_others = coverage_sum - p.coverage_bound
        frac = max(0.0, 1.0 - sum_others)
        if frac < 1e-14:
            frac = 0.0
        floors[p.provider_id] = total_budget * frac

    return floors


def main() -> None:
    args = parse_args()
    period = args.period
    total_budget = args.eur_total

    trust_path = Path(args.trust_csv)
    registry_path = Path(args.registry_json)
    coverage_path = Path(args.coverage_csv) if args.coverage_csv else None

    registry = load_provider_registry(registry_path)
    coverage_overrides = load_coverage_overrides(coverage_path)

    providers = load_providers_from_trust_csv(
        trust_path,
        coverage_overrides=coverage_overrides,
        registry=registry,
    )

    if not providers:
        raise SystemExit("[FLOOR] No providers loaded from trust CSV; aborting.")

    floors = compute_crovian_floors(providers, total_budget)

    out_path = Path(args.out_json) if args.out_json else DATA_DIR / f"floors_{period}.json"

    payload: Dict[str, Any] = {
        "period": period,
        "budget_total_eur": total_budget,
        "coverage_sum": sum(p.coverage_bound for p in providers if p.eligible),
        "providers": [],
    }

    for p in providers:
        floor_val = floors.get(p.provider_id) if p.eligible else None
        payload["providers"].append(
            {
                "provider_id": p.provider_id,
                "coverage_bound": p.coverage_bound,
                "eligible": p.eligible,
                "kyc_tier": p.kyc_tier,
                "status": p.status,
                "display_name": p.display_name,
                "floor_eur": floor_val,
            }
        )

    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    non_null = [v for v in floors.values() if v is not None]
    min_floor = min(non_null) if non_null else 0.0
    max_floor = max(non_null) if non_null else 0.0
    print(
        f"[FLOOR] floors written to {out_path} (providers={len(providers)}, "
        f"min_floor={min_floor:.2f}, max_floor={max_floor:.2f})"
    )


if __name__ == "__main__":
    main()
