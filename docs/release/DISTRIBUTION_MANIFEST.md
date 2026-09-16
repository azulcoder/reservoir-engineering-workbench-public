# Distribution manifest

What a published artefact of this project contains, what it excludes and why, and the
exact commands that verify both. Every file list and exit code below was produced by
running the commands on this repository at version 0.2.0; where something could not be
run as written, that is said rather than glossed.

## The artefacts

| Artefact | Name | Built by |
|---|---|---|
| Wheel | `reservoir_performance_lab-0.2.0-py3-none-any.whl` | `python -m build` (hatchling) |
| Source distribution | `reservoir_performance_lab-0.2.0.tar.gz` | `python -m build` (hatchling) |
| Git repository | the public tree itself | `scripts/check_public_release.py` gates it |
| Static site | the directory named by `--out-dir` | `scripts/build_release.py` |

The wheel is pure Python and platform independent (`py3-none-any`). It has no runtime
dependencies: `dependencies` in `pyproject.toml` is empty and stays empty, and a test
walks the import graph of every module under `src/` to keep that list honest. Plotting
and cross-checking libraries live in the `analysis` extra, used only by `cases/`, and
the toolchain lives in the `dev` extra.

## What the wheel contains

19 entries, and nothing else:

```
reservoir_lab/__init__.py            reservoir_lab/numerics.py
reservoir_lab/aquifer.py             reservoir_lab/provenance.py
reservoir_lab/depletion.py           reservoir_lab/pseudopressure.py
reservoir_lab/diagnostics.py         reservoir_lab/regression.py
reservoir_lab/errors.py              reservoir_lab/units.py
reservoir_lab/gas.py                 reservoir_lab/validation.py
reservoir_lab/gas_properties.py
reservoir_lab/material_balance.py

reservoir_performance_lab-0.2.0.dist-info/METADATA
reservoir_performance_lab-0.2.0.dist-info/WHEEL
reservoir_performance_lab-0.2.0.dist-info/RECORD
reservoir_performance_lab-0.2.0.dist-info/licenses/LICENSE
reservoir_performance_lab-0.2.0.dist-info/licenses/NOTICE.md
```

The library, its licence and its notice. No data directory, no case studies, no docs, no
tests, no scripts. That narrowness is deliberate and is itself a control: there is no
directory in the wheel where a restricted file could sit unnoticed.

## What the source distribution contains

The sdist carries the reproducible project: `src/`, `tests/`, `cases/`, `configs/`,
`examples/`, `docs/`, `scripts/`, the four `data/` policy documents, the packaging
metadata, the development lock and the pre-commit configuration. Its contents are
enumerated in `[tool.hatch.build.targets.sdist]` rather than filtered, so a new
top-level directory has to be added there deliberately before it can ship.

The `data/` portion of the sdist is exactly four files:

```
data/README.md
data/raw/README.md
data/reference/README.md
data/reference/MANIFEST.json
```

## What both artefacts exclude, and why

| Excluded | Why |
|---|---|
| `data/reference/nist_methane_isotherms.tsv`, `nist_carbon_dioxide_isotherms.tsv`, `nist_nitrogen_isotherms.tsv` | NIST Standard Reference Data. Copyrighted under a statutory exception (Public Law 90-396); citation alone is not established as permitting redistribution. See `docs/release/PUBLIC_DATA_POLICY.md`. Excluded from the tree, from git history, and by an explicit `**/*.tsv` rule in the sdist target so a locally acquired copy cannot be swept into an archive. |
| `cases/A2_pvt_independent_check/protocol.md`, `report.md`, `results/summary.json`, `results/run_record.json` | Derived from that extract and quote its values. `run.py` ships; it exits 1 and says the reference table is absent rather than producing a result from nothing. |
| `artifacts/` | Local run output. Reproducible from a committed configuration and a recorded revision, and it carries absolute paths from the machine that produced it. |
| `site/`, `site/node_modules/` | Presentation build inputs. Not part of the library, and `node_modules` is a resolved dependency tree, not project source. |
| `.venv/`, `dist/`, `build/`, `__pycache__/`, `*.py[cod]`, `.DS_Store` | Environments, build output and OS noise. |
| Any third-party dataset, simulator deck, book, paper or binary | None is acquired. Where a study would use one, the repository stores retrieval instructions and checksums; the third party's licence governs the material. |

