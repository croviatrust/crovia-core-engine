#!/usr/bin/env python3
"""Quick test for GitHub token"""
import os
import json
import urllib.request
import urllib.error

token = os.environ.get("GITHUB_TOKEN")
print(f"Token present: {bool(token)}")

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "CroviaTrust/1.0",
    "X-GitHub-Api-Version": "2022-11-28"
}

# Test on croviatrust repo
repo = "croviatrust/crovia-wedge"
print(f"Testing issue creation on: {repo}")

req = urllib.request.Request(
    f"https://api.github.com/repos/{repo}/issues",
    data=json.dumps({
        "title": "📋 Test - CROVIA Enhancement System",
        "body": "This is a test issue from the CROVIA Enhancement System.\n\nPlease close this issue.",
        "labels": ["test"]
    }).encode("utf-8"),
    headers=headers,
    method="POST"
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        print(f"SUCCESS! Issue #{data['number']} created")
        print(f"URL: {data['html_url']}")
except urllib.error.HTTPError as e:
    print(f"ERROR {e.code}: {e.read().decode()[:300]}")
except Exception as e:
    print(f"ERROR: {e}")
