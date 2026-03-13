#!/usr/bin/env python3
"""
CROVIA Dataset Target Generator (Mechanical Criterion)

Generates dataset target list based on deterministic criteria:
- HuggingFace datasets with downloads ≥ 5,000
- Publicly accessible
- Ordered by downloads DESC
- Limit: 150

This is NOT a ranking. This is a mechanical threshold.
"""

import requests
import json
from datetime import datetime, timezone

DOWNLOAD_THRESHOLD = 5000
TARGET_LIMIT = 150

def fetch_datasets_by_criteria():
    """Fetch datasets from HuggingFace API based on mechanical criteria."""
    
    all_datasets = []
    
    try:
        # HuggingFace API endpoint for datasets
        url = "https://huggingface.co/api/datasets"
        params = {
            'sort': 'downloads',
            'direction': -1,
            'limit': 200  # Fetch more, filter by threshold
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            datasets = response.json()
            
            # Filter by download threshold and public access
            for dataset in datasets:
                downloads = dataset.get('downloads', 0)
                dataset_id = dataset.get('id', '')
                private = dataset.get('private', False)
                
                if downloads >= DOWNLOAD_THRESHOLD and dataset_id and not private:
                    all_datasets.append({
                        'dataset_id': dataset_id,
                        'downloads': downloads,
                        'private': private
                    })
            
            print(f"[INFO] Found {len(all_datasets)} datasets with downloads ≥ {DOWNLOAD_THRESHOLD}")
        else:
            print(f"[WARN] Failed to fetch datasets: HTTP {response.status_code}")
    
    except Exception as e:
        print(f"[ERROR] Error fetching datasets: {e}")
    
    # Sort by downloads DESC
    all_datasets.sort(key=lambda x: x['downloads'], reverse=True)
    
    # Limit to TARGET_LIMIT
    final_datasets = all_datasets[:TARGET_LIMIT]
    
    return final_datasets

def generate_targets_json(datasets):
    """Generate targets in same format as models."""
    
    targets = []
    for dataset in datasets:
        targets.append({
            'target_id': dataset['dataset_id'],
            'tipo_target': 'dataset',
            'metadata': {
                'downloads': dataset['downloads']
            }
        })
    
    return targets

def main():
    print("=" * 80)
    print("CROVIA Dataset Target Generator")
    print("=" * 80)
    print(f"Criteria: downloads ≥ {DOWNLOAD_THRESHOLD}")
    print(f"Limit: {TARGET_LIMIT}")
    print()
    
    # Fetch datasets
    print("[1/2] Fetching datasets from HuggingFace API...")
    datasets = fetch_datasets_by_criteria()
    
    print()
    print(f"[INFO] Total datasets found: {len(datasets)}")
    if datasets:
        print(f"[INFO] Download range: {datasets[-1]['downloads']} - {datasets[0]['downloads']}")
    
    # Generate targets
    print()
    print("[2/2] Generating targets...")
    targets = generate_targets_json(datasets)
    
    # Write to file
    output_data = {
        'schema': 'crovia.targets.v1',
        'generated_at': datetime.now(timezone.utc).isoformat() + 'Z',
        'criteria': {
            'download_threshold': DOWNLOAD_THRESHOLD,
            'target_type': 'dataset',
            'limit': TARGET_LIMIT,
            'note': 'Mechanical criterion - not editorial selection'
        },
        'targets': targets
    }
    
    output_file = 'dataset_targets_generated.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"[INFO] Written to {output_file}")
    
    # Summary
    print()
    print("Summary:")
    print(f"  Total dataset targets: {len(targets)}")
    print(f"  Generated at: {output_data['generated_at']}")
    print(f"  Criteria: Mechanical (downloads ≥ {DOWNLOAD_THRESHOLD})")
    print()
    
    # Sample targets
    print("Sample datasets (top 10):")
    for i, target in enumerate(targets[:10], 1):
        print(f"  {i}. {target['target_id']} ({target['metadata']['downloads']:,} downloads)")
    
    print()
    print("=" * 80)
    print("DONE")
    print("=" * 80)

if __name__ == '__main__':
    main()
