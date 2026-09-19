#!/usr/bin/env bash
# Anchor the CURRENT substrate Merkle root with OpenTimestamps, once per new root.
#
# The live ots_anchors.json shows the same 50-leaf root from July stamped 38
# times in a row while latest_seal.json moved on to 456k leaves. This script
# reads the root the public page advertises, refuses to re-stamp a root that is
# already anchored, and appends a pending anchor for the new one. Confirmation
# (upgrade) is handled by the existing upgrade job or by `ots upgrade`.
#
#   DATA=/var/www/registry/data ./ots_stamp_substrate_root.sh          # stamp if new
#   DRY_RUN=1 ./ots_stamp_substrate_root.sh                             # show what would happen
#
# Requires: python3, ots (opentimestamps-client), jq optional.
set -euo pipefail
DATA="${DATA:-/var/www/registry/data}"
LATEST="$DATA/substrate/latest_seal.json"
ANCHORS="$DATA/substrate/ots_anchors.json"
# Same directory and <root>.ots naming as scripts/ots_anchor.py, so the nightly
# ots_refresh.py rebuild picks the proof up and upgrades it to a Bitcoin attestation.
OTS_DIR="${OTS_DIR:-/opt/crovia/substrate/anchors}"
DRY_RUN="${DRY_RUN:-0}"

root=$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d.get("merkle_root") or d.get("root") or "")' "$LATEST")
leaves=$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d.get("n_leaves") or d.get("leaf_count") or d.get("size") or 0)' "$LATEST")
[ -n "$root" ] || { echo "no merkle_root in $LATEST" >&2; exit 2; }
hex="${root#sha256:}"

if python3 - "$ANCHORS" "$root" "$hex" <<'EOF'
import json,sys
d=json.load(open(sys.argv[1])); roots={a.get("merkle_root") for a in d.get("anchors",[])}
sys.exit(0 if (sys.argv[2] in roots or sys.argv[3] in roots) else 1)
EOF
then
  echo "root $root already anchored ($leaves leaves); nothing to do"; exit 0
fi

echo "new substrate root: $root ($leaves leaves)"
mkdir -p "$OTS_DIR"
digest_file="$OTS_DIR/$hex.digest"
python3 -c 'import sys;open(sys.argv[2],"wb").write(bytes.fromhex(sys.argv[1]))' "$hex" "$digest_file"
if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] would run: ots stamp $digest_file && append pending anchor to $ANCHORS"; exit 0; fi

ots stamp "$digest_file"
mv "$digest_file.ots" "$OTS_DIR/$hex.ots"
# sidecar read by scripts/ots_refresh.py for stamped_at
printf '{"stamped_at":"%s","n_leaves":%s,"source":"phase0/ots_stamp_substrate_root.sh"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$leaves" > "$OTS_DIR/$hex.status.json"
python3 - "$ANCHORS" "$root" "$leaves" "$OTS_DIR/$hex.ots" <<'EOF'
import json,sys,datetime,os,tempfile
path,root,leaves,proof=sys.argv[1:5]
d=json.load(open(path))
d.setdefault("anchors",[]).append({
  "merkle_root": root, "n_leaves": int(leaves), "status": "pending",
  "anchor_date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
  "stamped_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
  "ots_proof": os.path.basename(proof), "note": "substrate root (canon §4)"})
d["generated_at"]=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
fd,tmp=tempfile.mkstemp(dir=os.path.dirname(path)); os.write(fd,json.dumps(d,separators=(",",":")).encode()); os.close(fd); os.chmod(tmp,0o644); os.replace(tmp,path)
print("appended pending anchor for", root)
EOF
