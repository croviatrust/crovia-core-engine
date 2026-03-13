#!/usr/bin/env python3
"""
enrich_outreach_v4.py — Enrich V4 outreach data with TPA cross-reference
=========================================================================
Reads V4 outreach_status.json and tpa_latest.json, enriches each record
with TPA fields (absent_count, highest_severity, jurisdictions_exposed).
Writes enriched output back to the same V4 file.

Safety: reads TPA data read-only, only modifies V4 outreach output.
"""
import json
import os
import sys
from datetime import datetime, timezone


def main():
    v4_path = os.environ.get("V4_PATH", "/var/www/registry/data_v4/outreach_status.json")
    tpa_path = os.environ.get("TPA_PATH", "/var/www/registry/data/tpa_latest.json")
    output_path = os.environ.get("OUTPUT_PATH", v4_path)

    print(f"Enriching V4 outreach with TPA data")
    print(f"  V4:  {v4_path}")
    print(f"  TPA: {tpa_path}")

    # Load V4 outreach
    with open(v4_path) as f:
        v4 = json.load(f)

    # Load TPA data and index by model_id (lowercase for fuzzy matching)
    tpa_index = {}
    try:
        with open(tpa_path) as f:
            tpa_data = json.load(f)
        tpas = tpa_data if isinstance(tpa_data, list) else tpa_data.get("tpas", tpa_data.get("data", []))
        for t in tpas:
            mid = t.get("model_id", "")
            if mid:
                tpa_index[mid.lower()] = t
        print(f"  TPA index: {len(tpa_index)} models")
    except Exception as e:
        print(f"  WARN: Could not load TPA: {e}")

    # Enrich records
    enriched = 0
    tpa_matched = 0
    for rec in v4.get("records", []):
        tid = rec.get("target_id", "")
        tid_lower = tid.lower()

        # Try exact match, then partial match
        tpa = tpa_index.get(tid_lower)
        if not tpa:
            # Try without platform prefix (gh: prefix)
            clean = tid.replace("gh:", "").lower()
            tpa = tpa_index.get(clean)

        if tpa:
            obs = tpa.get("observations", [])
            absent = [o for o in obs if not o.get("is_present", True)]
            present = [o for o in obs if o.get("is_present", True)]

            rec["has_tpa"] = True
            rec["absent_count"] = len(absent)
            rec["highest_severity"] = tpa.get("highest_severity", "UNKNOWN")
            rec["jurisdictions_exposed"] = tpa.get("jurisdictions_exposed", 0)
            rec["observed_at"] = tpa.get("observed_at", "")

            # Top missing NEC elements if not already populated
            if not rec.get("top_missing_nec"):
                rec["top_missing_nec"] = [o.get("element_label", o.get("nec_id", "")) for o in absent[:5]]

            # Provenance/documentation from TPA
            if rec.get("provenance_status") == "not tracked":
                has_prov = any(o.get("nec_id") == "NEC#1" and o.get("is_present") for o in obs)
                rec["provenance_status"] = "present" if has_prov else "missing"
            if rec.get("documentation_status") == "not tracked":
                has_doc = any(o.get("nec_id") in ("NEC#3", "NEC#4") and o.get("is_present") for o in obs)
                rec["documentation_status"] = "partial" if has_doc else "minimal"

            # Completeness score from TPA
            if rec.get("completeness_score", 0) == 0 and obs:
                rec["completeness_score"] = round(len(present) / len(obs) * 100) if obs else 0

            tpa_matched += 1

        # Ensure missing fields have defaults
        rec.setdefault("public_note", "")
        rec.setdefault("event_type", "")
        rec.setdefault("highest_severity", "")
        rec.setdefault("absent_count", 0)
        rec.setdefault("jurisdictions_exposed", 0)
        rec.setdefault("observed_at", "")
        enriched += 1

    # Update stats
    stats = v4.get("stats", {})
    stats["with_tpa"] = tpa_matched
    stats["enriched_at"] = datetime.now(timezone.utc).isoformat()

    # Write output
    with open(output_path, "w") as f:
        json.dump(v4, f, indent=2)

    size = os.path.getsize(output_path)
    print(f"\n  Records enriched: {enriched}")
    print(f"  TPA matched: {tpa_matched}/{enriched}")
    print(f"  Output: {output_path} ({size} bytes)")


if __name__ == "__main__":
    main()
