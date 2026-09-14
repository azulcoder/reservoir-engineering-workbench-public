/**
 * Release mode: prove the browser visited the directory the release built.
 *
 * The rest of the suite asserts things about "the site". This file asserts which bytes
 * that phrase referred to, and it exists because the two can come apart silently.
 *
 * The failure it is aimed at
 * -------------------------
 * Release verification builds a candidate directory with scripts/build_release.py, starts
 * a server over it, fingerprints it, runs the suite, and fingerprints it again. Every part
 * of that is necessary and none of it is sufficient. The Playwright configuration used to
 * carry a managed `webServer` whose command is `astro build && node tests/serve.mjs` with
 * QA_DIST=dist, and `reuseExistingServer` chooses between the caller's server and that one
 * by probing a URL. A caller's server that dies after the readiness check hands the suite
 * to the fallback, which builds site/dist and serves that instead. The candidate directory
 * then passes its after-fingerprint unchanged -- unchanged because nothing ever read it.
 *
 * QA_RELEASE=1 removes the fallback. These checks confirm the mode is actually armed and
 * then close the loop the fingerprint cannot: they compare what the browser received over
 * HTTP with what is on disk in QA_DIST, byte for byte. A match is direct evidence that the
 * origin under test is serving the candidate and not some other build of the same site.
 *
 * The whole file is conditional on release mode rather than skipping inside it. A developer
 * running the suite against the managed server has no candidate directory to compare
 * against, and a skip there would be a skip with nothing to say.
 */
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { expect, test } from "@playwright/test";
import { BASE, url } from "./support";

const RELEASE = process.env.QA_RELEASE === "1";
const DIST = resolve(process.env.QA_DIST ?? "dist");

function sha256(buffer: Buffer | Uint8Array): string {
  return createHash("sha256").update(buffer).digest("hex");
}

if (RELEASE) {
  test.describe("release mode serves the directory the release built", () => {
    test("no managed server is configured, so there is nothing to fall back to", async () => {
      const configured = test.info().config.webServer;
      expect(
        configured ?? null,
        "QA_RELEASE=1 must leave Playwright with no webServer of its own. A configured " +
          "one can start `astro build` into site/dist and test that instead.",
      ).toBeNull();
    });

    test("the home page the browser received is the candidate's bytes", async ({ page }) => {
      const response = await page.goto(url("/"));
      expect(response, "a response for the home page").not.toBeNull();
      expect(response!.status()).toBe(200);

      const overWire = sha256(await response!.body());
      const onDisk = sha256(readFileSync(join(DIST, "index.html")));
      expect(
        overWire,
        `the home page served at ${BASE} does not match ${join(DIST, "index.html")}. The ` +
          `origin under test is serving some other build, so every other result in this ` +
          `run is about a directory that is not the one being released.`,
      ).toBe(onDisk);
    });

    test("a deep route and a published download are the candidate's bytes too", async ({
      page,
    }) => {
      /* One HTML route below the root and one binary asset, because a server can be
         correct about the page it was pointed at and wrong about everything under it --
         a stale copy of the site with a fresh index.html would pass the check above. */
      const route = await page.goto(url("/studies/a4/"));
      expect(route!.status()).toBe(200);
      expect(
        sha256(await route!.body()),
        "the case report served does not match the candidate's studies/a4/index.html",
      ).toBe(sha256(readFileSync(join(DIST, "studies", "a4", "index.html"))));

      const asset = await page.request.get(url("/data/figures/f01.svg"));
      expect(asset.status()).toBe(200);
      expect(
        sha256(await asset.body()),
        "the published figure served does not match the candidate's copy on disk",
      ).toBe(sha256(readFileSync(join(DIST, "data", "figures", "f01.svg"))));
    });
  });
}
