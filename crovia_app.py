"""
CROVIA Open Dashboard (Open Core)



This module provides:

- visualization

- sandbox previews

- documentation rendering



It does NOT contain:

- attribution algorithms

- payout logic

- trust scoring engines

"""

from __future__ import annotations
from datetime import datetime, timezone
# Copyright 2025  Tarik En Nakhai
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from pathlib import Path
import csv
import re
import json
from datetime import datetime
import sys
import subprocess
import uuid

import markdown
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


# ---------------------------------------------------------------------------
# Paths & globals
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHARTS_DIR = BASE_DIR / "charts"
PROOFS_DIR = BASE_DIR / "proofs"
SANDBOX_DIR = BASE_DIR / "sandbox_runs"
STATS_FILE = BASE_DIR / "sandbox_stats.json"
MAX_SANDBOX_BYTES = 2_000_000  # ~2 MB sandbox limit


app = FastAPI(title="CroviaTrust Dashboard")

# Serve everything under /opt/crovia as /static/...
app.mount("/static", StaticFiles(directory=str(BASE_DIR)), name="static")

# Serve payout charts (Top-10 / cumulative) as static files
app.mount(
    "/charts",
    StaticFiles(directory=str(CHARTS_DIR)),
    name="charts",
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ---------------------------------------------------------------------------
# Helpers: periods, markdown, stats, subprocess
# ---------------------------------------------------------------------------

def detect_latest_period() -> str | None:
    """Trova l'ultimo periodo disponibile dai file payouts_YYYY-MM.csv."""
    periods: set[str] = set()
    if not DATA_DIR.exists():
        return None

    for path in DATA_DIR.glob("payouts_*.csv"):
        m = re.match(r"payouts_(\d{4}-\d{2})\.csv", path.name)
        if m:
            periods.add(m.group(1))

    if not periods:
        return None
    return sorted(periods)[-1]


def load_trust_summary_html() -> str | None:
    """
    Legge trust_summary.md e prende solo la parte 'di testo'
    (prima della tabella), rendendola in HTML.
    """
    path = BASE_DIR / "trust_summary.md"
    if not path.exists():
        return None

    raw = path.read_text(encoding="utf-8")
    header_lines: list[str] = []

    for line in raw.splitlines():
        # La tabella solitamente inizia con 'rank'
        if line.strip().startswith("rank"):
            break
        header_lines.append(line)

    text = "\n".join(header_lines).strip()
    if not text:
        return None

    return markdown.markdown(text)


def load_trust_table(max_rows: int = 10):
    """
    Legge data/trust_providers.csv e restituisce (header, rows)
    senza assumere i nomi delle colonne.
    """
    path = DATA_DIR / "trust_providers.csv"
    if not path.exists():
        return None, None

    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return None, None

        rows: list[list[str]] = []
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            rows.append(row)

    return header, rows


def load_payout_readme_html(period: str) -> str | None:
    """
    Legge README_PAYOUT_<period>.md e lo rende in HTML.
    """
    path = BASE_DIR / f"README_PAYOUT_{period}.md"
    if not path.exists():
        return None

    raw = path.read_text(encoding="utf-8")
    return markdown.markdown(raw)


def run_cmd(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """
    Esegue uno script Python usando lo stesso interprete del servizio.
    Ritorna (returncode, stdout, stderr).
    """
    if cwd is None:
        cwd = BASE_DIR

    proc = subprocess.Popen(
        [sys.executable, *args],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate()
    return proc.returncode, out, err


def load_stats():
    """Carica le statistiche sandbox dal JSON (o valori di default)."""
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text())
        except Exception:
            # se corrotto, reset
            pass

    return {
        "sandbox_runs": 0,
        "sandbox_receipts": 0,
        "last_update": None,
    }


def save_stats(stats: dict) -> None:
    """Salva le statistiche sandbox nel file JSON."""
    stats["last_update"] = datetime.now(timezone.utc).isoformat() + "Z"
    STATS_FILE.write_text(json.dumps(stats, indent=2))


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", response_class=PlainTextResponse)
async def health():
    return "OK"


# ---------------------------------------------------------------------------
# Dashboard principale "/"
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, period: str | None = None):
    """
    Dashboard principale.
    Se non viene passato ?period=YYYY-MM, prende l'ultimo disponibile.
    """
    if period is None:
        period = detect_latest_period()

    if period is None:
        raise HTTPException(
            status_code=500,
            detail="Nessun periodo trovato. Esegui prima run_period.py.",
        )

    payout_csv = DATA_DIR / f"payouts_{period}.csv"
    if not payout_csv.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File payouts_{period}.csv non trovato.",
        )

    trust_header, trust_rows = load_trust_table(max_rows=10)
    trust_summary_html = load_trust_summary_html()
    payout_readme_html = load_payout_readme_html(period)

    charts = {
        "top10": f"/charts/payout_top10_{period}.png",
        "cumulative": f"/charts/payout_cumulative_{period}.png",
    }

    bundle_name = f"trust_bundle_{period}.json"
    bundle_path = BASE_DIR / bundle_name
    bundle_exists = bundle_path.exists()

    stats = load_stats()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "period": period,
            "trust_summary_html": trust_summary_html,
            "trust_header": trust_header,
            "trust_rows": trust_rows,
            "payout_readme_html": payout_readme_html,
            "charts": charts,
            "bundle_exists": bundle_exists,
            "bundle_name": bundle_name,
            "stats": stats,
        },
    )


