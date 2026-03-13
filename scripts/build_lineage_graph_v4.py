#!/usr/bin/env python3
"""
build_lineage_graph_v4.py — Enhanced V4 Forensic Provenance Graph Builder
=========================================================================
Merges evidence from THREE sources for maximum graph density:
  1. evidence_ledger (model_claim_v1 → parent edges, tpa_receipt_v1, outreach, sonar)
  2. sonar_chains.json (declared datasets, base models, training signals)
  3. lineage_graph.json v2 (pre-existing provenance edges from lineage_builder)

Output format matches app_v4.js expectations:
  nodes: [{id, type, label, org, ...}]
  edges: [{source, target, type}]

Safety: read-only on all inputs; writes only to /var/www/registry/data_v4/lineage_graph_v4.json
"""

import json
import sqlite3
import os
import sys
import hashlib
from datetime import datetime, timezone

sys.path.insert(0, "/opt/crovia/CROVIA_DEV/crovia-pro-engine")

def load_json_safe(path):
    """Load JSON file, return empty dict/list on failure."""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"  WARN: Could not load {path}: {e}")
        return {}


def node_id_hash(prefix, label):
    """Generate deterministic short hash ID for a node."""
    h = hashlib.sha256(label.encode()).hexdigest()[:12]
    return f"{prefix}-{h}"


def extract_org(model_id):
    """Extract org from model_id like 'google/bert-base' -> 'google'."""
    if "/" in model_id:
        return model_id.split("/")[0]
    return "unknown"


