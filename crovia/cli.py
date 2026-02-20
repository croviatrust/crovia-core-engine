#!/usr/bin/env python3
"""
crovia.cli — CroviaTrust CLI (v0.1, Phase 1+2 UX)

Entry point:
    crovia <command> [options]

Commands:
    scan, check, refine, pay, bundle, sign, trace, explain, mode
"""

import argparse
import hashlib
import hmac
import json
import os
import shutil
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Windows UTF-8 fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ==========================
#  ANSI COLORS – CROVIA PALETTE
# ==========================

RESET = "\033[0m"
MAGENTA = "\033[35m"   # Crovia brand
CYAN = "\033[36m"      # info
GREEN = "\033[32m"     # ok
YELLOW = "\033[33m"    # warning
RED = "\033[31m"       # error
BOLD = "\033[1m"


def c(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


# ==========================
#  USER CONFIG (Phase 2)
# ==========================

def get_config_path() -> Path:
    home = Path(os.environ.get("HOME", "."))
    return home / ".crovia" / "config.json"


DEFAULT_CONFIG = {
    "mode": "default",           # "default" | "tarik"
    "auto_sign": False,
    "auto_hashchain": False,
    "default_budget": None,      # e.g. 1000000
    "prefer_interactive": True,
}


def load_config() -> dict:
    path = get_config_path()
    if not path.exists():
        return DEFAULT_CONFIG.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cfg = DEFAULT_CONFIG.copy()
        cfg.update(data)
        return cfg
    except Exception:
        # if broken, better a clean fallback than a crash
        return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


CONFIG = load_config()


def is_operator_mode() -> bool:
    return CONFIG.get("mode") == "operator"


# ==========================
#  OUTPUT HELPERS (UX)
# ==========================

def print_header(title: str) -> None:
    line = "-" * max(40, len(title) + 20)
    print(c(line, MAGENTA))
    print(c(f"CROVIA -- {title}", MAGENTA))
    print(c(line, MAGENTA))
    print()


def print_section(title: str) -> None:
    print(c(title + ":", CYAN))


def print_ok(msg: str) -> None:
    print(c("[OK] " + msg, GREEN))


def print_warn(msg: str) -> None:
    print(c("[!] " + msg, YELLOW))


def print_error(msg: str) -> None:
    print(c("[X] " + msg, RED))


def print_suggestion(msg: str) -> None:
    print(c(">>> " + msg, MAGENTA))


def ask_menu(prompt: str, options: list[str]) -> int:
    """
    Print a small numbered menu and return the selected option index (1-based).
    """
    print(c(prompt, MAGENTA))
    for i, opt in enumerate(options, 1):
        print(c(f"{i})", MAGENTA), opt)
    choice = input(">> ").strip()
    try:
        val = int(choice)
        if 1 <= val <= len(options):
            return val
    except Exception:
        pass
    return 0


# ==========================
#  COMMAND DISPATCHERS

def cmd_legend(args: argparse.Namespace) -> None:
    """    crovia legend
    → Human-friendly overview of commands and recommended flows.
    """
    print_header("Command legend & typical flows")

    print_section("Most common pipeline (end-to-end)")
    print("1) crovia scan   <dataset.ndjson>")
    print("   -> Turn a raw dataset into demo attribution receipts (royalty_receipt.v1).")
    print()
    print("2) crovia check  receipts.ndjson")
    print("   -> Validate receipts + basic AI Act readiness report.")
    print()
    print("3) crovia refine receipts.ndjson --out refined.ndjson")
    print("   -> Auto-fix share_sum / rank inconsistencies (optional).")
    print()
    print("4) crovia pay    refined.ndjson --period 2025-11 --budget 1000000")
    print("   -> Compute payouts for a monthly period (open-core engine).")
    print()
    print("5) crovia bundle --receipts refined.ndjson --payouts payouts_2025-11.ndjson")
    print("   -> Build a trust bundle JSON for audits / evidence.")
    print()
    print("6) crovia sign   crovia_trust_bundle.json")
    print("   -> Add an HMAC signature (CROVIA_HMAC_KEY) to the bundle.")
    print()
    print("7) crovia trace  receipts.ndjson --out proofs/hashchain_receipts.txt")
    print("   -> Create a hashchain over the receipts (or verify an existing one).")
    print()
    print("8) crovia explain crovia_trust_bundle.json")
    print("   -> Quick structural view (schema, signature, hashes, links.)")
    print()

    print_section("Command cheatsheet")
    print("  legend  -> Show this legend and recommended flows.")
    print("  scan    -> Spider / dataset attribution (demo receipts for now).")
    print("  check   -> Schema + business validation + AI Act hints.")
    print("  refine  -> Heuristic clean-up of weird receipts.")
    print("  pay     -> Turn receipts into payouts (with charts).")
    print("  bundle  -> Assemble all evidence into a single JSON bundle.")
    print("  sign    -> HMAC-sign JSON/NDJSON artifacts.")
    print("  trace   -> Hashchain generator / verifier.")
    print("  explain -> Metacognitive view on any Crovia JSON/.crovia file.")
    print("  mode    -> CLI profile (Operator Mode, defaults, auto-sign, etc.).")
    print()

    print_section("If you are completely new, start with")
    print("1) Put a demo receipts file under ./data/")
    print("2) Run:  crovia check data/royalty_receipts.ndjson")
    print("3) Then: crovia pay   data/royalty_receipts.ndjson --period 2025-11 --budget 1000000")
    print("4) Then: crovia bundle --receipts data/royalty_receipts.ndjson --payouts payouts_2025-11.ndjson")
    print()
    print_suggestion("You can always run 'crovia legend' again if you get lost.")


# ==========================

def cmd_scan(args: argparse.Namespace) -> None:
    """
    crovia scan <dataset>
    [ROADMAP] Attribution spider — generates royalty_receipt.v1 from raw datasets.
    Requires FAISS index + shard sketch pipeline (not yet in open core).
    """
    print_header("Scan (Attribution Spider) [ROADMAP]")
    print_warn("crovia scan requires the FAISS attribution pipeline which is not yet")
    print_warn("included in the open core. It will be released in a future version.")
    print()
    print_section("What scan will do (roadmap)")
    print("  1. Build shard sketches from your dataset")
    print("  2. Query FAISS index of known training corpora")
    print("  3. Output royalty_receipt.v1 NDJSON with attribution scores")
    print()
    print_section("In the meantime")
    print_suggestion("Use the example receipts: crovia check examples/minimal_royalty_receipts.ndjson")
    print_suggestion("Or run the full pipeline: crovia run --receipts <file> --period YYYY-MM --budget N --out <dir>")


def cmd_check(args: argparse.Namespace) -> None:
    """
    crovia check <receipts.ndjson>
    -> Validation + basic AI Act compliance view
    """
    print_header("Check (Integrity & Compliance)")

    path = Path(args.file)
    if not path.exists():
        print_error(f"File not found: {path}")
        sys.exit(1)

    print_section("Input")
    print(f"  File: {path}")
    print()

    _cli_dir = Path(__file__).parent.parent
    validate_py = _cli_dir / "validate" / "validate.py"
    if not validate_py.exists():
        print_error(f"validate.py not found at {validate_py}")
        sys.exit(1)

    out_md = Path(args.out) if getattr(args, 'out', None) else path.with_suffix('.validate_report.md')
    out_bad = path.with_suffix('.validate_bad.ndjson')

    print_section("Running validator")
    r = subprocess.run(
        [sys.executable, str(validate_py), str(path),
         "--out-md", str(out_md), "--out-bad", str(out_bad)],
        capture_output=True, text=True
    )
    if r.stdout.strip():
        print(r.stdout.strip())
    if r.returncode == 0:
        print_ok("Health: A/B — file is valid")
    elif r.returncode == 2:
        print_warn("Health: C — some issues found, check report")
    else:
        print_warn("Health: D — significant issues found")
    if r.stderr.strip():
        print(r.stderr.strip())
    print()
    print_section("Generated outputs")
    print(f"  Report:  {out_md}")
    print(f"  Bad recs: {out_bad}")
    print()
    print_section("Next step")
    print_suggestion(f"crovia refine {path}")


def cmd_refine(args: argparse.Namespace) -> None:
    """
    crovia refine <receipts.ndjson>
    -> Auto-fix share_sum normalization and rank ordering.
    """
    print_header("Refine (Auto-fix Heuristics)")

    path = Path(args.file)
    if not path.exists():
        print_error(f"File not found: {path}")
        sys.exit(1)

    text = path.read_text(encoding="utf-8", errors="replace")
    lines_raw = [l for l in text.splitlines() if l.strip()]
    records, parse_errors = [], 0
    for l in lines_raw:
        try: records.append(json.loads(l))
        except Exception: parse_errors += 1

    print_section("Input")
    print(f"  File:   {path}")
    print(f"  Lines:  {len(records)} valid, {parse_errors} unparseable")
    print()

    # Detect issues
    bad_sum, bad_rank = [], []
    TOL = 0.02
    for i, r in enumerate(records):
        if not isinstance(r, dict): continue
        top_k = r.get("top_k", [])
        if isinstance(top_k, list) and top_k:
            s = sum(e.get("share", 0) for e in top_k if isinstance(e, dict))
            if abs(s - 1.0) > TOL: bad_sum.append(i)
            ranks = [e.get("rank", 0) for e in top_k if isinstance(e, dict)]
            if ranks != sorted(ranks): bad_rank.append(i)

    print_section("Detected issues")
    if bad_sum: print_warn(f"{len(bad_sum)} records with share_sum out of tolerance (>{TOL})")
    else: print_ok("All share_sum values within tolerance")
    if bad_rank: print_warn(f"{len(bad_rank)} records with unsorted rank")
    else: print_ok("All rank fields correctly ordered")
    print()

    if not bad_sum and not bad_rank:
        print_ok("No fixes needed.")
        return

    out_path = Path(args.out or str(path.with_suffix('')) + ".refined.ndjson")

    # Apply fixes
    fixed = 0
    out_records = []
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            out_records.append(r); continue
        top_k = r.get("top_k", [])
        if isinstance(top_k, list) and top_k:
            if i in bad_rank:
                top_k = sorted(top_k, key=lambda e: e.get("rank", 0) if isinstance(e, dict) else 0)
                r["top_k"] = top_k
            if i in bad_sum:
                total = sum(e.get("share", 0) for e in top_k if isinstance(e, dict))
                if total > 0:
                    for e in top_k:
                        if isinstance(e, dict) and "share" in e:
                            e["share"] = round(e["share"] / total, 8)
                fixed += 1
        out_records.append(r)

    out_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in out_records) + "\n",
        encoding="utf-8"
    )
    print_ok(f"Fixed {fixed} records -> {out_path}")
    print()
    print_section("Next step")
    print_suggestion(f"crovia check {out_path}")


