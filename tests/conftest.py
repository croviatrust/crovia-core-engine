"""Skip test modules that import the professional-tier package when it is absent."""
import importlib.util

_PRIVATE_DEPENDENT = [
    "golden/test_claim_evaluation_determinism.py",
    "golden/test_dsl_number_validation.py",
    "golden/test_evidence_envelope_validation.py",
    "golden/test_ruleset_utils.py",
    "test_family_cycles.py",
    "test_gdna_fixes.py",
    "test_oras_engine.py",
    "test_oras_router.py",
]

collect_ignore = [] if importlib.util.find_spec("croviapro") else list(_PRIVATE_DEPENDENT)
