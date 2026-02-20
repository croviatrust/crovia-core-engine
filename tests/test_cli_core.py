"""
Minimal pytest suite for crovia-core-engine open core.
Covers: CLI entry point, CRC-1 pipeline (run + verify), validator, ask_menu CI safety,
        verify_hashchain security regressions.
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


# ---------------------------------------------------------------------------
# 5. verify_hashchain security regressions
# ---------------------------------------------------------------------------

VERIFIER = REPO / "core" / "verify_hashchain.py"


def _build_valid_chain(source_path: Path, chain_path: Path, chunk: int = 10000):
    """Build a valid chain file for the given source using the same logic as hashchain_writer."""
    import hashlib
    prev = b"\x00" * 32
    h = hashlib.sha256()
    count = 0
    entries = []
    with open(source_path, "r", encoding="utf-8-sig") as f:
        for raw in f:
            s = raw.rstrip("\n")
            if not s:
                continue
            h.update(prev)
            h.update(s.encode("utf-8"))
            count += 1
            if (count % chunk) == 0:
                digest = h.hexdigest()
                entries.append((len(entries), count, digest))
                prev = bytes.fromhex(digest)
                h = hashlib.sha256()
    if (count % chunk) != 0 and count > 0:
        digest = h.hexdigest()
        entries.append((len(entries), count, digest))
    with open(chain_path, "w") as cf:
        for blk, upto, dg in entries:
            cf.write(f"{blk}\t{upto}\t{dg}\n")
    return count


def _run_verifier(source, chain, chunk=10000):
    return subprocess.run(
        [sys.executable, str(VERIFIER), "--source", str(source), "--chain", str(chain), "--chunk", str(chunk)],
        capture_output=True, text=True
    )


def test_verifier_valid_chain():
    """A correctly built chain must verify OK."""
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "src.ndjson"
        chain = Path(d) / "chain.txt"
        src.write_text("\n".join(json.dumps({"i": i}) for i in range(5)) + "\n")
        _build_valid_chain(src, chain, chunk=3)
        r = _run_verifier(src, chain, chunk=3)
        assert r.returncode == 0, f"Valid chain failed:\n{r.stderr}"
        assert "[VERIFY] OK" in r.stdout


def test_verifier_rejects_trailing_entries():
    """Chain with extra trailing entries must be rejected (was accepted before fix)."""
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "src.ndjson"
        chain = Path(d) / "chain.txt"
        src.write_text("\n".join(json.dumps({"i": i}) for i in range(5)) + "\n")
        _build_valid_chain(src, chain, chunk=3)
        # Append a spurious extra entry
        with open(chain, "a") as cf:
            cf.write("99\t9999\t" + "a" * 64 + "\n")
        r = _run_verifier(src, chain, chunk=3)
        assert r.returncode != 0, "Verifier should reject chain with trailing extra entries"
        assert "extra trailing" in r.stderr


def test_verifier_rejects_tampered_block_idx():
    """Chain with altered block_idx must be rejected."""
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "src.ndjson"
        chain = Path(d) / "chain.txt"
        src.write_text("\n".join(json.dumps({"i": i}) for i in range(5)) + "\n")
        _build_valid_chain(src, chain, chunk=3)
        lines = Path(chain).read_text().splitlines()
        # Tamper first entry's block_idx from 0 to 99
        parts = lines[0].split("\t")
        parts[0] = "99"
        lines[0] = "\t".join(parts)
        Path(chain).write_text("\n".join(lines) + "\n")
        r = _run_verifier(src, chain, chunk=3)
        assert r.returncode != 0, "Verifier should reject chain with tampered block_idx"
        assert "block_idx mismatch" in r.stderr


def test_verifier_rejects_non_hex_digest():
    """Chain entry with non-hex digest must be skipped/rejected."""
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "src.ndjson"
        chain = Path(d) / "chain.txt"
        src.write_text("\n".join(json.dumps({"i": i}) for i in range(5)) + "\n")
        _build_valid_chain(src, chain, chunk=3)
        lines = Path(chain).read_text().splitlines()
        # Replace digest with 64 non-hex chars
        parts = lines[0].split("\t")
        parts[2] = "g" * 64
        lines[0] = "\t".join(parts)
        Path(chain).write_text("\n".join(lines) + "\n")
        r = _run_verifier(src, chain, chunk=3)
        # Entry is skipped → chain appears shorter → must fail
        assert r.returncode != 0, "Verifier should reject chain with non-hex digest"


# ---------------------------------------------------------------------------
# 6. payouts_from_royalties — invalid period regression
# ---------------------------------------------------------------------------

PAYOUTS_SCRIPT = REPO / "core" / "payouts_from_royalties.py"


def test_payouts_invalid_period_fatal():
    """Invalid --period must exit non-zero and create no output files."""
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "receipts.ndjson"
        src.write_text('{"schema":"royalty_receipt.v1","timestamp":"2025-11-01T00:00:00Z"}\n')
        out_ndjson = Path(d) / "payouts.ndjson"
        out_csv = Path(d) / "payouts.csv"
        r = subprocess.run(
            [sys.executable, str(PAYOUTS_SCRIPT),
             "--input", str(src),
             "--period", "not-a-period",
             "--eur-total", "1000",
             "--out-ndjson", str(out_ndjson),
             "--out-csv", str(out_csv)],
            capture_output=True, text=True
        )
        assert r.returncode != 0, "Invalid period should exit non-zero"
        assert "FATAL" in r.stderr, "Should print FATAL error message"
        assert not out_ndjson.exists(), "No output NDJSON should be created on invalid period"
        assert not out_csv.exists(), "No output CSV should be created on invalid period"


def test_payouts_invalid_month_fatal():
    """Month out of range (e.g. 2025-13) must also exit non-zero."""
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "receipts.ndjson"
        src.write_text('{"schema":"royalty_receipt.v1"}\n')
        out_ndjson = Path(d) / "payouts.ndjson"
        out_csv = Path(d) / "payouts.csv"
        r = subprocess.run(
            [sys.executable, str(PAYOUTS_SCRIPT),
             "--input", str(src),
             "--period", "2025-13",
             "--eur-total", "1000",
             "--out-ndjson", str(out_ndjson),
             "--out-csv", str(out_csv)],
            capture_output=True, text=True
        )
        assert r.returncode != 0, "Month 13 should exit non-zero"
        assert "FATAL" in r.stderr


def test_verifier_rejects_trailing_entries_exact_boundary():
    """Trailing entries must be rejected even when count is an exact multiple of chunk.

    Regression for the bug where the trailing-entry check was inside the
    'if (count % chunk) != 0' branch and was silently skipped at exact boundaries.
    6 lines, chunk=3 → 2 complete blocks, no partial block → trailing entry must still fail.
    """
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "src.ndjson"
        chain = Path(d) / "chain.txt"
        # Exactly 6 lines with chunk=3 → 2 complete blocks, count % chunk == 0
        src.write_text("\n".join(json.dumps({"i": i}) for i in range(6)) + "\n")
        _build_valid_chain(src, chain, chunk=3)
        # Sanity: valid chain must pass
        r = _run_verifier(src, chain, chunk=3)
        assert r.returncode == 0, f"Valid exact-boundary chain failed:\n{r.stderr}"
        # Append spurious trailing entry
        with open(chain, "a") as cf:
            cf.write("99\t9999\t" + "a" * 64 + "\n")
        r = _run_verifier(src, chain, chunk=3)
        assert r.returncode != 0, "Verifier should reject trailing entries at exact block boundary"
        assert "extra trailing" in r.stderr
