# Baseline execution record

This file is append-only. The 0.1 record below is the starter's, kept unchanged because it
is the baseline the 0.2 work was checked against; the 0.2 record follows it. A superseded
claim is marked rather than rewritten.

---

## 0.1 baseline (starter)

### Environment and execution

Local interpreter: Python 3.13.5. Platform: Linux-6.18.44-x86_64-with-glibc2.41.
The preserved synthetic run records its actual timestamp in [run_manifest.json](../examples/synthetic_demo/run_manifest.json): `2026-09-13T05:44:32.944465+00:00`.

The following commands were executed locally from the repository root:

```bash
python scripts/check.py
python scripts/check_repository.py
python scripts/run_demo.py --out examples/synthetic_demo
python -m coverage run --branch --source=src/reservoir_lab scripts/check.py
python -m coverage report -m
```

The 38 test methods passed. The numerical-core coverage report showed 96% combined statement/branch coverage; this does not establish scientific validation or complete input-domain coverage. Coverage is an optional reporting tool, not a runtime dependency. The public-repository check passed for the distributed content; its limited secret and file-policy checks do not approve data rights or guarantee discovery of all private material.

### Synthetic numerical result

| Quantity | Observed result |
|---|---:|
| Known synthetic gas in place | 1,000,000,000 standard m3 |
| Fitted gas in place | 1,001,492,564 standard m3 |
| Absolute relative gas-in-place error | 0.1493% |
| Conditional holdout pressure RMSE | 16,284.6 Pa |
| Conditional holdout RMSE / initial pressure | 0.0651% |
| Training / holdout observations | 9 / 4 |
| Predeclared synthetic demonstration gates | PASS |

The holdout uses supplied synthetic Z values; it is not an independent production forecast. The generator and inverse share the volumetric model. Z follows an illustrative trend rather than a measured or calibrated EOS table. This demonstrates limited numerical self-consistency, not validation against an actual reservoir.

### Not executed or established

OPM Flow, MRST, ECLIPSE, Petrel, Saphir, external data acquisition, a compositional flash, a forward PTA model, field history matching, and mature-gas option optimization were not executed. No external field-data rights are granted by this repository. The optional uv/pre-commit installation steps have not been executed; no fabricated lockfile is supplied.

The GitHub Actions workflow is configured but has not run on a destination repository. Only local Python 3.13.5 is covered by this record; the proposed 3.11–3.13 matrix must be checked on GitHub. No peer review or operating approval is claimed.

The source tree was not a committed Git repository during the preserved example run, so its Git commit and dirty-state fields are null. Source and configuration SHA-256 values are recorded instead. Future runs in a real repository should record the actual commit and working-tree state.


---

## 0.2 execution record

### Environment

Python 3.13.2, CPython, macOS (Darwin 25.6.0, arm64). No third-party runtime packages.
`ruff` and `mypy` were run through `uvx`; neither is a runtime dependency.

### Commands executed

```bash
python3 scripts/check.py
python3 scripts/check_repository.py
python3 scripts/fetch_nist_reference.py --out data/reference            # network, once
python3 scripts/fetch_nist_reference.py --out data/reference --verify-only
python3 scripts/run_demo.py --out <fresh dir>
PYTHONPATH=src python3 cases/<case>/run.py --out artifacts/<case>/run-00N
ruff check src tests scripts cases
ruff format --check src tests scripts cases
mypy
```

### Observed

| Check | Result |
|---|---|
| Test suite | 633 run, 0 failed, 0 errored, 0 skipped, 0 expected failures |
| Repository hygiene | 97 files, 0 errors, 0 warnings |
| `ruff check` | clean |
| `ruff format --check` | 45 files already formatted |
| `mypy --strict` | no issues in 14 source files |
| Reference digests | 3 files verified against `MANIFEST.json` |
| 0.1 demonstration | regenerated `summary.json` byte-identical to the committed example |
| A1–A4 case runs | each re-run into a fresh directory reproduced its committed snapshot byte-identically |

### Reproduction of the 0.1 claims before merging

| 0.1 claim | Reproduced | Observed |
|---|---|---|
| 38 tests pass | yes | `Ran 38 tests ... OK` |
| GIIP error ~0.149 % | yes | 0.149256357527916 % |
| Holdout error ~0.065 % of initial pressure | yes | 0.06513844917821768 % |

### Review actually performed

An adversarial review pass was run against every module and every case study, and a second
pass confirmed the corrections. It found 56 confirmed defects, 33 circular tests and 38
reverse-engineered tolerances in the modules, and roughly a dozen unreproduced numbers and
two dozen overclaims across the four case reports. All are addressed in the tree; the case
reports carry their own audit trails under "What the referee changed".

This was not peer review. The passes were separate and adversarially framed, and the
reviewer re-derived and re-ran rather than re-reading, which is worth more than a checkbox
— but no second person participated, and nothing here should be described as reviewed by
one.

### Still not executed or established

OPM Flow, MRST, ECLIPSE, Petrel, Saphir. No field data acquired. No compositional flash, no
forward pressure-transient model, no simulator benchmark, no history match, no mature-gas
option study. The GitHub Actions workflow is configured, pinned to verified commit SHAs and
exercised locally in equivalent form; it has not run on a hosting account, so the 3.11 and
3.12 legs of the matrix are untested and no badge is displayed.
