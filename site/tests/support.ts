/**
 * Shared helpers for the browser QA suite.
 *
 * Nothing here asserts. It builds URLs for whichever base is under test, lists the routes
 * the build actually produces, and does the arithmetic the contrast checks need. Keeping
 * the WCAG maths in one place means the numbers in docs/design/decisions.md are checked by
 * a function that was itself checked against published reference ratios (see
 * `contrastSelfCheck` below, which the contrast spec runs before it trusts anything).
 *
 * The same principle governs the two measuring helpers added at the bottom of this file.
 * `paintedTextSizes` reports the size glyphs are actually painted at, and it is pinned
 * against a control fixture of known sizes in measure.spec.ts before any page is judged
 * by it. `keyboardScrollIsExpressible` and `tabRingIncludesLinks` ask the engine under
 * test whether it can express a behaviour at all, using a control page with nothing on it
 * but that behaviour, so an engine limitation is never recorded as a site defect and a
 * site defect is never excused as an engine limitation.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { Page, Request } from "@playwright/test";

export const BASE = process.env.QA_BASE ?? "/reservoir-engineering-workbench-public/";

/** Every route the build emits. Order is the reading order of the site. */
export const ROUTES = [
  "/",
  "/studies/",
  "/studies/a4/",
  "/studies/a1/",
  "/studies/a3/",
  "/studies/a2/",
  "/methods/",
  "/about/",
] as const;

/** The 404 document, reachable as a file and as the body of any unknown path. */
export const NOT_FOUND_FILE = "/404.html";

/** Site path -> URL under the base being tested. */
export function url(path: string): string {
  if (!path.startsWith("/")) throw new Error(`site path must be absolute: ${path}`);
  return BASE === "/" ? path : BASE.replace(/\/$/, "") + path;
}

/** The eight computed aquifer strengths, as the export names them. */
export const CASES = ["0", "0.05", "0.2", "0.6", "2", "6", "20", "60"] as const;
export const BASE_CASE = "2";

/** Slug used in ids and file names for a case key. */
export function slugFor(key: string): string {
  return key.replace(".", "p");
}

/* ---------------------------------------------------------------------------
 * Console and network capture
 * ------------------------------------------------------------------------ */

export interface PageNoise {
  consoleErrors: string[];
  consoleWarnings: string[];
  pageErrors: string[];
  failed: string[];
  requests: string[];
}

/** Attach listeners before the first navigation and collect everything the page did. */
export function watch(page: Page): PageNoise {
  const noise: PageNoise = {
    consoleErrors: [],
    consoleWarnings: [],
    pageErrors: [],
    failed: [],
    requests: [],
  };
  page.on("console", (m) => {
    if (m.type() === "error") noise.consoleErrors.push(m.text());
    if (m.type() === "warning") noise.consoleWarnings.push(m.text());
  });
  page.on("pageerror", (e) => noise.pageErrors.push(String(e)));
  page.on("requestfailed", (r: Request) =>
    noise.failed.push(`${r.url()} :: ${r.failure()?.errorText ?? "unknown"}`),
  );
  page.on("request", (r: Request) => noise.requests.push(r.url()));
  return noise;
}

/* ---------------------------------------------------------------------------
 * WCAG relative luminance and contrast
 *
 * WCAG 2.x definition: L = 0.2126 R + 0.7152 G + 0.0722 B over linearised channels,
 * and contrast = (L1 + 0.05) / (L2 + 0.05).
 * ------------------------------------------------------------------------ */

export type RGB = [number, number, number];

export function parseColor(value: string): RGB | null {
  const m = value.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/i);
  if (m) return [Number(m[1]), Number(m[2]), Number(m[3])];
  const hex = value.trim().match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    const h = hex[1].length === 3 ? hex[1].replace(/./g, (c) => c + c) : hex[1];
    return [
      parseInt(h.slice(0, 2), 16),
      parseInt(h.slice(2, 4), 16),
      parseInt(h.slice(4, 6), 16),
    ];
  }
  return null;
}

export function luminance([r, g, b]: RGB): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