## Verifying an artefact

Everything below runs from a clean checkout. Exit codes are the check.

### 1. Gate the tree before building

```
python3 scripts/check_public_release.py --verbose
```

Exit 0 means no restricted file in the working tree or anywhere in git history, no
NIST-derived numeric payload in any scanned format, the publication decision stated
consistently across the manifest, the licence, the notice and the data README, and no
credential or private absolute path. Exit 1 means do not publish; the summary names every
item. Add `--fail-on-warning` to treat the advisory findings as blocking too, and `--json`
to consume the findings from another tool.

The gate reads git history with `git rev-list --objects --all --reflog`, content-hashes
every blob it finds, and compares those hashes against the digests `MANIFEST.json`
records. A restricted file that was committed and later deleted, or committed under a
different name, is caught by content rather than by path.

### 2. Build

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m build
```

`requirements-dev.lock` is a freeze of the resolved development environment, with the
interpreter, platform and resolution date recorded in its header. It pins the toolchain
only; the library itself has no runtime dependencies to pin.

### 3. Check the built contents

```
python3 -m zipfile -l dist/reservoir_performance_lab-0.2.0-py3-none-any.whl
tar tzf dist/reservoir_performance_lab-0.2.0.tar.gz | sed 's|^[^/]*/||' | sort
```

Then the two things that matter, which must both print nothing:

```
tar tzf dist/reservoir_performance_lab-0.2.0.tar.gz | grep -i '\.tsv'
python3 -m zipfile -l dist/reservoir_performance_lab-0.2.0-py3-none-any.whl | grep -i '\.tsv'
```

And the private-path sweep over an extracted sdist, which must report only files that
are known and accounted for:

```
tar xzf dist/reservoir_performance_lab-0.2.0.tar.gz -C /tmp
grep -rlE '/Users/[A-Za-z0-9._-]+/|/private/tmp/' /tmp/reservoir_performance_lab-0.2.0
```

### 4. Install the wheel somewhere clean and use it

The point of installing into a second environment and running from outside the checkout
is that a working directory on `sys.path` will import `src/` and hide a packaging
mistake completely.

```
python3 -m venv /tmp/smokeenv
/tmp/smokeenv/bin/python -m pip install dist/reservoir_performance_lab-0.2.0-py3-none-any.whl
cd /tmp && /tmp/smokeenv/bin/python -c "
import reservoir_lab
from reservoir_lab import gas_properties, units
pc = gas_properties.pseudocritical_sutton(0.65)
t_pr = units.fahrenheit_to_rankine(200.0) / pc.temperature_degr
p_pr = 2000.0 / pc.pressure_psia
z = gas_properties.z_factor_dak(t_pr, p_pr)
zhy = gas_properties.z_factor_hall_yarborough(t_pr, p_pr)
assert abs(z - zhy) < 5e-3, (z, zhy)
assert abs(units.fahrenheit_to_rankine(60.0) - 519.67) < 1e-12
print(reservoir_lab.__version__, reservoir_lab.__file__, z, zhy)
"
```

Two independently implemented deviation-factor correlations agreeing to a few parts in
ten thousand is a better smoke check than an import: it proves the installed module
computes, not merely that it loads.

### 5. Verify the editable install used for development

```
python3 -m venv /tmp/editenv
/tmp/editenv/bin/python -m pip install -e ".[dev]"
cd /tmp && /tmp/editenv/bin/python -c "
import reservoir_lab, pathlib
print(pathlib.Path(reservoir_lab.__file__).resolve())
"
```

The printed path must point at `src/reservoir_lab/` inside the checkout. If it points
into `site-packages`, the editable install did not take and tests are running against a
stale copy.

### 6. Run the suite

```
.venv/bin/python scripts/check.py
```

In a published tree this reports 20 skipped tests, every one of them in
`tests/test_gas_properties.py` with the message `NIST reference extract not present`, and
zero failures. The skips are the visible cost of the non-redistribution decision. They
are left visible on purpose: a stub that returned plausible numbers would turn a missing
oracle into a passing test, which is worse than a skip in every way that matters.

## Results of running this, 2026-09-13

| Step | Command | Exit | Result |
|---|---|---|---|
| Gate | `scripts/check_public_release.py` | 1 | Fails on findings in files outside this change's scope; see the summary it prints. No restricted file in the tree, and none in history. |
| Lock | `pip freeze --exclude-editable > requirements-dev.lock` | 0 | 19 pinned packages, CPython 3.13.2, darwin arm64. |
| Build | `python -m build` | 0 | Wheel and sdist built, in a copy of the tree carrying a placeholder `README.md`. `pyproject.toml` declares `README.md` as the readme, and hatchling fails the build with `OSError: Readme file does not exist: README.md` until that file is present. Re-run the build in place once it is; the file lists below are not affected by which README is used. |
| Wheel contents | `python -m zipfile -l` | 0 | 14 modules plus `dist-info`; `LICENSE` and `NOTICE.md` under `dist-info/licenses/`. |
| Sdist contents | `tar tzf` | 0 | No `artifacts/`, no `site/`, no `dist/`, no `.venv/`. `data/` limited to the four policy files. |
| Restricted data in artefacts | `grep -i '\.tsv'` over both | 1 (no match) | None. |
| A2 artefacts in sdist | `grep A2_` over the sdist listing | 0 | `cases/A2_pvt_independent_check/run.py` only. |
| Wheel install and use | fresh venv, install, run from `/tmp` | 0 | `z_factor_dak = 0.89735405`, `z_factor_hall_yarborough = 0.89774461`, difference 3.9e-4. |
| Editable install | fresh venv, `pip install -e ".[dev]"` | 0 | Resolves into the checkout; `pytest`, `ruff`, `mypy`, `pre_commit` present. |
| Suite | `scripts/check.py` | 0 | 641 run, 0 failed, 20 skipped. |

## The static site: one build sequence, one output directory

`scripts/build_release.py` is the whole definition of building this site. Nothing else
builds a publishable one, and there is no second list of steps to keep in step by hand.

```
python3 scripts/build_release.py --base-path / --out-dir site/dist/root
python3 scripts/build_release.py \
    --base-path /reservoir-engineering-workbench-public/ \
    --out-dir site/dist/project
