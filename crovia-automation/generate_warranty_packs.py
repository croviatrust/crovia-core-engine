#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


def _nowz() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_name(model_id: str) -> str:
    return model_id.replace("/", "__")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _data_dir() -> Path:
    env = os.environ.get("CROVIA_WEBROOT_DATA", "")
    if env:
        return Path(env)
    return REPO_ROOT / "webroot" / "registry" / "data"


def _warranty_output_dir() -> Path:
    env = os.environ.get("CROVIA_WARRANTY_OUTPUT", "")
    if env:
        return Path(env)
    return _data_dir() / "warranty"


def _load_tpa_index() -> tuple[dict[str, dict[str, Any]], Path | None]:
    candidates = [
        _data_dir() / "tpa_latest.json",
        _data_dir() / "tpa_cep.json",
    ]
    path = _first_existing(candidates)
    if not path:
        return {}, None
    payload = _load_json(path)
    root_public_key = payload.get("public_key_hex")
    root_chain_height = payload.get("chain_height")
    index: dict[str, dict[str, Any]] = {}
    for item in payload.get("tpas", []):
        model_id = item.get("model_id", "")
        if model_id:
            if root_public_key and not item.get("public_key_hex"):
                item["public_key_hex"] = root_public_key
            if root_chain_height is not None and not item.get("chain_height"):
                item["chain_height"] = root_chain_height
            index[model_id] = item
    return index, path


def _load_outreach_index() -> tuple[dict[str, dict[str, Any]], Path | None]:
    path = _first_existing([_data_dir() / "outreach_status.json"])
    if not path:
        return {}, None
    payload = _load_json(path)
    index: dict[str, dict[str, Any]] = {}
    for record in payload.get("records", []):
        target_id = record.get("target_id", "")
        if target_id:
            index[target_id] = record
    return index, path


def _load_sonar_index() -> tuple[dict[str, dict[str, Any]], Path | None]:
    path = _first_existing([_data_dir() / "sonar_chains.json"])
    if not path:
        return {}, None
    payload = _load_json(path)
    chains = payload if isinstance(payload, list) else payload.get("chains", [])
    index: dict[str, dict[str, Any]] = {}
    for item in chains:
        model_id = item.get("model_id", "")
        if model_id:
            index[model_id] = item
    return index, path


def _load_global_ranking_index() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], Path | None]:
    candidates = [
        _data_dir() / "global_ranking.json",
        REPO_ROOT / "global_ranking.json",
    ]
    path = _first_existing(candidates)
    if not path:
        return {}, {}, None
    payload = _load_json(path)
    model_index: dict[str, dict[str, Any]] = {}
    for item in payload.get("model_ranking", []):
        model_id = item.get("model_id", "")
        if model_id:
            model_index[model_id] = item
    org_index: dict[str, dict[str, Any]] = {}
    for item in payload.get("org_ranking", []):
        org = item.get("org", "")
        if org:
            org_index[org] = item
    return model_index, org_index, path


def _load_compliance_report(model_id: str) -> tuple[dict[str, Any] | None, Path | None]:
    path = _data_dir() / "compliance" / f"{_safe_name(model_id)}.json"
    if not path.exists():
        return None, None
    return _load_json(path), path


def _documentation_completeness_pct(tpa: dict[str, Any] | None) -> float | None:
    if not tpa:
        return None
    absent = int(tpa.get("absent_count", 0) or 0)
    present = int(tpa.get("present_count", 0) or 0)
    total = absent + present
    if total <= 0:
        return None
    return round((present / total) * 100, 1)