# ---------------------------------------------------------------------------
# Download JSON trust bundle
# ---------------------------------------------------------------------------

@app.get("/bundle/{period}", response_class=FileResponse)
async def download_bundle(period: str):
    bundle_path = BASE_DIR / f"trust_bundle_{period}.json"
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="Trust bundle not found.")
    return FileResponse(
        path=str(bundle_path),
        filename=bundle_path.name,
        media_type="application/json",
    )


# ---------------------------------------------------------------------------
# CROVIA sandbox: NDJSON upload + payout preview + usage stats
# ---------------------------------------------------------------------------

@app.get("/sandbox", response_class=HTMLResponse)
async def sandbox_get(request: Request):
    """Render empty sandbox form with current stats."""
    stats = load_stats()
    return templates.TemplateResponse(
        "sandbox.html",
        {
            "request": request,
            "result": None,
            "error": None,
            "stats": stats,
        },
    )


@app.post("/sandbox", response_class=HTMLResponse)
async def sandbox_post(
    request: Request,
    eur_total: float = Form(1000000.0),
    receipts_file: UploadFile = File(...),
):
    """Handle sandbox upload + run QA + payouts preview."""
    stats = load_stats()

    if not receipts_file.filename:
        error_msg = "No file uploaded."
        return templates.TemplateResponse(
            "sandbox.html",
            {"request": request, "result": None, "error": error_msg, "stats": stats},
        )

    data = await receipts_file.read()

    if not data:
        error_msg = "Empty file. Please upload at least one JSONL line."
        return templates.TemplateResponse(
            "sandbox.html",
            {"request": request, "result": None, "error": error_msg, "stats": stats},
        )

    if len(data) > MAX_SANDBOX_BYTES:
        error_msg = f"File too large. Sandbox limit is {MAX_SANDBOX_BYTES} bytes."
        return templates.TemplateResponse(
            "sandbox.html",
            {"request": request, "result": None, "error": error_msg, "stats": stats},
        )

    # Count receipts (roughly: number of lines)
    n_receipts = data.count(b"\n")
    if data and not data.endswith(b"\n"):
        n_receipts += 1

    # Ensure sandbox dir exists and save uploaded file
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    receipts_path = SANDBOX_DIR / f"sandbox_receipts_{run_id}.ndjson"
    receipts_path.write_bytes(data)

    # 1) QA step
    qa_code, qa_out, qa_err = run_cmd(
        [str(BASE_DIR / "qa_receipts.py"), str(receipts_path)]
    )

    if qa_code != 0:
        error_msg = (
            "QA failed. Check format and required fields.\n\n"
            + qa_out
            + "\n"
            + qa_err
        )
        return templates.TemplateResponse(
            "sandbox.html",
            {"request": request, "result": None, "error": error_msg, "stats": stats},
        )

    # 2) Payouts preview
    payouts_csv = SANDBOX_DIR / f"sandbox_payouts_{run_id}.csv"
    payouts_ndjson = SANDBOX_DIR / f"sandbox_payouts_{run_id}.ndjson"
    assumptions_json = SANDBOX_DIR / f"sandbox_assumptions_{run_id}.json"
    log_path = SANDBOX_DIR / f"sandbox_payouts_{run_id}.log"

    pay_args = [
        str(BASE_DIR / "payouts_from_royalties.py"),
        "--input",
        str(receipts_path),
        "--period",
        "sandbox",
        "--eur-total",
        str(eur_total),
        "--out-ndjson",
        str(payouts_ndjson),
        "--out-csv",
        str(payouts_csv),
        "--out-assumptions",
        str(assumptions_json),
        "--out-log",
        str(log_path),
    ]

    pay_code, pay_out, pay_err = run_cmd(pay_args)

    if pay_code != 0:
        error_msg = "Payouts computation failed.\n\n" + pay_out + "\n" + pay_err
        return templates.TemplateResponse(
            "sandbox.html",
            {"request": request, "result": None, "error": error_msg, "stats": stats},
        )

    # Read a small CSV preview (first 10 rows)
    preview_rows = []
    try:
        with payouts_csv.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                preview_rows.append(row)
                if len(preview_rows) >= 10:
                    break
    except Exception as exc:
        error_msg = f"Payouts computed but preview failed: {exc}"
        return templates.TemplateResponse(
            "sandbox.html",
            {"request": request, "result": None, "error": error_msg, "stats": stats},
        )

    # Update stats
    stats["sandbox_runs"] = stats.get("sandbox_runs", 0) + 1
    stats["sandbox_receipts"] = stats.get("sandbox_receipts", 0) + n_receipts
    save_stats(stats)

    result = {
        "run_id": run_id,
        "eur_total": eur_total,
        "n_receipts": n_receipts,
        "qa_out": qa_out,
        "payout_preview": preview_rows,
    }

    return templates.TemplateResponse(
        "sandbox.html",
        {"request": request, "result": result, "error": None, "stats": stats},
    )

