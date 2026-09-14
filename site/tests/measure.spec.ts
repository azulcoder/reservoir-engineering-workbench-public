/**
 * Check 0 -- the instruments, before anything is measured with them.
 *
 * Two of the checks in this suite are only as good as a helper: the 13px chart-text floor
 * depends on knowing how large a glyph is actually painted, and the WebKit keyboard
 * classification depends on knowing what the engine can express at all. This file pins
 * both against control fixtures whose answers are known by construction rather than by
 * measurement, in the same spirit as the contrast checker reproducing published ratios
 * before it is allowed to fail anything.
 *
 * Why this file exists at all
 * ---------------------------
 * The suite previously measured chart text as
 *
 *     computed font-size x (svg.getBoundingClientRect().width / svg.viewBox.baseVal.width)
 *
 * and reported the site's 13px labels as 10.9px on Chromium and WebKit while Firefox
 * passed. Every part of that was the instrument:
 *
 *   - the ratio cannot see a transform on a group inside the drawing, and the control
 *     fixture's scale(0.5) group is reported at 13px by that method in all three engines
 *     when it is painted at 6.5px;
 *   - on a NESTED <svg> -- which F03 contains -- Chromium and WebKit return the union of
 *     the painted children as the client rect (835.77px over a 1000-unit viewBox) while
 *     Firefox returns the layout box (1000px), which is the whole of the engine split;
 *   - getScreenCTM reports a scale of exactly 1 for that same text in all three engines,
 *     which is what the drawing actually does.
 *
 * The 13px target did not move. The instrument did.
 */
import { test, expect } from "@playwright/test";
import {
  CAPABILITY,
  loadFixture,
  paintedTextSizes,
  keyboardScrollIsExpressible,
  recordCapability,
  tabRingIncludesLinks,
} from "./support";

test.describe("the measuring helpers, against control fixtures", () => {
  test("painted text size reproduces every known size in the control fixture", async ({ page }) => {
    await loadFixture(page, "text-scale.html");

    /* What the fixture says it paints, taken from the markup rather than from a
       measurement, so the two sides of the comparison are independent. */
    const declared = await page.evaluate(() =>
      Array.from(document.querySelectorAll("[data-truth]")).map((el) => ({
        text: Array.from(el.childNodes)
          .filter((n) => n.nodeType === Node.TEXT_NODE)
          .map((n) => n.textContent ?? "")
          .join("")
          .replace(/\s+/g, " ")
          .trim()
          .slice(0, 40),
        truth: Number(el.getAttribute("data-truth")),
      })),
    );
    expect(declared.length, "control cases in the fixture").toBeGreaterThanOrEqual(12);

    const measured = await paintedTextSizes(page, "body");
    const byText = new Map(measured.map((m) => [m.text, m]));

    const wrong: string[] = [];
    for (const d of declared) {
      const m = byText.get(d.text);
      if (!m) {
        wrong.push(`"${d.text}": painted at ${d.truth}px but the helper did not report it`);
        continue;
      }
      if (Math.abs(m.px - d.truth) > 0.01) {
        wrong.push(
          `"${d.text}": painted at ${d.truth}px, helper says ${m.px.toFixed(3)}px ` +
            `(font ${m.fontPx}px x scale ${m.scale.toFixed(4)})`,
        );
      }
    }
    expect(wrong, "control cases the helper gets wrong").toEqual([]);
  });

  test("text that is not painted is excluded, not measured", async ({ page }) => {
    await loadFixture(page, "text-scale.html");

    const hiddenTexts = await page.evaluate(() =>
      Array.from(document.querySelectorAll("[data-hidden]")).map((el) =>
        (el.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 40),
      ),
    );
    /* Every one of them is authored below the floor on purpose: if any leaked into the
       measurement it would decide the minimum and fail a page that is fine. */
    expect(hiddenTexts.length, "hidden control cases").toBeGreaterThanOrEqual(6);

    const measured = await paintedTextSizes(page, "body");
    const reported = new Set(measured.map((m) => m.text));
    const leaked = hiddenTexts.filter((t) => t && reported.has(t));
    expect(leaked, "invisible text reported as painted").toEqual([]);

    /* And the minimum over the whole fixture is the smallest PAINTED size, 6.5px, not the
       4px inside the `hidden` attribute. */
    const min = measured.reduce((a, b) => (a.px <= b.px ? a : b));
    expect(min.px, `smallest painted text in the fixture ("${min.text}")`).toBeCloseTo(6.5, 2);
  });

  test("the element-width over viewBox method the suite used to use is wrong here", async ({
    page,
  }) => {
    /* A regression guard with a target, not a curiosity. If someone reinstates the ratio
       method this test says what it costs, in this engine, on a case whose answer is not
       in dispute: a glyph painted at 6.5px inside a scale(0.5) group. The failure is
       engine-independent -- the group transform is invisible to the ratio in all three. */
    await loadFixture(page, "text-scale.html");
    const naive = await page.evaluate(() => {
      const el = document.querySelector("#svg-group-scaled text")!;
      const svg = (el as SVGTextElement).ownerSVGElement!;
      const box = svg.getBoundingClientRect();
      const vb = svg.viewBox.baseVal.width || box.width;
      return parseFloat(getComputedStyle(el).fontSize) * (box.width / vb);
    });
    expect(naive, "the ratio method on a glyph painted at 6.5px").toBeCloseTo(13, 1);

    const measured = await paintedTextSizes(page, "#svg-group-scaled");
    const min = measured.reduce((a, b) => (a.px <= b.px ? a : b));
    expect(min.px, "the helper on the same glyph").toBeCloseTo(6.5, 2);
  });

  test("the keyboard-scroll control fixture is measured, not assumed", async ({
    page,
  }, testInfo) => {
    const cap = await keyboardScrollIsExpressible(page);
    recordCapability(testInfo, CAPABILITY.keyboardScrollOverflow, cap);
    /* No pass/fail on the engine itself. What is asserted is that the fixture is a real
       scroll container in every engine, so a negative result means "this engine will not
       drive it from the keyboard" and never "the fixture was not scrollable". */
    const scrollable = await page.evaluate(() => {
      const r = document.getElementById("region")!;
      return r.scrollWidth > r.clientWidth + 1;
    });
    expect(scrollable, "the control fixture overflows its box").toBe(true);
    expect(cap.evidence).toContain("scrollBy(60) moved it to 60");
  });

  test("the tab-ring control fixture is measured, not assumed", async ({
    page,
  }, testInfo) => {
    const cap = await tabRingIncludesLinks(page);
    recordCapability(testInfo, CAPABILITY.tabOrderIncludesLinks, cap);
    /* Whatever the engine does with links, the walk has to start from a real focus stop,
       or the probe is broken and its negative result would mean nothing. */
    expect(cap.evidence, "the control fixture starts from a focused button").toContain(
      'started on "control-button"',
    );
  });
});
