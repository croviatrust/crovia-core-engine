#!/usr/bin/env python3
"""
build_github_targets.py
=======================

Build a GitHub-only outreach target list with strict safety controls.
- Uses GitHub Search API (public or token-based)
- Dedupes to 1 repo per org by default
- Excludes orgs already contacted on HuggingFace/GitHub

Output: targets_github.json (list of dicts)
"""

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Set

GITHUB_API = "https://api.github.com/search/repositories"
USER_AGENT = "CroviaTrust/1.0 (https://croviatrust.com)"

DEFAULT_QUERIES = [
    "topic:machine-learning topic:model stars:>1000",
    "topic:deep-learning topic:pretrained-models stars:>500",
    "topic:transformer topic:nlp stars:>500",
    "topic:computer-vision topic:model stars:>500",
    "topic:large-language-model stars:>500",
    "topic:diffusion-model stars:>200",
]


def _load_jsonl_targets(path: str) -> Set[str]:
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
                tid = (
                    rec.get("repo_full_name")
                    or rec.get("repo_id")
                    or rec.get("target_id")
                    or ""
                )
                if not tid:
                    continue
                if ":" in tid:
                    tid = tid.split(":")[-1]
                if "/" in tid:
                    orgs.add(tid.split("/", 1)[0])
    except Exception:
        return orgs

    return orgs


def _fetch_repos(query: str, per_page: int, page: int, token: str = "") -> Dict:
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
        "page": page,
    }
    url = f"{GITHUB_API}?{urllib.parse.urlencode(params)}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data


def _load_tpa_orgs(path: str) -> Set[str]:
    orgs: Set[str] = set()
    if not path or not os.path.exists(path):
        return orgs
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return orgs
    for tpa in data.get("tpas", []):
        mid = tpa.get("model_id", "")
        if "/" in mid:
            orgs.add(mid.split("/", 1)[0])
    return orgs


def build_targets(
    queries: List[str],
    limit: int,
    per_page: int,
    max_pages: int,
    exclude_orgs: Set[str],
    allowed_orgs: Set[str],
    min_stars: int,
    token: str,
) -> List[Dict]:
    targets: List[Dict] = []
    seen_orgs: Set[str] = set()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    for query in queries:
        if len(targets) >= limit:
            break
        for page in range(1, max_pages + 1):
            if len(targets) >= limit:
                break
            try:
                data = _fetch_repos(query, per_page, page, token)
            except Exception as exc:
                print(f"GitHub fetch error ({query} p{page}): {exc}")
                break

            items = data.get("items", [])
            if not items:
                break

            for item in items:
                full_name = item.get("full_name", "")
                if not full_name or "/" not in full_name:
                    continue
                org = full_name.split("/", 1)[0]
                if allowed_orgs and org not in allowed_orgs:
                    continue
                if org in exclude_orgs or org in seen_orgs:
                    continue
                stars = int(item.get("stargazers_count", 0))
                if stars < min_stars:
                    continue

                targets.append(
                    {
                        "target_id": f"gh:{full_name}",
                        "source": "github",
                        "tipo_target": "repo",
                        "name": full_name,
                        "url": item.get("html_url", ""),
                        "popularity": {
                            "stars": stars,
                            "forks": int(item.get("forks_count", 0)),
                        },
                        "metadata": {
                            "language": item.get("language"),
                            "topics": (item.get("topics") or [])[:8],
                            "query": query,
                        },
                        "fetched_at": now,
                    }
                )
                seen_orgs.add(org)

                if len(targets) >= limit:
                    break

            time.sleep(1.2)

    return targets


def main():
    parser = argparse.ArgumentParser(description="Build GitHub outreach target list")
    parser.add_argument("--output", default="targets_github.json", help="Output JSON path")
    parser.add_argument("--limit", type=int, default=30, help="Max targets")
    parser.add_argument("--per-page", type=int, default=30, help="Results per query page")
    parser.add_argument("--max-pages", type=int, default=2, help="Max pages per query")
    parser.add_argument("--min-stars", type=int, default=500, help="Minimum stars")
    parser.add_argument("--dry-run", action="store_true", help="Do not write output")
    parser.add_argument("--query", action="append", help="Extra GitHub search query")
    parser.add_argument("--exclude-jsonl", action="append", help="JSONL logs to exclude orgs from")
    parser.add_argument("--tpa-only", action="store_true", help="Limit to orgs seen in tpa_latest.json")
    parser.add_argument("--tpa-file", default="/var/www/registry/data/tpa_latest.json", help="TPA latest JSON path")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    queries = DEFAULT_QUERIES + (args.query or [])

    exclude_orgs: Set[str] = set()
    exclude_paths = args.exclude_jsonl or []
    if not exclude_paths:
        exclude_paths = [
            os.path.join(os.path.dirname(__file__), "sent_discussions.jsonl"),
            os.path.join(os.path.dirname(__file__), "github_issues_sent.jsonl"),
        ]
    for path in exclude_paths:
        exclude_orgs.update(_load_jsonl_targets(path))

    allowed_orgs: Set[str] = set()
    if args.tpa_only:
        allowed_orgs = _load_tpa_orgs(args.tpa_file)

    print("=" * 60)
    print("CROVIA GitHub Targets Builder")
    print(f"Queries: {len(queries)}")
    print(f"Exclude orgs: {len(exclude_orgs)}")
    if args.tpa_only:
        print(f"TPA org filter: {len(allowed_orgs)}")
    print(f"Limit: {args.limit} | Min stars: {args.min_stars}")
    print("=" * 60)

    targets = build_targets(
        queries=queries,
        limit=args.limit,
        per_page=args.per_page,
        max_pages=args.max_pages,
        exclude_orgs=exclude_orgs,
        allowed_orgs=allowed_orgs,
        min_stars=args.min_stars,
        token=token,
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
