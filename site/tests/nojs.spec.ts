/**
 * Check 9 -- with JavaScript blocked.
 *
 * The claim the site makes about itself is strong: the evidence is in the delivered HTML
 * and the only script on the whole site reveals a control. This file blocks script
 * execution at the context level, which is what an enterprise policy or a content blocker
 * does, and then asks for the principal evidence: the figures, their numbers, their
 * caveats, and downloads that actually resolve.
 */
import { test, expect } from "@playwright/test";
import { ROUTES, url, CASES } from "./support";

test.use({ javaScriptEnabled: false });

test.describe("javascript blocked", () => {
  for (const route of ROUTES) {
    test(`${route} still renders its principal evidence`, async ({ page }) => {
      const res = await page.goto(url(route), { waitUntil: "load" });
      expect(res?.status()).toBe(200);
      await expect(page.locator("h1")).toHaveCount(1);
      await expect(page.locator("main#main")).toBeVisible();
      /* Something substantial is on the page, not a shell waiting for a script. */
      const words = (await page.locator("main").innerText()).split(/\s+/).length;
      expect(words, `words of prose on ${route}`).toBeGreaterThan(150);
    });
  }

  test("the case page keeps its figures, tables, caveats and downloads", async ({ page }) => {
    await page.goto(url("/studies/a4/"));
    /* Nine exhibits, drawn, with marks. */
    const svgs = page.locator(".figure__frame svg");
    expect(await svgs.count()).toBeGreaterThanOrEqual(9);
    const marks = await svgs.evaluateAll((els) =>
      els.map((s) => s.querySelectorAll("path, circle, line, rect, text").length),
    );
    for (const m of marks) expect(m).toBeGreaterThan(10);

    /* Every figure keeps its caveat and its evidence class. */
    expect(await page.locator(".figure__caveat").count()).toBeGreaterThanOrEqual(9);
    expect(await page.locator(".evidence-class").count()).toBeGreaterThanOrEqual(9);

    /* The limitations section is on the page, not behind a control. */
    await expect(page.locator("#limits")).toBeVisible();
    const limits = await page.locator("#limits").innerText();
    expect(limits.length).toBeGreaterThan(400);
  });

  test("the explorer shows the base case in full and hides its dead control", async ({ page }) => {
    await page.goto(url("/studies/a4/"));
    /* The control is hidden because it cannot work. */
    await expect(page.locator("[data-explorer-controls]")).toBeHidden();
    /* The note that explains its absence is visible instead. */
    const note = page.locator("[data-explorer-static]");
    await expect(note).toBeVisible();
    await expect(note).toContainText("Selecting a different");

    /* The base case is complete: three panels, both tables, its caveat, its downloads. */
    const base = page.locator('[data-case="2"]');
    await expect(base).toBeVisible();
    expect(await base.locator(".explorer__frame svg").count()).toBe(3);
    await expect(base.locator("#metrics-2")).toBeVisible();
    await expect(base.locator("table#obs-2")).toHaveCount(1);
    await expect(base.locator(".callout")).toBeVisible();
    expect(await base.locator(".explorer__downloads a").count()).toBe(2);

    /* And the other seven are hidden rather than half-shown. */
    for (const key of CASES) {
      if (key === "2") continue;
      await expect(page.locator(`[data-case="${key}"]`)).toBeHidden();
    }
  });

  test("every download on the case page resolves without a script", async ({ page, request }) => {
    await page.goto(url("/studies/a4/"));
    const hrefs = await page
      .locator("a[download]")
      .evaluateAll((as) => as.map((a) => a.getAttribute("href") ?? ""));
    expect(hrefs.length, "downloads offered with JavaScript off").toBeGreaterThan(10);
    const broken: string[] = [];
    for (const h of new Set(hrefs)) {
      const res = await request.get(h);
      if (res.status() !== 200) broken.push(`${h} -> ${res.status()}`);
      else if ((await res.body()).length === 0) broken.push(`${h} -> empty`);
    }
    expect(broken, "downloads that do not resolve").toEqual([]);
  });

  test("the full dataset carrying all eight cases is reachable with the selector dead", async ({
    page,
    request,
  }) => {
    await page.goto(url("/studies/a4/"));
    const full = await page
      .locator(".explorer__downloads--full a")
      .evaluateAll((as) => as.map((a) => a.getAttribute("href") ?? ""));
    expect(full.some((h) => h.includes("scenarios_all.csv"))).toBe(true);
    const csv = await (await request.get(full.find((h) => h.endsWith(".csv"))!)).text();
    /* All eight computed strengths are in that one file, which is the promise the page
       makes to a reader whose selector does not work. */
    for (const key of CASES) {
      expect(csv.split("\n").some((line) => line.split(",")[0] === key), `J = ${key} in the CSV`).toBe(
        true,
      );
    }
  });

  test("no page depends on a script for its navigation", async ({ page }) => {
    for (const route of ROUTES) {
      await page.goto(url(route));
      const nav = page.locator('nav[aria-label="Primary"] a');
      expect(await nav.count()).toBeGreaterThan(2);
      const hrefs = await nav.evaluateAll((as) => as.map((a) => a.getAttribute("href") ?? ""));
      for (const h of hrefs) expect(h).toMatch(/^\//);
    }
    /* And a link still navigates. */
    await page.goto(url("/"));
    await page.locator('nav[aria-label="Primary"] a').first().click();
    await expect(page.locator("h1")).not.toBeEmpty();
  });
});
