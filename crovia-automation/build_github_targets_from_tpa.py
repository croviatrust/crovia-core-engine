#!/usr/bin/env python3
"""
build_github_targets_from_tpa.py
================================

Build GitHub outreach targets ONLY when a GitHub repo is explicitly linked
from a TPA-backed HuggingFace model card.

- Reads TPA-backed models from tpa_latest.json
- Fetches HF README.md and extracts github.com/owner/repo links
- Dedupe to 1 repo per org
- Excludes orgs already contacted (HF/GitHub logs)

Output: targets_github.json (list of dicts)
"""

import argparse
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Set

USER_AGENT = "CroviaTrust/1.0 (https://croviatrust.com)"
GITHUB_RE = re.compile(r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")


def _load_jsonl_orgs(path: str) -> Set[str]:
    orgs: Set[str] = set()
    if not path or not os.path.exists(path):
        return orgs
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tid = rec.get("repo_full_name") or rec.get("repo_id") or rec.get("target_id") or ""
                if not tid:
                    continue
                if ":" in tid:
                    tid = tid.split(":")[-1]
                if "/" in tid:
                    orgs.add(tid.split("/", 1)[0].lower())
    except Exception:
        return orgs
    return orgs


def _load_tpa_models(path: str) -> List[str]:
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    models = []
    for tpa in data.get("tpas", []):
        mid = tpa.get("model_id", "")
        if "/" in mid:
            models.append(mid)
    return models


def _fetch_readme(model_id: str) -> str:
    url = f"https://huggingface.co/{model_id}/raw/main/README.md"
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _extract_github_repos(text: str) -> List[str]:
    if not text:
        return []
    repos = []
    for match in GITHUB_RE.finditer(text):
        owner, repo = match.group(1), match.group(2)
        if owner and repo:
            repos.append(f"{owner}/{repo}")
    return list(dict.fromkeys(repos))


def build_targets(
    model_ids: List[str],
    limit: int,
    max_models: int,
    sleep_s: float,
    exclude_orgs: Set[str],
) -> List[Dict]:
    targets: List[Dict] = []
    seen_orgs: Set[str] = set()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    for idx, model_id in enumerate(model_ids[:max_models]):
        if len(targets) >= limit:
            break
        try:
            readme = _fetch_readme(model_id)
        except Exception:
            continue

        repos = _extract_github_repos(readme)
        if not repos:
            time.sleep(sleep_s)
            continue

        for repo_full in repos:
            owner = repo_full.split("/", 1)[0].lower()
            if owner in exclude_orgs or owner in seen_orgs:
                continue
            targets.append(
                {
                    "target_id": f"gh:{repo_full}",
                    "source": "github",
                    "tipo_target": "repo",
                    "name": repo_full,
                    "url": f"https://github.com/{repo_full}",
                    "popularity": {},
                    "metadata": {
                        "linked_model_id": model_id,
                        "link_source": "hf_readme",
                    },
                    "fetched_at": now,
                }
            )
            seen_orgs.add(owner)
            if len(targets) >= limit:
                break

        time.sleep(sleep_s)

    return targets


def main() -> None:
    parser = argparse.ArgumentParser(description="Build GitHub targets from TPA-backed HF cards")
    parser.add_argument("--tpa-file", default="/var/www/registry/data/tpa_latest.json")
    parser.add_argument("--output", default="targets_github.json")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--max-models", type=int, default=400)
    parser.add_argument("--sleep", type=float, default=0.6)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--exclude-jsonl", action="append", help="JSONL logs to exclude orgs from")
    args = parser.parse_args()

    exclude_orgs: Set[str] = {"huggingface"}
    exclude_paths = args.exclude_jsonl or []
    if not exclude_paths:
        exclude_paths = [
            os.path.join(os.path.dirname(__file__), "sent_discussions.jsonl"),
            os.path.join(os.path.dirname(__file__), "github_issues_sent.jsonl"),
        ]
    for path in exclude_paths:
        exclude_orgs.update(_load_jsonl_orgs(path))

    model_ids = _load_tpa_models(args.tpa_file)

    print("=" * 60)
    print("CROVIA GitHub Targets (TPA-linked)")
    print(f"TPA models: {len(model_ids)}")
    print(f"Exclude orgs: {len(exclude_orgs)}")
    print(f"Limit: {args.limit} | Max models: {args.max_models}")
    print("=" * 60)

    targets = build_targets(
        model_ids=model_ids,
        limit=args.limit,
        max_models=args.max_models,
        sleep_s=args.sleep,
        exclude_orgs=exclude_orgs,
    )

    print(f"Found {len(targets)} GitHub targets")

    if args.dry_run:
        print("[DRY RUN] No output written.")
        for t in targets[:10]:
            print(" -", t.get("name"))
        return

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(targets, f, indent=2, ensure_ascii=False)

    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
