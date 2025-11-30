# CROVIA – AI Training Data Trust Profile v1.0

This profile defines how CROVIA represents:

1. **Attribution evidence** (royalty receipts),
2. **Periodic payouts** per provider,
3. **Trust Bundles** that package results and governance metadata.

The profile is designed to:

- be compact and streaming-friendly (newline-delimited JSON),
- support EU AI Act record-keeping and transparency requirements,
- fit into broader international AI governance frameworks.

---

## 1. Royalty receipts

A **royalty receipt** is a JSON object describing how a single model output is attributed to providers.

Conceptually it contains:

- information about the **output** (e.g. model, task, timestamp),
- a list of **providers** with their contribution weights,
- optional **quality / risk signals** (confidence, flags, bands),
- optional **shard / partition identifiers** for large-scale storage.

Receipts are written as **NDJSON** (one JSON object per line) so they can be:

- appended as logs,
- sharded across storage,
- processed incrementally.

---

## 2. Payouts

For each period (e.g. `2025-11`) and currency (e.g. EUR), CROVIA aggregates receipts into a **payout table**.

Conceptually each payout record contains:

- a **provider identifier**,
- the **period** and **currency**,
- the **payout amount** for that period,
- derived **metrics** (share, appearance counts, bands, risk indicators).

The exact mathematical allocation (how weights become payouts) is implementation-specific, but the profile guarantees:

- one record per provider and period,
- explicit totals and shares,
- fields that can be compared across periods.

---

## 3. Trust and priority

CROVIA computes **trust metrics** and a **priority band** per provider.

Typical signals included in the profile:

- a **trust score** in `[0, 1]`,
- a **risk score** or risk band,
- a **priority band** (e.g. HIGH / MED / LOW),
- statistics about how often the provider appears in top-ranked outputs.

These signals are stored alongside payouts so that business and compliance teams can:

- see not only “how much we pay”, but also
- “how much we rely on this provider and with which level of confidence”.

---

## 4. Trust Bundle

For each (period, currency) combination, CROVIA emits a **Trust Bundle JSON**.

Conceptually, a Trust Bundle contains:

1. **Header**
   - period, currency, generation timestamp,
   - engine / profile identifiers,
   - short narrative summary.

2. **Artifacts**
   - paths and checksums of key artifacts:
     - payout tables (CSV / NDJSON),
     - charts (top-10 payouts, cumulative curve),
     - compliance summary,
     - integrity proofs (hashchain files).

3. **Governance**
   - profile label (e.g. *“CROVIA – AI Training Data Trust Profile v1.0”*),
   - references to policies, runbooks or internal procedures,
   - role-based signatures (e.g. “Data Governance”, “Compliance”).

4. **Attestations (optional)**
   - statements such as:
     - coverage assumptions,
     - known gaps or exclusions,
     - validation steps performed before releasing the bundle.

The Trust Bundle is the object that can be **signed**, archived, and shared with partners or auditors.

---

## 5. Compliance and governance philosophy

The profile is intentionally aligned with:

- the **EU AI Act** requirements for record-keeping, traceability and transparency, and
- principles from major international AI governance frameworks.

The goal is:

- to make it easy for an organization to prove **what data was used**,  
- how **payouts and trust** were derived,  
- and which **checks and responsibilities** were in place at each run.

The profile does *not* try to encode every local regulation inside the JSON itself.  
Instead, it provides a **stable data backbone** that legal and compliance teams can map to their own obligations.

---

## 6. Extensibility

The v1.0 profile is intentionally minimal.  
Future versions may add:

- richer risk and bias metrics,
- links to model evaluations and red-team results,
- references to data protection impact assessments,
- multi-currency and multi-jurisdiction metadata.

Backward compatibility will be maintained wherever possible by:

- keeping core objects stable,
- adding new fields in an additive way,
- versioning bundles and receipts explicitly.

