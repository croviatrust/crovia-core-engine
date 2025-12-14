#!/usr/bin/env python3
import argparse, json, hashlib
from datetime import datetime, timezone
from pathlib import Path

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

ap = argparse.ArgumentParser(description="Attach a hashchain artifact into a Crovia trust bundle (open-core tool).")
ap.add_argument("--bundle", required=True, help="Input trust bundle JSON")
ap.add_argument("--hashchain", required=True, help="Hashchain file to attach")
ap.add_argument("--out", required=True, help="Output trust bundle JSON")
args = ap.parse_args()

bundle_path = Path(args.bundle)
hc_path = Path(args.hashchain)
out_path = Path(args.out)

bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
hc_sha = sha256_file(hc_path)

artifact = {
    "type": "hashchain",
    "path": str(hc_path),
    "sha256": hc_sha,
    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "note": "Hashchain over receipts NDJSON (line-order sensitive)."
}

# Ensure artifacts list exists
artifacts = bundle.get("artifacts")
if not isinstance(artifacts, list):
    artifacts = []
bundle["artifacts"] = artifacts

# Avoid duplicates
if not any(isinstance(a, dict) and a.get("type")=="hashchain" and a.get("sha256")==hc_sha for a in artifacts):
    artifacts.append(artifact)

bundle["meta"] = bundle.get("meta") or {}
bundle["meta"]["hashchain_bound"] = True
bundle["meta"]["hashchain_sha256"] = hc_sha

out_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print("[attach] OK")
print(" out =", out_path)
print(" hashchain_sha256 =", hc_sha)
