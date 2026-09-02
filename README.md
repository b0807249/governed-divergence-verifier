# governed-divergence-verifier (toy)

A minimal, executable illustration of the Governed Divergence model
(Expectation–Decision–Observation reconciliation for cross-platform agent assets).
It accompanies the JSS New Ideas and Trends short paper.

**What it is:** the paper's three governance objects (P, R, O), the five reconciliation
invariants, the machine-contract and canonical-split assurance checks, a frozen implementation
of the manifest-and-hash baseline (B4.3), and a synthetic two-host repository with eight cases
(base, three load-bearing mutations, three benign controls, one blanket-exemption variant).

**What it is not:** an evaluation. The cases are designed by the authors; the table shows only
that the definitions are executable and that they give different verdicts from the baseline
where the paper says they should. Detection power, false-positive burden and maintenance cost
are the subject of the planned follow-up study, not of this repository.

## Run

```
py -3.12 run_cases.py            # prints the verdict table, writes results/results.md
py -3.12 -m unittest discover -s tests
```

Python 3.12, standard library only.

## Layout

```
pro/         P, R, O data model; scanner; assurance runners; five-invariant verifier
baseline/    B4.3: fan-out, versioned manifest, hash-drift checker, expiring waivers
cases.py     synthetic repository and the mutations, with expected verdicts
run_cases.py builds each case in a scratch directory and runs both checkers
tests/       unittest wrappers around the cases
results/     generated table (results.md)
```

## Frozen semantics worth knowing

- The baseline compares the current tree with the current manifest only; nothing compares
  manifest v_t with v_{t+1}. A waiver in the baseline exempts a hash mismatch for a path until
  it expires.
- In P/R/O, an unsupported surface class yields `UNVERIFIABLE`, never `PASS`.
- Non-support is recorded, not omitted: an incidence marked unsupported in P must point to a
  waiver decision in R; removing an incidence from P without such a waiver is silent shrinkage.
- Masks are inline (`volatile` output fields; host-wiring regions delimited by markers).