export function contrast(a: RGB, b: RGB): number {
  const la = luminance(a);
  const lb = luminance(b);
  const [hi, lo] = la >= lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

/**
 * Published reference ratios. A checker that cannot reproduce these is not a checker.
 * Values as cited in docs/design/decisions.md section 8.
 */
export const CONTRAST_REFERENCES: Array<[string, string, number]> = [
  ["#000000", "#ffffff", 21.0],
  ["#767676", "#ffffff", 4.54],
  ["#777777", "#ffffff", 4.48],
  ["#0000ff", "#ffffff", 8.59],
  ["#ffffff", "#ffffff", 1.0],
];

export function contrastSelfCheck(): Array<{ pair: string; measured: number; published: number }> {
  return CONTRAST_REFERENCES.map(([fg, bg, published]) => ({
    pair: `${fg} on ${bg}`,
    measured: contrast(parseColor(fg)!, parseColor(bg)!),
    published,
  }));
}

/**
 * The effective background behind an element: walk up until a non-transparent
 * background-color is found. Enough for this site, which paints flat grounds and uses no
 * background images behind text.
 */
export const EFFECTIVE_BG = `(el) => {
  let node = el;
  while (node) {
    const bg = getComputedStyle(node).backgroundColor;
    const m = bg.match(/rgba?\\(\\s*([\\d.]+)[,\\s]+([\\d.]+)[,\\s]+([\\d.]+)(?:[,\\s]+([\\d.]+))?/i);
    if (m && (m[4] === undefined || Number(m[4]) > 0.99)) return bg;
    node = node.parentElement;
  }
  return 'rgb(255, 255, 255)';
}`;

/** Does the document scroll horizontally at the current viewport? */
export async function horizontalOverflow(page: Page): Promise<{
  scrollWidth: number;
  clientWidth: number;
  offenders: Array<{ tag: string; cls: string; right: number; width: number }>;
}> {
  return page.evaluate(() => {
    const doc = document.documentElement;
    const limit = doc.clientWidth;
    const offenders: Array<{ tag: string; cls: string; right: number; width: number }> = [];
    for (const el of Array.from(document.body.querySelectorAll<HTMLElement>("*"))) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      if (r.right > limit + 1) {
        /* An element allowed to scroll inside its own region is not page overflow. */
        let scroller: HTMLElement | null = el.parentElement;
        let inside = false;
        while (scroller) {
          const ov = getComputedStyle(scroller).overflowX;
          if (ov === "auto" || ov === "scroll") {
            inside = true;
            break;
          }
          scroller = scroller.parentElement;
        }
        if (!inside) {
          offenders.push({
            tag: el.tagName.toLowerCase(),
            cls: typeof el.className === "string" ? el.className : "",
            right: Math.round(r.right),
            width: Math.round(r.width),
          });
        }
      }
    }
    return { scrollWidth: doc.scrollWidth, clientWidth: doc.clientWidth, offenders };
  });
}

/* ---------------------------------------------------------------------------
 * Control fixtures
 *
 * Static pages with one property each, used to ask the engine a question before the
 * site is asked it. They are loaded with setContent rather than served, so they carry
 * nothing of the site: no stylesheet, no script, no base path.
 * ------------------------------------------------------------------------ */

const FIXTURES = join(dirname(fileURLToPath(import.meta.url)), "fixtures");

export function fixture(name: string): string {
  return readFileSync(join(FIXTURES, name), "utf8");
}

/** Load a control fixture and wait for fonts and layout to settle. */
export async function loadFixture(page: Page, name: string): Promise<void> {
  await page.setContent(fixture(name), { waitUntil: "load" });
  await settle(page);
}

/**
 * Fonts loaded, style recalculated, a frame painted.
 *
 * The wait is raced against a short timeout because a page with JavaScript blocked runs
 * neither a font promise nor a requestAnimationFrame callback, and awaiting either there
 * hangs until the test times out -- measured: the first version of this helper took the
 * whole 60s budget on the JavaScript-blocked checks. This site ships no web font, so the
 * font wait is hygiene rather than a dependency, and the synchronous layout read at the
 * end forces style and layout in every engine whether scripts run or not.
 */
export async function settle(page: Page): Promise<void> {
  await page.waitForLoadState("load");
  const painted = page
    .evaluate(async () => {
      await document.fonts.ready;
      await new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r())));
    })
    .catch(() => undefined);
  await Promise.race([painted, page.waitForTimeout(400)]);
  await page.evaluate(() => document.body.getBoundingClientRect().width);
}

