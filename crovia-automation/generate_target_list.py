#!/usr/bin/env python3
"""
CROVIA Target List Generator (Mechanical Criterion)

Generates target list based on deterministic, verifiable criteria:
- HuggingFace models with downloads ≥ 10,000 (last 30 days)
- Types: text-generation, text-classification, image-classification
- Publicly accessible
- Ordered by downloads DESC
- Limit: 300

This is NOT a ranking. This is a mechanical threshold.
"""

import requests
import json
from typing import List, Dict, Any
from datetime import datetime, timezone

# Mechanical criteria (non-editorial)
DOWNLOAD_THRESHOLD = 10000
MODEL_TYPES = [
    'text-generation',
    'text-classification', 
    'image-classification'
]
TARGET_LIMIT = 300

def fetch_models_by_criteria() -> List[Dict[str, Any]]:
    """
    Fetch models from HuggingFace API based on mechanical criteria.
    
    Criteria:
    - downloads ≥ 10,000
    - task types: text-generation, text-classification, image-classification
    - publicly accessible
    - sorted by downloads DESC
    """
    
    all_models = []
    
    for task_type in MODEL_TYPES:
        print(f"[INFO] Fetching models for task: {task_type}")
        
        try:
            # HuggingFace API endpoint
            url = f"https://huggingface.co/api/models"
            params = {
                'filter': task_type,
                'sort': 'downloads',
                'direction': -1,
                'limit': 100  # API limit per request
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                models = response.json()
                
                # Filter by download threshold
                for model in models:
                    downloads = model.get('downloads', 0)
                    model_id = model.get('modelId', model.get('id', ''))
                    
                    if downloads >= DOWNLOAD_THRESHOLD and model_id:
                        all_models.append({
                            'model_id': model_id,
                            'downloads': downloads,
                            'task': task_type,
                            'private': model.get('private', False)
                        })
                
                print(f"[INFO] Found {len([m for m in all_models if m['task'] == task_type])} models for {task_type}")
            else:
                print(f"[WARN] Failed to fetch {task_type}: HTTP {response.status_code}")
        
        except Exception as e:
            print(f"[ERROR] Error fetching {task_type}: {e}")
    
    # Remove duplicates (same model can have multiple tasks)
    unique_models = {}
    for model in all_models:
        model_id = model['model_id']
        if model_id not in unique_models:
            unique_models[model_id] = model
        else:
            # Keep the one with higher downloads
            if model['downloads'] > unique_models[model_id]['downloads']:
                unique_models[model_id] = model
    
    # Sort by downloads DESC
    sorted_models = sorted(unique_models.values(), key=lambda x: x['downloads'], reverse=True)
    
    # Filter out private models
    public_models = [m for m in sorted_models if not m.get('private', False)]
    
    # Limit to TARGET_LIMIT
    final_models = public_models[:TARGET_LIMIT]
    
    return final_models

def generate_targets_json(models: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate targets.json format."""
    
    targets = {
        'schema': 'crovia.targets.v1',
        'generated_at': datetime.now(timezone.utc).isoformat() + 'Z',
        'criteria': {
            'download_threshold': DOWNLOAD_THRESHOLD,
            'model_types': MODEL_TYPES,
            'limit': TARGET_LIMIT,
            'note': 'Mechanical criterion - not editorial selection'
        },
        'targets': [
            {
                'target_id': model['model_id'],
                'tipo_target': 'model',
                'metadata': {
                    'downloads': model['downloads'],
                    'task': model['task']
                }
            }
            for model in models
        ]
    }
    
    return targets

def main():
    print("=" * 80)
    print("CROVIA Target List Generator")
    print("=" * 80)
    print(f"Criteria: downloads ≥ {DOWNLOAD_THRESHOLD}, types: {MODEL_TYPES}")
    print(f"Limit: {TARGET_LIMIT}")
    print()
    
    # Fetch models
    print("[1/3] Fetching models from HuggingFace API...")
    models = fetch_models_by_criteria()
    
    print()
    print(f"[INFO] Total models found: {len(models)}")
    print(f"[INFO] Download range: {models[-1]['downloads']} - {models[0]['downloads']}")
    
    # Generate targets.json
    print()
    print("[2/3] Generating targets.json...")
    targets_data = generate_targets_json(models)
    
    # Write to file
    output_file = 'targets_generated.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(targets_data, f, indent=2, ensure_ascii=False)
    
    print(f"[INFO] Written to {output_file}")
    
    # Summary
    print()
    print("[3/3] Summary:")
    print(f"  Total targets: {len(targets_data['targets'])}")
    print(f"  Generated at: {targets_data['generated_at']}")
    print(f"  Criteria: Mechanical (downloads ≥ {DOWNLOAD_THRESHOLD})")
    print()
    
    # Sample targets
    print("Sample targets (top 10):")
    for i, target in enumerate(targets_data['targets'][:10], 1):
        print(f"  {i}. {target['target_id']} ({target['metadata']['downloads']:,} downloads)")
    
    print()
    print("=" * 80)
    print("DONE")
    print("=" * 80)

if __name__ == '__main__':
    main()
