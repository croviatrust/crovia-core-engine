"""
CROVIA — The Global Standard for AI Training Data Attribution
==============================================================

Cryptographic proofs, absence verification, and automatic royalty settlement.

CLI Commands:
    crovia oracle scan <model_id>   — Analyze model for trust gaps
    crovia oracle batch <file>      — Batch analysis (PRO)
    crovia oracle card <model_id>   — Generate Oracle Card
    crovia license status           — Show license status
    crovia license activate <key>   — Activate PRO license

Usage:
    pip install crovia
    crovia --help

License:
    Open: Free tier with daily limits
    PRO:  Unlimited access - https://croviatrust.com/pricing

Copyright (c) 2026 CroviaTrust
Apache License 2.0
"""

__version__ = "1.1.0"
__author__ = "CroviaTrust"
__email__ = "info@croviatrust.com"
__license__ = "Apache-2.0"

from crovia.auth import (
    get_license_status,
    check_rate_limit,
    LicenseStatus,
    activate_license,
    print_license_status,
)

from crovia.oracle import (
    analyze_model,
    generate_card,
    NECESSITY_CANON,
)

__all__ = [
    # Version
    "__version__",
    "__author__",
    
    # Auth
    "get_license_status",
    "check_rate_limit",
    "LicenseStatus",
    "activate_license",
    "print_license_status",
    
    # Oracle
    "analyze_model",
    "generate_card",
    "NECESSITY_CANON",
]