def cmd_pay(args: argparse.Namespace) -> None:
    """
    crovia pay <receipts.ndjson> --period YYYY-MM --budget EUR
    -> Compute payouts for a given period.
    """
    print_header("Pay (Payout Engine)")

    path = Path(args.file)
    if not path.exists():
        print_error(f"File not found: {path}")
        sys.exit(1)

    period = args.period
    budget = args.budget or CONFIG.get("default_budget")

    if budget is None:
        print_warn("No budget specified and no default_budget in config.")
        print_suggestion("Re-run with --budget or set default_budget in ~/.crovia/config.json")
        return

    print_section("Input")
    print(f"  Receipts: {path}")
    print(f"  Period:   {period}")
    print(f"  Budget:   {budget} EUR")
    print()

    _cli_dir = Path(__file__).parent.parent
    pay_py = _cli_dir / "core" / "payouts_from_royalties.py"
    if not pay_py.exists():
        print_error(f"payouts_from_royalties.py not found at {pay_py}")
        sys.exit(1)

    payouts_ndjson = Path(args.out or f"payouts_{period}.ndjson")
    payouts_csv = payouts_ndjson.with_suffix(".csv")
    assumptions = payouts_ndjson.with_name(payouts_ndjson.stem + "_assumptions.json")

    print_section("Computing payouts")
    r = subprocess.run(
        [sys.executable, str(pay_py),
         "--input", str(path),
         "--period", period,
         "--eur-total", str(budget),
         "--out-ndjson", str(payouts_ndjson),
         "--out-csv", str(payouts_csv),
         "--out-assumptions", str(assumptions),
        ],
        capture_output=True, text=True
    )
    if r.stdout.strip(): print(r.stdout.strip())
    if r.returncode == 0:
        print_ok(f"Payouts written: {payouts_ndjson}")
        print_ok(f"CSV:             {payouts_csv}")
        print_ok(f"Assumptions:     {assumptions}")
    else:
        print_error("Payout computation failed")
        if r.stderr.strip(): print(r.stderr.strip())
        sys.exit(1)
    print()
    print_section("Next step")
    print_suggestion(f"crovia bundle --receipts {path} --payouts {payouts_ndjson}")


