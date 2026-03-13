#!/usr/bin/env python3
"""
merge_outreach_v2_v4.py — Merge V2 enriched outreach data into V4
=================================================================
V2 has richer data (completeness, provenance, TPA, closed/acknowledged status)
V4 has more records (302 vs 100) but bare-bones fields.

Strategy:
  1. Start with V4 as base (302 records)
  2. For shared targets: merge V2 fields INTO V4 (V2 wins for enriched fields)
  3. For V2-only targets: add them to the output (preserves closed/acknowledged)
  4. Re-enrich ALL records with TPA cross-reference
  5. Recompute stats from actual data

Output: enriched V4 file with all records and proper statuses.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def normalize_id(tid):
    """Normalize target_id for fuzzy matching."""
    return tid.lower().strip().replace("gh:", "")


def main():
    v2_path = os.environ.get("V2_PATH", "/var/www/registry/data/outreach_status.json")
    v4_path = os.environ.get("V4_PATH", "/var/www/registry/data_v4/outreach_status.json")
    tpa_path = os.environ.get("TPA_PATH", "/var/www/registry/data/tpa_latest.json")
    output_path = os.environ.get("OUTPUT_PATH", v4_path)

    print("Merging V2 enriched data into V4")
    print(f"  V2: {v2_path}")
    print(f"  V4: {v4_path}")
    print(f"  TPA: {tpa_path}")

    v2 = json.load(open(v2_path))
    v4 = json.load(open(v4_path))

    # Build V2 index by normalized target_id
    v2_index = {}
    for r in v2.get("records", []):
        nid = normalize_id(r.get("target_id", ""))
        v2_index[nid] = r

    # Build TPA index
    tpa_index = {}
    try:
        tpa_data = json.load(open(tpa_path))
        tpas = tpa_data if isinstance(tpa_data, list) else tpa_data.get("tpas", tpa_data.get("data", []))
        for t in tpas:
            mid = t.get("model_id", "")
            if mid:
                tpa_index[mid.lower()] = t
        print(f"  TPA index: {len(tpa_index)} models")
    except Exception as e:
        print(f"  WARN TPA: {e}")

    # ---------------------------------------------------------------
    # Phase 1: Enrich V4 records with V2 data
    # ---------------------------------------------------------------
    merged = []
    v4_ids_seen = set()
    v2_merged = 0
    tpa_matched = 0

    # Status normalization: V4 uses "no_response"/"sent", V2 uses "pending"
    # We want the V2 status if it's richer (closed, acknowledged)
    RICH_STATUSES = {"closed", "acknowledged", "access_restricted", "replied"}

    for rec in v4.get("records", []):
        tid = rec.get("target_id", "")
        nid = normalize_id(tid)
        v4_ids_seen.add(nid)

        # Check if V2 has richer data for this target
        v2_rec = v2_index.get(nid)
        if v2_rec:
            # V2 has this record — merge enriched fields
            v2_status = v2_rec.get("status", "")

            # Use V2 status if it's richer (closed/acknowledged beat sent/no_response)
            if v2_status in RICH_STATUSES:
                rec["status"] = v2_status

            # Merge V2 enrichment fields (V2 wins if non-empty)
            for field in ["completeness_score", "provenance_status", "documentation_status",
                          "has_tpa", "highest_severity", "absent_count", "jurisdictions_exposed",
                          "observed_at", "public_note", "event_type", "top_missing_nec"]:
                v2_val = v2_rec.get(field)
                cur_val = rec.get(field)
                # V2 wins if it has actual data and current is empty/default
                if v2_val and (not cur_val or cur_val == "not tracked" or cur_val == "" or cur_val == 0):
                    rec[field] = v2_val

            v2_merged += 1

        # TPA enrichment (for ALL records, including already-merged)
        rec = enrich_with_tpa(rec, tpa_index)
        if rec.get("has_tpa"):
            tpa_matched += 1

        # Ensure all fields have defaults
        apply_defaults(rec)
        merged.append(rec)

    # ---------------------------------------------------------------
    # Phase 2: Add V2-only records (closed, acknowledged, etc.)
    # ---------------------------------------------------------------
    v2_only = 0
    for nid, v2_rec in v2_index.items():
        if nid not in v4_ids_seen:
            rec = dict(v2_rec)
            rec = enrich_with_tpa(rec, tpa_index)
            if rec.get("has_tpa"):
                tpa_matched += 1
            apply_defaults(rec)
            merged.append(rec)
            v2_only += 1

    # ---------------------------------------------------------------
    # Phase 3: Recompute stats from actual merged data
    # ---------------------------------------------------------------
    statuses = {}
    total_completeness = 0
    total_days = 0
    with_tpa = 0
    platforms = {}

    for r in merged:
        s = r.get("status", "unknown")
        statuses[s] = statuses.get(s, 0) + 1
        total_completeness += r.get("completeness_score", 0)
        total_days += r.get("days_pending", 0)
        if r.get("has_tpa"):
            with_tpa += 1
        p = r.get("platform", "unknown")
        platforms[p] = platforms.get(p, 0) + 1

    n = len(merged)
    stats = {
        "total_offered": n,
        "acknowledged": statuses.get("acknowledged", 0),
        "closed": statuses.get("closed", 0),
        "no_response": statuses.get("no_response", 0),
        "pending": statuses.get("pending", 0),
        "sent": statuses.get("sent", 0),
        "failed": statuses.get("failed", 0),
        "skipped": statuses.get("skipped", 0),
        "blocked": statuses.get("blocked", 0),
        "access_restricted": statuses.get("access_restricted", 0),
        "avg_days_pending": round(total_days / n, 1) if n else 0,
        "avg_completeness": round(total_completeness / n, 1) if n else 0,
        "with_tpa": with_tpa,
        "platforms": platforms,
        "merged_at": datetime.now(timezone.utc).isoformat(),
    }

    output = {
        "schema": v4.get("schema", "crovia.outreach_status.v4"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "records": merged,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    size = os.path.getsize(output_path)
    print(f"\n=== MERGE COMPLETE ===")
    print(f"  Total records: {n} (V2-merged: {v2_merged}, V2-only added: {v2_only})")
    print(f"  TPA matched: {tpa_matched}/{n}")
    print(f"  Statuses: {statuses}")
    print(f"  Avg completeness: {stats['avg_completeness']}%")
    print(f"  Output: {output_path} ({size} bytes)")


def enrich_with_tpa(rec, tpa_index):
    """Enrich a single record with TPA data."""
    tid = rec.get("target_id", "")
    tid_lower = tid.lower().replace("gh:", "")

    # Try exact match
    tpa = tpa_index.get(tid_lower)

    # Try matching by model name (last part of path)
    if not tpa and "/" in tid:
        parts = tid.split("/")
        model_name = parts[-1].lower()
        for mid, t in tpa_index.items():
            if mid.endswith("/" + model_name) or mid == model_name:
                tpa = t
                break

    if tpa:
        obs = tpa.get("observations", [])
        absent = [o for o in obs if not o.get("is_present", True)]
        present = [o for o in obs if o.get("is_present", True)]

        rec["has_tpa"] = True
        rec["absent_count"] = len(absent)
        rec["highest_severity"] = tpa.get("highest_severity", "UNKNOWN")
        rec["jurisdictions_exposed"] = tpa.get("jurisdictions_exposed", 0)
        rec["observed_at"] = tpa.get("observed_at", rec.get("observed_at", ""))

        if not rec.get("top_missing_nec") or rec["top_missing_nec"] == []:
            rec["top_missing_nec"] = [o.get("element_label", o.get("nec_id", "")) for o in absent[:5]]

        # Provenance/documentation from TPA
        if rec.get("provenance_status") in (None, "not tracked", ""):
            has_prov = any(o.get("nec_id") == "NEC#1" and o.get("is_present") for o in obs)
            rec["provenance_status"] = "present" if has_prov else "missing"
        if rec.get("documentation_status") in (None, "not tracked", ""):
            has_doc = any(o.get("nec_id") in ("NEC#3", "NEC#4") and o.get("is_present") for o in obs)
            rec["documentation_status"] = "partial" if has_doc else "minimal"

        # Completeness score from TPA
        if rec.get("completeness_score", 0) == 0 and obs:
            rec["completeness_score"] = round(len(present) / len(obs) * 100) if obs else 0

    return rec


def apply_defaults(rec):
    """Ensure all expected fields have defaults."""
    rec.setdefault("completeness_score", 0)
    rec.setdefault("provenance_status", "not tracked")
    rec.setdefault("documentation_status", "not tracked")
    rec.setdefault("has_tpa", False)
    rec.setdefault("highest_severity", "")
    rec.setdefault("absent_count", 0)
    rec.setdefault("jurisdictions_exposed", 0)
    rec.setdefault("observed_at", "")
    rec.setdefault("public_note", "")
    rec.setdefault("event_type", "")
    rec.setdefault("top_missing_nec", [])
    rec.setdefault("discussion_url", "")
    rec.setdefault("offer_date", "")
    rec.setdefault("days_pending", 0)
    rec.setdefault("platform", "unknown")
    rec.setdefault("status", "unknown")


if __name__ == "__main__":
    main()
