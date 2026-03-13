#!/usr/bin/env python3
"""
Rebuild search_targets.json from targets_unified.json + TPA presence check.
Output: /var/www/registry/data/search_targets.json
"""
import json, os
from pathlib import Path

TARGETS_FILE = Path(os.getenv('TPR_TARGETS_FILE', '/opt/crovia/CROVIA_DEV/crovia-automation/targets_unified.json'))
TPA_OPEN_DIR = Path(os.getenv('TPA_INPUT_DIR', '/opt/crovia/tpa/open'))
OUTPUT = Path(os.getenv('TPA_WEB_OUTPUT', '/var/www/registry/data')) / 'search_targets.json'

print(f"[search_targets] Loading targets from {TARGETS_FILE}")
raw = json.loads(TARGETS_FILE.read_text())
items = raw if isinstance(raw, list) else raw.get('targets', [])

# Build set of model_ids that have at least one TPA
tpa_ids = set()
if TPA_OPEN_DIR.exists():
    for d in TPA_OPEN_DIR.iterdir():
        if d.is_dir() and any(d.glob('*.json')):
            tpa_ids.add(d.name.replace('__', '/'))
print(f"[search_targets] TPA coverage: {len(tpa_ids)} models")

targets = []
for item in items:
    if isinstance(item, dict):
        mid = item.get('target_id') or item.get('model_id') or item.get('id', '')
        tipo = item.get('tipo_target') or item.get('type', 'model')
    elif isinstance(item, str):
        mid = item
        tipo = 'model'
    else:
        continue
    if not mid:
        continue
    targets.append({
        'id': mid,
        'type': tipo,
        'has_tpa': mid in tpa_ids,
    })

out = {
    'total': len(targets),
    'with_tpa': sum(1 for t in targets if t['has_tpa']),
    'targets': targets,
}
OUTPUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(f"[search_targets] Written {len(targets)} targets ({out['with_tpa']} with TPA) → {OUTPUT}")
