# CROVIA Sandbox – Quick guide

The CROVIA Sandbox lets you upload a **small NDJSON file** with royalty receipts
(demo limit ~2 MB) and see a **payout preview** computed by the CROVIA engine.

It is designed for:

- technical teams who want to understand how CROVIA reacts to their attribution logs,
- early pilots with synthetic or anonymised data,
- demos where you want to show “what happens if we plug our receipts into CROVIA”.

The Sandbox is **not** a production system and does not create payment obligations.

---

## 1. What you need

You need an **NDJSON file** (“newline-delimited JSON”) where each line is a JSON
object representing a single **royalty receipt**, i.e.:

- one model output or training event,
- a set of providers that contributed to it,
- attribution weights or scores.

The exact schema is determined by the *CROVIA – AI Training Data Trust Profile v1.0*
used in your pilot. In practice, your receipts will include:

- a **provider identifier** (or multiple providers),
- a **weight / share** per provider,
- metadata about the model / run / timestamp,
- optional quality or risk signals.

Receipts should be written one per line, without commas between them.

---

## 2. Using the Sandbox

1. Go to the **Sandbox** page on croviatrust.com.
2. Click on **“Choose file”** and select your NDJSON file.
3. Set the **budget** (EUR) you want to distribute for this test period.
4. Set the **period** label (e.g. `2025-11`) – this is only used for display.
5. Click **“Run sandbox”**.

If the file is valid and within the size limit, the Sandbox will:

- run a **QA check** on your receipts,
- aggregate contribution per provider,
- compute a **payout preview** from the given EUR budget,
- show you the resulting per-provider amounts and basic statistics.

---

## 3. Error messages

Typical error messages include:

- **“Empty file”** – the upload had no content.
- **“File too large”** – the file exceeds the demo limit (~2 MB).
- **“QA failed”** – the content does not match the expected profile
  (missing fields, wrong types, or invalid JSON).

In case of “QA failed”, the Sandbox returns a text log with hints about
what is wrong (for example: missing provider identifier, invalid schema
version, or malformed JSON).

---

## 4. Privacy and safety

The Sandbox is meant for **test data**:

- Prefer synthetic, anonymised or heavily sampled receipts.
- Do not upload confidential or legally sensitive logs unless explicitly agreed
  in a pilot or under NDA.

For production integrations, CROVIA is typically run in a controlled environment
(e.g. your own infrastructure or a managed service instance) with proper security
and data-handling agreements.

---

## 5. Counters and telemetry

At the top of the Sandbox page you will see:

- how many **sandbox runs** have been executed, and
- how many **receipts** have been processed in total.

These counters are meant to show that the engine is actively used. They are
aggregated at instance level and are not linked to individual users.

