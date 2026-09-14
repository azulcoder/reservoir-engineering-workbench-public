/**
 * Check 6 -- widths, reflow, and text scaling.
 *
 * Three nominal widths (375, 768, 1440), then the two cases WCAG actually names: reflow
 * at 320 CSS pixels (SC 1.4.10, which is 1280 at 400 percent zoom) and text scaled to
 * 200 percent (SC 1.4.4). The site is built in rem, so 200 percent text is applied the
 * way a reader's browser preference applies it -- by changing the root font size -- and
 * not by page zoom, which is a different thing and would not test the same rule.
 *
 * The rule being enforced: the PAGE must not scroll horizontally. A table, a figure or a
 * chart may scroll inside its own labelled region, and `horizontalOverflow` in support.ts
 * excludes anything inside a scroll container for exactly that reason. Nothing here hides
 * overflow to make the check pass.
 *
 * The 13px chart-text check at the bottom of this file used to be recorded as an expected
 * failure (finding F2). It is not one. The floor is met at every width in all three
 * engines; what was failing was the measurement, and the corrected helper it now uses is
 * pinned against a control fixture in measure.spec.ts. The target itself is unchanged.
 */
import { test, expect } from "@playwright/test";
import { ROUTES, url, horizontalOverflow, paintedTextSizes } from "./support";

const WIDTHS = [375, 768, 1440];

