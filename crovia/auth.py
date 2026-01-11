#!/usr/bin/env python3
"""
crovia.auth — Authentication & Rate Limiting for Crovia CLI

Tiers:
    - OPEN: Free, limited (5 oracle scans/day, 10 payouts/day)
    - PRO: Licensed, unlimited access to all features

License validation:
    - Local file: ~/.crovia/license.key
    - Environment: CROVIA_PRO_KEY
    - API validation against croviatrust.com/api/v1/license/validate
"""

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ============================================================
# CONFIGURATION
# ============================================================

CROVIA_API_URL = "https://croviatrust.com/api/v1"
CONFIG_DIR = Path.home() / ".crovia"
LICENSE_FILE = CONFIG_DIR / "license.key"
USAGE_FILE = CONFIG_DIR / "usage.json"
DEVICE_FILE = CONFIG_DIR / "device.id"

# Rate limits for OPEN tier (per day)
OPEN_LIMITS = {
    "oracle_scan": 5,
    "payout_compute": 10,
    "bundle_create": 20,
    "absence_proof": 0,  # PRO only
    "zk_proof": 0,       # PRO only
    "settlement": 0,     # PRO only
}

# ============================================================
# DEVICE IDENTIFICATION
# ============================================================

def get_device_id() -> str:
    """Get or create a unique device identifier."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    if DEVICE_FILE.exists():
        return DEVICE_FILE.read_text().strip()
    
    # Generate device ID based on machine characteristics
    machine_info = f"{os.name}-{os.getenv('COMPUTERNAME', os.getenv('HOSTNAME', 'unknown'))}"
    device_id = hashlib.sha256(machine_info.encode()).hexdigest()[:16]
    device_id = f"CRV-DEV-{device_id.upper()}"
    
    DEVICE_FILE.write_text(device_id)
    return device_id


def get_machine_fingerprint() -> str:
    """Generate a fingerprint for rate limiting."""
    device_id = get_device_id()
    # Include date to reset daily
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return hashlib.sha256(f"{device_id}:{today}".encode()).hexdigest()[:12]


# ============================================================
# LICENSE MANAGEMENT
# ============================================================

class LicenseStatus:
    OPEN = "open"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    INVALID = "invalid"


def get_license_key() -> Optional[str]:
    """Get license key from environment or file."""
    # Check environment first
    key = os.getenv("CROVIA_PRO_KEY")
    if key:
        return key.strip()
    
    # Check local file
    if LICENSE_FILE.exists():
        return LICENSE_FILE.read_text().strip()
    
    return None


def validate_license_format(key: str) -> bool:
    """Validate license key format: CRV-PRO-XXXX-XXXX-XXXX"""
    if not key:
        return False
    parts = key.split("-")
    if len(parts) != 5:
        return False
    if parts[0] != "CRV":
        return False
    if parts[1] not in ("PRO", "ENT", "TRIAL"):
        return False
    return all(len(p) == 4 and p.isalnum() for p in parts[2:])


def validate_license_online(key: str) -> Tuple[bool, Dict[str, Any]]:
    """Validate license against Crovia API."""
    if not REQUESTS_AVAILABLE:
        # Offline mode - trust format validation
        return validate_license_format(key), {"offline": True}
    
    try:
        response = requests.post(
            f"{CROVIA_API_URL}/license/validate",
            json={
                "key": key,
                "device_id": get_device_id(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("valid", False), data
        else:
            # API unreachable - trust format validation
            return validate_license_format(key), {"offline": True, "status": response.status_code}
            
    except requests.RequestException:
        # Network error - trust format validation for PRO users
        return validate_license_format(key), {"offline": True, "error": "network"}


def get_license_status() -> Tuple[str, Dict[str, Any]]:
    """
    Determine current license status.
    
    Returns:
        Tuple of (status, details)
    """
    key = get_license_key()
    
    if not key:
        return LicenseStatus.OPEN, {"reason": "no_license"}
    
    if not validate_license_format(key):
        return LicenseStatus.INVALID, {"reason": "invalid_format", "key": key[:10] + "..."}
    
    # Try online validation
    valid, details = validate_license_online(key)
    
    if valid:
        if key.startswith("CRV-ENT-"):
            return LicenseStatus.ENTERPRISE, details
        return LicenseStatus.PRO, details
    
    return LicenseStatus.INVALID, details


def save_license(key: str) -> bool:
    """Save license key to local file."""
    if not validate_license_format(key):
        return False
    
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    LICENSE_FILE.write_text(key)
    return True


# ============================================================
# USAGE TRACKING & RATE LIMITING
# ============================================================

def load_usage() -> Dict[str, Any]:
    """Load usage data from file."""
    if not USAGE_FILE.exists():
        return {"date": None, "counts": {}}
    
    try:
        data = json.loads(USAGE_FILE.read_text())
        return data
    except (json.JSONDecodeError, IOError):
        return {"date": None, "counts": {}}


def save_usage(usage: Dict[str, Any]) -> None:
    """Save usage data to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(usage, indent=2))


