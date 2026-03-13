#!/usr/bin/env python3
"""
CROVIA Lineage Builder v2 — Provenance Graph
==============================================

Builds a disclosure lineage graph from observed model data,
enriched with Model Sonar provenance chains.

Maps relationships: Organization → Model → Dataset → Omission patterns.
With Sonar fusion: Model → Base Model → Base's Data → Inherited Gaps.

The graph reveals:
- Which organizations share undocumented training data practices
- Which datasets are most commonly omitted from documentation
- Network effects — systemic disclosure gaps across model families
- Opacity Cascade — how a single opaque base model contaminates all derivatives
- Inherited provenance gaps — finetuned models that inherit undeclared data

This is observation, not accusation. We map what is publicly documented
and what is absent.

Usage:
    python lineage_builder.py --output lineage_graph.json --sonar provenance_chains.json

Copyright (c) 2026 Crovia / CroviaTrust
"""

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ═══════════════════════════════════════════════════════════════
# HuggingFace API
# ═══════════════════════════════════════════════════════════════

try:
    from huggingface_hub import HfApi, ModelCard
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

import requests as _requests

def _fetch_card_http(model_id: str) -> str:
    """Fallback: fetch model card via public HTTP (no token needed)."""
    for url in [
        f"https://huggingface.co/{model_id}/raw/main/README.md",
        f"https://huggingface.co/{model_id}/resolve/main/README.md",
    ]:
        try:
            r = _requests.get(url, timeout=15)
            if r.status_code == 200 and len(r.text) > 20:
                return r.text
        except Exception:
            pass
    return ""


def _load_token() -> Optional[str]:
    """Load HF token from env or tpr.env file."""
    token = os.getenv("HF_TOKEN")
    if token:
        return token
    for p in ["/etc/crovia/tpr.env", os.path.join(os.path.dirname(__file__), "..", ".env")]:
        if os.path.exists(p):
            with open(p) as f:
                for line in f:
                    if line.strip().startswith("HF_TOKEN="):
                        return line.strip().split("=", 1)[1].strip('"').strip("'")
    return None


# ═══════════════════════════════════════════════════════════════
# Dataset Extraction from Model Cards
# ═══════════════════════════════════════════════════════════════

# Known dataset patterns in model cards
DATASET_PATTERNS = [
    # Explicit HF dataset references
    r'(?:datasets?|trained\s+on|training\s+data)[:\s]+\[?([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)',
    # YAML metadata datasets field
    r'datasets?:\s*\n(?:\s*-\s*([a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_.-]+)?))+',
    # Common dataset names
    r'\b((?:the\s+)?(?:pile|c4|common[\s_]?crawl|wikipedia|bookcorpus|openwebtext|redpajama|'
    r'laion|imagenet|coco|squad|glue|superglue|wmt|opus|librispeech|voxpopuli|'
    r'mc4|oscar|cc100|mC4|roots|starcoder|the-stack|refinedweb|falcon-refinedweb|'
    r'dolma|slim[\s_]?pajama|fineweb|culturax|madlad|wudao|clue)(?:[\s_-]?\d+[a-zA-Z]?)?)\b',
]

# Known large-scale datasets and their characteristics
KNOWN_DATASETS = {
    "common_crawl": {"type": "web_scrape", "scale": "petabyte", "license_clarity": "low"},
    "the_pile": {"type": "curated", "scale": "800GB", "license_clarity": "medium"},
    "c4": {"type": "web_scrape", "scale": "305GB", "license_clarity": "low"},
    "wikipedia": {"type": "encyclopedia", "scale": "20GB", "license_clarity": "high"},
    "bookcorpus": {"type": "books", "scale": "5GB", "license_clarity": "disputed"},
    "openwebtext": {"type": "web_scrape", "scale": "38GB", "license_clarity": "low"},
    "redpajama": {"type": "curated", "scale": "1.2T tokens", "license_clarity": "medium"},
    "laion": {"type": "image_text", "scale": "5B pairs", "license_clarity": "low"},
    "imagenet": {"type": "image", "scale": "14M images", "license_clarity": "medium"},
    "refinedweb": {"type": "web_scrape", "scale": "5T tokens", "license_clarity": "medium"},
    "starcoder": {"type": "code", "scale": "6.4T tokens", "license_clarity": "medium"},
    "the_stack": {"type": "code", "scale": "6.4TB", "license_clarity": "medium"},
    "dolma": {"type": "curated", "scale": "3T tokens", "license_clarity": "high"},
    "slim_pajama": {"type": "curated", "scale": "627B tokens", "license_clarity": "medium"},
    "fineweb": {"type": "web_scrape", "scale": "15T tokens", "license_clarity": "medium"},
    "roots": {"type": "curated", "scale": "1.6TB", "license_clarity": "medium"},
}


