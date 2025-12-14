"""
CroviaTrust – open-core evidence & payout engine for AI datasets.

This package exposes:

- crovia.cli           → CLI entrypoint (console script: `crovia`)
- crovia.semantic.*    → semantic/DSSE utilities (imported explicitly when needed)

We intentionally keep __init__ minimal to avoid circular imports when the
`crovia` console script imports `crovia.cli`.
"""

__version__ = "0.1.0"

# NOTE:
# Do NOT import subpackages (like `from . import semantic`) here.
# Submodules can still be imported explicitly when installed.
# but `crovia` itself remains lightweight and safe for CLI bootstrap.
