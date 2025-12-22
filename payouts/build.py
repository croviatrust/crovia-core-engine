#!/usr/bin/env python3
"""
Crovia PRO Settlement Wrapper
--------------------------------
Takes royalty-based signals + DPI + DP Policy output
and produces PRO-level payout distribution using:

- DPICalibrator
- DPNoisePolicy
- DSSEProEngine
- Sentinel PRO Check
- PRO SettlementEngine

This wrapper converts receipts into the compact representation
required by the PRO engine, then writes a JSON output.

This keeps run_period.py clean and avoids mixing open-core with PRO logic.
"""

import json
import sys
from pathlib import Path

# PRO modules
from croviapro.settlement.settlement_engine import SettlementEngine, ProviderSettlementInput, ContractSpec
from croviapro.dpi.dpi_calibrator import DPIWeight
from croviapro.dpi.dp_noise_policy import DPNoiseDecision
from croviapro.semantic.dsse_pro_core import DSSEProEngine

def load_test_provider_inputs():
    """Temporary loader – replace with real pipeline after integration."""
    with open("test_providers.json") as f:
        data = json.load(f)

    providers = []
    for p in data:
        dpi = DPIWeight(
            provider_id=p["provider_id"],
            raw_value_score=p["dpi_weight"]["raw_value_score"],
            calibrated_score=p["dpi_weight"]["calibrated_score"],
            weight=p["dpi_weight"]["weight"],
            profile_name="test_profile",
            notes="test"
        )

        dp = DPNoiseDecision(
            provider_id=p["provider_id"],
            epsilon_target=p["dp_decision"]["epsilon_target"],
            clip_share_at=p["dp_decision"]["clip_share_at"],
            strategy=p["dp_decision"]["strategy"],
            notes=p["dp_decision"].get("notes", "")
        )

        c = ContractSpec(**p["contract"])

        providers.append(
            ProviderSettlementInput(
                provider_id=p["provider_id"],
                dpi_weight=dpi,
                dp_decision=dp,
                contract=c
            )
        )

    return providers


def main():
    if len(sys.argv) < 3:
        print("Usage: payouts_pro_from_royalties.py <period> <eur_total>")
        sys.exit(1)

    period = sys.argv[1]
    eur_total = float(sys.argv[2])

    providers = load_test_provider_inputs()

    eng = SettlementEngine(period=period, eur_total=eur_total)
    res = eng.settle(providers)

    out_path = Path(f"data/payouts_pro_{period}.json")
    out_path.write_text(json.dumps(res.to_dict(), indent=2))
    print(f"[OK] Wrote PRO payouts → {out_path}")

if __name__ == "__main__":
    main()
