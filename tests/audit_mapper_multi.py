"""
Multi-model audit of ComplianceMapper accuracy.
Runs the REAL ComplianceMapper against known models and compares to manual ground truth.
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'crovia-pro-engine'))

import requests
from croviapro.compliance.mapper import ComplianceMapper

def fetch_card(model_id):
    url = f'https://huggingface.co/{model_id}/raw/main/README.md'
    r = requests.get(url, timeout=20)
    if r.status_code == 200:
        return r.text
    return None

# Manual ground truth per model (from human reading of model cards)
GROUND_TRUTHS = {
    'openai-community/gpt2': {
        'NEC#1': 'present',   # Training data section: WebText, 40GB, Reddit scraping
        'NEC#2': 'partial',   # license:mit = MODEL license, no DATA license
        'NEC#3': 'present',   # Transformers model, 124M params, CLM, mask-mechanism
        'NEC#4': 'partial',   # 256 TPU v3 cores, but "duration not disclosed, nor exact details"
        'NEC#5': 'present',   # Full benchmark table
        'NEC#6': 'absent',    # No safety eval, no red-teaming
        'NEC#7': 'present',   # "text generation or fine-tune"
        'NEC#8': 'absent',    # Nothing about carbon/energy
        'NEC#9': 'absent',    # Nothing about human oversight
        'NEC#10': 'absent',   # Nothing about data retention
        'NEC#11': 'present',  # Limitations and bias section
        'NEC#12': 'present',  # Detailed bias examples with code
        'NEC#13': 'partial',  # "The team releasing GPT-2", "openAI team" - informal
        'NEC#14': 'present',  # BPE, vocab 50257, seq 1024
        'NEC#15': 'absent',   # Only "English language", no scope declaration
        'NEC#16': 'absent',   # Nothing about security
        'NEC#17': 'present',  # "How to use" section with code
        'NEC#18': 'absent',   # No reporting mechanism
        'NEC#19': 'partial',  # Related Models, paper link, but no changelog
        'NEC#20': 'partial',  # "bias will affect all fine-tuned versions"
    },
    'mistralai/Mistral-7B-v0.1': {
        'NEC#1': 'absent',    # No training data info at all ("pretrained" but no data sources)
        'NEC#2': 'partial',   # Apache 2.0 model license in YAML, no data license
        'NEC#3': 'present',   # Architecture: transformer, GQA, SWA, BPE tokenizer
        'NEC#4': 'absent',    # No training procedure info
        'NEC#5': 'partial',   # Claims "outperforms on all benchmarks" but no inline results table
        'NEC#6': 'absent',    # No safety evaluation
        'NEC#7': 'absent',    # No explicit intended use section or statement
        'NEC#8': 'absent',    # Nothing about environment
        'NEC#9': 'absent',    # Nothing about human oversight
        'NEC#10': 'absent',   # Nothing about data retention
        'NEC#11': 'partial',  # Notice section: "no moderation mechanisms" = limitation
        'NEC#12': 'absent',   # No bias assessment
        'NEC#13': 'present',  # "The Mistral AI Team" clearly identified with full names
        'NEC#14': 'partial',  # "BPE tokenizer" mentioned but minimal preprocessing detail
        'NEC#15': 'absent',   # Only YAML "language: en", no scope declaration
        'NEC#16': 'absent',   # Nothing about security
        'NEC#17': 'absent',   # Only troubleshooting, no deployment/usage guide
        'NEC#18': 'absent',   # No reporting mechanism
        'NEC#19': 'absent',   # No version history
        'NEC#20': 'absent',   # No downstream impact discussion
    },
    'bigscience/bloom': {
        'NEC#1': 'present',   # ROOTS corpus, 46 languages, 1.6TB
        'NEC#2': 'partial',   # RAIL license covers model AND data, but not explicit data-specific licensing section
        'NEC#3': 'present',   # Architecture described: 176B params, transformer
        'NEC#4': 'present',   # Training details: hardware (Jean Zay), 384 A100 GPUs
        'NEC#5': 'present',   # Evaluation results section
        'NEC#6': 'partial',   # Risk discussion in "Risks and Limitations" but no formal red-teaming/safety eval
        'NEC#7': 'present',   # Intended uses section
        'NEC#8': 'present',   # Carbon footprint section with quantified data
        'NEC#9': 'absent',    # No human oversight section
        'NEC#10': 'absent',   # No data retention policy
        'NEC#11': 'present',  # Limitations section
        'NEC#12': 'partial',  # Bias discussed within Risks section, not dedicated formal assessment
        'NEC#13': 'present',  # BigScience clearly identified, "Developed by" field
        'NEC#14': 'present',  # Preprocessing described
        'NEC#15': 'present',  # 46 languages documented
        'NEC#16': 'absent',   # No security assessment
        'NEC#17': 'present',  # How to use section
        'NEC#18': 'absent',   # No incident reporting (mentions "feedback" as recommendation, not implemented system)
        'NEC#19': 'partial',  # Version info, but no formal changelog
        'NEC#20': 'present',  # Dedicated "Downstream use" section
    },
}

# Additional models for broader validation
GROUND_TRUTHS['meta-llama/Llama-2-7b'] = {
    'NEC#1': 'present',   # Training data described
    'NEC#2': 'partial',   # Llama 2 Community License, not data-specific
    'NEC#3': 'present',   # Architecture well documented
    'NEC#4': 'present',   # Training methodology documented (A100 GPUs, etc.)
    'NEC#5': 'present',   # Benchmark results included
    'NEC#6': 'present',   # Red teaming, safety evaluations documented
    'NEC#7': 'present',   # Intended use clearly stated
    'NEC#8': 'present',   # Carbon footprint documented
    'NEC#9': 'absent',    # No human oversight section
    'NEC#10': 'absent',   # No data retention policy
    'NEC#11': 'present',  # Known limitations documented
    'NEC#12': 'present',  # Bias evaluation documented
    'NEC#13': 'present',  # Meta clearly identified
    'NEC#14': 'present',  # Data preprocessing documented
    'NEC#15': 'partial',  # English focus mentioned but limited multilingual scope
    'NEC#16': 'absent',   # No formal security assessment
    'NEC#17': 'present',  # How to use section
    'NEC#18': 'partial',  # Some feedback mechanisms mentioned
    'NEC#19': 'partial',  # Version info (Llama 2 vs Llama 1)
    'NEC#20': 'present',  # Downstream impact discussed
}

GROUND_TRUTHS['EleutherAI/gpt-neo-2.7B'] = {
    'NEC#1': 'present',   # The Pile dataset described
    'NEC#2': 'partial',   # MIT license for model, Pile has mixed licensing
    'NEC#3': 'present',   # Architecture documented
    'NEC#4': 'partial',   # Some training info but limited
    'NEC#5': 'present',   # Benchmark results
    'NEC#6': 'absent',    # No safety evaluation
    'NEC#7': 'present',   # Intended use documented
    'NEC#8': 'absent',    # No environmental info
    'NEC#9': 'absent',    # No human oversight
    'NEC#10': 'absent',   # No data retention
    'NEC#11': 'present',  # Limitations documented
    'NEC#12': 'present',  # Bias section
    'NEC#13': 'present',  # EleutherAI identified
    'NEC#14': 'partial',  # Some preprocessing mentioned
    'NEC#15': 'absent',   # English-only, no multilingual scope
    'NEC#16': 'absent',   # No security assessment
    'NEC#17': 'present',  # How to use section
    'NEC#18': 'absent',   # No incident reporting
    'NEC#19': 'absent',   # No version history
    'NEC#20': 'partial',  # Some downstream mention
}

mapper = ComplianceMapper()

print("=" * 120)
print("COMPLIANCE MAPPER MULTI-MODEL AUDIT")
print("=" * 120)

total_correct = 0
total_checks = 0
all_issues = []

for model_id, ground_truth in GROUND_TRUTHS.items():
    print(f"\n{'-' * 120}")
    print(f"MODEL: {model_id}")
    print(f"{'-' * 120}")
    
    card = fetch_card(model_id)
    if not card:
        print(f"  SKIP: Could not fetch card")
        continue
    
    report = mapper.analyze(model_id, card)
    
    model_correct = 0
    model_issues = []
    
    for obs in report.observations:
        gt = ground_truth.get(obs.nec_id, '?')
        if gt == '?':
            continue
        
        total_checks += 1
        match = obs.status == gt
        
        if match:
            icon = ' OK '
            model_correct += 1
            total_correct += 1
        elif obs.status == 'present' and gt == 'absent':
            icon = '*FP*'
            model_issues.append((obs.nec_id, obs.name, obs.status, gt, obs.evidence))
        elif obs.status == 'absent' and gt == 'present':
            icon = '*FN*'
            model_issues.append((obs.nec_id, obs.name, obs.status, gt, obs.evidence))
        else:
            icon = 'MISM'
            model_issues.append((obs.nec_id, obs.name, obs.status, gt, obs.evidence))
        
        ev_short = str(obs.evidence[:2]) if obs.evidence else '[]'
        print(f"  [{icon}] {obs.nec_id}  {obs.name:25s}  Mapper={obs.status:7s}  Truth={gt:7s}  {ev_short}")
    
    print(f"\n  SCORE: {model_correct}/20 correct")
    
    if model_issues:
        print(f"  ISSUES ({len(model_issues)}):")
        for nec_id, name, mapper_st, truth_st, evidence in model_issues:
            err_type = 'FALSE POSITIVE' if mapper_st == 'present' and truth_st == 'absent' else (
                'FALSE NEGATIVE' if mapper_st == 'absent' and truth_st == 'present' else 'SEVERITY MISMATCH')
            print(f"    {nec_id} {name}: {err_type} (mapper={mapper_st}, truth={truth_st})")
            print(f"      Evidence: {evidence}")
        all_issues.extend([(model_id, *i) for i in model_issues])

print(f"\n{'=' * 120}")
print(f"TOTAL ACCURACY: {total_correct}/{total_checks} ({total_correct/total_checks*100:.1f}%)")
print(f"TOTAL ISSUES: {len(all_issues)}")
print(f"{'=' * 120}")

if all_issues:
    print("\nALL ISSUES SUMMARY:")
    for model_id, nec_id, name, mapper_st, truth_st, evidence in all_issues:
        short_model = model_id.split('/')[-1]
        print(f"  {short_model:20s} {nec_id} {name:25s} mapper={mapper_st:7s} truth={truth_st:7s}")
