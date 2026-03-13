"""
Audit ComplianceMapper accuracy against manual ground truth.
GPT-2 model card used as test case.
"""
import requests, re, json, sys

def fetch_card(model_id):
    r = requests.get(f'https://huggingface.co/{model_id}/raw/main/README.md', timeout=15)
    if r.status_code == 200:
        return r.text
    return None

card = fetch_card('openai-community/gpt2')
if not card:
    print("FAIL: could not fetch GPT-2 card")
    sys.exit(1)

tl = card.lower()

def extract_sections(text):
    sections = {}
    current = '_preamble'
    buf = []
    for line in text.split('\n'):
        m = re.match(r'^(#{1,4})\s+(.+)$', line)
        if m:
            if buf:
                sections[current.lower()] = '\n'.join(buf)
            current = m.group(2).strip()
            buf = []
        else:
            buf.append(line)
    if buf:
        sections[current.lower()] = '\n'.join(buf)
    return sections

sections = extract_sections(card)

# --- NEC# detectors (reimplemented from ComplianceMapper logic) ---
DETS = {
    'NEC#1':  {'name':'Data provenance',     'sh':['training data','training dataset','data sources','pre-training data'],       'ks':['training data','training dataset','pre-training data'],                  'kr':[['training','data'],['trained','on'],['pre-training','data'],['training','corpus'],['training','dataset']], 'mc':50},
    'NEC#2':  {'name':'License attribution',  'sh':['license','terms of use','data rights'],                                      'ks':['data license','training data license','licensed under'],                 'kr':[['license','data'],['copyright','training'],['rights','dataset'],['data','usage','rights']], 'mc':50},
    'NEC#3':  {'name':'Model architecture',   'sh':['architecture','model architecture','model information','technical details'],  'ks':['architecture','transformer','decoder','encoder'],                        'kr':[['transformer','layer'],['architecture','model'],['hidden','size'],['attention','head'],['parameter','billion'],['parameter','million']], 'mc':50},
    'NEC#4':  {'name':'Training methodology', 'sh':['training','training details','implementation','hardware'],                   'ks':['hyperparameter','learning rate','TPU','GPU','A100','H100'],               'kr':[['learning','rate'],['batch','size'],['training','epoch'],['optimizer'],['training','hardware'],['training','infrastructure']], 'mc':50},
    'NEC#5':  {'name':'Evaluation results',   'sh':['evaluation','benchmark','results','performance'],                            'ks':['benchmark','evaluation','MMLU','HellaSwag','ARC','WinoGrande'],           'kr':[['benchmark','result'],['evaluation','metric'],['accuracy','score'],['MMLU'],['HellaSwag'],['perplexity']], 'mc':50},
    'NEC#6':  {'name':'Safety evaluation',    'sh':['safety','risk','responsible ai','ethics'],                                    'ks':['safety','red team','red-team','adversarial'],                            'kr':[['safety','evaluation'],['red','team'],['adversarial','test'],['harmful','content'],['risk','assessment']], 'mc':30},
    'NEC#7':  {'name':'Intended use',         'sh':['intended use','use cases','applications'],                                   'ks':['intended use','intended for','designed for'],                            'kr':[['intended','use'],['designed','for'],['use','case'],['meant','for']], 'mc':50},
    'NEC#8':  {'name':'Environmental impact', 'sh':['environmental','carbon','sustainability'],                                   'ks':['carbon','CO2','energy consumption','environmental'],                     'kr':[['carbon','footprint'],['energy','consumption'],['CO2','emission'],['compute','cost'],['environmental','impact']], 'mc':30},
    'NEC#9':  {'name':'Human oversight',      'sh':['human oversight','governance'],                                              'ks':['human oversight','human-in-the-loop','human review'],                    'kr':[['human','oversight'],['human-in-the-loop'],['human','review'],['human','intervention']], 'mc':30},
    'NEC#10': {'name':'Data retention',       'sh':['data retention','data policy','privacy'],                                     'ks':['data retention','right to erasure','data deletion'],                     'kr':[['data','retention'],['data','deletion'],['right','erasure'],['data','removal']], 'mc':30},
    'NEC#11': {'name':'Known limitations',    'sh':['limitations','known issues','caveats'],                                       'ks':['limitation','limitations','not intended','should not'],                  'kr':[['limitation','model'],['should','not','use'],['not','intended'],['caveat'],['failure','mode']], 'mc':50},
    'NEC#12': {'name':'Bias assessment',      'sh':['bias','fairness','ethics','responsible'],                                     'ks':['bias','fairness','demographic','representation'],                        'kr':[['bias','evaluation'],['fairness','assessment'],['demographic','analysis'],['bias','mitigation']], 'mc':50},
    'NEC#13': {'name':'Accountable entity',   'sh':['authors','team','organization','contact'],                                   'ks':['developed by','maintained by','contact'],                                'kr':[['developed','by'],['created','by'],['maintained','by'],['contact']], 'mc':50},
    'NEC#14': {'name':'Data preprocessing',   'sh':['data preprocessing','data preparation','data processing'],                    'ks':['preprocessing','deduplication','data cleaning','tokeniz'],               'kr':[['preprocessing','data'],['data','cleaning'],['deduplication'],['filtering','data'],['tokenization']], 'mc':50},
    'NEC#15': {'name':'Multilingual scope',   'sh':['languages','multilingual'],                                                  'ks':['multilingual','languages supported','language coverage'],                 'kr':[['language','support'],['multilingual'],['languages']], 'mc':20},
    'NEC#16': {'name':'Security assessment',  'sh':['security','robustness'],                                                     'ks':['security','vulnerability','adversarial robustness'],                     'kr':[['security','assessment'],['vulnerability'],['adversarial','robustness'],['cybersecurity']], 'mc':30},
    'NEC#17': {'name':'Deployment guidelines','sh':['usage','deployment','getting started','quickstart'],                          'ks':['deployment','integration','how to use','getting started'],               'kr':[['deployment','guide'],['integration','guide'],['getting','started'],['how','to','use']], 'mc':50},
    'NEC#18': {'name':'Incident reporting',   'sh':['reporting','feedback','contact'],                                             'ks':['report','feedback','issue tracker','responsible disclosure'],             'kr':[['report','issue'],['incident','report'],['feedback','mechanism'],['bug','report']], 'mc':20},
    'NEC#19': {'name':'Version history',      'sh':['changelog','version','release notes','history'],                              'ks':['changelog','version history','release notes'],                           'kr':[['version','history'],['changelog'],['release','note'],['v1','v2']], 'mc':20},
    'NEC#20': {'name':'Downstream impact',    'sh':['impact','downstream','societal'],                                            'ks':['downstream','impact assessment','societal impact'],                      'kr':[['downstream','impact'],['downstream','risk'],['fine-tuning','risk'],['impact','assessment']], 'mc':30},
}