# ---------------------------------------------------------------------------
# Public overview page: /about_legacy (markdown-based)
# ---------------------------------------------------------------------------

@app.get("/about", response_class=HTMLResponse)
@app.get("/about_legacy", response_class=HTMLResponse)
async def about_legacy(request: Request) -> HTMLResponse:

    """
    Public overview: what CROVIA is and how to use it.
    Renders docs/CROVIA_OVERVIEW.md as HTML.
    """
    md_path = BASE_DIR / "docs" / "CROVIA_OVERVIEW.md"
    if md_path.exists():
        raw = md_path.read_text(encoding="utf-8")
        body_html = markdown.markdown(raw)
    else:
        body_html = "<p>Overview document not found.</p>"

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CROVIA – Overview</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
  body {{
    margin: 0;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background:#020617;
    color:#e5e7eb;
  }}
    .main {{
      max-width: 920px;
      margin: 32px auto 64px auto;
      padding: 0 16px;
  }}

  .card {{
    background:#020617;
    border-radius:16px;
    border:1px solid #1e293b;
    padding:24px;
    box-shadow: 0 20px 30px rgba(15,23,42,0.6);
  }}
  nav {{
    margin-bottom:24px;
    display:flex;
    justify-content:space-between;
    align-items:center;
  }}
  nav a {{
    color:#9ca3af;
    text-decoration:none;
    font-size:14px;
    margin-left:16px;
  }}
  nav a:hover {{
    color:#e5e7eb;
  }}
  </style>
</head>
<body>
  <div class="main">
    <nav>
      <div>
        <span style="padding:4px 10px;border-radius:999px;border:1px solid #22c55e66;background:#22c55e1a;color:#22c55e;font-size:12px;">
          CROVIA
        </span>
      </div>
      <div>
        <a href="/">Dashboard</a>
        <a href="/about">About</a>
      </div>
    </nav>
    <div class="card">
      {body_html}
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# About CROVIA (static cards) – /about
# ---------------------------------------------------------------------------