def get_today_usage() -> Dict[str, int]:
    """Get today's usage counts, resetting if new day."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = load_usage()
    
    if usage.get("date") != today:
        # New day, reset counts
        usage = {"date": today, "counts": {}}
        save_usage(usage)
    
    return usage.get("counts", {})


def increment_usage(action: str) -> int:
    """Increment usage counter for an action. Returns new count."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = load_usage()
    
    if usage.get("date") != today:
        usage = {"date": today, "counts": {}}
    
    counts = usage.get("counts", {})
    counts[action] = counts.get(action, 0) + 1
    usage["counts"] = counts
    
    save_usage(usage)
    return counts[action]


def check_rate_limit(action: str) -> Tuple[bool, str]:
    """
    Check if action is allowed under current license.
    
    Returns:
        Tuple of (allowed, message)
    """
    status, _ = get_license_status()
    
    # PRO and Enterprise have no limits
    if status in (LicenseStatus.PRO, LicenseStatus.ENTERPRISE):
        return True, "PRO access"
    
    # Invalid license treated as OPEN
    if status == LicenseStatus.INVALID:
        status = LicenseStatus.OPEN
    
    # Check OPEN limits
    limit = OPEN_LIMITS.get(action, 0)
    
    if limit == 0:
        return False, f"'{action}' requires CROVIA PRO license. Get yours at https://croviatrust.com/pricing"
    
    current = get_today_usage().get(action, 0)
    
    if current >= limit:
        return False, f"Daily limit reached ({limit}/{limit}). Upgrade to PRO for unlimited access: https://croviatrust.com/pricing"
    
    return True, f"OK ({current + 1}/{limit} today)"


def require_pro(action: str):
    """Decorator to require PRO license for a function."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            allowed, message = check_rate_limit(action)
            if not allowed:
                print(f"\n❌ {message}\n")
                return 1
            
            # Increment usage for OPEN users
            status, _ = get_license_status()
            if status == LicenseStatus.OPEN:
                increment_usage(action)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================
# CLI HELPERS
# ============================================================

def print_license_status():
    """Print current license status."""
    status, details = get_license_status()
    
    print("\n╔══════════════════════════════════════════════════╗")
    print("║           CROVIA LICENSE STATUS                  ║")
    print("╠══════════════════════════════════════════════════╣")
    
    if status == LicenseStatus.ENTERPRISE:
        print("║  🏢 ENTERPRISE LICENSE                           ║")
        print("║  ✓ Unlimited access to all features             ║")
        print("║  ✓ Priority support                             ║")
        print("║  ✓ Custom integrations                          ║")
    elif status == LicenseStatus.PRO:
        print("║  💎 PRO LICENSE                                  ║")
        print("║  ✓ Unlimited Oracle scans                       ║")
        print("║  ✓ Absence proofs                               ║")
        print("║  ✓ ZK attestations                              ║")
        print("║  ✓ Royalty settlement                           ║")
    elif status == LicenseStatus.OPEN:
        print("║  🆓 OPEN (Free Tier)                             ║")
        print("║  • 5 Oracle scans/day                           ║")
        print("║  • 10 Payout computations/day                   ║")
        print("║  • Basic trust bundles                          ║")
        print("║  ✗ No absence proofs                            ║")
        print("║  ✗ No ZK attestations                           ║")
        print("║  ✗ No settlement                                ║")
        print("╠══════════════════════════════════════════════════╣")
        print("║  Upgrade: https://croviatrust.com/pricing       ║")
    else:
        print("║  ⚠️  INVALID LICENSE                             ║")
        print("║  Please check your license key                  ║")
    
    print("╚══════════════════════════════════════════════════╝")
    
    # Show today's usage for OPEN
    if status == LicenseStatus.OPEN:
        usage = get_today_usage()
        if usage:
            print("\n📊 Today's Usage:")
            for action, count in usage.items():
                limit = OPEN_LIMITS.get(action, "∞")
                print(f"   {action}: {count}/{limit}")
    
    print()


def activate_license(key: str) -> bool:
    """Activate a license key."""
    if not validate_license_format(key):
        print("❌ Invalid license format. Expected: CRV-PRO-XXXX-XXXX-XXXX")
        return False
    
    valid, details = validate_license_online(key)
    
    if valid:
        save_license(key)
        print("✅ License activated successfully!")
        print_license_status()
        return True
    else:
        print(f"❌ License validation failed: {details}")
        return False


# ============================================================
# TESTING
# ============================================================

if __name__ == "__main__":
    print("Crovia Auth Module Test")
    print("=" * 50)
    print(f"Device ID: {get_device_id()}")
    print(f"Fingerprint: {get_machine_fingerprint()}")
    print_license_status()
    
    # Test rate limiting
    print("\nRate Limit Tests:")
    for action in ["oracle_scan", "absence_proof", "settlement"]:
        allowed, msg = check_rate_limit(action)
        print(f"  {action}: {'✓' if allowed else '✗'} {msg}")
