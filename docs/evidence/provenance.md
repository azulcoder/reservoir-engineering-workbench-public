# Evidence card: Tooling pins and repository facts

> Each card records what an implementer needs, where it came from, and how far it was
> verified. A card is not an authority: it is a statement of evidence with its access
> level attached. Items marked unverified are unverified, and the implementation must
> treat them as such.

**Adversarial review verdict:** `SOUND_WITH_CORRECTIONS`  
**Corrections applied:** 7  
**Items left unverified:** 7

## Summary

Both SHA claims in the plan document are CONFIRMED by two independent retrieval methods (GitHub REST API and `git ls-remote` against the canonical remote): actions/checkout v4.2.2 = 11bd71901bbe5b1630ceea73d27597364c9af683 and actions/setup-python v5.6.0 = a26af69be951a213d495a4c3e4e4022e16d87065. Both are now far behind: latest is actions/checkout v7.0.1 (3d3c42e5aac5ba805825da76410c181273ba90b1) and actions/setup-python v7.0.0 (5fda3b95a4ea91299a34e894583c3862153e4b97). The plan's OPM Flow "2026.04" is CORRECT and is the current latest (tag release/2026.04/final, published 2026-05-20); OPM uses a YYYY.MM calendar scheme on a roughly semi-annual April/October cadence. Two items need the implementer's attention as PARTIAL REFUTATIONS. First, `persist-credentials: false` is a genuine first-party input on actions/checkout (documented in its README, default true) and a widespread hardening convention, but I could NOT find it recommended anywhere in GitHub's official secure-use security reference or in the OpenSSF Scorecard checks document — do not cite it as "official GitHub guidance". Second, NIST Chemistry WebBook data is NOT public domain: the site carries "© 2026 by the U.S. Secretary of Commerce ... All rights reserved" and the SRD terms state values may not be reproduced or stored in a retrieval system without prior permission, so hard-coding retrieved WebBook values into a test suite is a licensing decision, not a free action. NIST's methane EOS is Setzmann & Wagner (1991) as expected, but the viscosity model is Quinones-Cisneros, Huber & Deiters (unpublished, 2011) — not the older Younglove & Ely correlation that is commonly and wrongly assumed.

## Equations

### Hardened GitHub Actions workflow skeleton (permissions + SHA pin + persist-credentials)

```
name: ci
on: [push, pull_request]

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
        with:
          persist-credentials: false
      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065  # v5.6.0
        with:
          python-version: '3.12'
```

*Unit system:* N/A - YAML workflow syntax (GitHub Actions)

| Symbol | Meaning | Units |
|---|---|---|
| `permissions (workflow level)` | GITHUB_TOKEN scopes granted to every job. Per GitHub workflow-syntax docs: 'when you specify access for any of these scopes, all of those that are not specified are set to none' - so `contents: read` alone reduces all other scopes to none. | enum: read | write | none (per scope); or read-all | write-all |
| `uses: <owner>/<repo>@<sha>` | Action reference pinned to a full-length 40-hex-character commit SHA. GitHub: 'Pinning an action to a full-length commit SHA is currently the only way to use an action as an immutable release.' | 40 lowercase hex characters (SHA-1) |
| `persist-credentials` | actions/checkout input: 'Whether to configure the token or SSH key with the local git config.' Setting false prevents the GITHUB_TOKEN being left available to all later steps in the job. | boolean; DEFAULT true |

Assumptions:

- The trailing `# v4.2.2` comment is decorative only - it is not verified by the runner. Dependabot/Renovate parse it to propose updates, so keep it accurate but never trust it as a security control.
- `permissions: contents: read` at workflow level is sufficient for a test/lint workflow. Any job needing to push, comment on PRs, upload SARIF, or use OIDC must re-declare a wider `permissions` block at JOB level, which overrides the workflow level.
- persist-credentials: false breaks any step that does `git push`, `git fetch` of private submodules, or tools (e.g. reviewdog) that reuse the persisted credential. Only set it on checkouts that do not push.
- Lightweight-vs-annotated tags: all four tags checked (v4.2.2, v5.6.0, v7.0.1, v7.0.0) are LIGHTWEIGHT - `git ls-remote` returned no peeled `^{}` line - so the ref SHA equals the commit SHA directly. For an annotated tag the ref SHA is the tag object, and the commit SHA is the peeled `^{}` value; pinning the wrong one fails the run.

*Source:* GitHub Docs, 'Secure use reference' https://docs.github.com/en/actions/reference/security/secure-use ; GitHub Docs, 'Workflow syntax - permissions' https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions ; actions/checkout README at tag v7.0.1 https://raw.githubusercontent.com/actions/checkout/v7.0.1/README.md  
*Access:* full-text retrieved

### pre-commit: local repo hook at the pre-commit stage

```
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: ruff check --force-exclude
        language: system
        types_or: [python, pyi]
        require_serial: true
        stages: [pre-commit]
```

*Unit system:* N/A - YAML (.pre-commit-config.yaml schema)

| Symbol | Meaning | Units |
|---|---|---|
| `repo: local` | Sentinel value telling pre-commit the hooks are defined inline in this file rather than cloned from a remote repository. A `local` repo must NOT carry a `rev:` key. | literal string 'local' |
| `stages` | Which git hook(s) this hook runs at. Current valid values match the git hook names exactly. | list of: commit-msg, post-checkout, post-commit, post-merge, post-rewrite, pre-commit, pre-merge-commit, pre-push, pre-rebase, prepare-commit-msg, manual |
| `language: system` | Run `entry` using the already-installed executable on PATH; pre-commit creates no isolated environment. Appropriate when the tool comes from the project's own dev environment. | enum (system, python, script, docker_image, fail, ...) |
| `require_serial` | Run the hook once with all files rather than sharding across parallel processes. | boolean, default false |

Assumptions:

- CONFIRMED this session: the stage names were renamed. pre-commit.com states verbatim: 'The values of `stages` match the hook names. Previously, `commit`, `push`, and `merge-commit` matched `pre-commit`, `pre-push`, and `pre-merge-commit` respectively.' The rename landed in pre-commit 3.2.0. Use `pre-commit` / `pre-push`; the legacy `commit` / `push` names are deprecated.
- `language: system` requires the tool to exist on PATH at hook time. If CI runs pre-commit in a bare container, prefer a pinned `repo:`+`rev:` remote hook or `language: python` with `additional_dependencies` so the version is reproducible.
- A hook with no `stages` key defaults to running at every stage the hook declares support for, which in practice means it runs on pre-commit.

