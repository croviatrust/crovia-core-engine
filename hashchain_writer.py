#!/usr/bin/env python3
"""
CROVIA – Hash-chain writer

Builds a rolling SHA-256 hash-chain over an NDJSON file, in fixed-size chunks.

For each chunk of N lines (default: 10_000), it computes a block digest that
folds together:

    - the previous block digest (32 bytes, the “anchor”), and
    - the raw UTF-8 NDJSON lines in that block.

The initial anchor is 32 zero-bytes. A different convention can be adopted
by contract / policy, but MUST be kept consistent across writer and verifier.

The output is a tab-separated text file with one line per block:

    <block_index> <global_line_count> <hex_digest>

This file can later be verified with the matching hashchain verifier.
"""

import argparse
import hashlib
import os
import sys
from typing import Iterable


def iter_lines(path: str) -> Iterable[str]:
    """
    Stream non-empty lines from an NDJSON file, stripping trailing newlines.
    Keeps the original UTF-8 text (no JSON parsing here).
    """
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            s = line.rstrip("\n")
            if s:
                yield s


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CROVIA hash-chain writer over NDJSON (payouts, receipts, etc.)."
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Input NDJSON file to hash-chain.",
    )
    parser.add_argument(
        "--out",
        required=False,
        help=(
            "Output path for the hash-chain text file "
            "(default: proofs/hashchain_<basename>.txt)."
        ),
    )
    parser.add_argument(
        "--chunk",
        type=int,
        default=10000,
        help="Number of lines per block (default: 10000).",
    )
    args = parser.parse_args()

    if not os.path.exists(args.source):
        print(f"[FATAL] Source file not found: {args.source}", file=sys.stderr)
        sys.exit(2)

    base = os.path.basename(args.source)
    out_path = args.out or os.path.join("proofs", f"hashchain_{base}.txt")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    print(
        f"[HASHCHAIN] building hash-chain "
        f"(source={args.source}, chunk={args.chunk}, out={out_path})"
    )

    # Initial anchor (32 zero-bytes). This can be changed if a different anchor
    # convention is agreed in a contract / policy document, but MUST match the verifier.
    prev = b"\x00" * 32

    block_idx = 0       # 0-based index of the current block
    count = 0           # total number of processed lines
    h = hashlib.sha256()

    with open(out_path, "w", encoding="utf-8") as out:
        for s in iter_lines(args.source):
            # For each line, fold previous block digest + current line bytes.
            # NOTE: This is the convention used for the current CROVIA demo
            # and MUST remain in sync with verify_hashchain.py.
            h.update(prev)
            h.update(s.encode("utf-8"))
            count += 1

            # When we reach a full block, emit one line in the proofs file
            if (count % args.chunk) == 0:
                digest = h.hexdigest()
                out.write(f"{block_idx}\t{count}\t{digest}\n")
                prev = bytes.fromhex(digest)
                h = hashlib.sha256()
                block_idx += 1

        # Flush final partial block (if any)
        if count % args.chunk != 0:
            digest = h.hexdigest()
            out.write(f"{block_idx}\t{count}\t{digest}\n")

    total_blocks = block_idx + (1 if count % args.chunk != 0 else 0)
    print(
        f"[HASHCHAIN] wrote chain file: {out_path} "
        f"(blocks={total_blocks}, lines={count})"
    )


if __name__ == "__main__":
    main()