/* ---------------------------------------------------------------------------
 * How large is that glyph, really
 *
 * A painted glyph's size in CSS pixels is the computed font-size of the element that
 * carries it, multiplied by the scale of the transform chain between that element's own
 * coordinate space and the viewport. Three things this does NOT do, each of which was
 * measured to be wrong on the control fixture:
 *
 *  - It does not use getBoundingClientRect().height. A bounding box is the box of the
 *    glyphs that happen to be in the string, not the em size: "unscaled thirteen" at 13px
 *    measures 16.00 in Chromium, 18.00 in Firefox and 15.33 in WebKit, and rotating the
 *    same text turns the box on its side (94.55 tall, 16.00 wide).
 *
 *  - It does not divide the SVG element's client rect by its viewBox width. That is the
 *    method this suite used to use, and it is wrong in two separate ways. It cannot see a
 *    transform on a group inside the drawing -- the fixture's `scale(0.5)` group paints at
 *    6.5px and the ratio method reports 13px in all three engines -- and on a NESTED <svg>
 *    Chromium and WebKit return the union of the painted children as the client rect while
 *    Firefox returns the layout box, so the same drawing measures 10.87px in Chromium,
 *    10.86px in WebKit and 13.00px in Firefox. That engine split was an artefact of the
 *    measurement, not of the site.
 *
 *  - It does not multiply by devicePixelRatio. Device pixels are not CSS pixels and the
 *    13px floor is stated in CSS pixels.
 *
 * The scale comes from getScreenCTM(), which accumulates the whole chain: the outer
 * viewBox, every nested viewBox, every group transform, and any CSS transform on an HTML
 * ancestor. Taking hypot(c, d) -- the length of the transformed vertical unit vector --
 * gives the factor the em box is scaled by, and is invariant under rotation, which is
 * what makes rotated axis labels measure at their true size.
 * ------------------------------------------------------------------------ */

export interface PaintedText {
  /** The painted string, trimmed and truncated. */
  text: string;
  /** Computed font-size in CSS pixels, before the transform chain. */
  fontPx: number;
  /** Scale from the element's own coordinate space to CSS pixels. */
  scale: number;
  /** What the glyphs are actually painted at, in CSS pixels. */
  px: number;
  /** Nearest identifiable container, for the failure message. */
  where: string;
}

/**
 * Every painted text node inside `container`, with the size it is painted at.
 *
 * Text that is not genuinely visible is excluded rather than measured: the `hidden`
 * attribute, `display: none`, `visibility: hidden`, zero opacity, `fill: none`, a
 * zero-width box, an empty string, and the 1px clip that the `visually-hidden` utility
 * uses. Those exclusions matter because every one of them is a hidden ALTERNATIVE
 * rendering, and every one of them is smaller than the floor; a minimum taken over the
 * whole DOM would report one of them and call the page broken.
 */
export async function paintedTextSizes(page: Page, container: string): Promise<PaintedText[]> {
  await settle(page);
  return page.evaluate((sel) => {
    /* The visually-hidden utility clips its subtree to a 1px box. The text inside is
       laid out at full size and painted nowhere. */
    const clippedAway = (el: Element): boolean => {
      for (let a = el.parentElement; a; a = a.parentElement) {
        const r = a.getBoundingClientRect();
        if (r.width > 1 && r.height > 1) continue;
        const cs = getComputedStyle(a);
        if (cs.clipPath !== "none" || cs.clip !== "auto" || cs.overflow === "hidden") return true;
      }
      return false;
    };

    /* CSS transforms on the HTML ancestors of a non-SVG text element. For SVG text this
       is already inside getScreenCTM and must not be applied twice. */
    const htmlScale = (el: Element): number => {
      let s = 1;
      for (let a: Element | null = el; a; a = a.parentElement) {
        const t = getComputedStyle(a).transform;
        if (t && t !== "none") {
          const m = new DOMMatrixReadOnly(t);
          s *= Math.hypot(m.c, m.d);
        }
      }
      return s;
    };

    const out: Array<{
      text: string;
      fontPx: number;
      scale: number;
      px: number;
      where: string;
    }> = [];

    for (const root of Array.from(document.querySelectorAll(sel))) {
      for (const el of Array.from(root.querySelectorAll("text, tspan, p, span, div"))) {
        /* Only elements that paint their own characters. */
        const own = Array.from(el.childNodes)
          .filter((n) => n.nodeType === Node.TEXT_NODE)
          .map((n) => n.textContent ?? "")
          .join("")
          .trim();
        if (!own) continue;

        const visible = el.checkVisibility({
          contentVisibilityAuto: true,
          opacityProperty: true,
          visibilityProperty: true,
        });
        if (!visible || clippedAway(el)) continue;

        const box = el.getBoundingClientRect();
        if (box.width <= 0 || box.height <= 0) continue;

        const cs = getComputedStyle(el);
        const fontPx = parseFloat(cs.fontSize);
        if (!Number.isFinite(fontPx) || fontPx <= 0) continue;

        const isSvg = el.namespaceURI === "http://www.w3.org/2000/svg";
        if (isSvg) {
          const fill = cs.fill;
          if (fill === "none" || parseFloat(cs.fillOpacity) === 0) continue;
        }

        let scale: number;
        if (isSvg) {
          const graphic = el as unknown as SVGGraphicsElement;
          const m = typeof graphic.getScreenCTM === "function" ? graphic.getScreenCTM() : null;
          if (!m) continue; // not rendered: inside <defs>, a <clipPath>, or detached
          scale = Math.hypot(m.c, m.d);
        } else {
          scale = htmlScale(el);
        }
        if (!Number.isFinite(scale) || scale <= 0) continue;

        const figure = el.closest("figure");
        out.push({
          text: own.replace(/\s+/g, " ").slice(0, 40),
          fontPx,
          scale,
          px: fontPx * scale,
          where:
            figure?.id ||
            figure?.querySelector("figcaption")?.textContent?.trim().slice(0, 30) ||
            root.getAttribute("aria-label")?.slice(0, 40) ||
            sel,
        });
      }
    }
    return out;
  }, container);
}

