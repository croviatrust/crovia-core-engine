#!/usr/bin/env python3
"""
crovia.cli — CroviaTrust CLI (v0.1, Phase 1+2 UX)

Entry point:
    crovia <command> [options]

Commands:
    legend, scan, check, refine, pay, bundle, sign, trace, explain, mode
"""

import argparse
import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

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
# ==========================

def cmd_legend(args: argparse.Namespace) -> None:
    """
    crovia legend
    → Human-friendly overview of commands, flows, and what Crovia is about.
    """
    print_header("Legend (How Crovia thinks about evidence & payouts)")

    print_section("What this CLI really is")
    print(
        "This is not just another \"SDK\" for logs.\n"
        "CroviaTrust is your evidence + payout engine for AI datasets:\n"
        "- it turns raw attribution logs into receipts,\n"
        "- receipts into payouts,\n"
        "- and everything into a trust bundle you can show in public."
    )
    print()
    print("Behind this CLI there is a very simple idea:")
    print("if an AI model makes money on your data, there should be a receipt,")
    print("and that receipt should be auditable by anyone — not just a black-box SaaS.")
    print()

    print_section("Typical end-to-end pipeline")
    print("1) crovia scan   <dataset.ndjson>")
    print("   → Take a raw/open dataset and (for now) simulate attribution receipts.")
    print()
    print("2) crovia check  data/royalty_receipts.ndjson")
    print("   → Validate receipts + basic AI Act readiness (open-core validators).")
    print()
    print("3) crovia refine data/royalty_receipts.ndjson --out data/royalty_refined.ndjson")
    print("   → (Optional) Auto-fix share_sum / rank weirdness before money moves.")
    print()
    print("4) crovia pay    data/royalty_refined.ndjson --period 2025-11 --budget 1000000")
    print("   → Turn receipts into payouts for a given month and budget.")
    print()
    print("5) crovia bundle --receipts data/royalty_refined.ndjson --payouts payouts_2025-11.ndjson")
    print("   → Build a trust bundle JSON for audits, reports, and model cards.")
    print()
    print("6) crovia sign   crovia_trust_bundle.json")
    print("   → Add an HMAC signature (CROVIA_HMAC_KEY) so you can prove integrity.")
    print()
    print("7) crovia trace  data/royalty_refined.ndjson --out proofs/hashchain_receipts.txt")
    print("   → Create a hashchain over receipts (or verify an existing chain).")
    print()
    print("8) crovia explain crovia_trust_bundle.json")
    print("   → Get a quick structural view: schema, signature, hashes, links.")
    print()

    print_section("Command cheatsheet")
    print("• legend  → This legend + recommended flows.")
    print("• scan    → Spider / dataset attribution (demo receipts for now).")
    print("• check   → Schema + business validation + AI Act hints.")
    print("• refine  → Heuristic clean-up of suspicious receipts.")
    print("• pay     → Turn receipts into payouts (plus charts, in the open-core).")
    print("• bundle  → Assemble all evidence into a single JSON trust bundle.")
    print("• sign    → HMAC-sign JSON/NDJSON artifacts.")
    print("• trace   → Hashchain generator / verifier.")
    print("• explain → Metacognitive view on any Crovia JSON/.crovia file.")
    print("• mode    → CLI profile (Tarik Mode, defaults, auto-sign, etc.).")
    print()

    print_section("If you are completely new, do this")
    print("1) Put a demo receipts file under ./data/")
    print("2) Run:")
    print("     crovia check data/royalty_receipts.ndjson")
    print("3) Then:")
    print("     crovia pay data/royalty_receipts.ndjson --period 2025-11 --budget 1000000")
    print("4) Then:")
    print("     crovia bundle --receipts data/royalty_receipts.ndjson --payouts payouts_2025-11.ndjson")
    print()
    print_suggestion("You can always run 'crovia legend' again if you get lost.")
    print()

    print_section("Crovia philosophy")
    print("The more we dare to differ, the more we become Crovia.")
    print("And the more Crovia becomes itself, the more others become Crovia too.")
    print()

    if is_tarik_mode():
        print_suggestion("Tarik Mode is active — default budget, auto-sign and auto-hashchain are on.")
    else:
        print_suggestion("Tip: run 'crovia mode tarik' if you want the full ritual with auto-sign & hashchains.")


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
        out_path = args.out or "data/royalty_from_scan.ndjson"
        print_ok(f"(demo) Would generate receipts at: {out_path}")
        print()
        print_section("Next step")
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
    → Validation + basic AI Act compliance view (real open-core run)
    """
    print_header("Check (Integrity & Compliance)")

    path = Path(args.file)
    if not path.exists():
        print_error(f"File not found: {path}")
        sys.exit(1)

    print_section("Input")
    print(f"• File: {path}")
    print()

    # Derive output paths near the input file
    base = path.with_suffix("")
    validate_report = base.with_suffix(".validate.md")
    bad_sample = base.with_suffix(".bad.jsonl")
    compliance_summary = base.with_suffix(".compliance.md")
    compliance_gaps = base.with_suffix(".compliance_gaps.csv")
    compliance_pack = base.with_suffix(".compliance_pack.json")

    # 1) Structural + business validation (crovia_validate.py)
    print_section("Step 1 – Structural & business validation")
    try:
        proc_val = subprocess.run(
            [
                sys.executable,
                "crovia_validate.py",
                "--out-md", str(validate_report),
                "--out-bad", str(bad_sample),
                str(path),  # positional input
            ],
            capture_output=True,
            text=True,
        )
        if proc_val.stdout:
            print(proc_val.stdout.strip())
        if proc_val.stderr:
            print_warn(proc_val.stderr.strip())

        if proc_val.returncode == 0:
            print_ok("Validator finished successfully (see validation report).")
        else:
            print_warn(
                f"Validator returned exit code {proc_val.returncode} "
                f"(check {validate_report} and {bad_sample})."
            )
    except FileNotFoundError:
        print_error("crovia_validate.py not found in the current project directory.")
    except Exception as e:
        print_error(f"Unexpected error while running crovia_validate.py: {e}")

    print()

    # 2) AI Act / compliance view (compliance_ai_act.py)
    print_section("Step 2 – AI Act / compliance summary")
    try:
        proc_comp = subprocess.run(
            [
                sys.executable,
                "compliance_ai_act.py",
                "--out-summary", str(compliance_summary),
                "--out-gaps", str(compliance_gaps),
                "--out-pack", str(compliance_pack),
                str(path),  # positional input
            ],
            capture_output=True,
            text=True,
        )
        if proc_comp.stdout:
            print(proc_comp.stdout.strip())
        if proc_comp.stderr:
            print_warn(proc_comp.stderr.strip())

        if proc_comp.returncode == 0:
            print_ok("Compliance summary generated successfully.")
        else:
            print_warn(
                f"Compliance script returned exit code {proc_comp.returncode} "
                f"(check {compliance_summary} and {compliance_pack})."
            )
    except FileNotFoundError:
        print_error("compliance_ai_act.py not found in the current project directory.")
    except Exception as e:
        print_error(f"Unexpected error while running compliance_ai_act.py: {e}")

    print()

    print_section("Generated artifacts")
    print(f"• Validation report:       {validate_report}")
    print(f"• Sample of bad lines:     {bad_sample}")
    print(f"• AI Act summary (MD):     {compliance_summary}")
    print(f"• AI Act gaps (CSV):       {compliance_gaps}")
    print(f"• AI Act compliance pack:  {compliance_pack}")
    print()

    print_section("Next step")
    print_suggestion(f"crovia refine {path} --out {base.with_suffix('.refined.ndjson')}")


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
    → Run payout engine (payouts.v1 + CSV + charts + README)
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

    # Derive output artifacts
    payouts_ndjson = Path(args.out or f"payouts_{period}.ndjson")
    payouts_csv = Path(f"payouts_{period}.csv")
    readme = Path(f"README_PAYOUT_{period}.md")

    print_section("Step 1 – Compute payouts (payouts_from_royalties.py)")
    try:
        proc_pay = subprocess.run(
            [
                sys.executable,
                "payouts_from_royalties.py",
                "--input", str(path),
                "--period", str(period),
                "--eur-total", str(budget),
                "--out-ndjson", str(payouts_ndjson),
                "--out-csv", str(payouts_csv),
                "--out-assumptions", f"assumptions_{period}.json",
            ],
            capture_output=True,
            text=True,
        )
        if proc_pay.stdout:
            print(proc_pay.stdout.strip())
        if proc_pay.stderr:
            print_warn(proc_pay.stderr.strip())

        if proc_pay.returncode == 0:
            print_ok(f"Payouts computed successfully → {payouts_ndjson} / {payouts_csv}")
        else:
            print_warn(
                f"payouts_from_royalties.py exited with code {proc_pay.returncode}. "
                f"Check {payouts_ndjson} and {payouts_csv} (if created)."
            )
    except FileNotFoundError:
        print_error("payouts_from_royalties.py not found in the current project directory.")
        return
    except Exception as e:
        print_error(f"Unexpected error while running payouts_from_royalties.py: {e}")
        return

    print()
    print_section("Step 2 – Charts & README (make_payout_charts.py)")
    try:
        proc_charts = subprocess.run(
            [
                sys.executable,
                "make_payout_charts.py",
                "--period", str(period),
                "--csv", str(payouts_csv),
                "--readme", str(readme),
            ],
            capture_output=True,
            text=True,
        )
        if proc_charts.stdout:
            print(proc_charts.stdout.strip())
        if proc_charts.stderr:
            print_warn(proc_charts.stderr.strip())

        if proc_charts.returncode == 0:
            print_ok(f"Charts + README generated → {readme} (see charts/ directory).")
        else:
            print_warn(
                f"make_payout_charts.py exited with code {proc_charts.returncode}. "
                f"Check {readme} and charts/."
            )
    except FileNotFoundError:
        print_error("make_payout_charts.py not found in the current project directory.")
    except Exception as e:
        print_error(f"Unexpected error while running make_payout_charts.py: {e}")

    print()
    print_section("Generated artifacts")
    print(f"• Payouts NDJSON: {payouts_ndjson}")
    print(f"• Payouts CSV:    {payouts_csv}")
    print(f"• README:         {readme}")
    print(f"• Assumptions:    assumptions_{period}.json")
    print("• Charts:         charts/payout_top10_*.png, charts/payout_cumulative_*.png")
    print()

    print_section("Next step")
    print_suggestion(f"crovia bundle --receipts {path} --payouts {payouts_ndjson}")

def cmd_bundle(args: argparse.Namespace) -> None:
    """
    crovia bundle --receipts X --payouts Y [--compliance Z]
    → Build a Crovia trust bundle JSON tying together receipts, payouts, compliance, charts.
    """
    print_header("Bundle (Trust & Evidence Pack)")

    receipts = Path(args.receipts)
    payouts = Path(args.payouts)
    compliance = Path(args.compliance) if args.compliance else None

    # Basic existence checks
    for p in (receipts, payouts):
        if not p.exists():
            print_error(f"File not found: {p}")
            sys.exit(1)

    # Try to infer period from payouts NDJSON
    period = None
    try:
        with payouts.open("r", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rec = json.loads(ln)
                except Exception:
                    continue
                period = rec.get("period")
                break
    except Exception:
        pass

    # Auto-detect compliance pack if not provided
    if compliance is None:
        base = receipts.with_suffix("")
        auto_pack = base.with_suffix(".compliance_pack.json")
        if auto_pack.exists():
            compliance = auto_pack

    # Companion artifacts (if they exist)
    base_r = receipts.with_suffix("")
    validate_report = base_r.with_suffix(".validate.md")
    compliance_summary = base_r.with_suffix(".compliance.md")
    compliance_gaps = base_r.with_suffix(".compliance_gaps.csv")

    # Payout side artifacts
    payouts_csv = Path(f"payouts_{period}.csv") if period else None
    assumptions = Path(f"assumptions_{period}.json") if period else None

    # Charts
    charts = []
    if period:
        top10 = Path(f"charts/payout_top10_{period}.png")
        cumu = Path(f"charts/payout_cumulative_{period}.png")
        if top10.exists():
            charts.append(str(top10))
        if cumu.exists():
            charts.append(str(cumu))

    # Build bundle object
    bundle = {
        "schema": "crovia_trust_bundle.v1",
        "version": "1.0.0",
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "period": period,
        "engine": {
            "name": "Crovia Core Engine",
            "cli": "crovia",
            "cli_version": "0.1.0",
            "mode": CONFIG.get("mode"),
        },
        "artifacts": {
            "receipts_ndjson": str(receipts),
            "payouts_ndjson": str(payouts),
            "payouts_csv": str(payouts_csv) if payouts_csv and payouts_csv.exists() else None,
            "assumptions_json": str(assumptions) if assumptions and assumptions.exists() else None,
            "validation_report_md": str(validate_report) if validate_report.exists() else None,
            "compliance_summary_md": str(compliance_summary) if compliance_summary.exists() else None,
            "compliance_gaps_csv": str(compliance_gaps) if compliance_gaps.exists() else None,
            "compliance_pack_json": str(compliance) if compliance and compliance.exists() else None,
        },
        "charts": charts,
        "meta": {
            "demo": bool("demo" in receipts.name or "demo" in payouts.name),
            "notes": "Open-core trust bundle generated by CroviaTrust CLI.",
        },
    }

    out_path = Path(args.out or "crovia_trust_bundle.json")

    print_section("Input")
    print(f"• Receipts: {receipts}")
    print(f"• Payouts:  {payouts}")
    if compliance and compliance.exists():
        print(f"• Compliance pack: {compliance}")
    else:
        print("• Compliance pack: none or not found")
    print()

    print_section("Bundle summary (preview)")
    print(f"• schema: {bundle['schema']}")
    print(f"• period: {bundle['period']}")
    print(f"• demo flag: {bundle['meta']['demo']}")
    print()

    try:
        out_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        print_ok(f"Trust bundle written to: {out_path}")
    except Exception as e:
        print_error(f"Error while writing trust bundle: {e}")
        return

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
      This is NOT the enterprise attestation path (no hardware keys, no DSSE).
    - JSON  (e.g. crovia_trust_bundle.json): single object with a "signature" field.
    - NDJSON (receipts, payouts): each line gets its own "signature" field.
    """
    print_header("Sign (HMAC Signature)")

    path = Path(args.file)
    if not path.exists():
        print_error(f"File not found: {path}")
        sys.exit(1)

    env_var = args.env or "CROVIA_HMAC_KEY"
    key = os.environ.get(env_var, "")
    if not key:
        print_error(f"Env var {env_var} is not set. Export a secret key before signing.")
        print_suggestion(f"Example: export {env_var}='your-very-secret-key'")
        return

    out_path = Path(args.out or f"{path.with_suffix('')}.signed{path.suffix}")

    # Local import to avoid polluting global namespace
    import hmac, hashlib

    def compute_sig(obj: dict) -> str:
        payload = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hmac.new(key.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    print_section("Input")
    print(f"• File: {path}")
    print(f"• Env key: {env_var}")
    print(f"• Output: {out_path}")
    print()

    # Heuristic: .ndjson → line-based, everything else → single JSON
    if path.suffix == ".ndjson":
        print_section("Mode")
        print("• NDJSON mode (one JSON object per line)")
        print()

        total = 0
        signed = 0
        skipped = 0

        with path.open("r", encoding="utf-8") as fi, out_path.open("w", encoding="utf-8") as fo:
            for lineno, line in enumerate(fi, 1):
                s = line.strip()
                if not s:
                    continue
                total += 1
                try:
                    obj = json.loads(s)
                except Exception:
                    print_warn(f"Skipping invalid JSON at line {lineno}")
                    skipped += 1
                    continue
                sig = compute_sig(obj)
                obj["signature"] = sig
                fo.write(json.dumps(obj, ensure_ascii=False) + "\n")
                signed += 1

        print_section("Summary")
        print(f"• Lines read:     {total}")
        print(f"• Lines signed:   {signed}")
        print(f"• Lines skipped:  {skipped}")
    else:
        print_section("Mode")
        print("• Single JSON mode (trust bundle / config)")
        print()

        try:
            raw = path.read_text(encoding="utf-8")
            obj = json.loads(raw)
        except Exception as e:
            print_error(f"Could not parse JSON: {e}")
            return

        if not isinstance(obj, dict):
            print_warn("Top-level JSON is not an object; signing anyway with a 'signature' field.")
        # Mark this as an open-core demo signature
        meta_sig = obj.get("signature_meta") or {}
        meta_sig["demo_signer"] = True
        meta_sig["engine"] = "crovia-open-core-cli"
        obj["signature_meta"] = meta_sig
        sig = compute_sig(obj)
        obj["signature"] = sig

        try:
            out_path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print_error(f"Error while writing signed JSON: {e}")
            return

    print()
    print_ok(f"Signed file written to: {out_path}")
    print_section("Next step")
    print_suggestion(f"crovia explain {out_path}")

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
        print_ok("Simulated verification: OK — chain is consistent.")
    else:
        print_section("Hashchain generation (demo)")
        out_path = Path(args.out or f"proofs/hashchain_{source.name}.txt")
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
        print_ok("Tarik Mode activated.")
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

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="crovia",
        description=(
            "CroviaTrust CLI — Evidence & Payout Engine for AI datasets.\n"
            "Tip: run 'crovia legend' for a guided overview of the main flows."
        )
    )
    sub = p.add_subparsers(dest="command")

    # legend
    sp = sub.add_parser(
        "legend",
        help="Show command legend and recommended flows",
    )
    sp.set_defaults(func=cmd_legend)

    # scan
    sp = sub.add_parser("scan", help="Spider / dataset attribution")
    sp.add_argument("dataset", help="Path to the dataset (e.g. NDJSON)")
    sp.add_argument("--out", help="Output NDJSON with generated receipts")
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
        help="Demo HMAC signer (open-core) for JSON/NDJSON",
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
        help="Manage CLI profile (e.g. Tarik Mode)",
    )
    sp.add_argument(
        "action",
        choices=["show", "tarik", "default", "reset"],
        help="Action to apply to the current profile",
    )
    sp.set_defaults(func=cmd_mode)

    return p


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        print()
        print_suggestion("Run 'crovia legend' for a guided walkthrough of the main flows.")
        return 1

    return args.func(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
