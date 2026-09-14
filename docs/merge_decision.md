# Merge record: starter into working repository

## What happened, in order

The starter archive was extracted into a separate directory after work had already begun
from `PLAN.md` alone in the working repository. Two trees therefore existed briefly. This
note records what each contained, what was taken from which, and why — so that nothing
looks like it appeared from nowhere.

## Reproduction of the starter before merging anything

The starter's own claims were checked before its code was reused, because a claim that has
not been reproduced is a claim, not a baseline.

| Claim in the plan | Reproduced | Observed |
|---|---|---|
| 38 tests pass | yes | `Ran 38 tests ... OK`, Python 3.13.2 |
| GIIP recovered with ~0.149 % error | yes | 0.149256357527916 % |
| Holdout pressure error ~0.065 % of initial pressure | yes | 0.06513844917821768 % |
| Demo output stable across runs | yes | regenerated `summary.json` is byte-identical to the committed `examples/synthetic_demo/summary.json` |

The starter is what it says it is. Its limitations are stated in its own files rather than
hidden, and its executed example reproduces exactly.

## What was taken from the starter, unchanged

These are the project's own record and there was no reason to rewrite them:

`PLAN.md`, `AGENTS.md`, `NOTICE.md`, `docs/backlog.md`, `docs/baseline_execution.md`,
`docs/case_protocol_template.md`, `docs/data_contract.md`, `docs/decision_memo_template.md`,
`docs/references.md`, `docs/role_prompts.md`, `docs/verification_plan.md`,
`docs/workflow_setup.md`, `.github/dependabot.yml`, `.github/pull_request_template.md`,
`configs/synthetic_volumetric_gas.json`, `examples/synthetic_demo/*`, `scripts/run_demo.py`,
`src/reservoir_lab/gas.py`, `tests/test_gas.py`, `tests/test_repository.py`,
`tests/test_workflow.py`, `data/raw/README.md`.

The executed example still reproduces byte-identically after the merge. That was the
acceptance condition for the merge, and it is checked by `tests/test_workflow.py`, which
came from the starter and was not modified.

## The one real conflict: unit system

The starter is written in SI — `pressure_pa`, `temperature_k`, `sm3`. The new PVT layer is in
field units, because every correlation it implements (Dranchuk–Abou-Kassem, Hall–Yarborough,
Lee–Gonzalez–Eakin, Standing, Sutton, Wichert–Aziz) was fitted and published in field units,
and re-expressing a fitted correlation in another unit system adds a conversion to every
coefficient for no benefit. The Stage C simulator decks are also FIELD-unit decks.

Resolving this by converting the starter to field units would have been wrong, and the reason
is worth stating because it determined the whole layout. Look at what the starter's functions
actually compute:

* `gas_fvf` is a ratio of two states, `(Z/Zsc)(T/Tsc)(Psc/P)`.
* `fit_volumetric_pz` fits `p/Z` against `Gp`.
* `relative_pseudopressure` integrates `2p/(mu Z)`.
* `log_time_derivative` differentiates with respect to `ln t`.
* `cumulative_step_volume` integrates a rate over intervals.
* `component_balance_error` returns a normalised residual.

Every one of those is a ratio, a derivative or an integral that holds in **any internally
consistent absolute-pressure, absolute-temperature system**. The starter's `_pa` and `_k`
suffixes assert more than its arithmetic requires. So the split is by *nature of the
quantity*, not by preference:

| Module | Unit policy | Why |
|---|---|---|
| `reservoir_lab.gas` | any consistent units, absolute P and T | ratios, derivatives and integrals; no fitted constant inside |
| `reservoir_lab.gas_properties` | field units only, named in every parameter | fitted correlations; meaningless outside the units they were fitted in |
| `reservoir_lab.units` | the explicit bridge | exact conversions, derived not transcribed |

Mixing the two categories in one module is how a unit error becomes invisible, so they stay
apart and each says which it is.

## Reconciled files

| File | Resolution |
|---|---|
| `scripts/check_repository.py` | New implementation kept; it adds credential-shape, authorship, local-path and line-length checks. The starter's `inspect(path, data)` entry point was **preserved as a compatible adapter** so the starter's eight infrastructure tests run unmodified, and the starter's `data/raw` policy and 5 MiB limit were carried over rather than replaced. |
| `scripts/check.py` | New implementation kept; adds hygiene integration and a guard that makes an empty test suite a failure rather than a pass. |
| `.gitignore` | Union of both, keeping the starter's `data/raw` carve-out and adding one for the reviewed reference extract. |
| `pyproject.toml` | New file kept — it adds ruff, mypy, pytest and optional dependency groups. The starter's distribution name `reservoir-performance-lab` and its coverage configuration were carried over; version moved to 0.2.0. |
| `.pre-commit-config.yaml` | New file kept; it is a superset, and adds a reference-digest check at pre-push. |
| `.github/workflows/ci.yml` | New file kept. See below. |
| `README.md` | Rewritten against the merged contents, since the starter's status table no longer describes what is here. |

## CI action pins

The starter pinned `actions/checkout` to v4.2.2 and `actions/setup-python` to v5.6.0. Both
SHAs were checked against the GitHub API and **both are correct**:

* `actions/checkout` v4.2.2 → `11bd71901bbe5b1630ceea73d27597364c9af683` — confirmed
* `actions/setup-python` v5.6.0 → `a26af69be951a213d495a4c3e4e4022e16d87065` — confirmed

They are, however, well behind. The current releases are `actions/checkout` v7.0.1 and
`actions/setup-python` v7.0.0, so the workflow now pins those, with the SHAs resolved the same
way:

* `actions/checkout` v7.0.1 → `3d3c42e5aac5ba805825da76410c181273ba90b1`
* `actions/setup-python` v7.0.0 → `5fda3b95a4ea91299a34e894583c3862153e4b97`

A pin is a maintenance obligation, not a guarantee. These need review whenever either action
publishes a security fix.

## What became of the starter tree

The merged repository is the one under git and is the only tree anything depends on. The
extracted starter archive was left untouched in its own directory; it is not a git
repository. Deleting it loses nothing, since everything it contained is either merged here
or recorded above.