/** The smallest painted text inside `container`, or null when there is none. */
export async function smallestPaintedText(
  page: Page,
  container: string,
): Promise<PaintedText | null> {
  const all = await paintedTextSizes(page, container);
  if (all.length === 0) return null;
  return all.reduce((a, b) => (a.px <= b.px ? a : b));
}

/* ---------------------------------------------------------------------------
 * What this engine can and cannot express
 * ------------------------------------------------------------------------ */

export interface EngineCapability {
  /** True when the control fixture demonstrated the behaviour in this engine. */
  available: boolean;
  /** What was measured, for the annotation the test records either way. */
  evidence: string;
}

/**
 * Can a focused scroll container be scrolled with the arrow keys in this engine?
 *
 * The fixture is a 300px box with a 2000px child and a tabindex: no stylesheet, no SVG,
 * nothing the site contributes. If the arrow key does not move it there, it will not move
 * anything on the site either, and a figure frame that fails the same check is failing an
 * engine limitation rather than a conformance requirement. `scrollBy` is exercised in the
 * same fixture so the two outcomes can be told apart: a box that refuses the key but
 * accepts the script is a keyboard limitation, and a box that refuses both is not a scroll
 * container at all.
 */
/**
 * Poll an element's scrollLeft until it moves, or until the budget runs out.
 *
 * Returns the final value either way; the caller decides what zero means. A generous
 * budget costs nothing when the engine scrolls promptly -- the loop exits on the first
 * non-zero reading -- and only the genuinely negative case pays it.
 */
export async function scrollSettled(page: Page, id: string, budgetMs = 2000): Promise<number> {
  return settleScroll(page, () => page.evaluate((el) => document.getElementById(el)!.scrollLeft, id), budgetMs);
}

/**
 * The same wait, for a caller that already holds the element rather than its id.
 *
 * Both the probe and the test that skips on it must measure the behaviour the same way,
 * or they can disagree about the same engine in the same run -- which is exactly what
 * happened: the probe polled, the test slept 400 ms and read once, and WebKit reported
 * the capability present to one and absent to the other.
 */
export async function settleScroll(
  page: Page,
  read: () => Promise<number>,
  budgetMs = 2000,
): Promise<number> {
  const started = Date.now();
  let value = 0;
  while (Date.now() - started < budgetMs) {
    value = await read();
    if (value > 0) return value;
    await page.waitForTimeout(50);
  }
  return value;
}

export async function keyboardScrollIsExpressible(page: Page): Promise<EngineCapability> {
  await loadFixture(page, "keyboard-scroll.html");
  await page.evaluate(() => document.getElementById("region")!.focus());
  const focused = await page.evaluate(() => document.activeElement?.id ?? "");
  /* Two presses, and they have to agree.
     The first version slept a flat 400 ms and read scrollLeft once, which made the answer
     a race: the probe and the test that skips on it reported different answers for the
     same engine in the same run, and the skip-policy gate caught them disagreeing.
     Polling for the scroll fixed that half. The other half is load: under the full
     three-engine suite this fixture occasionally reported a single non-zero reading on
     WebKit while an isolated run of the same fixture, and the site's own figure frames on
     the same engine, reported zero every time. One reading is therefore not evidence.
     Reporting "available" only when two independent presses both move it suppresses the
     one-off without weakening the negative case, which is measured the same way. */
  await page.keyboard.press("ArrowRight");
  const firstPress = await scrollSettled(page, "region");
  await page.evaluate(() => {
    const r = document.getElementById("region")!;
    r.scrollLeft = 0;
    r.focus();
  });
  await page.keyboard.press("ArrowRight");
  const secondPress = await scrollSettled(page, "region");
  const byKey = Math.min(firstPress, secondPress);
  const byScript = await page.evaluate(() => {
    const r = document.getElementById("region")!;
    r.scrollLeft = 0;
    r.scrollBy(60, 0);
    return r.scrollLeft;
  });
  return {
    available: byKey > 0,
    evidence:
      `control fixture: focus landed on "${focused}", two ArrowRight presses moved scrollLeft ` +
      `to ${firstPress} and ${secondPress}, scrollBy(60) moved it to ${byScript}`,
  };
}

