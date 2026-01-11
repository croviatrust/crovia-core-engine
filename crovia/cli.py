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
import sys
import subprocess
from pathlib import Path

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


def is_tarik_mode() -> bool:
    return CONFIG.get("mode") == "tarik"


# ==========================
#  OUTPUT HELPERS (UX)
# ==========================

def print_header(title: str) -> None:
    line = "─" * max(40, len(title) + 20)
    print(c(line, MAGENTA))
    print(c(f"CROVIA — {title}", MAGENTA))
    print(c(line, MAGENTA))
    print()


def print_section(title: str) -> None:
    print(c(title + ":", CYAN))


def print_ok(msg: str) -> None:
    print(c("✔ " + msg, GREEN))


def print_warn(msg: str) -> None:
    print(c("⚠ " + msg, YELLOW))


def print_error(msg: str) -> None:
    print(c("✖ " + msg, RED))


def print_suggestion(msg: str) -> None:
    print(c("⋄ " + msg, MAGENTA))


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
    print("   → Turn a raw dataset into demo attribution receipts (royalty_receipt.v1).")
    print()
    print("2) crovia check  receipts.ndjson")
    print("   → Validate receipts + basic AI Act readiness report.")
    print()
    print("3) crovia refine receipts.ndjson --out refined.ndjson")
    print("   → Auto-fix share_sum / rank inconsistencies (optional).")
    print()
    print("4) crovia pay    refined.ndjson --period 2025-11 --budget 1000000")
    print("   → Compute payouts for a monthly period (open-core engine).")
    print()
    print("5) crovia bundle --receipts refined.ndjson --payouts payouts_2025-11.ndjson")
    print("   → Build a trust bundle JSON for audits / evidence.")
    print()
    print("6) crovia sign   crovia_trust_bundle.json")
    print("   → Add an HMAC signature (CROVIA_HMAC_KEY) to the bundle.")
    print()
    print("7) crovia trace  receipts.ndjson --out proofs/hashchain_receipts.txt")
    print("   → Create a hashchain over the receipts (or verify an existing one).")
    print()
    print("8) crovia explain crovia_trust_bundle.json")
    print("   → Quick structural view (schema, signature, hashes, links).")
    print()

    print_section("Command cheatsheet")
    print("• legend  → Show this legend and recommended flows.")
    print("• scan    → Spider / dataset attribution (demo receipts for now).")
    print("• check   → Schema + business validation + AI Act hints.")
    print("• refine  → Heuristic clean-up of weird receipts.")
    print("• pay     → Turn receipts into payouts (with charts).")
    print("• bundle  → Assemble all evidence into a single JSON bundle.")
    print("• sign    → HMAC-sign JSON/NDJSON artifacts.")
    print("• trace   → Hashchain generator / verifier.")
    print("• explain → Metacognitive view on any Crovia JSON/.crovia file.")
    print("• mode    → CLI profile (Operator Mode, defaults, auto-sign, etc.).")
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
    → Spider / attribution / demo receipts
    """
    print_header("Scan (Attribution Spider)")

    dataset = Path(args.dataset)
    if not dataset.exists():
        print_error(f"Dataset not found: {dataset}")
        sys.exit(1)

    print_section("Input")
    print(f"• Dataset: {dataset}")
    print()

    # Here you could inspect the first N lines to enrich the output.
    # For now, just a placeholder:
    print_section("Detection (demo)")
    print("• Type: NDJSON (guessed)")
    print("• Schema: raw / spider")
    print()

    choice = ask_menu(
        "What do you want to do next?",
        [
            "Generate receipts (royalty_receipt.v1)",
            "Extract provenance signals only",
            "Interactive inspection (TODO)",
            "Cancel",
        ],
    )

    if choice == 1:
        # TODO: integrate shard_sketch_gen.py + build_faiss_index.py + faiss_attributor_sim.py
        # e.g. subprocess.run([...]) or direct imports.
        out_path = args.out or "data/royalty_from_scan.ndjson"
        print_ok(f"(demo) Would generate receipts at: {out_path}")
        print()
        print_suggestion(f"crovia check {out_path}")

    elif choice == 2:
        print_warn("Provenance signal extraction: TODO implementation.")
    elif choice == 3:
        print_warn("Interactive inspection: TODO implementation.")
    else:
        print_warn("Cancelled by user.")


def cmd_check(args: argparse.Namespace) -> None:
    """
    crovia check <receipts.ndjson>
    → Validation + basic AI Act compliance view
    """
    print_header("Check (Integrity & Compliance)")

    path = Path(args.file)
    if not path.exists():
        print_error(f"File not found: {path}")
        sys.exit(1)

    print_section("Input")
    print(f"• File: {path}")
    print()

    # TODO: call crovia_validate.py + QA script + compliance_ai_act.py for real.
    # Example (subprocess):
    # subprocess.run([sys.executable, "crovia_validate.py", "--in", str(path)], check=True)

    # For now, demo of how results are presented:
    print_section("Integrity (demo)")
    print_ok("JSON structure: valid (simulated)")
    print_ok("Schema: royalty_receipt.v1 consistent (simulated)")
    print_warn("84 lines with share_sum out of tolerance (simulated)")
    print_warn("11 lines with unordered rank (simulated)")
    print()

    print_section("Compliance (demo)")
    print_ok("ISO8601 timestamps present (simulated)")
    print_warn("Partial license_refs in 22 lines (simulated)")
    print()

    print_section("Short explanation")
    print("share_sum out of tolerance → strong synergy between top shards or aggressive rounding.")
    print()

    print_section("Generated outputs")
    print("• validate_report.md (TODO)")
    print("• validate_sample_bad.jsonl (TODO)")
    print()

    print_section("Next step")
    print_suggestion(f"crovia refine {path}")


def cmd_refine(args: argparse.Namespace) -> None:
    """
    crovia refine <receipts.ndjson>
    → Auto-fix (share_sum, rank, etc.)
    """
    print_header("Refine (Auto-fix Heuristics)")

    path = Path(args.file)
    if not path.exists():
        print_error(f"File not found: {path}")
        sys.exit(1)

    print_section("Input")
    print(f"• File: {path}")
    print()

    # In the future you could run a first pass to count inconsistencies.
    print_section("Detected inconsistencies (demo)")
    print("• Incorrect share_sum in 84 lines (simulated)")
    print("• Unsorted rank in 11 lines (simulated)")
    print()

    choice = ask_menu(
        "How do you want to fix them?",
        [
            "Renormalize share_sum",
            "Reorder rank",
            "Both",
            "Report only (no changes)",
        ],
    )

    if choice in (1, 2, 3):
        out_path = args.out or f"{path.with_suffix('')}.refined.ndjson"
        # TODO: implement actual fixes (read NDJSON, fix, write)
        print_ok(f"(demo) Would apply fixes and save to: {out_path}")
        print()
        print_section("Next step")
        print_suggestion(f"crovia check {out_path}")
    elif choice == 4:
        print_warn("No changes applied (report only).")
    else:
        print_warn("Cancelled by user.")


def cmd_pay(args: argparse.Namespace) -> None:
    """
    crovia pay <receipts.ndjson> --period YYYY-MM --budget EUR
    → Payouts + charts
    """
    print_header("Pay (Payout Engine v1.1)")

    path = Path(args.file)
    if not path.exists():
        print_error(f"File not found: {path}")
        sys.exit(1)

    period = args.period
    budget = args.budget or CONFIG.get("default_budget")

    print_section("Input")
    print(f"• Receipts file: {path}")
    print(f"• Period: {period}")
    print(f"• Budget: {budget} EUR")
    print()

    if budget is None:
        print_warn("No budget specified and no default_budget in config.")
        print_suggestion("Re-run with --budget or set default_budget in ~/.crovia/config.json")
        return

    # TODO: call payouts_from_royalties.py + make_payout_charts.py
    # subprocess.run([...], check=True)

    print_section("Preliminary analysis (demo)")
    print("• 18,430 valid receipts (simulated)")
    print("• 42 providers (simulated)")
    print("• Cap top1: 0.55 / cap top3: 0.80 (default)")
    print()

    choice = ask_menu(
        "Proceed with these parameters?",
        ["Yes", "Change parameters (TODO)", "Cancel"],
    )
    if choice == 1:
        payouts_path = Path(args.out or f"payouts_{period}.ndjson")
        print_ok(f"(demo) Would compute payouts at: {payouts_path}")
        print_ok(f"(demo) Would also generate charts/ and README_PAYOUT_{period}.md")
        print()
        print_section("Next step")
        print_suggestion(f"crovia bundle --receipts {path} --payouts {payouts_path}")
    elif choice == 2:
        print_warn("Change-parameters UI: TODO.")
    else:
        print_warn("Cancelled by user.")


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

    # TODO: integrate trust_from_receipts.py + bundle builder
    out_path = Path(args.out or "crovia_trust_bundle.json")

    print_section("Expected content (demo)")
    print_ok("Period metadata (simulated)")
    print_ok("Provider distribution (simulated)")
    print_warn("Hashchain not included (unless you ran crovia trace)")
    print()

    print_ok(f"(demo) Would write bundle to: {out_path}")
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

    if args.verify:
        chain = Path(args.verify)
        if not chain.exists():
            print_error(f"Hashchain file not found: {chain}")
            sys.exit(1)
        print_section("Hashchain verification (demo)")
        # TODO: subprocess.run([...], check=True)
        print_ok("Simulated verification: OK — chain is consistent.")
    else:
        print_section("Hashchain generation (demo)")
        out_path = Path(args.out or f"proofs/hashchain_{source.name}.txt")
        # TODO: subprocess.run([...], check=True)
        print_ok(f"(demo) Would generate hashchain at: {out_path}")

    print()
    print_section("Next step")
    print_suggestion("crovia bundle ...  # include the hashchain in the bundle")


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

    # Demo: if JSON, show a quick top-level summary
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        print_warn("Could not parse JSON, showing basic file info only.")
        print_section("Info")
        print(f"• Path: {path}")
        print(f"• Size: {path.stat().st_size} bytes")
        return

    print_section("Structure")
    if isinstance(data, dict):
        keys = list(data.keys())
        print("• Type: JSON object")
        print(f"• Top-level keys: {', '.join(keys[:8])}{'...' if len(keys) > 8 else ''}")
        if "schema" in data:
            print(f"• schema: {data['schema']}")
    else:
        print("• JSON type: non-object")

    print()
    print_section("Strengths / weaknesses (demo)")
    if "signature" in data:
        print_ok("Signature present (field: signature)")
    else:
        print_warn("No signature found (field 'signature' missing)")

    if "hash_model" in data or "hash_data_index" in data:
        print_ok("Link to model/data index detected")
    print()

    print_section("Next step")
    print_suggestion("Extend explain() with real logic for trust bundle / receipts (TODO)")


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

    if sub == "tarik":
        CONFIG["mode"] = "tarik"
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
        choices=["show", "tarik", "default", "reset"],
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

    ws = wedge_sub.add_parser("scan", help="Run wedge scan on inputs")
    ws.set_defaults(func=lambda args: print_warn("wedge scan not wired yet"))

    ws = wedge_sub.add_parser("status", help="Show wedge status")
    ws.set_defaults(func=lambda args: print_warn("wedge status not wired yet"))

    ws = wedge_sub.add_parser("explain", help="Explain wedge signals")
    ws.set_defaults(func=lambda args: print_warn("wedge explain not wired yet"))

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

    return p


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

    print_section("Inputs")
    print(f"• Receipts: {receipts}")
    print(f"• Period:   {period}")
    print(f"• Budget:   {budget}")
    print(f"• Output:   {out_dir}")
    print()

    # 1) Validate
    print_section("Step 1/5 — Validate")
    validate_md = out_dir / "validate_report.md"
    subprocess.run([
        sys.executable,
        "validate/validate.py",
        "--in", str(receipts),
        "--out", str(validate_md),
    ], check=True)
    print_ok("Validation completed")

    # 2) Payouts
    print_section("Step 2/5 — Payouts")
    payouts = out_dir / "payouts.ndjson"
    subprocess.run([
        sys.executable,
        "payouts/payout_engine.py",
        "--in", str(receipts),
        "--period", period,
        "--budget", str(budget),
        "--out", str(payouts),
    ], check=True)
    print_ok("Payouts computed")

    # 3) Trust bundle
    print_section("Step 3/5 — Trust bundle")
    bundle = out_dir / "trust_bundle.json"
    subprocess.run([
        sys.executable,
        "pack/build_bundle.py",
        "--receipts", str(receipts),
        "--payouts", str(payouts),
        "--out", str(bundle),
    ], check=True)
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
    manifest = out_dir / "manifest.json"
    manifest.write_text(json.dumps({
        "schema": "crovia.manifest.v1",
        "period": period,
        "budget": budget,
        "artifacts": {
            "receipts": receipts.name,
            "validate_report": validate_md.name,
            "payouts": payouts.name,
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
