/**
 * Check 5 -- contrast, verified AS RENDERED rather than as tabulated.
 *
 * docs/design/decisions.md section 8 records measured ratios for token pairs. A token
 * table is a claim about colours; this file reads the colours the browser actually
 * computed for real elements on real pages and re-measures. The two can differ: a token
 * can be correct and still be applied over the wrong ground, or overridden, or not
 * applied at all.
 *
 * The checker is verified before it is trusted, against the same published reference
 * ratios the design document used (21:1, 4.54:1, 4.48:1, 8.59:1, 1:1). A checker that
 * cannot reproduce those has no standing to pass or fail anything.
 *
 * Targets, from WCAG 2.2: 4.5:1 for normal text, 3:1 for large text (>=24px, or >=18.66px
 * bold), 3:1 for non-text marks and control boundaries that carry information.
 */
import { test, expect } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import {
  CAPABILITY,
  contrast,
  contrastSelfCheck,
  EFFECTIVE_BG,
  notApplicable,
  parseColor,
  recordCapability,
  ROUTES,
  tabRingIncludesLinks,
  url,
} from "./support";

interface Sample {
  route: string;
  selector: string;
  text: string;
  fg: string;
  bg: string;
  ratio: number;
  px: number;
  weight: number;
  large: boolean;
  target: number;
}

const samples: Sample[] = [];

/* One file per worker, and none at all from a worker that measured nothing: each worker
   has its own module instance, so a shared file name lets an empty run overwrite a full
   one. */
test.afterAll(async ({}, testInfo) => {
  if (samples.length === 0) return;
  mkdirSync("test-results", { recursive: true });
  writeFileSync(
    `test-results/contrast-${testInfo.project.name}-${process.env.QA_PORT ?? "4321"}-w${testInfo.workerIndex}.json`,
    JSON.stringify(samples, null, 2),
  );
});

