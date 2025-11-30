#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
import hashlib


def iter_dpi_entries(dpi_root: str):
    """
    Ritorna tuple (collection_name, dataset_id, entry_dict) dai JSON di
    Data Provenance Collection (data_summaries/*.json).

    Supporta due forme comuni:
    - top-level: list[entry]
    - top-level: dict con:
        * chiave "datasets": list[entry]
        * oppure vari valori dict che contengono le entry
    """
    root = Path(dpi_root) / "data_summaries"
    if not root.is_dir():
        print(f"[ERR] directory non trovata: {root}", file=sys.stderr)
        return

    for path in sorted(root.glob("*.json")):
        # evitiamo template o file speciali
        if path.name.startswith("_"):
            continue

        try:
            raw = path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"[WARN] impossibile leggere {path}: {e}", file=sys.stderr)
            continue

        try:
            data = json.loads(raw)
        except Exception as e:
            print(f"[WARN] {path} JSON non valido: {e}", file=sys.stderr)
            continue

        # normalizza in lista di entry
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            if isinstance(data.get("datasets"), list):
                entries = data["datasets"]
            else:
                # prendi tutti i valori che sono dict
                entries = [v for v in data.values() if isinstance(v, dict)]
        else:
            print(
                f"[WARN] {path} tipo top-level inatteso: {type(data).__name__}, skip",
                file=sys.stderr,
            )
            continue

        usable = 0
        for entry in entries:
            if not isinstance(entry, dict):
                continue

            dataset_id = entry.get("Unique Dataset Identifier") or entry.get("Dataset Name")
            if not dataset_id:
                # se non c'è un identificativo chiaro, lascia stare
                continue

            usable += 1
            yield path.stem, str(dataset_id), entry

        if usable == 0:
            print(
                f"[WARN] {path} non contiene entry con "
                f"'Unique Dataset Identifier'/'Dataset Name', skip",
                file=sys.stderr,
            )


def guess_license_refs(entry: dict):
    """
    Estrae una lista di license_refs stile CROVIA a partire
    dai campi 'Licenses' / 'License' tipici di DPI.
    """
    lic_list = entry.get("Licenses") or entry.get("License") or []
    refs = []

    if isinstance(lic_list, list):
        for lic in lic_list:
            lid = None
            url = None

            if isinstance(lic, dict):
                lid = (
                    lic.get("License")
                    or lic.get("name")
                    or lic.get("id")
                    or lic.get("spdx_id")
                )
                url = (
                    lic.get("License URL")
                    or lic.get("url")
                    or lic.get("href")
                )
            elif isinstance(lic, str):
                lid = lic

            if lid:
                ref = {"license_id": str(lid)}
                if url:
                    ref["url"] = str(url)
                refs.append(ref)

    elif isinstance(lic_list, str):
        refs.append({"license_id": lic_list})

    return refs


def build_receipts_from_dpi(dpi_root: str, period: str, model_id: str):
    """
    Converte le schede DPI in ricevute CROVIA royalty_receipt.v1.

    Scelte:
    - 1 dataset DPI == 1 'output' sintetico
    - top_k ha un solo provider, share=1.0
    - provider_id == dataset_id
    """
    hash_model = hashlib.sha256(model_id.encode("utf-8")).hexdigest()[:16]
    hash_data_index = hashlib.sha256(f"dpi|{period}".encode("utf-8")).hexdigest()[:16]

    # timestamp coerente con il periodo (usiamo il giorno 01)
    ts = f"{period}-01T00:00:00Z"

    for collection, dataset_id, entry in iter_dpi_entries(dpi_root):
        obj = {
            "schema": "royalty_receipt.v1",
            "period": period,
            "output_id": f"{dataset_id}::dpi_synthetic",
            "request_id": dataset_id,
            "model_id": model_id,
            "timestamp": ts,
            "attribution_scope": "dpi_collection.v1",
            # usage opzionale: mettiamo placeholder
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
            },
            "top_k": [
                {
                    "rank": 1,
                    "provider_id": dataset_id,
                    "shard_id": dataset_id,
                    "share": 1.0,
                    "meta": {
                        "dpi_collection": collection,
                    },
                }
            ],
            "hash_model": hash_model,
            "hash_data_index": hash_data_index,
        }

        # Licenze (se presenti)
        lic_refs = guess_license_refs(entry)
        if lic_refs:
            obj["license_refs"] = lic_refs

        # Alcune info DPI utili in meta
        meta = obj.setdefault("meta", {})
        if entry.get("Dataset Name"):
            meta["dataset_name"] = entry["Dataset Name"]
        if entry.get("Hugging Face URL"):
            meta["hf_url"] = entry["Hugging Face URL"]
        if entry.get("Dataset URL"):
            meta["dataset_url"] = entry["Dataset URL"]
        if entry.get("Domain"):
            meta["domain"] = entry["Domain"]
        if entry.get("Task Type"):
            meta["task_type"] = entry["Task Type"]

        yield obj


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Converte Data Provenance Collection → CROVIA royalty_receipt.v1"
    )
    ap.add_argument(
        "--dpi-root",
        required=True,
        help="Root della Data Provenance Collection (es. /opt/dpi_collection)",
    )
    ap.add_argument(
        "--period",
        required=True,
        help="Periodo CROVIA, es. 2025-11",
    )
    ap.add_argument(
        "--model-id",
        required=True,
        help="Identificativo del modello (es. crovia-dpi-demo-v1)",
    )
    ap.add_argument(
        "--out",
        required=True,
        help="File NDJSON di output (royalty_receipt.v1)",
    )

    args = ap.parse_args(argv)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for rec in build_receipts_from_dpi(args.dpi_root, args.period, args.model_id):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1

    print(f"[DPI→CROVIA] Scritte {count} ricevute in: {out_path}")


if __name__ == "__main__":
    main()
