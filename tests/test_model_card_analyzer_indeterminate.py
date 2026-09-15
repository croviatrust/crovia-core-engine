import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "crovia-automation" / "model_card_analyzer.py"
SPEC = importlib.util.spec_from_file_location("model_card_analyzer", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def analyzer_with(readme, api_data):
    analyzer = MODULE.ModelCardAnalyzer()
    analyzer._fetch_readme = lambda repo_id, repo_type="model": (readme, api_data)
    return analyzer


def test_acquisition_failure_is_indeterminate_not_missing():
    analyzer = analyzer_with(None, None)

    with pytest.raises(RuntimeError, match="indeterminate acquisition"):
        analyzer.analyze("example/unreachable")

    assert analyzer.get_stats()["errors"] == 1
    assert analyzer.get_stats()["analyzed"] == 0


def test_nullable_card_data_does_not_crash():
    result = analyzer_with("# Model\n\nSubstantive description.", {"cardData": None}).analyze(
        "example/nullable"
    )

    assert result.readme_found is True
    assert result.has_license is False


def test_equal_length_content_changes_analysis_digest():
    first = analyzer_with("## Training\nDetails", {}).analyze("example/model")
    second = analyzer_with("## Intended\nDetails", {}).analyze("example/model")

    assert len("## Training\nDetails") == len("## Intended\nDetails")
    assert first.analysis_hash != second.analysis_hash
