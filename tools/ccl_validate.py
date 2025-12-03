#!/usr/bin/env python3
# tools/ccl_validate.py - minimal validator for CCL v1.1

import argparse, json, sys
from pathlib import Path
from typing import Any, Dict, List

REQUIRED_KEYS = [
    "ccl_version",
    "provider_hint",
    "artifact_type",
    "shard_shape",
    "license_scope",
    "usage_scope",
]

ARTIFACT_TYPES = {"model", "dataset", "rag-index", "api", "tool", "other"}
SHARD_SHAPES = {"embedding", "token", "chunk", "other"}
LICENSE_SCOPES = {"train", "rag", "eval", "unknown"}
USAGE_SCOPES = {"public_api", "internal", "research", "unknown"}

DP_VALUES = {"yes", "no", "unknown"}

DATA_ROLES = {"producer", "mixer", "annotator", "filter", "unknown"}
MODEL_ROLES = {"backbone", "adapter", "lora", "critic", "tool", "unknown"}
GATEWAY_ROLES = {"training", "inference", "broker", "cache", "unknown"}

def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"[FATAL] Cannot read/parse JSON: {path} ({e})")

def validate_core(obj: Dict[str, Any], errors: List[str]) -> None:
    for k in REQUIRED_KEYS:
        if k not in obj:
            errors.append(f"missing required field: {k}")

    if "ccl_version" in obj and not isinstance(obj["ccl_version"], str):
        errors.append("ccl_version must be a string")

    if "provider_hint" in obj and not isinstance(obj["provider_hint"], str):
        errors.append("provider_hint must be a string")

    at = obj.get("artifact_type")
    if at is not None:
        if not isinstance(at, str) or at not in ARTIFACT_TYPES:
            errors.append(f"artifact_type is invalid: {at!r}")

    ss = obj.get("shard_shape")
    if ss is not None:
        if not isinstance(ss, str) or ss not in SHARD_SHAPES:
            errors.append(f"shard_shape is invalid: {ss!r}")

    ls = obj.get("license_scope")
    if ls is not None:
        if not isinstance(ls, str) or ls not in LICENSE_SCOPES:
            errors.append(f"license_scope is invalid: {ls!r}")

    us = obj.get("usage_scope")
    if us is not None:
        if not isinstance(us, str) or us not in USAGE_SCOPES:
            errors.append(f"usage_scope is invalid: {us!r}")

    if "fingerprint" in obj and not isinstance(obj["fingerprint"], str):
        errors.append("fingerprint must be a string if present")

def validate_trust_hints(obj: Dict[str, Any], errors: List[str]) -> None:
    th = obj.get("trust_hints")
    if th is None:
        return
    if not isinstance(th, dict):
        errors.append("trust_hints must be an object")
        return
    dp = th.get("dp")
    if dp is not None and (not isinstance(dp, str) or dp not in DP_VALUES):
        errors.append(f"trust_hints.dp is invalid: {dp!r}")
    for k in ("stability", "uncertainty"):
        v = th.get(k)
        if v is not None:
            if not isinstance(v, (int, float)):
                errors.append(f"trust_hints.{k} must be numeric (0–1)")
            elif not (0.0 <= float(v) <= 1.0):
                errors.append(f"trust_hints.{k} out of range [0,1]: {v!r}")

def validate_roles(obj: Dict[str, Any], errors: List[str]) -> None:
    roles = obj.get("roles")
    if roles is None:
        return
    if not isinstance(roles, dict):
        errors.append("roles must be an object")
        return
    dr = roles.get("data_role")
    if dr is not None and (not isinstance(dr, str) or dr not in DATA_ROLES):
        errors.append(f"roles.data_role is invalid: {dr!r}")
    mr = roles.get("model_role")
    if mr is not None and (not isinstance(mr, str) or mr not in MODEL_ROLES):
        errors.append(f"roles.model_role is invalid: {mr!r}")
    gr = roles.get("gateway_role")
    if gr is not None and (not isinstance(gr, str) or gr not in GATEWAY_ROLES):
        errors.append(f"roles.gateway_role is invalid: {gr!r}")

def validate_links(obj: Dict[str, Any], errors: List[str]) -> None:
    links = obj.get("links")
    if links is None:
        return
    if not isinstance(links, dict):
        errors.append("links must be an object")
        return

    upstream = links.get("upstream")
    if upstream is not None:
        if not isinstance(upstream, list):
            errors.append("links.upstream must be a list of strings")
        else:
            for i, v in enumerate(upstream):
                if not isinstance(v, str):
                    errors.append(f"links.upstream[{i}] must be a string")

    for key in ("downstream_hint", "bundle_ref"):
        v = links.get(key)
        if v is not None and not isinstance(v, str):
            errors.append(f"links.{key} must be a string or null")

def main() -> None:
    ap = argparse.ArgumentParser(description="Minimal validator for CROVIA CCL v1.1")
    ap.add_argument("path", help="CCL JSON file to validate")
    args = ap.parse_args()

    p = Path(args.path)
    if not p.exists():
        print(f"[ERROR] File not found: {p}", file=sys.stderr)
        sys.exit(2)

    obj = load_json(p)
    errors: List[str] = []

    validate_core(obj, errors)
    validate_trust_hints(obj, errors)
    validate_roles(obj, errors)
    validate_links(obj, errors)

    if errors:
        print(f"[CCL] INVALID: {p}")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"[CCL] OK: {p}")
        sys.exit(0)

if __name__ == "__main__":
    main()
