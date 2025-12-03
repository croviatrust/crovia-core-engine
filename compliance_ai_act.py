#!/usr/bin/env python3
# compliance_ai_act.py
#
# Generate a simple AI Act–oriented "Training Data Summary" and
# "Gap Report" from royalty_receipt.v1 NDJSON logs.
#
# This is an OPEN-CORE tool:
# - it does NOT compute pricing or payouts
# - it does NOT use any private keys or contracts
#
# It is intended as a helper to prepare Annex IV style documentation:
# - what kind of training data was used?
# - from which providers / regions?
# - with which licenses?
# - where are the gaps (missing license / region / purpose metadata)?

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROYALTY_SCHEMA = "royalty_receipt.v1"
TOL_SHARE_SUM = 0.02


def iter_ndjson(path: str) -> Iterable[Tuple[int, Dict[str, Any]]]:
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for lineno, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception as e:
                yield lineno, {
                    "_parse_error": str(e),
                    "_raw": s,
                }
                continue
            yield lineno, obj


def safe_get_meta(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Helper to extract optional metadata commonly used for AI Act mapping.
    We keep this intentionally flexible: if fields are missing, they are just None.
    """
    meta = entry.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}

    return {
        "license": meta.get("license") or entry.get("license"),
        "license_family": meta.get("license_family") or None,
        "region": meta.get("region") or entry.get("region"),
        "source_type": meta.get("source_type") or entry.get("source_type"),
        "purpose": meta.get("purpose") or entry.get("purpose"),
        "collection_channel": meta.get("collection_channel") or entry.get("collection_channel"),
    }


def analyze_royalty_receipts(path: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Scan royalty_receipt.v1 NDJSON and build:
      - global summary (providers, licenses, regions, dp_epsilon, etc.)
      - gap list: records with missing license / region / purpose / parse errors.
    """

    total_lines = 0
    total_valid_schema = 0
    sum_bad_share = 0

    providers = Counter()
    shards = Counter()
    provider_share = Counter()
    shard_share = Counter()

    license_counter = Counter()
    license_family_counter = Counter()
    region_counter = Counter()
    source_type_counter = Counter()
    purpose_counter = Counter()
    channel_counter = Counter()

    epsilon_min: Optional[float] = None
    epsilon_max: Optional[float] = None

    gaps: List[Dict[str, Any]] = []

    first_lineno: Optional[int] = None
    last_lineno: Optional[int] = None

    for lineno, rec in iter_ndjson(path):
        total_lines += 1
        if first_lineno is None:
            first_lineno = lineno
        last_lineno = lineno

        # Parse errors
        if "_parse_error" in rec:
            gaps.append({
                "_line": lineno,
                "_reason": "JSON_PARSE_ERROR",
                "_detail": rec.get("_parse_error"),
                "_raw": rec.get("_raw"),
            })
            continue

        schema = rec.get("schema")
        if schema != ROYALTY_SCHEMA:
            gaps.append({
                "_line": lineno,
                "_reason": "WRONG_SCHEMA",
                "_schema": schema,
                "_expected": ROYALTY_SCHEMA,
            })
            continue

        total_valid_schema += 1

        # Validate and normalize top_k
        top_k = rec.get("top_k") or []
        if not isinstance(top_k, list) or not top_k:
            gaps.append({
                "_line": lineno,
                "_reason": "MISSING_TOPK",
                "_rec": rec,
            })
            continue

        entries: List[Tuple[str, str, float, Dict[str, Any]]] = []
        sum_share = 0.0
        for a in top_k:
            if not isinstance(a, dict):
                continue
            pid = str(a.get("provider_id", ""))
            sid = str(a.get("shard_id", ""))
            share = a.get("share")
            if not isinstance(share, (int, float)):
                continue
            v = float(share)
            if v < 0:
                continue
            sum_share += v
            meta = safe_get_meta(a)
            entries.append((pid, sid, v, meta))

        if not entries:
            gaps.append({
                "_line": lineno,
                "_reason": "NO_VALID_TOPK_ENTRIES",
                "_rec": rec,
            })
            continue

        # sum(share) sanity
        if abs(sum_share - 1.0) > TOL_SHARE_SUM:
            sum_bad_share += 1
            # per coerenza, scartiamo l'evento ambiguo dal summary
            gaps.append({
                "_line": lineno,
                "_reason": "BAD_SHARE_SUM",
                "_sum_share": sum_share,
                "_tol": TOL_SHARE_SUM,
            })
            continue

        # Normalized contributions
        for pid, sid, sh, meta in entries:
            frac = sh / sum_share if sum_share > 0 else 0.0
            providers[pid] += 1
            shards[sid] += 1
            provider_share[pid] += frac
            shard_share[sid] += frac

            lic = (meta.get("license") or "").strip() or None
            lic_family = (meta.get("license_family") or "").strip() or None
            region = (meta.get("region") or "").strip() or None
            source_type = (meta.get("source_type") or "").strip() or None
            purpose = (meta.get("purpose") or "").strip() or None
            channel = (meta.get("collection_channel") or "").strip() or None

            if lic:
                license_counter[lic] += frac
            else:
                gaps.append({
                    "_line": lineno,
                    "_reason": "MISSING_LICENSE",
                    "_provider_id": pid,
                    "_shard_id": sid,
                })

            if lic_family:
                license_family_counter[lic_family] += frac

            if region:
                region_counter[region] += frac
            else:
                gaps.append({
                    "_line": lineno,
                    "_reason": "MISSING_REGION",
                    "_provider_id": pid,
                    "_shard_id": sid,
                })

            if source_type:
                source_type_counter[source_type] += frac
            else:
                gaps.append({
                    "_line": lineno,
                    "_reason": "MISSING_SOURCE_TYPE",
                    "_provider_id": pid,
                    "_shard_id": sid,
                })

            if purpose:
                purpose_counter[purpose] += frac
            else:
                gaps.append({
                    "_line": lineno,
                    "_reason": "MISSING_PURPOSE",
                    "_provider_id": pid,
                    "_shard_id": sid,
                })

            if channel:
                channel_counter[channel] += frac

        # DP epsilon (if present at record-level)
        eps = rec.get("epsilon_dp")
        if isinstance(eps, (int, float)):
            v = float(eps)
            epsilon_min = v if epsilon_min is None else min(epsilon_min, v)
            epsilon_max = v if epsilon_max is None else max(epsilon_max, v)

    summary: Dict[str, Any] = {
        "schema": "crovia_training_data_summary.v1",
        "source_schema": ROYALTY_SCHEMA,
        "input_file": os.path.basename(path),
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "total_lines": total_lines,
        "valid_schema_records": total_valid_schema,
        "bad_share_sum_records": sum_bad_share,
        "providers_count": len(providers),
        "shards_count": len(shards),
        "epsilon_dp": {
            "min": epsilon_min,
            "max": epsilon_max,
        },
        "top_providers_by_share": [
            {"provider_id": pid, "share_fraction": round(float(frac), 6)}
            for pid, frac in provider_share.most_common(20)
        ],
        "top_shards_by_share": [
            {"shard_id": sid, "share_fraction": round(float(frac), 6)}
            for sid, frac in shard_share.most_common(20)
        ],
        "licenses": [
            {"license": lic, "share_fraction": round(float(frac), 6)}
            for lic, frac in license_counter.most_common()
        ],
        "license_families": [
            {"license_family": lf, "share_fraction": round(float(frac), 6)}
            for lf, frac in license_family_counter.most_common()
        ],
        "regions": [
            {"region": r, "share_fraction": round(float(frac), 6)}
            for r, frac in region_counter.most_common()
        ],
        "source_types": [
            {"source_type": st, "share_fraction": round(float(frac), 6)}
            for st, frac in source_type_counter.most_common()
        ],
        "purposes": [
            {"purpose": p, "share_fraction": round(float(frac), 6)}
            for p, frac in purpose_counter.most_common()
        ],
        "collection_channels": [
            {"collection_channel": ch, "share_fraction": round(float(frac), 6)}
            for ch, frac in channel_counter.most_common()
        ],
        "gaps_count": len(gaps),
        "first_line": first_lineno,
        "last_line": last_lineno,
    }

    return summary, gaps


def write_markdown_summary(path: str, summary: Dict[str, Any]) -> None:
    """
    Render a human-readable Annex IV–style summary in Markdown.
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Crovia – Training Data Summary (AI Act oriented)\n\n")
        f.write(f"- Generated at: **{summary['generated_at']}**\n")
        f.write(f"- Input file: `{summary['input_file']}`\n")
        f.write(f"- Source schema: `{summary['source_schema']}`\n")
        f.write(f"- Total lines: **{summary['total_lines']}**\n")
        f.write(f"- Valid records (schema OK): **{summary['valid_schema_records']}**\n")
        f.write(f"- Records with bad share sum: **{summary['bad_share_sum_records']}**\n")
        f.write(f"- Providers: **{summary['providers_count']}**\n")
        f.write(f"- Shards: **{summary['shards_count']}**\n\n")

        eps = summary.get("epsilon_dp") or {}
        f.write("## Differential Privacy (epsilon_dp)\n\n")
        f.write(f"- min: **{eps.get('min')}**\n")
        f.write(f"- max: **{eps.get('max')}**\n\n")

        f.write("## License distribution\n\n")
        licenses = summary.get("licenses") or []
        if not licenses:
            f.write("_No license information detected in the receipts._\n\n")
        else:
            f.write("| License | Share fraction |\n")
            f.write("|---------|----------------|\n")
            for row in licenses:
                f.write(f"| `{row['license']}` | {row['share_fraction']:.6f} |\n")
            f.write("\n")

        f.write("## Regions\n\n")
        regions = summary.get("regions") or []
        if not regions:
            f.write("_No region information detected._\n\n")
        else:
            f.write("| Region | Share fraction |\n")
            f.write("|--------|----------------|\n")
            for row in regions:
                f.write(f"| `{row['region']}` | {row['share_fraction']:.6f} |\n")
            f.write("\n")

        f.write("## Source types\n\n")
        stypes = summary.get("source_types") or []
        if not stypes:
            f.write("_No source_type information detected._\n\n")
        else:
            f.write("| Source type | Share fraction |\n")
            f.write("|-------------|----------------|\n")
            for row in stypes:
                f.write(f"| `{row['source_type']}` | {row['share_fraction']:.6f} |\n")
            f.write("\n")

        f.write("## Purposes\n\n")
        purposes = summary.get("purposes") or []
        if not purposes:
            f.write("_No purpose information detected._\n\n")
        else:
            f.write("| Purpose | Share fraction |\n")
            f.write("|---------|----------------|\n")
            for row in purposes:
                f.write(f"| `{row['purpose']}` | {row['share_fraction']:.6f} |\n")
            f.write("\n")

        f.write("## Collection channels\n\n")
        channels = summary.get("collection_channels") or []
        if not channels:
            f.write("_No collection_channel information detected._\n\n")
        else:
            f.write("| Channel | Share fraction |\n")
            f.write("|---------|----------------|\n")
            for row in channels:
                f.write(f"| `{row['collection_channel']}` | {row['share_fraction']:.6f} |\n")
            f.write("\n")

        f.write("## Top providers by share\n\n")
        top_prov = summary.get("top_providers_by_share") or []
        if not top_prov:
            f.write("_No providers detected._\n\n")
        else:
            f.write("| Provider ID | Share fraction |\n")
            f.write("|-------------|----------------|\n")
            for row in top_prov:
                f.write(f"| `{row['provider_id']}` | {row['share_fraction']:.6f} |\n")
            f.write("\n")

        f.write("## Top shards by share\n\n")
        top_shards = summary.get("top_shards_by_share") or []
        if not top_shards:
            f.write("_No shards detected._\n\n")
        else:
            f.write("| Shard ID | Share fraction |\n")
            f.write("|----------|----------------|\n")
            for row in top_shards:
                f.write(f"| `{row['shard_id']}` | {row['share_fraction']:.6f} |\n")
            f.write("\n")

        f.write("## AI Act Annex IV mapping (high level)\n\n")
        f.write("- **(a) Training data used** → described by providers, shards, licenses, regions.\n")
        f.write("- **(b) Data sources** → summarized via `source_types` and `collection_channels`.\n")
        f.write("- **(c) Data collection** → partially covered by `collection_channels`.\n")
        f.write("- **(d) Data governance** → license / region coverage and `gaps_count` highlight missing metadata.\n")
        f.write("\n")
        f.write("This summary is intended as a technical annex; legal teams should review\n")
        f.write("and complement it with contractual and policy documentation.\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate AI Act–oriented training data summary and gap report "
                    "from royalty_receipt.v1 NDJSON."
    )
    ap.add_argument(
        "input",
        help="Input NDJSON file (royalty_receipt.v1)",
    )
    ap.add_argument(
        "--out-summary",
        default="compliance_training_data_summary.md",
        help="Output Markdown summary path (default: compliance_training_data_summary.md)",
    )
    ap.add_argument(
        "--out-gaps",
        default="compliance_gaps.ndjson",
        help="Output NDJSON gap report path (default: compliance_gaps.ndjson)",
    )
    ap.add_argument(
        "--out-pack",
        default="compliance_pack.json",
        help="Output JSON pack path (default: compliance_pack.json)",
    )
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"[FATAL] Input file not found: {args.input}", file=sys.stderr)
        sys.exit(2)

    summary, gaps = analyze_royalty_receipts(args.input)

    # Write summary MD
    write_markdown_summary(args.out_summary, summary)

    # Write gaps NDJSON
    with open(args.out_gaps, "w", encoding="utf-8") as gf:
        for g in gaps:
            gf.write(json.dumps(g, ensure_ascii=False) + "\n")

    # Write combined pack JSON
    pack = {
        "schema": "crovia_ai_act_compliance_pack.v1",
        "summary": summary,
        "gaps_file": os.path.basename(args.out_gaps),
        "gaps_count": len(gaps),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    with open(args.out_pack, "w", encoding="utf-8") as pf:
        json.dump(pack, pf, ensure_ascii=False, indent=2)

    print(f"[COMPLIANCE] Summary: {args.out_summary}")
    print(f"[COMPLIANCE] Gaps:    {args.out_gaps}")
    print(f"[COMPLIANCE] Pack:     {args.out_pack}")


if __name__ == "__main__":
    main()
