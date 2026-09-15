/**
 * Capture the executive-visual-review screenshots.
 *
 * Deliberately a standalone script and not a spec: these are review artefacts for a
 * person to look at, nothing asserts on image bytes, and they must be capturable against
 * two different builds (the before and the after) without editing a test.
 *
 * Usage:
 *   node tests/review-captures.mjs <out-dir> <base-url>
 *
 * The capture list is the one the review asks for, and each entry says what a reviewer is
 * meant to judge in it. Section captures are anchored on a heading so the same part of the
 * page is framed before and after even when the surrounding layout changes.
 */
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const [, , outDir, baseUrl] = process.argv;
if (!outDir || !baseUrl) {
  console.error("usage: node tests/review-captures.mjs <out-dir> <base-url>");
  process.exit(2);
}

/** path, width, whether to capture the whole page, optional anchor selector. */
const SHOTS = [
  ["home", "/", 1440, false, null, "home, first viewport: is the project and its two flagship findings clear?"],
  ["home-full", "/", 1440, true, null, "home, whole page: total narrative length and section order"],
  ["home-768", "/", 768, false, null, "home at tablet width"],
  ["home-375", "/", 375, false, null, "home at phone width: does the hierarchy survive?"],
  ["studies", "/studies/", 1440, true, null, "studies index: progression or catalogue?"],
  ["studies-375", "/studies/", 375, true, null, "studies index at phone width"],
  ["a4", "/studies/a4/", 1440, false, null, "A4 first viewport: question, the inventory problem, synthetic status"],
  ["a4-375", "/studies/a4/", 375, false, null, "A4 first viewport at phone width"],
  ["a4-hero", "/studies/a4/", 1440, false, "#evidence", "A4 hero figure: is the conclusion visible in one figure?"],
  ["a4-result", "/studies/a4/", 1440, false, "#limits", "A4 major result / limitations section"],
  ["b1", "/studies/b1/", 1440, false, null, "B1 first viewport: question, instrument, silent-error insight, synthetic status"],
  ["b1-375", "/studies/b1/", 375, false, null, "B1 first viewport at phone width"],
  ["b1-visibility", "/studies/b1/", 1440, false, "#visibility", "B1 defect-visibility section: the primary insight"],
  ["b1-diagnostic", "/studies/b1/", 1440, false, "#evidence", "B1 primary diagnostic figure"],
  ["methods", "/methods/", 1440, false, null, "methods, first viewport"],
];

const browser = await chromium.launch();
const page = await browser.newPage();
mkdirSync(outDir, { recursive: true });
const captured = [];

for (const [name, path, width, fullPage, anchor, what] of SHOTS) {
  await page.setViewportSize({ width, height: 900 });
  await page.goto(baseUrl.replace(/\/$/, "") + path, { waitUntil: "networkidle" });
  if (anchor) {
    const target = page.locator(anchor).first();
    if (await target.count()) await target.scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
  }
  const file = `${name}.png`;
  await page.screenshot({ path: join(outDir, file), fullPage });
  captured.push({ file, path, width, fullPage, anchor, what });
  console.log(`  ${file.padEnd(22)} ${path} @ ${width}${fullPage ? " full" : ""}`);
}

writeFileSync(
  join(outDir, "INVENTORY.json"),
  JSON.stringify(
    {
      note: "review captures for human inspection; not pixel baselines, not comparable across operating systems",
      platform: process.platform,
      base_url: baseUrl,
      files: captured,
    },
    null,
    2,
  ) + "\n",
);
await browser.close();
