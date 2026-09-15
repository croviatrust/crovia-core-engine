#!/usr/bin/env python3
"""Build a deterministic, closed Crovia public-site release directory."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "release-manifest.json"


def safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe release path: {value!r}")
    return path


def build(output: Path) -> dict:
    release = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if release.get("schema") != "crovia.public-release.v1":
        raise ValueError("unsupported release manifest schema")

    output = output.resolve()
    if output == ROOT.resolve() or ROOT.resolve() in output.parents:
        raise ValueError("output must not contain or replace the source tree")
    if output.exists():
        if output.is_symlink():
            raise ValueError("output directory must not be a symlink")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    files = []
    seen = set()
    for entry in release["files"]:
        source_rel = safe_relative(entry["source"])
        target_rel = safe_relative(entry["target"])
        if str(target_rel) in seen:
            raise ValueError(f"duplicate release target: {target_rel}")
        seen.add(str(target_rel))

        source = ROOT.joinpath(*source_rel.parts)
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"source must be a regular non-symlink file: {source_rel}")
        data = source.read_bytes()

        target = output.joinpath(*target_rel.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(int(entry["mode"], 8))
        files.append({
            "target": str(target_rel),
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "mode": entry["mode"],
            "content_type": entry["content_type"],
        })

    artifact = {
        "schema": "crovia.public-release-artifact.v1",
        "release": release["release"],
        "target_root": release["target_root"],
        "files": files,
    }
    encoded = (json.dumps(artifact, indent=2, sort_keys=True) + "\n").encode()
    (output / "SHA256SUMS.json").write_bytes(encoded)
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