*Source:* pre-commit.com official documentation (https://pre-commit.com/), sections on hook `stages` and `repo: local`  
*Access:* full-text retrieved

### pre-commit: local repo hook at the pre-push stage (expensive checks)

```
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-fast
        name: pytest (fast suite)
        entry: pytest -q -m "not slow"
        language: system
        types: [python]
        pass_filenames: false
        always_run: true
        stages: [pre-push]
```

*Unit system:* N/A - YAML (.pre-commit-config.yaml schema)

| Symbol | Meaning | Units |
|---|---|---|
| `stages: [pre-push]` | Hook runs only on `git push`, not on `git commit`. Correct home for a test suite or a slow numerical regression check. | list containing the literal 'pre-push' |
| `pass_filenames` | When false, pre-commit does not append the staged filenames to `entry`. Required for pytest, which must select tests itself rather than be handed changed source files. | boolean, default true |
| `always_run` | Run the hook even when no files matching `types`/`files` changed. | boolean, default false |

Assumptions:

- The pre-push git hook must actually be installed: `pre-commit install --hook-type pre-push` (or `default_install_hook_types: [pre-commit, pre-push]` at the top of the config). A plain `pre-commit install` installs ONLY the pre-commit hook, so a pre-push hook silently never fires. This is the single most common defect with this pattern.
- `entry` is split on whitespace, not run through a shell - so shell metacharacters, pipes and globs in `entry` do not work. Wrap anything shell-like in a script or use `language: script`.

*Source:* pre-commit.com official documentation (https://pre-commit.com/), hook `stages` / `pass_filenames` / `always_run` reference  
*Access:* full-text retrieved

### Minimal src-layout pyproject.toml with extras and PEP 735 dependency groups

```
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "gas-reservoir-lab"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []          # dependency-free runtime, by design

[project.optional-dependencies]   # extras: SHIPPED in package metadata
plots = ["matplotlib>=3.8"]

[dependency-groups]               # PEP 735: dev only, NOT shipped
dev = ["pytest>=8", "ruff"]
docs = ["sphinx"]

# src layout:
# .
# |- pyproject.toml
# |- src/
# |   |- gas_reservoir_lab/
# |       |- __init__.py
# |- tests/
```

*Unit system:* N/A - TOML (PEP 517/518/621/735)

| Symbol | Meaning | Units |
|---|---|---|
| `[build-system].requires / build-backend` | PEP 518/517 build front-end contract. PyPA: 'The [build-system] table is strongly recommended. It allows you to declare which build backend you use and which other dependencies are needed to build your project.' | list of PEP 508 requirement strings / dotted module path string |
| `[project].name` | Distribution name. PyPA: 'This field is required and is the only field that cannot be marked as dynamic.' | string (PEP 503 normalizable) |
| `[project].version` | PyPA: 'This field is required, although it is often marked as dynamic.' | string (PEP 440 version) |
| `[project.optional-dependencies]` | Extras. Installed as `pip install pkg[plots]`. These DO become part of published package metadata and are visible to downstream consumers. | table of extra-name -> list of PEP 508 strings |
| `[dependency-groups]` | PEP 735 groups. Spec: 'Build backends MUST NOT include Dependency Group data in built distributions as package metadata.' Development-only; there is no standard end-user install syntax, tools provide their own (e.g. `uv sync --group dev`, `pip install --group dev`). | table of group-name -> list of PEP 508 strings or {include-group = "..."} tables |

Assumptions:

- src layout rationale, quoted from PyPA: it gives import isolation because 'if an import package exists in the current working directory with the same name as an installed import package, the variant from the current working directory will be used' - so a flat layout can silently test un-built source. It also means the project MUST be installed before running code.
- With hatchling and a package directory at src/<normalized_name>/, package discovery is automatic in the common case. I did NOT retrieve hatchling's discovery rules this session - see uncertainties. If the import name differs from the distribution name, declare it explicitly: [tool.hatch.build.targets.wheel] packages = ["src/gas_reservoir_lab"].
- With setuptools instead of hatchling, src layout is NOT automatic in all versions - add [tool.setuptools.packages.find] where = ["src"]. Not retrieved this session.
- PEP 735 dependency groups require a recent front-end. uv supports them; pip gained `--group` relatively recently. If the repo must support an old pip, keep dev deps in an extra instead and accept that they appear in published metadata.

*Source:* PyPA Python Packaging User Guide, 'Writing your pyproject.toml' https://packaging.python.org/en/latest/guides/writing-pyproject-toml/ ; 'src layout vs flat layout' https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/ ; PyPA spec 'Dependency Groups' (PEP 735) https://packaging.python.org/en/latest/specifications/dependency-groups/  
*Access:* full-text retrieved

### uv lockfile semantics: lock vs sync --locked vs sync --frozen (decision rule)

```
uv lock            -> resolve dependencies and CREATE/UPDATE uv.lock (writes)
uv lock --check    -> "Asserts that the `uv.lock` would remain unchanged after a
                      resolution. If the lockfile is missing or needs to be
                      updated, uv will exit with an error."  (== --locked)

uv sync --locked   -> "Assert that the `uv.lock` will remain unchanged.
                      Requires that the lockfile is up-to-date. If the lockfile
                      is missing or needs to be updated, uv will exit with an
                      error."        [env: UV_LOCKED]   <-- USE THIS IN CI

uv sync --frozen   -> "Sync without updating the `uv.lock` file. Instead of
                      checking if the lockfile is up-to-date, uses the versions
                      in the lockfile as the source of truth. If the lockfile is
                      missing, uv will exit with an error. If the `pyproject.toml`
                      includes changes to dependencies that have not been included
                      in the lockfile yet, they will not be present in the
                      environment."  [env: UV_FROZEN]
```

*Unit system:* N/A - CLI semantics, uv 0.11.7

| Symbol | Meaning | Units |
|---|---|---|
| `uv lock` | Resolution step. Mutates uv.lock. Must not appear in a verification CI job, because it will happily paper over a stale lockfile. | command; exit 0 on success |
| `--locked` | Verify-then-install. Fails the build if pyproject.toml and uv.lock have drifted apart. This is the flag that makes CI a genuine reproducibility gate. | flag; env UV_LOCKED=1 |
| `--frozen` | Install-without-verifying. Faster, but drift is SILENT: a newly added dependency in pyproject.toml is simply absent from the environment, producing a confusing ImportError rather than a lockfile error. | flag; env UV_FROZEN=1 |

Assumptions:

- Both --locked and --frozen error if uv.lock is missing entirely. They differ only in whether staleness is checked.
- The practical rule: `uv lock` on a developer machine when dependencies change; `uv sync --locked` in CI; `--frozen` only in a container image whose lockfile was already validated upstream, where you are trading the check for startup latency.
- `uv lock --check` is documented as 'Equivalent to `--locked`'. Note the separate `--check-exists` flag, which asserts only that a uv.lock exists WITHOUT checking freshness - confusingly it binds env var UV_FROZEN.
- Flag text captured from uv 0.11.7 installed locally. Wording may drift in later uv versions; the semantics have been stable.

*Source:* uv 0.11.7 built-in help (`uv help sync`, `uv help lock`) executed locally this session; cross-checked against Astral docs https://docs.astral.sh/uv/concepts/projects/sync/  
*Access:* full-text retrieved

## Constants

| Name | Value | Units | Source | How verified |
|---|---|---|---|---|
| actions/checkout tag v4.2.2 -> commit SHA (PLAN CLAIM: CONFIRMED) | `11bd71901bbe5b1630ceea73d27597364c9af683` | 40-hex-char Git SHA-1; lightweight tag (ref SHA == commit SHA) | GitHub REST API https://api.github.com/repos/actions/checkout/git/ref/tags/v4.2.2 (object.type = "commit") AND `git ls-remote https://github.com/actions/checkout.git 'refs/tags/v4.2.2*'` | CONFIRMED - retrieved 2026-09-13 by two independent methods (REST API and git protocol against the canonical remote), byte-for-byte identical to the plan document's claim. No peeled ^{} ref returned, so the tag is lightweight and this SHA is directly usable in `uses:`. |
| actions/setup-python tag v5.6.0 -> commit SHA (PLAN CLAIM: CONFIRMED) | `a26af69be951a213d495a4c3e4e4022e16d87065` | 40-hex-char Git SHA-1; lightweight tag | GitHub REST API https://api.github.com/repos/actions/setup-python/git/ref/tags/v5.6.0 (object.type = "commit") AND `git ls-remote https://github.com/actions/setup-python.git 'refs/tags/v5.6.0*'` | CONFIRMED - retrieved 2026-09-13 by two independent methods, byte-for-byte identical to the plan document's claim. |
| actions/checkout - current latest release tag | `v7.0.1 (published 2026-07-20T15:10:05Z)` | Git tag name | https://api.github.com/repos/actions/checkout/releases/latest | Retrieved 2026-09-13 via GitHub REST API releases/latest endpoint. Time-varying by nature - re-check before pinning. |
| actions/checkout v7.0.1 -> commit SHA | `3d3c42e5aac5ba805825da76410c181273ba90b1` | 40-hex-char Git SHA-1; lightweight tag | `git ls-remote --tags https://github.com/actions/checkout.git` | Retrieved 2026-09-13 via git protocol. Single method (REST API was used for the release metadata, ls-remote for the SHA). The floating major tag `v7` currently points at this same SHA, which is consistent with v7.0.1 being the newest v7. |
| actions/checkout v7.0.0 -> commit SHA | `9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0` | 40-hex-char Git SHA-1 | `git ls-remote --tags https://github.com/actions/checkout.git` | Retrieved 2026-09-13 via git protocol. Recorded only to demonstrate that v7 != v7.0.0; do not pin this in preference to v7.0.1. |
| actions/checkout v6.1.0 -> commit SHA (most recent v6, conservative upgrade target) | `d23441a48e516b6c34aea4fa41551a30e30af803` | 40-hex-char Git SHA-1 | `git ls-remote --tags https://github.com/actions/checkout.git` | Retrieved 2026-09-13 via git protocol, single method. |
| actions/setup-python - current latest release tag | `v7.0.0 (published 2026-07-20T03:15:01Z)` | Git tag name | https://api.github.com/repos/actions/setup-python/releases/latest | Retrieved 2026-09-13 via GitHub REST API releases/latest. Release notes mention migration to ESM and dependency upgrades. |
| actions/setup-python v7.0.0 -> commit SHA | `5fda3b95a4ea91299a34e894583c3862153e4b97` | 40-hex-char Git SHA-1; lightweight tag | `git ls-remote https://github.com/actions/setup-python.git 'refs/tags/v7.0.0*'` | Retrieved 2026-09-13 via git protocol; the floating `v7` tag resolves to the same SHA, a weak consistency cross-check. |
| actions/setup-python v6.3.0 -> commit SHA (latest v6; floating v6 points here) | `ece7cb06caefa5fff74198d8649806c4678c61a1` | 40-hex-char Git SHA-1 | `git ls-remote --tags https://github.com/actions/setup-python.git` | Retrieved 2026-09-13 via git protocol. Note the floating `v6` tag and `v6.3.0` share this SHA, confirming v6.3.0 is the v6 line tip. |
| OPM Flow (OPM/opm-simulators) - latest release (PLAN CLAIM 2026.04: CONFIRMED) | `2026.04, tag `release/2026.04/final`, published 2026-05-20T14:13:35Z, prerelease = false` | YYYY.MM calendar version | https://api.github.com/repos/OPM/opm-simulators/releases?per_page=10 AND https://opm-project.org/?page_id=36 | CONFIRMED - retrieved 2026-09-13 from the GitHub releases API and cross-checked against the OPM project website news page, which announces 'New Release 2026.04' (announced 2026-05-21). |
| OPM release numbering scheme and cadence | `YYYY.MM calendar versioning; git tags of the form `release/<YYYY.MM>/final`; approximately semi-annual (April and October cycles). Three most recent: 2026.04, 2025.10, 2025.04.` | N/A | https://api.github.com/repos/OPM/opm-simulators/releases (tag_name values) and https://opm-project.org/?page_id=36 | Retrieved 2026-09-13. The YYYY.MM pattern and the `release/*/final` tag form are directly observed in the API output. NOTE: the version number is the nominal cycle month (2026.04), while the actual publication date is later (2026-05-20) - do not infer the release date from the version number. |
| pre-commit version that renamed hook stages | `3.2.0` | semantic version | https://pre-commit.com/ (stages documentation) | Retrieved 2026-09-13 from pre-commit.com. The site states verbatim that 'Previously, `commit`, `push`, and `merge-commit` matched `pre-commit`, `pre-push`, and `pre-merge-commit` respectively', with the change attributed to 3.2.0. CURRENT NAMES ARE `pre-commit` / `pre-push` - the plan should not use legacy `commit`/`push`. |
| uv version against which the lock/sync flag semantics were verified | `0.11.7 (9d177269e 2026-04-15 aarch64-apple-darwin)` | semantic version | `uv --version` on the local machine | Executed locally 2026-09-13. Flag help text quoted in the equations section comes from this exact binary via `uv help sync` / `uv help lock`. |
| NIST Chemistry WebBook - methane reference equation of state | `Setzmann, U. and Wagner, W. (1991)` | N/A (citation) | https://webbook.nist.gov/cgi/fluid.cgi?ID=C74828 isotherm output, references block | Retrieved 2026-09-13. Verbatim: 'Setzmann, U. and Wagner, W., A New Equation of State and Tables of Thermodynamic Properties for Methane Covering the Range from the Melting Line to 625 K at Pressures up to 1000 MPa, J. Phys. Chem. Ref. Data, 20(6):1061-1151, 1991.' |
| NIST Chemistry WebBook - methane viscosity model (CORRECTS A COMMON ASSUMPTION) | `Quinones-Cisneros, S.E., Huber, M.L., and Deiters, U.K., unpublished work, 2011` | N/A (citation) | https://webbook.nist.gov/cgi/fluid.cgi?ID=C74828 isotherm output, references block | Retrieved 2026-09-13, quoted verbatim from the WebBook reference block. This REFUTES the widespread assumption that WebBook methane viscosity comes from Younglove & Ely (1987). Note it is cited as UNPUBLISHED work, so there is no peer-reviewed paper to audit the coefficients against - a real limitation if the repo wants a traceable viscosity reference. |
| NIST Chemistry WebBook - methane thermal conductivity model | `Friend, D.G., Ely, J.F., and Ingham, H., NIST Technical Note 1325, 1989` | N/A (citation) | https://webbook.nist.gov/cgi/fluid.cgi?ID=C74828 isotherm output, references block | Retrieved 2026-09-13, verbatim: 'Friend, D.G., Ely, J.F., and Ingham, H., Tables for the Thermophysical Properties of Methane, NIST Technical Note 1325, 1989.' |
| NIST Chemistry WebBook copyright status (NOT public domain) | `© 2026 by the U.S. Secretary of Commerce on behalf of the United States of America. All rights reserved.` | N/A (licence) | https://webbook.nist.gov/chemistry/ footer, and https://www.nist.gov/srd/public-law | Retrieved 2026-09-13 from both the WebBook landing page and the NIST SRD public-law page. The SRD page states: 'None of our SRD may be reproduced, stored in a retrieval system or transmitted, in any form or by any means, electronic, mechanical, photocopying, recording or otherwise, without prior permission.' See uncertainties - I could NOT retrieve an explicit fair-use/small-extract carve-out. |
| actions/checkout `persist-credentials` default | `true` | boolean | https://raw.githubusercontent.com/actions/checkout/v7.0.1/README.md | Retrieved 2026-09-13 from the action's own README at the v7.0.1 tag. Verbatim input description: 'Whether to configure the token or SSH key with the local git config. Default: true'. The v6 release notes add: 'Improved credential security: persist-credentials now stores credentials in a separate file under $RUNNER_TEMP instead of directly in .git/config'. |

## Validity ranges

- Commit SHAs are immutable content addresses and are valid indefinitely ONCE the tag-to-SHA binding is recorded. The BINDING itself is not immutable: all four tags verified are lightweight and can be force-moved by a maintainer. The SHA you pin stays what you pinned; it is the human-readable comment `# v4.2.2` that can silently become a lie.
- 'Latest release' facts (checkout v7.0.1, setup-python v7.0.0, OPM 2026.04) are true as of 2026-09-13 and will expire. Re-verify before any release of this repository.
- actions/checkout v4.2.2 and setup-python v5.6.0 are Node 20 era actions. GitHub has been retiring Node 20 on hosted runners; a workflow pinned this far back may begin emitting deprecation annotations or fail outright on future runner images. The pin is verified-correct but is a maintenance liability, not a permanent resting place.
- actions/checkout v5+ requires a minimum Actions Runner version (the README states v5 needs runner >= v2.327.1). Self-hosted runners below that will fail on modern pins. I did not retrieve the specific minimum for v7 - assume it is at least as high.
- pre-commit stage names `pre-commit`/`pre-push` require pre-commit >= 3.2.0. Configs using them will error on older pre-commit; configs using legacy `commit`/`push` will warn (and eventually error) on newer pre-commit. Set `minimum_pre_commit_version` in the config if you need the guard.
- PEP 735 `[dependency-groups]` requires a front-end that implements it (uv, recent pip with `--group`, recent Hatch). On an older toolchain the table is silently ignored, which means dev dependencies quietly do not install.
- The NIST methane numbers quoted below are single-phase supercritical gas at T = 300 K (above the 190.564 K critical temperature), P = 1-10 MPa. Setzmann & Wagner is valid from the melting line to 625 K and to 1000 MPa, per its own title; the viscosity and thermal conductivity models have narrower, separately-stated ranges that I did not retrieve.
- OPM Flow 2026.04 is a source release; binary package availability for a given Ubuntu/RHEL version lags and is not guaranteed for every distro at release time.

## Failure modes

- PINNING A TAG NAME INSTEAD OF A SHA (`actions/checkout@v4`) defeats the entire exercise - a mutable tag can be repointed at malicious code by anyone who compromises the action repo. GitHub: 'Pinning an action to a full-length commit SHA is currently the only way to use an action as an immutable release.'
- PINNING A SHORT SHA. Must be the full 40 characters. Short SHAs are ambiguity-prone and are not accepted as an immutable pin.
- PINNING AN ANNOTATED TAG'S TAG-OBJECT SHA instead of the commit SHA. Not a hazard for the four tags verified here (all lightweight), but it will bite on other actions. Always check for a peeled `refs/tags/X^{}` line in `git ls-remote` and pin the peeled value when present.
- TRUSTING THE `# v4.2.2` COMMENT. The runner ignores it. A stale or forged comment next to a correct SHA is harmless; a correct comment next to a wrong SHA is a supply-chain incident. Verify SHA-first, comment-second.
- PINNING A SHA FROM A FORK. GitHub's guidance warns to verify the SHA originates from the authentic repository, not a fork. A fork's commit SHA is syntactically valid and will resolve - `uses: actions/checkout@<sha-from-a-fork>` can fail closed or, worse, not fail at all depending on reachability.
- SETTING `permissions: contents: read` AT WORKFLOW LEVEL AND THEN NEEDING MORE. Because unspecified scopes become `none`, a job that uploads SARIF (needs security-events: write), comments on a PR (pull-requests: write), or uses OIDC (id-token: write) will fail with an opaque 403. Fix by adding a job-level `permissions` block, not by widening the workflow-level one.
- `persist-credentials: false` BREAKING PUSH-BASED JOBS. Release automation, gh-pages deploys, backport bots and reviewdog all need the persisted credential. Apply the flag per-checkout, not blanket.
- CITING `persist-credentials: false` AS OFFICIAL GITHUB SECURITY GUIDANCE. I searched GitHub's 'Secure use reference' page and the string does not appear anywhere on it, nor does '.git/config'. An adversarial reviewer will catch this. Cite the actions/checkout README (first-party, documents the input) and describe the recommendation as community/defense-in-depth practice.
- USING pre-commit STAGE NAMES `commit`/`push`. These are the legacy names, deprecated since 3.2.0.
- RUNNING `pre-commit install` AND EXPECTING pre-push HOOKS TO FIRE. They will not. You need `pre-commit install --hook-type pre-push` or `default_install_hook_types: [pre-commit, pre-push]`. The failure is silent - the hook simply never runs, and the repo appears to pass.
- USING `uv sync --frozen` IN CI AS A REPRODUCIBILITY GATE. It is not one. Per uv's own help: 'If the pyproject.toml includes changes to dependencies that have not been included in the lockfile yet, they will not be present in the environment.' The build then fails with an ImportError far from the root cause, or passes while testing the wrong dependency set. Use `--locked`.
- RUNNING `uv lock` IN CI. It writes a fresh lockfile, so a stale committed lockfile can never fail the build. This is the inverse defect of the above.
- FLAT LAYOUT INSTEAD OF src LAYOUT. Per PyPA, Python puts the CWD first on sys.path, so tests run from the repo root import the unbuilt source tree rather than the installed package - packaging bugs (missing data files, wrong package_data, a module never added to the wheel) become invisible until a user installs.
- HARD-CODING NIST WebBook VALUES INTO THE TEST SUITE WITHOUT A LICENSING DECISION. WebBook output is copyrighted ('All rights reserved'), not public domain. See uncertainties.
- ASSUMING WebBook METHANE VISCOSITY IS YOUNGLOVE & ELY. It is not; it is Quinones-Cisneros, Huber & Deiters (2011, unpublished). Any code comment claiming otherwise is wrong.
- TREATING OPM's VERSION NUMBER AS A RELEASE DATE. 2026.04 was published 2026-05-20.

## Numerical pitfalls

- The methane fixture values above are MASS DENSITY in kg/m3, not molar density and not z-factor. Converting to z requires the molar mass; using 16 g/mol instead of 16.04246 g/mol introduces a ~0.27% systematic bias that will look like a real discrepancy against a reference EOS but is purely a units error.
- NIST WebBook pressures are ABSOLUTE (MPa), and temperatures ABSOLUTE (K). Any field-units layer in this repository converting to psia/degR must not silently mix psig with psia - a 14.7 psi offset is a large fraction of a low-pressure depletion calculation.
- The quoted WebBook values carry 5 significant digits because Digits=5 was requested in the query URL. Do not assert equality to more digits than were requested, and do not assume the 5th digit is accurate to the underlying EOS - it is the display precision, not an uncertainty statement.
- A cubic EOS will disagree with Setzmann-Wagner by percent-level amounts at 10 MPa. Choosing a tight tolerance against these fixtures and then loosening it when a cubic EOS fails is exactly the kind of tolerance-fitting that hides real bugs. Decide the tolerance from the model class BEFORE running the test.
- Git SHA comparison must be case-normalized and whitespace-stripped if any pin-checking script is written; `git ls-remote` output is tab-separated, and a naive split on spaces will not parse it.
- 40-hex-character SHAs are strings, never numbers. Any tooling that coerces them (a YAML parser seeing a SHA that happens to be all digits, or a spreadsheet) will mangle them. A SHA consisting only of decimal digits is rare but legal - quote SHAs in any data file.

## Implementation notes

- PIN DECISION: the plan's two SHAs are correct, so there is no correctness reason to change them. But both are behind by two major versions. Recommended action is a deliberate upgrade to actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 (v7.0.1) and actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 (v7.0.0), taken as its own commit so a CI break is attributable. If the team prefers stability over currency, keeping the verified v4.2.2/v5.6.0 pins is defensible short-term but should carry a dated TODO.
- Reproduce every SHA locally before committing - it takes seconds and removes all dependence on my retrieval: `git ls-remote https://github.com/actions/checkout.git 'refs/tags/v4.2.2*'`. If a second line ending in `^{}` appears, the tag is annotated and you must pin the `^{}` SHA.
- Write the workflow with `permissions: contents: read` at the TOP level and add narrower job-level blocks only where a job provably needs more. Do not start permissive and tighten later; you will never tighten it.
- Apply `persist-credentials: false` to the checkout in the test/lint workflow (which never pushes), and document it in a comment as defense-in-depth rather than as a GitHub requirement, since it is not in GitHub's official security reference.
- Enable pre-push hooks explicitly. Put `default_install_hook_types: [pre-commit, pre-push]` at the top of .pre-commit-config.yaml so a plain `pre-commit install` wires up both - otherwise the pre-push test hook silently never runs.
- Keep the runtime dependency-free as designed by putting pytest/ruff in `[dependency-groups]` (PEP 735), not in `[project.optional-dependencies]`. Dependency groups are explicitly excluded from built distribution metadata, so a downstream consumer of the wheel sees a genuinely zero-dependency package. Matplotlib for optional plotting is the one thing that legitimately belongs in an extra.
- CI dependency step must be `uv sync --locked`. Add a separate fast job running `uv lock --check` if you want the lockfile-drift failure to be reported distinctly from a test failure.
- For the OPM cross-validation track, pin to the release tag `release/2026.04/final` rather than to a branch, and record the tag in the repo so a future reviewer can reproduce. Expect the next release around 2026.10 on the observed semi-annual cadence.
- For NIST reference values: the defensible pattern is to store a small fixture file of retrieved values WITH the full Setzmann-Wagner / Quinones-Cisneros citations and the retrieval URL and date, treat it as third-party reference data in the repo's licensing notes, and keep it small. If the project is to be published openly, get the licensing question answered before that commit rather than after - see uncertainties.
- Label the methane viscosity reference correctly in code comments: Quinones-Cisneros, Huber & Deiters (2011, unpublished), NOT Younglove & Ely. If the repo needs a citable, auditable viscosity model, WebBook is the wrong source and a published correlation (Lee-Gonzalez-Eakin for gas reservoir work, or a peer-reviewed reference model) should be used instead, with WebBook retained only as a numerical cross-check.
- Adopt src layout from the start. Retrofitting it later invalidates every relative path in the test suite and in any notebook.

## Open uncertainties

- NIST LICENSING - THE MOST IMPORTANT UNRESOLVED ITEM. I retrieved the NIST SRD statement 'None of our SRD may be reproduced, stored in a retrieval system or transmitted, in any form or by any means ... without prior permission' and the WebBook footer '(c) 2026 by the U.S. Secretary of Commerce on behalf of the United States of America. All rights reserved.' I could NOT retrieve any explicit small-extract / fair-use / redistribute-with-attribution carve-out. The task asked me to confirm whether small extracts may be redistributed with attribution - I CANNOT CONFIRM THAT. My recollection is that the WebBook has historically carried language permitting copies for scientific use with customary citation, but I did not retrieve that text this session and will not assert it. The implementer should fetch https://webbook.nist.gov/chemistry/ and its Citation Guide link directly, or contact NIST SRD, before committing WebBook-derived numbers to a public repository. Note also that SRD copyright is a real statutory exception (Standard Reference Data Act, PL 90-396) to the usual rule that US Government works are public domain - the intuition 'it's a .gov site so it's public domain' is wrong here.
- persist-credentials: false - I verified the INPUT exists and its default is true (actions/checkout README, first-party), and I verified by negative control that it is NOT recommended in GitHub's official 'Secure use reference' page nor in OpenSSF Scorecard's checks.md. I did not exhaustively search every GitHub Docs page or the GitHub Security Lab blog, so I cannot state that GitHub has never recommended it anywhere - only that it is absent from the page a reviewer would most naturally cite. Treat the plan's framing of it as 'current recommended hardening' as UNSUPPORTED BY OFFICIAL DOCS, though it remains sound defense-in-depth.
- The exact minimum Actions Runner version for actions/checkout v7 was not retrieved; the README gave the figure for v5 (>= v2.327.1). Self-hosted runner users should check the v7 release notes directly.
- hatchling's src-layout auto-discovery rules were NOT retrieved this session. I stated that src/<normalized_name>/ is discovered automatically in the common case - this is RECALLED, not verified. If the import name differs from the distribution name, set [tool.hatch.build.targets.wheel] packages explicitly rather than relying on it. Likewise the setuptools equivalent ([tool.setuptools.packages.find] where = ["src"]) is recalled, not retrieved.
- I confirmed that pre-commit stages were renamed and that 3.2.0 is the version cited on pre-commit.com, but I did NOT verify whether the legacy names `commit`/`push` currently produce a deprecation warning or a hard error in the latest pre-commit release. Assume warning, plan for error.
- 'Latest release' for actions/checkout, actions/setup-python and OPM are time-varying facts retrieved on 2026-09-13. They are already potentially stale by the time this card is read.
- The SHAs for the LATEST tags (checkout v7.0.1, setup-python v7.0.0, v6.3.0, v6.1.0) were obtained by a single method (`git ls-remote`), unlike the two plan-claimed SHAs which I verified twice. They are corroborated only weakly by floating-tag self-consistency. Re-verify independently before pinning any of them.
- PEP 735 support levels across pip versions were not retrieved; I did not confirm the exact pip version that introduced `pip install --group`.
- OPM release cadence 'approximately semi-annual, April/October' is inferred from three observed data points (2025.04, 2025.10, 2026.04), not from a published release-policy document. I did not find an official statement of the cadence.
- The NIST methane isotherm was retrieved as a rendered table via an HTML-to-markdown conversion layer. The values are self-consistent and monotonic, but a single transcription error in a 5th digit would not be caught by that sanity check. If any of these numbers becomes a load-bearing test fixture, re-fetch it directly and diff.

## Independent check values

| Check | Inputs | Expected | Source | Retrieved or recalled |
|---|---|---|---|---|
| Dual-method verification of the plan document's actions/checkout v4.2.2 SHA claim. Method A: GitHub REST API git-ref endpoint. Method B: git wire protocol via `git ls-remote` against the canonical HTTPS remote. These share a server but exercise completely different code paths and response formats, so a transcription or parsing error in one would not reproduce in the other. | `Tag `v4.2.2` in repository actions/checkout` | `11bd71901bbe5b1630ceea73d27597364c9af683 (object.type = commit; no peeled ^{} ref => lightweight tag)` | https://api.github.com/repos/actions/checkout/git/ref/tags/v4.2.2 ; `git ls-remote https://github.com/actions/checkout.git 'refs/tags/v4.2.2*'` | RETRIEVED 2026-09-13 - both methods returned the identical SHA, matching the plan document. PLAN CLAIM CONFIRMED. |
| Dual-method verification of the plan document's actions/setup-python v5.6.0 SHA claim, same two methods. | `Tag `v5.6.0` in repository actions/setup-python` | `a26af69be951a213d495a4c3e4e4022e16d87065 (object.type = commit; lightweight)` | https://api.github.com/repos/actions/setup-python/git/ref/tags/v5.6.0 ; `git ls-remote https://github.com/actions/setup-python.git 'refs/tags/v5.6.0*'` | RETRIEVED 2026-09-13 - both methods agree, matching the plan document. PLAN CLAIM CONFIRMED. |
| Self-consistency cross-check on floating major tags. If `vN` and the highest `vN.x.y` tag disagree, one of the two SHA readings is stale or wrong. | `checkout tags `v7` and `v7.0.1`; setup-python tags `v7` and `v7.0.0`, and `v6` and `v6.3.0`` | `checkout v7 == v7.0.1 == 3d3c42e5aac5ba805825da76410c181273ba90b1; setup-python v7 == v7.0.0 == 5fda3b95a4ea91299a34e894583c3862153e4b97; setup-python v6 == v6.3.0 == ece7cb06caefa5fff74198d8649806c4678c61a1` | `git ls-remote --tags` on both repositories | RETRIEVED 2026-09-13 - all three pairs agree, consistent with the releases/latest API responses. |
| NIST Chemistry WebBook methane isotherm at T = 300 K. Usable as a fixture to validate any real-gas density or z-factor implementation in the repository (subject to the licensing caveat below). Density here is mass density; convert to z via z = PM/(rho R T) with M = 16.04246 g/mol. | `Methane (CAS 74-82-8, WebBook ID C74828), T = 300 K, P = 1 to 10 MPa in 1 MPa steps, 5 significant digits, SI units (kg/m3, uPa*s)` | `[reference values withheld -- see docs/release/PUBLIC_DATA_POLICY.md; re-acquire locally with scripts/fetch_nist_reference.py to run this check]` | https://webbook.nist.gov/cgi/fluid.cgi?T=300&PLow=1&PHigh=10&PInc=1&Digits=5&ID=C74828&Action=Load&Type=IsoTherm&TUnit=K&PUnit=MPa&DUnit=kg%2Fm3&VisUnit=uPa*s | RETRIEVED 2026-09-13 directly from the NIST WebBook isotherm generator. Monotonicity sanity check passes: density rises with pressure, and viscosity rises with pressure as expected for a dense supercritical gas. LICENSING CAVEAT APPLIES - see uncertainties before committing these numbers to the repo. |
| Negative control for the persist-credentials claim: confirm the string is genuinely absent from the authoritative pages rather than merely unfound by a bad query. I checked two independent authorities that WOULD carry it if it were official guidance. | `Search for 'persist-credentials', 'credential', '.git/config' on GitHub Docs 'Secure use reference'; search for 'persist-credentials' in OpenSSF Scorecard docs/checks.md` | `If persist-credentials: false were official hardening guidance, it would appear in at least one of these.` | https://docs.github.com/en/actions/reference/security/secure-use ; https://raw.githubusercontent.com/ossf/scorecard/main/docs/checks.md | RETRIEVED 2026-09-13 - ABSENT from both. GitHub's page does discuss least-privilege credentials and SHA pinning, and OpenSSF Scorecard has Token-Permissions and Pinned-Dependencies checks, but neither mentions persist-credentials. The control also shows the instrument works: the SAME fetches successfully returned the pinning and permissions guidance, so the absence is a real absence, not a retrieval failure. |
| Verification that GitHub's permissions semantics actually deliver least privilege - i.e. that writing only `contents: read` genuinely zeroes the other scopes rather than leaving them at default. | `GitHub workflow-syntax reference, `permissions` key` | `Specifying any scope sets all unspecified scopes to none` | https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions | RETRIEVED 2026-09-13 - confirmed verbatim: when you specify access for any permission, 'all of those that are not specified are set to none'. So `permissions: {contents: read}` at workflow level is a complete least-privilege posture for a test workflow, not a partial one. |
| uv flag semantics verified against the actual installed binary rather than documentation alone, guarding against doc drift. | ``uv help sync`, `uv help lock` on uv 0.11.7` | `--locked = assert lockfile unchanged, error if stale or missing; --frozen = use lockfile as source of truth without checking freshness, error only if missing; `uv lock --check` documented as 'Equivalent to --locked'` | Local uv 0.11.7 CLI help; cross-checked against https://docs.astral.sh/uv/concepts/projects/sync/ | RETRIEVED/EXECUTED 2026-09-13. Binary help and published docs agree. Note the docs page has a subtly different emphasis ('to run a command without checking if the environment is up-to-date, use --frozen'); the CLI help is the more precise statement and is what I quoted. |

## Adversarial review

### Corrections

**pre-commit `entry` parsing (equations[2].assumptions)** — severity medium, confidence high - confirmed from the tool's own first-party source, and independently corroborated by the card's own working example

- Claimed: "`entry` is split on whitespace, not run through a shell - so shell metacharacters, pipes and globs in `entry` do not work."
- Correct: `entry` is passed through `shlex.split()`, not split on whitespace. The 'no shell' half is right; the 'whitespace' half is wrong and the difference is observable. pre-commit's own source states it verbatim: pre_commit/clientlib.py carries the docstring "the hook `entry` is passed through `shlex.split()` by the command". This is an INTERNAL CONTRADICTION in the card: its own example in the same block is `entry: pytest -q -m "not slow"`, which works ONLY because shlex honours the quotes. Under the card's stated rule that entry is whitespace-split, that example would decompose to `-m`, `"not`, `slow"` and the hook would fail. An implementer who believes the stated rule will needlessly wrap quoted-argument hooks in a shim script, or will mis-diagnose the first quoting bug they hit.
- Evidence: https://raw.githubusercontent.com/pre-commit/pre-commit/main/pre_commit/clientlib.py - retrieved 2026-09-13, contains `import shlex` and the docstring "the hook `entry` is passed through `shlex.split()` by the command".

**GitHub immutable releases - an entire mechanism the card does not mention (equations[0], failure_modes[0], validity_ranges[0])** — severity medium, confidence high - official GitHub docs page plus a machine-readable per-release API field

- Claimed: SHA pinning is framed as absolute and tags as uniformly mutable: "Pinning an action to a full-length commit SHA is currently the only way to use an action as an immutable release"; "a mutable tag can be repointed at malicious code"; "The BINDING itself is not immutable: all four tags verified are lightweight and can be force-moved by a maintainer."
- Correct: The quote is transcribed accurately from GitHub's secure-use page, but that page's wording is now STALE relative to GitHub's own newer documentation, and the card never surfaces the conflict. GitHub Docs ships a dedicated page, 'Using immutable releases and tags to manage your action's releases', which states: "If you are ready to share an unchangeable version of your action, create a release on GitHub with a release-specific tag (for example, v1.0.0)" - and contrasts it with tags you deliberately leave movable. This is verifiable per-release: the REST API exposes an `immutable` field. I checked all four actions named in the card - actions/setup-python v7.0.0 returns immutable=true, while actions/checkout v7.0.1, actions/checkout v4.2.2 and actions/setup-python v5.6.0 all return immutable=false. So the card's own recommended upgrade target for setup-python is in fact an immutable release, a fact its threat model has no slot for. SHA pinning remains the correct default (it is repo-policy-independent and survives a maintainer disabling the feature), but the card should state that immutability is now a per-release property that can be queried, not a property no tag can ever have.
- Evidence: https://docs.github.com/en/actions/how-tos/create-and-publish-actions/using-immutable-releases-and-tags-to-manage-your-actions-releases ; GET https://api.github.com/repos/actions/setup-python/releases/tags/v7.0.0 -> immutable=true ; same endpoint for actions/checkout v7.0.1, v4.2.2 and setup-python v5.6.0 -> immutable=false. All retrieved 2026-09-13.

**NIST SRD licensing - the card's strongest evidence comes from a page NIST itself marks as outdated (uncertainties[0], constants 'NIST Chemistry WebBook copyright status')** — severity medium, confidence high - both pages retrieved this session; the licence URL comes from the WebBook's own structured metadata

- Claimed: The restriction is sourced to https://www.nist.gov/srd/public-law, quoted as "None of our SRD may be reproduced, stored in a retrieval system or transmitted, in any form or by any means ... without prior permission", and the card reports it could find no fair-use carve-out.
- Correct: The quote is verbatim-accurate, but that page carries a banner the card did not report: "This page is no longer being updated and the information may be out of date." Citing a self-declared stale page as the primary authority for a licensing decision is a defect an adversarial reviewer will use. The WebBook itself designates a different, current licence URL in the JSON-LD of the very isotherm page the card retrieved: "license": "https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications#SRD". I retrieved that current page. It does NOT contain the 'may not be reproduced' sentence; it requires the copyright notice and points to nist.gov/srd for licensed SRD. Two consequences, cutting in opposite directions: (a) the card's absolute 'may not be reproduced' framing is weaker than presented, but (b) the card's CONCLUSION gets STRONGER, because the current page structurally separates 'Standard Reference Data (SRD)' from a distinct section headed 'Fair Use of Other NIST Data/Works', which it scopes to "Data/works created by NIST employees that are NOT covered by the Standard Reference Data Act". That is positive evidence that the fair-use language does not reach WebBook data - an upgrade from the card's absence-of-evidence. Net: the card's bottom line (WebBook output is copyrighted, is not public domain, and committing it is a licensing decision) SURVIVES, but the citation must be swapped to the current page.
- Evidence: https://www.nist.gov/srd/public-law (banner text, retrieved 2026-09-13) ; https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications (retrieved 2026-09-13; section headings and the 'not covered by the Standard Reference Data Act' scoping) ; JSON-LD "license" key embedded in the WebBook fluid.cgi isotherm response.

**Setzmann & Wagner (1991) page range (constants 'NIST Chemistry WebBook - methane reference equation of state')** — severity minor, confidence high - publisher-of-record metadata via Crossref, independent of NIST

- Claimed: "J. Phys. Chem. Ref. Data, 20(6):1061-1151, 1991"
- Correct: 1061-1155. Crossref metadata for DOI 10.1063/1.555898 returns page '1061-1155', volume 20, issue 6, published 1991-11-01, title '...at Pressures up to 1000 MPa'. The card faithfully transcribed a typo that exists on NIST's own page: the WebBook free-text note says 1061-1151 while the structured citation block on the SAME page says '1991, 20, 6, 1061-1155, https://doi.org/10.1063/1.555898'. The card quoted the wrong one of the two and did not notice the page disagreed with itself. Low impact numerically, but this citation is destined for a repo references file and a code comment, which is exactly where a wrong page range survives forever.
- Evidence: https://api.crossref.org/works/10.1063/1.555898 -> page '1061-1155' (retrieved 2026-09-13), cross-checked against the internally inconsistent NIST fluid.cgi reference block.

**When pre-commit's legacy stage names became deprecated (failure_modes; constants 'pre-commit version that renamed hook stages')** — severity minor, confidence high - first-party changelog, full-text scanned rather than spot-checked

- Claimed: "USING pre-commit STAGE NAMES `commit`/`push`. These are the legacy names, deprecated since 3.2.0." The card also lists as an open uncertainty whether legacy names currently warn or hard-error.
- Correct: Two distinct releases, and the card collapsed them. pre-commit 3.2.0 (2023-03-17) only ADDED the new names - changelog: "Allow `pre-commit`, `pre-push`, and `pre-merge-commit` as `stages`." Deprecation WARNINGS for the old names landed 18 months later in 4.0.0 (2024-10-05): "Add warnings for deprecated `stages` (`commit` -> `pre-commit`, `push` -> `pre-push`, `merge-commit` -> `pre-merge-commit`)", alongside "Handle `stages` deprecation in `pre-commit migrate-config`." This also RESOLVES the card's open uncertainty: as of the current release 4.6.2 (2026-08-10) the legacy names still WARN and do not hard-error - no changelog entry removes them, and `pre-commit migrate-config` exists to rewrite them. The card's 'assume warning, plan for error' posture was right and is now confirmed rather than assumed.
- Evidence: https://raw.githubusercontent.com/pre-commit/pre-commit/main/CHANGELOG.md - 3.2.0 and 4.0.0 sections, full changelog scanned for every 'stage' entry ; https://api.github.com/repos/pre-commit/pre-commit/releases/latest -> v4.6.2. Retrieved 2026-09-13.

**Methane molar mass used for the density-to-z conversion (numerical_pitfalls; independent_checks[3])** — severity minor, confidence medium - the absence from the cited source is confirmed; the correct replacement value is recalled, not retrieved

- Claimed: "convert to z via z = PM/(rho R T) with M = 16.04246 g/mol", and separately warns that "using 16 g/mol instead of 16.04246 g/mol introduces a ~0.27% systematic bias".
- Correct: The 0.27% arithmetic is right (16.04246/16 - 1 = 0.265%) and the warning is well taken, but the constant 16.04246 itself is NOT sourced anywhere in the card, and it is not on the NIST page the card retrieved - I re-fetched that isotherm page and it publishes critical constants (Tc 190.564 K, Pc 4.5992 MPa, Dc 162.66 kg/m3, acentric factor 0.01142, normal boiling point 111.667 K) but NO molar mass. This violates the card's own rule 1. It matters more than it looks: the physically correct M for this conversion is not a periodic-table formula weight at all, it is whatever M the reference implementation used internally to convert its molar-basis EOS to the mass density it printed. Setzmann-Wagner / REFPROP use a slightly different value (recalled as ~16.043 g/mol; I did not retrieve it). The discrepancy is ~0.002% - numerically immaterial - but a card that warns about a 0.27% M error while leaving its own M unsourced hands the adversarial reviewer a free hit.
- Evidence: Re-fetch of https://webbook.nist.gov/cgi/fluid.cgi?...ID=C74828... 2026-09-13: grep for 'Molecular weight', 'Molar mass' and '16.04' returns nothing in the page body. Card cites no other source for the value.

**Quote fidelity on the GitHub permissions semantics (equations[0].symbols; independent_checks[5])** — severity trivial, confidence high

- Claimed: Presented inside quotation marks as GitHub's wording: "when you specify access for any of these scopes, all of those that are not specified are set to none".
- Correct: GitHub's actual sentence is "If you specify the access for any of these permissions, all of those that are not specified are set to none." The card says 'scopes' where GitHub says 'permissions' and opens with 'when' rather than 'If'. The SEMANTIC claim is fully confirmed and the card's conclusion (workflow-level `contents: read` is a complete least-privilege posture, not a partial one) stands. Flagged only because the card's entire method is verbatim quotation, so a paraphrase inside quote marks is a method violation a reviewer will use to impeach the other quotes.
- Evidence: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax - retrieved 2026-09-13, exact sentence appears twice. Also observed there: `id-token` and `vulnerability-alerts` do not accept the full read|write|none triple (`id-token: write|none`, `vulnerability-alerts: read|none`).

### Left unverified

- Methane molar mass 16.04246 g/mol. Asserted by the card as the conversion constant for z = PM/(rho R T) with no citation, and absent from the NIST isotherm page the card retrieved. Neither the card nor I sourced it this session. The value that actually matters is the M internal to Setzmann-Wagner/REFPROP, which must be read from the EOS paper or the REFPROP fluid file, not from a periodic table.
- Second and third virial coefficients I used for my own cross-check (B(300 K) ~= -42.8 cm3/mol, C(300 K) ~= 2600 cm6/mol2) are RECALLED from the Dymond & Smith compilation, not retrieved. My virial check agrees with the card's fixtures to ~1e-3 in z, which is strong corroboration, but if that check is promoted to a repo test oracle the coefficients must be sourced first.
- The specific minimum Actions Runner version for actions/checkout v7. The card flagged this; I narrowed it but did not close it. The v7.0.1 README states v2.327.1 only under the '# Checkout v5' heading (node24 migration) and v2.329.0 under '# Checkout v6' for the narrower case of running authenticated git commands from a Docker container action. No v7-specific runner floor is published in the README.
- Whether actions/checkout will enable immutable releases. Today v7.0.1 returns immutable=false while setup-python v7.0.0 returns immutable=true, so the two actions this repo depends on are currently under different release-immutability regimes. That asymmetry is a retrieved fact but a maintainer decision, and it can change without notice.
- Whether GitHub has ever recommended persist-credentials:false anywhere outside the two pages checked. The card's negative control is sound and I independently re-confirmed that 'persist-credentials' appears 0 times and '.git/config' 0 times on the secure-use reference page, while the same fetch did return the SHA-pinning and least-privilege guidance (so the instrument demonstrably works). But absence from two pages is not absence from GitHub's corpus; the honest claim is scoped to those pages, which is what the card says.
- Exact uv versions over which the --locked / --frozen semantics have been stable. Both the card and I verified only uv 0.11.7, the single binary on this machine. 'The semantics have been stable' is an assertion neither of us tested against any other version.
- The NIST WebBook isotherm values remain single-method. The card flagged that it retrieved them through an HTML-to-markdown layer; I re-fetched the raw HTML and cross-checked the values against a virial EOS (agreement ~1e-3 in z), which catches gross transcription error but would NOT catch a wrong 5th digit. A byte-level re-fetch and diff is still required before these become load-bearing fixtures.

### Missing before implementation

- NIST's own stated model uncertainties, which the card said it did not retrieve and which are mandatory for choosing a defensible test tolerance. I retrieved them from the same isotherm page. DENSITY: 0.03% for pressures below 12 MPa and temperatures below 350 K, up to 0.07% for pressures less than 50 MPa. VISCOSITY: less than 0.3% between 200-400 K for pressures under 30 MPa, under 2% over the rest of the fluid surface to 100 MPa, rising to 5% for 100-500 MPa and 10% for 500-1000 MPa. THERMAL CONDUCTIVITY: dilute gas 130-625 K is 2.5%; excluding the dilute gas, 2% between 110 and 725 K to 70 MPa, 5% or greater near the critical point. Crucially the page adds that the viscosity uncertainties "are valid when used with the equation of state of Setzmann, U. and Wagner, W. ... The use of other equations of state may result in larger uncertainties" - so pairing this viscosity model with a cubic EOS voids its stated accuracy. Note the card's entire 1-10 MPa / 300 K fixture window sits inside the tightest density band (0.03%), which is the tolerance to write down.
- The distinction between display precision and physical accuracy, now quantifiable. The card correctly warns that Digits=5 is display precision but gives no number. At 10 MPa the 5th digit of the tabulated density is of order 1e-5 relative, roughly three orders of magnitude tighter than the 0.03% EOS uncertainty. The density itself is excluded from this release under docs/release/PUBLIC_DATA_POLICY.md. So: asserting all 5 digits against a Setzmann-Wagner REIMPLEMENTATION is legitimate (the EOS is deterministic, you are testing your own algebra); asserting 5 digits as PHYSICAL truth is not. The test suite must state which of the two each fixture is testing.
- Methane critical constants, needed for any corresponding-states or cubic-EOS path and absent from the card except Tc. From the same retrieved page: Tc = 190.564 K, Pc = 4.5992 MPa, Dc = 162.66 kg/m3, acentric factor = 0.01142, normal boiling point = 111.667 K, dipole moment 0.0 Debye.
- A decision on GitHub immutable releases before the workflow is written: whether the pin-audit script should query the REST API `immutable` field, and whether to record each pinned release's immutability alongside its SHA. Without it the repo's threat model silently assumes all tags are movable, which is no longer true for at least one of its two actions.
- The pip version floor for PEP 735, which the card left open. `--group` was added in pip 25.1 (NEWS.rst: "Add a ``--group`` option which allows installation from :pep:`735` Dependency Groups"). If the repo must support pip < 25.1, dev dependencies cannot live in [dependency-groups] and must fall back to an extra, accepting that they then appear in published metadata.
- A concrete licensing decision and the text to accompany it, given that the fair-use carve-out does NOT extend to SRD. Minimum: the NIST-prescribed copyright notice, the retrieval URL and date, the full model citations (Setzmann & Wagner 1991 with the CORRECTED page range 1061-1155; Quinones-Cisneros, Huber & Deiters 2011 unpublished), and a note that the viscosity model has no peer-reviewed publication against which to audit coefficients.
- Minimum tool versions to pin in .pre-commit-config.yaml and CI: `minimum_pre_commit_version: '4.0.0'` if the config is to rely on the new stage names warning-free, and `default_install_hook_types: [pre-commit, pre-push]`, which the card correctly identifies as the fix for the silent pre-push no-op.
- OPM cadence evidence is understated rather than wrong, and can be strengthened for free. The card infers 'approximately semi-annual' from three data points; the releases API actually shows seven consecutive April/October finals - 2023.04, 2023.10, 2024.04, 2024.10, 2025.04, 2025.10, 2026.04 - plus one interim prerelease (2024.12). The publication lag varies from about 1 month (2025.10 -> 2025-10-31) to about 3 months (2024.04 -> 2024-07-04), which supports the card's 'do not infer the release date from the version number' warning far better than the three points it cited.

### Recommended independent test oracles

**Virial-EOS cross-check of the NIST methane density fixtures (executed this session)**

- Inputs: `The card's 10 fixture pairs at T = 300 K, P = 1..10 MPa. Compute z_webbook = P*Vm/(R*T) with Vm = M/rho, and compare against a truncated virial series z = 1 + B/Vm + C/Vm^2 using literature B(300 K) and C(300 K) for methane.`
- Expected: `I ran this. Agreement is 2.1e-4 at 1 MPa, peaking at 5.2e-4 near 4 MPa, then crossing sign and reaching -9.9e-4 at 10 MPa. The magnitude, the sign change and the monotone growth of the residual at high density are precisely the signature of a series truncated after the third virial coefficient. The derived z values across the range are excluded from this release under docs/release/PUBLIC_DATA_POLICY.md.`
- Why independent: The virial expansion is fitted to PVT and acoustic measurements and shares no functional form, no coefficients and no fitting data with a 40-term Helmholtz-energy reference EOS, so it cannot reproduce a Setzmann-Wagner coefficient error. The diagnostic power is in the RESIDUAL SHAPE, not the agreement: a transcription error in one fixture appears as an isolated spike breaking the smooth trend - exactly the failure the card admits its monotonicity check cannot catch.

**Zero-pressure asymptote and its first derivative**

- Inputs: `Evaluate the repo's z-factor routine at P -> 0 at fixed T = 300 K, and numerically differentiate: lim(P->0) dz/dP.`
- Expected: `z -> 1 exactly, and dz/dP -> B(T)/(R*T), about -1.72e-8 per Pa at 300 K (equivalently z ~ 1 - 0.0172 per MPa near zero). Extrapolating the card's own fixture set to P = 0 reproduces this slope.`
- Why independent: A closed-form limit forced by statistical mechanics, not by any correlation, so no published table is needed and it cannot be circular. It is two-sided: it catches a pressure units error (the slope scales wrongly), a gauge-vs-absolute pressure bug (z reaches 1 at -101325 Pa instead of 0, making the card's own psig/psia pitfall visible), and a sign error in the first virial term.

**Annotated-tag detection, with a live positive control inside the very repo being pinned**

- Inputs: `Run the repo's pin-audit script against actions/checkout tags v4.2.2 (expected lightweight) AND v6.0.3 (expected annotated).`
- Expected: `v4.2.2 -> single ls-remote line, 11bd71901bbe5b1630ceea73d27597364c9af683, no peeled ref. v6.0.3 -> TWO lines: ref 9f698171ed81b15d1823a05fc7211befd50c8ae0 and peeled 'refs/tags/v6.0.3^{}' df4cb1c069e1874edd31b4311f1884172cec0e10. The script must pin df4cb1c0..., and must FAIL if it would have pinned 9f698171....`
- Why independent: This is the positive control the card's annotated-tag failure mode lacks: it asserts the hazard 'will bite on other actions' while verifying only four tags that all happen to be lightweight, so its instrument is never shown to fire. I found a real annotated tag inside actions/checkout itself. Without this case the audit script passes vacuously on four lightweight tags and its peeled-ref branch is dead code that has never executed.

**Wheel-metadata oracle for the PEP 735 / extras split (executed this session)**

- Inputs: `Build the card's exact pyproject.toml with hatchling and inspect the resulting wheel's METADATA and file list.`
- Expected: `I ran this and it builds. The wheel contains gas_reservoir_lab/__init__.py. METADATA contains 'Provides-Extra: plots' and "Requires-Dist: matplotlib>=3.8; extra == 'plots'" and contains NO trace of the dev or docs groups. This simultaneously confirms (a) the PEP 735 non-shipping guarantee behaviourally rather than by quotation, and (b) that hatchling's name normalization turns the hyphenated distribution name 'gas-reservoir-lab' into the underscored directory src/gas_reservoir_lab/ - which the card explicitly flagged as RECALLED, NOT VERIFIED. It is now verified twice: empirically, and in hatchling's source, where WheelBuilderConfig.default_file_selection_options tries normalize_file_name_component(raw_name) against <NAME>/__init__.py then src/<NAME>/__init__.py, raising an error if all heuristics fail.`
- Why independent: It tests the built artifact rather than the specification prose, so it stays true across backend versions and would catch a future hatchling regression that the PEP quotation never could. It also converts the repo's central design promise - a genuinely zero-dependency wheel - from an intention into an assertion.

**uv lockfile-drift gate, tested behaviourally rather than by reading --help**

- Inputs: `In a scratch project: (1) `uv lock`, then `uv sync --locked` -> expect exit 0. (2) Add a dependency to pyproject.toml WITHOUT re-locking, then `uv sync --locked` -> expect NONZERO exit. (3) Same stale state with `uv sync --frozen` -> expect exit 0 and the new package ABSENT from the environment. (4) Delete uv.lock entirely -> expect both flags to fail.`
- Expected: `Exit codes 0 / nonzero / 0-with-missing-package / nonzero-nonzero. Step 3 is the one that matters: a green build with a missing dependency is the exact silent failure the card warns about, and this test makes it observable.`
- Why independent: It exercises the binary's behaviour instead of quoting its help text, so it survives the documentation drift the card itself flags as a risk. It is also the only check that distinguishes --locked from --frozen by consequence rather than by description, so a reviewer cannot dismiss it as restating the docs.

**pre-commit `entry` quoting oracle**

- Inputs: `A repo: local hook with `entry: python -c "import sys; sys.exit(0 if sys.argv[1:] == ['a b'] else 1)" "a b"`, `language: system`, `pass_filenames: false`, `always_run: true`. Run `pre-commit run --all-files`.`
- Expected: `PASS. The quoted `a b` must arrive as ONE argv element. If entry were whitespace-split as the card's assumption states, it would arrive as two elements and the hook would exit 1.`
- Why independent: A behavioural discriminator that separates the two competing claims (shlex.split vs whitespace split) by observable outcome, deciding the correction without appeal either to the card or to my reading of pre-commit's source. It also directly protects the card's own `pytest -q -m "not slow"` example, which silently depends on the answer.

**Corresponding-states sanity band on the z fixtures**

- Inputs: `Reduce the fixture conditions with the NIST-published critical constants: Tr = 300/190.564 = 1.5743; Pr = P/4.5992, giving Pr = 0.217 at 1 MPa to 2.174 at 10 MPa. Compare the derived z against a generalized compressibility (Standing-Katz) chart reading at those reduced coordinates.`
- Expected: `z at Tr = 1.574 falling monotonically across Pr = 0.22 to 2.17 and agreeing with the chart to within its own readability (~1%); the z values themselves are derived from the reference extract and are excluded from this release.`
- Why independent: Standing-Katz is a generalized corresponding-states correlation fitted to natural-gas mixtures, unrelated in form and in fitting data to a component-specific Helmholtz reference EOS. Its ~1% resolution is far too coarse to validate the 5th digit, so it must be used ONLY as an order-of-magnitude and shape guard - which is precisely its value: it catches a decimal-point or unit blunder without tempting anyone to treat it as a precision oracle.

## Sources

| Citation | Access level | Supports |
|---|---|---|
| GitHub REST API, git ref endpoints for actions/checkout tag v4.2.2 and actions/setup-python tag v5.6.0 | full-text retrieved | Primary, authoritative confirmation of both plan-document SHA claims, including object.type = commit. |
| Git wire protocol, `git ls-remote` against https://github.com/actions/checkout.git and https://github.com/actions/setup-python.git | full-text retrieved | Independent second-method confirmation of all tag-to-SHA bindings; also establishes that the tags are lightweight (no peeled ^{} refs) and enumerates the current v6/v7 tag SHAs. |
| GitHub REST API, releases/latest for actions/checkout and actions/setup-python | full-text retrieved | Current latest release tags and publication timestamps: checkout v7.0.1 (2026-07-20T15:10:05Z), setup-python v7.0.0 (2026-07-20T03:15:01Z). |
| GitHub Docs, 'Secure use reference' (GitHub Actions security guidance) | full-text retrieved | Official SHA-pinning guidance ('Pinning an action to a full-length commit SHA is currently the only way to use an action as an immutable release'), least-privilege GITHUB_TOKEN guidance, and the verified ABSENCE of any persist-credentials recommendation. |
| GitHub Docs, 'Workflow syntax for GitHub Actions' - permissions key | full-text retrieved | The list of permission scopes, the read/write/none values, and the critical semantic that unspecified scopes are set to none. |
| actions/checkout README at tag v7.0.1 (first-party action documentation) | full-text retrieved | The persist-credentials input description and its default of true; the v6 note about credentials moving to $RUNNER_TEMP; runner version requirements. |
| OpenSSF Scorecard, docs/checks.md (Token-Permissions and Pinned-Dependencies checks) | full-text retrieved | Secondary corroboration of least-privilege and hash-pinning as recognised hardening practices; and the negative control showing persist-credentials is absent here too. |
| OPM/opm-simulators GitHub releases API | full-text retrieved | Latest release 2026.04 (tag release/2026.04/final, 2026-05-20, not a prerelease); the release/<YYYY.MM>/final tag scheme; the 2025.10 and 2025.04 predecessors. |
| OPM project website, Download/Releases page | full-text retrieved | Independent cross-check of the 2026.04 release announcement (dated 2026-05-21) and the YYYY.MM numbering scheme. |
| NIST Chemistry WebBook, Thermophysical Properties of Fluid Systems - methane (CAS 74-82-8) isotherm generator, with reference block | full-text retrieved | The methane EOS (Setzmann & Wagner 1991), viscosity model (Quinones-Cisneros, Huber & Deiters 2011, unpublished), thermal conductivity model (Friend, Ely & Ingham, NIST TN 1325, 1989), and the 300 K density/viscosity fixture values. |
| NIST Standard Reference Data Program, 'Public Law' / SRD terms page | full-text retrieved | The statutory copyright basis (Standard Reference Data Act, PL 90-396) and the restriction that SRD may not be reproduced or stored in a retrieval system without prior permission. |
| NIST Chemistry WebBook landing page (copyright footer) | full-text retrieved | The verbatim '(c) 2026 by the U.S. Secretary of Commerce on behalf of the United States of America. All rights reserved.' notice. |
| PyPA Python Packaging User Guide, 'Writing your pyproject.toml' | full-text retrieved | The [build-system] recommendation, required [project] keys name and version, and [project.optional-dependencies] for extras. |
| PyPA Python Packaging User Guide, 'src layout vs flat layout' | full-text retrieved | Definition of src layout, the canonical directory tree, and the import-isolation and editable-install rationale. |
| PyPA specification, 'Dependency Groups' (PEP 735) | full-text retrieved | The [dependency-groups] table syntax and the key distinction from extras: 'Build backends MUST NOT include Dependency Group data in built distributions as package metadata.' |
| pre-commit official documentation | full-text retrieved | The complete current list of valid `stages` values, the verbatim statement of the stage rename, version 3.2.0 as the rename release, and the repo: local hook schema. |
| uv 0.11.7 built-in CLI help (`uv help sync`, `uv help lock`), executed locally 2026-09-13 | full-text retrieved | Verbatim semantics of --locked, --frozen, `uv lock --check` (equivalent to --locked) and --check-exists, from the binary itself plus the published Astral documentation as cross-check. |
