import argparse
import json
import os
import fcntl
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "crovia-pro-engine"))

from croviapro.sonar_v2.family_cycles import select_family_cycle, load_processed_run_summaries

USER_AGENT = "Crovia-Research/1.0 (https://croviatrust.com; research@croviatrust.com)"
FALLBACK_FILES = [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.json",
    "merges.txt",
]


def _family_slug(family: str) -> str:
    return family.strip().lower().replace("/", "_").replace("-", "_").replace(" ", "_")


def _default_output_dir() -> Path:
    return Path(os.getenv("FAMILY_OUTPUT_DIR", os.getenv("SONAR_OUTPUT_DIR", "/opt/crovia/sonar_runs")))


def _default_tokenizer_cache_dir() -> Path:
    return Path(os.getenv("TOKENIZER_CACHE_DIR", "/opt/crovia/tokenizer_cache"))


def _default_status_file(family: str) -> Path:
    base = Path(os.getenv("FAMILY_STATUS_DIR", "/var/log/crovia"))
    return base / f"{_family_slug(family)}_cycle_state.json"


def _default_lock_file(family: str) -> Path:
    base = Path(os.getenv("FAMILY_LOCK_DIR", "/tmp"))
    return base / f"{_family_slug(family)}_sonar_cycle.lock"


def write_state(status_file: Path, family: str, stage: str, model_id: str | None = None, status: str = "running", **extra: object) -> None:
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "family": family,
        "stage": stage,
        "status": status,
        "model_id": model_id,
    }
    payload.update(extra)
    status_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = status_file.with_suffix(status_file.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(status_file)


def acquire_lock(lock_file: Path, status_file: Path, family: str):
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_file, "w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        write_state(status_file, family, "locked", status="skipped", message=f"Another {family} cycle run is already active")
        handle.close()
        return None
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def _tokenizer_ready(target_dir: Path) -> bool:
    if not target_dir.exists():
        return False
    file_count = len([p for p in target_dir.iterdir() if p.is_file()])
    if file_count < 2:
        return False
    has_tokenizer_json = (target_dir / "tokenizer.json").exists()
    has_vocab_pair = (target_dir / "vocab.json").exists() and (target_dir / "merges.txt").exists()
    return has_tokenizer_json or has_vocab_pair


def _download_file(url: str, dest: Path) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False
    dest.write_bytes(data)
    return True


def ensure_tokenizer(model_id: str, tokenizer_cache_dir: Path, status_file: Path, family: str) -> bool:
    target_dir = tokenizer_cache_dir / model_id.replace("/", "__")
    if _tokenizer_ready(target_dir):
        write_state(status_file, family, "tokenizer_ready", model_id=model_id, tokenizer_dir=str(target_dir), file_count=len([p for p in target_dir.iterdir() if p.is_file()]))
        return True

    target_dir.mkdir(parents=True, exist_ok=True)

    if not any(target_dir.iterdir()):
        write_state(status_file, family, "tokenizer_clone_start", model_id=model_id, tokenizer_dir=str(target_dir))
        clone_cmd = [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:limit=5m",
            f"https://huggingface.co/{model_id}",
            str(target_dir),
        ]
        clone_res = subprocess.run(clone_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if clone_res.returncode == 0 and _tokenizer_ready(target_dir):
            write_state(status_file, family, "tokenizer_clone_ok", model_id=model_id, tokenizer_dir=str(target_dir), file_count=len([p for p in target_dir.iterdir() if p.is_file()]))
            return True
        if clone_res.returncode != 0:
            write_state(status_file, family, "tokenizer_clone_failed", model_id=model_id, tokenizer_dir=str(target_dir), returncode=clone_res.returncode)
            shutil.rmtree(target_dir, ignore_errors=True)
            target_dir.mkdir(parents=True, exist_ok=True)

    base = f"https://huggingface.co/{model_id}/resolve/main"
    write_state(status_file, family, "tokenizer_fallback_download", model_id=model_id, tokenizer_dir=str(target_dir))
    for filename in FALLBACK_FILES:
        _download_file(f"{base}/{filename}", target_dir / filename)

    ready = _tokenizer_ready(target_dir)
    write_state(
        status_file,
        family,
        "tokenizer_ready" if ready else "tokenizer_unavailable",
        model_id=model_id,
        status="running" if ready else "failed",
        tokenizer_dir=str(target_dir),
        file_count=len([p for p in target_dir.iterdir() if p.is_file()]),
    )
    return ready


def next_model(family: str, output_dir: Path, include_deduped: bool, cycle_size: int) -> str | None:
    processed = load_processed_run_summaries(output_dir / "run_summaries.json")
    cycle = select_family_cycle(
        family=family,
        processed=processed,
        cycle_size=cycle_size,
        include_deduped=include_deduped,
        bridge_count=0,
    )
    if cycle["done"]:
        return None
    selected = cycle["selected"]
    return selected[0] if selected else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", required=True)
    parser.add_argument("--cycle-size", type=int, default=1)
    parser.add_argument("--exclude-deduped", action="store_true")
    parser.add_argument("--output-dir", default=str(_default_output_dir()))
    parser.add_argument("--status-file")
    parser.add_argument("--lock-file")
    parser.add_argument("--token")
    args = parser.parse_args(argv)

    family = args.family
    output_dir = Path(args.output_dir)
    tokenizer_cache_dir = _default_tokenizer_cache_dir()
    status_file = Path(args.status_file) if args.status_file else _default_status_file(family)
    lock_file = Path(args.lock_file) if args.lock_file else _default_lock_file(family)
    include_deduped = not args.exclude_deduped

    lock_handle = acquire_lock(lock_file, status_file, family)
    if lock_handle is None:
        return 0

    model_id = next_model(family, output_dir, include_deduped, args.cycle_size)
    if not model_id:
        print(f"[{family}_cycle] Family already complete")
        write_state(status_file, family, "family_complete", status="completed", message=f"No pending models for family {family}")
        return 0

    print(f"[{family}_cycle] Next model: {model_id}")
    write_state(status_file, family, "model_selected", model_id=model_id, output_dir=str(output_dir))
    if not ensure_tokenizer(model_id, tokenizer_cache_dir, status_file, family):
        print(f"[{family}_cycle] Tokenizer unavailable for {model_id}")
        write_state(status_file, family, "tokenizer_unavailable", model_id=model_id, status="failed")
        return 1

    cmd = [
        sys.executable,
        "-m",
        "croviapro.sonar_v2.run_batch",
        "--models",
        model_id,
        "--output-dir",
        str(output_dir),
    ]
    if args.token:
        cmd.extend(["--token", args.token])
    print(f"[{family}_cycle] Launching run_batch for {model_id}")
    write_state(status_file, family, "run_batch_started", model_id=model_id, command=cmd)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    last_log_line = ""
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip("\n")
        last_log_line = line
        print(line, flush=True)
        write_state(status_file, family, "run_batch_running", model_id=model_id, last_log_line=last_log_line)
    proc.wait()
    write_state(
        status_file,
        family,
        "completed" if proc.returncode == 0 else "failed",
        model_id=model_id,
        status="completed" if proc.returncode == 0 else "failed",
        returncode=proc.returncode,
        last_log_line=last_log_line,
    )
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
