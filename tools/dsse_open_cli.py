#!/usr/bin/env python3
"""
CLI for DSSE (Open edition)

Usage:

    python tools/dsse_open_cli.py analyze data.txt --out report.json

Input can be:
- a .txt file (one sample per line)
- a .json file with a list of strings: ["sample1", "sample2", ...]
"""

import argparse
import json
from crovia.semantic.dsse_open import DSSEOpenEngine


def load_samples(path: str):
    if path.endswith(".txt"):
        with open(path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    if path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [str(x) for x in data]
            raise ValueError("JSON must be a list of strings")
    raise ValueError("Unsupported format. Use .txt or .json")


def main():
    parser = argparse.ArgumentParser(description="DSSE Open-Core CLI")
    parser.add_argument("command", choices=["analyze"])
    parser.add_argument("input_path")
    parser.add_argument("--out", default="dsse_report.json")
    args = parser.parse_args()

    if args.command != "analyze":
        raise SystemExit("Only 'analyze' is supported in this version")

    samples = load_samples(args.input_path)
    engine = DSSEOpenEngine()
    result = engine.analyze(samples)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)

    print(f"[DSSE] Report written to {args.out}")


if __name__ == "__main__":
    main()
