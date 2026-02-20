"""
Minimal pytest suite for crovia-core-engine open core.
Covers: CLI entry point, CRC-1 pipeline (run + verify), validator, ask_menu CI safety.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples"
MINIMAL_RECEIPTS = EXAMPLES / "minimal_royalty_receipts.ndjson"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_cli(*args, cwd=None, env=None):
    """Run crovia CLI as subprocess, return CompletedProcess."""
    return subprocess.run(
        [sys.executable, "-m", "crovia.cli", *args],
        capture_output=True, text=True,
        cwd=str(cwd or REPO), env=env or os.environ.copy()
    )


# ---------------------------------------------------------------------------
# 1. CLI entry point
# ---------------------------------------------------------------------------

def test_cli_no_args():
    """crovia with no args should exit 0 or 1 (not crash)."""
    r = run_cli()
    assert r.returncode in (0, 1)


def test_cli_legend():
    r = run_cli("legend")
    assert r.returncode == 0
    assert "crovia" in r.stdout.lower()


def test_cli_wedge_explain():
    r = run_cli("wedge", "explain")
    assert r.returncode == 0
    assert "PRIMARY" in r.stdout.upper() or "artifact" in r.stdout.lower()


def test_cli_scan_roadmap():
    """crovia scan should always exit 0 and mention ROADMAP/FAISS."""
    r = run_cli("scan", "dummy.ndjson")
    assert r.returncode == 0
    assert "FAISS" in r.stdout or "roadmap" in r.stdout.lower()


# ---------------------------------------------------------------------------
# 2. ask_menu — CI/headless safety
# ---------------------------------------------------------------------------

def test_ask_menu_eof():
    """ask_menu must not crash when stdin is closed (CI/headless)."""
    code = (
        "from crovia.cli import ask_menu; "
        "result = ask_menu('Choose', ['a', 'b', 'cancel']); "
        "assert result == 3, f'Expected 3 (last option), got {result}'"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True,
        stdin=subprocess.DEVNULL
    )
    assert r.returncode == 0, f"ask_menu crashed on EOF:\n{r.stderr}"


# ---------------------------------------------------------------------------
# 3. Validator (check command)
# ---------------------------------------------------------------------------

def test_check_valid_file():
    """crovia check on the example receipts should report Health A or B."""
    if not MINIMAL_RECEIPTS.exists():
        pytest.skip("Example receipts file not found")
    r = run_cli("check", str(MINIMAL_RECEIPTS))
    assert r.returncode == 0
    assert "Health" in r.stdout or "valid" in r.stdout.lower()


def test_check_missing_file():
    """crovia check on a non-existent file should exit non-zero."""
    r = run_cli("check", "nonexistent_file_xyz.ndjson")
    assert r.returncode != 0


# ---------------------------------------------------------------------------
# 4. CRC-1 pipeline: run + verify
# ---------------------------------------------------------------------------

def test_run_and_verify():
    """Full CRC-1 pipeline: crovia run -> crovia-verify."""
    if not MINIMAL_RECEIPTS.exists():
        pytest.skip("Example receipts file not found")

    with tempfile.TemporaryDirectory() as tmpdir:
        r = subprocess.run(
            [sys.executable, "-m", "crovia.cli", "run",
             "--receipts", str(MINIMAL_RECEIPTS),
             "--period", "2025-11",
             "--budget", "1000000",
             "--out", tmpdir],
            capture_output=True, text=True, cwd=str(REPO)
        )
        assert r.returncode == 0, f"crovia run failed:\n{r.stdout}\n{r.stderr}"

        manifest = Path(tmpdir) / "MANIFEST.json"
        assert manifest.exists(), "MANIFEST.json not created"
        m = json.loads(manifest.read_text())
        assert m.get("contract") == "CRC-1"

        r2 = subprocess.run(
            [sys.executable, "-m", "crovia.verify", tmpdir],
            capture_output=True, text=True, cwd=str(REPO)
        )
        assert r2.returncode == 0, f"crovia-verify failed:\n{r2.stdout}\n{r2.stderr}"
        assert "CRC-1 VERIFIED" in r2.stdout
