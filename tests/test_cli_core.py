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

def _repo_env():
    """Return a copy of os.environ with REPO prepended to PYTHONPATH."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO) + (os.pathsep + existing if existing else "")
    return env


def run_cli(*args, cwd=None, env=None):
    """Run crovia CLI as subprocess, return CompletedProcess."""
    return subprocess.run(
        [sys.executable, "-m", "crovia.cli", *args],
        capture_output=True, text=True,
        cwd=str(cwd or REPO), env=env if env is not None else _repo_env()
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

def test_run_from_external_cwd():
    """crovia run launched from a directory outside the repo must still produce MANIFEST.json."""
    if not MINIMAL_RECEIPTS.exists():
        pytest.skip("Example receipts file not found")
    with tempfile.TemporaryDirectory() as external_dir:
        external_dir = Path(external_dir)
        receipts = external_dir / "receipts.ndjson"
        receipts.write_text(MINIMAL_RECEIPTS.read_text(encoding="utf-8"), encoding="utf-8")
        out_dir = external_dir / "crc1_out"
        r = subprocess.run(
            [
                sys.executable, "-m", "crovia.run",
                "--receipts", str(receipts),
                "--period", "2025-11",
                "--out", str(out_dir),
            ],
            capture_output=True, text=True,
            cwd=str(external_dir),   # NOT the repo root
            env=_repo_env(),
        )
        assert r.returncode == 0, f"crovia run failed from external cwd:\n{r.stdout}\n{r.stderr}"
        assert (out_dir / "MANIFEST.json").exists(), "MANIFEST.json not produced"
        manifest = json.loads((out_dir / "MANIFEST.json").read_text())
        assert manifest.get("contract") == "CRC-1"


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


def test_verifier_accepts_empty_source_and_chain():
    """Empty source + empty chain must be accepted as valid (consistent with writer)."""
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "src.ndjson"
        chain = Path(d) / "chain.txt"
        src.write_text("")   # empty source
        chain.write_text("") # empty chain
        r = _run_verifier(src, chain, chunk=3)
        assert r.returncode == 0, f"Empty source+chain should be OK:\n{r.stderr}"
        assert "OK" in r.stdout


def test_verifier_rejects_empty_source_with_nonempty_chain():
    """Empty source + non-empty chain must be rejected."""
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "src.ndjson"
        chain = Path(d) / "chain.txt"
        src.write_text("")
        chain.write_text("0\t1\t" + "a" * 64 + "\n")
        r = _run_verifier(src, chain, chunk=3)
        assert r.returncode != 0, "Empty source with non-empty chain should fail"
        assert "FATAL" in r.stderr


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
# 6. trust_bundle_validator — double-count regression
# ---------------------------------------------------------------------------

TRUST_VALIDATOR_SCRIPT = REPO / "core" / "trust_bundle_validator.py"


def test_trust_bundle_validator_single_error_per_artifact():
    """Artifact with both size and hash mismatch must count as 1 error, not 2."""
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        # Create a real artifact file
        artifact = d / "receipts.ndjson"
        artifact.write_text('{"schema":"royalty_receipt.v1"}\n')
        real_size = artifact.stat().st_size
        # Build bundle with wrong bytes AND wrong sha256
        bundle = {
            "schema": "crovia.trust_bundle.v1",
            "period": "2025-11",
            "artifacts": {
                "receipts": {
                    "path": "receipts.ndjson",
                    "bytes": real_size + 999,           # wrong size
                    "sha256": "a" * 64,                 # wrong hash
                }
            }
        }
        bundle_path = d / "trust_bundle.json"
        bundle_path.write_text(json.dumps(bundle))
        r = subprocess.run(
            [sys.executable, str(TRUST_VALIDATOR_SCRIPT),
             "--bundle", str(bundle_path), "--base-dir", str(d)],
            capture_output=True, text=True
        )
        assert r.returncode != 0, "Bundle with mismatch should fail"
        assert "1 error(s)" in r.stdout, f"Expected '1 error(s)', got:\n{r.stdout}"
        assert "SIZE_MISMATCH" in r.stdout
        assert "HASH_MISMATCH" in r.stdout


# ---------------------------------------------------------------------------
# 7. NDJSONWriter — filename-only path regression
# ---------------------------------------------------------------------------

def test_ndjson_writer_filename_only():
    """NDJSONWriter must not crash when path has no directory component (e.g. 'events.ndjson')."""
    import sys
    sys.path.insert(0, str(REPO / "core"))
    from ndjson_io import NDJSONWriter
    with tempfile.TemporaryDirectory() as d:
        orig_dir = os.getcwd()
        try:
            os.chdir(d)
            w = NDJSONWriter("events.ndjson")
            w.write({"schema": "test", "value": 42})
            w.close()
            content = (Path(d) / "events.ndjson").read_text()
            rec = json.loads(content.strip())
            assert rec["value"] == 42
        finally:
            os.chdir(orig_dir)


# ---------------------------------------------------------------------------
# 7. hashchain writer/verifier — invalid --chunk regression
# ---------------------------------------------------------------------------

WRITER_SCRIPT = REPO / "core" / "hashchain_writer.py"
VERIFIER_SCRIPT = REPO / "core" / "verify_hashchain.py"


def test_hashchain_writer_rejects_chunk_zero():
    """hashchain_writer --chunk 0 must exit non-zero with FATAL message."""
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "src.ndjson"
        src.write_text('{"i":0}\n')
        r = subprocess.run(
            [sys.executable, str(WRITER_SCRIPT), "--source", str(src), "--chunk", "0"],
            capture_output=True, text=True
        )
        assert r.returncode != 0, "chunk=0 should exit non-zero"
        assert "FATAL" in r.stderr


def test_hashchain_verifier_rejects_negative_chunk():
    """verify_hashchain --chunk -5 must exit non-zero with FATAL message."""
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "src.ndjson"
        chain = Path(d) / "chain.txt"
        src.write_text('{"i":0}\n')
        chain.write_text("0\t1\t" + "a" * 64 + "\n")
        r = subprocess.run(
            [sys.executable, str(VERIFIER_SCRIPT),
             "--source", str(src), "--chain", str(chain), "--chunk", "-5"],
            capture_output=True, text=True
        )
        assert r.returncode != 0, "chunk=-5 should exit non-zero"
        assert "FATAL" in r.stderr


# ---------------------------------------------------------------------------
# 7. crovia.verify — path traversal regression
# ---------------------------------------------------------------------------

def test_verify_rejects_artifact_path_traversal():
    """MANIFEST with ../outside path must be rejected by crovia.verify."""
    import importlib, io
    with tempfile.TemporaryDirectory() as d:
        bundle = Path(d) / "bundle"
        bundle.mkdir()
        outside = Path(d) / "outside.ndjson"
        outside.write_text('{"schema":"royalty_receipt.v1"}\n')

        # Build a minimal valid MANIFEST but with traversal in receipts
        manifest = {
            "schema": "crovia.manifest.v1",
            "contract": "CRC-1",
            "artifacts": {
                "receipts": "../outside.ndjson",   # traversal
                "validate_report": "validate_report.md",
                "hashchain": "hashchain.txt",
                "trust_bundle": "trust_bundle.json",
            }
        }
        (bundle / "MANIFEST.json").write_text(json.dumps(manifest))
        # Create the other artifacts inside bundle so they don't trigger missing-file first
        (bundle / "validate_report.md").write_text("ok")
        (bundle / "hashchain.txt").write_text("0\t1\t" + "a" * 64 + "\n")
        (bundle / "trust_bundle.json").write_text("{}")

        r = subprocess.run(
            [sys.executable, "-m", "crovia.verify", str(bundle)],
            capture_output=True, text=True, cwd=str(REPO)
        )
        assert r.returncode != 0, "crovia.verify must reject path traversal in artifacts"
        assert "traversal" in r.stdout.lower() or "traversal" in r.stderr.lower() or "escapes" in r.stdout.lower()


# ---------------------------------------------------------------------------
# 7. payouts_from_royalties — invalid period regression
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


def test_payouts_period_requires_zero_padded_month_fatal():
    """--period 2025-1 (non-zero-padded) must exit non-zero with FATAL message."""
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "receipts.ndjson"
        src.write_text('{"schema":"royalty_receipt.v1","timestamp":"2025-01-01T00:00:00Z"}\n')
        r = subprocess.run(
            [sys.executable, str(PAYOUTS_SCRIPT),
             "--input", str(src),
             "--period", "2025-1",
             "--eur-total", "1000",
             "--out-csv", str(Path(d) / "out.csv"),
             "--out-ndjson", str(Path(d) / "out.ndjson"),
             "--out-assumptions", str(Path(d) / "assumptions.json"),
             ],
            capture_output=True, text=True
        )
        assert r.returncode != 0, "2025-1 should be rejected"
        assert "FATAL" in r.stderr


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
