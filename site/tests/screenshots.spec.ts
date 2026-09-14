/**
 * Screenshot capture.
 *
 * These are NOT pixel-comparison baselines and nothing here asserts on image bytes.
 * They are captures a person then looks at; the observations are written up in
 * docs/release/UI_QA.md. Pixel comparison across machines would be meaningless anyway:
 * these were taken on macOS with Chromium's own rasteriser, and macOS and Linux font
 * rasterisation are not comparable.
 *
 * Run it on its own, on one engine, so the file names mean one thing:
 *   PLAYWRIGHT_BROWSERS_PATH=... npx playwright test --project=chromium screenshots.spec.ts
 */
import { test, expect } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { url } from "./support";

const DIR = "screenshots";
const WIDTHS = [375, 768, 1440];

const captured: Array<{ file: string; what: string; width: number; engine: string }> = [];

test.beforeAll(() => mkdirSync(DIR, { recursive: true }));

test.afterAll(async ({}, testInfo) => {
  writeFileSync(
    join(DIR, `INVENTORY-${testInfo.project.name}.json`),
    JSON.stringify(
      {
        captured_on: new Date().toISOString().slice(0, 10),
        platform: process.platform,
        engine: testInfo.project.name,
        note: "captures for human inspection; not pixel baselines, not comparable across operating systems",
        files: captured,
      },
      null,
      2,
    ),
  );
});

async function shot(
  page: import("@playwright/test").Page,
  file: string,
  what: string,
  width: number,
  engine: string,
  fullPage = true,
) {
  await page.screenshot({ path: join(DIR, file), fullPage });
  captured.push({ file, what, width, engine });
}

test.describe("captures", () => {
  test("home and the case page at three widths", async ({ page }, testInfo) => {
    test.setTimeout(180_000);
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 900 });

      /* The home page is short enough to capture whole. */
      await page.goto(url("/"));
      await page.waitForTimeout(150);
      await shot(page, `home-${width}.png`, "home page, whole page", width, testInfo.project.name);

      /* The case page is not: a full-page capture of it is 30,000 pixels tall and about
         5 MB, which is a poor thing to put in a repository once per width. The first
         screen is captured instead, and the two things a full-page capture would have
         shown -- the clipped tables and the document width -- are in metrics-table-375.png
         and in the measurements in docs/release/UI_QA.md. To regenerate the full pages,
         pass true as the last argument to shot() below. */
      await page.goto(url("/studies/a4/"));
      await page.waitForTimeout(150);
      await shot(
        page,
        `a4-${width}.png`,
        "case page A4, first screen, default state",
        width,
        testInfo.project.name,
        false,
      );
    }
    expect(captured.length).toBeGreaterThanOrEqual(6);
  });

  test("the explorer in a non-default state", async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(url("/studies/a4/") + "?case=60");
    await expect(page.locator('[data-case="60"]')).toBeVisible();
    /* Anchor on the control itself, not the top of a section several screens tall, so
       the capture shows which case is selected. */
    await page.locator("[data-explorer-controls]").scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
    await shot(
      page,
      "explorer-case-60-1440.png",
      "scenario explorer with J = 60 selected, arrived by deep link",
      1440,
      testInfo.project.name,
      false,
    );

    /* And the invalid-case state, which is its own piece of evidence. */
    await page.goto(url("/studies/a4/") + "?case=999");
    await expect(page.locator("[data-explorer-invalid]")).toBeVisible();
    await page.locator("[data-explorer-invalid]").scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
    await shot(
      page,
      "explorer-invalid-case-1440.png",
      "scenario explorer asked for a case that does not exist",
      1440,
      testInfo.project.name,
      false,
    );

    /* The explorer at 375, where the panels have to scroll inside their own frame. */
    await page.setViewportSize({ width: 375, height: 900 });
    await page.goto(url("/studies/a4/") + "?case=0");
    await page.locator("[data-explorer-controls]").scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
    await shot(
      page,
      "explorer-case-0-375.png",
      "scenario explorer, volumetric control case, narrow viewport",
      375,
      testInfo.project.name,
      false,
    );
  });

  test("one exhibit on its own, at the widest and the narrowest width", async ({
    page,
  }, testInfo) => {
    /* The figure alone, so the rendered size of its axis labels can be judged by eye
       rather than inferred from a full-page capture that has been scaled to fit. */
    for (const width of [1440, 375]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(url("/studies/a4/"));
      await page.locator("#f01").scrollIntoViewIfNeeded();
      await page.waitForTimeout(200);
      await page.locator("#f01 .figure__frame").screenshot({
        path: join(DIR, `figure-f01-${width}.png`),
      });
      captured.push({
        file: `figure-f01-${width}.png`,
        what: "exhibit F01 alone, as rendered, for judging label legibility",
        width,
        engine: testInfo.project.name,
      });
    }
  });

  test("the unavailable-reference page", async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(url("/studies/a2/"));
    await shot(
      page,
      "a2-unavailable-1440.png",
      "A2, the study whose exhibits are withheld on rights grounds",
      1440,
      testInfo.project.name,
    );
  });

  test("the case page with JavaScript blocked", async ({ browser }, testInfo) => {
    const context = await browser.newContext({
      javaScriptEnabled: false,
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();
    await page.goto(url("/studies/a4/"));
    await page.screenshot({ path: join(DIR, "a4-nojs-1440.png") });
    captured.push({
      file: "a4-nojs-1440.png",
      what: "case page A4, first screen, with JavaScript blocked at the context level",
      width: 1440,
      engine: testInfo.project.name,
    });
    /* The explorer region on its own, which is where the difference is. */
    await page.locator("[data-explorer-static]").scrollIntoViewIfNeeded();
    await page.screenshot({ path: join(DIR, "explorer-nojs-1440.png") });
    captured.push({
      file: "explorer-nojs-1440.png",
      what: "the explorer section with JavaScript blocked: no control, base case in full",
      width: 1440,
      engine: testInfo.project.name,
    });
    await context.close();
  });

  test("the print stylesheet", async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 1200 });
    await page.goto(url("/studies/a4/"));
    await page.emulateMedia({ media: "print" });
    await page.waitForTimeout(200);
    await shot(
      page,
      "a4-print-top.png",
      "case page A4 under the print stylesheet, first screen",
      1440,
      testInfo.project.name,
      false,
    );
    await page.locator("#limits").scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
    await shot(
      page,
      "a4-print-limitations.png",
      "case page A4 under the print stylesheet, the limitations section",
      1440,
      testInfo.project.name,
      false,
    );
  });

  test("the widest table at 375, where the reflow finding is visible", async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 375, height: 900 });
    await page.goto(url("/studies/a4/"));
    await page.locator("#explorer").scrollIntoViewIfNeeded();
    await page.locator("#metrics-2").scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
    await shot(
      page,
      "metrics-table-375.png",
      "the three-column metrics table at 375: finding F3, clipped with no way to scroll",
      375,
      testInfo.project.name,
      false,
    );
  });
});
