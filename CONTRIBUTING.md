# Contributing

This repository is the Crovia Substrate: collectors, observer, sealer, anchoring
job and the Phase-0 post-processors behind the 2026 archive. Live observation of
absence happens in [TACET](https://github.com/croviatrust/countersign); if your
change is about silence proofs, predicates or witnesses, open it there.

## What is welcome here

- **Reproducibility.** Anything that lets a third party recompute a published
  figure from the public data files (`ops/phase0/`, `crovia-verify`).
- **Collector correctness.** A fetch that fails is *indeterminate*, never an
  absence; a content hash must cover exactly the fields that are assessed.
  Tests that pin these two rules are always accepted.
- **Schema fidelity.** `schemas/` is the contract with every public JSON file
  under `croviatrust.com/registry/data/`. Changes need a version bump and a
  note in the file's `schema` field.
- **Bringing the server pipeline into the repo.** `ops/phase0/README.md` lists
  what still runs only from `/opt/crovia/scripts`; porting one of those scripts
  here, with a test, is the most useful kind of pull request.

## Rules

1. Numbers are defined once, in
   [CANON.md](https://github.com/croviatrust/countersign/blob/main/CANON.md).
   A pull request that changes how a headline figure is computed also changes
   the canon, in the same change set.
2. No accusatory wording. The ledger records what was observed; it does not
   say a provider "hid" anything.
3. Tests that need the professional-tier `croviapro` package must be marked
   so they skip when it is absent (`tests/conftest.py` does this). The open
   suite stays green on a plain checkout.
4. One logical change per commit. Explain *why* in the message.

## Run the suite

```bash
pip install -e .
pytest tests -q
crovia --help
```

## Reporting problems

Data or reproducibility problems: open an issue with the file URL, the figure
you expected and the one you computed. Security problems: see `SECURITY.md`.
