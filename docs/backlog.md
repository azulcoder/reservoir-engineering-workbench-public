# Task backlog

Use each row as a bounded issue. Mark completion only after the acceptance evidence exists. The order is based on dependencies, not the attractiveness of the final figure.

Status column added at 0.2. "done" means the acceptance evidence exists in the tree and
has been re-run; it does not mean the task cannot be improved.

| ID | Status | Task | Dependencies | Acceptance evidence |
|---|---|---|---|---|
| 01 | done | Run the starter from a clean local directory and inspect its limitations | None | Test output, unchanged source, reproduced numerical summary |
| 02 | open | Verify repository CI after publishing to an account-controlled repository | 01 | Actual workflow logs for the configured matrix; no invented badge |
| 03 | done | Build a gas-properties evidence card from legitimate textbook access | 01 | Equation/page references, symbols, units and applicability limits |
| 04 | done | Acquire a minimal NIST reference query with documented conditions | 03 | Source/units/phase record and independent property comparison |
| 05 | done | Add an independent volumetric material-balance example | 03 | Literal or independently derived oracle and test |
| 06 | done | Add a distinct aquifer/variable-pore-volume counterexample | 05 | Governing balance, misleading simple fit and interpretation |
| 07 | done | Analyse pressure/Z error and short-history uncertainty | 05, 06 | Predeclared error model, scenario results and limitations |
| 08 | done | Release the PVT/material-balance case memo | 04–07 | Reviewed report, manifest, clean reproduction command |
| 09 | open | Implement an independently verified analytical PTA forward baseline | 03 | Dimensional derivation, exact/reference tests, scope boundaries |
| 10 | open | Add pressure/rate synchronization and correct test-time handling | 09 | Edge cases for rate changes and buildup assumptions |
| 11 | open | Analyse derivative noise, storage/skin ambiguity and alternatives | 09, 10 | Clean successful case and defensibly inconclusive case |
| 12 | open | Release a bounded gas-PTA case | 11 | Independent forward comparison and interpretation review |
| 13 | open | Install and identify a pinned OPM Flow environment | 01 | Actual executable/version, environment record and official source |
| 14 | open | Review and acquire a current pinned SPE1/SPE3 tree | 13 | File-level hashes, license decision and include-file inventory |
| 15 | open | Reproduce unmodified benchmark and investigate warnings | 14 | Execution logs, reference source, discrepancy register |
| 16 | open | Add conservation, timestep and controlled grid checks | 15 | Component inventories and justified numerical-sensitivity results |
| 17 | open | Define synthetic mature-gas decision alternatives | 08, 12, 16 | Protocol with fluid/support/constraint assumptions and holdout |
| 18 | open | Execute bounded history/forecast ensembles | 17 | Immutable manifests, failed-run accounting and untuned holdout |
| 19 | open | Write and review the capstone decision memo | 18 | Conditional recommendation, reversal condition and missing data |
| 20 | open | Add a separately licensed real-field QC extension | 08 | Provenance, reconciliation and oil/gas applicability boundary |
| 21 | open | Add optional sanding or subsidence screening | 19 | Legitimate source study, declared assumptions and no operating-limit claim |
| 22 | open | Repeat a case in legitimately licensed commercial software | Relevant case | Actual hands-on task log, matched assumptions and allowed evidence |

## Where 0.2 left it

Tasks 01 and 03 to 08 are done. The evidence for each is in `cases/A1` to `cases/A4`, in
`docs/evidence/`, and in the reference extract under `data/reference/`. Every case re-runs
into a fresh directory and reproduces its committed snapshot byte-identically.

Task 02 is the only cheap one left and it cannot be done from here: the CI workflow is
configured and pinned to verified commit SHAs, and its checks pass locally, but it has not
executed on a hosting account. Until it has, no badge belongs in the README.

## Next, and why in this order

The next milestone is task 09, the analytical pressure-transient forward baseline. It comes
before 13 (the simulator environment) for a reason worth stating: 09 needs nothing acquired,
nothing licensed and nothing downloaded, and it produces the independent forward reference
that tasks 10 to 12 all depend on. Installing a simulator first would be the more impressive
commit and the less useful one.

Three things Stage A surfaced that belong in the backlog rather than in a report:

| ID | Status | Task | Why it came up |
|---|---|---|---|
| 23 | open | Add error in cumulative production to the generators and exercise the Deming and York fits on it | A1 measured a one-for-one mapping from Gp bias into G, and no case simulates it. OLS assumes an error-free abscissa, so the reported standard error currently means something narrower than it appears to. |
| 24 | open | Pre-register a Cole-plot and intercept-mismatch diagnostic with the deviation-factor correlation deliberately mismatched between generator and analyst | A4 found that a Z-correlation mismatch fires the curvature detector harder than the aquifer does, so that detector's false-positive rate holds only under a condition no field analysis meets. |
| 25 | open | Add the geopressured / abnormally pressured case to the generators | Rock and connate-water compressibility curve p/Z and overestimate G with no aquifer present. A4 demonstrates one way the volumetric assumption fails; this is a second, and it is not in any generator. |

Tasks 13 to 22 remain future work, and nothing in this repository claims otherwise.