def normalize_dataset_name(name: str) -> str:
    """Normalize dataset name for deduplication."""
    name = name.lower().strip()
    name = re.sub(r'[\s_-]+', '_', name)
    name = re.sub(r'^the_', '', name)
    return name


def extract_datasets_from_card(card_text: str) -> List[Dict[str, Any]]:
    """Extract dataset references from a model card."""
    datasets = []
    seen = set()
    text_lower = card_text.lower()

    # Method 1: YAML metadata
    yaml_match = re.search(r'^---\n(.*?)\n---', card_text, re.DOTALL)
    if yaml_match:
        yaml_text = yaml_match.group(1)
        for m in re.finditer(r'^\s*-\s+(\S+)', yaml_text, re.MULTILINE):
            ds = m.group(1).strip()
            if '/' in ds or len(ds) > 3:
                norm = normalize_dataset_name(ds)
                if norm not in seen:
                    seen.add(norm)
                    datasets.append({
                        "name": ds,
                        "normalized": norm,
                        "source": "yaml_metadata",
                        "confidence": 0.9,
                    })

    # Method 2: Pattern matching in text
    for pattern in DATASET_PATTERNS:
        for m in re.finditer(pattern, text_lower, re.IGNORECASE):
            ds = m.group(1) if m.lastindex else m.group(0)
            ds = ds.strip()
            norm = normalize_dataset_name(ds)
            if norm not in seen and len(norm) > 2:
                seen.add(norm)
                known = KNOWN_DATASETS.get(norm, {})
                datasets.append({
                    "name": ds,
                    "normalized": norm,
                    "source": "text_pattern",
                    "confidence": 0.7 if known else 0.5,
                    "dataset_type": known.get("type", "unknown"),
                    "license_clarity": known.get("license_clarity", "unknown"),
                })

    return datasets


# ═══════════════════════════════════════════════════════════════
# Lineage Graph Builder
# ═══════════════════════════════════════════════════════════════

