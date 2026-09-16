/**
 * Check 11 -- the same guards, under the conditions a reader actually imposes.
 *
 * The checks elsewhere in this suite run at a default root font size, with script enabled,
 * at three nominal widths. A reader who has set their browser's text size to 200 percent,
 * or whose script did not run, is not a different site; they are the same site under a
 * condition that has to hold. This file re-runs the guards that can move under those
 * conditions -- the chart-text floor, what stays inside its own drawing, and whether a
 * region that scrolls can still be reached -- across 320, 375, 768 and 1440 CSS pixels, at
 * 200 percent text, and with JavaScript blocked.
 *
 * Text scaling is applied the way a reader's preference applies it, by changing the root
 * font size, not by page zoom. Page zoom scales the device pixel ratio and would leave
 * every CSS measurement in this file unchanged, which is precisely why it would prove
 * nothing about SC 1.4.4.
 */
import { test, expect } from "@playwright/test";
import { ROUTES, url, paintedTextSizes, horizontalOverflow, settle } from "./support";

const WIDTHS = [320, 375, 768, 1440];
const FIGURE_ROUTES = ["/", "/studies/a4/", "/studies/a1/", "/studies/a3/", "/studies/b1/", "/studies/b2/"];
const TWO_HUNDRED_PERCENT = "html { font-size: 200% !important; }";

/** Every text node painted outside the drawing it belongs to, at the current state. */
async function clippedText(page: import("@playwright/test").Page) {
  await settle(page);
  return page.evaluate(() => {
    const out: string[] = [];
    for (const frame of Array.from(
      document.querySelectorAll(".figure__frame, .explorer__frame"),
    )) {
      if (frame.closest("[data-case][hidden]")) continue;
      const root = frame.querySelector("svg");
      if (!root) continue;
      const rb = root.getBoundingClientRect();
      for (const t of Array.from(root.querySelectorAll("text"))) {
        const tb = t.getBoundingClientRect();
        if (tb.width === 0) continue;
        const over = Math.max(tb.right - rb.right, rb.left - tb.left);
        if (over > 1) out.push((t.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 40));
      }
    }
    return out;
  });
}

test.describe("guards at 200 percent text", () => {
  test("chart text holds the 13px floor when the reader doubles their text size", async ({
    page,
  }) => {
    const worst: string[] = [];
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 900 });
      for (const route of FIGURE_ROUTES) {
        await page.goto(url(route));
        await page.addStyleTag({ content: TWO_HUNDRED_PERCENT });
        const painted = await paintedTextSizes(page, ".figure__frame, .explorer__frame");
        expect(painted.length, `labels measured on ${route} at ${width}`).toBeGreaterThan(20);
        const min = painted.reduce((a, b) => (a.px <= b.px ? a : b));
        if (min.px < 13 - 1e-6) {
          worst.push(`${route} @${width}: ${min.px.toFixed(2)}px ("${min.text}")`);
        }
      }
    }
    expect(worst, "chart text below the 13px floor at 200 percent").toEqual([]);
  });

  test("doubling the text size loses no chart content that is not already lost", async ({
    page,
  }) => {
    /* This is the SC 1.4.4 question stated so that it cannot be answered by a defect that
     * belongs to somebody else. Two annotations on /studies/a4/ are drawn past the edge of
     * their own canvas at EVERY text size -- that is finding F7, it is a figure-authoring
     * decision, and runtime.spec.ts holds it. What this check asks is narrower and is the
     * layout question: does doubling the text size clip anything that was not already
     * clipped?
     *
     * It used to. With the labels sized in rem inside a fixed 1000-unit canvas, 182 labels
     * and annotations across the site ran off their drawings at 200 percent against 2 at
     * 100 percent -- content lost purely by honouring the reader's preference. base.css now
     * sizes the canvas in rem and the labels in the canvas's own units, so the drawing
     * scales as one thing.
     */
    const newlyLost: string[] = [];
    for (const route of ROUTES) {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(url(route));
      const before = await clippedText(page);
      await page.addStyleTag({ content: TWO_HUNDRED_PERCENT });
      const after = await clippedText(page);
      const baseline = new Set(before);
      for (const t of after) {
        if (!baseline.has(t)) newlyLost.push(`${route}: "${t}"`);
      }
    }
    expect(newlyLost, "chart text clipped only once the reader scales their text").toEqual([]);
  });

  test("the explorer panel labels follow the reader's text-size preference", async ({ page }) => {
    /* The panels carry font-size="13" as a presentation attribute, which no stylesheet rule
       used to override, so their labels stayed 13px while the prose around them doubled.
       The panel canvas is now sized in rem, so the labels scale with it. */
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(url("/studies/a4/"));
    const at100 = await paintedTextSizes(page, ".explorer__frame");
    await page.addStyleTag({ content: TWO_HUNDRED_PERCENT });
    const at200 = await paintedTextSizes(page, ".explorer__frame");

    expect(at100.length, "panel labels measured").toBeGreaterThan(10);
    const min100 = at100.reduce((a, b) => (a.px <= b.px ? a : b)).px;
    const min200 = at200.reduce((a, b) => (a.px <= b.px ? a : b)).px;
    expect(min100, "smallest panel label at 100 percent").toBeGreaterThanOrEqual(13 - 1e-6);
    expect(
      min200 / min100,
      `panel label scale factor: ${min100.toFixed(2)}px -> ${min200.toFixed(2)}px`,
    ).toBeGreaterThan(1.9);
  });

  test("the page still does not scroll sideways at 200 percent, at every width", async ({
    page,
  }) => {
    /* A 2000px canvas inside a 320px viewport has to scroll inside its own frame. If it
       moved the page instead, the fix above would have traded one 1.4.4 failure for a
       1.4.10 one. */
    const offenders: string[] = [];
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 900 });
      for (const route of FIGURE_ROUTES) {
        await page.goto(url(route));
        await page.addStyleTag({ content: TWO_HUNDRED_PERCENT });
        await page.evaluate(() =>
          document
            .querySelectorAll("details")
            .forEach((d) => ((d as HTMLDetailsElement).open = true)),
        );
        await settle(page);
        const r = await horizontalOverflow(page);
        if (r.scrollWidth > r.clientWidth + 1) {
          offenders.push(
            `${route} @${width}: ${r.scrollWidth} > ${r.clientWidth}; ` +
              r.offenders.slice(0, 4).map((o) => `${o.tag}.${o.cls}`).join(", "),
          );
        }
      }
    }
    expect(offenders, "page-level horizontal scroll at 200 percent text").toEqual([]);
  });
});

