# CROVIA Floor Standard v1.1

## 1. Purpose

The CROVIA Floor Standard v1.1 defines how to compute, for each payout period,
a **Payout Floor** for every data provider.

The **Crovian Floor** of a provider `i` is the minimum payout that any payout
scheme can assign to `i` **without contradicting** the coverage constraints
recorded by CROVIA.

It does **not** say how much you *should* pay in total.
It says how low you **cannot** go without breaking your own coverage bounds.

---

## 2. Period inputs Ω(T)

For a period `T` (e.g. `2025-11`) and a total payout budget `B` (e.g. `1_000_000` EUR),
CROVIA considers, for each provider `i`:

- `coverage_bound_i` (FLOAT, (0,1]):
  an upper bound on the fraction of events (training or inference) in which
  data from provider `i` could have contributed during period `T`.

  In v1.1, if the Coverage & Witness Layer does not yet provide explicit
  coverage bounds, CROVIA may derive them from usage metrics (e.g. `topk`)
  or, in the worst case, conservatively set:

  coverage_bound_i = 1.0

- `eligible_i` (BOOL):
  indicates whether provider `i` is eligible for payouts in period `T`
  (not suspended, not revoked, etc.).

We denote the input set as:

Ω(T) = { (coverage_bound_i, eligible_i) } for i = 1..n

over all providers participating in the period.

---

## 3. Defendable payout space P(Ω,B)

A payout vector x = (x_1, ..., x_n) is **Crovian-defendable** if it satisfies:

1. Budget (BUD)

   sum_i x_i = B

2. Non-negativity (NN)

   x_i >= 0  for all i

3. Coverage (COV)

   x_i <= B * coverage_bound_i  for all i

4. Eligibility (ELG)

   if eligible_i is false then x_i = 0

The defendable payout space is:

P(Ω,B) = { x in R^n_{\>=0} | x satisfies BUD, NN, COV, ELG }

A necessary condition for P(Ω,B) to be non-empty is:

sum_{i with eligible_i = true} coverage_bound_i >= 1

---

## 4. Definition of the Crovian Floor

For each eligible provider i, the standard defines:

Floor_i(Ω,B) = min { x_i | x in P(Ω,B) }

Intuitively:

- we consider all defendable payout vectors x in P(Ω,B),
- for provider i, we ask how low its payout can go
  without breaking any constraint (budget, coverage, eligibility),
- that minimum is the Crovian Floor of provider i.

With the v1.1 constraints, let

C = sum over all eligible j of coverage_bound_j.

Assuming C >= 1, for each eligible provider k we can express the floor
in closed form:

Floor_k = max( 0, B * (1 - sum_{j != k} coverage_bound_j) )

If the sum of all coverage bounds of OTHER providers is already >= 1,
the floor of k becomes 0: coverage constraints alone do not force
a positive minimum for k.

### Implementation note (reference engine)

In real deployments, raw coverage bounds loaded from logs or CSV tables
may be incomplete or noisy. If the raw sum of coverage bounds over eligible
providers is < 1, a naive interpretation would make P(Ω,B) empty and
the standard would signal a configuration error.

The **reference CROVIA engine** is allowed to apply a conservative fallback,
for example:

- detecting coverage_sum < 1,
- lifting all coverage_bound_i to 1.0 for the period,

which results in all floors being 0.0 (no enforceable minimum derived
purely from coverage in that period). The JSON artifact still records the
resulting floors, and the situation can be audited.

---

## 5. Period floor artifact: floors_T.json

For each period T, CROVIA produces a machine-readable artifact:

data/floors_T.json  (for example: data/floors_2025-11.json)

with at least the following structure:

- period (string, YYYY-MM)
- budget_total_eur (float)
- coverage_sum (float)
- providers (array), where each element contains:

  - provider_id (string)
  - coverage_bound (float)
  - eligible (bool)
  - floor_eur (float or null)

Example (informal):

{
  "period": "2025-11",
  "budget_total_eur": 1000000.0,
  "coverage_sum": 1.35,
  "providers": [
    {
      "provider_id": "publisher_A",
      "coverage_bound": 0.93,
      "eligible": true,
      "floor_eur": 0.0
    },
    {
      "provider_id": "research_B",
      "coverage_bound": 0.22,
      "eligible": true,
      "floor_eur": 12345.67
    }
  ]
}

If the engine detects that coverage bounds are inconsistent with the budget
(e.g. coverage_sum < 1 and no fallback is applied), it may set floor_eur
to null for affected providers and emit an explicit warning in logs.

---

## 6. Crovian-consistent payout

Let Floor_i(Ω,B) be the floor computed for period T and budget B.

An actual payout vector y = (y_1, ..., y_n) is **Crovian-consistent
for period T** if:

1. sum_i y_i = B  (same budget as used for floors),
2. y_i >= 0 for all providers,
3. for every eligible provider i:

   y_i >= Floor_i(Ω,B)

In that case:

- y belongs to the defendable space P(Ω,B), and
- no provider is being paid below its Crovian minimum for that period.

In contractual terms, a clause may state:

"For each period T, the AI operator commits to pay each eligible provider
at least its Crovian Floor as published by CROVIA for that period."

---

## 7. Role for providers, AI operators and auditors

- For **providers**, Floor_i is a logically defendable **minimum dividend**
  implied by the coverage constraints recorded by CROVIA for that period.

- For **AI operators**, the Floor defines a clear lower bound:
  any internal payout scheme is acceptable as long as it does not assign
  y_i < Floor_i to any eligible provider.

- For **auditors and regulators**, Floors are **recomputable** from:

  - coverage bounds,
  - the period budget B,
  - the list of eligible providers.

This makes CROVIA Floors a useful tool for checking whether an AI
is paying below the minimum that can be justified by its own
coverage assumptions.
