from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

from .core.receipts import write_ndjson
from .core.validate import iter_validate_ndjson
from .sources.laion_adapter import iter_laion_spider_receipts


def cmd_from_laion(args: argparse.Namespace) -> int:
    meta_path = Path(args.metadata_path)
    out_path = Path(args.out)

    if not meta_path.exists():
        print(f"[FATAL] metadata file not found: {meta_path}", file=sys.stderr)
        return 2

    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(
        f"[SPIDER] Building spider_receipt.v1 from LAION metadata "
        f"(meta={meta_path}, sample={args.sample}, period={args.period}, out={out_path})"
    )

    receipts_iter = iter_laion_spider_receipts(
        metadata_path=meta_path,
        period=args.period,
        dataset_origin=args.dataset_origin,
        sample=args.sample,
    )

    with out_path.open("w", encoding="utf-8") as f:
        n = write_ndjson(f, receipts_iter)

    print(f"[SPIDER] Done. Wrote {n} receipts to {out_path}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    in_path = Path(args.input) if args.input != "-" else None

    if in_path is not None and not in_path.exists():
        print(f"[FATAL] input file not found: {in_path}", file=sys.stderr)
        return 2

    def _iter_lines() -> Iterable[str]:
        if in_path is None:
            for line in sys.stdin:
                yield line
        else:
            with in_path.open("r", encoding="utf-8") as f:
                for line in f:
                    yield line

    stats = iter_validate_ndjson(_iter_lines())
    print(
        f"[VALIDATE] total={stats['total']} ok={stats['ok']} failed={stats['failed']}",
        file=sys.stderr,
    )
    return 0 if stats["failed"] == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="crovia-spider",
        description="Crovia Spider — turn open training corpora into spider_receipt.v1 logs.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # from-laion
    laion = sub.add_parser(
        "from-laion",
        help="Generate spider_receipt.v1 NDJSON from a LAION-style metadata Parquet.",
    )
    laion.add_argument(
        "--metadata-path",
        required=True,
        help="Path to LAION metadata Parquet file (e.g. laion2B-en-meta.parquet).",
    )
    laion.add_argument(
        "--out",
        required=True,
        help="Output NDJSON path for spider_receipt.v1 logs.",
    )
    laion.add_argument(
        "--period",
        required=True,
        help="Crovia period (YYYY-MM) for these receipts (e.g. 2025-12).",
    )
    laion.add_argument(
        "--dataset-origin",
        default="LAION-5B",
        help='Human-readable dataset name (default: "LAION-5B").',
    )
    laion.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Optional number of rows to sample from metadata.",
    )
    laion.set_defaults(func=cmd_from_laion)

    # validate
    v = sub.add_parser(
        "validate",
        help="Validate spider_receipt.v1 NDJSON file.",
    )
    v.add_argument(
        "--input",
        default="-",
        help="Input NDJSON path, or '-' for stdin (default: '-').",
    )
    v.set_defaults(func=cmd_validate)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 1
    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
