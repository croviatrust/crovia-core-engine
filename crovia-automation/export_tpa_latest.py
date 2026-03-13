#!/usr/bin/env python3
"""
Export TPA Latest — generates tpa_latest.json for the registry web page.

Reads OPEN TPA files from the TPA output directory, picks the latest
TPA per model, and writes a summary JSON for the web frontend.

Also copies latest OPEN TPAs to the HF dataset repo for public visibility.

Usage:
    python export_tpa_latest.py

Environment:
    TPA_INPUT_DIR   — where OPEN TPAs are stored (default: /opt/crovia/tpa/open)
    TPA_WEB_OUTPUT  — where to write tpa_latest.json (default: /var/www/registry/data)
    TPA_HF_OUTPUT   — where to copy OPEN TPAs for HF (default: open/tpa in HF repo)
    TPA_MAX_DISPLAY — max TPAs to show on web page (default: 50)
"""

import hashlib
import json
import os
import shutil
from pathlib import Path
from datetime import datetime, timezone


TPA_INPUT_DIR = Path(os.getenv(
    'TPA_INPUT_DIR', '/opt/crovia/tpa/open'
))
TPA_WEB_OUTPUT = Path(os.getenv(
    'TPA_WEB_OUTPUT', '/var/www/registry/data'
))
TPA_HF_OUTPUT = Path(os.getenv(
    'TPA_HF_OUTPUT', ''
))
TPA_MAX_DISPLAY = int(os.getenv('TPA_MAX_DISPLAY', '500'))
OUTREACH_LOG = Path(os.getenv(
    'OUTREACH_HF_LOG',
    str(Path(__file__).parent / 'sent_discussions.jsonl'),
))
TPA_CHAIN_FILE = Path(os.getenv(
    'TPA_CHAIN_FILE', '/opt/crovia/tpa/chain_state.json'
))
DSSE_SONAR_FILE = Path(os.getenv(
    'DSSE_SONAR_FILE', '/var/www/registry/data/sonar_chains.json'
))


def _load_dsse_index() -> dict:
    """Load sonar_chains.json and build a model_id → DSSE entry index."""
    if not DSSE_SONAR_FILE.exists():
        return {}
    try:
        data = json.loads(DSSE_SONAR_FILE.read_text(encoding='utf-8'))
        arr = data if isinstance(data, list) else data.get('chains', list(data.values()) if isinstance(data, dict) else [])
        return {(e.get('model_id') or e.get('id', '')): e for e in arr if e.get('model_id') or e.get('id')}
    except Exception as e:
        print(f"  DSSE index load error: {e}")
        return {}


