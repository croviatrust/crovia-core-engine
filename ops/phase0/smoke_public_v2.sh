#!/usr/bin/env bash
# Public smoke test aligned with CANON.md §5. Replaces the 2025 probe list that
# still checked /check.html, /observatory/, /registry/tpa/ and other retired paths.
#
#   ./smoke_public_v2.sh                            # human output
#   ./smoke_public_v2.sh --json > _smoke.json       # same schema as the current _smoke.json
#   ./smoke_public_v2.sh --json --out /var/www/registry/data/_smoke.json
#
# Exit 0 iff every check passes. With --out the JSON is written atomically
# (tmp + mv) whether or not checks fail: a smoke file must show the failure,
# not freeze at the last green run. Never chain `--json > f && mv` in cron
# for that reason (that form froze _smoke.json from 2026-09-19 to 09-24).
# Dependencies: curl, python3.
set -u
BASE="${BASE:-https://croviatrust.com}"
SEAL="${SEAL:-https://seal.croviatrust.com}"
UA="crovia-smoke/2.0"
JSON=0; OUT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON=1;;
    --out) OUT="${2:-}"; shift;;
    *) echo "usage: $0 [--json] [--out PATH]" >&2; exit 2;;
  esac
  shift
done
[ -n "$OUT" ] && JSON=1
results=()
n_ok=0; n_fail=0

check() {  # name url expected_status [marker]   (CHECK_UA overrides the User-Agent for one call)
  local name="$1" url="$2" want="$3" marker="${4:-}"
  local body code ua="${CHECK_UA:-$UA}"
  body=$(curl -sS -L -A "$ua" --max-time 30 -w $'\n%{http_code}' "$url" 2>/dev/null)
  code="${body##*$'\n'}"; body="${body%$'\n'*}"
  local ok=1
  [ "$code" = "$want" ] || ok=0
  if [ -n "$marker" ] && [ "$ok" = 1 ]; then grep -qF -- "$marker" <<<"$body" || ok=0; fi
  if [ "$ok" = 1 ]; then n_ok=$((n_ok+1)); else n_fail=$((n_fail+1)); fi
  results+=("$(python3 -c 'import json,sys;print(json.dumps({"name":sys.argv[1],"url":sys.argv[2],"expected":int(sys.argv[3]),"status":int(sys.argv[4] or 0),"marker":sys.argv[5] or None,"ok":sys.argv[6]=="1"}))' "$name" "$url" "$want" "$code" "$marker" "$ok")")
  [ $JSON = 1 ] || printf '%s %-38s %s\n' "$([ "$ok" = 1 ] && echo PASS || echo FAIL)" "$name" "$code"
  sleep 1.2
}

redirect() {  # name path expected_location_prefix
  local name="$1" path="$2" want="$3" code loc ok=0
  read -r code loc < <(curl -sS -o /dev/null -A "$UA" --max-time 30 -w '%{http_code} %{redirect_url}\n' "$BASE$path")
  case "$code" in 301|302|308) [[ "$loc" == "$BASE$want"* ]] && ok=1;; esac
  if [ "$ok" = 1 ]; then n_ok=$((n_ok+1)); else n_fail=$((n_fail+1)); fi
  results+=("$(python3 -c 'import json,sys;print(json.dumps({"name":sys.argv[1],"url":sys.argv[2],"expected":"redirect->"+sys.argv[3],"status":int(sys.argv[4] or 0),"location":sys.argv[5],"ok":sys.argv[6]=="1"}))' "$name" "$BASE$path" "$want" "$code" "$loc" "$ok")")
  [ $JSON = 1 ] || printf '%s %-38s %s -> %s\n' "$([ "$ok" = 1 ] && echo PASS || echo FAIL)" "$name" "$code" "$loc"
  sleep 1.2
}

# Pages (canon §5)
check home            "$BASE/"                                200 "Silence you can verify"
check whitepaper      "$BASE/whitepaper.html"                 200 "Whitepaper"
check proof           "$BASE/proof.html"                      200
check registry        "$BASE/registry/"                       200 "Crovia Registry"
check explore         "$BASE/registry/explore/"               200 "Evidence Explorer"
check verify          "$BASE/registry/verify/"                200 "Crovia Passport"
check compliance      "$BASE/registry/compliance/"            200 "Compliance"
check lacuna          "$BASE/registry/lacuna/"                200 "LACUNA"
check api_docs        "$BASE/registry/api/"                   200
check seal            "$BASE/registry/seal/"                  200 "Open Provenance Receipt"
check seal_spec       "$BASE/registry/seal/spec/"             200
check seal_threat     "$BASE/registry/seal/threat-model/"     200
check seal_verify     "$BASE/registry/seal/verify/"           200 "crovia.seal.v1"
check seal_log        "$BASE/registry/seal/log/"              200
check provenance      "$BASE/registry/provenance/"            200
check embed_silence   "$BASE/registry/embed/silence.html"     200
check llms_txt        "$BASE/llms.txt"                        200 "croviatrust.com"
check llms_full       "$BASE/llms-full.txt"                   200
check robots          "$BASE/robots.txt"                      200
check sitemap         "$BASE/sitemap.xml"                     200 "<urlset"
check ai_plugin       "$BASE/.well-known/ai-plugin.json"      200 "schema_version"
check openapi         "$BASE/.well-known/openapi.yaml"        200 "openapi:"

