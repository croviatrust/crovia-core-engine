import os, json
from typing import Dict, Iterator, TextIO
try:
    import orjson
    _dumps = lambda o: orjson.dumps(o).decode()
except Exception:
    _dumps = lambda o: json.dumps(o, separators=(",", ":"), ensure_ascii=False)

class NDJSONWriter:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o644)
        self.f: TextIO = os.fdopen(fd, "a", buffering=1, encoding="utf-8")
    def write(self, rec: Dict):
        self.f.write(_dumps(rec) + "\n"); self.f.flush(); os.fsync(self.f.fileno())
    def close(self): self.f.close()

def iter_ndjson_from_textio(f: TextIO) -> Iterator[Dict]:
    for lineno, line in enumerate(f, 1):
        s = line.strip()
        if not s: continue
        try: yield json.loads(s)
        except Exception as e: print(f"[WARN] NDJSON skip line {lineno}: {e}")

def stream_file(path: str, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk: break
            yield chunk
