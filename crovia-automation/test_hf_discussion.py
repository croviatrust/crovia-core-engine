#!/usr/bin/env python3
"""Quick test for HF Discussion API"""
import os
from huggingface_hub import HfApi

token = os.environ.get("HF_TOKEN")
print(f"Token present: {bool(token)}")

api = HfApi(token=token)

# Test with a simple model
repo_id = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
print(f"Testing discussion on: {repo_id}")

try:
    discussion = api.create_discussion(
        repo_id=repo_id,
        title="📋 Documentation Enhancement Suggestion",
        description="Test from CROVIA - please ignore and close.",
        repo_type="model"
    )
    print(f"SUCCESS! Discussion URL: https://huggingface.co/{repo_id}/discussions/{discussion.num}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