test.describe("responsive", () => {
  for (const width of WIDTHS) {
    test(`no page-level horizontal overflow at ${width}`, async ({ page }) => {
      const offenders: string[] = [];
      for (const route of ROUTES) {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(url(route));
        /* Open every disclosure: a collapsed table cannot overflow. */
        await page.evaluate(() =>
          document
            .querySelectorAll("details")
            .forEach((d) => ((d as HTMLDetailsElement).open = true)),
        );
        const r = await horizontalOverflow(page);
        if (r.scrollWidth > r.clientWidth + 1) {
          offenders.push(
            `${route}: document scrolls ${r.scrollWidth} > ${r.clientWidth}; ` +
              r.offenders.slice(0, 4).map((o) => `${o.tag}.${o.cls}@${o.right}`).join(", "),
          );
        }
      }
      expect(offenders, `horizontal overflow at ${width}`).toEqual([]);
    });
  }

  test("reflow at 320 CSS pixels, the SC 1.4.10 case", async ({ page }) => {
    const offenders: string[] = [];
    for (const route of ROUTES) {
      /* 1280 x 1024 at 400 percent zoom is 320 x 256 CSS pixels. */
      await page.setViewportSize({ width: 320, height: 256 });
      await page.goto(url(route));
      await page.evaluate(() =>
        document.querySelectorAll("details").forEach((d) => ((d as HTMLDetailsElement).open = true)),
      );
      const r = await horizontalOverflow(page);
      if (r.scrollWidth > r.clientWidth + 1) {
        offenders.push(
          `${route}: ${r.scrollWidth} > ${r.clientWidth}; ` +
            r.offenders.slice(0, 6).map((o) => `${o.tag}.${o.cls}@${o.right}`).join(", "),
        );
      }
    }
    expect(offenders, "content lost or requiring two-dimensional scroll at 320").toEqual([]);
  });

  test("text at 200 percent, the SC 1.4.4 case", async ({ page }) => {
    const offenders: string[] = [];
    for (const route of ROUTES) {
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.goto(url(route));
      const beforePx = await page
        .locator("main p")
        .first()
        .evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
      await page.addStyleTag({ content: "html { font-size: 200% !important; }" });
      await page.evaluate(() =>
        document.querySelectorAll("details").forEach((d) => ((d as HTMLDetailsElement).open = true)),
      );
      await page.waitForTimeout(100);
      const r = await horizontalOverflow(page);
      if (r.scrollWidth > r.clientWidth + 1) {
        offenders.push(
          `${route}: ${r.scrollWidth} > ${r.clientWidth}; ` +
            r.offenders.slice(0, 6).map((o) => `${o.tag}.${o.cls}@${o.right}`).join(", "),
        );
      }
      /* And the text really did grow, by the factor asked for -- a page that sized its
         type in px would pass the overflow check trivially by ignoring the preference. */
      const afterPx = await page
        .locator("main p")
        .first()
        .evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
      expect(afterPx / beforePx, `text scale factor on ${route}`).toBeGreaterThan(1.9);
    }
    expect(offenders, "horizontal overflow with text at 200 percent").toEqual([]);
  });

  test("the SC 1.4.12 text-spacing overrides do not clip anything", async ({ page }) => {
    const offenders: string[] = [];
    for (const route of ROUTES) {
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.goto(url(route));
      await page.addStyleTag({
        content: `* { line-height: 1.5 !important; letter-spacing: 0.12em !important;
                      word-spacing: 0.16em !important; }
                  p { margin-bottom: 2em !important; }`,
      });
      await page.waitForTimeout(100);
      const r = await horizontalOverflow(page);
      if (r.scrollWidth > r.clientWidth + 1) offenders.push(`${route}: ${r.scrollWidth} > ${r.clientWidth}`);
    }
    expect(offenders, "overflow under the text-spacing overrides").toEqual([]);
  });

  test("nothing hides overflow globally to conceal clipping", async ({ page }) => {
    await page.goto(url("/studies/a4/"));
    const global = await page.evaluate(() => {
      const html = getComputedStyle(document.documentElement);
      const body = getComputedStyle(document.body);
      return { htmlX: html.overflowX, bodyX: body.overflowX };
    });
    expect(["visible", "auto"]).toContain(global.htmlX);
    expect(["visible", "auto"]).toContain(global.bodyX);
  });

  test("wide tables scroll inside a labelled region, not the page", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 900 });
    await page.goto(url("/studies/a4/"));
    await page.evaluate(() =>
      document.querySelectorAll("details").forEach((d) => ((d as HTMLDetailsElement).open = true)),
    );
    const regions = await page.locator(".scroll-region").evaluateAll((els) =>
      els.map((el) => ({
        scrolls: el.scrollWidth > el.clientWidth + 1,
        role: el.getAttribute("role"),
        label: el.getAttribute("aria-label") ?? el.getAttribute("aria-labelledby"),
        tabindex: el.getAttribute("tabindex"),
      })),
    );
    expect(regions.length, "scroll regions on the case page").toBeGreaterThan(0);
    for (const r of regions) {
      if (!r.scrolls) continue;
      expect(r.label, "a scrolling region carries a name").toBeTruthy();
      expect(r.tabindex, "a scrolling region is reachable by keyboard").toBe("0");
    }
  });

  test("chart text renders at or above the 13px floor the design sets", async ({ page }) => {
    /* D24 in docs/design/decisions.md: "Chart labels never render below 13px."
     *
     * The figures are authored at 13px against a 1000px canvas and base.css deliberately
     * takes them out of `img, svg { max-width: 100% }`, so the drawing keeps its authored
     * size and the frame scrolls instead of the text shrinking. The explorer panels do the
     * same with a 460px floor. This check measures what is on screen and confirms it.
     *
     * It is measured with `paintedTextSizes`, which is pinned against a control fixture of
     * known sizes in measure.spec.ts. The previous version of this check divided the SVG's
     * client rect by its viewBox width, which is blind to a group transform and, on the
     * nested <svg> inside F03, reads a different rect in Chromium and WebKit than in
     * Firefox. That -- not the drawing -- was the 10.9px it used to report and the reason
     * only two of the three engines reported it. The floor is unchanged. */
    const FLOOR = 13;
    const WIDTHS = [320, 375, 768, 1440];
    const PAGES = ["/", "/studies/a4/", "/studies/a1/", "/studies/a3/"];
    const worst: Array<{ at: string; px: number; text: string; where: string }> = [];

    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 900 });
      for (const route of PAGES) {
        await page.goto(url(route));
        const painted = await paintedTextSizes(page, ".figure__frame, .explorer__frame");
        expect(painted.length, `chart labels measured on ${route} at ${width}`).toBeGreaterThan(20);
        const min = painted.reduce((a, b) => (a.px <= b.px ? a : b));
        worst.push({ at: `${route} @${width}`, px: min.px, text: min.text, where: min.where });
      }
    }

    const below = worst.filter((w) => w.px < FLOOR - 1e-6);
    expect(
      below.map((w) => `${w.at} ${w.where}: ${w.px.toFixed(2)}px ("${w.text}")`),
      `chart text below the ${FLOOR}px floor`,
    ).toEqual([]);
  });

  test("the explorer controls keep a 44px target at every width", async ({ page }) => {
    for (const width of [375, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(url("/studies/a4/"));
      const boxes = await page.locator(".explorer__option label").evaluateAll((els) =>
        els.map((el) => {
          const r = el.getBoundingClientRect();
          return { w: Math.round(r.width), h: Math.round(r.height) };
        }),
      );
      for (const b of boxes) {
        expect(b.h, `control height at ${width}`).toBeGreaterThanOrEqual(44);
        expect(b.w, `control width at ${width}`).toBeGreaterThanOrEqual(44);
      }
      const reset = await page.locator("[data-explorer-reset]").boundingBox();
      expect(Math.round(reset!.height), `reset height at ${width}`).toBeGreaterThanOrEqual(44);
    }
  });
});