```

| # | Step | What it runs | Why it is where it is |
|---|---|---|---|
| 1 | public-source policy | `scripts/check_public_release.py` | A tree that may not be published is not worth building. |
| 2 | verification prerequisites | `scripts/verify.py --profile public-core` | The numbers are checked before anything draws them. |
| 3 | figure-data validation and reconciliation | `scripts/export_presentation_data.py` into a scratch directory, then a byte comparison with the committed export | The exporter reconciles every value against the frozen case summary and refuses to write on a disagreement; this also proves the committed export is what the exporter produces today. |
| 4 | figure rendering | `node scripts/render-figures.mjs` | Figures are drawn only from data that passed step 3. |
| 5 | public-download emission | `node src/scripts/emit-public-data.mjs` | Downloads are copied from the canonical rendered outputs of step 4. |
| 6 | download/source consistency | `node src/scripts/emit-public-data.mjs --verify` | Closes F4. See the next section. |
| 7 | site and tooling type checks | `npm run check` | `astro check` plus `tsc` over scripts, tests and the Playwright config. |
| 8 | static site generation | `npx astro build --outDir <out>` | The base path comes from `--base-path`; the output directory from `--out-dir`, so two base builds never write into the same place. |
| 9 | required-output validation | in-process, `validate_output` | Routes, downloads, figure identity in the built HTML, raster placement, base-path correctness. |

Three properties it is built to have:

- **Real exit status through any log.** Every command runs through `subprocess.Popen` and
  its status comes from `wait()`. The tee to the per-step log is done in Python, so no
  step's status is ever the exit status of `tee`. `--log-dir` gives the logs a home;
  `--json` writes the summary; neither involves a shell pipeline.
- **A skipped step is not a pass.** A step that cannot be attempted is BLOCKED and the run
  fails. Narrowing a step through an argument — `--verify-cases fast`, the default — is
  reported in the summary under `coverage_reductions`, so a green run cannot be read as
  wider than it was.
- **A machine-readable summary.** Every step with its argv, exit code, duration and log.

The `npm` wrappers are `npm run release`, `npm run release:project` and `npm run drills`.
One caveat worth knowing: a bare `npm run build` uses Astro's default output directory,
`site/dist`, and Astro clears that directory, which removes `site/dist/root` and
`site/dist/project` with it. Run the release builds after a bare build, not before.

## The download chain, and what closes F4

`site/public/data/index.json` says of every published figure that it is byte-identical to
the file the page inlines. Until this pass nothing compared the two. The published copy
was checked against a digest written by the same script that made the copy, so a figure
could be re-rendered while its published copy went stale and both still agreed with the
stale digest. That was finding F4, and drill H in `docs/release/UI_QA.md` recorded it as
"exit 0, no message".

The chain is now enforced at build time at every link:

```
checked numerical data      site/src/data/figures/*.json, digests declared in contract.json
        |                   re-hashed by the renderer and by src/lib/figures.ts
figure specification        site/src/generated/figures/manifest.json
        |
canonical rendered figure   site/src/generated/figures/<id>.svg and <id>.png
        |
published download          site/public/data/figures/<id>.svg and <id>.png
        |
displayed figure            the SVG inlined into the built HTML
```

Two independent gates, either of which alone fails the build:

1. `node src/scripts/emit-public-data.mjs --verify` re-emits the whole tree into a scratch
   directory and compares it with what is published, byte for byte and in both
   directions; then compares every published figure artefact against the canonical file
   it claims to copy; then re-hashes the index; then checks the drawing against its
   specification and two presentation floors. Emission is deterministic, so anything
   published that is not what the emitter would write today is named by file.
2. `astro build` itself. `src/scripts/public-data.ts` compares each published SVG with the
   canonical rendered figure the same build is inlining, and refuses the build on any
   difference. Observed, with a published SVG altered by three bytes and its index digest
   updated to match: `astro build` exit 1, `PublicDataError: [public-data] published
   figure "figures/f01.svg" is not the drawing this build displays`, with both digests.

**The one transformation, stated and tested separately.** `src/scripts/exhibits.ts` trims
leading and trailing whitespace from the canonical SVG before inlining it, and changes
nothing else: no id is rewritten, no accessibility association is re-pointed, no attribute
is added or removed. Source-to-download identity stays exact; the trim applies to the
displayed copy alone. Step 9 of the build sequence proves it by requiring the trimmed
canonical bytes to appear verbatim as a substring of the built HTML for every figure a
page displays.

**Variants are registered, never conflated.** Each figure is published in two variants,
each with its own provenance in `index.json`:

| Variant | File | Identity claim |
|---|---|---|
| `canonical-vector` | `<id>.svg` | byte-identical to `site/src/generated/figures/<id>.svg`, which is what the page inlines |
| `raster-export` | `<id>.png` | byte-identical to `site/src/generated/figures/<id>.png`; the same drawing as the SVG at 216 dpi, in a different encoding — never described as the same bytes |

There is no compact/wide pair today. F01 and F01b are two figures with different questions
and different domains, each with its own manifest entry, not two renderings of one. A real
size variant added later gets its own registry entry, its own provenance and its own link
text; it does not inherit another variant's, and two intentionally different layouts are
never called identical.

## Published downloads, and where the bytes are

Measured from `site/public/data/index.json` after a clean run of the sequence.

| Class | Files | Bytes | In a page payload? |
|---|---|---|---|
| `full` — whole-dataset CSV and JSON | 28 | 473,381 | no, download only |
| `selected` — one computed case each | 16 | 220,189 | no, download only |
| `canonical-vector` — figures | 22 | 615,505 | the same bytes are inlined in the HTML |
| `raster-export` — PNG exports | 22 | 14,012,983 | **no** |
| Total | 88 | 15,322,058 | |

> **[RECOUNTED 2026-09-17]** The previous version of this table read 20 / 16 / 12 / 12 and a
> total of 60 files and 9,048,112 bytes, and named the last two classes `exhibit` and
> `exhibit-raster`. Those counts were already stale before case B2 was added, and the class
> names did not match what `index.json` actually writes. Every figure in the table above was
> recounted directly from `site/public/data/index.json` after a clean run of the sequence
> rather than adjusted by the difference. Nothing about the policy changed; only the
> measurement of it was wrong.

The rasters are accounted for separately because they behave differently from everything
else in the table. Nothing on the site inlines, embeds or preloads one: they are reachable
only as a download link, step 9 of the build sequence fails if any page carries an `<img>`,
`<image>` or `<link>` pointing at one, and `dataIndex()` reports them in their own block so
no page can fold them into a payload figure. 14.0 MB of PNG is 91 percent of the published
download bytes and 0 percent of what a reader downloads to read a page.

Per figure, vector and raster:

| Figure | SVG | PNG (216 dpi) |
|---|---|---|
| F01 | 26,492 | 561,566 |
| F01b | 23,057 | 479,059 |
| F02 | 18,366 | 443,133 |
| F03 | 43,075 | 766,665 |
| F04 | 34,384 | 609,144 |
| F05 | 34,880 | 687,863 |
| F06 | 24,016 | 677,914 |
| F07 | 15,982 | 516,737 |
| F08 | 37,246 | 677,497 |
| F09 | 48,633 | 1,457,920 |
| A1-01 | 24,508 | 755,432 |
| A3-01 | 25,044 | 625,590 |

The rasters come from the reviewed renderer — `site/scripts/render-figures.mjs`, through
sharp (libvips and librsvg), from the exact canonical SVG — and not from a browser
screenshot. Text in the raster is set by the rasteriser's fontconfig rather than by a
reader's system font stack, which is the reason the SVG stays the authoritative artefact
and the PNG is described as a shareable export.

Per-figure data downloads are unchanged: the full dataset and the selected case remain
separate files with separate names, and nothing derived from the withheld reference
outputs is published in any variant.

## Failure drills

`scripts/drills_release.py` breaks one thing at a time in a throwaway copy of the tree,
runs the gate that should notice, records the exit code and the sentence that named the
problem, then restores the fixture and requires the gate to return to zero. The repository
is read once to make the copy and never written. `cases/*/results/*.json` are copied
because the emitter reads two blocks out of them; every drill digests both before and
after and fails if either moved.

Run on a clean tree, 2026-09-14: 10 cases, 10 caught, 0 not caught, exit 0.

| Drill | What was broken | Gate | Exit | Message |
|---|---|---|---|---|
| stale-public-copy | canonical figure re-rendered, manifest updated consistently, published copy left alone (this is F4) | `emit-public-data --verify` | 1 | `2 published file(s) differ from a fresh emission: figures/f01.svg: published 26492 B sha 664e9fe191ab, a fresh emission writes 26492 B sha b078ca3950c5` |
| tampered-download | published SVG repainted and its `index.json` digest updated to match | `emit-public-data --verify` | 1 | `figures/f03.svg: published 43038 B sha 00cea49bd12b, a fresh emission writes 43038 B sha ceb475f070c9` |
| missing-artefact | published download removed | `emit-public-data --verify` | 1 | `site/public/data: 1 missing (figures/f05.png), 0 unexpected (none)` |
| missing-artefact | canonical raster variant removed | `emit-public-data --verify` | 1 | `figure F05: manifest.json declares f05.png but the canonical file is absent` |
| missing-artefact | figure data file removed | `emit-public-data --verify` | 1 | `cannot read required source .../f03_bias_sweep.json` |
| wrong-binding | the J = 2 selected-case download serves the J = 60 case's numbers, digest updated to match | `emit-public-data --verify` | 1 | `f01_f02_case-2.json: published 21663 B sha be3fc36f88e7, a fresh emission writes 21587 B sha 4508d6f3f31e` |
| wrong-binding | the specification's accessible name and unit made to disagree with the drawing's | `emit-public-data --verify` | 1 | `f04.svg: the drawing's accessible name is "F04 — what the inventory estimate does as history accumulates" but the specification records "F04 — progressive fits, in barrels"` |
| below-floor-text | an annotation set to 9px and republished, so only the presentation gate can fire | `emit-public-data` then `--verify` | 1 | `f01.svg: text set below the 13px floor the figure specification records: 9px` |
| below-floor-text | an annotation's anchor moved outside the viewBox and republished | `emit-public-data` then `--verify` | 1 | `f01.svg: 1 text anchor(s) outside the 1000x876 viewBox -- (1480.0, 486.7)` |
| numerical-reconciliation | one exported value moved by 5 percent | `emit-public-data --verify` | 1 | `3 published file(s) differ from a fresh emission: f03_bias_sweep.csv ...` |

Every case restored to exit 0 when the fixture was put back, and no drill moved a frozen
case summary. The numerical reconciliation tolerance belongs to
`scripts/export_presentation_data.py` — `RECONCILE_RELATIVE_TOLERANCE = 1.0e-12` — and the
drill reads it and prints it rather than setting it. No drill regenerates a case, relaxes a
tolerance or rewrites a result snapshot.

What the static-text gates cannot see, stated rather than implied: the text-floor check
resolves each label's effective `font-size` through the SVG's own ancestor chain, and the
axis tick labels Observable Plot emits carry no `font-size` at all — their rendered size
comes from the site stylesheet. `--verify` counts those labels per figure under
`text_with_inherited_size` and returns no verdict on them; the browser responsive check is
the instrument that can measure them and it owns that floor. The clipping check locates
each text anchor by accumulating the translate transforms above it and requires the anchor
to lie inside the viewBox; it does not measure glyph extents, so it catches an annotation
placed outside the drawing and not one that overflows the edge by a few pixels.

## Results of running the site sequence, 2026-09-14

Run on a clean tree — every tracked file at its working-tree state, plus the published
rasters, with `site/node_modules` symlinked. The reason for a clean tree rather than the
working copy is recorded under "what this manifest does not claim" below.

| Base path | Output | Exit | Steps | Files | Size | Seconds |
|---|---|---|---|---|---|---|
| `/` | `site/dist/root` | 0 | 10/10 passed | 81 | 11 MB (9.8 MB of it `data/`) | 49.2 |
| `/reservoir-engineering-workbench-public/` | `site/dist/project` | 0 | 10/10 passed | 81 | 11 MB (9.8 MB of it `data/`) | 143.3 |

The second run did not disturb the first: both output directories exist and are complete
after both runs, which is the property `--out-dir` exists to give.

Initial page payload at the project base, HTML only, rasters excluded by construction:

| Page | Bytes |
|---|---|
| `index.html` | 34,440 |
| `methods/index.html` | 76,365 |
| `studies/a4/index.html` | 574,718 |

## What this manifest does not claim

No hosted continuous integration has run these commands; the results above are from local
runs on one machine, on one platform, at one point in time. The artefacts have not been
uploaded anywhere, and no package index hosts this project. Nothing here has been through
external review, and none of the numerical results has been checked against field data.

The site sequence was measured on a clean tree, not on the working copy, and the reason is
a finding rather than a convenience. At the time of measurement the working copy carried
scratch files — `site/.qa-crop.mjs`, `site/.qa-print.mjs`, `site/.qa-removal.mjs` — with a
private sandbox path in them, and `scripts/check_public_release.py` fails on those as
`[FAIL] secrets`, which is the gate behaving correctly. Step 1 of the sequence therefore
fails on the working copy today, exit 1, and that is the honest state of the tree: it is
not publishable until those files are removed. The clean-tree numbers show what the
sequence does when the tree is publishable; they do not claim the tree is.

`--verify-cases fast` was used, so not every synthetic case was re-run in these timings.
The run reports that under `coverage_reductions` rather than leaving a green result to be
read as full coverage; `--verify-cases all` is the wider run.

The raster identity check is done where the bytes are readable as bytes. `astro build`
compares every published SVG with its canonical source, but `import.meta.glob` hands a
module text, so the published PNGs are not re-hashed inside the Astro build. Their byte
identity with the canonical rasters is enforced by `emit-public-data --verify`, which is a
mandatory step of the sequence, and by the served-digest check in the browser suite. That
split is stated here so that "the build verifies every download" is not read wider than
what was actually done.
