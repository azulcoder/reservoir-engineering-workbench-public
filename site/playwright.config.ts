import { defineConfig, devices } from "@playwright/test";

/**
 * Browser QA for the built site.
 *
 * Two things this configuration insists on.
 *
 * 1. It tests the BUILD, not the dev server. `webServer` runs `astro build` and then a
 *    static server over dist/ (tests/serve.mjs explains why not `astro preview`).
 *    That is the DEVELOPER loop. Release verification uses QA_RELEASE=1 instead; see
 *    below.
 *
 * 2. The base path is a variable, and the default is the NON-ROOT project base. A GitHub
 *    project site is served from a subdirectory, so that is the configuration that has to
 *    be proven; the root base is a second pass, run with QA_BASE=/.
 *
 *      npx playwright test                                  # project base, port 4321
 *      QA_BASE=/ QA_PORT=4322 npx playwright test           # root base
 *
 * 3. RELEASE MODE, QA_RELEASE=1, has no managed server at all.
 *
 *    In release verification the directory under test is the one scripts/build_release.py
 *    produced, fingerprinted before the suite and re-checked after, and the server over it
 *    is started by the caller. The managed `webServer` below would run `astro build` into
 *    site/dist -- a DIFFERENT directory -- and `reuseExistingServer` decides between the
 *    two by probing a URL. If the intended server dies between the caller's readiness
 *    check and the first test, that probe fails, Playwright starts its own, and the suite
 *    goes green against bytes nobody is shipping. A fingerprint of the untouched candidate
 *    directory would not notice: it is unchanged precisely because nothing visited it.
 *
 *    So release mode omits `webServer` entirely rather than configuring it more carefully.
 *    With no fallback to fall back to, an absent server is a connection refused on every
 *    test, which is the correct outcome: fail, do not substitute. tests/release-mode.spec.ts
 *    asserts the mode is armed, and serve.mjs independently refuses to serve a build made
 *    for a different base.
 *
 * Browser binaries are not in the user profile. Export
 * PLAYWRIGHT_BROWSERS_PATH=<repo>/site/.playwright-cache or nothing launches.
 */

const BASE = process.env.QA_BASE ?? "/reservoir-engineering-workbench-public/";
const PORT = Number(process.env.QA_PORT ?? (BASE === "/" ? 4322 : 4321));
const ORIGIN = `http://127.0.0.1:${PORT}`;

/** Release verification drives a prebuilt directory served by the caller. No fallback. */
const RELEASE = process.env.QA_RELEASE === "1";

/**
 * The managed developer server, or nothing at all in release mode.
 *
 * Deliberately a plain value rather than a conditional spread on the object below, so that
 * "release mode has no webServer" is one readable line and not a property that may or may
 * not exist depending on how an object literal was assembled.
 */
const managedServer = RELEASE
  ? undefined
  : {
      command: `npx astro build && node tests/serve.mjs`,
      url: `${ORIGIN}${BASE}`,
      /* Never reuse: the command rebuilds dist, and a reused server would silently serve
         the previous build. QA_REUSE=1 opts back in for a fast iteration loop. */
      reuseExistingServer: process.env.QA_REUSE === "1",
      timeout: 180_000,
      stdout: "pipe" as const,
      stderr: "pipe" as const,
      env: {
        SITE_BASE: BASE,
        QA_BASE: BASE,
        QA_PORT: String(PORT),
        QA_DIST: "dist",
      },
    };

if (RELEASE) {
  console.log(`[playwright] release mode: no managed server, ${ORIGIN}${BASE} must already answer`);
}

export default defineConfig({
  testDir: "./tests",
  testMatch: /.*\.spec\.ts/,
  /* The screenshot captures are excluded from an unfiltered run, and opted back in with
     QA_CAPTURES=1.

     They write fixed file names -- screenshots/home-1440.png and so on -- and the file
     says at the top that it must run on one engine "so the file names mean one thing".
     Nothing enforced that. `npx playwright test` with no filter, which is exactly what
     both workflows run, put three engines into the same seventeen paths concurrently:
     the committed captures became whichever engine finished last, and two extra
     INVENTORY files appeared. Measured, not deduced -- it happened here on 2026-09-14
     and `git checkout -- site/screenshots/` was the repair.

     Opting out by convention failed because convention is not a mechanism. The captures
     are a separate deliberate step and this is what makes them one:

       QA_CAPTURES=1 npx playwright test --project=chromium tests/screenshots.spec.ts

     They are not skipped when excluded. A skip is a check that could not be made, and
     these are not a check at all -- nothing in the file asserts on image bytes. Declaring
     an engine-wide skip for them would be exactly the "we stopped measuring on this
     engine" that site/tests/skip-policy.json exists to refuse. */
  testIgnore: process.env.QA_CAPTURES === "1" ? [] : ["**/screenshots.spec.ts"],
  fullyParallel: true,
  forbidOnly: true,
  retries: 0,
  workers: process.env.QA_WORKERS ? Number(process.env.QA_WORKERS) : 4,
  reporter: [["list"], ["json", { outputFile: `test-results/report-${PORT}.json` }]],
  timeout: 60_000,
  expect: { timeout: 10_000 },

  use: {
    baseURL: ORIGIN,
    trace: "off",
    screenshot: "off",
    video: "off",
    /* A real reader's default. Tests that need another setting declare it locally. */
    colorScheme: "light",
    reducedMotion: "no-preference",
  },

  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],

  webServer: managedServer,
});
