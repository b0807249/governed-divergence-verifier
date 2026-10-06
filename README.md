# governed-divergence-verifier (toy)

A minimal, executable illustration of the Governed Divergence model
(Expectation–Decision–Observation reconciliation for cross-platform agent assets).
It accompanies the short paper *Declared, Not Assumed: Governed Divergence for
Cross-Platform Agent Assets* (Journal of Systems and Software, New Ideas and Trends
Paper; under submission).

**What it is:** the paper's three governance objects (P, R, O), the five reconciliation
invariants, the machine-contract and canonical-split assurance checks, a frozen implementation
of the manifest-and-hash baseline (B4.3), and a synthetic two-host repository with eight cases
(the base repository and seven mutations: M1, M2a, M2b and M3 from the three load-bearing
mutation families, with M2a and M2b also run against the baseline under a blanket exemption,
and the benign controls B1–B3).

**What it is not:** an evaluation. The cases were designed by the author; the table shows only
that the definitions are executable and that they give different verdicts from the baseline
where the paper says they should. Detection power, false-positive burden and maintenance cost
are the subject of the planned follow-up study, not of this repository.

## Run

```
py -3.12 run_cases.py            # prints the verdict table, writes results/results.md
py -3.12 -m unittest discover -s tests
```

Python 3.12, standard library only. On Linux or macOS use `python3.12` instead of `py -3.12`.

## Layout

```
pro/         P, R, O data model; scanner; assurance runners; five-invariant verifier
baseline/    B4.3: fan-out, versioned manifest, hash-drift checker, expiring exemptions
cases.py     synthetic repository and the mutations, with expected verdicts
run_cases.py builds each case in a scratch directory and runs both checkers
tests/       unittest wrappers around the cases
results/     generated table (results.md)
```

## Frozen semantics worth knowing

- The baseline compares the current tree with the current manifest only; nothing compares
  manifest v_t with v_{t+1}. An exemption in the baseline excuses a hash mismatch for a path
  until it expires.
- In P/R/O, an unsupported surface class yields `UNVERIFIABLE`, never `PASS`.
- Non-support is recorded, not omitted: an incidence marked unsupported in P must point to a
  waiver decision in R; removing an incidence from P without such a waiver is silent shrinkage.
- Masks are inline (`volatile` output fields; host-wiring regions delimited by markers).

## Known limits of the comparison

Every case in which the verifier departs from the baseline rests on something the baseline is
not given:

| Case | What the verifier has that the baseline does not |
|---|---|
| M1 silent shrinkage | the previous version of P (manifest history) |
| M2a / M2b | executed fixtures and a shared schema |
| M3 unknown surface | a scanner capability map |
| B1 / B2 benign controls | normalization before comparison |

A baseline that compared successive manifest versions and required approval for removed rows
would also flag M1, and a hash over normalized or parsed content would also pass B1 and B2.
The paper's claim is not that these mechanisms are new, but that the model makes their absence
a violation rather than leaving it to configuration. The follow-up study adds a history-aware
baseline variant to test whether that obligation is worth its cost.

## Citation

See `CITATION.cff`. Licensed under the MIT License (`LICENSE`).
