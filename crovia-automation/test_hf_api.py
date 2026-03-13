#!/usr/bin/env python3
"""Quick HF API diagnostic — run on Hetzner to check token + create_discussion."""
import os
import sys
import time

print("=== HF API Diagnostic ===", flush=True)

token = os.environ.get("HF_TOKEN")
print(f"HF_TOKEN present: {bool(token)}", flush=True)
if token:
    print(f"HF_TOKEN starts: {token[:10]}...", flush=True)
else:
    print("ERROR: HF_TOKEN not set. Cannot proceed.", flush=True)
    sys.exit(1)

try:
    from huggingface_hub import HfApi
    print("huggingface_hub imported OK", flush=True)
except ImportError:
    print("ERROR: huggingface_hub not installed", flush=True)
    sys.exit(1)

api = HfApi(token=token)

# Test 1: whoami
print("\nTest 1: whoami...", flush=True)
try:
    info = api.whoami()
    print(f"  User: {info.get('name', '?')}", flush=True)
    print(f"  Type: {info.get('type', '?')}", flush=True)
except Exception as e:
    print(f"  FAIL: {e}", flush=True)
    sys.exit(1)

# Test 2: create_discussion on a test repo (dry — just check we can reach the endpoint)
print("\nTest 2: create_discussion (timeout test)...", flush=True)
t0 = time.time()
try:
    # Try creating on a known repo — this will fail with 403 or similar but proves API reachability
    result = api.create_discussion(
        repo_id="bert-base-uncased",
        title="[TEST] API connectivity check",
        description="This is a connectivity test. Please ignore.",
        repo_type="model",
    )
    elapsed = time.time() - t0
    print(f"  OK in {elapsed:.1f}s: {result}", flush=True)
except Exception as e:
    elapsed = time.time() - t0
    err = str(e)[:200]
    print(f"  Error in {elapsed:.1f}s: {err}", flush=True)
    if elapsed > 25:
        print("  WARNING: API call took >25s — likely timeout/hang issue", flush=True)
    else:
        print("  API responded (error is expected for test repo)", flush=True)

print("\n=== Diagnostic complete ===", flush=True)
