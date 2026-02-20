"""
Regression tests for proofs/hashchain_writer.py --chunk validation.

Bug: --chunk 0 (or negative) caused ZeroDivisionError at runtime because
count % args.chunk was executed without prior validation.

Fix: validate args.chunk <= 0 immediately after parse_args(), print
[FATAL] to stderr and exit with code 2.
"""

import subprocess
import sys
import pytest


SCRIPT = "proofs/hashchain_writer.py"


class TestChunkValidation:

    def _run(self, *extra_args):
        return subprocess.run(
            [sys.executable, SCRIPT, "--source", "nonexistent.ndjson"] + list(extra_args),
            capture_output=True,
            text=True,
            cwd=str(pytest.importorskip("pathlib").Path(__file__).parent.parent),
        )

    def test_chunk_zero_exits_nonzero(self):
        """--chunk 0 must exit with non-zero code (exit 2)."""
        result = self._run("--chunk", "0")
        assert result.returncode != 0, (
            f"Expected non-zero exit for --chunk 0, got {result.returncode}"
        )

    def test_chunk_zero_prints_fatal(self):
        """--chunk 0 must print [FATAL] to stderr."""
        result = self._run("--chunk", "0")
        assert "FATAL" in result.stderr, (
            f"Expected [FATAL] in stderr for --chunk 0, got: {result.stderr!r}"
        )

    def test_chunk_negative_exits_nonzero(self):
        """--chunk -1 must also exit with non-zero code."""
        result = self._run("--chunk", "-1")
        assert result.returncode != 0

    def test_chunk_negative_prints_fatal(self):
        """--chunk -1 must print [FATAL] to stderr."""
        result = self._run("--chunk", "-1")
        assert "FATAL" in result.stderr

    def test_chunk_exit_code_is_2(self):
        """Exit code for invalid --chunk must be exactly 2."""
        result = self._run("--chunk", "0")
        assert result.returncode == 2, (
            f"Expected exit code 2, got {result.returncode}"
        )
