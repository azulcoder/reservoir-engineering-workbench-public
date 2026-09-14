/**
 * Check 3 -- axe-core on every route.
 *
 * What this is and is not. axe-core tests a subset of WCAG: it finds programmatically
 * detectable failures. It cannot judge whether an alternative is *accurate*, whether a
 * heading structure describes the document, whether focus order is sensible, or whether a
 * figure's second encoding channel is meaningful. A clean axe run is therefore evidence,
 * not conformance, and this file records the ruleset it ran so the gap is visible. The
 * judgements axe cannot make are in manual.spec.ts and in the written review.
 *
 * Both the default page state and the explorer's non-default state are scanned, because
 * the second is markup the first never displays.
 */
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { ROUTES, url } from "./support";

const TAGS = [
  "wcag2a",
  "wcag2aa",
  "wcag21a",
  "wcag21aa",
  "wcag22aa",
  "best-practice",
];

interface Row {
  route: string;
  state: string;
  rule: string;
  impact: string;
  help: string;
  nodes: string[];
  tags: string[];
}

const collected: Row[] = [];
const scans: string[] = [];

/* One file per worker. Playwright gives each worker its own module instance, so a single
   file name would be written by every worker and the last one to finish -- possibly one
   that ran no scan at all -- would win. An empty violations list has to mean "scanned and
   found nothing", which is only readable if the scans are recorded alongside it. */
test.afterAll(async ({}, testInfo) => {
  if (scans.length === 0) return;
  mkdirSync("test-results", { recursive: true });
  writeFileSync(
    `test-results/axe-${testInfo.project.name}-${process.env.QA_PORT ?? "4321"}-w${testInfo.workerIndex}.json`,
    JSON.stringify({ tags: TAGS, scans, violations: collected }, null, 2),
  );
});

async function scan(page: import("@playwright/test").Page, route: string, state: string) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  scans.push(`${route} (${state})`);
  for (const v of results.violations) {
    collected.push({
      route,
      state,
      rule: v.id,
      impact: v.impact ?? "unknown",
      help: v.help,
      tags: v.tags,
      nodes: v.nodes.slice(0, 4).map((n) => n.html.replace(/\s+/g, " ").slice(0, 160)),
    });
  }
  return results.violations;
}

test.describe("axe-core", () => {
  for (const route of ROUTES) {
    test(`${route} has no axe violation at WCAG 2.2 AA plus best-practice`, async ({ page }) => {
      await page.goto(url(route), { waitUntil: "load" });
      const violations = await scan(page, route, "default");
      const summary = violations.map(
        (v) => `${v.id} [${v.impact}] x${v.nodes.length}: ${v.help}`,
      );
      expect(summary, `axe violations on ${route}`).toEqual([]);
    });
  }

  test("/404.html has no axe violation", async ({ page }) => {
    await page.goto(url("/404.html"), { waitUntil: "load" });
    const violations = await scan(page, "/404.html", "default");
    expect(violations.map((v) => `${v.id} [${v.impact}]: ${v.help}`)).toEqual([]);
  });

  test("the explorer in a non-default state has no axe violation", async ({ page }) => {
    await page.goto(url("/studies/a4/") + "?case=60", { waitUntil: "load" });
    await expect(page.locator('[data-case="60"]')).toBeVisible();
    /* Open every disclosure too: a closed <details> hides its contents from axe. */
    await page.evaluate(() =>
      document.querySelectorAll("details").forEach((d) => ((d as HTMLDetailsElement).open = true)),
    );
    const violations = await scan(page, "/studies/a4/?case=60", "case=60, all disclosures open");
    expect(violations.map((v) => `${v.id} [${v.impact}]: ${v.help}`)).toEqual([]);
  });

  test("the explorer's invalid-case state has no axe violation", async ({ page }) => {
    await page.goto(url("/studies/a4/") + "?case=999", { waitUntil: "load" });
    await expect(page.locator("[data-explorer-invalid]")).toBeVisible();
    const violations = await scan(page, "/studies/a4/?case=999", "invalid case notice shown");
    expect(violations.map((v) => `${v.id} [${v.impact}]: ${v.help}`)).toEqual([]);
  });

  test("every route survives axe with all disclosures open", async ({ page }) => {
    const failures: string[] = [];
    for (const route of ROUTES) {
      await page.goto(url(route), { waitUntil: "load" });
      await page.evaluate(() =>
        document
          .querySelectorAll("details")
          .forEach((d) => ((d as HTMLDetailsElement).open = true)),
      );
      const violations = await scan(page, route, "all disclosures open");
      for (const v of violations) failures.push(`${route}: ${v.id} [${v.impact}] ${v.help}`);
    }
    expect(failures).toEqual([]);
  });
});
