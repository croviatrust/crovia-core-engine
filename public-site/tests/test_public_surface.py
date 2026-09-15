#!/usr/bin/env python3
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
claims = json.loads((ROOT / "data/public_claims.json").read_text(encoding="utf-8"))
schema = json.loads((ROOT / "schemas/public-claims-v1.json").read_text(encoding="utf-8"))
release = json.loads((ROOT / "release-manifest.json").read_text(encoding="utf-8"))
page = (ROOT / "status/index.html").read_text(encoding="utf-8")
llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
readme = (ROOT.parent / "README.md").read_text(encoding="utf-8")

assert claims["version"] == "1.0.0"
assert claims["schema"] == schema["$id"]
assert schema["$schema"].endswith("/draft/2020-12/schema")

assert release["schema"] == "crovia.public-release.v1"
assert release["target_root"] == "/var/www/registry"
assert release["preflight"]["require_backup"] is True
assert release["post_deploy"]["rollback_on_failure"] is True
allowed_targets = {
    "status/index.html",
    "llms.txt",
    "data/public_claims.json",
    "schemas/public-claims-v1.json",
}
targets = {entry["target"] for entry in release["files"]}
assert targets == allowed_targets
for entry in release["files"]:
    source = Path(entry["source"])
    target = Path(entry["target"])
    assert not source.is_absolute() and ".." not in source.parts
    assert not target.is_absolute() and ".." not in target.parts
    assert (ROOT / source).is_file()
    assert entry["mode"] == "0644"

assert claims["status"] == "source-contract"
assert claims["generated_at"] is None
assert len(claims["claims"]) >= 3
claim_ids = [claim["id"] for claim in claims["claims"]]
assert len(claim_ids) == len(set(claim_ids))
for claim in claims["claims"]:
    assert claim["id"] and claim["statement"]
    assert claim["evidence"] and claim["limitations"]

observation_claim = next(claim for claim in claims["claims"] if claim["id"] == "crovia-observation-scope")
assert any("parsing failures are indeterminate" in item for item in observation_claim["limitations"])

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

for forbidden_machine_claim in (
    "Crovia Seal is an IETF standard",
    "Crovia Seal is an open standard",
    "every record is Bitcoin",
    "immutable by construction",
    "courtroom-grade",
):
    assert forbidden_machine_claim.lower() not in llms.lower()

for copied_counter in ("287,116", "492 LACUNA", "45 batches", "419,640"):
    assert copied_counter not in llms
assert "An Internet-Draft is not an IETF standard or endorsement." in llms
assert "does not establish intent, illegality" in llms

assert "https://croviatrust.com/status/" in readme
assert "https://croviatrust.com/data/public_claims.json" in readme
assert "https://croviatrust.com/registry/seal/verify/" in readme
assert "https://croviatrust.com/registry/verify/" not in readme
assert "An Internet-Draft is not an IETF standard or endorsement." in readme
assert "Crovia produces **facts**" not in readme
assert "Signature validity, Merkle inclusion, OpenTimestamps submission, and Bitcoin confirmation are separate states." in readme

assert "https://croviatrust.com/registry/seal/verify/" in llms
assert "/registry/seal/verify/" in page
assert "https://croviatrust.com/registry/seal/verify/" in json.dumps(claims)
assert "/verify/" not in page.replace("/registry/seal/verify/", "")
assert "https://croviatrust.com/registry/verify/" not in llms

assert 'cache:"no-store"' in page
assert "d?.ledger?.pulse_freshness_seconds" in page
assert "documentAge<=ttl" in page
assert "observationAge<=ttl" in page
assert "reportedEvidenceAge<=ttl" in page
assert "value===null" in page
assert "Number.isSafeInteger(n)&&n>=0" in page
assert "setTimeout(()=>location.reload()" in page
assert "Evidence is stale or has no valid timestamp" in page
assert "Ledger envelopes" in page
assert "Signed envelopes" not in page
assert 'id="generated-at"' in page
assert 'id="last-observed-at"' in page
assert "d?.ledger?.last_envelope_at" in page
assert 'textContent=iso(d.generated_at)' in page

with tempfile.TemporaryDirectory() as tmp:
    output = Path(tmp) / "release"
    subprocess.run(
        ["python3", str(ROOT / "tools/build_release.py"), "--output", str(output)],
        check=True,
    )
    artifact = json.loads((output / "SHA256SUMS.json").read_text(encoding="utf-8"))
    assert artifact["schema"] == "crovia.public-release-artifact.v1"
    assert {item["target"] for item in artifact["files"]} == allowed_targets
    for item in artifact["files"]:
        deployed = output / item["target"]
        assert deployed.is_file() and not deployed.is_symlink()
        assert hashlib.sha256(deployed.read_bytes()).hexdigest() == item["sha256"]
        assert deployed.stat().st_size == item["size"]

with tempfile.TemporaryDirectory() as tmp:
    occupied = Path(tmp) / "occupied"
    occupied.mkdir()
    sentinel = occupied / "must-survive.txt"
    sentinel.write_text("do not delete", encoding="utf-8")
    refused = subprocess.run(
        ["python3", str(ROOT / "tools/build_release.py"), "--output", str(occupied)],
        capture_output=True,
        text=True,
    )
    assert refused.returncode != 0
    assert sentinel.read_text(encoding="utf-8") == "do not delete"

print("public surface contract: PASS")
