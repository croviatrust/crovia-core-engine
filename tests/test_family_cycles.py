from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "crovia-pro-engine"))

from croviapro.sonar_v2.family_cycles import get_family_members, select_family_cycle


def test_pythia_family_includes_deduped_by_default():
    members = get_family_members("pythia")
    assert "EleutherAI/pythia-70m" in members
    assert "EleutherAI/pythia-70m-deduped" in members


def test_pythia_family_can_exclude_deduped():
    members = get_family_members("pythia", include_deduped=False)
    assert all("deduped" not in model_id.lower() for model_id in members)
    assert "EleutherAI/pythia-70m" in members


def test_family_cycle_selects_next_pending_window():
    processed = {
        "EleutherAI/pythia-70m",
        "EleutherAI/pythia-70m-deduped",
        "EleutherAI/pythia-160m",
    }
    cycle = select_family_cycle("pythia", processed=processed, cycle_size=2)
    assert cycle["selected"] == [
        "EleutherAI/pythia-160m-deduped",
        "EleutherAI/pythia-410m",
    ]


def test_gdna_cycle_can_bridge_previous_models():
    processed = {
        "EleutherAI/pythia-70m",
        "EleutherAI/pythia-70m-deduped",
        "EleutherAI/pythia-160m",
    }
    cycle = select_family_cycle("pythia", processed=processed, cycle_size=2, bridge_count=2)
    assert cycle["selected"] == [
        "EleutherAI/pythia-70m-deduped",
        "EleutherAI/pythia-160m",
        "EleutherAI/pythia-160m-deduped",
        "EleutherAI/pythia-410m",
    ]
