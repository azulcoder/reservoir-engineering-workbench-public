# Deployment runbook

Everything in this document is external to the repository and **none of it has been
done**. There is no git remote, no hosted project, no Pages site, and no URL. The two
workflow files under `.github/workflows/` describe a pipeline that has never executed on
a hosted runner. This runbook is the sequence that would change that, written down before
it is followed so that the steps can be argued with while they are still cheap to change.

It is written for whoever owns the eventual repository. That person is not named here,
and neither is an account, an organisation, or a domain, because none of those exist yet
and none of them can be inferred from anything in this tree. Guessing one and writing it
into a workflow would produce a file that looks configured and deploys to a stranger.

## The claim this runbook governs

> Hosted CI is **NOT RUN**.

That remains true until a hosted execution is observed for a named commit SHA, and it is
true no matter how carefully anyone reads the workflow files. Reading `ci.yml` locally,
linting its YAML, extracting a step and running it by hand, or watching all of it pass on
a laptop are all useful and none of them is a hosted run. A workflow file is a
description of an intention; a run is an event with an identifier, a start time, a
conclusion, and a log that someone else can fetch.

When the first hosted run happens, the thing that changes the claim is a specific record:

| field | example shape |
| --- | --- |
| workflow | `verification` |
| commit | the full 40-character SHA, not a branch name |
| run id and attempt | the numeric id from the run URL |
| conclusion | success or failure, per job |
| observed by | who read the log, and when |

Until that table can be filled in from a real run, every document in this repository that
mentions CI must keep saying it has not run. `docs/release/VERIFICATION.md` already does.

## Before anything leaves this machine

These are repository-local and are not part of the external sequence, but the external
sequence is a waste of everyone's time if they are not done first.

1. The working tree is clean and the commit to be published is reviewed.
2. `scripts/build_release.py` passes for both fixture bases, which includes
   `npm run check` reporting 0 errors, 0 warnings and 0 hints:

   ```
   python3 scripts/build_release.py --base-path / --out-dir site/dist-root
   python3 scripts/build_release.py \
       --base-path /reservoir-engineering-workbench-public/ --out-dir site/dist-project
   ```
3. The local browser QA is green. As of 2026-09-14 it is: **466 passed, 0 failed,
   14 skipped**, identical across three engines at both fixture bases. The current
   verdict is [RC_CLOSURE.md](RC_CLOSURE.md) and the machine-readable record is
   `evidence/release_status.json`.

   This item used to read "**It is not green today**" and quote 401/12/13. That was true
   when it was written and it is kept as history rather than deleted: the five defects
   behind those twelve failures, and what each of them actually was, are in
   [UI_QA.md](UI_QA.md) (banner-marked historical) and in the issue map in RC_CLOSURE.md.
   A runbook that still cites a superseded red gate stops anyone who reads it, which is
   the opposite of what a gate is for.

   Run the two release builds and the browser suite in release mode, then the skip gate
   over the JSON report each run leaves behind:

   ```
   cd site && QA_DIST=$PWD/dist-project QA_BASE=/reservoir-engineering-workbench-public/ \
       QA_PORT=4321 node tests/serve.mjs &
   QA_RELEASE=1 QA_BASE=/reservoir-engineering-workbench-public/ QA_PORT=4321 \
       npx playwright test
   python3 ../scripts/check_skip_policy.py --report test-results/report-4321.json
   ```

   `QA_RELEASE=1` is not optional here. Without it the Playwright configuration keeps a
   managed server whose command is `astro build && node tests/serve.mjs` over `site/dist`,
   and if the server started above is not answering when the suite starts, that fallback
   runs and the suite tests a directory the release did not build. Release mode has no
   fallback: an absent server fails every test instead.
4. The skip gate is clean. `scripts/check_skip_policy.py` is the same gate both workflows
   call. It reads `site/tests/skip-policy.json`, requires every skip to name a declared
   capability id, requires a probe-backed skip to carry the measurement that justifies it
   and to agree with the independent control-fixture probe, and fails an empty suite, an
   engine that produced nothing, an engine that produced only skips, and any check that
   ended up skipped everywhere. It does **not** compare the skip count to a baseline:
   14 is what macOS took, not a target for any other platform.

## The external sequence

### 1. Owner approves the destination and the visibility

A decision, made by a person, recorded somewhere durable before any of the mechanics
below. It has three parts and they are separable:

- **Destination.** Which account or organisation, and which repository name. This fixes
  the base path: a project site is served from `/<repo>/` and a user or organisation site
  or a custom domain is served from `/`. The site is built through that value, so it is
  not a detail that can be settled afterwards.