test.describe("contrast as rendered", () => {
  test("the checker reproduces the published reference ratios", async () => {
    for (const r of contrastSelfCheck()) {
      expect(Math.abs(r.measured - r.published), `${r.pair}`).toBeLessThan(0.01);
    }
  });

  test("every text node on every route meets its target", async ({ page }) => {
    test.setTimeout(180_000);
    const failures: string[] = [];
    for (const route of ROUTES) {
      await page.goto(url(route));
      await page.evaluate(() =>
        document.querySelectorAll("details").forEach((d) => ((d as HTMLDetailsElement).open = true)),
      );
      const measured = await page.evaluate((bgFn) => {
        const effectiveBg = eval(bgFn) as (el: Element) => string;
        const out: Array<{
          selector: string;
          text: string;
          fg: string;
          bg: string;
          px: number;
          weight: number;
        }> = [];
        const seen = new Set<string>();
        for (const el of Array.from(document.body.querySelectorAll<HTMLElement>("*"))) {
          /* Only elements that paint their own text. */
          const direct = Array.from(el.childNodes).some(
            (n) => n.nodeType === Node.TEXT_NODE && (n.textContent ?? "").trim().length > 0,
          );
          if (!direct) continue;
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) continue;
          const cs = getComputedStyle(el);
          if (cs.visibility === "hidden" || cs.opacity === "0") continue;
          /* Visually hidden long descriptions are not rendered text. */
          if (el.classList.contains("visually-hidden")) continue;
          const key = `${el.tagName}.${el.className}|${cs.color}|${effectiveBg(el)}|${cs.fontSize}|${cs.fontWeight}`;
          if (seen.has(key)) continue;
          seen.add(key);
          out.push({
            selector: `${el.tagName.toLowerCase()}${el.className ? "." + String(el.className).split(" ")[0] : ""}`,
            text: (el.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 40),
            fg: cs.color,
            bg: effectiveBg(el),
            px: parseFloat(cs.fontSize),
            weight: Number(cs.fontWeight) || 400,
          });
        }
        return out;
      }, EFFECTIVE_BG);

      for (const m of measured) {
        const fg = parseColor(m.fg);
        const bg = parseColor(m.bg);
        if (!fg || !bg) continue;
        const ratio = contrast(fg, bg);
        const large = m.px >= 24 || (m.px >= 18.66 && m.weight >= 700);
        const target = large ? 3 : 4.5;
        samples.push({ route, ...m, ratio, large, target });
        if (ratio + 0.005 < target) {
          failures.push(
            `${route} ${m.selector} "${m.text}": ${ratio.toFixed(2)}:1 ` +
              `(${m.fg} on ${m.bg}, ${m.px}px/${m.weight}) needs ${target}:1`,
          );
        }
      }
    }
    expect(failures, "text below its contrast target as rendered").toEqual([]);
    expect(samples.length, "distinct text/ground pairs measured").toBeGreaterThan(40);
  });

  test("the tokens the design document measured are the tokens in the page", async ({ page }) => {
    await page.goto(url("/studies/a4/"));
    const tokens = await page.evaluate(() => {
      const cs = getComputedStyle(document.documentElement);
      const names = [
        "--c-canvas",
        "--c-surface",
        "--c-sunken",
        "--c-ink",
        "--c-ink-2",
        "--c-ink-3",
        "--c-blue",
        "--c-blue-strong",
        "--c-blue-tint",
        "--c-contrast",
        "--c-contrast-mark",
        "--c-contrast-tint",
        "--c-series-context",
        "--c-border-strong",
        "--c-focus",
        "--c-gridline",
        "--c-band-neutral",
        "--c-plot-bg",
      ];
      /* The bundler shortens #ffffff to #fff, so normalise before comparing. */
      const norm = (v: string) => {
        const t = v.trim().toLowerCase();
        const m = t.match(/^#([0-9a-f]{3})$/);
        return m ? "#" + m[1].replace(/./g, (c) => c + c) : t;
      };
      const out: Record<string, string> = {};
      for (const n of names) out[n] = norm(cs.getPropertyValue(n));
      return out;
    });

    /* The values docs/design/decisions.md section 8 says it measured. */
    const DECLARED: Record<string, string> = {
      "--c-canvas": "#fbfaf8",
      "--c-surface": "#ffffff",
      "--c-sunken": "#f2f1ed",
      "--c-ink": "#14181c",
      "--c-ink-2": "#434c55",
      "--c-ink-3": "#5b646d",
      "--c-blue": "#17518f",
      "--c-blue-strong": "#0e3a6b",
      "--c-blue-tint": "#e8eef6",
      "--c-contrast": "#a8400f",
      "--c-contrast-mark": "#c04e13",
      "--c-contrast-tint": "#fbede5",
      "--c-series-context": "#7f868c",
      "--c-border-strong": "#8a8981",
      "--c-focus": "#0b4fa8",
      "--c-gridline": "#e4e6e8",
      "--c-band-neutral": "#efeeea",
    };
    for (const [name, value] of Object.entries(DECLARED)) {
      expect(tokens[name].toLowerCase(), `${name} as served`).toBe(value);
    }
    expect(tokens["--c-plot-bg"].toLowerCase()).toBe("#ffffff");
  });

  test("the ratios the design document tabulates reproduce from the served tokens", async ({
    page,
  }) => {
    await page.goto(url("/"));
    const t = await page.evaluate(() => {
      const cs = getComputedStyle(document.documentElement);
      const get = (n: string) => cs.getPropertyValue(n).trim();
      return {
        canvas: get("--c-canvas"),
        surface: get("--c-surface"),
        sunken: get("--c-sunken"),
        ink: get("--c-ink"),
        ink2: get("--c-ink-2"),
        ink3: get("--c-ink-3"),
        blue: get("--c-blue"),
        blueStrong: get("--c-blue-strong"),
        blueTint: get("--c-blue-tint"),
        contrast: get("--c-contrast"),
        contrastMark: get("--c-contrast-mark"),
        contrastTint: get("--c-contrast-tint"),
        series: get("--c-series-context"),
        border: get("--c-border-strong"),
        focus: get("--c-focus"),
        gridline: get("--c-gridline"),
        band: get("--c-band-neutral"),
      };
    });
    const ratio = (a: string, b: string) => contrast(parseColor(a)!, parseColor(b)!);

    /* Every row of the two tables in decisions.md section 8, re-measured. */
    const TABLE: Array<[string, number, number]> = [
      ["ink on canvas", ratio(t.ink, t.canvas), 17.1],
      ["ink on surface", ratio(t.ink, t.surface), 17.84],
      ["ink on sunken", ratio(t.ink, t.sunken), 15.78],
      ["ink-2 on canvas", ratio(t.ink2, t.canvas), 8.38],
      ["ink-2 on surface", ratio(t.ink2, t.surface), 8.74],
      ["ink-3 on canvas", ratio(t.ink3, t.canvas), 5.77],
      ["ink-3 on surface", ratio(t.ink3, t.surface), 6.02],
      ["ink-3 on sunken", ratio(t.ink3, t.sunken), 5.33],
      ["blue on canvas", ratio(t.blue, t.canvas), 7.71],
      ["blue on surface", ratio(t.blue, t.surface), 8.05],
      ["blue on blue-tint", ratio(t.blue, t.blueTint), 6.89],
      ["blue-strong on canvas", ratio(t.blueStrong, t.canvas), 10.96],
      ["contrast on canvas", ratio(t.contrast, t.canvas), 5.91],
      ["contrast on surface", ratio(t.contrast, t.surface), 6.17],
      ["contrast on contrast-tint", ratio(t.contrast, t.contrastTint), 5.39],
      ["ink-2 on blue-tint", ratio(t.ink2, t.blueTint), 7.49],
      ["ink-2 on contrast-tint", ratio(t.ink2, t.contrastTint), 7.63],
      ["contrast-mark on plot bg", ratio(t.contrastMark, t.surface), 4.84],
      ["series-context on plot bg", ratio(t.series, t.surface), 3.69],
      ["border-strong on plot bg", ratio(t.border, t.surface), 3.51],
      ["border-strong on canvas", ratio(t.border, t.canvas), 3.37],
      ["border-strong on sunken", ratio(t.border, t.sunken), 3.11],
      ["focus on canvas", ratio(t.focus, t.canvas), 7.46],
      ["focus on surface", ratio(t.focus, t.surface), 7.78],
      ["focus on blue-tint", ratio(t.focus, t.blueTint), 6.67],
      ["series-context on canvas", ratio(t.series, t.canvas), 3.54],
      ["contrast-mark on canvas", ratio(t.contrastMark, t.canvas), 4.64],
      ["blue on band-neutral", ratio(t.blue, t.band), 6.93],
      ["contrast-mark on band-neutral", ratio(t.contrastMark, t.band), 4.17],
      ["series-context on band-neutral", ratio(t.series, t.band), 3.18],
      ["contrast-mark on blue-tint", ratio(t.contrastMark, t.blueTint), 4.15],
      ["ink on blue-tint", ratio(t.ink, t.blueTint), 15.28],
      /* The two deliberately below 3:1, checked to be where the document says. */
      ["gridline on plot bg (declared 1.25)", ratio(t.gridline, t.surface), 1.25],
      ["band-neutral on plot bg (declared 1.16)", ratio(t.band, t.surface), 1.16],
    ];

    const drift: string[] = [];
    for (const [name, measured, published] of TABLE) {
      if (Math.abs(measured - published) > 0.02) {
        drift.push(`${name}: measured ${measured.toFixed(2)}, document says ${published}`);
      }
    }
    expect(drift, "rows of decisions.md that do not reproduce").toEqual([]);
  });

  test("the focus ring meets 3:1 against what it sits on", async ({ page }, testInfo) => {
    /* This check walks the tab ring, so it can only run where links are in the tab ring.
       macOS WebKit does not put them there unless the system's full keyboard access is on.
       That is an engine setting and not a property of this site -- and it is measured here
       rather than assumed, on a control page carrying one link and one button, so the skip
       below reports what this engine did in this run and lifts itself the moment the engine
       behaves differently. */
    const cap = await tabRingIncludesLinks(page);
    recordCapability(testInfo, CAPABILITY.tabOrderIncludesLinks, cap);
    test.skip(
      !cap.available,
      notApplicable(
        CAPABILITY.tabOrderIncludesLinks,
        "this engine does not put links in the sequential tab order, so a tab walk would " +
          "measure the engine's setting and not the site.",
      ),
    );
    test.setTimeout(180_000);
    await page.goto(url("/studies/a4/"));
    const failures: string[] = [];
    /* One of each kind of focus stop the page has. The contents rail's own summary is
       deliberately display:none at >= 64rem -- the list is always shown there and there is
       no control to operate -- so the disclosure summaries are the ones to measure. */
    const stops: Array<{ focus: string; measure?: string }> = [
      { focus: "a.site-header__mark" },
      { focus: "main a[href]" },
      { focus: ".explorer__reset" },
      /* The radio itself is clipped to 1px; the ring is drawn on its label by
         `input:focus-visible + label`, so focus one and measure the other. */
      /* Tab enters a radio group at the CHECKED radio, which is the base case. */
      { focus: "#case-2", measure: 'label[for="case-2"]' },
      { focus: ".figure__frame" },
      { focus: ".disclosure > summary" },
      { focus: ".scroll-region" },
    ];
    /* A scroll region inside a closed disclosure is not in the tab ring at all. */
    await page.evaluate(() =>
      document.querySelectorAll("details").forEach((d) => ((d as HTMLDetailsElement).open = true)),
    );
    for (const stop of stops) {
      const sel = stop.focus;
      const el = page.locator(sel).first();
      if (!(await el.count())) continue;
      /* Focus it the way a keyboard reader does. Calling .focus() from script sets
         :focus but NOT :focus-visible, and this stylesheet -- correctly -- draws the ring
         only for :focus-visible, so a scripted focus would measure an outline that is not
         there for a pointer user and is there for a keyboard user. Tab from the top of
         the document until the ring lands on the element under test. */
      /* Start every walk from a fresh document. Blurring is not enough: once a walk has
         run the tab ring off the end of the page, Firefox hands focus to the browser
         chrome and further Tab presses never come back, so the next selector would never
         be reached. Reloading resets the sequential focus navigation starting point. */
      await page.reload();
      await page.evaluate(() =>
        document.querySelectorAll("details").forEach((d) => ((d as HTMLDetailsElement).open = true)),
      );
      await el.evaluate((node) => node.setAttribute("data-qa-focus-target", "1"));
      let landed = false;
      for (let i = 0; i < 1200 && !landed; i += 1) {
        await page.keyboard.press("Tab");
        landed = await page.evaluate(
          () => document.activeElement?.hasAttribute("data-qa-focus-target") ?? false,
        );
      }
      if (!landed) {
        await el.evaluate((node) => node.removeAttribute("data-qa-focus-target"));
        failures.push(`${sel}: never received keyboard focus in 1200 tab presses`);
        continue;
      }
      const target = page.locator(stop.measure ?? stop.focus).first();
      const m = await target.evaluate((node, bgFn) => {
        const effectiveBg = eval(bgFn) as (el: Element) => string;
        const cs = getComputedStyle(node);
        return {
          outline: cs.outlineColor,
          width: parseFloat(cs.outlineWidth),
          style: cs.outlineStyle,
          bg: effectiveBg(node.parentElement ?? node),
        };
      }, EFFECTIVE_BG);
      /* Clear the marker before the next selector, or the tab walk would stop on this
         element again and measure the wrong one. */
      await el.evaluate((node) => node.removeAttribute("data-qa-focus-target"));
      if (m.style === "none" || m.width < 1) {
        failures.push(`${sel}: no outline when focused`);
        continue;
      }
      const r = contrast(parseColor(m.outline)!, parseColor(m.bg)!);
      if (r < 3) failures.push(`${sel}: focus ring ${r.toFixed(2)}:1 against ${m.bg}`);
    }
    expect(failures, "focus indicators below 3:1").toEqual([]);
  });

  /* EXPECTED TO FAIL -- finding F5 in docs/release/UI_QA.md. decisions.md section 8 names
     exactly two colours as deliberately below 3:1 and says both are marked aria-hidden:
     --c-gridline at 1.25:1 and --c-band-neutral at 1.16:1. As rendered, the figures also
     draw separator lines in --c-rule #e1dfda at 1.33:1, which that table does not list at
     all, and the band's legend swatch is painted outside any aria-hidden group. Left
     failing: the rule is the document's own, and the gap is in the drawing, not here. */
  test("information-bearing chart marks meet 3:1 against the plot ground", async ({ page }) => {
    await page.goto(url("/studies/a4/"));
    const result = await page.evaluate(() => {
      const cs = getComputedStyle(document.documentElement);
      const plotBg = cs.getPropertyValue("--c-plot-bg").trim() || "#ffffff";
      const strokes = new Map<string, number>();
      for (const svg of Array.from(document.querySelectorAll(".figure__frame > svg"))) {
        for (const el of Array.from(svg.querySelectorAll<SVGElement>("*"))) {
          if (el.closest("[aria-hidden=true]")) continue; // gridlines and bands
          for (const attr of ["stroke", "fill"]) {
            const v = (el.getAttribute(attr) ?? "").toLowerCase();
            if (/^#[0-9a-f]{6}$/.test(v) && v !== "#ffffff") {
              strokes.set(v, (strokes.get(v) ?? 0) + 1);
            }
          }
        }
      }
      return { plotBg, marks: [...strokes.entries()] };
    });

    const bg = parseColor(result.plotBg)!;
    const weak: string[] = [];
    for (const [colour, count] of result.marks) {
      /* Ignore colours used a handful of times for text; the text check covers those. */
      const r = contrast(parseColor(colour)!, bg);
      if (r < 3) weak.push(`${colour} used ${count}x: ${r.toFixed(2)}:1 on ${result.plotBg}`);
    }
    expect(weak, "chart marks below 3:1 that are not declared decorative").toEqual([]);
    expect(result.marks.length, "distinct mark colours measured").toBeGreaterThan(2);
  });

  /* EXPECTED TO FAIL -- the second half of finding F5. */
  test("the two decorative colours are marked aria-hidden, as the document claims", async ({
    page,
  }) => {
    await page.goto(url("/studies/a4/"));
    const leaked = await page.evaluate(() => {
      const cs = getComputedStyle(document.documentElement);
      const grid = cs.getPropertyValue("--c-gridline").trim().toLowerCase();
      const band = cs.getPropertyValue("--c-band-neutral").trim().toLowerCase();
      const out: string[] = [];
      for (const svg of Array.from(document.querySelectorAll(".figure__frame > svg"))) {
        for (const el of Array.from(svg.querySelectorAll<SVGElement>("*"))) {
          const used = [el.getAttribute("stroke"), el.getAttribute("fill")]
            .filter(Boolean)
            .map((v) => v!.toLowerCase());
          if (!used.includes(grid) && !used.includes(band)) continue;
          if (!el.closest("[aria-hidden=true]")) {
            out.push(`${el.tagName} with ${used.join("/")} is not inside aria-hidden`);
          }
        }
      }
      return out;
    });
    expect(leaked, "decorative colours used outside an aria-hidden group").toEqual([]);
  });
});