/**
 * Does this engine put links in the sequential tab order?
 *
 * macOS WebKit does not unless the system's full keyboard access is on, and Playwright's
 * WebKit inherits that default. The fixture holds one link and one button; if Tab reaches
 * the button and never the link, a tab walk over the site is measuring the setting and not
 * the site.
 */
export async function tabRingIncludesLinks(page: Page): Promise<EngineCapability> {
  await loadFixture(page, "tab-ring.html");
  /* The walk starts from a control that is focused programmatically rather than from the
     top of the document. A freshly loaded page is not necessarily the focused surface in
     every engine -- in WebKit a forward Tab from nothing reached nothing at all, button
     included -- and starting from a known stop separates "this engine will not tab to a
     link" from "no key reached this page". Shift+Tab is the same ring, walked backwards. */
  await page.evaluate(() => document.getElementById("control-button")!.focus());
  const start = await page.evaluate(() => (document.activeElement as HTMLElement | null)?.id ?? "");
  await page.keyboard.press("Shift+Tab");
  const back = await page.evaluate(() => (document.activeElement as HTMLElement | null)?.id ?? "");
  return {
    available: back === "control-link",
    evidence:
      `control fixture: focus started on "${start || "nothing"}", ` +
      `Shift+Tab moved it to "${back || "nothing, or outside the document"}"`,
  };
}

/* ---------------------------------------------------------------------------
 * Declaring a skip so that the gate can check it
 * ------------------------------------------------------------------------ */

/**
 * The capability policy, read from the same file `scripts/check_skip_policy.py` reads.
 *
 * One source of truth, loaded rather than restated. The previous arrangement declared the
 * permitted skips as English sentences inside both workflow files and matched them by
 * exact string, so rewording a message in a test turned a declared skip into an undeclared
 * one in two places at once and neither of them was where anybody was looking.
 */
const POLICY = JSON.parse(
  readFileSync(join(dirname(fileURLToPath(import.meta.url)), "skip-policy.json"), "utf8"),
) as {
  annotation_prefix: string;
  engines: string[];
  capabilities: Array<{ id: string; capability: string; evidence: "probe" | "engine"; engines: string[] }>;
};

/** Stable ids. These are what the gate matches on; the prose around them is diagnostic. */
export const CAPABILITY = {
  printToPdf: "print-to-pdf",
  tabOrderIncludesLinks: "tab-order-includes-links",
  keyboardScrollOverflow: "keyboard-scroll-overflow",
} as const;

export type CapabilityId = (typeof CAPABILITY)[keyof typeof CAPABILITY];

/** Every id the policy declares, so a test cannot invent one that the gate would reject. */
export const DECLARED_CAPABILITIES: string[] = POLICY.capabilities.map((c) => c.id);

/** Which engines the policy permits a capability to be missing on. */
export function permittedEngines(id: CapabilityId): string[] {
  const entry = POLICY.capabilities.find((c) => c.id === id);
  if (!entry) throw new Error(`capability ${id} is not declared in skip-policy.json`);
  return entry.engines;
}

/**
 * The skip reason, in the grammar the gate parses.
 *
 * The id is the load-bearing part and the sentence is for whoever reads the report. A
 * reason that merely begins "NOT APPLICABLE" is rejected by the gate, so this helper is
 * the only supported way to write one.
 */
export function notApplicable(id: CapabilityId, sentence: string): string {
  if (!DECLARED_CAPABILITIES.includes(id)) {
    throw new Error(`capability ${id} is not declared in skip-policy.json`);
  }
  return `NOT APPLICABLE [${id}]: ${sentence}`;
}

/**
 * The measurement a probe-backed skip has to carry, under a type the gate can find.
 *
 * It is pushed whichever way the measurement came out. A test that ran because the
 * capability WAS available still records that it asked, so the report says what was
 * measured on every engine rather than only where something was missing.
 */
export function recordCapability(
  testInfo: { annotations: Array<{ type: string; description?: string }> },
  id: CapabilityId,
  cap: EngineCapability,
): void {
  testInfo.annotations.push({
    type: `${POLICY.annotation_prefix}${id}`,
    description: `${cap.available ? "available" : "unavailable"} -- ${cap.evidence}`,
  });
}