- **Visibility.** Public or private repository, and whether Pages is enabled for it.
  Note that enabling Pages on a repository publishes the built site to an anonymous
  reader even when the repository itself is private on some plans; that is a separate
  decision from repository visibility and it should be made deliberately.
- **Content.** Confirmation that the owner has read what would be published. The
  distribution manifest (`docs/release/DISTRIBUTION_MANIFEST.md`) and the data policy
  (`docs/release/PUBLIC_DATA_POLICY.md`) are the two documents that answer "what exactly
  goes out", including the standing constraint that no restricted NIST extract, and
  nothing derived from one, appears in any form.

The approval is recorded in the repository as the Actions variable
`PAGES_PUBLICATION_APPROVED=approved`. That variable is a gate in `pages.yml`, not
decoration: without it the preflight job fails and nothing downstream runs.

### 2. Create the remote and push the reviewed commit

The shape of this step depends on whether the target repository already has history.
They are different situations and only one of them is a bootstrap.

#### 2a. An empty, newly created repository — the bootstrap exception

A pull request needs a base branch, and a repository created with no README, no licence
and no initial commit has none. There is nothing to open a pull request *against*, and
manufacturing one — an unrelated README commit on `main`, so that the candidate has
something to be diffed with — would put a commit nobody reviewed into the published
history for the sole purpose of satisfying a process step. So the first candidate is
pushed as a branch and verified as a branch:

```
gh repo create <owner>/reservoir-engineering-workbench-public \
    --public --disable-issues=false --disable-wiki
git remote add origin https://github.com/<owner>/reservoir-engineering-workbench-public.git
git push -u origin release/rc-close
```

`verification` runs on that push, because `ci.yml` listens to `push` on `main` and on
`release/**`. That trigger exists for exactly this moment. `pages.yml` has
`workflow_dispatch` and nothing else, so the push cannot deploy anything: the repository
is public from this instant, but the site is not.

Then, and only after a green run for that exact SHA (step 4):

```
git push origin release/rc-close:main     # fast-forward, no force, no rewrite
gh repo edit <owner>/<repo> --default-branch main
```

This is an **initial bootstrap**, and it should be recorded as one. It is not a pull
request that was reviewed and merged; no such review happened, and writing it up as one
would be a false claim about a process that did not occur. What did happen is: a reviewed
local candidate was pushed, a hosted pipeline verified that commit, and the default branch
was created at the verified commit.

Every subsequent change uses the ordinary path — a feature or release branch, a pull
request against `main`, the `pull_request` trigger. The bootstrap is available once,
because "the repository has no commits" is true once.

#### 2b. A repository that already has history

Do not bootstrap. Inspect the real default branch, branch from it, push the branch, open
a pull request against it, and respect whatever protections and review requirements that
repository already has. Do not fast-forward its `main` from a branch and do not change its
default branch.

#### Either way

Record the SHA that was pushed. Every later step refers to it, and "the latest commit" is
not a usable identifier once anything else is pushed. Note that a pull request has *two*
SHAs — the head commit of the branch and the temporary merge commit GitHub creates to test
it — and they are not interchangeable. Record which one a given run used.

Push the candidate branch only. Not `--all`, not `--mirror`, not `--force`, and no tags:
there are none in this repository and an unreviewed tag is an unreviewed publication.

### 3. Set the repository configuration

Settings → Secrets and variables → Actions → Variables:

| variable | what it is | validated by |
| --- | --- | --- |
| `PAGES_SITE_ORIGIN` | the scheme and host the site is served from, e.g. `https://<host>`, no path | must match `^https://[A-Za-z0-9.-]+$` |
| `PAGES_BASE_PATH` | the path the site is served under, `/` or `/<repo>/` | must match `^/([A-Za-z0-9._-]+/)*$`, so it begins and ends with `/` |
| `PAGES_PUBLICATION_APPROVED` | the step 1 decision, literally `approved` | exact string comparison |

These are variables and not secrets on purpose. Both values appear in every page the
build emits, so hiding them would be theatre, and it would hide them from the logs that
make a deployment auditable.

No secret is required by either workflow. If a future step needs one, it does not belong
in a job that runs on `pull_request`, because that trigger runs a contributor's code.

### 4. Inspect the hosted run for that SHA

The push in step 2 triggers `verification`, because `ci.yml` listens to `push` on `main`
and on `release/**`. Open the run, and read it against the SHA recorded in step 2 rather
than against the branch name. Identify it fully — repository, workflow, event, commit, run
id and attempt — because "the latest run" stops identifying anything the moment there are
two.

What to look at, in order:

- **Did every job run.** A skipped job is not a passing job. The graph is
  `source-policy` → the three Python jobs → `figure-contract` → `qa-plan` →
  `site-release` (one leg per base path). If a job is grey, find out why before reading
  anything below it.
