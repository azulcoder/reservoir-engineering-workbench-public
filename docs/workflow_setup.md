# Workflow setup

## Start without external dependencies

From the repository root, run:

```bash
python scripts/check.py
python scripts/check_repository.py
python scripts/run_demo.py --out artifacts/my-first-run
```

These commands require Python 3.11 or later and use only the standard library. Output directories are deliberately not overwritten. The supplied source-import test runner verifies the starter; a later packaged distribution should also be tested after installation in a clean environment.

## Optional dependency locking and hooks

When a reviewed uv installation is available, initialize the actual development dependency and lockfile on your own machine:

```bash
uv add --dev pre-commit
uv sync --locked
uv run --locked pre-commit install --hook-type pre-commit --hook-type pre-push
```

Those steps modify `pyproject.toml` and produce a real `uv.lock`; review and commit both together. They have not been executed as part of the dependency-free baseline. Resolve scientific dependencies only when the case needs them and rerun the tests after each reviewed update.

The local pre-commit hook scans the complete staged tree for selected prohibited files and patterns. The pre-push hook runs the tests. Run the scripts directly whenever hooks are unavailable. A hook can be bypassed; it is not a substitute for CI or manual data-rights review.

## GitHub setup

Create an empty repository under an account you control, then initialize or connect this source tree using your normal authenticated Git workflow. Review every staged file before the first push. Do not commit raw third-party data, access tokens, temporary signed URLs, or licensed software.

The included workflow uses official actions pinned to specific commits and a read-only contents token. After pushing, inspect the actual results on Python 3.11, 3.12 and 3.13. Local baseline testing covered Python 3.13.5 only. The workflow does not create a remote repository, configure account permissions or set branch protection automatically.

Before displaying a passing badge, confirm an actual successful workflow on the destination default branch. Enable appropriate protected-branch/required-check settings where available. Review proposed action updates; preserve a reproducible known-good configuration rather than treating a pin as permanent maintenance.

## Simulator environment

OPM Flow and MRST are not installed or executed by the starter. Choose an installation path from official project instructions appropriate to your operating system, pin the executable/container identity, and verify it before retrieving a reviewed benchmark. Do not copy arbitrary install scripts from untrusted notebooks. Record the deck revision, include-file hashes, parser warnings and reference comparison before calling a study reproduced.