# Manual ground truth for GPT-2 (by human reading)
GROUND_TRUTH = {
    'NEC#1': 'PRESENT',  # Training data section: WebText, 40GB, Reddit scraping, no Wikipedia
    'NEC#2': 'PARTIAL',  # license:mit = MODEL license, but no DATA license
    'NEC#3': 'PRESENT',  # Transformers model, 124M params, CLM, mask-mechanism
    'NEC#4': 'PARTIAL',  # 256 TPU v3 cores, but 'duration not disclosed, nor exact details'
    'NEC#5': 'PRESENT',  # Full benchmark table
    'NEC#6': 'ABSENT',   # No safety eval, no red-teaming, no risk assessment
    'NEC#7': 'PRESENT',  # 'text generation or fine-tune'
    'NEC#8': 'ABSENT',   # Nothing about carbon/energy/environment
    'NEC#9': 'ABSENT',   # Nothing about human oversight
    'NEC#10': 'ABSENT',  # Nothing about data retention/deletion/erasure
    'NEC#11': 'PRESENT', # Limitations and bias section with bias examples
    'NEC#12': 'PRESENT', # Detailed bias examples with code (racial bias demo)
    'NEC#13': 'PARTIAL', # 'The team releasing GPT-2', 'openAI team' - no formal 'Developed by' field
    'NEC#14': 'PRESENT', # BPE, vocab 50257, seq 1024 in Preprocessing section
    'NEC#15': 'ABSENT',  # Only says 'English' in passing, no language scope declaration
    'NEC#16': 'ABSENT',  # Nothing about security
    'NEC#17': 'PRESENT', # 'How to use' section with code
    'NEC#18': 'ABSENT',  # No reporting mechanism
    'NEC#19': 'PARTIAL', # Related Models referenced, paper linked, but no changelog
    'NEC#20': 'PARTIAL', # 'bias will affect all fine-tuned versions' = downstream impact mention
}

GROUND_TRUTH_REASONS = {
    'NEC#1': 'Section Training data: WebText, 40GB, Reddit scraping described',
    'NEC#2': 'license:mit in YAML = MODEL license, NOT data rights',
    'NEC#3': 'transformers model, 124M params, CLM, mask-mechanism described',
    'NEC#4': '256 TPU v3 cores mentioned, but duration+details "not disclosed"',
    'NEC#5': 'Full benchmark table: LAMBADA, CBT, WikiText2, PTB',
    'NEC#6': 'No safety evaluation, no red-teaming, no risk assessment',
    'NEC#7': 'text generation or fine-tune to downstream task',
    'NEC#8': 'Nothing about carbon/energy/environment',
    'NEC#9': 'Nothing about human oversight',
    'NEC#10': 'Nothing about data retention/deletion/erasure',
    'NEC#11': 'Limitations and bias section with detailed examples',
    'NEC#12': 'Detailed bias examples with code (racial bias demo)',
    'NEC#13': '"The team releasing GPT-2", "openAI team" - but no formal Developed by field',
    'NEC#14': 'BPE tokenization, vocab 50257, seq 1024 described in Preprocessing section',
    'NEC#15': 'Says "English language" but no multilingual scope declaration',
    'NEC#16': 'Nothing about security/vulnerabilities',
    'NEC#17': '"How to use" section with PyTorch + TensorFlow code',
    'NEC#18': 'No reporting mechanism, no issue tracker link',
    'NEC#19': 'Related Models listed but no changelog/version history',
    'NEC#20': '"bias will also affect all fine-tuned versions" = downstream impact mention',
}