- **`site-release`, both legs.** Each leg runs `scripts/build_release.py` for its base
  into its own output directory, then fingerprints that directory, serves it, runs the
  full browser suite against it, and fingerprints it again. A green leg is a statement
  about the bytes that were fingerprinted, which is the only version of "the tests
  passed" worth having.
- **The ten-step table the sequence prints.** `build_release.py` reports each step as
  PASSED, FAILED or BLOCKED. BLOCKED means a step could not run, and it fails the run;
  it is not a "not applicable". Step `06-download-identity` is the one that checks every
  published download against the canonical file it copies, and it is the first time that
  check runs on Linux.
- **The line beginning `REDUCED coverage`.** The verification workflow passes
  `--verify-cases fast` because its own `synthetic-cases` job re-runs every case in the
  same run, so that one reduction is expected and the workflow refuses any other. The
  deployment build in `pages.yml` passes `--verify-cases all` and refuses every
  reduction. If a `REDUCED` line appears that you did not expect, the run checked less
  than the last one did.
- **The skip policy step in each leg.** It runs `scripts/check_skip_policy.py`, the same
  gate the local path and the deployment workflow run, and prints an executed/skipped
  count per engine, every skip by capability id, and what each control-fixture probe
  measured on each engine. Read that list. A skip is a check that was not made, and the
  list is short enough to read every time. The machine-readable copy is written next to
  the Playwright report and travels in the evidence artifact.
- **The uploaded evidence artifact**, if any leg is red. It carries the Playwright JSON
  and the per-step logs of the canonical sequence for the failing leg.

### 5. Resolve hosted failures

A hosted failure is resolved by fixing the cause and pushing a new commit, then repeating
step 4 against the new SHA. It is not resolved by re-running the job until it is green, by
adding `continue-on-error`, by narrowing a matrix, or by lowering a threshold. Neither
workflow contains any of those and neither should acquire one; if a target turns out to be
wrong, the way to change it is evidence and a regression test, in that order.

Two failure shapes deserve naming because they are likely and they are not bugs in the
site:

- **A platform difference in the Python lock.** `requirements-dev.lock` was resolved on
  macOS/arm64 and carries no hashes. A wheel that exists there may be absent on Linux and
  `pip check` will say so. The fix is to regenerate the lock on Linux, not to relax the
  install.
- **A platform difference in what the engines can express.** This used to be a defect in
  the suite: three keyboard checks skipped on `browserName === "webkit"` with the reason
  "macOS WebKit excludes links from the tab order by default" — an engine name standing in
  for a capability, and a claim about macOS asserted on a Linux runner. It has been
  replaced. Each of those skips is now decided by a control fixture measured in the same
  run: a page with one link and one button for the tab ring, a 300px box with a 2000px
  child for arrow-key scrolling. Neither fixture carries anything of the site.

  So on Linux the skip count may legitimately differ from the 14 macOS takes. If Linux
  WebKit puts links in the tab ring, those checks **run** there and the count drops with no
  edit anywhere; if it does not, they skip with that run's own measurement attached. The
  gate reads what was measured rather than a count, and
  `scripts/check_skip_policy.py` fails if a skip's measurement disagrees with the
  independent probe — which is what a site defect wearing a capability excuse looks like.
  Read the per-engine table the gate prints; it says which engine ran what.

### 6. Deploy the tested artifact, manually

`pages.yml` has one trigger, `workflow_dispatch`, and no other.

Two things about dispatching it that are easy to get wrong. A manually dispatched workflow
must exist **on the default branch** — so `pages.yml` has to be on `main` before it can be
started at all, which it is once step 2 has fast-forwarded `main`. And `--ref` takes a
branch or a tag, never a bare commit SHA; the commit is resolved on the server after the
dispatch, so a branch that moves in between would publish something else.

That is what `expected_sha` is for. It is required, it must be a full 40-character
lowercase SHA, and the preflight job compares it with `github.sha` — the commit this run
actually checked out — before any expensive step runs. A mismatch fails the run and
nothing is built or deployed. Checking the ref's SHA before dispatching is still worth
doing, but it is the weak end of the binding; this is the strong one.

```
VERIFIED_SHA=<the 40-character SHA that passed step 4>
git ls-remote origin main                 # confirm main resolves to it, before dispatch
gh workflow run pages.yml \
    --repo "$OWNER/$REPO" \
    --ref main \
    -f acknowledge=PUBLISH \
    -f expected_sha="$VERIFIED_SHA"
```

Then confirm the run that started is on that SHA again, from the run's own record rather
than from the dispatch:

```
gh run list --repo "$OWNER/$REPO" --workflow pages.yml --limit 1 \
    --json databaseId,headSha,event,status,conclusion
```