@app.get("/about_cards", response_class=HTMLResponse)
async def about_cards():
    """
    Static about page for CROVIA.
    """
    html =""" <!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>About CROVIA</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
  body {
    margin:0;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background:#050815;
    color:#e5e7eb;
  }
  .main {
    max-width:960px;
    margin:32px auto 64px auto;
    padding:0 16px;
  }
  nav {
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-bottom:24px;
  }
  .badge {
    display:inline-block;
    padding:4px 10px;
    border-radius:999px;
    font-size:12px;
    letter-spacing:0.12em;
    text-transform:uppercase;
    background:#111827;
    border:1px solid #1f2937;
    color:#9ca3af;
  }
  nav a {
    margin-left:16px;
    font-size:14px;
    color:#e5e7eb;
    text-decoration:none;
  }
  nav a:hover {
    color:#ffffff;
  }
  .card {
    background:#0b1020;
    border-radius:18px;
    padding:24px 28px;
    border:1px solid #111827;
    box-shadow:0 18px 45px rgba(0,0,0,0.55);
    margin-bottom:24px;
  }
  .card h1, .card h2 {
    color:#f9fafb;
    margin-top:0;
  }
  .card p {
    line-height:1.6;
  }
  .card ul {
    padding-left:20px;
  }
  .small {
    font-size:14px;
    color:#9ca3af;
  }
  </style>
</head>
<body>
  <div class="main">
    <nav>
      <div><span class="badge">CROVIA</span></div>
      <div>
        <a href="/">Dashboard</a>
        <a href="/sandbox">Sandbox</a>
        <a href="/about">About</a>
        <a href="/standard">Standard</a>
      </div>
    </nav>

    <div class="card">
      <h1>What is CROVIA?</h1>
      <p>
        CROVIA is an engine that turns AI training attribution logs
        (<em>royalty receipts</em>) into verifiable payouts, trust scores for
        data providers and audit-ready evidence packs.
      </p>
      <p class="small">
        The public demo shows synthetic data only. Real deployments run
        in controlled environments with private logs and signed Trust
        Bundles.
      </p>
    </div>

    <div class="card">
      <h2>How it is structured</h2>
      <ul>
        <li><strong>M0 – Open Profile:</strong> public data model and examples.</li>
        <li><strong>M1 – Lite tools:</strong> basic validation and hashchain checks.</li>
        <li><strong>M2 – Enterprise Kit:</strong> full trust, payouts, compliance and proofs.</li>
      </ul>
      <p class="small">
        The profile is open so partners can integrate; the engine remains private
        so algorithms can evolve without breaking contracts.
      </p>
    </div>

    <div class="card">
      <h2>Governance &amp; alignment</h2>
      <p>
        CROVIA is designed to support AI training data governance aligned
        with the EU AI Act and leading international best practices on
        record-keeping and auditability.
      </p>
      <p class="small">
        The Trust Bundle JSON contains the evidence pack for a given period:
        payouts, assumptions, compliance pack and integrity proofs.
      </p>
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)

@app.get("/standard", response_class=HTMLResponse)
async def standard_profile(request: Request) -> HTMLResponse:
    """
    Public page: CROVIA Open Profile M0.
    Rende in HTML il file docs/CROVIA_PROFILE_M0.md.
    """
    md_path = BASE_DIR / "docs" / "CROVIA_PROFILE_M0.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Profile document not found")

    raw_md = md_path.read_text(encoding="utf-8")
    body_html = markdown.markdown(
        raw_md,
        extensions=["fenced_code", "tables"],
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CROVIA – AI Training Data Trust Profile M0</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      margin: 0;
      padding: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #050815;
      color: #f5f5f7;
    }}
    a {{
      color: #4ea8ff;
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    main {{
      max-width: 920px;
      margin: 32px auto 64px auto;
      padding: 0 16px;
    }}
    nav {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      background: #111827;
      border: 1px solid #1f2937;
      color: #9ca3af;
    }}
    nav a {{
      margin-left: 16px;
      font-size: 14px;
      color: #e5e7eb;
    }}
    nav a.active {{
      font-weight: 600;
      color: #ffffff;
    }}
    .card {{
      background: #0b1020;
      border-radius: 18px;
      padding: 24px 28px;
      border: 1px solid #111827;
      box-shadow: 0 18px 45px rgba(0, 0, 0, 0.55);
    }}
    .card h1, .card h2, .card h3 {{
      color: #f9fafb;
    }}
    .card pre {{
      background: #020617;
      padding: 10px 12px;
      border-radius: 10px;
      overflow-x: auto;
    }}
    .card code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
                   "Liberation Mono", "Courier New", monospace;
      font-size: 13px;
    }}
    .card ul {{
      padding-left: 20px;
    }}
    .card hr {{
      border: 0;
      border-top: 1px solid #1f2937;
      margin: 24px 0;
    }}
  </style>
</head>
<body>
  <div class="main">
    <nav>
      <div><span class="badge">CROVIA</span></div>
      <div>
        <a href="/">Dashboard</a>
        <a href="/sandbox">Sandbox</a>
        <a href="/about">About</a>
        <a href="/standard" class="active">Standard</a>
      </div>
    </nav>
    <div class="card">
      {body_html}
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(html)

@app.get("/lite-tools", response_class=HTMLResponse)
async def lite_tools(request: Request) -> HTMLResponse:
    """
    Public page: CROVIA Lite Tools Pack M1.
    Rende in HTML il file docs/CROVIA_LITE_TOOLS_M1.md.
    """
    md_path = BASE_DIR / "docs" / "CROVIA_LITE_TOOLS_M1.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Lite tools document not found")

    raw_md = md_path.read_text(encoding="utf-8")
    body_html = markdown.markdown(
        raw_md,
        extensions=["fenced_code", "tables"],
    )

    STYLE = """
    body {
      margin: 0;
      padding: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #050815;
      color: #f5f5f7;
    }
    a {
      color: #4ea8ff;
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
    .main {
      max-width: 920px;
      margin: 32px auto 64px auto;
      padding: 0 16px;
    }
    nav {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
    }
    .badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      background: #111827;
      border: 1px solid #1f2937;
      color: #9ca3af;
    }
    nav a {
      margin-left: 16px;
      font-size: 14px;
      color: #e5e7eb;
    }
    nav a.active {
      font-weight: 600;
      color: #ffffff;
    }
    .card {
      background: #0b1020;
      border-radius: 18px;
      padding: 24px 28px;
      border: 1px solid #111827;
      box-shadow: 0 18px 45px rgba(0, 0, 0, 0.55);
    }
    .card h1, .card h2, .card h3 {
      color: #f9fafb;
    }
    .card code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 13px;
    }
    .card pre {
      background: #020617;
      padding: 10px 12px;
      border-radius: 10px;
      overflow-x: auto;
    }
    .card ul {
      padding-left: 20px;
    }
    .card hr {
      border: 0;
      border-top: 1px solid #1f2937;
      margin: 24px 0;
    }
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CROVIA – Lite Tools Pack M1</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
  {STYLE}
  </style>