def cmd_bundle(args: argparse.Namespace) -> None:
    """
    crovia bundle --receipts X --payouts Y [--compliance Z]
    → Trust bundle JSON
    """
    print_header("Bundle (Trust & Evidence Pack)")

    receipts = Path(args.receipts)
    payouts = Path(args.payouts)
    compliance = Path(args.compliance) if args.compliance else None

    for p in (receipts, payouts):
        if not p.exists():
            print_error(f"File not found: {p}")
            sys.exit(1)
    if compliance and not compliance.exists():
        print_warn(f"Compliance pack not found (will be ignored): {compliance}")
        compliance = None

    print_section("Input")
    print(f"• Receipts: {receipts}")
    print(f"• Payouts: {payouts}")
    if compliance:
        print(f"• Compliance pack: {compliance}")
    else:
        print("• Compliance pack: none")
    print()

    out_path = Path(args.out or "crovia_trust_bundle.json")

    def _sha256(p):
        import hashlib
        if not p.exists(): return None
        return hashlib.sha256(p.read_bytes()).hexdigest()

    artifacts = {
        "receipts": {"file": str(receipts), "sha256": _sha256(receipts)},
        "payouts": {"file": str(payouts), "sha256": _sha256(payouts)},
    }
    if compliance:
        artifacts["compliance"] = {"file": str(compliance), "sha256": _sha256(compliance)}

    # Check for existing hashchain
    chain_candidates = list(Path(".").glob(f"*hashchain*{receipts.stem}*")) + \
                       list(Path("proofs").glob(f"*{receipts.stem}*")) if Path("proofs").exists() else \
                       list(Path(".").glob(f"*hashchain*{receipts.stem}*"))
    if chain_candidates:
        artifacts["hashchain"] = {"file": str(chain_candidates[0]), "sha256": _sha256(chain_candidates[0])}

    bundle_doc = {
        "schema": "crovia_trust_bundle.v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "artifacts": artifacts,
    }
    out_path.write_text(json.dumps(bundle_doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print_ok(f"Bundle written: {out_path}")
    print(f"  Artifacts included: {', '.join(artifacts.keys())}")
    print()
    print_section("Next step")
    if CONFIG.get("auto_sign"):
        print_suggestion(f"crovia sign {out_path}  # auto_sign is ON")
    else:
        print_suggestion(f"crovia sign {out_path}")


def cmd_sign(args: argparse.Namespace) -> None:
    
    """
    crovia sign <file> [--env VAR] [--out PATH]
    → DEMO-ONLY HMAC-SHA256 signer for JSON / NDJSON artifacts (open-core).

    - JSON  (e.g. trust_bundle_2025-11.json): single object with a "signature" field.
    - NDJSON (receipts, payouts): each line gets its own "signature" field.
    """
    from pathlib import Path

    path = Path(args.file)
    if not path.exists():
        print_error(f"File not found: {path}")
        return

    env_var = getattr(args, "env", None) or "CROVIA_HMAC_KEY"
    import os
    key = os.getenv(env_var, "")
    if not key:
        print_error(f"Env var {env_var} is not set. Export a secret key before signing.")
        return

    out_path = Path(getattr(args, "out", None) or f"{path.with_suffix('')}.signed{path.suffix}")

    def hmac_hex(payload: bytes) -> str:
        return hmac.new(key.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    # Decide JSON vs NDJSON
    try:
        raw = path.read_bytes()
    except Exception as e:
        print_error(f"Failed reading file: {e}")
        return

    text = raw.decode("utf-8", errors="replace")
    is_ndjson = "\n" in text and not text.lstrip().startswith("{")

    # If file endswith .ndjson, treat as NDJSON no matter what
    if path.suffix.lower() == ".ndjson":
        is_ndjson = True

    if is_ndjson:
        signed = 0
        out_lines = []
        for i, line in enumerate(text.splitlines()):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                # Preserve invalid lines (but warn)
                out_lines.append(line)
                continue
            # Canonical payload for signing: original line bytes (stable)
            sig = hmac_hex(line.encode("utf-8"))
            obj["signature"] = sig
            out_lines.append(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
            signed += 1

        try:
            out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        except Exception as e:
            print_error(f"Error while writing signed NDJSON: {e}")
            return

        print_ok("CROVIA — Sign (HMAC Signature)")
        print(f"• Input:  {path}")
        print(f"• Output: {out_path}")
        print(f"• Lines signed:   {signed}")
        return

    # JSON object
    try:
        obj = json.loads(text)
    except Exception as e:
        print_error(f"Invalid JSON: {e}")
        return

    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac_hex(payload)

    if not isinstance(obj, dict):
        print_warn("Top-level JSON is not an object; signing anyway with a 'signature' field.")
        obj = {"value": obj}

    meta_sig = obj.get("signature_meta") or {}
    meta_sig["demo_signer"] = True
    obj["signature_meta"] = meta_sig
    obj["signature"] = sig

    try:
        out_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        print_error(f"Error while writing signed JSON: {e}")
        return

    print_ok("CROVIA — Sign (HMAC Signature)")
    print(f"• Input:  {path}")
    print(f"• Output: {out_path}")

def cmd_trace(args: argparse.Namespace) -> None:
    """
    crovia trace <ndjson> [--verify chainfile]
    → Hashchain write/verify
    """
    print_header("Trace (Hashchain)")

    source = Path(args.file)
    if not source.exists():
        print_error(f"Source file not found: {source}")
        sys.exit(1)

    # Locate hashchain scripts relative to this file
    _cli_dir = Path(__file__).parent.parent
    hashchain_writer = _cli_dir / "proofs" / "hashchain_writer.py"
    hashchain_verifier = _cli_dir / "proofs" / "verify_hashchain.py"

    if args.verify:
        chain = Path(args.verify)
        if not chain.exists():
            print_error(f"Hashchain file not found: {chain}")
            sys.exit(1)
        if hashchain_verifier.exists():
            print_section("Hashchain verification")
            r = subprocess.run([sys.executable, str(hashchain_verifier),
                "--source", str(source), "--chain", str(chain)], capture_output=True, text=True)
            print(r.stdout.strip())
            if r.returncode == 0:
                print_ok("Hashchain verified — chain is consistent.")
            else:
                print_error("Hashchain verification FAILED")
                if r.stderr: print(r.stderr.strip())
                sys.exit(1)
        else:
            print_error("hashchain verifier not found in proofs/")
            sys.exit(1)
    else:
        out_path = Path(args.out or f"proofs/hashchain_{source.name}.txt")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if hashchain_writer.exists():
            print_section("Hashchain generation")
            r = subprocess.run([sys.executable, str(hashchain_writer),
                "--source", str(source), "--out", str(out_path)], capture_output=True, text=True)
            print(r.stdout.strip())
            if r.returncode == 0:
                print_ok(f"Hashchain written: {out_path}")
            else:
                print_error("Hashchain generation failed")
                if r.stderr: print(r.stderr.strip())
                sys.exit(1)
        else:
            print_error("hashchain_writer.py not found in proofs/")
            sys.exit(1)

    print()
    print_section("Next step")
    print_suggestion(f"crovia trace {source} --verify {args.out or f'proofs/hashchain_{source.name}.txt'}  # verify the chain")


def cmd_explain(args: argparse.Namespace) -> None:
    """
    crovia explain <file.json|.crovia|.signed.json>
    → Light metacognitive view
    """
    print_header("Explain (Metacognitive View)")

    path = Path(args.file)
    if not path.exists():
        print_error(f"File not found: {path}")
        sys.exit(1)

    text = path.read_text(encoding="utf-8", errors="replace")
    is_ndjson = path.suffix.lower() == ".ndjson" or ("\n" in text and not text.lstrip().startswith("{"))

    if is_ndjson:
        lines = [l for l in text.splitlines() if l.strip()]
        records = []
        errors = 0
        for l in lines:
            try: records.append(json.loads(l))
            except Exception: errors += 1
        print_section("Structure")
        print(f"  Type:    NDJSON")
        print(f"  Lines:   {len(lines)} total, {len(records)} valid, {errors} unparseable")
        if records:
            sample = records[0]
            keys = list(sample.keys()) if isinstance(sample, dict) else []
            print(f"  Schema:  {sample.get('schema', sample.get('type', 'unknown'))}")
            print(f"  Fields:  {', '.join(keys[:8])}{'...' if len(keys) > 8 else ''}")
        print()
        print_section("Integrity")
        signed = sum(1 for r in records if isinstance(r, dict) and "signature" in r)
        if signed == len(records) and len(records) > 0:
            print_ok(f"All {signed} records signed")
        elif signed > 0:
            print_warn(f"{signed}/{len(records)} records signed")
        else:
            print_warn("No signatures found — run: crovia sign <file>")
        return

    try:
        data = json.loads(text)
    except Exception:
        print_warn("Could not parse file as JSON or NDJSON.")
        print(f"  Path: {path}")
        print(f"  Size: {path.stat().st_size} bytes")
        return

    print_section("Structure")
    if isinstance(data, dict):
        keys = list(data.keys())
        print(f"  Type:    JSON object")
        print(f"  Schema:  {data.get('schema', 'not declared')}")
        print(f"  Fields:  {', '.join(keys[:8])}{'...' if len(keys) > 8 else ''}")
    print()
    print_section("Integrity")
    if "signature" in data:
        print_ok("Signature present")
    else:
        print_warn("No signature — run: crovia sign <file>")
    if "hashchain" in data.get("artifacts", {}):
        print_ok("Hashchain reference present")
    if "schema" not in data:
        print_warn("No schema field declared")


def cmd_mode(args: argparse.Namespace) -> None:
    """
    crovia mode [show|tarik|default|reset]
    → Manage user profile and preferences
    """
    global CONFIG
    print_header("Mode (User Profile)")

    sub = args.action
    if sub == "show":
        print_section("Current config")
        print(json.dumps(CONFIG, indent=2))
        return

    if sub == "operator":
        CONFIG["mode"] = "operator"
        if CONFIG.get("default_budget") is None:
            CONFIG["default_budget"] = 1_000_000
        CONFIG["auto_hashchain"] = True
        CONFIG["auto_sign"] = True
        CONFIG["prefer_interactive"] = True
        save_config(CONFIG)
        print_ok("Operator Mode activated.")
    elif sub == "default":
        CONFIG["mode"] = "default"
        save_config(CONFIG)
        print_ok("Mode set to: default.")
    elif sub == "reset":
        CONFIG = DEFAULT_CONFIG.copy()
        save_config(CONFIG)
        print_ok("Config reset to default values.")


# ==========================
#  MAIN + ARGPARSE
# ==========================


# ==========================
#  OPEN-CORE PACK COMMANDS (crovia-core-engine-open)
# ==========================

def _open_core_path(*parts: str) -> Path:
    return Path("/opt/crovia/crovia-core-engine-open").joinpath(*parts)


def cmd_pack(args: argparse.Namespace) -> None:
    """
    crovia pack --source <ndjson> [--out <dir>] [--chunk N]
    -> Build a minimal open-core Evidence Pack (validate + hashchain).
    """
    print_header("Pack (Evidence Pack)")

    src = Path(args.source)
    if not src.exists():
        print_error(f"Source not found: {src}")
        raise SystemExit(1)

    out_dir = Path(args.out) if args.out else (Path("packs") / (src.stem + "_pack"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) validate -> report.md
    validate_py = _open_core_path("validate", "validate.py")
    report_md = out_dir / "report.md"
    cmd1 = [sys.executable, str(validate_py), "--in", str(src), "--out", str(report_md)]
    print_section("Validate")
    print(" ".join(cmd1))
    r = subprocess.run(cmd1)
    if r.returncode not in (0, 2):
        print_warn(f"Validator returned code {r.returncode} (report written anyway)")

    # 2) hashchain -> proofs/hashchain_*.txt
    proofs_dir = out_dir / "proofs"
    proofs_dir.mkdir(parents=True, exist_ok=True)
    hashchain_py = _open_core_path("proofs", "hashchain_writer.py")
    chain_out = proofs_dir / ("hashchain_" + src.name + ".txt")
    cmd2 = [
        sys.executable,
        str(hashchain_py),
        "--source", str(src),
        "--out", str(chain_out),
        "--chunk", str(args.chunk),
    ]
    print_section("Hashchain")
    print(" ".join(cmd2))
    r2 = subprocess.run(cmd2)
    if r2.returncode != 0:
        print_error("Hashchain writer failed")
        raise SystemExit(r2.returncode)

    print_ok(f"Pack folder ready: {out_dir}")
    print_suggestion(f"Next: crovia verify-pack --source {src} --chain {chain_out} --chunk {args.chunk}")


def cmd_verify_pack(args: argparse.Namespace) -> None:
    """
    crovia verify-pack --source <ndjson> --chain <txt> [--chunk N]
    -> Verify open-core hashchain proof.
    """
    print_header("Verify Pack (Hashchain)")

    src = Path(args.source)
    chain = Path(args.chain)
    if not src.exists():
        print_error(f"Source not found: {src}")
        raise SystemExit(1)
    if not chain.exists():
        print_error(f"Chain not found: {chain}")
        raise SystemExit(1)

    verify_py = _open_core_path("proofs", "verify_hashchain.py")
    cmd = [
        sys.executable,
        str(verify_py),
        "--source", str(src),
        "--chain", str(chain),
        "--chunk", str(args.chunk),
    ]
    print_section("Verify")
    print(" ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode == 0:
        print_ok("Hashchain OK")
    else:
        print_error("Hashchain FAIL")
        raise SystemExit(r.returncode)


# ==========================
#  RUN — OPEN CORE ORCHESTRATOR
# ==========================

def cmd_run(args: argparse.Namespace) -> None:
    """
    crovia run
    → Deterministic open-core end-to-end pipeline
    """

    print_header("Run (Open-Core Orchestrator)")

    receipts = Path(args.receipts)
    if not receipts.exists():
        print_error(f"Receipts file not found: {receipts}")
        sys.exit(1)

    period = args.period
    budget = args.budget
    out_dir = Path(args.out)

    out_dir.mkdir(parents=True, exist_ok=True)

    # Copy receipts into output dir (CRC-1 requires self-contained pack)
    receipts_copy = out_dir / "receipts.ndjson"
    shutil.copyfile(receipts, receipts_copy)
    receipts = receipts_copy

    print_section("Inputs")
    print(f"• Receipts: {receipts}")
    print(f"• Period:   {period}")
    print(f"• Budget:   {budget}")
    print(f"• Output:   {out_dir}")
    print()

    # 1) Validate
    print_section("Step 1/5 — Validate")
    validate_md = out_dir / "validate_report.md"
    validate_bad = out_dir / "validate_bad.ndjson"
    subprocess.run([
        sys.executable,
        "validate/validate.py",
        str(receipts),
        "--out-md", str(validate_md),
        "--out-bad", str(validate_bad),
    ], check=True)
    print_ok("Validation completed")

    # 2) Payouts
    print_section("Step 2/5 — Payouts")
    payouts_ndjson = out_dir / "payouts.ndjson"
    payouts_csv = out_dir / "payouts.csv"
    subprocess.run([
        sys.executable,
        "core/payouts_from_royalties.py",
        "--input", str(receipts),
        "--period", period,
        "--eur-total", str(budget),
        "--out-ndjson", str(payouts_ndjson),
        "--out-csv", str(payouts_csv),
    ], check=True)
    print_ok("Payouts computed")

    # 3) Trust bundle (built inline — aggregates artifacts + hashes)
    print_section("Step 3/5 — Trust bundle")
    bundle = out_dir / "trust_bundle.json"
    def _file_sha256(p):
        if not p.exists():
            return None
        return hashlib.sha256(p.read_bytes()).hexdigest()

    bundle_doc = {
        "schema": "crovia_trust_bundle.v1",
        "period": period,
        "budget_eur": budget,
        "artifacts": {
            "receipts": {"file": receipts.name, "sha256": _file_sha256(receipts)},
            "payouts_ndjson": {"file": payouts_ndjson.name, "sha256": _file_sha256(payouts_ndjson)},
            "payouts_csv": {"file": payouts_csv.name, "sha256": _file_sha256(payouts_csv)},
            "validate_report": {"file": validate_md.name, "sha256": _file_sha256(validate_md)},
        },
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    bundle.write_text(json.dumps(bundle_doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print_ok("Trust bundle created")

    # 4) Hashchain
    print_section("Step 4/5 — Hashchain")
    hashchain = out_dir / "hashchain.txt"
    subprocess.run([
        sys.executable,
        "proofs/hashchain_writer.py",
        "--source", str(receipts),
        "--out", str(hashchain),
    ], check=True)
    print_ok("Hashchain generated")

    # 5) Manifest
    print_section("Step 5/5 — Manifest")
    manifest = out_dir / "MANIFEST.json"
    manifest.write_text(json.dumps({
        "schema": "crovia.manifest.v1",
        "contract": "CRC-1",
        "period": period,
        "budget": budget,
        "artifacts": {
            "receipts": receipts.name,
            "validate_report": validate_md.name,
            "payouts_ndjson": payouts_ndjson.name,
            "payouts_csv": payouts_csv.name,
            "trust_bundle": bundle.name,
            "hashchain": hashchain.name,
        }
    }, indent=2), encoding="utf-8")

    print_ok("Manifest written")
    print()
    print_ok("crovia run completed successfully")
    print_suggestion(f"Inspect output: {out_dir}")


# ---- argparse binding for run ----
def _bind_run(sub):
    p = sub.add_parser("run", help="Run full open-core pipeline")
    p.add_argument("--receipts", required=True, help="Input receipts NDJSON")
    p.add_argument("--period", required=True, help="Period (e.g. 2025-11)")
    p.add_argument("--budget", required=True, type=float, help="Total budget (EUR)")
    p.add_argument("--out", required=True, help="Output directory")
    p.set_defaults(func=cmd_run)


# ==========================
#  WEDGE COMMANDS
# ==========================

_WEDGE_PRIMARY = [
    "EVIDENCE.json",
    "trust_bundle.v1.json",
    "cep_capsule.v1.json",
    "crovia_manifest.json",
    "crovia_trust_bundle.json",
]
_WEDGE_SECONDARY = [
    "receipts*.ndjson",
    "payouts*.ndjson",
    "hashchain*.txt",
    ".crovia/cfic_certificate.json",
    "CFIC.json",
]


def _wedge_check(root: Path):
    """Scan a directory for Crovia evidence artifacts. Returns (found, status, details)."""
    found = []
    for name in _WEDGE_PRIMARY:
        if (root / name).exists():
            found.append(name)
    # glob for receipts/payouts/hashchain
    for pattern in ["receipts*.ndjson", "payouts*.ndjson", "hashchain*.txt"]:
        matches = list(root.glob(pattern))
        if matches:
            found.append(f"{pattern} ({len(matches)} file(s))")
    # CFIC
    for marker in [".crovia/cfic_certificate.json", "CFIC.json"]:
        if (root / marker).exists():
            found.append(f"[CFIC] {marker}")
    # gap_index
    gap_index = root / "gaps" / "gap_index.jsonl"
    critical = 0
    if gap_index.exists():
        for line in gap_index.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(line)
                if o.get("severity", 0) >= 0.8:
                    critical += 1
            except Exception:
                pass
    status = "GREEN" if found and critical == 0 else ("RED" if not found else "YELLOW")
    return found, status, critical


def cmd_wedge_scan(args: argparse.Namespace) -> None:
    print_header("Wedge — Evidence Presence Scan")
    root = Path(getattr(args, "path", ".")).resolve()
    mode = getattr(args, "mode", "warn")
    print_section("Scanning")
    print(f"  Directory: {root}")
    print()
    found, status, critical = _wedge_check(root)
    print_section("Evidence artifacts found")
    if found:
        for f in found:
            print_ok(f)
    else:
        print_warn("No Crovia evidence artifacts detected in this directory.")
    print()
    print_section("Verdict")
    if status == "GREEN":
        print_ok("GREEN — Auditable training evidence present.")
    elif status == "YELLOW":
        print_warn(f"YELLOW — Evidence present but {critical} critical gap(s) detected.")
    else:
        print_warn("RED — No auditable training evidence detected.")
    print()
    if status == "RED" and mode == "fail":
        print_error("Exiting with code 1 (--mode fail)")
        sys.exit(1)
    print_suggestion("Run 'crovia run' to generate a full evidence pack for this directory.")


def cmd_wedge_status(args: argparse.Namespace) -> None:
    root = Path(getattr(args, "path", ".")).resolve()
    found, status, critical = _wedge_check(root)
    color = GREEN if status == "GREEN" else (YELLOW if status == "YELLOW" else RED)
    print(c(f"[WEDGE] {status}", color + BOLD), f"| {len(found)} artifact(s) | {critical} critical gap(s) | {root}")


def cmd_wedge_explain(args: argparse.Namespace) -> None:
    print_header("Wedge — Evidence Artifacts Reference")
    print_section("Primary artifacts (any one is sufficient)")
    for name in _WEDGE_PRIMARY:
        print(f"  {name}")
    print()
    print_section("Secondary artifacts (strengthen the evidence)")
    for name in _WEDGE_SECONDARY:
        print(f"  {name}")
    print()
    print_section("How to generate them")
    print_suggestion("crovia run --receipts <file> --period YYYY-MM --budget N --out <dir>")
    print_suggestion("crovia sign <trust_bundle.json>")
    print_suggestion("crovia trace <receipts.ndjson>")
    print()
    print_section("Verdict logic")
    print("  GREEN  = at least one primary artifact found, no critical gaps")
    print("  YELLOW = artifacts found but critical gaps detected")
    print("  RED    = no artifacts found")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="crovia",
        description="CroviaTrust CLI — Evidence & Payout Engine for AI datasets"
    )
    sub = p.add_subparsers(dest="command")

    # legend
    sp = sub.add_parser("legend", help="Explain Crovia philosophy and flows")
    sp.set_defaults(func=cmd_legend)


    # scan
    sp = sub.add_parser("scan", help="Spider / dataset attribution")
    sp.add_argument("dataset", help="Path to the dataset (e.g. NDJSON)")
    sp.add_argument("--out", help="Output NDJSON with generated receipts")
    sp.add_argument("--env", default="CROVIA_HMAC_KEY", help="Env var holding HMAC key")
    sp.set_defaults(func=cmd_scan)

    # check
    sp = sub.add_parser(
        "check",
        help="Validate receipts and basic AI Act readiness",
    )
    sp.add_argument("file", help="Receipts NDJSON file")
    sp.set_defaults(func=cmd_check)

    # refine
    sp = sub.add_parser(
        "refine",
        help="Auto-fix inconsistencies (share_sum, rank, etc.)",
    )
    sp.add_argument("file", help="Receipts NDJSON file to refine")
    sp.add_argument("--out", help="Output path for refined NDJSON")
    sp.set_defaults(func=cmd_refine)

    # pay
    sp = sub.add_parser(
        "pay",
        help="Compute payouts for a given period",
    )
    sp.add_argument("file", help="Receipts NDJSON file")
    sp.add_argument("--period", required=True, help="Period in YYYY-MM format")
    sp.add_argument("--budget", type=float, help="Total budget in EUR")
    sp.add_argument("--out", help="Output NDJSON file for payouts")
    sp.set_defaults(func=cmd_pay)

    # bundle
    sp = sub.add_parser(
        "bundle",
        help="Create a Crovia trust bundle JSON",
    )
    sp.add_argument("--receipts", required=True, help="Receipts NDJSON path")
    sp.add_argument("--payouts", required=True, help="Payouts NDJSON path")
    sp.add_argument(
        "--compliance",
        help="Optional compliance pack JSON (AI Act, etc.)",
    )
    sp.add_argument("--out", help="Output bundle JSON path")
    sp.set_defaults(func=cmd_bundle)

    # sign
    sp = sub.add_parser(
        "sign",
        help="HMAC-sign a JSON/NDJSON file",
    )
    sp.add_argument("file", help="File to sign (JSON or NDJSON)")
    sp.add_argument(
        "--env",
        help="Env var name with HMAC key (default: CROVIA_HMAC_KEY)",
    )
    sp.add_argument("--out", help="Output signed file path")
    sp.set_defaults(func=cmd_sign)

    # trace
    sp = sub.add_parser(
        "trace",
        help="Create or verify a hashchain",
    )
    sp.add_argument("file", help="Source NDJSON file")
    sp.add_argument(
        "--out",
        help="Output hashchain path when generating",
    )
    sp.add_argument(
        "--verify",
        help="Existing hashchain file to verify against",
    )
    sp.set_defaults(func=cmd_trace)

    # explain
    sp = sub.add_parser(
        "explain",
        help="Metacognitive view on JSON/.crovia file",
    )
    sp.add_argument("file", help="File to inspect")
    sp.set_defaults(func=cmd_explain)

    # mode
    sp = sub.add_parser(
        "mode",
        help="Manage CLI profile (e.g. Operator Mode)",
    )
    sp.add_argument(
        "action",
        choices=["show", "operator", "default", "reset"],
        help="Action to apply to the current profile",
    )
    sp.set_defaults(func=cmd_mode)

    # ==========================
    #  WEDGE (Evidence Presence Wedge)
    # ==========================

    wedge = sub.add_parser(
        "wedge",
        help="Evidence Presence Wedge (absence / presence signals)",
    )
    wedge_sub = wedge.add_subparsers(dest="wedge_cmd")

    ws = wedge_sub.add_parser("scan", help="Scan current directory for evidence artifacts")
    ws.add_argument("--path", default=".", help="Directory to scan (default: current)")
    ws.add_argument("--mode", choices=["warn", "fail"], default="warn", help="Fail on RED status")
    ws.set_defaults(func=cmd_wedge_scan)

    ws = wedge_sub.add_parser("status", help="Show wedge status of current directory")
    ws.add_argument("--path", default=".", help="Directory to check (default: current)")
    ws.set_defaults(func=cmd_wedge_status)

    ws = wedge_sub.add_parser("explain", help="Explain what evidence artifacts Crovia looks for")
    ws.set_defaults(func=cmd_wedge_explain)

    # ==========================
    #  ORACLE (Omission Oracle)
    # ==========================
    try:
        from crovia.oracle import bind_oracle_commands
        bind_oracle_commands(sub)
    except ImportError:
        pass  # Oracle module not available

    # ==========================
    #  LICENSE (Auth & License Management)
    # ==========================
    license_p = sub.add_parser("license", help="Manage Crovia license")
    license_sub = license_p.add_subparsers(dest="license_cmd")

    ls = license_sub.add_parser("status", help="Show license status")
    ls.set_defaults(func=lambda args: _cmd_license_status())

    la = license_sub.add_parser("activate", help="Activate a license key")
    la.add_argument("key", help="License key (CRV-PRO-XXXX-XXXX-XXXX)")
    la.set_defaults(func=lambda args: _cmd_license_activate(args.key))

    # ==========================
    #  ZK-BRIDGE PREVIEW (Open Core Teaser)
    # ==========================

    bridge = sub.add_parser(
        "bridge",
        help="Crovia ZK-Bridge Preview - Technical Authority for AI Compliance",
    )
    bridge_sub = bridge.add_subparsers(dest="bridge_cmd")

    # Preview compliance
    bp = bridge_sub.add_parser("preview", help="Preview compliance potential")
    bp.add_argument("model", help="Model ID or HuggingFace repo")
    bp.set_defaults(func=lambda args: cmd_bridge_preview(args))

    # List PRO capabilities
    bl = bridge_sub.add_parser("upgrades", help="List PRO upgrade capabilities")
    bl.set_defaults(func=lambda args: cmd_bridge_upgrades(args))

    # Demo PRO capability
    bd = bridge_sub.add_parser("demo", help="Demo PRO capability")
    bd.add_argument("capability", help="Capability ID to demo")
    bd.set_defaults(func=lambda args: cmd_bridge_demo(args))

    # run (open-core orchestrator)
    _bind_run(sub)

    return p


def cmd_bridge_preview(args):
    """Preview compliance potential for a model."""
    from .bridge_preview import preview_compliance
    
    try:
        preview = preview_compliance(args.model)
        
        print_ok(f"🔍 Compliance Preview: {args.model}")
        print()
        
        print(f"📊 Current Score (Open): {preview.preview_score:.1%}")
        print(f"🚀 Potential Score (PRO): {preview.potential_score:.1%}")
        print(f"📈 Improvement: +{(preview.potential_score - preview.preview_score):.1%}")
        print()
        
        print("🌍 Global Coverage:")
        for reg, scores in preview.global_coverage.items():
            current = scores.get("current", 0)
            potential = scores.get("potential", 0)
            print(f"  {reg}: {current:.1%} -> {potential:.1%}")
        print()
        
        if preview.missing_capabilities:
            print("🔓 Missing PRO Capabilities:")
            for cap in preview.missing_capabilities:
                print(f"  • {cap}")
            print()
        
        if preview.upgrade_benefits:
            print("💎 Upgrade Benefits:")
            for benefit in preview.upgrade_benefits:
                print(f"  • {benefit}")
            print()
        
        print("💡 Upgrade to crovia-pro for full technical authority")
        
    except Exception as e:
        print_error(f"Preview failed: {e}")


def cmd_bridge_upgrades(args):
    """List all PRO upgrade capabilities."""
    from .bridge_preview import list_upgrades
    
    try:
        capabilities = list_upgrades()
        
        print_ok("🚀 Crovia PRO Capabilities")
        print()
        
        for cap in capabilities:
            print(f"💎 {cap.name}")
            print(f"   {cap.description}")
            print(f"   📋 Coverage: {', '.join(cap.regulatory_coverage)}")
            print(f"   🔍 Evidence: {', '.join(cap.evidence_types)}")
            print()
        
        print("💡 Upgrade to crovia-pro to unlock all capabilities")
        
    except Exception as e:
        print_error(f"Failed to list capabilities: {e}")


def cmd_bridge_demo(args):
    """Demo a PRO capability."""
    from .bridge_preview import demo_capability
    
    try:
        demo = demo_capability(args.capability)
        
        if "error" in demo:
            print_error(f"Capability not available: {args.capability}")
            return
        
        print_ok(f"🎬 Demo: {demo['name']}")
        print()
        print(f"📋 Description: {demo['name']}")
        print(f"🌍 Coverage: {', '.join(demo['regulatory_coverage'])}")
        print(f"🔍 Evidence Types: {', '.join(demo['evidence_types'])}")
        print()
        
        if "sample_results" in demo:
            print("📊 Sample Results:")
            for key, value in demo["sample_results"].items():
                print(f"  {key}: {value}")
            print()
        
        print(f"💡 {demo['upgrade_message']}")
        
    except Exception as e:
        print_error(f"Demo failed: {e}")


def _cmd_license_status():
    try:
        from crovia.auth import print_license_status
        print_license_status()
    except ImportError:
        print_warn("Auth module not available")
    return 0


def _cmd_license_activate(key):
    try:
        from crovia.auth import activate_license
        return 0 if activate_license(key) else 1
    except ImportError:
        print_warn("Auth module not available")
        return 1


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    # In the future, this is where command guessing could be added.
    return args.func(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
