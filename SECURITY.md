# Security Policy

## What the Substrate claims

Every envelope in the AXIOM ledger is Ed25519-signed by the observer key
published in
[`trust_root.json`](https://croviatrust.com/registry/data/substrate/trust_root.json).
The ledger is Merkle-sealed hourly; the root is published in
`latest_seal.json`; each new root is stamped with OpenTimestamps and listed in
`ots_anchors.json` once confirmed in Bitcoin.

The claim is therefore: **an envelope covered by an anchored root existed no
later than the Bitcoin block that confirms the root, and has not been changed
since.**

## What it does not claim

- That an observation is *true* about the provider. It records fetched bytes,
  a hash over the assessed fields and a verdict; it does not infer intent.
- That a failed fetch is an absence. Collection failure is recorded as
  indeterminate and excluded from every absence count.
- Anything about time *between* observations. Streaks are bounded by the
  observation window (`first_seen`/`last_seen`).
- Resistance to a compromised observer key. The key is a trust anchor; if it
  leaks, historical anchored roots remain valid but new envelopes could be
  forged. Rotation is by publishing a new `trust_root.json` with the retiring
  key's fingerprint and its last sealed root.

## Reporting a vulnerability

Email info@croviatrust.com with a description and reproduction steps. Do not
open a public issue for an exploitable problem. Acknowledgment within 72 hours;
fix or public statement within 30 days.

Highest severity: a way to produce an envelope that verifies against the
published key without the key, or a ledger modification that leaves a sealed
root unchanged.
