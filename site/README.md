# The publication site

A static Astro build that presents the studies in `cases/`. No UI framework, no CDN, no
analytics, no remote fonts. Figures are rendered to SVG at build time and inlined, so the
delivered HTML carries the evidence with no client JavaScript on any page but one.

Everything here reads committed data. The site never recomputes a reservoir quantity: the
figure data under `src/data/figures/` is produced by `scripts/export_presentation_data.py`
in the repository root, and `scripts/render-figures.mjs` fails closed if any file's SHA-256
disagrees with `src/data/figures/contract.json`.

## Prerequisites

Node and npm, and nothing else. Measured with Node 24.14.0 and npm 11.9.0; Astro 7 needs
Node 20 or newer. The Python side is not required to build the site.

```bash
cd site
npm ci
```

## Build

```bash
npm run figures   # render SVG from the committed figure data, into src/generated/figures/
npm run build     # figures, then astro build, into dist/
```

`npm run build` runs the figure step itself, so the first command is only needed when you
want to regenerate the SVG without a full build.

Deployment identity comes from the environment, because this repository has no remote and
no real values exist yet:

```bash
# root base — local inspection only
npm run build

# project base, the shape a GitHub project site is served at
SITE_BASE=/reservoir-engineering-workbench-public/ npm run build

# with an origin, for canonical URLs (example.invalid is a placeholder; supply the real one)
SITE_URL=https://example.invalid SITE_BASE=/reservoir-engineering-workbench-public/ npm run build
```

Every URL in the site is built through `base`, so a page that works at the root base and
breaks under a project base is a bug worth catching before deployment, not after. Build
both.

## Preview

```bash
export SITE_BASE=/reservoir-engineering-workbench-public/   # the same value the build used
npm run build
npm run preview   # http://localhost:4321/reservoir-engineering-workbench-public/
npx astro preview stop

npm run dev       # dev server, for editing pages
npm run check     # astro check
```

`astro preview` in Astro 7 runs as a background daemon and returns immediately; stop it
with `npx astro preview stop`, and read its output with `npx astro preview logs`. Measured
with the project base above: `/reservoir-engineering-workbench-public/` answers 200 and `/`
answers 404, which is the correct behaviour and the quickest way to confirm the base took.

`astro preview` re-reads `astro.config.mjs`, so it takes `SITE_BASE` from the environment
exactly as the build did. Build at a project base and preview without it and the server
will answer at `/` while the pages ask for their assets under the project base — a broken
preview of a correct build. Export the variable once and use it for both commands.

`preview` serves what was actually built. `dev` does not, so use `preview` for anything you
intend to believe about the output.

## Browser tests

Playwright 1.63.0 with `@axe-core/playwright` 4.13.0, across Chromium, Firefox and WebKit.
The browser binaries are in `site/.playwright-cache`, not in the user profile, so the
environment variable is mandatory — without it nothing launches.

```bash
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright-cache"   # from site/

npx playwright test                          # project base, port 4321 (the default)
QA_BASE=/ QA_PORT=4322 npx playwright test   # root base, second pass
```

The configuration builds the site and serves `dist/` over a static server before the tests
run; it does not test the dev server. The default base is the non-root project base,
because that is the configuration a project site has to prove.

At the time this file was written the suite collected 120 tests in three spec files
(`routes`, `runtime`, `axe`) across the three browser projects. No result is recorded here;
run it and read the run.

## What the build produces

Measured at the project base:

- **9 routes**: `/`, `/studies/`, `/studies/a1/` through `/studies/a4/`, `/methods/`,
  `/about/`, `/404.html`. The same 9 at the root base.
- **Largest page** is `/studies/a4/` at 573,287 bytes raw, 81,746 gzipped. Every other page
  is under 78 kB raw.
- **`dist/` totals 1.8 MB**, including the downloadable data files under `public/data/`.
- **JavaScript**: one inline module of 5,824 bytes, on `/studies/a4/` only, for the scenario
  explorer. Every other page ships no script tag at all. Zero external script files, zero
  `@font-face`, zero `@import`, zero analytics, zero cookies, zero `fetch`.
- The only external host string in the output is `www.w3.org`, which is an SVG namespace
  declaration and not a request.

The explorer script is a presentation control and nothing more: it reveals markup this
build already produced from the committed export, for the eight cases the study computed.
It does not interpolate, does not re-run anything, and with JavaScript switched off the
page shows the base case complete — panels, tables, caveat and working downloads.

## Deployment is unset, deliberately

`SITE_URL` and `SITE_BASE` have no defaults beyond a root-relative local preview. No
username, repository name or domain is written anywhere in this directory or in
`.github/workflows/pages.yml`, because none is known.

`pages.yml` has never run. Its only trigger is `workflow_dispatch`, it requires repository
configuration variables that do not exist, it requires a typed human acknowledgement, and
its build step fails rather than uploading an empty directory. Nothing has been deployed
and no site has been published.