class LineageBuilder:
    """Builds the disclosure lineage graph from real observed data + Sonar provenance."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or _load_token()
        self.api = HfApi(token=self.token) if HF_AVAILABLE and self.token else None
        self.nodes = {}      # id -> node dict
        self.edges = []      # list of edge dicts
        self.org_models = defaultdict(list)  # org -> [model_ids]
        self.dataset_models = defaultdict(list)  # dataset -> [model_ids]
        self.sonar_chains = {}  # model_id -> provenance chain from Sonar
        self.base_model_dependents = defaultdict(list)  # base_model -> [dependent_model_ids]

    def _node_id(self, node_type: str, name: str) -> str:
        """Generate deterministic node ID."""
        h = hashlib.sha256(f"{node_type}:{name}".encode()).hexdigest()[:12]
        return f"{node_type[0].upper()}-{h}"

    def add_model_node(self, model_id: str, metadata: Dict) -> str:
        """Add a model node to the graph."""
        nid = self._node_id("model", model_id)
        self.nodes[nid] = {
            "id": nid,
            "type": "model",
            "label": model_id,
            "org": model_id.split("/")[0] if "/" in model_id else "unknown",
            **metadata,
        }
        return nid

    def add_org_node(self, org: str) -> str:
        """Add an organization node."""
        nid = self._node_id("org", org)
        if nid not in self.nodes:
            self.nodes[nid] = {
                "id": nid,
                "type": "org",
                "label": org,
            }
        return nid

    def add_dataset_node(self, dataset: Dict) -> str:
        """Add a dataset node."""
        norm = dataset["normalized"]
        nid = self._node_id("dataset", norm)
        if nid not in self.nodes:
            self.nodes[nid] = {
                "id": nid,
                "type": "dataset",
                "label": dataset["name"],
                "normalized": norm,
                "dataset_type": dataset.get("dataset_type", "unknown"),
                "license_clarity": dataset.get("license_clarity", "unknown"),
            }
        return nid

    def add_edge(self, source: str, target: str, edge_type: str, weight: float = 1.0, metadata: Dict = None):
        """Add an edge between nodes."""
        self.edges.append({
            "source": source,
            "target": target,
            "type": edge_type,
            "weight": weight,
            **(metadata or {}),
        })

    def load_sonar_data(self, sonar_path: str):
        """Load Model Sonar provenance chains."""
        if not os.path.exists(sonar_path):
            return 0
        with open(sonar_path) as f:
            data = json.load(f)
        chains = data.get("chains", [])
        # Also handle single-model output (no "chains" key)
        if not chains and "model_id" in data:
            chains = [data]
        for chain in chains:
            mid = chain.get("model_id", "")
            if mid:
                self.sonar_chains[mid] = chain
        return len(self.sonar_chains)

    def process_model(self, model_id: str, card_text: str, compliance: Dict = None):
        """Process a single model: extract datasets, build relationships."""
        org = model_id.split("/")[0] if "/" in model_id else "unknown"

        # Compliance data
        comp_score = 0
        severity = "unknown"
        nec_absent = []
        if compliance:
            comp_score = compliance.get("summary", {}).get("overall_score_pct", 0)
            severity = compliance.get("summary", {}).get("severity_label", "unknown")
            for obs in compliance.get("observations", []):
                if obs.get("status") == "absent":
                    nec_absent.append(obs["nec_id"])

        # Sonar provenance data
        sonar = self.sonar_chains.get(model_id, {})
        prov_score = sonar.get("provenance_score", 0)
        base_model = sonar.get("base_model")
        base_chain = sonar.get("base_model_chain", [])
        sonar_declared = sonar.get("declared_datasets", [])
        sonar_inferred = sonar.get("inferred_datasets", [])

        # Add nodes
        model_nid = self.add_model_node(model_id, {
            "compliance_score": comp_score,
            "severity": severity,
            "nec_absent": nec_absent,
            "card_length": len(card_text),
            "provenance_score": prov_score,
            "base_model": base_model,
            "sonar_declared": len(sonar_declared),
            "sonar_inferred": len(sonar_inferred),
        })
        org_nid = self.add_org_node(org)

        # Org -> Model edge
        self.add_edge(org_nid, model_nid, "owns")
        self.org_models[org].append(model_id)

        # Extract datasets from card text
        datasets = extract_datasets_from_card(card_text)

        # Merge Sonar declared datasets (higher confidence)
        card_ds_names = {d["normalized"] for d in datasets}
        for sd in sonar_declared:
            norm = normalize_dataset_name(sd)
            if norm not in card_ds_names:
                datasets.append({
                    "name": sd,
                    "normalized": norm,
                    "source": "sonar_tag",
                    "confidence": 0.95,
                    "dataset_type": KNOWN_DATASETS.get(norm, {}).get("type", "unknown"),
                    "license_clarity": KNOWN_DATASETS.get(norm, {}).get("license_clarity", "unknown"),
                })

        for ds in datasets:
            ds_nid = self.add_dataset_node(ds)
            self.add_edge(model_nid, ds_nid, "trained_on", weight=ds["confidence"])
            self.dataset_models[ds["normalized"]].append(model_id)

        # Base model chain (from Sonar)
        if base_model:
            self.base_model_dependents[base_model].append(model_id)
            # Ensure base model has a node
            base_org = base_model.split("/")[0] if "/" in base_model else "unknown"
            base_nid = self.add_model_node(base_model, {
                "provenance_score": self.sonar_chains.get(base_model, {}).get("provenance_score", 0),
                "base_model": self.sonar_chains.get(base_model, {}).get("base_model"),
                "is_base_model": True,
            })
            base_org_nid = self.add_org_node(base_org)
            self.add_edge(base_org_nid, base_nid, "owns")
            # Model -> Base edge
            self.add_edge(model_nid, base_nid, "finetuned_from", weight=0.99)

            # Full chain: model -> base -> base's base -> ...
            prev_nid = base_nid
            for ancestor in base_chain[1:]:
                anc_org = ancestor.split("/")[0] if "/" in ancestor else "unknown"
                anc_nid = self.add_model_node(ancestor, {
                    "provenance_score": self.sonar_chains.get(ancestor, {}).get("provenance_score", 0),
                    "is_base_model": True,
                })
                anc_org_nid = self.add_org_node(anc_org)
                self.add_edge(anc_org_nid, anc_nid, "owns")
                self.add_edge(prev_nid, anc_nid, "finetuned_from", weight=0.95)
                self.base_model_dependents[ancestor].append(model_id)
                prev_nid = anc_nid

        # If NEC#1 (data provenance) is absent, add a "shadow" node
        if "NEC#1" in nec_absent:
            shadow_nid = self._node_id("shadow", model_id)
            self.nodes[shadow_nid] = {
                "id": shadow_nid,
                "type": "shadow",
                "label": f"Undocumented data ({model_id})",
                "model_id": model_id,
            }
            self.add_edge(model_nid, shadow_nid, "undocumented_source")

        # Inherited shadow: base model is opaque, derivative inherits the gap
        if base_model and prov_score < 0.3:
            base_prov = self.sonar_chains.get(base_model, {}).get("provenance_score", 0)
            if base_prov < 0.3:
                inherited_nid = self._node_id("inherited_shadow", model_id)
                self.nodes[inherited_nid] = {
                    "id": inherited_nid,
                    "type": "inherited_shadow",
                    "label": f"Inherited opacity from {base_model}",
                    "model_id": model_id,
                    "base_model": base_model,
                    "base_provenance_score": base_prov,
                }
                self.add_edge(model_nid, inherited_nid, "inherited_opacity")

        return len(datasets)

    def compute_metrics(self) -> Dict:
        """Compute graph-level metrics including opacity cascades."""
        models = [n for n in self.nodes.values() if n["type"] == "model"]
        orgs = [n for n in self.nodes.values() if n["type"] == "org"]
        datasets = [n for n in self.nodes.values() if n["type"] == "dataset"]
        shadows = [n for n in self.nodes.values() if n["type"] == "shadow"]
        inherited = [n for n in self.nodes.values() if n["type"] == "inherited_shadow"]

        # Shared datasets (used by 2+ models from different orgs)
        shared_datasets = []
        for ds_name, model_ids in self.dataset_models.items():
            orgs_using = set(m.split("/")[0] for m in model_ids if "/" in m)
            if len(orgs_using) >= 2:
                shared_datasets.append({
                    "dataset": ds_name,
                    "models": len(model_ids),
                    "organizations": len(orgs_using),
                })

        # Org compliance distribution
        org_scores = {}
        for n in models:
            org = n.get("org", "unknown")
            if org not in org_scores:
                org_scores[org] = []
            org_scores[org].append(n.get("compliance_score", 0))

        org_avg = {
            org: round(sum(scores) / len(scores), 1)
            for org, scores in org_scores.items()
        }

        # Provenance distribution (from Sonar)
        prov_scores = [n.get("provenance_score", 0) for n in models if n.get("provenance_score") is not None]
        prov_buckets = {"opaque_0_20": 0, "low_20_40": 0, "medium_40_60": 0, "good_60_80": 0, "transparent_80_100": 0}
        for s in prov_scores:
            if s < 0.2: prov_buckets["opaque_0_20"] += 1
            elif s < 0.4: prov_buckets["low_20_40"] += 1
            elif s < 0.6: prov_buckets["medium_40_60"] += 1
            elif s < 0.8: prov_buckets["good_60_80"] += 1
            else: prov_buckets["transparent_80_100"] += 1

        # Opacity Cascades: base models whose opacity affects the most derivatives
        opacity_cascades = []
        for base_id, dependents in self.base_model_dependents.items():
            base_prov = self.sonar_chains.get(base_id, {}).get("provenance_score", 0)
            if base_prov < 0.4 and len(dependents) >= 1:
                dep_orgs = set(d.split("/")[0] for d in dependents if "/" in d)
                opacity_cascades.append({
                    "base_model": base_id,
                    "base_provenance_score": round(base_prov, 3),
                    "affected_models": len(dependents),
                    "affected_organizations": len(dep_orgs),
                    "dependents": dependents[:10],
                })
        opacity_cascades.sort(key=lambda x: -x["affected_models"])

        # Finetuning chain stats
        finetuned_edges = [e for e in self.edges if e["type"] == "finetuned_from"]
        inherited_edges = [e for e in self.edges if e["type"] == "inherited_opacity"]

        # Org provenance averages
        org_prov = defaultdict(list)
        for n in models:
            org = n.get("org", "unknown")
            ps = n.get("provenance_score", 0)
            if ps > 0:
                org_prov[org].append(ps)
        org_avg_prov = {
            org: round(sum(scores) / len(scores) * 100, 1)
            for org, scores in org_prov.items() if scores
        }

        return {
            "total_models": len(models),
            "total_organizations": len(orgs),
            "total_datasets_observed": len(datasets),
            "total_undocumented_shadows": len(shadows),
            "total_inherited_shadows": len(inherited),
            "total_finetuning_chains": len(finetuned_edges),
            "shared_datasets": sorted(shared_datasets, key=lambda x: -x["organizations"])[:20],
            "org_avg_compliance": org_avg,
            "undocumented_rate": round(len(shadows) / max(len(models), 1) * 100, 1),
            # Sonar-enriched metrics
            "provenance_distribution": prov_buckets,
            "avg_provenance_score": round(sum(prov_scores) / max(len(prov_scores), 1) * 100, 1) if prov_scores else None,
            "opacity_cascades": opacity_cascades[:20],
            "most_depended_bases": sorted(
                [{"base": k, "dependents": len(v)} for k, v in self.base_model_dependents.items()],
                key=lambda x: -x["dependents"]
            )[:15],
            "org_avg_provenance": org_avg_prov,
        }

    def export(self) -> Dict:
        """Export the full graph as JSON (PRIVATE — contains Sonar data)."""
        metrics = self.compute_metrics()
        return {
            "schema": "crovia.provenance_graph.v2",
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "sonar_enriched": len(self.sonar_chains) > 0,
            "sonar_chains_loaded": len(self.sonar_chains),
            "metrics": metrics,
            "nodes": list(self.nodes.values()),
            "edges": self.edges,
        }

    def export_public(self) -> Dict:
        """Export a public graph for D3.js visualization.

        Shows visual impact (finetuning chains, inherited shadows, opacity labels)
        but strips exact scores, raw signals, cascade analysis, org averages.
        """
        # Strip exact numeric scores and raw Sonar fields — keep categorical labels
        STRIP_NODE_KEYS = {"sonar_declared", "sonar_inferred", "base_provenance_score"}

        pub_nodes = []
        for n in self.nodes.values():
            clean = {k: v for k, v in n.items() if k not in STRIP_NODE_KEYS}
            # Convert provenance_score to category label (no exact number)
            ps = n.get("provenance_score")
            if ps is not None and ps > 0:
                clean.pop("provenance_score", None)
                if ps >= 0.7:
                    clean["transparency"] = "transparent"
                elif ps >= 0.4:
                    clean["transparency"] = "partial"
                else:
                    clean["transparency"] = "opaque"
            # inherited_shadow: simplify label (no base_provenance_score)
            if n["type"] == "inherited_shadow":
                clean["label"] = f"Inherited opacity from {n.get('base_model', 'base')}"
            pub_nodes.append(clean)

        # Keep all edge types including finetuned_from and inherited_opacity
        pub_edges = list(self.edges)

        # Public metrics: show counts and inherited shadows, strip detailed analysis
        metrics = self.compute_metrics()
        # Keep these for visual impact
        inherited_count = metrics.get("total_inherited_shadows", 0)
        finetuning_count = metrics.get("total_finetuning_chains", 0)
        # Strip detailed numeric analysis
        for key in ["opacity_cascades", "provenance_distribution", "avg_provenance_score",
                    "most_depended_bases", "org_avg_provenance"]:
            metrics.pop(key, None)

        return {
            "schema": "crovia.provenance_graph.v2.public",
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "metrics": metrics,
            "nodes": pub_nodes,
            "edges": pub_edges,
        }


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Build CROVIA Provenance Graph (Lineage + Sonar)")
    parser.add_argument("--output", type=str, default=None, help="Public output JSON (stripped, no Sonar)")
    parser.add_argument("--output-full", type=str, default=None, help="Private full output (with Sonar data)")
    parser.add_argument("--compliance-dir", type=str, default=None, help="Compliance reports dir")
    parser.add_argument("--sonar", type=str, default=None, help="Path to Sonar provenance_chains.json")
    args = parser.parse_args()

    token = _load_token()
    builder = LineageBuilder(token=token)

    # Determine paths
    script_dir = Path(__file__).resolve().parent
    sent_log = script_dir / "sent_discussions.jsonl"

    comp_dir = Path(args.compliance_dir) if args.compliance_dir else None
    if not comp_dir:
        for candidate in [
            Path("/opt/crovia/data/compliance_full"),
            Path("/var/www/registry/data/compliance"),
            script_dir.parent / "webroot" / "registry" / "data" / "compliance",
        ]:
            if candidate.exists():
                comp_dir = candidate
                break

    output_path = Path(args.output) if args.output else None
    if not output_path:
        for candidate in [
            Path("/var/www/registry/data/lineage_graph.json"),
            script_dir.parent / "webroot" / "registry" / "data" / "lineage_graph.json",
        ]:
            if candidate.parent.exists():
                output_path = candidate
                break
        if not output_path:
            output_path = Path("lineage_graph.json")

    # Load Sonar data
    sonar_path = args.sonar
    if not sonar_path:
        for candidate in [
            "/var/www/registry/data/provenance_chains.json",
            str(script_dir.parent / "webroot" / "registry" / "data" / "provenance_chains.json"),
        ]:
            if os.path.exists(candidate):
                sonar_path = candidate
                break

    if sonar_path and os.path.exists(sonar_path):
        loaded = builder.load_sonar_data(sonar_path)
        print(f"  Sonar chains: {loaded}")
    else:
        print("  Sonar: no data (run model_sonar.py first for enrichment)")

    print("=" * 60)
    print("CROVIA Provenance Graph Builder v2 (Lineage + Sonar)")
    print("=" * 60)

    # Load outreach targets from sent_discussions.jsonl
    model_ids = []
    if sent_log.exists():
        with open(sent_log) as f:
            for line in f:
                rec = json.loads(line.strip())
                tid = rec.get("target_id", "")
                if tid and tid not in model_ids:
                    model_ids.append(tid)

    # Also load from targets_unified.json (discovery targets)
    targets_file = script_dir / "targets_unified.json"
    if targets_file.exists():
        try:
            with open(targets_file) as f:
                tdata = json.load(f)
                for t in tdata:
                    tid = t.get("target_id", "") if isinstance(t, dict) else str(t)
                    if tid and tid not in model_ids:
                        model_ids.append(tid)
        except Exception:
            pass

    print(f"  Targets: {len(model_ids)}")

    # Load compliance reports
    compliance_data = {}
    if comp_dir and comp_dir.exists():
        for f in comp_dir.glob("*.json"):
            if f.name == "index.json":
                continue
            try:
                with open(f) as fh:
                    data = json.load(fh)
                mid = data.get("model_id")
                if mid:
                    compliance_data[mid] = data
            except Exception:
                pass
    print(f"  Compliance reports: {len(compliance_data)}")

    # Fetch model cards and build graph
    api = HfApi(token=token) if HF_AVAILABLE and token else None
    total_datasets = 0
    processed = 0

    for i, model_id in enumerate(model_ids):
        print(f"  [{i+1}/{len(model_ids)}] {model_id} ...", end=" ", flush=True)

        # Get model card
        card_text = ""
        if api:
            try:
                card = ModelCard.load(model_id, token=token)
                card_text = card.text or ""
            except Exception:
                pass

        if not card_text:
            card_text = _fetch_card_http(model_id)

        if not card_text:
            # Try to get from compliance report
            comp = compliance_data.get(model_id, {})
            card_text = f"# {model_id}\n"  # minimal fallback

        comp = compliance_data.get(model_id)
        ds_count = builder.process_model(model_id, card_text, comp)
        total_datasets += ds_count
        processed += 1
        print(f"{ds_count} datasets")

    # Export PUBLIC graph (stripped, no Sonar secrets) -> webroot
    pub_graph = builder.export_public()

    # Sentinel + attribution — traceable if data is copied/republished
    import hashlib as _hashlib
    from datetime import datetime as _dt, timezone as _tz
    _gen = _dt.now(_tz.utc).isoformat()
    _sentinel_raw = f"{_gen}:{len(pub_graph['nodes'])}:{len(pub_graph['edges'])}"
    pub_graph["generated_at"] = _gen
    pub_graph["sentinel"] = _hashlib.sha256(_sentinel_raw.encode()).hexdigest()[:24]
    pub_graph["license"] = "CC-BY-4.0"
    pub_graph["attribution"] = "Crovia Registry — https://registry.croviatrust.com — Provenance graph generated by the Crovia autonomous observer network. Attribution required for any reuse."
    pub_graph["terms"] = "https://croviatrust.com/terms"

    with open(output_path, "w") as f:
        json.dump(pub_graph, f, indent=2)
    print(f"\nPublic graph: {output_path} ({len(pub_graph['nodes'])} nodes, {len(pub_graph['edges'])} edges)")

    # Export FULL graph (private, with Sonar data) -> /opt/crovia/data/sonar/
    output_full = getattr(args, 'output_full', None)
    if output_full:
        full_graph = builder.export()
        os.makedirs(os.path.dirname(output_full), exist_ok=True)
        with open(output_full, "w") as f:
            json.dump(full_graph, f, indent=2)
        print(f"Full graph (PRIVATE): {output_full}")
        m = full_graph["metrics"]
    else:
        m = pub_graph["metrics"]

    print(f"\nProvenance Graph:")
    print(f"   Models: {m['total_models']}")
    print(f"   Organizations: {m['total_organizations']}")
    print(f"   Datasets observed: {m['total_datasets_observed']}")
    print(f"   Undocumented shadows: {m['total_undocumented_shadows']}")
    print(f"   Inherited shadows: {m.get('total_inherited_shadows', 0)}")
    print(f"   Finetuning chains: {m.get('total_finetuning_chains', 0)}")
    print(f"   Undocumented rate: {m['undocumented_rate']}%")
    print(f"   Shared datasets: {len(m['shared_datasets'])}")
    if m.get('avg_provenance_score') is not None:
        print(f"   Avg provenance score: {m['avg_provenance_score']}%")
        pd = m.get('provenance_distribution', {})
        print(f"   Provenance: opaque={pd.get('opaque_0_20',0)} low={pd.get('low_20_40',0)} "
              f"med={pd.get('medium_40_60',0)} good={pd.get('good_60_80',0)} transparent={pd.get('transparent_80_100',0)}")
    cascades = m.get('opacity_cascades', [])
    if cascades:
        print(f"\n   OPACITY CASCADES ({len(cascades)} detected):")
        for c in cascades[:5]:
            print(f"     {c['base_model']} (score={c['base_provenance_score']:.0%}) -> "
                  f"{c['affected_models']} models, {c['affected_organizations']} orgs")
    print("=" * 60)


if __name__ == "__main__":
    main()
