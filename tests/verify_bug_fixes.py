"""Verify specific bug fixes identified in review."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'crovia-pro-engine'))

from croviapro.compliance.mapper import ComplianceMapper

m = ComplianceMapper()
passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name} -- {detail}")
        failed += 1


print("=== BUG 1: NEC#1 'pretrained on' false positive ===")

card_pretrained = (
    "# Model Card\n"
    "## Description\n"
    "This is a pretrained generative text model with 7B parameters.\n"
    "It outperforms other models on all benchmarks.\n"
)
r = m.analyze('test/pretrained-only', card_pretrained)
nec1 = [o for o in r.observations if o.nec_id == 'NEC#1'][0]
print(f"  Card with only 'pretrained' (no data sources) -> {nec1.status}")
check("pretrained-only is absent", nec1.status == 'absent',
      f"got {nec1.status}, evidence: {nec1.evidence}")

card_trained_on = (
    "# Model Card\n"
    "## Training data\n"
    "This model was trained on the Common Crawl dataset, 1TB of web text.\n"
)
r2 = m.analyze('test/trained-on', card_trained_on)
nec1b = [o for o in r2.observations if o.nec_id == 'NEC#1'][0]
print(f"  Card with 'trained on Common Crawl' -> {nec1b.status}")
check("trained-on is present", nec1b.status == 'present',
      f"got {nec1b.status}")

card_separated = (
    "# Model Card\n"
    "## Overview\n"
    "We provide training scripts. The data is available on request.\n"
)
r3 = m.analyze('test/training-data-separated', card_separated)
nec1c = [o for o in r3.observations if o.nec_id == 'NEC#1'][0]
print(f"  Card with 'training' and 'data' in different contexts -> {nec1c.status}")
check("separated training+data no longer matches as phrase", nec1c.status == 'absent',
      f"got {nec1c.status}, evidence: {nec1c.evidence}")


print("\n=== BUG 2: NEC#10 canonical alignment ===")

det = m.detectors['NEC#10']
print(f"  Mapper name: '{det.name}'")
print(f"  Canon name:  'Missing temporal validity and revocation metadata'")
check("NEC#10 name matches canon",
      "temporal validity" in det.name.lower(),
      f"got '{det.name}'")

card_deprecated = (
    "# Model Card\n"
    "## Deprecation Notice\n"
    "This model has been deprecated as of 2025-06-01.\n"
    "Please use v2 instead. End of life: 2026-01-01.\n"
)
r4 = m.analyze('test/deprecated', card_deprecated)
nec10 = [o for o in r4.observations if o.nec_id == 'NEC#10'][0]
print(f"  Card with deprecation notice -> {nec10.status}")
check("deprecation detected", nec10.status in ('present', 'partial'),
      f"got {nec10.status}")

card_no_lifecycle = (
    "# Model Card\n"
    "## Overview\n"
    "A language model for text generation.\n"
)
r5 = m.analyze('test/no-lifecycle', card_no_lifecycle)
nec10b = [o for o in r5.observations if o.nec_id == 'NEC#10'][0]
print(f"  Card without any lifecycle info -> {nec10b.status}")
check("no lifecycle is absent", nec10b.status == 'absent',
      f"got {nec10b.status}")


print("\n=== BUG 3: NEC#15 'multilingual' in keywords_strong ===")

card_ml_tok = (
    "# Model Card\n"
    "## Architecture\n"
    "This model uses a multilingual tokenizer based on BPE.\n"
    "The model is designed for English text only.\n"
)
r6 = m.analyze('test/multilingual-tokenizer', card_ml_tok)
nec15 = [o for o in r6.observations if o.nec_id == 'NEC#15'][0]
print(f"  Card with 'multilingual tokenizer' only -> {nec15.status}")
check("multilingual tokenizer alone is not PRESENT",
      nec15.status != 'present',
      f"got {nec15.status}")

card_real_ml = (
    "# Model Card\n"
    "## Languages\n"
    "This model supports 46 languages including English, French, German, "
    "Spanish, Chinese, Japanese, Korean, and Arabic.\n"
    "It is a multilingual model trained on diverse corpora.\n"
)
r7 = m.analyze('test/real-multilingual', card_real_ml)
nec15b = [o for o in r7.observations if o.nec_id == 'NEC#15'][0]
print(f"  Card with Languages section + multilingual -> {nec15b.status}")
check("real multilingual scope is present",
      nec15b.status == 'present',
      f"got {nec15b.status}")


print("\n=== BUG 4: crystal_type label accuracy (temporal_estoppel) ===")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'crovia-pro-engine'))
from croviapro.tpa.temporal_estoppel import (
    INDICATIVE_REVIEW_PERIOD_DAYS, INDICATIVE_DAILY_RATE_EUR,
    CRYSTALLIZATION_THRESHOLDS, DAILY_FINE_RATE_EUR,
)

check("INDICATIVE_REVIEW_PERIOD_DAYS exists",
      isinstance(INDICATIVE_REVIEW_PERIOD_DAYS, dict))
check("backward compat alias works",
      CRYSTALLIZATION_THRESHOLDS is INDICATIVE_REVIEW_PERIOD_DAYS)
check("INDICATIVE_DAILY_RATE_EUR has disclaimer name",
      True)  # exists by import
check("backward compat alias works for rates",
      DAILY_FINE_RATE_EUR is INDICATIVE_DAILY_RATE_EUR)


print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed")
if failed > 0:
    sys.exit(1)
print("ALL TESTS PASSED")
