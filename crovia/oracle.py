#!/usr/bin/env python3
"""
crovia.oracle — Omission Oracle CLI Integration

Analyze HuggingFace models for trust declaration gaps.
Calculates Shadow Score and detects NEC# violations.

Usage:
    crovia oracle scan <model_id>
    crovia oracle batch <file>
    crovia oracle card <model_id>
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from huggingface_hub import HfApi
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

import requests as _requests

def _fetch_model_http(model_id: str) -> Dict[str, Any]:
    """Fallback: fetch model metadata via public HTTP (no token needed)."""
    try:
        r = _requests.get(f"https://huggingface.co/api/models/{model_id}", timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}

from crovia.auth import check_rate_limit, increment_usage, get_license_status, LicenseStatus

# ============================================================
# CONFIGURATION
# ============================================================

NECESSITY_CANON = {
    "NEC#1": {
        "name": "Missing data provenance",
        "description": "No training dataset declaration",
        "severity": 75,
        "eu_ai_act": "Article 10(2)"
    },
    "NEC#2": {
        "name": "Missing license attribution",
        "description": "No license or unclear terms",
        "severity": 80,
        "eu_ai_act": "Article 10(5)"
    },
    "NEC#7": {
        "name": "Missing usage scope",
        "description": "No intended use cases declared",
        "severity": 45,
        "eu_ai_act": "Article 13(3)"
    },
    "NEC#10": {
        "name": "Missing temporal validity",
        "description": "No version or date information",
        "severity": 40,
        "eu_ai_act": "Article 12(1)"
    },
    "NEC#13": {
        "name": "Missing accountable entity",
        "description": "No responsible organization declared",
        "severity": 70,
        "eu_ai_act": "Article 16"
    },
}

# ============================================================
# COLORS
# ============================================================

RESET = "\033[0m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
DIM = "\033[2m"

def c(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"

# ============================================================
# ORACLE ENGINE
# ============================================================

def analyze_model(model_id: str) -> Dict[str, Any]:
    """
    Analyze a HuggingFace model for trust violations.
    
    Returns:
        Dict with score, badge, violations, and evidence hash.
    """
    try:
        # Try HfApi first, fall back to public HTTP
        card_data = {}
        if HF_AVAILABLE:
            try:
                api = HfApi()
                info = api.model_info(model_id)
                card_data = info.card_data or {}
                license_val = card_data.get("license") or getattr(info, "license", None)
                datasets = card_data.get("datasets", []) or []
                author = info.author or ""
                tags = info.tags or []
                downloads = info.downloads or 0
                likes = info.likes or 0
                created = getattr(info, "created_at", None)
            except Exception:
                card_data = None  # signal fallback needed

        if not HF_AVAILABLE or card_data is None:
            raw = _fetch_model_http(model_id)
            if not raw:
                return {"error": f"Cannot fetch model info for {model_id}"}
            cd = raw.get("cardData", {}) or {}
            license_val = cd.get("license") or raw.get("license", "")
            datasets = cd.get("datasets", []) or []
            author = raw.get("author", "")
            tags = raw.get("tags", []) or []
            downloads = raw.get("downloads", 0) or 0
            likes = raw.get("likes", 0) or 0
            created = raw.get("createdAt", None)
            card_data = cd
        
        violations = []
        
        # NEC#1: Data provenance
        if not datasets:
            violations.append("NEC#1")
        
        # NEC#2: License
        if not license_val:
            violations.append("NEC#2")
        
        # NEC#7: Usage scope
        has_use = any("task" in t.lower() or "use" in t.lower() for t in tags)
        if not has_use and not card_data.get("pipeline_tag"):
            violations.append("NEC#7")
        
        # NEC#10: Temporal validity
        if not created:
            violations.append("NEC#10")
        
        # NEC#13: Accountable entity
        if not author:
            violations.append("NEC#13")
        
        # Calculate Shadow Score
        total_severity = sum(
            NECESSITY_CANON.get(v, {}).get("severity", 30) 
            for v in violations
        )
        score = max(0, min(100, 100 - int(total_severity * 0.15)))
        
        # Determine badge
        if score >= 90:
            badge = "GOLD"
        elif score >= 75:
            badge = "SILVER"
        elif score >= 60:
            badge = "BRONZE"
        else:
            badge = "UNVERIFIED"
        
        # Generate evidence hash
        evidence_data = f"{model_id}:{score}:{','.join(sorted(violations))}"
        evidence_hash = hashlib.sha256(evidence_data.encode()).hexdigest()[:16]
        
        return {
            "model_id": model_id,
            "score": score,
            "badge": badge,
            "violations": violations,
            "violation_details": [
                {
                    "code": v,
                    "name": NECESSITY_CANON[v]["name"],
                    "description": NECESSITY_CANON[v]["description"],
                    "severity": NECESSITY_CANON[v]["severity"],
                    "eu_ai_act": NECESSITY_CANON[v]["eu_ai_act"],
                }
                for v in violations
            ],
            "metadata": {
                "author": author or "Unknown",
                "license": license_val or "Not declared",
                "datasets": datasets,
                "downloads": downloads,
                "likes": likes,
            },
            "evidence": {
                "hash": evidence_hash,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "engine_version": "2.0.0",
            }
        }
        
    except Exception as e:
        return {"error": f"Failed to analyze model: {str(e)}"}


def format_result(result: Dict[str, Any], verbose: bool = True) -> str:
    """Format analysis result for terminal output."""
    if "error" in result:
        return c(f"✖ Error: {result['error']}", RED)
    
    lines = []
    
    # Header
    lines.append("")
    lines.append(c("╔══════════════════════════════════════════════════════════════╗", MAGENTA))
    lines.append(c("║                 CROVIA DISCLOSURE SCANNER                    ║", MAGENTA))
    lines.append(c("╠══════════════════════════════════════════════════════════════╣", MAGENTA))
    
    # Model
    lines.append(c(f"║  Model: {result['model_id']:<52} ║", CYAN))
    
    # Score with color
    score = result["score"]
    if score >= 90:
        score_color = GREEN
    elif score >= 75:
        score_color = CYAN
    elif score >= 60:
        score_color = YELLOW
    else:
        score_color = RED
    
    lines.append(c("╠══════════════════════════════════════════════════════════════╣", MAGENTA))
    
    # Big score display
    score_str = str(score)
    badge = result["badge"]
    lines.append(f"║                                                              ║")
    lines.append(f"║           {c(f'DISCLOSURE SCORE: {score_str}', score_color + BOLD)}                          ║")
    lines.append(f"║           {c(f'Badge: {badge}', score_color)}                                     ║")
    lines.append(f"║                                                              ║")
    
    # Violations
    if result["violations"]:
        lines.append(c("╠══════════════════════════════════════════════════════════════╣", MAGENTA))
        lines.append(c("║  [!] DISCLOSURE GAPS OBSERVED                                ║", YELLOW))
        lines.append(c("╠══════════════════════════════════════════════════════════════╣", MAGENTA))
        
        for v in result["violation_details"]:
            code = v["code"]
            name = v["name"][:40]
            lines.append(f"║  {c(code, YELLOW)}  {name:<46} ║")
            if verbose:
                lines.append(f"║       {c(v['description'][:50], DIM):<55} ║")
    else:
        lines.append(c("╠══════════════════════════════════════════════════════════════╣", MAGENTA))
        lines.append(c("║  [OK] NO DISCLOSURE GAPS OBSERVED                            ║", GREEN))
    
    # Metadata
    lines.append(c("╠══════════════════════════════════════════════════════════════╣", MAGENTA))
    meta = result["metadata"]
    lines.append(f"║  Author: {meta['author'][:50]:<52} ║")
    lines.append(f"║  License: {str(meta['license'])[:50]:<51} ║")
    lines.append(f"║  Downloads: {meta['downloads']:,}                                        ║"[:65] + " ║")
    
    # Evidence
    lines.append(c("╠══════════════════════════════════════════════════════════════╣", MAGENTA))
    evidence = result["evidence"]
    lines.append(f"║  Evidence: {c(evidence['hash'], DIM)}                               ║")
    lines.append(f"║  Timestamp: {evidence['timestamp'][:30]}                    ║")
    
    lines.append(c("╚══════════════════════════════════════════════════════════════╝", MAGENTA))
    lines.append("")
    
    return "\n".join(lines)


def generate_card(result: Dict[str, Any], output_path: Optional[Path] = None) -> str:
    """Generate Oracle Card JSON file."""
    if "error" in result:
        return None
    
    card = {
        "schema": "crovia.oracle_card.v1",
        "generated": datetime.now(timezone.utc).isoformat(),
        "model_id": result["model_id"],
        "shadow_score": result["score"],
        "badge": result["badge"],
        "violations": result["violations"],
        "violation_count": len(result["violations"]),
        "evidence_hash": result["evidence"]["hash"],
        "engine_version": result["evidence"]["engine_version"],
    }
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(card, indent=2))
        return str(output_path)
    
    return json.dumps(card, indent=2)


# ============================================================
# CLI COMMANDS
# ============================================================

def cmd_oracle_scan(args) -> int:
    """crovia oracle scan <model_id>"""
    model_id = args.model_id
    
    # Check rate limit
    allowed, message = check_rate_limit("oracle_scan")
    if not allowed:
        print(c(f"\n❌ {message}\n", RED))
        return 1
    
    print(c(f"\n🔮 Analyzing {model_id}...\n", CYAN))
    
    result = analyze_model(model_id)
    
    # Increment usage for OPEN users
    status, _ = get_license_status()
    if status == LicenseStatus.OPEN:
        increment_usage("oracle_scan")
    
    print(format_result(result, verbose=args.verbose if hasattr(args, 'verbose') else True))
    
    # Save card if requested
    if hasattr(args, 'output') and args.output:
        card_path = Path(args.output)
        generate_card(result, card_path)
        print(c(f"📄 Card saved: {card_path}", GREEN))
    
    return 0 if "error" not in result else 1


def cmd_oracle_batch(args) -> int:
    """crovia oracle batch <file>"""
    status, _ = get_license_status()
    
    if status == LicenseStatus.OPEN:
        print(c("\n❌ Batch analysis requires CROVIA PRO license.", RED))
        print(c("   Upgrade at: https://croviatrust.com/pricing\n", DIM))
        return 1
    
    input_file = Path(args.file)
    if not input_file.exists():
        print(c(f"❌ File not found: {input_file}", RED))
        return 1
    
    # Read model IDs
    model_ids = [line.strip() for line in input_file.read_text().splitlines() if line.strip()]
    
    print(c(f"\n🔮 Batch analyzing {len(model_ids)} models...\n", CYAN))
    
    results = []
    for i, model_id in enumerate(model_ids, 1):
        print(f"  [{i}/{len(model_ids)}] {model_id}...", end=" ")
        result = analyze_model(model_id)
        
        if "error" in result:
            print(c("✗", RED))
        else:
            score = result["score"]
            color = GREEN if score >= 75 else YELLOW if score >= 60 else RED
            print(c(f"{score}/100 {result['badge']}", color))
        
        results.append(result)
    
    # Save results
    if hasattr(args, 'output') and args.output:
        output_path = Path(args.output)
        output_path.write_text(json.dumps(results, indent=2))
        print(c(f"\n📄 Results saved: {output_path}", GREEN))
    
    # Summary
    valid_results = [r for r in results if "error" not in r]
    if valid_results:
        avg_score = sum(r["score"] for r in valid_results) / len(valid_results)
        print(f"\n📊 Summary: {len(valid_results)} models, avg score: {avg_score:.1f}")
    
    return 0


def cmd_oracle_card(args) -> int:
    """crovia oracle card <model_id> — Generate Oracle Card JSON"""
    model_id = args.model_id
    
    # Check rate limit
    allowed, message = check_rate_limit("oracle_scan")
    if not allowed:
        print(c(f"\n❌ {message}\n", RED))
        return 1
    
    result = analyze_model(model_id)
    
    # Increment usage for OPEN users
    status, _ = get_license_status()
    if status == LicenseStatus.OPEN:
        increment_usage("oracle_scan")
    
    if "error" in result:
        print(c(f"❌ {result['error']}", RED))
        return 1
    
    output = args.output if hasattr(args, 'output') and args.output else None
    
    if output:
        card_path = Path(output)
        generate_card(result, card_path)
        print(c(f"📄 Oracle Card saved: {card_path}", GREEN))
    else:
        print(generate_card(result))
    
    return 0


# ============================================================
# ARGPARSE BINDING
# ============================================================

def bind_oracle_commands(subparsers):
    """Add oracle subcommands to CLI."""
    oracle_parser = subparsers.add_parser(
        "oracle",
        help="Omission Oracle — Analyze AI models for trust gaps"
    )
    oracle_sub = oracle_parser.add_subparsers(dest="oracle_cmd")
    
    # scan
    scan_p = oracle_sub.add_parser("scan", help="Analyze a single model")
    scan_p.add_argument("model_id", help="HuggingFace model ID (e.g., meta-llama/Llama-3-8B)")
    scan_p.add_argument("-o", "--output", help="Save Oracle Card to file")
    scan_p.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    scan_p.set_defaults(func=cmd_oracle_scan)
    
    # batch
    batch_p = oracle_sub.add_parser("batch", help="Batch analyze models (PRO only)")
    batch_p.add_argument("file", help="File with model IDs (one per line)")
    batch_p.add_argument("-o", "--output", help="Save results to file")
    batch_p.set_defaults(func=cmd_oracle_batch)
    
    # card
    card_p = oracle_sub.add_parser("card", help="Generate Oracle Card JSON")
    card_p.add_argument("model_id", help="HuggingFace model ID")
    card_p.add_argument("-o", "--output", help="Output file path")
    card_p.set_defaults(func=cmd_oracle_card)
    
    return oracle_parser


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":
    # Quick test
    print("Crovia Oracle Module Test")
    print("=" * 50)
    
    test_model = "meta-llama/Llama-3.2-1B"
    print(f"Testing with: {test_model}")
    
    result = analyze_model(test_model)
    print(format_result(result))