def main():
    db_path = os.environ.get("DB_PATH", "/opt/crovia/CROVIA_DEV/crovia_ledger.sqlite")
    sonar_path = os.environ.get("SONAR_PATH", "/var/www/registry/data/sonar_chains.json")
    v2_path = os.environ.get("V2_GRAPH_PATH", "/var/www/registry/data/lineage_graph.json")
    out_dir = os.environ.get("OUT_DIR", "/var/www/registry/data_v4")

    print(f"Building V4 Forensic Graph (Enhanced)")
    print(f"  Ledger: {db_path}")
    print(f"  Sonar:  {sonar_path}")
    print(f"  V2:     {v2_path}")

    nodes = {}   # id -> node dict
    edges = {}   # (source, target, type) -> edge dict  (dedup key)
    orgs = set()
    datasets = set()

    def ensure_model_node(model_id, extra=None):
        if model_id not in nodes:
            org = extract_org(model_id)
            nodes[model_id] = {
                "id": model_id,
                "type": "model",
                "label": model_id,
                "org": org,
                "tpa_absent_count": 0,
                "outreach_status": None,
            }
            orgs.add(org)
        if extra:
            nodes[model_id].update(extra)

    def ensure_org_node(org):
        oid = node_id_hash("O", org)
        if oid not in nodes:
            nodes[oid] = {"id": oid, "type": "org", "label": org}
        return oid

    def ensure_dataset_node(ds_name, model_id=None):
        did = node_id_hash("D", ds_name)
        if did not in nodes:
            nodes[did] = {"id": did, "type": "dataset", "label": ds_name}
        datasets.add(ds_name)
        return did

    def ensure_shadow_node(model_id):
        sid = node_id_hash("S", f"shadow-{model_id}")
        if sid not in nodes:
            nodes[sid] = {
                "id": sid,
                "type": "shadow",
                "label": f"Undocumented data ({model_id})",
                "model_id": model_id,
            }
        return sid

    def add_edge(source, target, etype, confidence=0.8):
        key = (source, target, etype)
        if key not in edges:
            edges[key] = {"source": source, "target": target, "type": etype, "confidence": confidence}

    # =========================================================================
    # SOURCE 1: Evidence Ledger
    # =========================================================================
    print("\n--- Source 1: Evidence Ledger ---")
    ledger_claims = 0
    ledger_parents = 0
    ledger_tpa = 0
    ledger_outreach = 0

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # 1a. Model Claims (parent extraction)
        for row in conn.execute("SELECT target_id, raw_payload FROM evidence_ledger WHERE signal_type='model_claim_v1'"):
            target_id = row["target_id"]
            payload = json.loads(row["raw_payload"])
            ensure_model_node(target_id)
            ledger_claims += 1

            parent = payload.get("extracted_parent")
            if parent:
                if isinstance(parent, list):
                    parent = parent[0]
                ensure_model_node(parent)
                add_edge(target_id, parent, "finetuned_from", 0.95)
                ledger_parents += 1

        # 1b. TPA Receipts
        for row in conn.execute("SELECT target_id, raw_payload FROM evidence_ledger WHERE signal_type='tpa_receipt_v1'"):
            target_id = row["target_id"]
            payload = json.loads(row["raw_payload"])
            ensure_model_node(target_id, {
                "tpa_absent_count": payload.get("absent_count", 0),
                "tpa_highest_severity": payload.get("highest_severity", "UNKNOWN"),
                "has_tpa": True,
            })
            ledger_tpa += 1

        # 1c. Outreach Status
        for row in conn.execute("SELECT target_id, raw_payload FROM evidence_ledger WHERE signal_type='outreach_status_v1'"):
            target_id = row["target_id"]
            payload = json.loads(row["raw_payload"])
            # Try to match existing node
            matched = None
            repo_lower = target_id.lower()
            for nid in list(nodes.keys()):
                if nid.lower() == repo_lower:
                    matched = nid
                    break
            if matched:
                nodes[matched]["outreach_status"] = payload.get("status")
                nodes[matched]["outreach_platform"] = payload.get("platform")
            else:
                ensure_model_node(target_id, {
                    "outreach_status": payload.get("status"),
                    "outreach_platform": payload.get("platform"),
                })
            ledger_outreach += 1

        conn.close()
        print(f"  Claims: {ledger_claims}, Parents: {ledger_parents}, TPA: {ledger_tpa}, Outreach: {ledger_outreach}")
    except Exception as e:
        print(f"  ERROR reading ledger: {e}")

    # =========================================================================
    # SOURCE 2: Sonar Chains (declared datasets + base models)
    # =========================================================================
    print("\n--- Source 2: Sonar Chains ---")
    sonar = load_json_safe(sonar_path)
    chains = sonar.get("chains", [])
    sonar_ds_edges = 0
    sonar_base_edges = 0
    sonar_shadow = 0

    for chain in chains:
        mid = chain.get("model_id", "")
        if not mid:
            continue
        ensure_model_node(mid, {
            "provenance_score": chain.get("provenance_score", 0),
            "card_length": chain.get("card_length", 0),
        })

        # Declared datasets → trained_on edges
        for ds in chain.get("declared_datasets", []):
            ds_name = ds if isinstance(ds, str) else ds.get("name", str(ds))
            if ds_name and len(ds_name) > 1:
                did = ensure_dataset_node(ds_name, mid)
                add_edge(mid, did, "trained_on", 0.9)
                sonar_ds_edges += 1

        # Base model → finetuned_from edges
        base = chain.get("base_model")
        if base:
            if isinstance(base, list):
                base = base[0] if base else None
            if base and isinstance(base, str) and "/" in base:
                ensure_model_node(base)
                add_edge(mid, base, "finetuned_from", 0.85)
                sonar_base_edges += 1

        # Models with 0 declared datasets → shadow node
        if not chain.get("declared_datasets") and chain.get("provenance_score", 100) < 30:
            sid = ensure_shadow_node(mid)
            add_edge(mid, sid, "undocumented_source", 0.7)
            sonar_shadow += 1

    print(f"  Chains: {len(chains)}, Dataset edges: {sonar_ds_edges}, Base edges: {sonar_base_edges}, Shadows: {sonar_shadow}")

    # =========================================================================
    # SOURCE 3: Lineage Graph V2 (merge existing edges)
    # =========================================================================
    print("\n--- Source 3: Lineage Graph V2 ---")
    v2 = load_json_safe(v2_path)
    v2_nodes_added = 0
    v2_edges_added = 0

    for n in v2.get("nodes", []):
        ntype = n.get("type", "model")
        nid = n.get("id", "")
        if ntype == "model" and n.get("label"):
            label = n["label"]
            ensure_model_node(label, {
                "compliance_score": n.get("compliance_score"),
                "severity": n.get("severity"),
                "nec_absent": n.get("nec_absent", []),
                "card_length": n.get("card_length", 0),
                "provenance_score": n.get("provenance_score", 0),
                "base_model": n.get("base_model"),
            })
            # Map old ID to label for edge resolution
            nodes[nid] = nodes.get(label, nodes.get(nid, {"id": nid, "type": ntype, "label": label}))
            v2_nodes_added += 1
        elif ntype == "org":
            label = n.get("label", nid)
            ensure_org_node(label)
            nodes[nid] = nodes.get(node_id_hash("O", label), {"id": nid, "type": "org", "label": label})
            v2_nodes_added += 1
        elif ntype == "dataset":
            label = n.get("label", nid)
            ensure_dataset_node(label)
            nodes[nid] = nodes.get(node_id_hash("D", label), {"id": nid, "type": "dataset", "label": label})
            v2_nodes_added += 1
        elif ntype == "shadow":
            nodes[nid] = n
            v2_nodes_added += 1

    for e in v2.get("edges", []):
        src = e.get("source", "")
        tgt = e.get("target", "")
        etype = e.get("type", "trained_on")
        if src in nodes and tgt in nodes:
            key = (src, tgt, etype)
            if key not in edges:
                edges[key] = {"source": src, "target": tgt, "type": etype, "confidence": 0.8}
                v2_edges_added += 1

    print(f"  V2 nodes merged: {v2_nodes_added}, V2 edges merged: {v2_edges_added}")

    # =========================================================================
    # Add org nodes + org->model edges
    # =========================================================================
    org_edges = 0
    for nid, n in list(nodes.items()):
        if n.get("type") == "model" and n.get("org"):
            oid = ensure_org_node(n["org"])
            add_edge(nid, oid, "belongs_to", 1.0)
            org_edges += 1

    # =========================================================================
    # Compute metrics
    # =========================================================================
    sev_counts = {}
    for n in nodes.values():
        if n.get("type") == "model" and n.get("severity"):
            s = n["severity"]
            sev_counts[s] = sev_counts.get(s, 0) + 1

    model_count = sum(1 for n in nodes.values() if n.get("type") == "model")
    org_count = sum(1 for n in nodes.values() if n.get("type") == "org")
    dataset_count = sum(1 for n in nodes.values() if n.get("type") == "dataset")
    shadow_count = sum(1 for n in nodes.values() if n.get("type") == "shadow")

    # Compute undocumented rate from sonar
    shadow_rate = 0
    if chains:
        opaque = sum(1 for c in chains if c.get("provenance_score", 0) < 30)
        shadow_rate = round(opaque / len(chains) * 100, 1)

    # Shared datasets
    ds_model_count = {}
    ds_org_count = {}
    for (src, tgt, etype) in edges:
        if etype == "trained_on":
            tgt_node = nodes.get(tgt, {})
            src_node = nodes.get(src, {})
            ds_label = tgt_node.get("label", tgt)
            if ds_label not in ds_model_count:
                ds_model_count[ds_label] = set()
                ds_org_count[ds_label] = set()
            ds_model_count[ds_label].add(src)
            if src_node.get("org"):
                ds_org_count[ds_label].add(src_node["org"])

    shared_datasets = sorted(
        [{"dataset": ds, "models": len(models), "organizations": len(ds_org_count.get(ds, set()))}
         for ds, models in ds_model_count.items() if len(models) >= 2],
        key=lambda x: x["models"], reverse=True
    )[:20]

    # Org compliance averages
    org_scores = {}
    for n in nodes.values():
        if n.get("type") == "model" and n.get("org") and n.get("compliance_score") is not None:
            org = n["org"]
            if org not in org_scores:
                org_scores[org] = []
            org_scores[org].append(n["compliance_score"])
    org_avg_compliance = {org: round(sum(scores)/len(scores), 1) for org, scores in org_scores.items()}

    # =========================================================================
    # Build output
    # =========================================================================
    graph = {
        "schema": "crovia.provenance_graph.v4.public",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "total_models": model_count,
            "total_organizations": org_count,
            "total_datasets_observed": dataset_count,
            "total_undocumented_shadows": shadow_count,
            "total_inherited_shadows": 0,
            "total_finetuning_chains": sum(1 for (_, _, t) in edges if t == "finetuned_from"),
            "shared_datasets": shared_datasets,
            "org_avg_compliance": org_avg_compliance,
            "undocumented_rate": shadow_rate,
        },
        "metadata": {
            "version": "4.1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "nodes_count": len(nodes),
            "edges_count": len(edges),
            "sources": ["evidence_ledger", "sonar_chains", "lineage_v2"],
        },
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "lineage_graph_v4.json")

    with open(out_path, "w") as f:
        json.dump(graph, f)

    print(f"\n=== V4 Graph Generated ===")
    print(f"  Nodes: {len(nodes)} (models={model_count}, orgs={org_count}, datasets={dataset_count}, shadows={shadow_count})")
    print(f"  Edges: {len(edges)} (finetuned={sum(1 for (_,_,t) in edges if t=='finetuned_from')}, trained_on={sum(1 for (_,_,t) in edges if t=='trained_on')}, shadow={sum(1 for (_,_,t) in edges if t=='undocumented_source')}, belongs_to={org_edges})")
    print(f"  Shared datasets: {len(shared_datasets)}")
    print(f"  Shadow rate: {shadow_rate}%")
    print(f"  Output: {out_path} ({os.path.getsize(out_path)} bytes)")


if __name__ == "__main__":
    main()
