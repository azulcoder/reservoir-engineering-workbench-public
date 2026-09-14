/**
 * Check 10 -- the rules that have to reach markup the component did not author.
 *
 * Every chart on this site arrives through `set:html`. Astro does not add its scoping
 * attribute to markup inserted that way, so a component-scoped selector whose LAST
 * compound is an SVG element compiles to `svg[data-astro-cid-...]` and matches nothing.
 * The failure is silent: the rule is in the stylesheet, the selector is well formed, and
 * the drawing is simply unstyled. The explorer panel hit exactly this and needed
 * `:global(svg)`; this file is the check that says whether anything else did.
 *
 * Nothing here is inferred from the source. Every assertion reads a COMPUTED value off a
 * real injected element in the browser, which is the only evidence that a selector applied.
 */
import { test, expect } from "@playwright/test";
import { url } from "./support";

test.describe("styles that must reach injected markup", () => {
  test("no component-scoped rule tries to select injected SVG through a scope attribute", async ({
    page,
  }) => {
    await page.goto(url("/studies/a4/"));
    const dead = await page.evaluate(() => {
      const SVG_TAGS = ["svg", "text", "tspan", "g", "path", "circle", "rect", "line", "polyline", "polygon"];
      const out: string[] = [];
      for (const sheet of Array.from(document.styleSheets)) {
        let rules: CSSRuleList;
        try {
          rules = sheet.cssRules;
        } catch {
          continue; // cross-origin; runtime.spec.ts asserts there are none
        }
        const walk = (list: CSSRuleList) => {
          for (const rule of Array.from(list)) {
            if ("cssRules" in rule) walk((rule as CSSGroupingRule).cssRules);
            const selector = (rule as CSSStyleRule).selectorText;
            if (!selector) continue;
            for (const one of selector.split(",")) {
              /* The last compound is what the rule actually selects. If the scoping
                 attribute lands there and the element is part of a drawing, the rule
                 cannot match anything that arrived through set:html. */
              const last = one.trim().split(/[\s>+~]+/).pop() ?? "";
              const tag = last.match(/^[a-z]+/)?.[0] ?? "";
              if (SVG_TAGS.includes(tag) && last.includes("[data-astro-cid-")) {
                out.push(one.trim());
              }
            }
          }
        };
        walk(rules);
      }
      return out;
    });
    expect(dead, "scoped selectors that can never match injected SVG").toEqual([]);
  });

  test("injected SVG carries no scope attribute, which is why :global is needed", async ({
    page,
  }) => {
    await page.goto(url("/studies/a4/"));
    const scoped = await page.evaluate(() =>
      Array.from(document.querySelectorAll(".figure__frame > svg, .explorer__frame > svg"))
        .filter((svg) => Array.from(svg.attributes).some((a) => a.name.startsWith("data-astro-cid")))
        .map((svg) => svg.getAttribute("aria-label") ?? "(unnamed)"),
    );
    expect(scoped, "injected SVG that unexpectedly carries an Astro scope attribute").toEqual([]);
  });

  test("the exhibit rules land on the exhibit, as computed values", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(url("/studies/a4/"));
    const seen = await page.evaluate(() => {
      const root = getComputedStyle(document.documentElement);
      const token = (n: string) => root.getPropertyValue(n).trim();
      /* --text-xs is authored in rem; what matters is what it resolves to here. */
      const probe = document.createElement("span");
      probe.style.fontSize = "var(--text-xs)";
      document.body.appendChild(probe);
      const textXsPx = getComputedStyle(probe).fontSize;
      probe.remove();
      const svgs = Array.from(document.querySelectorAll<SVGSVGElement>(".figure__frame > svg"));
      return {
        count: svgs.length,
        sans: token("--font-sans"),
        textXs: token("--text-xs"),
        textXsPx,
        ink2: token("--c-ink-2"),
        svgs: svgs.map((svg) => {
          const cs = getComputedStyle(svg);
          const label = svg.getAttribute("aria-label")?.slice(0, 24) ?? "(unnamed)";
          const t = svg.querySelector("text");
          const ts = t ? getComputedStyle(t) : null;
          return {
            label,
            maxWidth: cs.maxWidth,
            display: cs.display,
            usedWidth: Math.round(svg.getBoundingClientRect().width),
            viewBoxWidth: svg.viewBox.baseVal.width,
            textFontSize: ts?.fontSize ?? "",
            textFontFamily: ts?.fontFamily ?? "",
            textFill: ts?.fill ?? "",
            numeric: ts?.fontVariantNumeric ?? "",
          };
        }),
      };
    });

    expect(seen.count, "inlined exhibits on the case page").toBeGreaterThanOrEqual(9);
    const seenTextXs = seen.textXsPx;
    const problems: string[] = [];
    for (const s of seen.svgs) {
      /* `img, svg { max-width: 100% }` in the reset would scale the drawing and its text
         together. `.figure__frame svg { max-width: none }` is the rule that stops it, and
         this is the evidence that it reached an element the component never authored. */
      if (s.maxWidth !== "none") problems.push(`${s.label}: max-width computed ${s.maxWidth}`);
      if (s.display !== "block") problems.push(`${s.label}: display computed ${s.display}`);
      /* base.css sizes the canvas as `--exhibit-units * 1rem / 16` with --exhibit-units at
         1000, which is only correct while every exhibit really is authored on a 1000-unit
         canvas. An exhibit drawn to another width would be silently rescaled, so the
         assumption is asserted rather than assumed. */
      if (s.viewBoxWidth !== 1000) {
        problems.push(`${s.label}: viewBox is ${s.viewBoxWidth} units, the rule assumes 1000`);
      }
      /* At the browser's default root size the drawing keeps its authored size exactly:
         one user unit is one CSS pixel. */
      if (Math.abs(s.usedWidth - s.viewBoxWidth) > 1) {
        problems.push(`${s.label}: painted ${s.usedWidth}px over a ${s.viewBoxWidth}-unit viewBox`);
      }
      /* The label constant and the --text-xs token say the same thing from two directions:
         13 user units of a 1000-unit canvas, and the 13px floor D24 states. They are tied
         together here so neither can drift without a failure. */
      if (s.textFontSize !== seenTextXs) {
        problems.push(
          `${s.label}: chart text computed ${s.textFontSize}, --text-xs resolves to ${seenTextXs}`,
        );
      }
      if (s.textFontSize !== "13px") problems.push(`${s.label}: chart text computed ${s.textFontSize}`);
      if (!s.textFontFamily || !seen.sans.includes(s.textFontFamily.split(",")[0].replace(/["']/g, ""))) {
        problems.push(`${s.label}: chart text font-family computed ${s.textFontFamily}`);
      }
      if (!s.textFill || s.textFill === "rgb(0, 0, 0)") {
        problems.push(`${s.label}: chart text fill computed ${s.textFill}, token not applied`);
      }
    }
    expect(problems, "exhibit rules that did not reach the injected drawing").toEqual([]);
  });

  test("the explorer panel rules land on the panel, as computed values", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 900 });
    await page.goto(url("/studies/a4/"));
    const panels = await page.evaluate(() =>
      Array.from(document.querySelectorAll(".explorer__frame"))
        .filter((el) => !el.closest("[data-case][hidden]"))
        .map((frame) => {
          const svg = frame.querySelector("svg")!;
          const cs = getComputedStyle(svg);
          const fcs = getComputedStyle(frame);
          return {
            minWidth: cs.minWidth,
            maxWidth: cs.maxWidth,
            display: cs.display,
            frameOverflowX: fcs.overflowX,
            scrolls: frame.scrollWidth > frame.clientWidth + 1,
            paintedWidth: Math.round(svg.getBoundingClientRect().width),
          };
        }),
    );
    expect(panels.length, "visible explorer panels at 375").toBe(3);
    for (const p of panels) {
      /* These three declarations are the ones that needed :global() to reach the injected
         panel at all. A computed 460px minimum is the proof that they did. */
      expect(p.minWidth, "panel svg min-width").toBe("460px");
      expect(p.maxWidth, "panel svg max-width").toBe("none");
      expect(p.display, "panel svg display").toBe("block");
      expect(p.frameOverflowX, "panel frame overflow-x").toBe("auto");
      expect(p.scrolls, "the panel scrolls inside its own region at 375").toBe(true);
      expect(p.paintedWidth, "panel svg painted width").toBeGreaterThanOrEqual(460);
    }
  });
});