# Data (canon §5) — sequential, rate-limited by nginx
check pulse           "$BASE/registry/data/_home_pulse.json"                     200 "n_envelopes_total"
check silence_index   "$BASE/registry/data/silence_index.json"                   200 "generated_at"
check collectors      "$BASE/registry/data/substrate/collectors.json"            200
check latest_seal     "$BASE/registry/data/substrate/latest_seal.json"           200 "merkle_root"
check ots_anchors     "$BASE/registry/data/substrate/ots_anchors.json"           200 "anchors"
check trust_root      "$BASE/registry/data/substrate/trust_root.json"            200 "public_key_hex"
check lacuna_cands    "$BASE/registry/data/substrate/lacuna_candidates.json"     200 "candidates"
check seal_public_log "$BASE/registry/data/seal/public_log.jsonl"                200 "crovia.seal.v1"

# The same data for a plain script. The reference verifiers (tacet, the
# Python examples in the API docs) fetch with urllib and send its default
# User-Agent; Cloudflare's Browser Integrity Check answers that client with
# 403 (error 1010) unless the path is exempted. A 200 above and a 403 here
# means "verifiable by anyone" is false for scripts. Fix: Cloudflare →
# Rules → Configuration Rules → URI path starts with /registry/data/ →
# Browser Integrity Check: off (same rule on causari.dev for /reports/, /r/).
CHECK_UA="Python-urllib/3.12" check script_latest_seal "$BASE/registry/data/substrate/latest_seal.json" 200 "merkle_root"
CHECK_UA="Python-urllib/3.12" check script_public_log  "$BASE/registry/data/seal/public_log.jsonl"      200 "crovia.seal.v1"
CHECK_UA="Python-urllib/3.12" check script_trust_root  "$BASE/registry/data/substrate/trust_root.json"  200 "public_key_hex"
CHECK_UA="Python-urllib/3.12" check script_silence     "$BASE/registry/data/silence_index.json"         200 "generated_at"

# Seal issuer
check seal_trust_root "$SEAL/trust-root.json"                 200 "pubkey"
check seal_health     "$SEAL/health"                          200
check seal_stats      "$SEAL/v1/stats"                        200 "total_seals"

# MCP (tools/list must answer; body is JSON-RPC)
mcp=$(curl -sS -A "$UA" --max-time 30 -X POST "$BASE/mcp" -H 'content-type: application/json' -H 'accept: application/json, text/event-stream' \
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' -w $'\n%{http_code}')
code="${mcp##*$'\n'}"; body="${mcp%$'\n'*}"
# MCP server 2.0 (2026-09-20) renamed get_lacuna → get_silence_proof.
ok=0; [ "$code" = 200 ] && grep -q '"lookup_model"' <<<"$body" && grep -q '"get_silence_proof"' <<<"$body" && ok=1
if [ "$ok" = 1 ]; then n_ok=$((n_ok+1)); else n_fail=$((n_fail+1)); fi
results+=("{\"name\":\"mcp_tools_list\",\"url\":\"$BASE/mcp\",\"expected\":200,\"status\":${code:-0},\"ok\":$([ "$ok" = 1 ] && echo true || echo false)}")
[ $JSON = 1 ] || printf '%s %-38s %s\n' "$([ "$ok" = 1 ] && echo PASS || echo FAIL)" mcp_tools_list "$code"

# Retired paths must redirect (canon §5)
redirect r_check        /check.html            /registry/verify/
redirect r_howto        /how-to-read.html      /
redirect r_absence      /absence-clock.html    /registry/lacuna/
redirect r_observatory  /observatory/          /registry/
redirect r_tpa          /registry/tpa/         /registry/verify/
redirect r_ranking      /registry/ranking/     /registry/compliance/
redirect r_substrate    /registry/substrate/   /registry/explore/
redirect r_omissions    /registry/omissions/   /registry/explore/

checked_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
emit_json() {
  printf '{"schema":"crovia.smoke.v2","checked_at":"%s","base":"%s","n_checks":%d,"n_ok":%d,"n_failed":%d,"checks":[' "$checked_at" "$BASE" $((n_ok+n_fail)) $n_ok $n_fail
  (IFS=,; printf '%s' "${results[*]}")
  printf ']}\n'
}
if [ -n "$OUT" ]; then
  tmp="$OUT.tmp.$$"
  if emit_json > "$tmp" && python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$tmp" 2>/dev/null; then
    mv -f "$tmp" "$OUT"
  else
    rm -f "$tmp"; echo "smoke: could not write $OUT" >&2; exit 2
  fi
elif [ $JSON = 1 ]; then
  emit_json
else
  echo; echo "$checked_at  $n_ok passed, $n_fail failed"
fi
[ $n_fail = 0 ]
