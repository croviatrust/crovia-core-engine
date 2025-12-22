
---

## Quickstart (30 seconds)

This repository includes a minimal NDJSON example to test the Crovia open-core pipeline.

### 1) Validation (health score + business rules)
~~bash
python3 convalidare/validate.py --in examples/minimal_royalty_receipts.ndjson --out report.md
~~

### 2) Integrity proof (hash-chain) and offline verification
~~bash
python3 prove/hashchain_writer.py --source examples/minimal_royalty_receipts.ndjson --chunk 2
python3 prove/verify_hashchain.py --source examples/minimal_royalty_receipts.ndjson --chain prove/hashchain_minimal_royalty_receipts.ndjson.txt --chunk 2
~~

Notes:
- If you modify even a single byte in the NDJSON file, `verify_hashchain.py` MUST fail.
- This demonstrates offline integrity and auditability (open-grade).