def run_detector(nec_id, det, card_lower, card_sections):
    score = 0.0
    evidence = []
    
    # Section header match (+0.4)
    for hint in det['sh']:
        for sn in card_sections:
            if hint in sn and len(card_sections[sn].strip()) >= det['mc']:
                score += 0.4
                evidence.append('sec:' + sn)
                break
        if score >= 0.4:
            break
    
    # Keyword match (+0.3)
    for kw in det['ks']:
        if kw.lower() in card_lower:
            score += 0.3
            evidence.append('kw:' + kw)
            break
    
    # Keyword group match (+0.3)
    for group in det['kr']:
        if all(kw.lower() in card_lower for kw in group):
            score += 0.3
            evidence.append('gr:' + '+'.join(group))
            break
    
    if score >= 0.6:
        result = 'PRESENT'
    elif score >= 0.3:
        result = 'PARTIAL'
    else:
        result = 'ABSENT'
    
    return result, score, evidence


print("=" * 100)
print("COMPLIANCE MAPPER AUDIT: GPT-2 (openai-community/gpt2)")
print("=" * 100)
print()
print(f"Card length: {len(card)} chars")
print(f"Sections found: {list(sections.keys())}")
print()

correct = 0
wrong_fp = 0
wrong_fn = 0
wrong_sev = 0
issues = []

for nec_id in sorted(DETS.keys(), key=lambda x: int(x.replace('NEC#',''))):
    det = DETS[nec_id]
    mapper_result, score, evidence = run_detector(nec_id, det, tl, sections)
    gt = GROUND_TRUTH[nec_id]
    
    if mapper_result == gt:
        icon = ' OK '
        correct += 1
    elif mapper_result == 'PRESENT' and gt in ('ABSENT',):
        icon = '*FP*'
        wrong_fp += 1
        issues.append((nec_id, det['name'], mapper_result, gt, GROUND_TRUTH_REASONS[nec_id], evidence, score))
    elif mapper_result == 'ABSENT' and gt in ('PRESENT',):
        icon = '*FN*'
        wrong_fn += 1
        issues.append((nec_id, det['name'], mapper_result, gt, GROUND_TRUTH_REASONS[nec_id], evidence, score))
    else:
        icon = 'MISM'
        wrong_sev += 1
        issues.append((nec_id, det['name'], mapper_result, gt, GROUND_TRUTH_REASONS[nec_id], evidence, score))

    name_pad = det['name'].ljust(25)
    print(f"  [{icon}] {nec_id}  {name_pad}  Mapper={mapper_result:7s}  Truth={gt:7s}  (score={score:.1f}) {evidence}")

print()
print("-" * 80)
absent_mapper = sum(1 for nid in DETS if run_detector(nid, DETS[nid], tl, sections)[0] == 'ABSENT')
partial_mapper = sum(1 for nid in DETS if run_detector(nid, DETS[nid], tl, sections)[0] == 'PARTIAL')
present_mapper = sum(1 for nid in DETS if run_detector(nid, DETS[nid], tl, sections)[0] == 'PRESENT')
absent_truth = sum(1 for v in GROUND_TRUTH.values() if v == 'ABSENT')
partial_truth = sum(1 for v in GROUND_TRUTH.values() if v == 'PARTIAL')
present_truth = sum(1 for v in GROUND_TRUTH.values() if v == 'PRESENT')

print(f"MAPPER OUTPUT:  Present={present_mapper}  Partial={partial_mapper}  Absent={absent_mapper}")
print(f"GROUND TRUTH:   Present={present_truth}  Partial={partial_truth}  Absent={absent_truth}")
print(f"ACCURACY: {correct}/20 correct  |  False Pos: {wrong_fp}  |  False Neg: {wrong_fn}  |  Severity mismatch: {wrong_sev}")
print()

if issues:
    print("=" * 80)
    print("ERRORS TO FIX:")
    print("=" * 80)
    for nec_id, name, mapper, truth, reason, evidence, score in issues:
        if mapper == 'PRESENT' and truth == 'ABSENT':
            err_type = 'FALSE POSITIVE'
        elif mapper == 'ABSENT' and truth == 'PRESENT':
            err_type = 'FALSE NEGATIVE'
        else:
            err_type = 'SEVERITY MISMATCH'
        print(f"\n  {nec_id} {name}: {err_type}")
        print(f"    Mapper says: {mapper}  (score={score:.1f})")
        print(f"    Truth is:    {truth}")
        print(f"    Reason:      {reason}")
        print(f"    Evidence:    {evidence}")
