import time
import math
import json
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import gradio as gr
import plotly.graph_objects as go
from huggingface_hub import HfApi, hf_hub_download

# ============================================================
# CROVIA · CEP TERMINAL
# Evidence-first interface for auditable AI datasets
# ============================================================

CEP_DATASET = "Crovia/cep-capsules"
OPEN_DEMO_MODE = True   # honest declaration: space does lightweight checks

# ----------------------------
# Utilities (pure, deterministic)
# ----------------------------

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def canon_bytes(obj: dict) -> bytes:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False
    ).encode("utf-8")

def short(h: str, n=16) -> str:
    return h[:n] + "…" if isinstance(h, str) and len(h) > n else h

# ----------------------------
# Capsule discovery (single source of truth)
# ----------------------------

def list_capsules() -> list[str]:
    """
    Returns all CEP capsule IDs present in the dataset.
    No fallback. If HF is down, the UI stays empty (honest failure).
    """
    api = HfApi()
    files = api.list_repo_files(repo_id=CEP_DATASET, repo_type="dataset")
    items = [
        Path(f).stem
        for f in files
        if f.endswith(".json") and f.startswith("CEP-")
    ]
    return sorted(set(items))

CAPSULES = list_capsules()

# ----------------------------
# Capsule loading
# ----------------------------

def fetch_capsule(cep_id: str) -> dict:
    path = hf_hub_download(
        repo_id=CEP_DATASET,
        filename=f"{cep_id}.json",
        repo_type="dataset",
    )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ----------------------------
# Evidence inspection (real checks)
# ----------------------------

_RE_PERIOD = re.compile(r"^\d{4}-\d{2}$")

def inspect(capsule: dict, cep_id: str):
    """
    Returns:
      terminal_text, inspector_text, evidence_graph
    """
    terminal = []
    inspector = []

    terminal.append("CROVIA · Evidence Terminal v1")
    terminal.append(f"capsule      {cep_id}")
    terminal.append(f"dataset      {CEP_DATASET}")
    terminal.append(f"timestamp    {now_utc()}")

    if OPEN_DEMO_MODE:
        terminal.append("[ MODE: OPEN DEMO — structural checks only ]")

    terminal.append("")

    canon = canon_bytes(capsule)
    cap_sha = sha256_hex(canon)

    schema = capsule.get("schema", "unknown")
    period = capsule.get("period", "unknown")
    model_id = capsule.get("model", {}).get("model_id", "unknown")

    evidence = capsule.get("evidence", {})
    meta = capsule.get("meta", {}) if isinstance(capsule.get("meta"), dict) else {}

    checks = [
        ("schema", schema != "unknown", schema),
        ("period", bool(_RE_PERIOD.match(period)), period),
        ("model_id", model_id != "unknown", model_id),
        ("evidence_nodes",
         isinstance(evidence, dict) and len(evidence) > 0,
         len(evidence) if isinstance(evidence, dict) else 0),
        ("hashchain_root",
         isinstance(meta.get("hashchain_sha256"), str),
         short(meta.get("hashchain_sha256", ""))),
        ("signature",
         "signature" in capsule,
         "present" if "signature" in capsule else "missing"),
    ]

    terminal.append("[ load capsule ........ OK ]")
    terminal.append("[ canonical fingerprint OK ]")
    terminal.append("")

    health = "A" if all(ok for _, ok, _ in checks[:4]) else "B"

    terminal.append(f"health       {health}")
    terminal.append(f"schema       {schema}")
    terminal.append(f"model        {model_id}")
    terminal.append(f"period       {period}")
    terminal.append(f"fingerprint  sha256:{short(cap_sha)}")

    if meta.get("hashchain_sha256"):
        terminal.append(f"hashchain    sha256:{short(meta['hashchain_sha256'])}")

    terminal.append("")

    proof = (
        f"crovia:v1;"
        f"m={model_id};"
        f"p={period};"
        f"h={cap_sha};"
        f"u=hf://{CEP_DATASET}/{cep_id}.json"
    )

    terminal.append("CROVIA PROOF STRING")
    terminal.append(proof)

    inspector.append("INSPECTOR — VERIFIED FACTS")
    for name, ok, info in checks:
        inspector.append(f"- {name:14s} : {'OK' if ok else 'FAIL'}  | {info}")
    inspector.append("")
    inspector.append(f"capsule_sha256 : {cap_sha}")

    fig = build_graph(evidence, cep_id)

    return "\n".join(terminal), "\n".join(inspector), fig

# ----------------------------
# Evidence graph (truthful, minimal)
# ----------------------------

def build_graph(evidence: dict, cep_id: str):
    fig = go.Figure()

    if not isinstance(evidence, dict) or not evidence:
        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=420,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        return fig

    labels = list(evidence.keys())
    n = len(labels)

    xs, ys = [0.0], [0.0]
    texts = [cep_id]

    edge_x, edge_y = [], []

    for i, label in enumerate(labels):
        angle = 2 * math.pi * i / max(n, 1)
        x = math.cos(angle)
        y = math.sin(angle)

        xs.append(x)
        ys.append(y)
        texts.append(label)

        edge_x += [0.0, x, None]
        edge_y += [0.0, y, None]

    fig.add_trace(go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line=dict(width=1, color="#6b7280"),
        hoverinfo="none"
    ))

    fig.add_trace(go.Scatter(
        x=xs,
        y=ys,
        mode="markers+text",
        text=texts,
        textposition="top center",
        marker=dict(size=16, color="#38bdf8"),
    ))

    fig.update_layout(
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=420,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig

# ----------------------------
# Gradio UI (clean, deterministic)
# ----------------------------

with gr.Blocks(title="CROVIA · CEP Terminal") as demo:
    gr.Markdown(
        """
# CROVIA · CEP TERMINAL
**Inspect real evidence capsules. No simulations. No black boxes.**

If an AI model makes money with data,
there must be a receipt — and that receipt must be inspectable.
"""
    )

    cep_input = gr.Dropdown(
        choices=CAPSULES,
        value=None,
        label="CEP Capsule ID",
        interactive=True,
    )

    terminal_out = gr.Textbox(label="Terminal", lines=16)
    inspector_out = gr.Textbox(label="Inspector", lines=10)
    graph_out = gr.Plot()

    def run(cep_id):
        if not cep_id:
            return "Select a CEP capsule.", "", build_graph({}, "")
        capsule = fetch_capsule(cep_id)
        return inspect(capsule, cep_id)

    cep_input.change(
        run,
        inputs=cep_input,
        outputs=[terminal_out, inspector_out, graph_out]
    )

    demo.load(
        run,
        inputs=cep_input,
        outputs=[terminal_out, inspector_out, graph_out]
    )

demo.launch()
