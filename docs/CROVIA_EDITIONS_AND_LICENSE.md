# CROVIA – Editions & Licensing (draft, non-binding)

> This document is a **product / architecture note**, not a legal contract.  
> The final terms are defined by the LICENSE file(s) and any commercial agreements.

CROVIA is structured in **layers**:

- **M0 – Open Profile & Objects**  
  Schemas and profiles:
  - `royalty_receipt.v1`
  - `payouts.v1`
  - `crovia_trust_bundle.v1`
  - floor / coverage standards (text)

- **M1 – Lite Tools (QA + AI Act + hashchain)**  
  Command-line tools that run on any `royalty_receipt.v1` logs:
  - `qa_receipts.py`
  - `crovia_validate.py`
  - `compliance_ai_act.py`
  - `hashchain_writer.py`
  - `verify_hashchain.py`

- **M1+ – Bridges & adapters (e.g. MIT Bridge)**  
  Adapters that convert external valuation outputs into CROVIA receipts:
  - `mit_adapter.py` (future, experimental)
  - other bridges (HF callbacks, custom logs…)

- **M2 – Settlement Engine (Enterprise)**  
  The opinionated engine that turns receipts into:
  - trust metrics & bands
  - payouts per provider
  - floors (governance rules)
  - Trust Bundle JSON
  - optional CROVIA Grade / Reflex

---

## 1. Intended availability (product view)

This is the **intended split** between open and enterprise:

| Layer / component                          | Examples                                         | Intended availability              |
|-------------------------------------------|--------------------------------------------------|------------------------------------|
| **Standards & profiles (M0)**             | `royalty_receipt.v1`, `payouts.v1`, `trust_bundle.v1`, floor text | **Public, freely readable**       |
| **Docs & reference markdown**             | `CROVIA_PROFILE_M0.md`, `CROVIA_LITE_TOOLS_M1.md`, `CROVIA_MIT_BRIDGE_v1.md` | **Public repo**                    |
| **Lite tools (M1)**                       | `qa_receipts.py`, `crovia_validate.py`, `compliance_ai_act.py`, `hashchain_*` | **Open for research / pilots**    |
| **Bridges (M1+)**                         | `mit_adapter.py`, future HF/data-lake adapters   | **Open or source-available**      |
| **Core engine (M2)**                      | `run_period.py`, `crovia_trust.py`, `crovia_floor.py`, `make_trust_bundle.py`, `augment_trust_bundle.py`, dashboards | **Source-available / commercial** |
| **Reflex & Grade layers**                 | CROVIA Reflex M∞, CROVIA Grade A/B/C/D           | **Enterprise features**            |
| **Hosted service / dashboard**            | croviatrust.com multi-tenant, managed runs       | **SaaS / enterprise only**        |

This separation lets you:

- be **very generous** on standards and tools (M0/M1),
- keep **strategic leverage** on the settlement engine and higher layers (M2).

---

## 2. How this maps to licenses (draft intention)

**This section is NOT legal advice.**  
It captures intent, so future lawyers and partners understand what you want.

### 2.1. M0 / docs / specs

Goal:

- anyone can **read, implement and extend** the CROVIA standards,  
  even without using your engine.

Intended direction:

- use a well-known open license for **schemas and docs**  
  (e.g. an OSI-approved license for code, and a documentation license for text),
- keep them **stable and citable** so prior art is obvious.

### 2.2. M1 – Lite tools

Goal:

- make it trivial for others to **validate their logs** and **generate basic evidence**
  using your CLI tools, without full adoption of the engine.

Intended direction:

- Lite tools can be **open-source** for:
  - research,
  - pilots,
  - non-production experiments,
- with a clear statement that:
  - there is **no SLA**,
  - large-scale / commercial deployments may require a commercial agreement.

### 2.3. M2 – Settlement engine

Goal:

- keep the **full settlement logic** (floors, trust, governance, Reflex/Grade)  
  as your **differentiator** and monetisation lever.

Intended direction:

- engine code is **source-available**, but **not** a generic open-source licence,
- allowed:
  - internal evaluation,
  - research experiments,
- restricted:
  - running CROVIA as a **public SaaS** competitor,
  - embedding the engine in a commercial product **without agreement**,
  - re-licensing the engine under a different licence.

The exact legal text belongs in a dedicated engine licence, e.g.:

- `CROVIA_ENGINE_LICENSE.md`

to be written together with a lawyer.

---

## 3. Why this matters (strategic intent)

1. **Defensive publication & prior art**

   - Specs and docs (M0/M1, MIT Bridge, FAISS/Merkle demo) are public.
   - Timestamps + repo history make it clear **who did what, when**.

2. **Adoption without losing control**

   - Anyone can adopt the M0 schema and M1 tools.
   - If big players want **floors, trust, Grade, Reflex, dashboards**,  
     they either:
       - use your engine under licence, or  
       - re-implement everything from scratch (hard).

3. **Room for enterprise deals**

   - You can negotiate:
     - per-model or per-dataset licences,
     - managed runs,
     - integration support,
     - SLAs and governance guarantees.

---

## 4. Next legal steps (out of scope for this repo)

This document is a **technical & product design note**.

To make it fully binding, you still need:

1. A clear `LICENSE` file at repo root (or multiple files per component).
2. A specific **engine licence text** (source-available, commercial).
3. Optional **contributor agreement** if you accept external PRs.
4. Legal review by a qualified professional.

Until then, treat this document as the **intended direction**,  
not as a final contract.