What the run then does, in order, and what to watch:

1. `preflight` checks the acknowledgement and the three variables from step 3 and fails
   loudly, naming the missing one, if the configuration is not there.
2. `verification` runs the entire pipeline from step 4 again, as a reusable workflow. The
   gate in front of a deployment is the same gate that runs on a pull request, by
   construction, not by two lists someone keeps in step by hand.
3. `build` installs from the lock and runs `scripts/build_release.py` at the real base
   path with `--verify-cases all` and the real `--site-url`, which builds the site
   **once** into `site/dist-deploy`. It then fingerprints the result, serves that exact
   directory, runs the full browser suite against it, checks the skip policy, confirms
   the fingerprint is unchanged, and uploads that directory and nothing else. The step
   summary prints the file count and the fingerprint.
4. `deploy` publishes the artifact that run produced. It is the only job in either
   workflow with write permissions, and it holds exactly `pages: write` and
   `id-token: write`.

The artifact that is deployed is the artifact that was tested. There is no second build
between the tests and the upload, no committed `dist`, and no rebuild in the deploy job.
If the architecture ever changes so that a second build is unavoidable, that build has to
repeat this validation and its fingerprint has to be shown to match, or the sentence at
the top of this paragraph stops being true and this runbook has to stop saying it.

### 7. Record what was deployed

Copy the block the `build` job printed into its step summary, here:

| field | value |
| --- | --- |
| commit | _(40-character SHA)_ |
| origin | _(from `PAGES_SITE_ORIGIN`)_ |
| base path | _(from `PAGES_BASE_PATH`)_ |
| files | _(count)_ |
| fingerprint | _(sha256 of the sorted digest listing)_ |
| run id | _(from the run URL)_ |
| page URL | _(from the deploy job's environment URL)_ |
| deployed at | _(UTC)_ |

The fingerprint is the sha256 of the sorted `sha256sum` listing of every file in the
built directory. It is what makes "the deployed revision" checkable later: re-running the
build at the same commit with the same Node version reproduces it, and if it does not,
something between the commit and the published bytes is not deterministic and that is
worth knowing.

### 8. Verify the live site

The workflow does not do this and cannot. It checks a directory on a runner; the public
site is served by a different system with its own redirect, caching and index behaviour.
Check, against the real origin:

- **Every route.** `/`, `/studies/`, `/studies/a1/`, `/studies/a2/`, `/studies/a3/`,
  `/studies/a4/`, `/methods/`, `/about/`. Each must answer 200 and carry one `h1`.
- **Base behaviour.** Every internal link and every asset URL carries the configured base
  prefix. A site built for `/` and served from `/<repo>/` looks correct on the home page
  and 404s on the first click, which is exactly the failure that is easy to miss.
- **Trailing slash.** The site is built with `trailingSlash: "always"`. A request for a
  directory without the slash must redirect to the slashed form rather than 404.
- **404.** An unknown path returns the built `404.html` under a 404 status, not a 200 and
  not the host's generic page.
- **Downloads.** Fetch several files under `/data/`, including at least one CSV, one JSON
  and one SVG, and compare each against the `bytes` and `sha256` recorded in
  `site/public/data/index.json`. That index claims each published SVG is byte-identical
  to the file the page inlines; this is the step that checks the claim survived the trip
  through the host.
- **No network beyond the origin.** Load a page with the browser network panel open and
  confirm there is no request to any third party: no analytics, no CDN, no remote font.
- **The disclosures.** Spot-check that the published pages still say what this repository
  requires them to say: the data is synthetic and labelled as such, the inventory is not
  called recoverable gas or reserves, the conditional holdout still discloses that it
  uses future synthetic Z, and there are eight computed aquifer cases with nothing
  interpolated between them.

Record the results next to the table in step 7. A deployment that has not been checked
against its own URL is a deployment nobody has verified.

## What this runbook does not authorise

- Inventing a destination. If `PAGES_SITE_ORIGIN` is unset, the correct outcome is a red
  preflight, not a plausible-looking default.
- Deploying with the browser QA red. It is green as of 2026-09-14 and the gate is step 3
  above; this line is the rule, not a status.
- Claiming a hosted CI result from a local one. See the first section.
- Publishing any form of the restricted NIST extract, or anything derived from it.

## Status

| item | state |
| --- | --- |
| git remote | none |
| hosted repository | does not exist |
| Pages site | not provisioned |
| `PAGES_SITE_ORIGIN`, `PAGES_BASE_PATH`, `PAGES_PUBLICATION_APPROVED` | unset |
| hosted run of `verification` | **NOT RUN** |
| hosted run of `pages` | **NOT RUN** |
| deployed revision | none |

Last reviewed 2026-09-14 against `release/rc-close`.