</head>
<body>
  <div class="main">
    <nav>
      <div><span class="badge">CROVIA</span></div>
      <div>
        <a href="/">Dashboard</a>
        <a href="/sandbox">Sandbox</a>
        <a href="/about">About</a>
        <a href="/standard">Standard</a>
        <a href="/lite-tools" class="active">Lite tools M1</a>
      </div>
    </nav>
    <div class="card">
      {body_html}
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(html)

@app.get("/faiss-demo", response_class=HTMLResponse)
async def faiss_demo(request: Request) -> HTMLResponse:
    """
    Public demo page: FAISS-based attribution run on a real log.
    Renders docs/CROVIA_FAISS_DEMO_REAL.md as HTML.
    """
    md_path = BASE_DIR / "docs" / "CROVIA_FAISS_DEMO_REAL.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Demo document not found")

    raw_md = md_path.read_text(encoding="utf-8")
    body_html = markdown.markdown(
        raw_md,
        extensions=["fenced_code", "tables"],
    )

    STYLE = """
    body {
      margin: 0;
      padding: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #050815;
      color: #f5f5f7;
    }
    a {
      color: #4ea8ff;
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
    .main {
      max-width: 920px;
      margin: 32px auto 64px auto;
      padding: 0 16px;
    }
    nav {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
    }
    .badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      background: #111827;
      border: 1px solid #1f2937;
      color: #9ca3af;
    }
    nav a {
      margin-left: 16px;
      font-size: 14px;
      color: #e5e7eb;
    }
    nav a.active {
      font-weight: 600;
      color: #ffffff;
    }
    .card {
      background: #0b1020;
      border-radius: 18px;
      padding: 24px 28px;
      border: 1px solid #111827;
      box-shadow: 0 18px 45px rgba(0, 0, 0, 0.55);
    }
    .card h1, .card h2, .card h3 {
      color: #f9fafb;
    }
    .card code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: 13px;
    }
    .card pre {
      background: #020617;
      padding: 10px 12px;
      border-radius: 10px;
      overflow-x: auto;
    }
    .card ul {
      padding-left: 20px;
    }
    .card hr {
      border: 0;
      border-top: 1px solid #1f2937;
      margin: 24px 0;
    }
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CROVIA – FAISS Attribution Evidence Demo</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
  {STYLE}
  </style>
</head>
<body>
  <div class="main">
    <nav>
      <div><span class="badge">CROVIA</span></div>
      <div>
        <a href="/">Dashboard</a>
        <a href="/sandbox">Sandbox</a>
        <a href="/about">About</a>
        <a href="/standard">Standard</a>
      </div>
    </nav>
    <div class="card">
      {body_html}
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(html)