test.describe("guards with JavaScript blocked", () => {
  test.use({ javaScriptEnabled: false });

  test("chart text holds the 13px floor without a script, at every width", async ({ page }) => {
    /* The drawings are inlined at build time and the floor is a stylesheet property, so a
       blocked script must not be able to move either. Stated as a check because "must not"
       is a claim and this file's job is to test claims. */
    const worst: string[] = [];
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 900 });
      for (const route of FIGURE_ROUTES) {
        await page.goto(url(route));
        const painted = await paintedTextSizes(page, ".figure__frame, .explorer__frame");
        expect(painted.length, `labels measured on ${route} at ${width}`).toBeGreaterThan(20);
        const min = painted.reduce((a, b) => (a.px <= b.px ? a : b));
        if (min.px < 13 - 1e-6) {
          worst.push(`${route} @${width}: ${min.px.toFixed(2)}px ("${min.text}")`);
        }
      }
    }
    expect(worst, "chart text below the 13px floor with JavaScript blocked").toEqual([]);
  });

  test("a region that scrolls is still reachable and named without a script", async ({ page }) => {
    const problems: string[] = [];
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 900 });
      for (const route of ROUTES) {
        await page.goto(url(route));
        const regions = await page.evaluate(() =>
          Array.from(
            document.querySelectorAll(".scroll-region, .figure__frame, .explorer__frame"),
          )
            .filter((el) => !el.closest("[data-case][hidden]"))
            .map((el) => ({
              name:
                el.getAttribute("aria-label") ??
                el.querySelector("caption")?.textContent?.replace(/\s+/g, " ").trim().slice(0, 40) ??
                el.className,
              scrolls: el.scrollWidth > el.clientWidth + 1,
              tabindex: el.getAttribute("tabindex"),
              named: Boolean(
                el.getAttribute("aria-label") ?? el.getAttribute("aria-labelledby"),
              ),
              role: el.getAttribute("role"),
            })),
        );
        for (const r of regions) {
          if (!r.scrolls) continue;
          if (r.tabindex !== "0") problems.push(`${route} @${width} "${r.name}": no focus stop`);
          if (!r.named) problems.push(`${route} @${width} "${r.name}": not named`);
          if (!r.role) problems.push(`${route} @${width} "${r.name}": no region role`);
        }
      }
    }
    expect(problems, "scrolling regions unreachable with JavaScript blocked").toEqual([]);
  });

  test("no page-level horizontal scroll without a script, at every width", async ({ page }) => {
    const offenders: string[] = [];
    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 900 });
      for (const route of ROUTES) {
        await page.goto(url(route));
        const r = await horizontalOverflow(page);
        if (r.scrollWidth > r.clientWidth + 1) {
          offenders.push(
            `${route} @${width}: ${r.scrollWidth} > ${r.clientWidth}; ` +
              r.offenders.slice(0, 4).map((o) => `${o.tag}.${o.cls}`).join(", "),
          );
        }
      }
    }
    expect(offenders, "page-level horizontal scroll with JavaScript blocked").toEqual([]);
  });
});