def _load_outreach_targets() -> set:
    """Load outreach target IDs to prioritize in export."""
    targets = set()
    if not OUTREACH_LOG.exists():
        return targets
    try:
        with open(OUTREACH_LOG, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        r = json.loads(line)
                        tid = r.get('repo_id') or r.get('target_id', '')
                        if tid and '/' in tid:
                            targets.add(tid)
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass
    return targets


def collect_latest_tpas() -> list:
    """Collect the most recent OPEN TPA per model, prioritizing outreach targets."""
    if not TPA_INPUT_DIR.exists():
        print(f"  TPA input dir does not exist: {TPA_INPUT_DIR}")
        return []

    outreach_ids = _load_outreach_targets()
    dsse_index = _load_dsse_index()
    print(f"  Outreach targets loaded: {len(outreach_ids)}")
    print(f"  DSSE index loaded: {len(dsse_index)} models")

    model_dirs = [d for d in TPA_INPUT_DIR.iterdir() if d.is_dir()]
    latest_tpas = []

    for model_dir in sorted(model_dirs):
        tpa_files = sorted(model_dir.glob('*.json'), reverse=True)
        if not tpa_files:
            continue

        latest_file = tpa_files[0]
        try:
            tpa = json.loads(latest_file.read_text(encoding='utf-8'))
            model_id = tpa.get('model_id', model_dir.name.replace('__', '/'))
            tpa['_is_outreach'] = model_id in outreach_ids
            # Enrich with sonar provenance fingerprint if available
            sonar = dsse_index.get(model_id)
            if sonar:
                signals = sonar.get('signals', [])
                dataset_signals = [s['value'] for s in signals if s.get('signal_type') in ('readme_dataset', 'config_dataset') and s.get('confidence', 0) >= 0.7]
                tpa['sonar'] = {
                    'provenance_hash': sonar.get('provenance_hash', ''),
                    'provenance_score': sonar.get('provenance_score', 0),
                    'base_model': sonar.get('base_model', ''),
                    'license': sonar.get('license', ''),
                    'training_section_present': sonar.get('training_section_present', False),
                    'declared_datasets': sonar.get('declared_datasets', [])[:5],
                    'top_dataset_signals': dataset_signals[:5],
                    'scanned_at': sonar.get('scanned_at', ''),
                }
            latest_tpas.append(tpa)
        except Exception as e:
            print(f"  Error reading {latest_file}: {e}")

    # Sort: outreach targets first, then by recency
    latest_tpas.sort(
        key=lambda t: (not t.get('_is_outreach', False), -t.get('observation_epoch', 0))
    )

    outreach_count = sum(1 for t in latest_tpas if t.get('_is_outreach'))
    print(f"  Outreach with TPA: {outreach_count}")

    # Include ALL outreach TPAs + fill remaining with recent others
    result = []
    others = []
    for t in latest_tpas:
        if t.pop('_is_outreach', False):
            result.append(t)
        else:
            others.append(t)
    result.extend(others[:max(0, TPA_MAX_DISPLAY - len(result))])
    return result


def read_chain_state() -> dict:
    """Read chain state if available."""
    if TPA_CHAIN_FILE.exists():
        try:
            return json.loads(TPA_CHAIN_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


def export_web(tpas: list, chain_state: dict) -> None:
    """Write tpa_latest.json for the registry web page."""
    TPA_WEB_OUTPUT.mkdir(parents=True, exist_ok=True)

    unique_models = len({t.get('model_id') for t in tpas})
    total_available = len([d for d in TPA_INPUT_DIR.iterdir() if d.is_dir()]) if TPA_INPUT_DIR.exists() else len(tpas)

    generated_at = datetime.now(timezone.utc).isoformat()

    # Sentinel: unique fingerprint per export — traceable if data is copied/republished
    sentinel_raw = f"{generated_at}:{total_available}:{chain_state.get('chain_height', 0)}:{chain_state.get('public_key_hex', '')}"
    sentinel = hashlib.sha256(sentinel_raw.encode()).hexdigest()[:24]

    output = {
        "generated_at": generated_at,
        "total_tpas": len(tpas),
        "total_available": total_available,
        "unique_models": unique_models,
        "chain_height": chain_state.get('chain_height', 0),
        "public_key_hex": chain_state.get('public_key_hex', ''),
        "sentinel": sentinel,
        "license": "CC-BY-4.0",
        "attribution": "Crovia Registry — https://registry.croviatrust.com — Data generated by the Crovia autonomous observer network. Attribution required for any reuse.",
        "terms": "https://croviatrust.com/terms",
        "tpas": tpas,
    }

    out_file = TPA_WEB_OUTPUT / 'tpa_latest.json'
    out_file.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
    print(f"  Web export: {out_file} ({len(tpas)} TPAs, {unique_models} models)")


def export_hf(tpas: list) -> None:
    """Copy latest OPEN TPAs to HF dataset repo."""
    if not TPA_HF_OUTPUT or not Path(TPA_HF_OUTPUT).parent.exists():
        return

    hf_dir = Path(TPA_HF_OUTPUT)
    hf_dir.mkdir(parents=True, exist_ok=True)

    readme = hf_dir / 'README.md'
    if not readme.exists():
        readme.write_text(
            "# Temporal Proof of Absence (OPEN tier)\n\n"
            "Cryptographically committed observations of absent disclosures.\n"
            "Each file is a self-contained OPEN TPA — the public tier.\n\n"
            "Full cryptographic verification available in Crovia PRO.\n\n"
            "See: https://croviatrust.com/registry/tpa\n",
            encoding='utf-8',
        )

    for tpa in tpas:
        model_id = tpa.get('model_id', 'unknown')
        epoch = tpa.get('observation_epoch', 0)
        safe_id = model_id.replace('/', '__')
        model_dir = hf_dir / safe_id
        model_dir.mkdir(parents=True, exist_ok=True)

        tpa_file = model_dir / f"{epoch}.json"
        if not tpa_file.exists():
            tpa_file.write_text(
                json.dumps(tpa, indent=2, ensure_ascii=False),
                encoding='utf-8',
            )

    print(f"  HF export: {hf_dir} ({len(tpas)} TPAs)")


def main():
    print(f"[TPA Export] {datetime.now(timezone.utc).isoformat()}")
    print(f"  Input: {TPA_INPUT_DIR}")

    tpas = collect_latest_tpas()
    if not tpas:
        print("  No TPAs found.")
        return

    chain_state = read_chain_state()
    export_web(tpas, chain_state)

    if TPA_HF_OUTPUT:
        export_hf(tpas)

    print(f"  Done: {len(tpas)} TPAs exported")


if __name__ == '__main__':
    main()