def _build_claims(
    model_id: str,
    tpa: dict[str, Any] | None,
    compliance: dict[str, Any] | None,
    outreach: dict[str, Any] | None,
    sonar: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    completeness = _documentation_completeness_pct(tpa)
    if tpa:
        claims.append(
            {
                "claim_id": "documentation_observation",
                "title": "Documentation disclosure state observed",
                "statement": (
                    f"Crovia recorded a disclosure state for {model_id} with "
                    f"{tpa.get('absent_count', 0)} absent and {tpa.get('present_count', 0)} present NEC elements."
                ),
                "evidence_tier": "cryptographic_observation",
                "confidence": "HIGH",
                "support": {
                    "tpa_id": tpa.get("tpa_id"),
                    "merkle_root": tpa.get("merkle_root"),
                    "anchor_hash": tpa.get("anchor_hash") or tpa.get("temporal_anchor", {}).get("anchor_hash"),
                    "observation_timestamp": tpa.get("observation_timestamp"),
                    "documentation_completeness_pct": completeness,
                },
            }
        )
    if compliance:
        summary = compliance.get("summary", {})
        claims.append(
            {
                "claim_id": "compliance_gap_map",
                "title": "Compliance gap map available",
                "statement": (
                    f"Crovia generated a public compliance map scoring {model_id} at "
                    f"{summary.get('overall_score_pct', 0)}% with severity {summary.get('severity_label', 'UNKNOWN')}."
                ),
                "evidence_tier": "structured_public_analysis",
                "confidence": "MEDIUM",
                "support": {
                    "overall_score_pct": summary.get("overall_score_pct", 0),
                    "severity_label": summary.get("severity_label", "UNKNOWN"),
                    "top_gaps": compliance.get("top_gaps", [])[:3],
                },
            }
        )
    if outreach:
        claims.append(
            {
                "claim_id": "notice_trail",
                "title": "Notice trail available",
                "statement": (
                    f"Crovia issued a public outreach/notice event for {model_id} via {outreach.get('platform', 'unknown')} "
                    f"with status {outreach.get('status', 'unknown')}."
                ),
                "evidence_tier": "documentary_notice",
                "confidence": "MEDIUM",
                "support": {
                    "platform": outreach.get("platform"),
                    "status": outreach.get("status"),
                    "offer_date": outreach.get("offer_date"),
                    "days_pending": outreach.get("days_pending"),
                    "discussion_url": outreach.get("discussion_url"),
                },
            }
        )
    if sonar:
        claims.append(
            {
                "claim_id": "provenance_support",
                "title": "Supporting provenance signals available",
                "statement": (
                    f"Crovia extracted supporting provenance signals for {model_id} with score {round(float(sonar.get('provenance_score', 0.0)), 3)}."
                ),
                "evidence_tier": "heuristic_support",
                "confidence": "LOW",
                "support": {
                    "provenance_score": sonar.get("provenance_score", 0),
                    "license": sonar.get("license"),
                    "base_model": sonar.get("base_model"),
                    "declared_datasets": sonar.get("declared_datasets", [])[:5],
                    "inferred_datasets": sonar.get("inferred_datasets", [])[:5],
                },
            }
        )
    return claims


def _determine_warranty_state(
    tpa: dict[str, Any] | None,
    compliance: dict[str, Any] | None,
    outreach: dict[str, Any] | None,
) -> tuple[str, str, str]:
    if tpa and compliance and outreach:
        return (
            "WARRANTY_PREP_READY",
            "HIGH",
            "Suitable for enterprise due diligence, vendor challenge, and pre-contract review with explicit exclusions.",
        )
    if tpa and compliance:
        return (
            "EVIDENCE_PACK_READY",
            "HIGH",
            "Suitable for evidence-backed diligence, but notice/remediation coverage is still incomplete.",
        )
    if tpa or compliance or outreach:
        return (
            "PARTIAL_RAIL",
            "MEDIUM",
            "Usable for challenge preparation and analyst review, not yet a full warranty object.",
        )
    return (
        "INSUFFICIENT_EVIDENCE",
        "LOW",
        "Insufficient structured evidence to issue a meaningful warranty preparation pack.",
    )


def _build_exclusions(tpa: dict[str, Any] | None, compliance: dict[str, Any] | None, sonar: dict[str, Any] | None) -> list[str]:
    exclusions = [
        "This pack is an evidence-backed preparation object, not a legal opinion or insurance contract.",
        "Heuristic provenance signals are supportive only and must not be treated as cryptographic proof of training composition.",
    ]
    if not tpa:
        exclusions.append("No cryptographically anchored TPA was available for this model in the local public data plane.")
    if not compliance:
        exclusions.append("No public compliance map was available for this model in the local registry mirror.")
    if not sonar:
        exclusions.append("No supporting provenance scan was available for this model in the current Sonar export.")
    return exclusions


def _build_pack(
    model_id: str,
    tpa: dict[str, Any] | None,
    compliance: dict[str, Any] | None,
    outreach: dict[str, Any] | None,
    sonar: dict[str, Any] | None,
    model_rank: dict[str, Any] | None,
    org_rank: dict[str, Any] | None,
    source_paths: dict[str, str],
) -> dict[str, Any]:
    organization = model_id.split("/")[0] if "/" in model_id else model_id
    warranty_state, confidence_tier, commercial_use = _determine_warranty_state(tpa, compliance, outreach)
    claims = _build_claims(model_id, tpa, compliance, outreach, sonar)
    completeness_pct = _documentation_completeness_pct(tpa)
    compliance_summary = (compliance or {}).get("summary", {})
    pack = {
        "schema": "crovia.warranty_pack.v1",
        "generated_at": _nowz(),
        "model_id": model_id,
        "organization": organization,
        "summary": {
            "warranty_state": warranty_state,
            "confidence_tier": confidence_tier,
            "immediate_use": commercial_use,
            "claim_count": len(claims),
            "exclusion_count": len(_build_exclusions(tpa, compliance, sonar)),
        },
        "scores": {
            "documentation_completeness_pct": completeness_pct,
            "compliance_score_pct": compliance_summary.get("overall_score_pct") if compliance else None,
            "provenance_score": sonar.get("provenance_score") if sonar else None,
            "global_rank_score": model_rank.get("score") if model_rank else None,
            "org_avg_score": org_rank.get("avg_score") if org_rank else None,
        },
        "evidence_presence": {
            "has_tpa": tpa is not None,
            "has_compliance_map": compliance is not None,
            "has_notice_trail": outreach is not None,
            "has_provenance_support": sonar is not None,
        },
        "claims": claims,
        "notice_trail": {
            "status": outreach.get("status") if outreach else None,
            "platform": outreach.get("platform") if outreach else None,
            "days_pending": outreach.get("days_pending") if outreach else None,
            "discussion_url": outreach.get("discussion_url") if outreach else None,
        },
        "top_gaps": (compliance or {}).get("top_gaps", [])[:3],
        "tpa": {
            "tpa_id": tpa.get("tpa_id") if tpa else None,
            "observation_timestamp": tpa.get("observation_timestamp") if tpa else None,
            "chain_height": tpa.get("chain_height") if tpa else None,
            "absent_count": tpa.get("absent_count") if tpa else None,
            "present_count": tpa.get("present_count") if tpa else None,
            "highest_severity": tpa.get("highest_severity") if tpa else None,
            "merkle_root": tpa.get("merkle_root") if tpa else None,
            "anchor_hash": (tpa.get("anchor_hash") if tpa else None),
            "public_key_hex": tpa.get("public_key_hex") if tpa else None,
        },
        "provenance_support": {
            "base_model": sonar.get("base_model") if sonar else None,
            "license": sonar.get("license") if sonar else None,
            "training_section_present": sonar.get("training_section_present") if sonar else None,
            "declared_datasets": sonar.get("declared_datasets", [])[:5] if sonar else [],
            "inferred_datasets": sonar.get("inferred_datasets", [])[:5] if sonar else [],
        },
        "exclusions": _build_exclusions(tpa, compliance, sonar),
        "source_paths": source_paths,
    }
    return pack


def _candidate_models(
    tpa_index: dict[str, dict[str, Any]],
    outreach_index: dict[str, dict[str, Any]],
    targets: list[str],
    outreach_only: bool,
) -> list[str]:
    if targets:
        return targets
    if outreach_only:
        return sorted(outreach_index.keys())
    all_models = set(tpa_index.keys()) | set(outreach_index.keys())
    return sorted(all_models)


def generate_packs(targets: list[str], outreach_only: bool = False, limit: int | None = None) -> dict[str, Any]:
    out_dir = _warranty_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    tpa_index, tpa_path = _load_tpa_index()
    outreach_index, outreach_path = _load_outreach_index()
    sonar_index, sonar_path = _load_sonar_index()
    model_ranking_index, org_ranking_index, ranking_path = _load_global_ranking_index()

    models = _candidate_models(tpa_index, outreach_index, targets, outreach_only)
    if limit is not None:
        models = models[:limit]

    packs = []
    for model_id in models:
        tpa = tpa_index.get(model_id)
        compliance, compliance_path = _load_compliance_report(model_id)
        outreach = outreach_index.get(model_id)
        sonar = sonar_index.get(model_id)
        model_rank = model_ranking_index.get(model_id)
        org = model_id.split("/")[0] if "/" in model_id else model_id
        org_rank = org_ranking_index.get(org)
        source_paths = {
            "tpa": str(tpa_path) if tpa_path else "",
            "outreach": str(outreach_path) if outreach_path else "",
            "sonar": str(sonar_path) if sonar_path else "",
            "ranking": str(ranking_path) if ranking_path else "",
            "compliance": str(compliance_path) if compliance_path else "",
        }
        pack = _build_pack(
            model_id=model_id,
            tpa=tpa,
            compliance=compliance,
            outreach=outreach,
            sonar=sonar,
            model_rank=model_rank,
            org_rank=org_rank,
            source_paths=source_paths,
        )
        pack_path = out_dir / f"{_safe_name(model_id)}.json"
        pack_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")
        packs.append(
            {
                "model_id": model_id,
                "organization": pack["organization"],
                "warranty_state": pack["summary"]["warranty_state"],
                "confidence_tier": pack["summary"]["confidence_tier"],
                "documentation_completeness_pct": pack["scores"]["documentation_completeness_pct"],
                "compliance_score_pct": pack["scores"]["compliance_score_pct"],
                "provenance_score": pack["scores"]["provenance_score"],
                "has_notice_trail": pack["evidence_presence"]["has_notice_trail"],
                "pack_path": f"warranty/{_safe_name(model_id)}.json",
            }
        )

    packs.sort(
        key=lambda item: (
            item["confidence_tier"] == "HIGH",
            item["has_notice_trail"],
            item["documentation_completeness_pct"] is not None,
            item["documentation_completeness_pct"] or -1,
            item["compliance_score_pct"] or -1,
        ),
        reverse=True,
    )

    index = {
        "schema": "crovia.warranty_index.v1",
        "generated_at": _nowz(),
        "total_packs": len(packs),
        "states": {
            "WARRANTY_PREP_READY": sum(1 for item in packs if item["warranty_state"] == "WARRANTY_PREP_READY"),
            "EVIDENCE_PACK_READY": sum(1 for item in packs if item["warranty_state"] == "EVIDENCE_PACK_READY"),
            "PARTIAL_RAIL": sum(1 for item in packs if item["warranty_state"] == "PARTIAL_RAIL"),
            "INSUFFICIENT_EVIDENCE": sum(1 for item in packs if item["warranty_state"] == "INSUFFICIENT_EVIDENCE"),
        },
        "packs": packs,
    }
    (out_dir / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Crovia Warranty Rail packs from existing registry evidence")
    parser.add_argument("targets", nargs="*", help="Optional model IDs to generate")
    parser.add_argument("--outreach-only", action="store_true", help="Generate packs only for models with outreach records")
    parser.add_argument("--limit", type=int, help="Limit number of generated packs")
    args = parser.parse_args()

    index = generate_packs(targets=args.targets, outreach_only=args.outreach_only, limit=args.limit)
    print(f"[Warranty] wrote {index['total_packs']} packs to {_warranty_output_dir()}")
    print(f"[Warranty] states: {index['states']}")


if __name__ == "__main__":
    main()
