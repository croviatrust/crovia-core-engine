#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
claims = json.loads((ROOT / "data/public_claims.json").read_text(encoding="utf-8"))
page = (ROOT / "status/index.html").read_text(encoding="utf-8")
llms = (ROOT / "llms.txt").read_text(encoding="utf-8")

assert claims["version"] == "1.0.0"
assert claims["status"] == "source-contract"
assert claims["generated_at"] is None
assert len(claims["claims"]) >= 3
for claim in claims["claims"]:
    assert claim["id"] and claim["statement"]
    assert claim["evidence"] and claim["limitations"]

required_paths = (
    'd?.ledger?.n_envelopes_total',
    'd?.ledger?.by_axiom_type?.["AX.LAC"]',
    'd?.silence?.total_days',
    'd?.bitcoin?.n_bitcoin',
)
for token in required_paths:
    assert token in page, token

for forbidden in (
    "IETF standard",
    "every record is Bitcoin",
    "immutable by construction",
    "courtroom-grade",
):
    assert forbidden.lower() not in page.lower()
    assert forbidden.lower() not in llms.lower()

for copied_counter in ("287,116", "492 LACUNA", "45 batches", "419,640"):
    assert copied_counter not in llms
assert "An Internet-Draft is not an IETF standard or endorsement." in llms
assert "does not establish intent, illegality" in llms

assert 'cache:"no-store"' in page
assert "d?.ledger?.pulse_freshness_seconds" in page
assert "documentAge<=ttl" in page
assert "evidenceAge<=ttl" in page
assert "Evidence is stale or has no valid timestamp" in page
print("public surface contract: PASS")
