/**
 * Render every principal figure to static SVG at build time.
 *
 * Why build time. The site must work on GitHub Pages with no application server, no
 * Python, and -- for the principal evidence -- no client JavaScript at all. So the SVG
 * is produced here, by Node, and inlined into the HTML. A reader with scripting blocked
 * still sees the charts, the tables and the downloads.
 *
 * Why Observable Plot. One grammar for every figure, with accessibility affordances
 * (aria-label, aria-description) built into the mark API, and a documented Node path
 * that takes an explicit `document`. linkedom supplies that document. It has no layout
 * engine, so Plot's text measurement falls back to its own estimates; that is fine for a
 * fixed-width figure and is why every label is checked at the rendered size by the
 * browser tests rather than assumed here.
 *
 * This file contains no reservoir equation. Every number it draws comes from
 * ../src/data/figures/*.json, which scripts/export_presentation_data.py produced from the
 * audited case code and reconciled against the audited summary before writing, or -- for
 * the two appendix exhibits -- from the committed case summaries under ../../cases/.
 *
 * Fail closed. A missing file, a missing field, a NaN or an Infinity, a figure that would
 * emit no marks, or a data file whose SHA-256 disagrees with contract.json all raise, and
 * the raised message names the figure. Nothing here ever emits a placeholder.
 */

import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseHTML } from "linkedom";
import * as Plot from "@observablehq/plot";

const HERE = dirname(fileURLToPath(import.meta.url));
export const DATA_DIR = join(HERE, "..", "src", "data", "figures");
export const OUT_DIR = join(HERE, "..", "src", "generated", "figures");
const REPO_ROOT = join(HERE, "..", "..");
const TOKENS_PATH = join(REPO_ROOT, "docs", "design", "tokens.css");

const { document, window } = parseHTML("<!doctype html><html><body></body></html>");
globalThis.document = document;
globalThis.window = window;

/** Read one exported figure-data file. */
export async function loadData(name) {
  return JSON.parse(await readFile(join(DATA_DIR, `${name}.json`), "utf8"));
}

/**
 * Serialise a Plot figure to a standalone, accessible SVG string.
 *
 * `title` becomes the SVG's accessible name and `description` its long description, so
 * the figure carries its own text alternative even when extracted from the page.
 */
export function serialise(node, { title, description }) {
  const svg = node.tagName?.toLowerCase() === "svg" ? node : node.querySelector("svg");
  if (!svg) throw new Error(`figure "${title}" produced no svg element`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", title);
  if (description) {
    const id = `desc-${title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`;
    const desc = document.createElement("desc");
    desc.setAttribute("id", id);
    desc.textContent = description;
    svg.insertBefore(desc, svg.firstChild);
    svg.setAttribute("aria-describedby", id);
  }
  svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");

  /* Plot names every mark group it draws -- aria-label="dot", "line", "rule", "text",
     "x-axis tick label" and so on -- on a bare <g>. An SVG <g> with no role exposes no
     role that permits an accessible name, so axe-core reports each one as
     aria-prohibited-attr at serious impact, and the names themselves say nothing a
     reader could use: "dot" is not a description of anything. The figure's own name and
     long description are on the root, which carries role="img", and under role="img" the
     subtree is presentational in any case. So the mark-level names are stripped here,
     after the root has been labelled, and nothing that carries information is touched:
     the root's aria-label and aria-describedby, and the aria-hidden="true" the renderer
     puts on gridlines and band fills, all survive. */
  for (const el of svg.querySelectorAll("[aria-label]")) {
    if (el === svg) continue;
    if (el.getAttribute("role")) continue;
    el.removeAttribute("aria-label");
  }

  const out = svg.outerHTML ?? String(svg);
  // linkedom uppercases the tag name of a namespaced element on serialisation.
  return out.replace(/^<SVG/, "<svg").replace(/<\/SVG>$/, "</svg>");
}

/** Write one figure and report its byte size, so the payload budget is measured. */
export async function emit(id, svgText) {
  await mkdir(OUT_DIR, { recursive: true });
  const path = join(OUT_DIR, `${id}.svg`);
  await writeFile(path, `${svgText}\n`, "utf8");
  return { id, bytes: Buffer.byteLength(svgText, "utf8"), path };
}

export { Plot, document };

/* =====================================================================
 * 1. Guards. Everything below fails closed.
 * ================================================================== */

/** Assert a finite number. `where` names the figure and the field. */
function fin(value, where) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${where}: expected a finite number, got ${JSON.stringify(value)}`);
  }
  return value;
}

/** Assert a present field. */
function req(object, key, where) {
  if (object == null || !Object.prototype.hasOwnProperty.call(object, key)) {
    throw new Error(`${where}: required field "${key}" is absent`);
  }
  return object[key];
}

/** Assert an array of finite numbers of an expected length. */
function finArray(values, where, expectedLength) {
  if (!Array.isArray(values)) throw new Error(`${where}: expected an array`);
  if (expectedLength != null && values.length !== expectedLength) {
    throw new Error(
      `${where}: expected ${expectedLength} values, got ${values.length}`,
    );
  }
  values.forEach((v, i) => fin(v, `${where}[${i}]`));
  return values;
}

/* =====================================================================
 * 2. Design tokens, read from docs/design/tokens.css rather than retyped.
 * ================================================================== */

/**
 * Parse `--name: value;` declarations and resolve `var(--other)` references, so the
 * figures use the measured token values and not a second copy of them.
 */
function parseTokens(css) {
  const raw = new Map();
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const [, name, value] of stripped.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/gi)) {
    if (!raw.has(name)) raw.set(name, value.trim());
  }
  const resolve = (name, seen = new Set()) => {
    if (!raw.has(name)) throw new Error(`tokens.css: token ${name} is absent`);
    if (seen.has(name)) throw new Error(`tokens.css: token ${name} is cyclic`);
    seen.add(name);
    const value = raw.get(name);
    const ref = value.match(/^var\((--[a-z0-9-]+)\)$/i);
    return ref ? resolve(ref[1], seen) : value;
  };
  return resolve;
}

const token = parseTokens(await readFile(TOKENS_PATH, "utf8"));

const C = {
  canvas: token("--c-canvas"),
  surface: token("--c-surface"),
  sunken: token("--c-sunken"),
  ink: token("--c-ink"),
  ink2: token("--c-ink-2"),
  ink3: token("--c-ink-3"),
  /* --c-rule is deliberately absent. It is 1.33:1 against the plot ground, and every rule
     these figures draw -- the divider above the caveat lines, the separator between table
     rows -- turned out to be structure a reader depends on rather than decoration, so all
     of them use --c-border-strong instead. The token is still a page hairline in the
     stylesheet, where it separates blocks of prose; it is not a chart mark. */
  gridline: token("--c-gridline"),
  border: token("--c-border-strong"),
  truth: token("--c-series-truth"),
  observed: token("--c-series-observed"),
  model: token("--c-series-model"),
  context: token("--c-series-context"),
  band: token("--c-band-neutral"),
  blueTint: token("--c-blue-tint"),
  contrastTint: token("--c-contrast-tint"),
};
const DASH = {
  truth: token("--dash-truth"),
  observed: token("--dash-observed"),
  model: token("--dash-model"),
  neutral: token("--dash-neutral"),
};
const FONT = token("--font-sans");
const MONO = token("--font-mono");
const STROKE = {
  emphasis: Number.parseFloat(token("--stroke-emphasis")),
  default: Number.parseFloat(token("--stroke-default")),
  context: Number.parseFloat(token("--stroke-context")),
};
const MARKER_R = Number.parseFloat(token("--marker-size"));

/** The text floor: --text-xs is 0.8125rem, which is 13px at a 16px root. */
const TEXT_MIN_PX = Math.round(Number.parseFloat(token("--text-xs")) * 16);
if (TEXT_MIN_PX !== 13) {
  throw new Error(`tokens.css: --text-xs resolved to ${TEXT_MIN_PX}px, expected 13px`);
}

const FS = { base: 13, label: 13, title: 17, panel: 14 };

/* =====================================================================
 * 2b. Text metrics.
 *
 * Why this table exists. linkedom has no layout engine, so nothing in this process can
 * ask how wide a string is. Until now the renderer guessed with a single average advance
 * per character, and the guess was wrong in the direction that hurts: it under-counts
 * capitals, digits and the wide punctuation these figures are full of, which is how an
 * annotation came to be drawn 62 CSS px outside its own canvas (finding F7).
 *
 * What the numbers are. Horizontal advance widths in thousandths of an em, measured once
 * in a real browser as the MAXIMUM over every family this project's --font-sans stack
 * resolves to on the measuring machine -- Arial, Helvetica Neue, Helvetica,
 * -apple-system, system-ui and the generic sans-serif. Taking the maximum rather than an
 * average makes each estimate an upper bound over those faces instead of a typical value
 * among them.
 *
 * What the numbers are not. Three members of the stack could not be measured, because
 * they are not installed on the machine that measured: Segoe UI, Roboto and Noto Sans.
 * Segoe UI and Roboto are narrower than Arial across the ASCII range and Noto Sans is
 * drawn to Arial's metrics, so SAFETY below carries a further 4 percent on top. The
 * estimate is therefore deliberately conservative: it may break a line one word early,
 * and it will not let a line run past its frame.
 *
 * Nothing here is trusted on its own. assertTextInside() re-uses these widths to refuse
 * to emit a figure whose text would fall outside its own drawing, and the browser checks
 * measure what three real engines actually paint.
 * ================================================================== */

/* Advance widths in thousandths of an em, weight 400. */
const ADVANCE_REGULAR = {
  " ": 278, "!": 333, '"': 426, "#": 604, $: 604, "%": 1000, "&": 778, "'": 278, "(": 333, ")": 333,
  "*": 500, "+": 604, ",": 278, "-": 429, ".": 278, "/": 333, 0: 606, 1: 556, 2: 566, 3: 592,
  4: 604, 5: 585, 6: 617, 7: 556, 8: 600, 9: 617, ":": 278, ";": 278, "<": 604, "=": 604,
  ">": 604, "?": 556, "@": 1015, A: 722, B: 685, C: 722, D: 722, E: 667, F: 611, G: 778,
  H: 722, I: 333, J: 519, K: 722, L: 611, M: 889, N: 722, O: 778, P: 667, Q: 778,
  R: 722, S: 667, T: 611, U: 722, V: 722, W: 944, X: 722, Y: 722, Z: 617, "[": 333,
  "\\": 333, "]": 333, "^": 604, _: 556, "`": 500, a: 556, b: 593, c: 537, d: 593, e: 556,
  f: 333, g: 574, h: 556, i: 278, j: 278, k: 519, l: 278, m: 853, n: 556, o: 574,
  p: 593, q: 593, r: 333, s: 500, t: 315, u: 556, v: 500, w: 758, x: 518, y: 500,
  z: 500, "{": 480, "|": 260, "}": 480, "~": 604, "°": 400, "±": 604, "²": 333, "³": 333, "µ": 576,
  "×": 604, "÷": 604, "‘": 333, "’": 333, "“": 444, "”": 444, "–": 556, "—": 1000, "…": 1000, "←": 1000,
  "↑": 781, "→": 1000, "↓": 781, "−": 604, "≈": 604, "≤": 604, "≥": 604, "Δ": 722, "α": 611, "β": 611,
  "μ": 611, "ρ": 611, "σ": 617, "Ω": 778,
};

/* The same measurement at weight 600. Bold is not a uniform multiple of regular: the
   narrow letters grow by a third and the capitals hardly move, so the table is kept
   rather than approximated by a factor. */
const ADVANCE_SEMIBOLD = {
  " ": 278, "!": 333, '"': 555, "#": 627, $: 633, "%": 1000, "&": 833, "'": 278, "(": 362, ")": 362,
  "*": 500, "+": 633, ",": 278, "-": 437, ".": 278, "/": 371, 0: 639, 1: 556, 2: 591, 3: 617,
  4: 633, 5: 612, 6: 641, 7: 563, 8: 632, 9: 641, ":": 333, ";": 333, "<": 633, "=": 633,
  ">": 633, "?": 611, "@": 975, A: 722, B: 722, C: 741, D: 741, E: 667, F: 611, G: 778,
  H: 778, I: 389, J: 556, K: 778, L: 667, M: 944, N: 741, O: 778, P: 667, Q: 778,
  R: 722, S: 667, T: 667, U: 741, V: 722, W: 1000, X: 722, Y: 722, Z: 667, "[": 362,
  "\\": 371, "]": 362, "^": 633, _: 560, "`": 500, a: 574, b: 611, c: 574, d: 611, e: 574,
  f: 338, g: 611, h: 611, i: 278, j: 333, k: 574, l: 278, m: 906, n: 611, o: 611,
  p: 611, q: 611, r: 444, s: 556, t: 352, u: 611, v: 556, w: 814, x: 556, y: 556,
  z: 519, "{": 394, "|": 280, "}": 394, "~": 633, "°": 433, "±": 633, "²": 392, "³": 392, "µ": 609,
  "×": 633, "÷": 633, "‘": 333, "’": 333, "“": 500, "”": 500, "–": 560, "—": 1000, "…": 1000, "←": 1000,
  "↑": 804, "→": 1000, "↓": 804, "−": 633, "≈": 633, "≤": 633, "≥": 633, "Δ": 778, "α": 618, "β": 610,
  "μ": 612, "ρ": 619, "σ": 684, "Ω": 802,
};

/** A character outside the table is charged the widest advance in it, never an average. */
const ADVANCE_FALLBACK = 1015;
/**
 * One advance for every monospaced face in --font-mono: Menlo 602, SF Mono 600,
 * Liberation Mono 600, Consolas 550. 620 is above all four.
 */
const MONO_ADVANCE = 620;
/** Headroom for the three stack members that could not be measured here. */
const TEXT_SAFETY = 1.04;

/** Upper bound, in CSS pixels, on the painted width of one line of text. */
function measureText(string, size, { weight = 400, mono = false } = {}) {
  const text = String(string);
  if (mono) return (text.length * MONO_ADVANCE * size * TEXT_SAFETY) / 1000;
  const table = weight >= 600 ? ADVANCE_SEMIBOLD : ADVANCE_REGULAR;
  let mille = 0;
  for (const character of text) mille += table[character] ?? ADVANCE_FALLBACK;
  return (mille * size * TEXT_SAFETY) / 1000;
}

/* =====================================================================
 * 3. SVG plumbing.
 * ================================================================== */

const NS = "http://www.w3.org/2000/svg";
const W = 1000;
const PADX = 28;

function svgEl(name, attrs = {}, textContent) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) if (v != null) node.setAttribute(k, String(v));
  if (textContent != null) node.textContent = textContent;
  return node;
}

function textNode(x, y, string, { size = FS.base, fill = C.ink2, weight = 400, anchor = "start", family = FONT } = {}) {
  return svgEl(
    "text",
    {
      x,
      y,
      "font-size": `${size}px`,
      "font-family": family,
      "font-weight": weight,
      fill,
      "text-anchor": anchor,
      "font-variant-numeric": "tabular-nums",
    },
    string,
  );
}

/**
 * Greedy wrap to a MEASURED width, using the advance table above rather than a single
 * average advance per character. A single token wider than the line (a file path, a
 * hash) is broken by character rather than allowed to run past the frame.
 *
 * `style` carries the weight and the monospace flag through to the measurement, so a
 * semibold title and a monospaced table cell are each wrapped against their own metrics
 * instead of the body face's.
 */
function wrap(string, maxWidth, size, style = {}) {
  const width = (s) => measureText(s, size, style);
  const words = [];
  for (const word of String(string).split(/\s+/)) {
    if (!word.length) continue;
    if (width(word) <= maxWidth) {
      words.push(word);
      continue;
    }
    let piece = "";
    for (const character of word) {
      if (piece.length && width(piece + character) > maxWidth) {
        words.push(piece);
        piece = character;
      } else piece += character;
    }
    if (piece.length) words.push(piece);
  }
  const lines = [];
  let line = "";
  for (const word of words) {
    if (!line.length) line = word;
    else if (width(`${line} ${word}`) <= maxWidth) line += ` ${word}`;
    else {
      lines.push(line);
      line = word;
    }
  }
  if (line.length) lines.push(line);
  return lines.length ? lines : [""];
}

/**
 * Strip Plot's scoped stylesheet and class hook from a nested plot, so that a figure
 * composed of two panels carries no page-level CSS of its own and rasterises the same
 * way it renders.
 */
function tidyPlot(node, where) {
  if (!node || node.tagName?.toLowerCase() !== "svg") {
    throw new Error(`${where}: Plot did not return an svg element`);
  }
  // Plot's own stylesheet is class-scoped and carries the style option, including the
  // font size. Removing it keeps the composed figure free of page-level CSS, so the type
  // is restated here as presentation attributes -- otherwise every axis tick label falls
  // back to Plot's 10px root attribute, below the 13px floor the tokens set.
  for (const style of [...node.querySelectorAll("style")]) style.remove();
  node.removeAttribute("class");
  node.setAttribute("style", "white-space:pre");
  node.setAttribute("font-size", String(FS.base));
  node.setAttribute("font-family", FONT);
  const height = Number.parseFloat(node.getAttribute("height"));
  fin(height, `${where}: plot height`);
  return node;
}

/** One legend entry drawn by hand; Plot's own legend is HTML, which an inline SVG cannot use. */
function legendRow(items, x, y, width) {
  const group = svgEl("g", {});
  let cx = x;
  let cy = y;
  const SAMPLE = 34;
  for (const item of items) {
    const labelWidth = measureText(item.label, FS.base);
    const entryWidth = SAMPLE + 8 + labelWidth + 22;
    if (cx + entryWidth > x + width && cx > x) {
      cx = x;
      cy += 22;
    }
    if (item.dash !== "hidden") {
      group.appendChild(
        svgEl("line", {
          x1: cx,
          y1: cy - 4,
          x2: cx + SAMPLE,
          y2: cy - 4,
          stroke: item.color,
          "stroke-width": item.width ?? STROKE.default,
          "stroke-dasharray": item.dash === "none" || item.dash == null ? null : item.dash,
        }),
      );
    }
    const mx = cx + SAMPLE / 2;
    const my = cy - 4;
    if (item.symbol === "circle") {
      group.appendChild(svgEl("circle", { cx: mx, cy: my, r: 4, fill: item.color }));
    } else if (item.symbol === "square") {
      group.appendChild(svgEl("rect", { x: mx - 4, y: my - 4, width: 8, height: 8, fill: item.color }));
    } else if (item.symbol === "diamond") {
      group.appendChild(
        svgEl("polygon", { points: `${mx},${my - 5} ${mx + 5},${my} ${mx},${my + 5} ${mx - 5},${my}`, fill: item.color }),
      );
    } else if (item.symbol === "open-square") {
      group.appendChild(
        svgEl("rect", { x: mx - 4, y: my - 4, width: 8, height: 8, fill: "none", stroke: item.color, "stroke-width": 1.5 }),
      );
    } else if (item.symbol === "times") {
      group.appendChild(
        svgEl("path", {
          d: `M${mx - 4},${my - 4}L${mx + 4},${my + 4}M${mx - 4},${my + 4}L${mx + 4},${my - 4}`,
          stroke: item.color,
          "stroke-width": 1.8,
        }),
      );
    } else if (item.symbol === "band") {
      /* The band fill is --c-band-neutral at 1.16:1 against the plot ground. In the plot
         it is decorative -- every band it fills has its own boundary rules in
         --c-border-strong at 3.51:1 and its own text label, and the figure reads with the
         fill removed -- so the fill is aria-hidden there and is aria-hidden here too.
         But a legend swatch at 1.16:1 shows the reader nothing at all: it is a blank gap
         beside a label. So the swatch carries a boundary in --c-border-strong. The
         boundary is what makes the swatch visible and it meets 3:1; the fill inside it
         stays what it is in the plot, decorative and hidden. */
      const swatch = svgEl("g", { "aria-hidden": "true" });
      swatch.appendChild(svgEl("rect", { x: cx, y: my - 7, width: SAMPLE, height: 14, fill: item.color }));
      swatch.appendChild(
        svgEl("rect", {
          x: cx + 0.5,
          y: my - 6.5,
          width: SAMPLE - 1,
          height: 13,
          fill: "none",
          stroke: C.border,
          "stroke-width": 1,
        }),
      );
      group.appendChild(swatch);
    }
    group.appendChild(textNode(cx + SAMPLE + 8, cy, item.label, { size: FS.base, fill: C.ink2 }));
    cx += entryWidth;
  }
  return { group, height: cy - y + 22 };
}

/**
 * The drawing area of each flattened panel, in the coordinates of the figure that
 * contains it, so assertTextInside() can judge a label against the panel it belongs to
 * and not only against the outer canvas.
 */
const VIEWPORT = new WeakMap();

/** Attributes that describe a viewport rather than how its contents are painted. */
const VIEWPORT_ATTRS = new Set(["x", "y", "width", "height", "viewBox", "xmlns", "class", "preserveAspectRatio"]);

/**
 * Turn a nested <svg> panel into a <g transform="translate(...)">.
 *
 * Two reasons, one of them a real defect.
 *
 * 1. Composition. A panel drawn by Plot arrives as a standalone <svg> at 0,0; placing it
 *    with x and y made it a nested viewport, which is a second coordinate system inside
 *    the figure for no benefit -- the scale is 1 either way, and the assertion below
 *    refuses to flatten anything whose viewBox says otherwise.
 *
 * 2. Measurement. getBoundingClientRect() on a NESTED <svg> does not agree between
 *    engines: Chromium and WebKit return the union of the rendered content, Firefox
 *    returns the viewport rectangle. Any browser check that divides that box by the
 *    element's viewBox to recover a scale factor therefore gets a number that is not a
 *    scale factor at all on two engines out of three -- it reported this project's 13px
 *    labels as 10.9px there while Firefox, measuring the same drawing, reported 13px.
 *    A <g> has no viewport of its own, so ownerSVGElement resolves to the figure's root
 *    <svg>, whose box and viewBox are the same thing in every engine. The drawing does
 *    not change; the ambiguity does.
 *
 * Flattening also drops the clipping a nested viewport gave for free, which is why
 * assertTextInside() records each panel's box here and enforces the same boundary
 * explicitly, at build time, where a violation names the figure instead of silently
 * cutting a caveat in half.
 */
function flattenViewport(node, dx, dy, where) {
  if (node.tagName?.toLowerCase() !== "svg") {
    throw new Error(`${where}: expected an svg panel to place, got <${node.tagName}>`);
  }
  const x = Number.parseFloat(node.getAttribute("x") ?? "0") || 0;
  const y = Number.parseFloat(node.getAttribute("y") ?? "0") || 0;
  const width = fin(Number.parseFloat(node.getAttribute("width")), `${where}: panel width`);
  const height = fin(Number.parseFloat(node.getAttribute("height")), `${where}: panel height`);
  const viewBox = node.getAttribute("viewBox");
  if (viewBox) {
    const [vx, vy, vw, vh] = viewBox.trim().split(/[\s,]+/).map(Number);
    if (vx !== 0 || vy !== 0 || Math.abs(vw - width) > 1e-6 || Math.abs(vh - height) > 1e-6) {
      throw new Error(
        `${where}: viewBox "${viewBox}" is not the panel's own ${width} by ${height} box; ` +
          "flattening it would rescale every mark it contains",
      );
    }
  }
  const tx = dx + x;
  const ty = dy + y;
  const group = svgEl("g", { transform: tx || ty ? `translate(${tx},${ty})` : null });
  for (const attribute of Array.from(node.attributes)) {
    if (VIEWPORT_ATTRS.has(attribute.name)) continue;
    group.setAttribute(attribute.name, attribute.value);
  }
  VIEWPORT.set(group, { width, height });
  while (node.firstChild) group.appendChild(node.firstChild);
  for (const child of Array.from(group.children)) {
    if (child.tagName?.toLowerCase() === "svg") {
      group.replaceChild(flattenViewport(child, 0, 0, `${where} > inner panel`), child);
    }
  }
  return group;
}

/**
 * Compose a finished figure: heading, sub-heading, hand-drawn legend, one or more Plot
 * panels or hand-built tables, then the caveat and provenance lines. Everything a reader
 * needs to interpret the figure travels inside the SVG.
 */
function frame({ title, subtitle, legend, sections, notes = [], width = W }) {
  const svg = svgEl("svg", { width, style: `color:${C.ink}` });
  const background = svgEl("rect", { x: 0, y: 0, width, fill: C.surface });
  svg.appendChild(background);
  const inner = width - 2 * PADX;
  let y = 30;

  for (const line of wrap(title, inner, FS.title, { weight: 600 })) {
    svg.appendChild(textNode(PADX, y, line, { size: FS.title, fill: C.ink, weight: 600 }));
    y += 23;
  }
  if (subtitle) {
    y += 3;
    for (const line of wrap(subtitle, inner, FS.base)) {
      svg.appendChild(textNode(PADX, y, line, { size: FS.base, fill: C.ink3 }));
      y += 18;
    }
  }
  if (legend?.length) {
    y += 20;
    const { group, height } = legendRow(legend, PADX, y, inner);
    svg.appendChild(group);
    y += height - 12;
  }
  y += 10;

  for (const section of sections) {
    const sectionHeight = fin(
      Number.parseFloat(section.getAttribute("height")),
      `${title}: section height`,
    );
    svg.appendChild(flattenViewport(section, 0, y, `${title}: section`));
    y += sectionHeight + 6;
  }

  y += 12;
  /* The divider between the drawing and the lines that qualify it. It is not decoration:
     it is the boundary a reader uses to tell the figure's evidence from the caveat,
     provenance and standard-conditions text that governs how that evidence may be read,
     and below it sits 13px prose on the same ground with no other boundary. Removing it
     leaves the first caveat line looking like one more axis annotation. So it is drawn in
     --c-border-strong at 3.51:1, not in --c-rule at 1.33:1. See docs/design/figure_spec.md
     section "Non-text contrast: what each mark does". */
  svg.appendChild(svgEl("line", { x1: PADX, y1: y - 12, x2: width - PADX, y2: y - 12, stroke: C.border }));
  for (const note of notes) {
    for (const line of wrap(note, inner, FS.base)) {
      svg.appendChild(textNode(PADX, y, line, { size: FS.base, fill: C.ink3 }));
      y += 18;
    }
    y += 6;
  }
  const height = Math.round(y + 8);
  background.setAttribute("height", height);
  svg.setAttribute("height", height);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  return svg;
}

/**
 * A hand-built table: rules and text, no chart grammar. Cells wrap inside their column,
 * so a long sentence in the last column cannot run past the frame. Returns an svg node.
 */
function tableSection({ columns, rows, width = W, note }) {
  const headerHeight = 30;
  const lineHeight = 18;
  const total = columns.reduce((a, c) => a + c.width, 0);
  const scale = (width - 2 * PADX) / total;
  let x = PADX;
  const geometry = columns.map((c) => {
    const at = x;
    const columnWidth = c.width * scale;
    x += columnWidth;
    return { at, width: columnWidth };
  });

  const wrapped = rows.map((row) =>
    columns.map((column, i) => {
      const value = row[i] == null ? "" : String(row[i]);
      return wrap(value, geometry[i].width - 14, FS.base, {
        mono: column.mono === true,
        weight: column.emphasis ? 600 : 400,
      });
    }),
  );
  const heights = wrapped.map((cells) => Math.max(...cells.map((c) => c.length)) * lineHeight + 10);
  const noteLines = note ? wrap(note, width - 2 * PADX, FS.base) : [];
  const height =
    headerHeight + heights.reduce((a, b) => a + b, 0) + noteLines.length * lineHeight + (note ? 14 : 0) + 8;
  const svg = svgEl("svg", { width, height });

  columns.forEach((column, i) => {
    svg.appendChild(textNode(geometry[i].at, 20, column.label, { size: FS.base, fill: C.ink, weight: 600 }));
  });
  svg.appendChild(
    svgEl("line", { x1: PADX, y1: headerHeight - 4, x2: width - PADX, y2: headerHeight - 4, stroke: C.border }),
  );

  let top = headerHeight;
  wrapped.forEach((cells, r) => {
    /* The row separator carries information: cells wrap independently, so a three-line
       sentence in the last column sits beside a one-line value in the first, and the rule
       is what says which value belongs to which row. Remove it and a reader cannot tell
       where one row ends. It is therefore drawn in --c-border-strong at 3.51:1 rather
       than --c-rule at 1.33:1, the same colour as the header rule above it. */
    if (r > 0) svg.appendChild(svgEl("line", { x1: PADX, y1: top, x2: width - PADX, y2: top, stroke: C.border }));
    cells.forEach((lines, i) => {
      lines.forEach((line, li) => {
        svg.appendChild(
          textNode(geometry[i].at, top + 18 + li * lineHeight, line, {
            size: FS.base,
            fill: columns[i].emphasis ? C.ink : C.ink2,
            weight: columns[i].emphasis ? 600 : 400,
            family: columns[i].mono ? MONO : FONT,
          }),
        );
      });
    });
    top += heights[r];
  });
  noteLines.forEach((line, i) => {
    svg.appendChild(textNode(PADX, top + 20 + i * lineHeight, line, { size: FS.base, fill: C.ink3 }));
  });
  return svg;
}

/* =====================================================================
 * 4. Plot helpers.
 * ================================================================== */

const PLOT_STYLE = { fontFamily: FONT, fontSize: `${FS.base}px`, color: C.ink2, background: "none" };

function panel(options, where) {
  const node = Plot.plot({ style: PLOT_STYLE, ...options });
  return tidyPlot(node, where);
}

/**
 * Draw a multi-line annotation inside a finished panel, at a position taken from the
 * panel's own scales and wrapped to a width this renderer has MEASURED.
 *
 * Why not Plot.text with `lineWidth`. Plot's `lineWidth` is a budget in ems against its
 * own internal width estimate, and it is expressed independently of where the text sits,
 * so a label anchored two thirds of the way across a panel can satisfy its lineWidth and
 * still run off the canvas -- which is exactly what F05's calibration note did, by 62 CSS
 * pixels on every engine. Here the budget is computed from the anchor to the edge of the
 * plot area, in pixels, so the block cannot overhang by construction.
 *
 * `at` is in data units and is converted through the panel's x and y scales, so the
 * annotation stays attached to the feature it describes if a domain ever changes.
 */
function plotAnnotation(node, { scaleX, scaleY, at, text, fill, size = FS.label, weight = 400, anchor = "start", dx = 0, dy = 0, lineHeight = 17, where }) {
  const x = fin(scaleX.apply(at.x), `${where}: annotation x`) + dx;
  const y = fin(scaleY.apply(at.y), `${where}: annotation y`) + dy;
  const [left, right] = [Math.min(...scaleX.range), Math.max(...scaleX.range)];
  const room = anchor === "end" ? x - left : anchor === "middle" ? 2 * Math.min(x - left, right - x) : right - x;
  if (!(room > size * 4)) {
    throw new Error(
      `${where}: annotation "${String(text).slice(0, 40)}" has ${room.toFixed(1)} px of room ` +
        `at x = ${x.toFixed(1)} in a plot area of ${left.toFixed(1)}..${right.toFixed(1)}; ` +
        "move the anchor or widen the panel rather than letting it overhang",
    );
  }
  const lines = wrap(text, room, size, { weight });
  const group = svgEl("g", {});
  lines.forEach((line, i) => {
    group.appendChild(textNode(x, y + i * lineHeight, line, { size, fill, weight, anchor }));
  });
  node.appendChild(group);
  return { lines: lines.length, height: (lines.length - 1) * lineHeight };
}

const grid = (axis, options = {}) =>
  (axis === "x" ? Plot.gridX : Plot.gridY)({ stroke: C.gridline, strokeOpacity: 1, ariaHidden: true, ...options });

/**
 * Plot ignores a tickFormat function on a log scale (marks/axis.js, inferTickFormat) and
 * falls back to d3's log formatter, which silently blanks the label of any tick whose
 * mantissa it dislikes -- 80 psi, for instance. Supplying the text channel on an explicit
 * axis mark bypasses that path, so log axes are drawn with these and `axis: null` on the
 * scale.
 */
const logAxis = (axis, values, { label, labelOffset, format = String }) =>
  (axis === "x" ? Plot.axisX : Plot.axisY)(values, {
    text: (d) => format(d),
    label,
    labelAnchor: "center",
    labelOffset,
    fontSize: FS.base,
    stroke: C.border,
  });

/** Number formatting that never hides a sign. */
const pct = (v, digits = 2) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(digits)}%`;
const sig = (v, digits = 3) => (v === 0 ? "0" : v.toExponential(digits));
/** Percentages that are zero only to machine precision are said to be, not printed as -0.00%. */
const pctOrZero = (v, digits = 2) => (Math.abs(v) < 1e-9 ? "0 at machine precision" : pct(v, digits));
/** Decade ticks on a log axis, written as a reader would write them. */
const expTick = (d) => (d === 0 ? "0" : d.toExponential(0));

/* =====================================================================
 * 5. The figures.
 * ================================================================== */

const STANDARD_CONDITIONS =
  "Standard conditions: SPE / one standard atmosphere, 14.6959 psia, 60 degF, Z_sc = 1. Pressure is absolute (psia).";
const EVIDENCE_SHORT =
  "Synthetic. Generator and estimator are separate modules. Known inventory is evaluation-only information that no field measurement provides.";

/** The truth value, derived from exported fields, and cross-checked over all eight scenarios. */
function deriveTrueGasInPlace(scenarios, where) {
  const derived = scenarios.map((s) => {
    const fit = req(s, "fit", where);
    const g = fin(req(fit, "gas_in_place_scf", where), `${where}: fit.gas_in_place_scf`);
    const e = fin(req(s, "relative_gas_in_place_error", where), `${where}: relative_gas_in_place_error`);
    return g / (1 + e);
  });
  const first = derived[0];
  for (const value of derived) {
    if (Math.abs(value - first) / first > 1e-9) {
      throw new Error(
        `${where}: derived true gas in place disagrees across scenarios (${value} vs ${first})`,
      );
    }
  }
  return fin(first, `${where}: derived true gas in place`);
}

function baseScenario(data, where) {
  const scenarios = req(data, "scenarios", where);
  if (!Array.isArray(scenarios) || scenarios.length !== 8) {
    throw new Error(`${where}: expected 8 scenarios, got ${scenarios?.length}`);
  }
  const base = scenarios.find((s) => s.is_base_case === true);
  if (!base) throw new Error(`${where}: no scenario is flagged is_base_case`);
  return { scenarios, base };
}

/** Shared validation for one 49-point scenario record. */
function scenarioSeries(scenario, where) {
  const n = fin(req(scenario, "n_observations", where), `${where}: n_observations`);
  if (n !== 49) throw new Error(`${where}: expected 49 observations, got ${n}`);
  const x = finArray(req(scenario, "cumulative_gas_bscf", where), `${where}: cumulative_gas_bscf`, 49);
  const y = finArray(req(scenario, "p_over_z_psia", where), `${where}: p_over_z_psia`, 49);
  const fitted = finArray(req(scenario, "fitted_p_over_z_psia", where), `${where}: fitted_p_over_z_psia`, 49);
  const residual = finArray(req(scenario, "residual_p_over_z_psia", where), `${where}: residual_p_over_z_psia`, 49);
  const times = finArray(req(scenario, "times_years", where), `${where}: times_years`, 49);
  return { x, y, fitted, residual, times, n };
}

/* ---------- F01 ---------- */

function buildF01(data, { observedRangeOnly = false } = {}) {
  const where = observedRangeOnly ? "F01-observed" : "F01";
  const { scenarios, base } = baseScenario(data, where);
  const { x, y, fitted } = scenarioSeries(base, where);
  const fit = req(base, "fit", where);
  const intercept = fin(req(fit, "intercept_psia", where), `${where}: fit.intercept_psia`);
  const slope = fin(req(fit, "slope_psia_per_scf", where), `${where}: fit.slope_psia_per_scf`);
  const gBscf = fin(req(fit, "gas_in_place_bscf", where), `${where}: fit.gas_in_place_bscf`);
  const rSquared = fin(req(fit, "r_squared", where), `${where}: fit.r_squared`);
  const extent = fin(req(base, "observed_extent_bscf", where), `${where}: observed_extent_bscf`);
  const trueBscf = deriveTrueGasInPlace(scenarios, where) / 1e9;
  const relError = fin(req(base, "relative_gas_in_place_error", where), `${where}: relative_gas_in_place_error`);

  // The extrapolation is computed from the exported coefficients, not by extending a path.
  const atG = intercept + slope * gBscf * 1e9;
  if (Math.abs(atG) > 1e-6) {
    throw new Error(`${where}: fitted line does not reach zero at its own x-intercept (${atG} psia)`);
  }
  const extrapolation = [];
  const steps = 40;
  for (let i = 0; i <= steps; i += 1) {
    const bscf = extent + ((gBscf - extent) * i) / steps;
    extrapolation.push({ x: bscf, y: fin(intercept + slope * bscf * 1e9, `${where}: extrapolation`) });
  }

  const observedPoints = x.map((v, i) => ({ x: v, y: y[i] }));
  const fittedPoints = x.map((v, i) => ({ x: v, y: fitted[i] }));
  const context = scenarios
    .filter((s) => s !== base)
    .flatMap((s, k) => {
      const series = scenarioSeries(s, `${where}: context scenario ${s.label}`);
      return series.x.map((v, i) => ({ x: v, y: series.y[i], k }));
    });

  const xDomain = observedRangeOnly ? [-1.5, extent + 2] : [-2, 120];
  const yDomain = observedRangeOnly
    ? [Math.min(...y, ...fitted) - 40, Math.max(...y, ...fitted) + 60]
    : [0, 4650];

  const marks = [
    grid("y"),
    grid("x"),
    Plot.line(context, {
      x: "x",
      y: "y",
      z: "k",
      stroke: C.context,
      strokeWidth: STROKE.context,
      strokeDasharray: DASH.neutral,
    }),
    Plot.line(observedPoints, { x: "x", y: "y", stroke: C.observed, strokeWidth: STROKE.default }),
    Plot.dot(observedPoints, { x: "x", y: "y", r: 3.4, fill: C.observed, symbol: "circle" }),
    // The fit is drawn over the observations, not under them: the two nearly coincide,
    // and the reader has to be able to see that they do.
    Plot.line(fittedPoints, {
      x: "x",
      y: "y",
      stroke: C.model,
      strokeWidth: STROKE.emphasis,
      strokeDasharray: DASH.model,
    }),
    Plot.ruleX([extent], { stroke: C.border, strokeDasharray: "4 4", strokeWidth: 1 }),
  ];

  if (!observedRangeOnly) {
    marks.push(
      Plot.line(extrapolation, {
        x: "x",
        y: "y",
        stroke: C.model,
        strokeWidth: STROKE.context,
        strokeDasharray: DASH.model,
      }),
      Plot.ruleX([trueBscf], { stroke: C.truth, strokeDasharray: DASH.truth, strokeWidth: 1.4 }),
      Plot.dot([{ x: trueBscf, y: 0 }], { x: "x", y: "y", r: 6, symbol: "diamond", fill: C.truth }),
      Plot.dot([{ x: gBscf, y: 0 }], { x: "x", y: "y", r: 5, symbol: "times", stroke: C.model, strokeWidth: 2 }),
      Plot.text([{ x: 78, y: 1250 }], {
        x: "x",
        y: "y",
        text: () => "extrapolated — no data here",
        fontSize: FS.label,
        fill: C.model,
        textAnchor: "start",
        dy: -8,
      }),
      Plot.text([{ x: trueBscf, y: 4180 }], {
        x: "x",
        y: "y",
        text: () => `true G = ${trueBscf.toFixed(1)} Bscf (known only because this is synthetic)`,
        fontSize: FS.label,
        fill: C.truth,
        textAnchor: "end",
        dx: -8,
      }),
      Plot.text([{ x: gBscf, y: 3560 }], {
        x: "x",
        y: "y",
        text: () => `fitted x-intercept = ${gBscf.toFixed(2)} Bscf (${pct(relError * 100)})`,
        fontSize: FS.label,
        fill: C.model,
        textAnchor: "end",
        dx: -8,
      }),
      Plot.text([{ x: extent, y: 4520 }], {
        x: "x",
        y: "y",
        text: () => `observed production ends, ${extent.toFixed(1)} Bscf`,
        fontSize: FS.label,
        fill: C.ink2,
        textAnchor: "end",
        dx: -8,
      }),
    );
  } else {
    marks.push(
      Plot.text([{ x: extent, y: yDomain[1] - 20 }], {
        x: "x",
        y: "y",
        text: () => `observed production ends, ${extent.toFixed(1)} Bscf`,
        fontSize: FS.label,
        fill: C.ink2,
        textAnchor: "end",
        dx: -8,
      }),
    );
  }

  const plot = panel(
    {
      width: W,
      height: observedRangeOnly ? 430 : 540,
      marginLeft: 84,
      marginBottom: 56,
      marginTop: 18,
      marginRight: 28,
      x: { domain: xDomain, label: "cumulative gas produced, Bscf →", labelAnchor: "center", labelOffset: 44 },
      y: {
        domain: yDomain,
        label: observedRangeOnly ? "↑ p/Z, psia (axis truncated, see caption)" : "↑ p/Z, psia",
        labelAnchor: "center",
        labelOffset: 70,
      },
      marks,
    },
    where,
  );

  const legend = [
    { label: "observed p/Z, 49 points", color: C.observed, dash: "none", symbol: "circle" },
    { label: "volumetric straight-line fit", color: C.model, dash: DASH.model, width: STROKE.emphasis, symbol: "none" },
    ...(observedRangeOnly
      ? []
      : [
          { label: "extrapolation, half stroke", color: C.model, dash: DASH.model, width: STROKE.context, symbol: "none" },
          { label: "true G, known only because synthetic", color: C.truth, dash: DASH.truth, symbol: "diamond" },
        ]),
    { label: "seven non-selected scenarios", color: C.context, dash: DASH.neutral, width: STROKE.context, symbol: "none" },
  ];

  const title = observedRangeOnly
    ? "F01b — the same fit over the observed interval only"
    : "F01 — the fit that looks right: p/Z and the inventory it extrapolates to";
  const subtitle = observedRangeOnly
    ? `Base case, J = 2.0 bbl/day/psi. Vertical range restricted to the observed data so that deviations of a few psia are inspectable. The extrapolation to ${gBscf.toFixed(2)} Bscf is in F01; it is not drawn here.`
    : `Base case, J = 2.0 bbl/day/psi. R-squared = ${rSquared.toFixed(6)}. The fitted line crosses zero at ${gBscf.toFixed(2)} Bscf against a true ${trueBscf.toFixed(1)} Bscf, an error of ${pct(relError * 100, 3)}.`;

  const notes = observedRangeOnly
    ? [
        "The y-axis on this view does not include zero. That is deliberate and it is why this view is secondary: a truncated ordinate would misstate the x-intercept, which is the quantity F01 exists to show. Read the intercept from F01, read the deviations here.",
        `Non-colour channels: observed solid with circle markers, fit long-dashed ${DASH.model}, context traces sparse-dotted ${DASH.neutral}.`,
        EVIDENCE_SHORT,
        STANDARD_CONDITIONS,
      ]
    : [
        `Everything to the right of ${extent.toFixed(1)} Bscf is extrapolation: no observation exists there. The seven thin traces are the other aquifer strengths (J = 0, 0.05, 0.2, 0.6, 6, 20, 60 bbl/day/psi); they are drawn for context and are not labelled individually.`,
        "The history comes from a Fetkovich-aquifer tank model; the fit comes from a separate constant-pore-volume estimator with no influx term. The true gas in place is derived from the exported fields as fit.gas_in_place_scf / (1 + relative_gas_in_place_error); it is not typed into this renderer.",
        `Non-colour channels: observed solid with circle markers, fit long-dashed ${DASH.model} at full stroke, extrapolation the same dash at half stroke plus its own text label, truth fine-dotted ${DASH.truth} with a diamond, context sparse-dotted ${DASH.neutral}.`,
        EVIDENCE_SHORT,
        STANDARD_CONDITIONS,
      ];

  const description = observedRangeOnly
    ? `Scatter plot of p/Z against cumulative gas produced for the base-case water-drive scenario over the observed interval only, from 0 to ${extent.toFixed(1)} Bscf. Forty-nine observed points are drawn as circles joined by a solid line, with the volumetric straight-line fit as a long-dashed line. The vertical axis is truncated to the observed range, from about ${yDomain[0].toFixed(0)} to ${yDomain[1].toFixed(0)} psia, so that departures of a few psia between the observations and the fit are visible; the observations lie above the fit at both ends and below it in the middle. The extrapolation to the fitted x-intercept is deliberately not drawn in this view. Full values in the data table below the figure.`
    : `Scatter plot of p/Z against cumulative gas produced for the base-case water-drive scenario, with the volumetric straight-line fit and its extrapolation to the x-axis. Forty-nine observed points run from ${y[0].toFixed(1)} psia at zero cumulative gas to ${y[48].toFixed(1)} psia at ${extent.toFixed(1)} Bscf, which is where observation stops. The fitted line crosses zero at ${gBscf.toFixed(2)} Bscf; the true gas in place is ${trueBscf.toFixed(1)} Bscf, marked by a fine dotted vertical rule with a diamond. R-squared is ${rSquared.toFixed(6)}. Seven thin dotted traces behind show the other aquifer strengths. Full values in the data table below the figure.`;

  return {
    id: observedRangeOnly ? "f01b-observed-range" : "f01",
    node: frame({ title, subtitle, legend, sections: [plot], notes }),
    title,
    description,
    meta: {
      figure_id: observedRangeOnly ? "F01b" : "F01",
      case_id: "A4_misleading_fit_counterexample",
      selector: "f01_f02_scenarios.json /scenarios[is_base_case] (J = 2.0 bbl/day/psi), 49 observations",
      data_files: ["f01_f02_scenarios.json"],
      axes: {
        x: { quantity: "cumulative gas produced", unit: "Bscf = 1e9 scf", scale: "linear", domain: xDomain },
        y: {
          quantity: "p/Z",
          unit: "psia (absolute)",
          scale: "linear",
          domain: yDomain,
          includes_zero: !observedRangeOnly,
        },
      },
      transformations: [
        "cumulative gas divided by 1e9 to report Bscf (exported as both scf and Bscf; the Bscf field is used directly)",
        "extrapolation evaluated as intercept_psia + slope_psia_per_scf * G, from the exported fit coefficients, not by extending a drawn path",
        "true gas in place derived as fit.gas_in_place_scf / (1 + relative_gas_in_place_error) and cross-checked across all eight scenarios to 1e-9 relative",
      ],
      uncertainty: "none: this figure shows no uncertainty. fit.gas_in_place_stderr_scf exists in the data and belongs in the table, not on the chart; the error here is bias, not scatter.",
      question: "What does a volumetric p/Z fit to an aquifer-supported reservoir actually look like, and where does its x-intercept land relative to the truth?",
      caveat: observedRangeOnly
        ? "Vertical axis truncated. This view is for inspecting deviations only; the intercept geometry is in F01. Noise-free synthetic history."
        : `Everything beyond ${extent.toFixed(1)} Bscf is extrapolation with no data behind it. The true inventory is evaluation-only information; no field measurement provides it.`,
    },
  };
}

/* ---------- F02 ---------- */

function buildF02(data) {
  const where = "F02";
  const { base } = baseScenario(data, where);
  const { x, residual } = scenarioSeries(base, where);
  const extent = fin(req(base, "observed_extent_bscf", where), `${where}: observed_extent_bscf`);
  const points = x.map((v, i) => ({ x: v, y: residual[i] }));
  const rms = Math.sqrt(residual.reduce((a, r) => a + r * r, 0) / residual.length);
  const maxAbs = Math.max(...residual.map(Math.abs));
  const worst = points.reduce((a, p) => (Math.abs(p.y) > Math.abs(a.y) ? p : a), points[0]);
  const initialPz = fin(base.p_over_z_psia[0], `${where}: p_over_z_psia[0]`);
  fin(rms, `${where}: rms residual`);

  // The two judgement bands are nested, so the inner one is given its own boundary
  // rules: two fills of the same token colour would read as one block.
  const bands = [{ y1: -50, y2: 50 }];
  const bandRight = extent + 2;

  const plot = panel(
    {
      width: W,
      height: 400,
      marginLeft: 84,
      marginBottom: 56,
      marginTop: 18,
      marginRight: 28,
      x: { domain: [-2, 120], label: "cumulative gas produced, Bscf →", labelAnchor: "center", labelOffset: 44 },
      y: { domain: [-60, 60], label: "↑ observation − fit, psia of p/Z", labelAnchor: "center", labelOffset: 70 },
      marks: [
        grid("y"),
        Plot.rect(bands, {
          x1: () => -2,
          x2: () => bandRight,
          y1: (d) => d.y1,
          y2: (d) => d.y2,
          fill: C.band,
          ariaHidden: true,
        }),
        Plot.ruleY([-10, 10], { stroke: C.border, strokeDasharray: "2 4", strokeWidth: 1, x1: -2, x2: bandRight }),
        Plot.ruleY([0], { stroke: C.border, strokeWidth: 1.2 }),
        Plot.ruleX([extent], { stroke: C.border, strokeDasharray: "4 4", strokeWidth: 1 }),
        Plot.line(points, { x: "x", y: "y", stroke: C.observed, strokeWidth: STROKE.default, curve: "linear" }),
        Plot.dot(points, { x: "x", y: "y", r: 3.4, fill: C.observed, symbol: "circle" }),
        Plot.text([{ x: bandRight, y: 50 }], {
          x: "x",
          y: "y",
          text: () => "±50 psia",
          fontSize: FS.label,
          fill: C.ink3,
          textAnchor: "start",
          dx: 8,
          dy: -2,
        }),
        Plot.text([{ x: bandRight, y: 10 }], {
          x: "x",
          y: "y",
          text: () => "±10 psia",
          fontSize: FS.label,
          fill: C.ink3,
          textAnchor: "start",
          dx: 8,
          dy: -2,
        }),
        Plot.text([{ x: bandRight, y: 32 }], {
          x: "x",
          y: "y",
          text: () => "the two bands are the case author's engineering judgement of volume-averaged reservoir pressure accuracy, 10 to 50 psi — not a retrieved figure",
          fontSize: FS.label,
          fill: C.ink3,
          textAnchor: "start",
          dx: 8,
          lineWidth: 36,
        }),
        Plot.text([worst], {
          x: "x",
          y: "y",
          text: () => `largest excursion ${worst.y >= 0 ? "+" : "−"}${Math.abs(worst.y).toFixed(2)} psia at ${worst.x.toFixed(0)} Bscf`,
          fontSize: FS.label,
          fill: C.observed,
          textAnchor: "start",
          dx: 10,
          dy: -6,
        }),
        Plot.text([{ x: extent, y: -56 }], {
          x: "x",
          y: "y",
          text: () => `observation ends, ${extent.toFixed(1)} Bscf`,
          fontSize: FS.label,
          fill: C.ink2,
          textAnchor: "end",
          dx: -8,
        }),
      ],
    },
    where,
  );

  const title = "F02 — the residual structure that would have had to give it away";
  const subtitle = `All 49 observation-minus-fit residuals for the base case, same x-scale as F01. RMS ${rms.toFixed(2)} psia, largest absolute residual ${maxAbs.toFixed(2)} psia, which is ${((maxAbs / initialPz) * 100).toFixed(2)} percent of the initial p/Z.`;
  const description = `Residuals of the volumetric straight-line fit for the base-case scenario, in psia of p/Z, against cumulative gas produced, with a zero rule and two neutral reference bands at plus or minus 10 and plus or minus 50 psia. The residuals are not scattered: they start at plus ${residual[0].toFixed(2)} psia at zero cumulative production, sweep down to about ${Math.min(...residual).toFixed(2)} psia, rise back through zero and fall again, an RMS of ${rms.toFixed(2)} psia over the 49 points. Nothing is smoothed and no point is omitted. Full values in the data table below the figure.`;

  return {
    id: "f02",
    node: frame({
      title,
      subtitle,
      legend: [
        { label: "residual, observation − fit", color: C.observed, dash: "none", symbol: "circle" },
        { label: "zero rule", color: C.border, dash: "none", symbol: "none" },
        { label: "±10 and ±50 psia judgement bands", color: C.band, dash: "hidden", symbol: "band" },
      ],
      sections: [plot],
      notes: [
        "These are residuals, not uncertainty bars. They carry no confidence statement of any kind: they are the exact arithmetic difference between a noise-free synthetic observation and the straight line fitted through it.",
        "Noise-free. Real data adds measurement error on top of this structure. Nothing is smoothed; the line joins consecutive observations because the sequence is the signal.",
        "The 10 to 50 psi band is the case author's engineering judgement about volume-averaged reservoir pressure accuracy, not a retrieved figure, and it is the single load-bearing premise of the detectability conclusion: if the real band is 1 to 5 psi, that conclusion reverses.",
        EVIDENCE_SHORT,
        STANDARD_CONDITIONS,
      ],
    }),
    title,
    description,
    meta: {
      figure_id: "F02",
      case_id: "A4_misleading_fit_counterexample",
      selector: "f01_f02_scenarios.json /scenarios[is_base_case]/residual_p_over_z_psia, 49 values",
      data_files: ["f01_f02_scenarios.json"],
      axes: {
        x: { quantity: "cumulative gas produced", unit: "Bscf", scale: "linear", domain: [-2, 120] },
        y: { quantity: "residual of the volumetric fit", unit: "psia of p/Z", scale: "linear", domain: [-60, 60] },
      },
      transformations: [
        "none on the residuals; they are the exported observation-minus-fit values, plotted at full precision in source order",
        `RMS ${rms.toFixed(6)} psia and largest absolute residual ${maxAbs.toFixed(6)} psia are derived here from the same 49 values`,
      ],
      uncertainty:
        "none: this figure shows no uncertainty. The residuals are not error bars; the drawn bands are a declared engineering judgement about achievable pressure accuracy, labelled as such.",
      question: "Is there structure in the residuals of that excellent fit, and how large is it compared with the pressure accuracy a real field could achieve?",
      caveat:
        "Residuals are not uncertainty bars. Noise-free history. The 10 to 50 psi band is the case author's judgement, not a retrieved figure, and the detectability conclusion depends on it.",
    },
  };
}

/* ---------- F03 ---------- */

function buildF03(data) {
  const where = "F03";
  const rows = req(data, "rows", where);
  if (!Array.isArray(rows) || rows.length !== 8) throw new Error(`${where}: expected 8 rows`);
  const note = req(data, "note", where);
  const points = rows.map((r, i) => {
    const j = fin(req(r, "productivity_index_bbl_per_day_psi", where), `${where}[${i}]: J`);
    return {
      j,
      label: j === 0 ? "J = 0 (volumetric control)" : `J = ${j}`,
      x: fin(req(r, "invaded_pore_volume_fraction", where), `${where}[${i}]: invaded_pore_volume_fraction`),
      gip: fin(req(r, "relative_gas_in_place_error", where), `${where}[${i}]: relative_gas_in_place_error`) * 100,
      remaining: fin(req(r, "relative_remaining_gas_error", where), `${where}[${i}]: relative_remaining_gas_error`) * 100,
      r2: fin(req(r, "r_squared", where), `${where}[${i}]: r_squared`),
      isBase: j === 2,
      isControl: j === 0,
    };
  });
  const xDomain = [-0.012, 0.36];
  const marginLeft = 92;
  const marginRight = 150;

  const upper = panel(
    {
      width: W,
      height: 360,
      marginLeft,
      marginRight,
      marginTop: 24,
      marginBottom: 40,
      x: { domain: xDomain, label: null, ticks: 8 },
      y: { domain: [-10, 180], label: "↑ relative error, percent", labelAnchor: "center", labelOffset: 74 },
      marks: [
        grid("y"),
        Plot.ruleY([0], { stroke: C.border, strokeWidth: 1.2 }),
        Plot.line(points, { x: "x", y: "remaining", stroke: C.context, strokeWidth: STROKE.default, strokeDasharray: DASH.neutral }),
        Plot.dot(points, { x: "x", y: "remaining", r: 4, symbol: "square", fill: C.context }),
        Plot.line(points, { x: "x", y: "gip", stroke: C.model, strokeWidth: STROKE.emphasis, strokeDasharray: DASH.model }),
        Plot.dot(points, { x: "x", y: "gip", r: 3.6, symbol: "circle", fill: C.model }),
        Plot.dot(points.filter((p) => p.isBase), { x: "x", y: "gip", r: 8, symbol: "circle", stroke: C.ink, strokeWidth: 1.6, fill: "none" }),
        Plot.dot(points.filter((p) => p.isControl), { x: "x", y: "gip", r: 8, symbol: "diamond", stroke: C.ink, strokeWidth: 1.6, fill: "none" }),
        // textAnchor, dx and dy are constants in Plot and not channels, so each point's
        // label is its own mark. The four low-influx cases sit almost on top of one
        // another, so they are labelled as a vertical ladder rather than in place.
        ...points.map((p, i) =>
          Plot.text([p], {
            x: "x",
            y: "gip",
            text: () => (p.j === 0 ? "J = 0" : `J = ${p.j}`),
            fontSize: FS.label,
            fill: C.ink2,
            textAnchor: p.x < 0.06 ? "start" : "middle",
            dx: p.x < 0.06 ? 10 : 0,
            dy: p.x < 0.06 ? -16 - 19 * i : i % 2 === 0 ? -16 : -32,
          }),
        ),
        Plot.text(points.filter((p) => p.isBase), {
          x: "x",
          y: "gip",
          text: () => "base case",
          fontSize: FS.label,
          fill: C.ink,
          textAnchor: "start",
          dx: 12,
          dy: 16,
        }),
        Plot.text([points[7]], {
          x: "x",
          y: "remaining",
          text: () => "remaining-gas error (what an engineer acts on)",
          fontSize: FS.label,
          fill: C.context,
          textAnchor: "end",
          dx: -10,
          dy: -14,
        }),
        Plot.text([points[5]], {
          x: "x",
          y: "gip",
          text: () => "gas-in-place error",
          fontSize: FS.label,
          fill: C.model,
          textAnchor: "start",
          dx: 12,
          dy: 20,
        }),
      ],
    },
    `${where} upper panel`,
  );

  // Lower panel. 1 - R-squared on a log scale. The J = 0 row is exactly 1.0, so its
  // 1 - R-squared is exactly zero: it is drawn at the axis floor, as a position and not
  // as a value, and labelled. Nothing is clipped and no epsilon is added.
  const oneMinus = points.map((p) => ({ ...p, v: 1 - p.r2 }));
  const nonZero = oneMinus.filter((p) => p.v > 0);
  const zeros = oneMinus.filter((p) => p.v === 0);
  if (!nonZero.length) throw new Error(`${where}: lower panel would emit no marks`);
  const smallest = Math.min(...nonZero.map((p) => p.v));
  const floor = smallest / 40;
  const zeroPosition = smallest / 6;
  const ceil = Math.max(...nonZero.map((p) => p.v)) * 4;

  const lower = panel(
    {
      width: W,
      height: 320,
      marginLeft,
      marginRight,
      marginTop: 20,
      marginBottom: 58,
      x: { domain: xDomain, label: "terminal water influx as a fraction of the initial hydrocarbon pore volume, dimensionless →", labelAnchor: "center", labelOffset: 46, ticks: 8 },
      y: { type: "log", domain: [floor, ceil], axis: null },
      marks: [
        logAxis("y", [1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2].filter((v) => v >= floor && v <= ceil), {
          label: "↑ 1 − R-squared, log scale (lower = better fit)",
          labelOffset: 74,
          format: expTick,
        }),
        grid("y", { ticks: [1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2].filter((v) => v >= floor && v <= ceil) }),
        Plot.line(nonZero, { x: "x", y: "v", stroke: C.observed, strokeWidth: STROKE.default }),
        Plot.dot(nonZero, { x: "x", y: "v", r: 4, symbol: "circle", fill: C.observed }),
        Plot.dot(zeros.map((p) => ({ ...p, v: zeroPosition })), {
          x: "x",
          y: "v",
          r: 6,
          symbol: "times",
          stroke: C.ink,
          strokeWidth: 2,
        }),
        Plot.dot(nonZero.filter((p) => p.isBase), { x: "x", y: "v", r: 8, symbol: "circle", stroke: C.ink, strokeWidth: 1.6, fill: "none" }),
        Plot.text(zeros.map((p) => ({ ...p, v: zeroPosition })), {
          x: "x",
          y: "v",
          text: () => "J = 0: 1 − R² is exactly 0, drawn at the axis floor as a position, not a value",
          fontSize: FS.label,
          fill: C.ink,
          textAnchor: "start",
          dx: 12,
        }),
        Plot.text(nonZero.filter((p) => p.isBase), {
          x: "x",
          y: "v",
          text: (d) => `base case: R² = ${d.r2.toFixed(6)}`,
          fontSize: FS.label,
          fill: C.ink,
          textAnchor: "start",
          dx: 12,
          dy: 4,
        }),
        Plot.text([nonZero[nonZero.length - 1]], {
          x: "x",
          y: "v",
          text: (d) => `worst fit in the sweep: R² = ${d.r2.toFixed(4)}`,
          fontSize: FS.label,
          fill: C.observed,
          textAnchor: "end",
          dx: -8,
          dy: -12,
        }),
      ],
    },
    `${where} lower panel`,
  );

  const table = tableSection({
    columns: [
      { label: "J, bbl/day/psi", width: 120, emphasis: true },
      { label: "invaded PV fraction", width: 150 },
      { label: "gas-in-place error", width: 150 },
      { label: "remaining-gas error", width: 160 },
      { label: "R-squared", width: 150 },
      { label: "1 − R-squared", width: 150 },
    ],
    rows: points.map((p) => [
      p.isControl ? "0 (control)" : String(p.j),
      p.x.toFixed(4),
      pctOrZero(p.gip, 3),
      pctOrZero(p.remaining, 3),
      p.r2.toFixed(6),
      1 - p.r2 === 0 ? "0 exactly" : sig(1 - p.r2),
    ]),
    note: "R-squared is shown here as an aligned exhibit, not as a second axis on the error panel: the two quantities are incommensurable, and this figure exists to show R-squared staying high while the inventory error grows.",
  });

  const title = "F03 — how the inventory bias scales with aquifer support, and what R-squared says about it";
  const subtitle = "Eight computed support cases, J = 0, 0.05, 0.2, 0.6, 2, 6, 20 and 60 bbl/day/psi. There is no continuum here and nothing is interpolated between the points; the joining lines connect computed cases only.";
  const description = `Two stacked panels against aquifer strength, sharing one horizontal axis: terminal water influx as a fraction of the initial hydrocarbon pore volume, from 0 to ${points[7].x.toFixed(4)}. The upper panel shows the relative error in fitted gas in place rising from about zero at the J equals 0 volumetric control to plus ${points[7].gip.toFixed(0)} percent at J equals 60, with the remaining-gas error above it at every point, reaching plus ${points[7].remaining.toFixed(0)} percent. The base case, J equals 2, is circled at plus ${points[4].gip.toFixed(2)} percent. The lower panel shows one minus R-squared on a logarithmic scale, rising only from exactly zero at the control, through ${sig(1 - points[4].r2)} at the base case, to ${sig(1 - points[7].r2)} at J equals 60 — that is, R-squared falls only from 1.000000 to ${points[7].r2.toFixed(4)} while the inventory error reaches ${points[7].gip.toFixed(0)} percent. Each point carries its J value as a direct label. Full values in the table inside this figure and in the data table below it.`;

  return {
    id: "f03",
    node: frame({
      title,
      subtitle,
      legend: [
        { label: "gas-in-place error", color: C.model, dash: DASH.model, width: STROKE.emphasis, symbol: "circle" },
        { label: "remaining-gas error", color: C.context, dash: DASH.neutral, symbol: "square" },
        { label: "1 − R-squared (lower panel)", color: C.observed, dash: "none", symbol: "circle" },
        { label: "exactly zero, drawn at the axis floor", color: C.ink, dash: "hidden", symbol: "times" },
        { label: "base case / control, circled", color: C.ink, dash: "hidden", symbol: "open-square" },
      ],
      sections: [upper, lower, table],
      notes: [
        note,
        "The J = 0 volumetric control is on both panels and is never hidden. It is not placed on the log axis: its 1 − R-squared is exactly zero, so it is drawn at the axis floor with its own marker and label rather than clipped or shifted by an epsilon.",
        "The bias/stderr column of the source data is meaningless for the J = 0 row — its residuals are at the 1e-10 level, so its standard error is a rounding artefact — and that row's value of −2.06 is reported as exported and excluded from the 50-to-88 range quoted elsewhere.",
        EVIDENCE_SHORT,
      ],
    }),
    title,
    description,
    meta: {
      figure_id: "F03",
      case_id: "A4_misleading_fit_counterexample",
      selector: "f03_bias_sweep.json /rows, audited summary pointer /strength_sweep, 8 rows",
      data_files: ["f03_bias_sweep.json"],
      axes: {
        x: { quantity: "terminal invaded pore-volume fraction", unit: "dimensionless", scale: "linear", domain: xDomain },
        y_upper: { quantity: "relative error", unit: "percent (signed)", scale: "linear", domain: [-10, 180] },
        y_lower: { quantity: "1 − R-squared", unit: "dimensionless", scale: "log", domain: [floor, ceil] },
      },
      transformations: [
        "relative errors multiplied by 100 to report percent; sign preserved",
        "R-squared transformed to 1 − R-squared for the log panel; the exactly-zero control is placed at the axis floor as a labelled position, not clipped and not epsilon-shifted",
      ],
      uncertainty:
        "none: this figure shows no uncertainty. fitted_stderr_scf and bias_over_stderr exist in the source and belong in the table; bias_over_stderr is not interpretable for the J = 0 row.",
      question: "Does the error grow with aquifer strength, and does the fit statistic warn you about it?",
      caveat:
        "Only the aquifer productivity index was varied; the horizontal axis is a model output of this generator, not an independent field observation. Eight computed cases, no continuum, no interpolation.",
    },
  };
}

/* ---------- F04 ---------- */

function buildF04(data) {
  const where = "F04";
  const rows = req(data, "rows", where);
  if (!Array.isArray(rows) || rows.length !== 40) throw new Error(`${where}: expected 40 rows, got ${rows.length}`);
  const note = req(data, "note", where);
  const xAxisName = req(data, "x_axis", where);
  if (xAxisName !== "requested fraction of history") {
    throw new Error(`${where}: exported x_axis is "${xAxisName}", the axis label contract has changed`);
  }
  const selected = [0, 2, 6, 60];
  const clean = rows.map((r, i) => ({
    j: fin(req(r, "productivity_index_bbl_per_day_psi", where), `${where}[${i}]: J`),
    f: fin(req(r, "history_fraction", where), `${where}[${i}]: history_fraction`) * 100,
    e: fin(req(r, "relative_gas_in_place_error", where), `${where}[${i}]: relative_gas_in_place_error`) * 100,
    n: fin(req(r, "n_points", where), `${where}[${i}]: n_points`),
    years: fin(req(r, "years_observed", where), `${where}[${i}]: years_observed`),
  }));
  const shown = clean.filter((r) => selected.includes(r.j));
  if (shown.length !== 20) throw new Error(`${where}: expected 20 rows for the four default series, got ${shown.length}`);
  const ends = selected.map((j) => shown.filter((r) => r.j === j).sort((a, b) => b.f - a.f)[0]);
  const base = shown.filter((r) => r.j === 2).sort((a, b) => a.f - b.f);
  const strongest = shown.filter((r) => r.j === 60).sort((a, b) => a.f - b.f);
  const drift = base[base.length - 1].e - base[0].e;
  const peak = strongest.reduce((a, r) => (r.e > a.e ? r : a), strongest[0]);

  const style = {
    0: { color: C.context, dash: DASH.neutral, symbol: "square", width: STROKE.default },
    2: { color: C.model, dash: "none", symbol: "circle", width: STROKE.emphasis },
    6: { color: C.observed, dash: DASH.model, symbol: "diamond", width: STROKE.default },
    60: { color: C.ink, dash: DASH.truth, symbol: "triangle", width: STROKE.default },
  };

  const marks = [grid("y"), Plot.ruleY([0], { stroke: C.border, strokeWidth: 1.2 })];
  for (const j of selected) {
    const series = shown.filter((r) => r.j === j).sort((a, b) => a.f - b.f);
    const s = style[j];
    marks.push(
      Plot.line(series, { x: "f", y: "e", stroke: s.color, strokeWidth: s.width, strokeDasharray: s.dash === "none" ? null : s.dash }),
      Plot.dot(series, { x: "f", y: "e", r: 4, symbol: s.symbol, fill: s.color }),
    );
  }
  marks.push(
    Plot.text(ends, {
      x: "f",
      y: "e",
      text: (d) => (d.j === 0 ? "J = 0 (volumetric control)" : d.j === 2 ? "J = 2, base case" : `J = ${d.j}`),
      fontSize: FS.label,
      fill: (d) => style[d.j].color,
      textAnchor: "start",
      dx: 10,
    }),
    Plot.text([{ f: base[0].f, e: 58 }], {
      x: "f",
      y: "e",
      text: () => `base case moves ${drift.toFixed(2)} percentage points of true G between the first fifth of the history and all of it, always upward`,
      fontSize: FS.label,
      fill: C.model,
      textAnchor: "start",
      dx: 4,
      lineWidth: 40,
    }),
    Plot.text([peak], {
      x: "f",
      y: "e",
      text: () => "J = 60 peaks here and falls back: a stabilising estimate is not evidence that it is right",
      fontSize: FS.label,
      fill: C.ink,
      textAnchor: "start",
      dx: 10,
      dy: -12,
    }),
  );

  const plot = panel(
    {
      width: W,
      height: 460,
      marginLeft: 92,
      marginRight: 190,
      marginTop: 24,
      marginBottom: 56,
      x: { domain: [14, 104], ticks: [20, 40, 60, 80, 100], label: "requested fraction of history, percent →", labelAnchor: "center", labelOffset: 44 },
      y: { domain: [-8, 108], label: "↑ relative error in fitted gas in place, percent", labelAnchor: "center", labelOffset: 74 },
      marks,
    },
    where,
  );

  const table = tableSection({
    columns: [
      { label: "requested fraction", width: 150, emphasis: true },
      { label: "realised points", width: 120 },
      { label: "years observed", width: 130 },
      { label: "J = 0", width: 120 },
      { label: "J = 2 (base)", width: 130 },
      { label: "J = 6", width: 120 },
      { label: "J = 60", width: 120 },
    ],
    rows: [20, 40, 60, 80, 100].map((f) => {
      const at = (j) => shown.find((r) => r.j === j && Math.round(r.f) === f);
      return [
        `${f} percent`,
        String(at(0).n),
        at(0).years.toFixed(2),
        pctOrZero(at(0).e, 2),
        pct(at(2).e, 2),
        pct(at(6).e, 2),
        pct(at(60).e, 2),
      ];
    }),
    note: "history_fraction times horizon is not necessarily the realised sample time, which is why the realised point count and the years observed are columns of their own.",
  });

  const title = "F04 — what the inventory estimate does as history accumulates";
  const subtitle = "Four of the eight computed support cases are drawn so the chart stays readable: the volumetric control and J = 2, 6 and 60 bbl/day/psi. All eight are in the exported data and belong in the page's data table.";
  const description = `Slope chart of the relative error in fitted gas in place against the requested fraction of history, at five requested fractions — 20, 40, 60, 80 and 100 percent — with one line per aquifer strength. The volumetric control is flat at zero to machine precision. The base case, J equals 2, rises monotonically from plus ${base[0].e.toFixed(2)} percent at the first fifth of the history to plus ${base[base.length - 1].e.toFixed(2)} percent at the whole of it, a move of ${drift.toFixed(2)} percentage points. J equals 6 rises from plus ${shown.find((r) => r.j === 6 && r.f === 20).e.toFixed(2)} to a peak and falls slightly. J equals 60 runs plus ${strongest.map((r) => r.e.toFixed(2)).join(", plus ")} percent: it peaks at the second point and then falls back for the rest of the history. Each line is drawn in its own dash pattern and marker shape and is labelled directly at its right end. Full values in the table inside this figure and in the data table below it.`;

  return {
    id: "f04",
    node: frame({
      title,
      subtitle,
      legend: selected.map((j) => ({
        label: j === 0 ? "J = 0 (volumetric control)" : j === 2 ? "J = 2, base case" : `J = ${j}`,
        color: style[j].color,
        dash: style[j].dash,
        width: style[j].width,
        symbol: style[j].symbol === "triangle" ? "diamond" : style[j].symbol,
      })),
      sections: [plot, table],
      notes: [
        note,
        "The horizontal axis is the requested fraction of history, exactly as exported: it is a request to the fitter, not a realised sample time. The realised point count and the years observed are in the table.",
        "Prefix fits share observations. Consecutive points on one line are not independent samples, and the apparent stabilisation of a line carries no statistical guarantee.",
        "The direction of drift is specific to a reservoir whose aquifer support weakens over time; a constant-pressure aquifer would drift differently.",
        EVIDENCE_SHORT,
      ],
    }),
    title,
    description,
    meta: {
      figure_id: "F04",
      case_id: "A4_misleading_fit_counterexample",
      selector: "f04_progressive.json /rows, audited summary pointer /progressive_fits, 40 rows; 4 of 8 series drawn (J = 0, 2, 6, 60)",
      data_files: ["f04_progressive.json"],
      axes: {
        x: { quantity: "requested fraction of history", unit: "percent of the requested horizon", scale: "linear", domain: [14, 104] },
        y: { quantity: "relative error in fitted gas in place", unit: "percent (signed)", scale: "linear", domain: [-8, 108] },
      },
      transformations: [
        "history_fraction multiplied by 100 for the axis; relative errors multiplied by 100 to report percent, sign preserved",
        "no interpolation between the five requested fractions; the joining line connects computed prefix fits only",
      ],
      uncertainty:
        "none: this figure shows no uncertainty. relative_stderr exists per row in the source and belongs in the table; prefix fits share observations, so a band drawn across this axis would be misleading.",
      question: "If you had refitted every few years, would the estimate have been stable, and does stability mean correctness?",
      caveat:
        "Prefix fits share observations and are not independent samples. The axis is the requested fraction of history, not the realised sample time. Four of eight computed series are drawn; all eight are in the data.",
    },
  };
}

/* ---------- F05 ---------- */

function buildF05(data) {
  const where = "F05";
  const calibration = fin(req(data, "calibration_points", where), `${where}: calibration_points`);
  const holdout = fin(req(data, "holdout_points", where), `${where}: holdout_points`);
  const splitIndex = fin(req(data, "split_index", where), `${where}: split_index`);
  if (calibration !== 30 || holdout !== 19 || splitIndex !== 30) {
    throw new Error(`${where}: expected a 30/19 split at index 30, got ${calibration}/${holdout} at ${splitIndex}`);
  }
  const splitX = fin(req(data, "split_cumulative_gas_bscf", where), `${where}: split_cumulative_gas_bscf`);
  const x = finArray(req(data, "cumulative_gas_bscf", where), `${where}: cumulative_gas_bscf`, 49);
  const t = finArray(req(data, "times_years", where), `${where}: times_years`, 49);
  const obs = finArray(req(data, "observed_p_over_z_psia", where), `${where}: observed_p_over_z_psia`, 49);
  const fitted = finArray(req(data, "fitted_p_over_z_psia", where), `${where}: fitted_p_over_z_psia`, 49);
  const obsP = finArray(req(data, "observed_pressure_psia", where), `${where}: observed_pressure_psia`, 49);
  const recon = req(data, "reconstructed_pressure_psia_conditional", where);
  const futureZ = req(data, "future_synthetic_z_used", where);
  if (recon.length !== 49 || futureZ.length !== 49) throw new Error(`${where}: reconstruction arrays are not 49 long`);
  recon.forEach((v, i) => {
    if (i < splitIndex) {
      if (v !== null) throw new Error(`${where}: reconstruction at calibration index ${i} should be null`);
    } else fin(v, `${where}: reconstructed_pressure_psia_conditional[${i}]`);
  });
  futureZ.forEach((v, i) => {
    if (i >= splitIndex) fin(v, `${where}: future_synthetic_z_used[${i}]`);
  });
  const metrics = req(data, "metrics", where);
  const calErr = fin(req(metrics, "calibration_relative_gas_in_place_error", where), `${where}: calibration error`) * 100;
  const calR2 = fin(req(metrics, "calibration_r_squared", where), `${where}: calibration_r_squared`);
  const rmse = fin(req(metrics, "holdout_rmse_pressure_psia", where), `${where}: holdout_rmse_pressure_psia`);
  const rmseFrac = fin(req(metrics, "holdout_rmse_fraction_of_initial_pressure", where), `${where}: rmse fraction`) * 100;
  const pDenom = fin(req(metrics, "initial_pressure_psia_denominator", where), `${where}: initial_pressure_psia_denominator`);
  const gate = fin(req(metrics, "borrowed_demonstration_gate", where), `${where}: borrowed_demonstration_gate`) * 100;

  const obsPoints = x.map((v, i) => ({ x: v, y: obs[i], held: i >= splitIndex }));
  const fitPoints = x.map((v, i) => ({ x: v, y: fitted[i] }));

  const primary = panel(
    {
      width: W,
      height: 430,
      marginLeft: 88,
      marginRight: 28,
      marginTop: 22,
      marginBottom: 54,
      x: { domain: [-1.5, 57], label: "cumulative gas produced, Bscf →", labelAnchor: "center", labelOffset: 44 },
      y: { domain: [0, 4700], label: "↑ p/Z, psia", labelAnchor: "center", labelOffset: 72 },
      marks: [
        grid("y"),
        Plot.rect([{}], {
          x1: () => -1.5,
          x2: () => splitX,
          y1: () => 0,
          y2: () => 4700,
          fill: C.band,
          ariaHidden: true,
        }),
        Plot.ruleX([splitX], { stroke: C.border, strokeWidth: 1.4 }),
        Plot.line(obsPoints, { x: "x", y: "y", stroke: C.observed, strokeWidth: STROKE.default }),
        Plot.dot(obsPoints, {
          x: "x",
          y: "y",
          r: 3.6,
          symbol: (d) => (d.held ? "square" : "circle"),
          fill: C.observed,
        }),
        // Drawn over the observations, which it very nearly coincides with: that
        // coincidence over the held-out region is the finding.
        Plot.line(fitPoints, { x: "x", y: "y", stroke: C.model, strokeWidth: STROKE.emphasis, strokeDasharray: DASH.model }),
        Plot.text([{ x: splitX / 2, y: 600 }], {
          x: "x",
          y: "y",
          text: () => `calibrated here — ${calibration} points, ${t[splitIndex - 1].toFixed(2)} years`,
          fontSize: FS.label,
          fill: C.ink2,
          textAnchor: "middle",
        }),
        Plot.text([{ x: (splitX + 55) / 2, y: 600 }], {
          x: "x",
          y: "y",
          text: () => `predicted — ${holdout} points, no tuning here`,
          fontSize: FS.label,
          fill: C.ink2,
          textAnchor: "middle",
        }),
        Plot.text([{ x: splitX, y: 4560 }], {
          x: "x",
          y: "y",
          text: () => `split at ${splitX.toFixed(3)} Bscf`,
          fontSize: FS.label,
          fill: C.ink,
          textAnchor: "end",
          dx: -8,
        }),
      ],
    },
    `${where} primary panel`,
  );

  /* The calibration statistic sits in the held-out half of the panel, beside the fit it
     describes. It used to be a Plot.text with lineWidth 36, which let it run 62 CSS px
     past the right edge of the figure on every engine: the exported SVG and the PNG both
     cut the sentence off mid-qualification. It is now wrapped to the room that actually
     exists between its anchor and the edge of the plot area, and nothing is dropped --
     "of true G" is the part that says the error is against the known inventory rather
     than against the calibration sample, and it is the part a crop would take. */
  plotAnnotation(primary, {
    scaleX: primary.scale("x"),
    scaleY: primary.scale("y"),
    at: { x: splitX + 2, y: 1500 },
    text: `calibration R² = ${calR2.toFixed(6)}, calibration gas in place ${pct(calErr)} of true G`,
    fill: C.model,
    anchor: "start",
    where: `${where} primary panel`,
  });

  const reconPoints = recon
    .map((v, i) => ({ t: t[i], p: v, z: futureZ[i] }))
    .filter((d) => d.p !== null);
  if (reconPoints.length !== holdout) throw new Error(`${where}: expected ${holdout} reconstructed points`);
  const obsPPoints = t.map((v, i) => ({ t: v, p: obsP[i] }));

  const secondary = panel(
    {
      width: W,
      height: 380,
      marginLeft: 88,
      marginRight: 28,
      marginTop: 22,
      marginBottom: 56,
      x: { domain: [-0.3, 12.3], label: "time, years of 365.25 days →", labelAnchor: "center", labelOffset: 44 },
      y: { domain: [0, 4300], label: "↑ pressure, psia (absolute)", labelAnchor: "center", labelOffset: 72 },
      marks: [
        grid("y"),
        Plot.rect([{}], {
          x1: () => -0.3,
          x2: () => t[splitIndex],
          y1: () => 0,
          y2: () => 4300,
          fill: C.band,
          ariaHidden: true,
        }),
        Plot.ruleX([t[splitIndex]], { stroke: C.border, strokeWidth: 1.4 }),
        Plot.line(obsPPoints, { x: "t", y: "p", stroke: C.observed, strokeWidth: STROKE.default }),
        Plot.dot(obsPPoints, { x: "t", y: "p", r: 3.2, symbol: "circle", fill: C.observed }),
        Plot.line(reconPoints, { x: "t", y: "p", stroke: C.model, strokeWidth: STROKE.emphasis, strokeDasharray: DASH.model }),
        Plot.dot(reconPoints, { x: "t", y: "p", r: 4, symbol: "square", stroke: C.model, strokeWidth: 1.6, fill: "none" }),
        Plot.text([{ t: 0.2, p: 900 }], {
          x: "t",
          y: "p",
          text: () =>
            "This panel is not a forecast. Each reconstructed pressure is a predicted p/Z multiplied by the deviation factor of the held-out state — exported as future_synthetic_z_used — which a real forecast does not have.",
          fontSize: FS.label,
          fill: C.ink,
          textAnchor: "start",
          lineWidth: 62,
        }),
        Plot.text([reconPoints[reconPoints.length - 1]], {
          x: "t",
          y: "p",
          text: (d) => `future synthetic Z at the last held point = ${d.z.toFixed(6)}`,
          fontSize: FS.label,
          fill: C.model,
          textAnchor: "end",
          dx: -6,
          dy: 22,
        }),
      ],
    },
    `${where} secondary panel`,
  );

  const title = "F05 — the chronological holdout the wrong model passes";
  const subtitle = `A volumetric fit calibrated on the first ${calibration} of 49 observations and used to predict the remaining ${holdout}. No tuning on the held-out points.`;
  const description = `Two panels for a chronological holdout on the base case. The primary panel, in p/Z space, plots 49 observations against cumulative gas produced with the volumetric fit as a long-dashed line; the first ${calibration} points, to ${splitX.toFixed(3)} Bscf, sit in a shaded calibration region and are drawn as circles, and the remaining ${holdout} held-out points are unshaded and drawn as squares. The calibration R-squared is ${calR2.toFixed(6)} and the calibration gas in place is ${calErr.toFixed(2)} percent too high, yet the fit tracks the held-out observations closely by eye. The secondary panel, in pressure space against time in years, plots the observed pressure and the conditional reconstruction, which exists only over the holdout region: it is a predicted p/Z multiplied by the deviation factor of the held-out state, exported as future_synthetic_z_used, so it borrows future information and is not a blind forecast. The held-out pressure RMSE is ${rmse.toFixed(2)} psia, which is ${rmseFrac.toFixed(3)} percent of the ${pDenom.toFixed(0)} psia initial pressure. Full values in the data table below the figure.`;

  return {
    id: "f05",
    node: frame({
      title,
      subtitle,
      legend: [
        { label: "observed, calibration region", color: C.observed, dash: "none", symbol: "circle" },
        { label: "observed, held-out region", color: C.observed, dash: "none", symbol: "square" },
        { label: "volumetric fit / conditional reconstruction", color: C.model, dash: DASH.model, width: STROKE.emphasis, symbol: "open-square" },
        { label: "calibration window (shaded)", color: C.band, dash: "hidden", symbol: "band" },
      ],
      sections: [primary, secondary],
      notes: [
        `Two different denominators, and they are not comparable. Inventory error: ${pct(calErr)} of the true gas in place, denominator = true G. Held-out pressure RMSE: ${rmse.toFixed(2)} psia = ${rmseFrac.toFixed(3)} percent of the initial pressure, denominator = ${pDenom.toFixed(1)} psia. One is an error in a quantity outside the data; the other is an error in a quantity inside it.`,
        `The ${gate.toFixed(1)} percent marker in the source metrics is a borrowed demonstration gate, not a forecast-accuracy result and not a validation criterion. It is recorded here because the case recorded it: ${gate.toFixed(1)} percent of ${pDenom.toFixed(0)} psia is ${((gate / 100) * pDenom).toFixed(1)} psia.`,
        "This is the most uncomfortable number in the case: a genuine chronological holdout, with no tuning on the held-out points, is passed comfortably by a model whose gas in place is 11.3 percent wrong. A holdout tests the forecast over the horizon it covers; it does not test a quantity that lives outside the data.",
        "The pressure panel is a conditional reconstruction, not a blind forecast. Nothing on this page is marked validated.",
        EVIDENCE_SHORT,
        STANDARD_CONDITIONS,
      ],
    }),
    title,
    description,
    meta: {
      figure_id: "F05",
      case_id: "A4_misleading_fit_counterexample",
      selector: "f05_holdout.json, 30 calibration and 19 held-out observations, split index 30",
      data_files: ["f05_holdout.json"],
      axes: {
        x_primary: { quantity: "cumulative gas produced", unit: "Bscf", scale: "linear", domain: [-1.5, 57] },
        y_primary: { quantity: "p/Z", unit: "psia (absolute)", scale: "linear", domain: [0, 4700], includes_zero: true },
        x_secondary: { quantity: "time", unit: "years of 365.25 days", scale: "linear", domain: [-0.3, 12.3] },
        y_secondary: { quantity: "pressure", unit: "psia (absolute)", scale: "linear", domain: [0, 4300], includes_zero: true },
      },
      transformations: [
        "none on the plotted series; the calibration-region reconstruction is null by construction and is not imputed, interpolated or drawn",
        "relative errors multiplied by 100 to report percent",
      ],
      uncertainty:
        "none: this figure shows no uncertainty band. The two error statistics reported are a calibration inventory error (denominator: true gas in place) and a held-out pressure RMSE (denominator: initial pressure, 4000 psia); they are labelled separately and never combined.",
      question: "Does a genuine chronological holdout catch the error?",
      caveat:
        "The pressure reconstruction multiplies a predicted p/Z by the deviation factor of the held-out state — future synthetic Z — so the 15.7 psia figure is a borrowed demonstration, not an attainable forecast error. No validation is claimed.",
    },
  };
}

/* ---------- F06 ---------- */

function buildF06(data) {
  const where = "F06";
  const original = req(data, "original", where);
  const power = req(data, "post_review_power_curve", where);
  const originalRows = req(original, "rows", where);
  const powerRows = req(power, "rows", where);
  if (originalRows.length !== 7) throw new Error(`${where}: expected 7 original rows`);
  if (powerRows.length !== 10) throw new Error(`${where}: expected 10 power-curve rows`);
  const replicatesOriginal = fin(req(original, "replicates", where), `${where}: original replicates`);
  const replicatesPower = fin(req(power, "replicates", where), `${where}: power-curve replicates`);
  const seedNote = req(original, "seed_note", where);
  const powerNote = req(power, "note", where);

  const A = originalRows.map((r, i) => ({
    sigma: fin(req(r, "pressure_sigma_psi", where), `${where}: original[${i}] sigma`),
    water: fin(req(r, "detection_rate_water_drive", where), `${where}: original[${i}] water-drive rate`),
    nullRate: fin(req(r, "detection_rate_volumetric_null", where), `${where}: original[${i}] null rate`),
  }));
  const B = powerRows.map((r, i) => ({
    sigma: fin(req(r, "pressure_sigma_psi", where), `${where}: power[${i}] sigma`),
    rate: fin(req(r, "detection_rate", where), `${where}: power[${i}] rate`),
  }));

  // Half-power crossing, interpolated on the page between the two bracketing exported rows.
  const above = B.filter((d) => d.rate >= 0.5).sort((a, b) => b.sigma - a.sigma)[0];
  const below = B.filter((d) => d.rate < 0.5).sort((a, b) => a.sigma - b.sigma)[0];
  if (!above || !below) throw new Error(`${where}: the power curve does not bracket a detection rate of 0.5`);
  const crossing = above.sigma + ((0.5 - above.rate) / (below.rate - above.rate)) * (below.sigma - above.sigma);
  fin(crossing, `${where}: half-power crossing`);

  const sigmaTicks = [1, 2, 5, 10, 20, 40, 80];
  const xScale = { type: "log", domain: [0.85, 95], axis: null };
  const refs = () => [
    Plot.ruleY([0.5], { stroke: C.border, strokeDasharray: "4 4", strokeWidth: 1 }),
    Plot.ruleY([0.05], { stroke: C.border, strokeDasharray: "1 3", strokeWidth: 1 }),
    Plot.text([{ x: 0.9, y: 0.5 }], {
      x: "x",
      y: "y",
      text: () => "half power, 0.5",
      fontSize: FS.label,
      fill: C.ink3,
      textAnchor: "start",
      dy: -6,
    }),
    Plot.text([{ x: 0.9, y: 0.05 }], {
      x: "x",
      y: "y",
      text: () => "nominal size, 0.05",
      fontSize: FS.label,
      fill: C.ink3,
      textAnchor: "start",
      dy: 16,
    }),
  ];

  const upper = panel(
    {
      width: W,
      height: 380,
      marginLeft: 88,
      marginRight: 210,
      marginTop: 22,
      marginBottom: 40,
      x: xScale,
      y: { domain: [-0.04, 1.09], label: "↑ detection rate, dimensionless", labelAnchor: "center", labelOffset: 72 },
      marks: [
        logAxis("x", sigmaTicks, { label: null, labelOffset: 36 }),
        grid("y"),
        ...refs(),
        Plot.line(A, { x: "sigma", y: "water", stroke: C.observed, strokeWidth: STROKE.default }),
        Plot.dot(A, { x: "sigma", y: "water", r: 4.5, symbol: "circle", fill: C.observed }),
        Plot.line(A, { x: "sigma", y: "nullRate", stroke: C.context, strokeWidth: STROKE.default, strokeDasharray: DASH.neutral }),
        Plot.dot(A, { x: "sigma", y: "nullRate", r: 4.5, symbol: "square", fill: C.context }),
        Plot.text([A[A.length - 1]], {
          x: "sigma",
          y: "water",
          text: () => `water-drive detection\n(positive control)\n${replicatesOriginal} replicates`,
          fontSize: FS.label,
          fill: C.observed,
          textAnchor: "start",
          dx: 12,
          dy: -34,
        }),
        Plot.text([A[0]], {
          x: "sigma",
          y: "nullRate",
          text: () => `volumetric-null rejection (negative control), flat at ${A[0].nullRate.toFixed(4)}, ${replicatesOriginal} replicates`,
          fontSize: FS.label,
          fill: C.context,
          textAnchor: "start",
          dx: 10,
          dy: -14,
        }),
      ],
    },
    `${where} panel A`,
  );

  const lower = panel(
    {
      width: W,
      height: 360,
      marginLeft: 88,
      marginRight: 210,
      marginTop: 22,
      marginBottom: 56,
      x: xScale,
      y: { domain: [-0.04, 1.09], label: "↑ detection rate, dimensionless", labelAnchor: "center", labelOffset: 72 },
      marks: [
        logAxis("x", sigmaTicks, {
          label: "standard deviation of the independent Gaussian error added to the reported pressures, psi (log scale) →",
          labelOffset: 44,
        }),
        grid("y"),
        ...refs(),
        Plot.line(B, { x: "sigma", y: "rate", stroke: C.model, strokeWidth: STROKE.context, strokeDasharray: "2 4" }),
        Plot.dot(B, { x: "sigma", y: "rate", r: 4.5, symbol: "diamond", fill: C.model }),
        Plot.ruleX([crossing], { stroke: C.ink, strokeDasharray: DASH.truth, strokeWidth: 1.2 }),
        Plot.text([{ x: crossing, y: 0.86 }], {
          x: "x",
          y: "y",
          text: () =>
            `half-power crossing interpolated on this page: ${above.sigma} psi → ${above.rate}, ${below.sigma} psi → ${below.rate}, linear interpolation gives ${crossing.toFixed(2)} psi (±0.2 psi, from the case report). Not an exported field.`,
          fontSize: FS.label,
          fill: C.ink,
          textAnchor: "start",
          dx: 10,
          lineWidth: 30,
        }),
        Plot.text([B[B.length - 1]], {
          x: "sigma",
          y: "rate",
          text: () => `post-review power curve\n${replicatesPower} replicates, own seed\nseparate experiment`,
          fontSize: FS.label,
          fill: C.model,
          textAnchor: "start",
          dx: 12,
          dy: -10,
        }),
      ],
    },
    `${where} panel B`,
  );

  const title = "F06 — could anyone have told, under noise? Two separate experiments, never spliced";
  const subtitle = `Upper panel: the pre-registered noise sweep, ${replicatesOriginal} replicates at each of seven sigma levels. Lower panel: the post-review power curve, ${replicatesPower} replicates at ten levels, a different experiment with its own seed. They share the horizontal axis and nothing else.`;
  const description = `Detection rate of the pre-registered curvature test against added pressure noise, on a logarithmic horizontal axis from 1 to 80 psi, in two panels. The upper panel is the original sweep at ${replicatesOriginal} replicates: the water-drive detection rate, the positive control, falls from ${A[0].water.toFixed(2)} at 1 psi through ${A[3].water.toFixed(3)} at 10 psi to ${A[A.length - 1].water.toFixed(4)} at 80 psi, drawn with circle markers; the volumetric-null rejection rate, the negative control, is flat at ${A[0].nullRate.toFixed(4)} at every level, drawn with square markers on a sparse dotted line. The lower panel is a separate post-review experiment at ${replicatesPower} replicates and a different seed, measuring the power curve between 8 and 16 psi: it falls from ${B[0].rate.toFixed(5)} at 8 psi to ${B[B.length - 1].rate.toFixed(5)} at 16 psi, drawn with diamond markers. The two experiments are in separate panels and are never joined into one curve. Reference rules are drawn at a detection rate of 0.5 and at the nominal size of 0.05. Full values in the two data tables below the figure.`;

  return {
    id: "f06",
    node: frame({
      title,
      subtitle,
      legend: [
        { label: `water-drive detection, ${replicatesOriginal} replicates`, color: C.observed, dash: "none", symbol: "circle" },
        { label: `volumetric-null rejection, ${replicatesOriginal} replicates`, color: C.context, dash: DASH.neutral, symbol: "square" },
        { label: `post-review power curve, ${replicatesPower} replicates`, color: C.model, dash: "2 4", width: STROKE.context, symbol: "diamond" },
      ],
      sections: [upper, lower],
      notes: [
        "The measured quantities are the discrete points. Every connecting line in this figure is a visual guide between computed sigma levels and carries no information between them.",
        "Two distinct events are distinguished and never pooled: detecting curvature in a water-drive history (the alternative) and rejecting the straight line on a strictly volumetric history (the null).",
        powerNote,
        `Rates are exact, not rounded: at ${replicatesOriginal} replicates every rate is a multiple of ${(1 / replicatesOriginal).toFixed(4)}. ${seedNote} So the seven levels are rescalings of one draw set rather than seven independent experiments, and the ${A[0].nullRate.toFixed(4)} null rate is a high draw of that seed, not the detector's size: pooled over 20000 replicates on a fresh seed it is 0.0473.`,
        "The null rate is identical at every noise level because the null p/Z series is exactly linear, so the t statistic is scale-invariant.",
        "Conditional on this detector, 49 quarterly observations, and independent Gaussian pressure error; correlated or systematically biased error was not tested.",
        EVIDENCE_SHORT,
      ],
    }),
    title,
    description,
    meta: {
      figure_id: "F06",
      case_id: "A4_misleading_fit_counterexample",
      selector:
        "f06_detection.json /original (pointer /residuals_and_detectability/noise_sweep, 400 replicates, 7 levels) and /post_review_power_curve (pointer /post_review_sensitivities/power_curve, 4000 replicates, 10 levels), drawn as two separate panels",
      data_files: ["f06_detection.json"],
      axes: {
        x: { quantity: "standard deviation of added independent Gaussian pressure error", unit: "psi", scale: "log", domain: [0.85, 95] },
        y: { quantity: "detection rate", unit: "dimensionless, 0 to 1", scale: "linear", domain: [-0.04, 1.09] },
      },
      transformations: [
        "none on the rates; they are plotted as exported",
        `half-power crossing interpolated linearly on this page between the bracketing exported rows (${above.sigma} psi at ${above.rate} and ${below.sigma} psi at ${below.rate}), giving ${crossing.toFixed(4)} psi; the derivation is printed in the figure and the value is not an exported field`,
      ],
      uncertainty: `frequency framing rather than an interval: each series prints its replicate count (${replicatesOriginal} and ${replicatesPower}). No confidence band is drawn, because the two experiments have different replicate counts and different seeds and a band would invite pooling them.`,
      question: "At what pressure measurement accuracy does the curvature detector actually work, and does it false-positive on a reservoir with no aquifer?",
      caveat:
        "Two experiments with different seeds and replicate counts, drawn in separate panels and never spliced. The 0.0675 null rate is a high draw of one seed, not the detector's size. Connecting lines are visual guides.",
    },
  };
}

/* ---------- F07 ---------- */

function buildF07(data) {
  const where = "F07";
  const values = req(data, "values", where);
  const criticalT = fin(req(data, "critical_t", where), `${where}: critical_t`);
  const note = req(data, "note", where);
  const valuesNote = req(values, "note", where);
  const g = (key) => fin(req(values, key, where), `${where}: values.${key}`);

  const errors = [
    { label: "matched", v: g("base_case_matched_relative_gas_in_place_error") * 100, symbol: "circle", color: C.observed },
    { label: "mismatched (DAK \u2192 H-Y)", v: g("base_case_mismatched_relative_gas_in_place_error") * 100, symbol: "diamond", color: C.model },
    { label: "consistent H-Y", v: g("base_case_consistent_hall_yarborough_relative_gas_in_place_error") * 100, symbol: "square", color: C.context },
  ];
  const spread = Math.max(...errors.map((e) => e.v)) - Math.min(...errors.map((e) => e.v));

  const tStats = [
    { label: "water drive, matched", v: g("base_case_matched_curvature_t"), symbol: "circle", color: C.observed },
    { label: "water drive, mismatched", v: g("base_case_mismatched_curvature_t"), symbol: "diamond", color: C.model },
    { label: "volumetric null, mismatched", v: g("null_mismatched_curvature_t"), symbol: "square", color: C.context },
  ];
  // The category names sit on the y-axis rather than beside each point: three long
  // labels floating in a half-width panel collide with each other and with the frame.
  const place = (value, domain) => {
    const f = (value - domain[0]) / (domain[1] - domain[0]);
    return f > 0.55 ? { textAnchor: "end", dx: -14 } : { textAnchor: "start", dx: 14 };
  };
  const errorDomain = [12.0, 12.75];
  const tDomain = [-10.5, 10.5];

  const half = (W - 24) / 2;
  const left = panel(
    {
      width: half,
      height: 300,
      /* Wide enough for "mismatched (DAK → H-Y)" as measured, not as guessed: at 170 the
         label ran 3 px past the left edge of the panel and was cut off there. */
      marginLeft: 182,
      marginRight: 24,
      marginTop: 26,
      marginBottom: 60,
      x: { domain: errorDomain, label: "relative error in gas in place, percent →", labelAnchor: "center", labelOffset: 42, ticks: 4 },
      y: { domain: errors.map((e) => e.label), label: null },
      marks: [
        grid("x"),
        ...errors.map((e) => Plot.dot([e], { x: "v", y: "label", r: 7, symbol: e.symbol, fill: e.color })),
        ...errors.map((e) =>
          Plot.text([e], {
            x: "v",
            y: "label",
            text: () => pct(e.v, 3),
            fontSize: FS.label,
            fill: C.ink2,
            ...place(e.v, errorDomain),
          }),
        ),
      ],
    },
    `${where} left panel`,
  );
  left.setAttribute("x", 0);

  const right = panel(
    {
      width: half,
      height: 300,
      marginLeft: 215,
      marginRight: 24,
      marginTop: 26,
      marginBottom: 60,
      x: { domain: tDomain, label: "curvature t statistic, signed, dimensionless →", labelAnchor: "center", labelOffset: 42 },
      y: { domain: tStats.map((t) => t.label), label: null },
      marks: [
        grid("x"),
        Plot.rect([{}], {
          x1: () => -criticalT,
          x2: () => criticalT,
          y1: () => -0.5,
          y2: () => 2.5,
          fill: C.band,
          ariaHidden: true,
        }),
        Plot.ruleX([-criticalT, criticalT], { stroke: C.border, strokeWidth: 1.2 }),
        Plot.ruleX([0], { stroke: C.border, strokeDasharray: "1 3", strokeWidth: 1 }),
        ...tStats.map((t) => Plot.dot([t], { x: "v", y: "label", r: 7, symbol: t.symbol, fill: t.color })),
        ...tStats.map((t) =>
          Plot.text([t], {
            x: "v",
            y: "label",
            text: () => `${t.v >= 0 ? "+" : "−"}${Math.abs(t.v).toFixed(3)}`,
            fontSize: FS.label,
            fill: C.ink2,
            ...place(t.v, tDomain),
          }),
        ),
        Plot.text([{ x: 0, y: tStats[0].label }], {
          x: "x",
          y: "y",
          text: () => `shaded: ±${criticalT.toFixed(4)}, not rejected`,
          fontSize: FS.label,
          fill: C.ink,
          textAnchor: "middle",
          dy: -22,
        }),
      ],
    },
    `${where} right panel`,
  );

  const pair = svgEl("svg", { width: W, height: 300 });
  left.setAttribute("y", 0);
  right.setAttribute("x", half + 24);
  right.setAttribute("y", 0);
  pair.appendChild(left);
  pair.appendChild(right);

  const title = "F07 — the detector is not a clean aquifer diagnostic";
  const subtitle = "Left: the inventory bias barely moves when the analyst reads Z from a different correlation. Right: the curvature statistic does, and it changes sign on a reservoir with no aquifer at all.";
  const description = `Two panels on deviation-factor correlation choice. On the left, three gas-in-place errors on a common position scale: matched at ${pct(errors[0].v, 3)}, mismatched at ${pct(errors[1].v, 3)} and consistent Hall-Yarborough at ${pct(errors[2].v, 3)}, all three inside ${spread.toFixed(2)} percentage points of one another. On the right, three curvature t statistics on a signed axis symmetric about zero, against a critical value of plus or minus ${criticalT.toFixed(4)} drawn as a shaded acceptance band: the matched water-drive case at plus ${tStats[0].v.toFixed(3)}, the mismatched water-drive case at plus ${tStats[1].v.toFixed(3)}, and a strictly volumetric history read with the wrong correlation at minus ${Math.abs(tStats[2].v).toFixed(3)} — twice the aquifer's own magnitude, with the opposite sign. Each point carries a direct text label and its own marker shape. Full values in the data table below the figure.`;

  return {
    id: "f07",
    node: frame({
      title,
      subtitle,
      legend: [
        { label: "matched (circle)", color: C.observed, dash: "hidden", symbol: "circle" },
        { label: "mismatched (diamond)", color: C.model, dash: "hidden", symbol: "diamond" },
        { label: "consistent Hall-Yarborough / volumetric null (square)", color: C.context, dash: "hidden", symbol: "square" },
        { label: `acceptance band, ±${criticalT.toFixed(4)}`, color: C.band, dash: "hidden", symbol: "band" },
      ],
      sections: [pair],
      notes: [
        valuesNote,
        note,
        `The volumetric-null case is ${tStats[2].v.toFixed(3)}, not ${Math.abs(tStats[2].v).toFixed(3)}: taking its magnitude would erase the fact that a reservoir with no aquifer produces a rejection with the opposite sign, and one twice the size of the aquifer's own.`,
        `On the left, all three gas-in-place errors sit inside ${spread.toFixed(2)} percentage points of one another: the bias is insensitive to the correlation choice, and the detector is not.`,
        "Rejecting the straight line does not uniquely identify aquifer support. The detector's false-positive rate of about 0.05 is conditional on the analyst using exactly the correlation that generated the history, a condition no field analysis can meet, since nature uses neither correlation.",
        "This block is post-review. It was not pre-registered.",
        EVIDENCE_SHORT,
      ],
    }),
    title,
    description,
    meta: {
      figure_id: "F07",
      case_id: "A4_misleading_fit_counterexample",
      selector: "f07_z_mismatch.json /values and /critical_t, audited summary pointer /post_review_sensitivities/z_correlation_sensitivity",
      data_files: ["f07_z_mismatch.json"],
      axes: {
        x_left: { quantity: "relative error in gas in place", unit: "percent (signed)", scale: "linear", domain: [12.0, 12.75] },
        x_right: { quantity: "curvature t statistic", unit: "dimensionless, signed", scale: "linear", domain: [-10.5, 10.5], symmetric_about_zero: true },
      },
      transformations: [
        "relative errors multiplied by 100 to report percent; sign preserved",
        "t statistics plotted signed, with no absolute value anywhere in the figure or its description",
      ],
      uncertainty:
        "the critical value is the uncertainty statement: ±critical_t = ±2.0128955989194295 is the two-sided acceptance band of the pre-registered curvature test, drawn as a shaded region. No interval is placed on the individual statistics.",
      question: "If the analyst reads the deviation factor from a different correlation than the one that generated the history, what happens to the bias, and what happens to the detector?",
      caveat:
        "Post-review, not pre-registered. Rejecting the straight-line model does not uniquely identify aquifer support: a strictly volumetric history read with the wrong correlation rejects harder, with the opposite sign.",
    },
  };
}

/* ---------- F08 ---------- */

/** The bound F08 publishes for the solver convergence residual, in psia of p/Z. */
const RESIDUAL_BOUND_PSIA = 1e-8;

/**
 * Present a solver convergence residual as a bound rather than as digits.
 *
 * The exact value of this residual is zero: it measures how far the solve failed to
 * close, not a property of the reservoir. Printing it to four significant figures
 * asserts a precision the cross-platform comparison does not support - the same residual
 * computed on macOS arm64 and on Linux x86_64 agrees only in order of magnitude, because
 * two dozen libm functions are permitted to disagree in their last place and a Newton
 * iteration turns that into a different stopping point. Four digits of such a number are
 * platform noise dressed as a measurement.
 *
 * So the figure states what is both true and stable everywhere it was measured: the
 * residual is below 1e-8 psia. That bound was checked against 48 values - eight
 * refinement levels in each of six environments, spanning the pinned canonical
 * container, ordinary Ubuntu runners on CPython 3.11, 3.12 and 3.13, and macOS arm64 -
 * with the largest observed 3.44e-09 psia, a factor of 2.9 inside the bound.
 *
 * The full-precision value stays in the case summary and in the exported figure data.
 * Nothing is rounded, quantised or hidden; only the label changes. The guard below fails
 * the build rather than printing a bound some future value does not satisfy.
 */
function residualBoundLabel(value) {
  if (!(Math.abs(value) < RESIDUAL_BOUND_PSIA)) {
    throw new Error(
      `F08: max_solver_residual_p_over_z_psia is ${value}, which is not below the ` +
        `published bound of ${RESIDUAL_BOUND_PSIA} psia. Re-establish the bound against ` +
        `every supported environment rather than widening it.`,
    );
  }
  return `< ${RESIDUAL_BOUND_PSIA.toExponential(0)}`;
}

/**
 * Significant figures used for the relative gas-in-place error in the F08 table.
 *
 * Nine, not the sixteen this table used to print. Sixteen is the full repr of a double,
 * and the digits past about the eighth are not stable across the supported platforms:
 * the measured cross-platform spread on these values is around 1e-13 relative, which
 * lands inside a sixteen-digit rendering and outside a nine-digit one. Nine keeps every
 * digit the convergence argument needs - the four refinement levels of each series stay
 * visibly distinct, and the deviation column that carries the convergence rate is
 * unaffected - while printing nothing the comparison cannot support.
 */
const RELATIVE_ERROR_SIGNIFICANT_FIGURES = 9;

function buildF08(data) {
  const where = "F08";
  const note = req(data, "note", where);
  const series = ["J_2", "J_60"].map((key) => {
    const block = req(data, key, where);
    const levels = req(block, "levels", where);
    if (!Array.isArray(levels) || levels.length !== 4) throw new Error(`${where}: ${key} expected 4 levels`);
    const span = fin(req(block, "error_span_over_refinement", where), `${where}: ${key}.error_span_over_refinement`);
    const clean = levels.map((l, i) => ({
      dt: fin(req(l, "timestep_days", where), `${where}: ${key}.levels[${i}].timestep_days`),
      steps: fin(req(l, "steps", where), `${where}: ${key}.levels[${i}].steps`),
      influx: fin(req(l, "terminal_water_influx_bbl", where), `${where}: ${key}.levels[${i}].terminal_water_influx_bbl`),
      err: fin(req(l, "relative_gas_in_place_error", where), `${where}: ${key}.levels[${i}].relative_gas_in_place_error`),
      solver: fin(req(l, "max_solver_residual_p_over_z_psia", where), `${where}: ${key}.levels[${i}].max_solver_residual_p_over_z_psia`),
    }));
    const finest = clean.reduce((a, l) => (l.dt < a.dt ? l : a), clean[0]);
    for (const level of clean) level.dev = Math.abs(level.err - finest.err);
    const spanCheck = Math.abs(clean[0].dev - span);
    if (spanCheck / span > 1e-9) {
      throw new Error(`${where}: ${key} coarsest deviation ${clean[0].dev} disagrees with exported span ${span}`);
    }
    return { key, label: key === "J_2" ? "J = 2 (base case)" : "J = 60 (strongest aquifer)", levels: clean, finest, span };
  });

  const THRESHOLD = 1e-3;
  const nonZero = series.flatMap((s) => s.levels.filter((l) => l.dev > 0).map((l) => l.dev));
  if (!nonZero.length) throw new Error(`${where}: no non-zero deviations, the figure would emit no marks`);
  const floor = Math.min(...nonZero) / 8;
  const ceil = THRESHOLD * 4;

  const style = {
    J_2: { color: C.observed, dash: "none", symbol: "circle", width: STROKE.default },
    J_60: { color: C.context, dash: DASH.neutral, symbol: "square", width: STROKE.default },
  };

  const decades = [1e-9, 1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2].filter((v) => v >= floor && v <= ceil);
  const marks = [
    logAxis("y", decades, {
      label: "↑ |deviation from the finest computed level|, dimensionless (log)",
      labelOffset: 86,
      format: expTick,
    }),
    logAxis("x", series[0].levels.map((l) => l.dt), {
      label: "timestep, days (log scale, decreasing to the right: more refined →)",
      labelOffset: 44,
      format: (d) => d.toFixed(2),
    }),
    grid("y", { ticks: decades }),
    Plot.ruleY([THRESHOLD], { stroke: C.ink, strokeDasharray: DASH.truth, strokeWidth: 1.4 }),
    Plot.text([{ x: series[0].levels[0].dt, y: THRESHOLD }], {
      x: "x",
      y: "y",
      text: () => "pre-registered acceptance threshold A4 = 1e-3",
      fontSize: FS.label,
      fill: C.ink,
      textAnchor: "start",
      dy: -8,
    }),
  ];
  for (const s of series) {
    const drawn = s.levels.filter((l) => l.dev > 0);
    const zeroed = s.levels.filter((l) => l.dev === 0);
    const st = style[s.key];
    marks.push(
      Plot.line(drawn, { x: "dt", y: "dev", stroke: st.color, strokeWidth: st.width, strokeDasharray: st.dash === "none" ? null : st.dash }),
      Plot.dot(drawn, { x: "dt", y: "dev", r: 4.5, symbol: st.symbol, fill: st.color }),
      Plot.dot(zeroed.map((l) => ({ ...l, dev: floor })), { x: "dt", y: "dev", r: 6, symbol: "times", stroke: C.ink, strokeWidth: 2 }),
      Plot.text([drawn[0]], {
        x: "dt",
        y: "dev",
        text: () => `${s.label}, span ${s.span.toExponential(2)}`,
        fontSize: FS.label,
        fill: st.color,
        textAnchor: "start",
        dx: 12,
        dy: -2,
      }),
    );
  }
  marks.push(
    Plot.text([{ x: series[0].finest.dt, y: floor }], {
      x: "x",
      y: "y",
      text: () => "finest computed level: deviation is exactly 0 by construction. Drawn at the axis floor as a position, not a value — not clipped, no epsilon added, and not a truth value.",
      fontSize: FS.label,
      fill: C.ink,
      textAnchor: "end",
      dx: -22,
      dy: -16,
      lineWidth: 40,
    }),
  );

  const plot = panel(
    {
      width: W,
      height: 440,
      marginLeft: 104,
      marginRight: 40,
      marginTop: 26,
      marginBottom: 56,
      // A descending domain puts the coarse step at the left and the refined step at
      // the right. `reverse` would undo that, so it is deliberately not used.
      x: { type: "log", domain: [35, 3.2], axis: null },
      y: { type: "log", domain: [floor, ceil], axis: null },
      marks,
    },
    where,
  );

  const table = tableSection({
    columns: [
      { label: "series", width: 130, emphasis: true },
      { label: "dt, days", width: 100 },
      { label: "steps", width: 80 },
      { label: "terminal influx, bbl", width: 170 },
      { label: "relative gas-in-place error", width: 230, mono: true },
      { label: "deviation from finest", width: 160 },
      { label: "max solver residual, psia", width: 180 },
    ],
    rows: series.flatMap((s) =>
      s.levels.map((l, i) => [
        i === 0 ? (s.key === "J_2" ? "J = 2" : "J = 60") : "",
        l.dt.toFixed(4),
        String(l.steps),
        l.influx.toFixed(3),
        l.err.toPrecision(RELATIVE_ERROR_SIGNIFICANT_FIGURES),
        l.dev === 0 ? "0 exactly (comparator)" : l.dev.toExponential(3),
        residualBoundLabel(l.solver),
      ]),
    ),
    note: "Successive-halving ratios of the deviation are about 4.2 and 5.0, consistent with a second-order scheme; the comparator is the finest computed level and not an exact solution.",
  });

  const title = "F08 — is the reported bias resolved in time, or is it a timestep artefact?";
  const subtitle = `Convergence of the recovered gas-in-place error under timestep refinement, for the base case and the strongest aquifer. Both series sit three to four decades below the pre-registered acceptance threshold of ${THRESHOLD.toExponential(0)}.`;
  const description = `Timestep refinement for two aquifer strengths, both axes logarithmic, with the timestep decreasing to the right so that more refined reads rightward. The vertical axis is the absolute deviation of each level's relative gas-in-place error from that series' own finest computed level. For J equals 2 the deviations are ${series[0].levels
    .map((l) => (l.dev === 0 ? "exactly 0" : l.dev.toExponential(2)))
    .join(", ")} at timesteps of ${series[0].levels.map((l) => l.dt.toFixed(2)).join(", ")} days; for J equals 60 they are ${series[1].levels
    .map((l) => (l.dev === 0 ? "exactly 0" : l.dev.toExponential(2)))
    .join(", ")}. The finest level of each series is exactly zero by construction and is drawn at the axis floor with a cross marker and an explicit label rather than being dropped by the logarithmic scale. A horizontal rule marks the pre-registered acceptance threshold of ${THRESHOLD.toExponential(0)}, three to four decades above every plotted point. Full values in the convergence table inside this figure.`;

  return {
    id: "f08",
    node: frame({
      title,
      subtitle,
      legend: [
        { label: "J = 2 (base case)", color: C.observed, dash: "none", symbol: "circle" },
        { label: "J = 60 (strongest aquifer)", color: C.context, dash: DASH.neutral, symbol: "square" },
        { label: "deviation exactly 0, drawn at the axis floor", color: C.ink, dash: "hidden", symbol: "times" },
        { label: "pre-registered threshold, 1e-3", color: C.ink, dash: DASH.truth, symbol: "none" },
      ],
      sections: [plot, table],
      notes: [
        note,
        "The quantity plotted is a difference against the finest computed level, so that level sits at zero by construction. It is drawn at the axis floor with its own marker and label: log(0) is never taken, the value is never clipped, and no epsilon is added to it.",
        "The finest level is a comparator, not truth. A scheme that converged to the wrong answer would produce exactly this picture, which is why this figure answers only the timestep question and no other.",
        EVIDENCE_SHORT,
      ],
    }),
    title,
    description,
    meta: {
      figure_id: "F08",
      case_id: "A4_misleading_fit_counterexample",
      selector: "f08_refinement.json /J_2/levels and /J_60/levels, audited summary pointer /timestep_refinement, 4 levels each",
      data_files: ["f08_refinement.json"],
      axes: {
        x: { quantity: "timestep", unit: "days", scale: "log, reversed", domain: [35, 3.2] },
        y: { quantity: "absolute deviation of the relative gas-in-place error from the finest computed level", unit: "dimensionless", scale: "log", domain: [floor, ceil] },
      },
      transformations: [
        "deviation computed here as |relative_gas_in_place_error(level) − relative_gas_in_place_error(finest level)| per series, and cross-checked against the exported error_span_over_refinement to 1e-9 relative",
        "the exactly-zero finest level is positioned at the axis floor and labelled; it is not clipped and no epsilon is added",
      ],
      uncertainty:
        "none: this figure shows no uncertainty. It shows numerical convergence against a comparator, which is a different thing from an error bar, and the comparator is not an exact solution.",
      question: "Is the reported bias a physical result or a timestep artefact?",
      caveat:
        "The finest computation is a numerical comparator, not an exact solution. Convergence of this quantity does not establish that the formulation is right.",
    },
  };
}

/* ---------- F09 ---------- */

function buildF09(contract, digests, extra) {
  const where = "F09";
  const source = req(contract, "numerical_source", where);
  const exportBlock = req(contract, "export", where);
  const units = req(contract, "units", where);
  const files = req(contract, "files", where);
  const evidence = req(contract, "evidence_class", where);
  const stages = [
    { name: "1. Protocol", detail: "pre-registered before the run", hash: req(source, "protocol_sha256", where) },
    { name: "2. Case source", detail: "cases/A4_.../run.py", hash: req(source, "case_source_sha256", where) },
    { name: "3. Audited summary", detail: req(source, "baseline_summary_path", where), hash: req(source, "baseline_summary_sha256", where) },
    {
      name: "4. Export",
      detail: `${req(exportBlock, "exporter_path", where)}, ${req(exportBlock, "reconciliation_checks_passed", where)} checks at rtol ${req(exportBlock, "reconcile_relative_tolerance", where)}`,
      hash: req(exportBlock, "exporter_sha256", where),
    },
  ];

  const chainHeight = 150;
  const chain = svgEl("svg", { width: W, height: chainHeight });
  const boxWidth = (W - 2 * PADX - 3 * 18) / 4;
  stages.forEach((stage, i) => {
    const x = PADX + i * (boxWidth + 18);
    chain.appendChild(
      svgEl("rect", { x, y: 10, width: boxWidth, height: 104, fill: "none", stroke: C.border, "stroke-width": 1, rx: 3 }),
    );
    chain.appendChild(textNode(x + 12, 34, stage.name, { size: FS.base, fill: C.ink, weight: 600 }));
    let y = 54;
    for (const line of wrap(stage.detail, boxWidth - 24, FS.base)) {
      chain.appendChild(textNode(x + 12, y, line, { size: FS.base, fill: C.ink3 }));
      y += 17;
    }
    chain.appendChild(
      textNode(x + 12, 104, `${stage.hash.slice(0, 12)}…`, { size: FS.base, fill: C.ink2, family: MONO }),
    );
    if (i < stages.length - 1) {
      const ax = x + boxWidth;
      chain.appendChild(
        svgEl("path", { d: `M${ax + 2},62 L${ax + 14},62 M${ax + 9},57 L${ax + 14},62 L${ax + 9},67`, stroke: C.border, "stroke-width": 1.4, fill: "none" }),
      );
    }
  });
  chain.appendChild(
    textNode(PADX, 138, "Short forms are shown in the chain; every full SHA-256 and the command that reproduces it is in the table below.", {
      size: FS.base,
      fill: C.ink3,
    }),
  );

  const hashTable = tableSection({
    columns: [
      { label: "stage or file", width: 300, emphasis: true },
      { label: "SHA-256 (full, selectable)", width: 640, mono: true },
    ],
    rows: [
      ...stages.map((s) => [s.name.replace(/^\d+\.\s*/, ""), s.hash]),
      ...files.map((f) => [`${f.path} → ${figureConsumers(f.figure_data)}`, f.sha256]),
    ],
    note: "Reproduce any row with: shasum -a 256 <path>. Paths are relative to the repository root, except the figure data files, which are under site/src/data/figures/.",
  });

  const verified = digests.every((d) => d.match);
  const statusRows = [
    ["Seven figure-data digests match contract.json", verified ? "PASS" : "FAIL", `recomputed by this renderer at build time; ${digests.filter((d) => d.match).length} of ${digests.length} match`],
    ["Export reconciliation against the audited summary", "PASS", `${req(exportBlock, "reconciliation_checks_passed", where)} quantities at relative tolerance ${req(exportBlock, "reconcile_relative_tolerance", where)}, as recorded by the exporter`],
    ["NIST reference extracts present in this repository", "BLOCKED", "deliberately absent: scripts/fetch_nist_reference.py --verify-only exits 1 reporting 3 files MISSING; 20 tests in tests/test_gas_properties.py skip with \"NIST reference extract not present\"; cases/A2_pvt_independent_check/run.py exits 1 with a declared reference-table-absent status"],
    ["Hosted continuous-integration run", "NOT RUN", "none is claimed and none is linked"],
    ["Journal peer review", "NOT APPLICABLE", "the referee pass described in the case report was a review of the case, and no stronger phrase is used"],
    ["Field validation against measured reservoir data", "NOT RUN", "every history on this page is synthetic"],
    ["Deployment to an operational workflow", "NOT APPLICABLE", "nothing here is deployed"],
    ["Independent from-scratch reimplementation", "NOT RUN", "one exists but it is not a committed artifact of this repository, so a reader cannot check it here"],
    ["Known-influx oracle closes on the governing equation", "PASS", "closes to 3.6e-11, but it is an algebraic rearrangement of the same equation the generator solves: it tests the solve, not the formulation"],
    ["Test counts rendered from a committed file", "NOT RUN", "no file under site/src/data/ carries them; run the suite locally rather than read a count that no committed file contains"],
  ];
  const statusTable = tableSection({
    columns: [
      { label: "check", width: 380, emphasis: true },
      { label: "state", width: 150 },
      { label: "what the state rests on", width: 470 },
    ],
    rows: statusRows,
    note: "States are PASS, FAIL, NOT RUN, BLOCKED or NOT APPLICABLE. There is deliberately no composite score: the states are not commensurable and averaging them would hide the BLOCKED row.",
  });

  const unitsTable = tableSection({
    columns: [
      { label: "unit declaration", width: 240, emphasis: true },
      { label: "value, verbatim from contract.json", width: 700 },
    ],
    rows: Object.entries(units).map(([k, v]) => [k, v]),
    note: `evidence_class: ${evidence}`,
  });

  const title = "F09 — how to check all of this without taking anyone's word for it";
  const subtitle = `Contract version ${req(contract, "contract_version", where)}, case ${req(contract, "case_id", where)}. Four stages from the pre-registered protocol to the export script, then every digest, then the verification state of each claim.`;
  const description = `Provenance chain for every number on this page, drawn as four labelled boxes left to right: the pre-registered protocol, the case source, the audited summary and the export script, each with its SHA-256 in short form, joined by arrows. Below the chain, a table of the four stage digests and the seven figure-data file digests in full, with the command shasum -a 256 that reproduces them. Below that, a verification status table of ten checks with the states PASS, BLOCKED, NOT RUN and NOT APPLICABLE and the evidence each state rests on, including the deliberate absence of the three NIST reference extracts and the absence of any hosted continuous-integration run, peer review, field validation or deployment. There is no composite score. Finally, the five unit declarations and the evidence class, verbatim from contract.json. ${extra}`;

  return {
    id: "f09",
    node: frame({
      title,
      subtitle,
      sections: [chain, hashTable, statusTable, unitsTable],
      notes: [
        "The reconciliation tolerance is a declared same-environment determinism target. The exporter and the audited run execute the same code on the same interpreter, so exact agreement is expected; the 1e-12 tolerance exists so that a cross-platform run reports a quantified disagreement rather than an unexplained failure. It was declared before the comparison was evaluated.",
        "Three NIST reference extracts are deliberately absent from this repository. As a direct consequence: 20 tests in tests/test_gas_properties.py skip with the message \"NIST reference extract not present\", cases/A2_pvt_independent_check/run.py exits 1 with a declared reference-table-absent status, and scripts/fetch_nist_reference.py --verify-only exits 1 reporting 3 files MISSING. scripts/fetch_nist_reference.py is the route by which a reader obtains the extracts.",
        "No hosted continuous-integration run, no journal peer review, no field validation and no deployment is claimed.",
        "The known-influx oracle tests the solve, not the formulation: it is an algebraic rearrangement of the same governing equation the generator solves, so an equation mis-transcribed identically in both would still close to 3.6e-11. An independent from-scratch reimplementation exists but is not a committed artifact of this repository.",
        "This renderer recomputed the SHA-256 of each figure-data file against contract.json before drawing anything, and refuses to emit if any digest disagrees.",
      ],
    }),
    title,
    description,
    meta: {
      figure_id: "F09",
      case_id: req(contract, "case_id", where),
      selector: "contract.json in full: numerical_source, export, units, evidence_class and the seven files entries",
      data_files: ["contract.json"],
      axes: { note: "no axes: this figure is a chain diagram and three semantic tables, with no quantitative encoding" },
      transformations: ["none: every value is rendered verbatim from contract.json, except the digest match column, which this renderer measured"],
      uncertainty: "none: this figure shows no uncertainty. It shows provenance and verification state.",
      question: "Are the numbers on this page the numbers in the repository, and how would I check without taking anyone's word for it?",
      caveat:
        "States are PASS, FAIL, NOT RUN, BLOCKED and NOT APPLICABLE, with no composite score. The reconciliation tolerance is a same-environment determinism target, not an independent reproduction.",
    },
  };
}

function figureConsumers(name) {
  const map = {
    f01_f02_scenarios: "F01, F01b, F02",
    f03_bias_sweep: "F03",
    f04_progressive: "F04",
    f05_holdout: "F05",
    f06_detection: "F06",
    f07_z_mismatch: "F07",
    f08_refinement: "F08",
  };
  if (!map[name]) throw new Error(`F09: contract lists an unknown figure_data "${name}"`);
  return map[name];
}

/* ---------- A1-01 ---------- */

function buildA1(summary) {
  const where = "A1-01";
  const block = req(summary, "diagnostic_d1_defect_sensitivity", where);
  const gate = fin(req(block, "gate_used_for_detection", where), `${where}: gate_used_for_detection`);
  const cases = req(block, "cases", where);
  if (!Array.isArray(cases) || cases.length !== 14) throw new Error(`${where}: expected 14 seeded cases, got ${cases?.length}`);
  const thresholds = req(block, "detection_thresholds", where);
  const description0 = req(block, "description", where);

  const rows = cases.map((c, i) => ({
    name: req(c, "name", where),
    klass: req(c, "defect_class", where),
    magnitude: req(c, "magnitude", where),
    err: Math.abs(fin(req(c, "recovery_relative_error", where), `${where}: cases[${i}].recovery_relative_error`)),
    signed: fin(c.recovery_relative_error, `${where}: cases[${i}].recovery_relative_error`),
    detected: req(c, "detected_at_A1_gate", where) === true,
  }));
  const order = ["none", "standard-volume basis", "reservoir temperature", "ordinate multiplicative", "abscissa multiplicative", "ordinate point-wise"];
  rows.sort((a, b) => order.indexOf(a.klass) - order.indexOf(b.klass) || a.err - b.err);
  const names = rows.map((r) => r.name);

  const nonZero = rows.filter((r) => r.err > 0);
  if (!nonZero.length) throw new Error(`${where}: no non-zero recovery errors, the figure would emit no marks`);
  const smallest = Math.min(...nonZero.map((r) => r.err));
  const floor = smallest / 400;
  const zeroPosition = smallest / 40;
  const ceil = Math.max(...nonZero.map((r) => r.err)) * 12;
  const a1Decades = [1e-18, 1e-16, 1e-14, 1e-12, 1e-10, 1e-8, 1e-6, 1e-4, 1e-2].filter(
    (v) => v >= floor && v <= ceil,
  );

  const plot = panel(
    {
      width: W,
      height: 34 * rows.length + 120,
      marginLeft: 330,
      marginRight: 200,
      marginTop: 26,
      marginBottom: 62,
      x: { type: "log", domain: [floor, ceil], axis: null },
      y: { domain: names, label: null },
      marks: [
        logAxis("x", a1Decades, {
          label: "|relative error in recovered gas in place| after the defect is seeded, log scale →",
          labelOffset: 46,
          format: expTick,
        }),
        grid("x", { ticks: a1Decades }),
        Plot.ruleX([gate], { stroke: C.ink, strokeDasharray: DASH.truth, strokeWidth: 1.4 }),
        Plot.text([{ x: gate, y: names[0] }], {
          x: "x",
          y: "y",
          text: () => `A1 detection gate, ${gate.toExponential(0)}`,
          fontSize: FS.label,
          fill: C.ink,
          textAnchor: "start",
          dx: 6,
          dy: -14,
        }),
        Plot.dot(nonZero, {
          x: "err",
          y: "name",
          r: 5.5,
          symbol: (d) => (d.detected ? "circle" : "square"),
          fill: (d) => (d.detected ? C.model : "none"),
          stroke: (d) => (d.detected ? C.model : C.context),
          strokeWidth: 1.8,
        }),
        Plot.dot(rows.filter((r) => r.err === 0).map((r) => ({ ...r, err: zeroPosition })), {
          x: "err",
          y: "name",
          r: 6,
          symbol: "times",
          stroke: C.context,
          strokeWidth: 2,
        }),
        Plot.text(rows, {
          x: (d) => (d.err === 0 ? zeroPosition : d.err),
          y: "name",
          text: (d) => (d.err === 0 ? "exactly 0" : `${d.signed >= 0 ? "+" : "−"}${Math.abs(d.signed).toExponential(2)} — ${d.detected ? "detected" : "not detected"}`),
          fontSize: FS.label,
          fill: (d) => (d.detected ? C.model : C.ink3),
          textAnchor: "start",
          dx: 12,
        }),
      ],
    },
    where,
  );

  const table = tableSection({
    columns: [
      { label: "defect class", width: 250, emphasis: true },
      { label: "detected at the A1 gate", width: 200 },
      { label: "what the sweep measured", width: 500 },
    ],
    rows: [
      [
        "standard-volume basis",
        req(thresholds.standard_volume_basis, "detected", where) ? "yes" : "no",
        req(thresholds.standard_volume_basis, "note", where),
      ],
      [
        "ordinate multiplicative",
        req(thresholds.ordinate_multiplicative, "detected", where) ? "yes" : "no",
        req(thresholds.ordinate_multiplicative, "note", where),
      ],
      [
        "abscissa multiplicative",
        req(thresholds.abscissa_multiplicative, "detected", where) ? "yes" : "no",
        `sensitivity dG/dbias = ${fin(thresholds.abscissa_multiplicative.sensitivity_dG_over_dbias, `${where}: sensitivity`).toFixed(12)}; minimum detectable relative bias ${thresholds.abscissa_multiplicative.minimum_detectable_relative_bias.toExponential(3)}`,
      ],
      [
        "ordinate point-wise",
        req(thresholds.ordinate_point_wise, "detected", where) ? "yes" : "no",
        `sensitivity ${fin(thresholds.ordinate_point_wise.sensitivity_relative_error_per_psia, `${where}: sensitivity`).toExponential(4)} relative error per psia; minimum detectable shift ${thresholds.ordinate_point_wise.minimum_detectable_shift_psia.toExponential(3)} psia`,
      ],
    ],
  });

  const title = "A1-01 — what the A1 recovery gate can and cannot see: a seeded-defect positive control";
  const subtitle = `Fourteen seeded defects against the experiment-1 arm of A1, whose uncorrupted recovery error is exactly 0.0. Detection is at the gate of ${gate.toExponential(0)} relative error. Four defect classes; two are invisible to this gate by construction.`;
  const description = `Horizontal dot plot of fourteen seeded defects against the A1 volumetric baseline, one row per defect, with the absolute relative error in recovered gas in place on a logarithmic horizontal axis. Five defects register exactly zero error — the uncorrupted baseline, the three standard-volume-basis corruptions at plus 50 percent, and the reservoir-temperature corruption at plus 40.6 percent — and are drawn at the axis floor with a cross marker and the label "exactly 0, not detected", because the standard group and the reservoir temperature cancel out of the balance. Two further ordinate-multiplicative defects, including scaling the ordinate by 1.5 and the analyst dividing by a deviation factor of 0.8 instead of 0.9, register 2.22e-16, which is machine epsilon and below the gate: a uniform rescaling of the ordinate does not move the x-intercept of a straight line. The defects the gate does catch are the abscissa-multiplicative ones, at 1.00e-3 and 1.00e-2, which pass through one for one, and the three single-point ordinate shifts of 0.01 psia, at 1.33e-6, 2.05e-7 and 1.74e-6. A vertical rule marks the detection gate at 5e-12. Detected defects are filled circles, undetected defects open squares, and every point carries its signed value and its detection state as a direct label.`;

  return {
    id: "a1-01",
    node: frame({
      title,
      subtitle,
      legend: [
        { label: "detected at the gate", color: C.model, dash: "hidden", symbol: "circle" },
        { label: "not detected", color: C.context, dash: "hidden", symbol: "open-square" },
        { label: "recovery error exactly 0, not detected — drawn at the axis floor", color: C.context, dash: "hidden", symbol: "times" },
        { label: `detection gate, ${gate.toExponential(0)}`, color: C.ink, dash: DASH.truth, symbol: "none" },
      ],
      sections: [plot, table],
      notes: [
        description0,
        "This is a positive control for the A1 recovery criterion and nothing more: it establishes which defect classes the criterion can see before any claim is made about what its passing means. Two classes — the standard-volume basis and a uniform rescaling of the ordinate — are invisible to it by construction, not by accident, and the notes column says why.",
        "Rows whose error is exactly 0 are drawn at the axis floor as a position, not a value. The logarithm of zero is never taken, nothing is clipped, and no epsilon is added.",
        "Source: cases/A1_volumetric_baseline/results/summary.json, /diagnostic_d1_defect_sensitivity. Synthetic throughout; the generator and the estimator share the volumetric assumption set.",
      ],
    }),
    title,
    description,
    meta: {
      figure_id: "A1-01",
      case_id: "A1_volumetric_baseline",
      selector: "cases/A1_volumetric_baseline/results/summary.json /diagnostic_d1_defect_sensitivity, 14 seeded cases and 4 detection-threshold blocks",
      data_files: ["cases/A1_volumetric_baseline/results/summary.json"],
      axes: {
        x: { quantity: "absolute relative error in recovered gas in place", unit: "dimensionless", scale: "log", domain: [floor, ceil] },
        y: { quantity: "seeded defect", unit: "categorical, 14 rows ordered by defect class", scale: "band" },
      },
      transformations: [
        "absolute value taken for the logarithmic position only; the signed value is printed as the direct label on every point",
        "rows whose error is exactly zero are positioned at the axis floor and labelled; not clipped, no epsilon added",
      ],
      uncertainty:
        "none: this figure shows no uncertainty. The recovery errors are deterministic, noise-free arithmetic; the only threshold drawn is the declared A1 detection gate.",
      question: "Which defects would the A1 recovery criterion actually have caught, and which are invisible to it?",
      caveat:
        "Post-hoc, not pre-registered and not gated, as the case summary states. It is a positive control for one criterion, not evidence about the physics.",
    },
  };
}

/* ---------- A3-01 ---------- */

function buildA3(summary) {
  const where = "A3-01";
  const results = req(summary, "results", where);
  const ranking = req(results, "E7_ranking", where);
  const byGroup = req(ranking, "rankings_by_assumed_sigma", where);
  const stable = req(ranking, "ranking_stable_under_sigma_factor_two", where);
  const convention = req(ranking, "combination_convention", where);
  const keys = Object.keys(byGroup);
  if (keys.length !== 3) throw new Error(`${where}: expected 3 assumed-sigma groups, got ${keys.length}`);

  const style = {
    0: { color: C.context, symbol: "square" },
    1: { color: C.observed, symbol: "circle" },
    2: { color: C.model, symbol: "diamond" },
  };
  const sigmaLabel = (k) => `${k.replace("sigma_", "").replace("_psia", "")} psia`;

  const points = [];
  keys.forEach((key, gi) => {
    const entries = byGroup[key];
    entries.forEach((entry, i) => {
      points.push({
        group: key,
        gi,
        source: req(entry, "source", where),
        v: fin(req(entry, "relative_effect", where), `${where}: ${key}[${i}].relative_effect`) * 100,
      });
    });
  });
  const reference = byGroup[keys[1]].map((e) => e.source);
  const maxV = Math.max(...points.map((p) => p.v));

  const plot = panel(
    {
      width: W,
      height: 400,
      marginLeft: 320,
      marginRight: 180,
      marginTop: 26,
      marginBottom: 60,
      x: { domain: [-0.08, maxV * 1.18], label: "relative effect on the fitted gas in place, percent →", labelAnchor: "center", labelOffset: 46 },
      y: { domain: reference, label: null },
      marks: [
        grid("x"),
        Plot.ruleX([0], { stroke: C.border, strokeWidth: 1.2 }),
        // Five of the six sources do not depend on the assumed sigma, so their three
        // markers land on exactly the same value. Drawn largest first they nest, and
        // all three stay visible instead of one hiding the other two.
        ...keys.map((key, gi) =>
          Plot.dot(points.filter((p) => p.group === key), {
            x: "v",
            y: "source",
            r: [9, 6.5, 4][gi],
            symbol: style[gi].symbol,
            fill: style[gi].color,
          }),
        ),
        Plot.text(points.filter((p) => p.gi === 1), {
          x: "v",
          y: "source",
          text: (d) => `${Math.abs(d.v) < 1e-6 ? d.v.toExponential(2) : d.v.toFixed(4)} percent at 45 psia`,
          fontSize: FS.label,
          fill: C.ink3,
          textAnchor: "start",
          dx: 18,
          dy: 0,
        }),
        Plot.text(points.filter((p) => p.source === reference[0]), {
          x: "v",
          y: "source",
          text: (d) => sigmaLabel(d.group),
          fontSize: FS.label,
          fill: (d) => style[d.gi].color,
          textAnchor: "middle",
          dy: -16,
        }),
      ],
    },
    where,
  );

  const table = tableSection({
    columns: [
      { label: "error source", width: 340, emphasis: true },
      { label: "rank at 22.5 psia", width: 200 },
      { label: "rank at 45 psia", width: 200 },
      { label: "rank at 90 psia", width: 200 },
    ],
    rows: reference.map((source) => [
      source,
      String(byGroup[keys[0]].findIndex((e) => e.source === source) + 1),
      String(byGroup[keys[1]].findIndex((e) => e.source === source) + 1),
      String(byGroup[keys[2]].findIndex((e) => e.source === source) + 1),
    ]),
    note: `ranking_stable_under_sigma_factor_two = ${stable}. The top two swap between the 22.5 psia and the 45 psia column, which is the whole finding: the ordering of the error budget is not a property of the reservoir, it is a property of the gauge accuracy you assume.`,
  });

  const title = "A3-01 — the error budget re-ranks itself when you change the assumed gauge accuracy";
  const subtitle = `Six error sources, ranked by their relative effect on the fitted gas in place, under three assumed pressure sigmas. Combination convention, from the case: ${convention}`;
  const description = `Horizontal dot plot of six error sources against their relative effect on the fitted gas in place, in percent, with three markers per row for the three assumed pressure standard deviations of 22.5, 45 and 90 psia. Only the random pressure scatter moves with the assumption: it runs ${points.filter((p) => p.source === "random pressure scatter, one sigma").map((p) => p.v.toFixed(4)).join(", ")} percent across the three assumptions, while the shared calibration bias of 25 psia stays at ${points.find((p) => p.source === "shared calibration bias, 25 psia").v.toFixed(4)} percent, psig supplied as psia at ${points.find((p) => p.source === "psig supplied as psia").v.toFixed(4)} percent, the deviation-factor correlation choice at ${points.find((p) => p.source === "deviation-factor correlation choice").v.toFixed(4)} percent, the standard-basis difference at ${points.find((p) => p.source === "standard basis 14.696 against 14.73").v.toFixed(4)} percent, and a uniform multiplicative Z error of 5 percent at effectively zero, ${points.find((p) => p.source.startsWith("uniform multiplicative Z")).v.toExponential(1)} percent, because a uniform rescaling of the ordinate leaves the x-intercept alone. At the smallest assumed sigma the shared calibration bias ranks first and the random scatter second; at the other two the order reverses. The accompanying table gives the rank of every source under each assumption.`;

  return {
    id: "a3-01",
    node: frame({
      title,
      subtitle,
      legend: keys.map((key, gi) => ({
        label: `assumed sigma ${sigmaLabel(key)}`,
        color: style[gi].color,
        dash: "hidden",
        symbol: style[gi].symbol === "diamond" ? "diamond" : style[gi].symbol,
      })),
      sections: [plot, table],
      notes: [
        "The case records this instability as a triggered inconclusive condition rather than as a finding about which error source is worst.",
        "Only one of the six sources depends on the assumed sigma. The other five are deterministic shifts, so the re-ranking is entirely a statement about where the random term lands relative to them.",
        "The uniform multiplicative Z error sits at the zero rule because its effect is 3.05e-16 relative, machine epsilon: rescaling the ordinate uniformly does not move the x-intercept of a straight line. It is plotted at its value on a linear axis, not hidden and not floored.",
        "Source: cases/A3_uncertainty_experiments/results/summary.json, /results/E7_ranking. Synthetic throughout: no field data, no simulator execution, no third-party dataset.",
      ],
    }),
    title,
    description,
    meta: {
      figure_id: "A3-01",
      case_id: "A3_uncertainty_experiments",
      selector: "cases/A3_uncertainty_experiments/results/summary.json /results/E7_ranking/rankings_by_assumed_sigma, 3 groups of 6 sources",
      data_files: ["cases/A3_uncertainty_experiments/results/summary.json"],
      axes: {
        x: { quantity: "relative effect on the fitted gas in place", unit: "percent", scale: "linear", domain: [-0.08, maxV * 1.18] },
        y: { quantity: "error source", unit: "categorical, 6 rows in the 45 psia order", scale: "band" },
      },
      transformations: ["relative effects multiplied by 100 to report percent; no other transformation"],
      uncertainty:
        "the figure is itself a sensitivity statement rather than an interval: the three marker shapes are three assumed values of the pressure standard deviation, and no distribution is placed over that assumption.",
      question: "Which measurement error dominates the inventory estimate, and does that ordering survive a change in the assumed gauge accuracy?",
      caveat:
        "The ranking is not stable under a factor of two in the assumed sigma. The combination convention is the case's own and is printed in the subtitle; the ordering is a property of the assumption, not of the reservoir.",
    },
  };
}

/* =====================================================================
 * 6. Emission, verification and the manifest.
 * ================================================================== */

const MARK_PATTERN = /<(path|circle|rect|line|polygon|ellipse)[\s>]/;

/** Pull the translation out of an SVG transform list, and say whether it also rotates. */
function readTransform(value) {
  if (!value) return { dx: 0, dy: 0, rotated: false };
  let dx = 0;
  let dy = 0;
  for (const [, a, b] of value.matchAll(/translate\(\s*(-?[\d.eE+]+)(?:[\s,]+(-?[\d.eE+]+))?\s*\)/g)) {
    dx += Number.parseFloat(a) || 0;
    dy += Number.parseFloat(b ?? "0") || 0;
  }
  return { dx, dy, rotated: /rotate\(/.test(value) };
}

/**
 * Refuse to emit a figure that paints text outside its own drawing.
 *
 * This is the build-time half of finding F7. The browser check that caught it measures
 * three real engines after the fact; this one measures here, names the figure and the
 * sentence, and stops the build, so a caveat can never be silently cropped in the
 * exported SVG, the PNG or the print sheet on the way to that check.
 *
 * Every label is judged against the box it belongs to: a mark inside a flattened panel
 * against that panel, everything else against the figure's canvas. Widths come from
 * measureText(), which is a deliberate over-estimate, so the check errs towards making a
 * line break early rather than towards letting one escape. Rotated text -- the vertical
 * axis titles -- is judged on the line height it occupies horizontally, which is the font
 * size, because that is what it actually covers.
 */
function assertTextInside(root, where) {
  const rootWidth = fin(Number.parseFloat(root.getAttribute("width")), `${where}: canvas width`);
  const offenders = [];

  const visit = (node, tx, inherited, clip) => {
    for (const child of Array.from(node.children ?? [])) {
      const tag = child.tagName?.toLowerCase();
      const moved = readTransform(child.getAttribute("transform"));
      const x = tx + moved.dx;
      const fontSize = Number.parseFloat(child.getAttribute("font-size") ?? "");
      const family = child.getAttribute("font-family");
      const style = {
        size: Number.isFinite(fontSize) ? fontSize : inherited.size,
        weight: Number.parseFloat(child.getAttribute("font-weight") ?? "") || inherited.weight,
        mono: family ? /mono|menlo|consolas|courier/i.test(family) : inherited.mono,
        anchor: child.getAttribute("text-anchor") ?? inherited.anchor,
        rotated: inherited.rotated || moved.rotated,
      };
      const box = VIEWPORT.get(child);
      const area = box ? { x0: x, x1: x + box.width } : clip;
      if (tag === "text") {
        const spans = Array.from(child.children ?? []).filter((c) => c.tagName?.toLowerCase() === "tspan");
        const baseX = Number.parseFloat(child.getAttribute("x") ?? "0") || 0;
        const lines = spans.length
          ? spans.map((s) => ({
              x: Number.parseFloat(s.getAttribute("x") ?? String(baseX)) || 0,
              text: s.textContent ?? "",
            }))
          : [{ x: baseX, text: child.textContent ?? "" }];
        for (const line of lines) {
          if (!line.text.trim().length) continue;
          const at = x + line.x;
          const painted = measureText(line.text, style.size, style);
          const [left, right] = style.rotated
            ? [at - style.size, at + style.size]
            : style.anchor === "end"
              ? [at - painted, at]
              : style.anchor === "middle"
                ? [at - painted / 2, at + painted / 2]
                : [at, at + painted];
          if (left < area.x0 - 0.5 || right > area.x1 + 0.5) {
            offenders.push(
              `"${line.text.slice(0, 60)}" spans ${left.toFixed(1)}..${right.toFixed(1)} ` +
                `in a drawing area of ${area.x0.toFixed(1)}..${area.x1.toFixed(1)}`,
            );
          }
        }
      } else visit(child, x, style, area);
    }
  };

  visit(
    root,
    0,
    { size: FS.base, weight: 400, mono: false, anchor: "start", rotated: false },
    { x0: 0, x1: rootWidth },
  );
  if (offenders.length) {
    throw new Error(
      `${where}: ${offenders.length} label(s) fall outside the drawing that contains them. ` +
        "Wrap them to the room that exists, move the anchor, or widen the panel; do not crop " +
        `the text.\n  ${offenders.join("\n  ")}`,
    );
  }
}

async function sha256(path) {
  return createHash("sha256").update(await readFile(path)).digest("hex");
}

async function emitPng(id, svgText) {
  const { default: sharp } = await import("sharp");
  const path = join(OUT_DIR, `${id}.png`);
  const buffer = await sharp(Buffer.from(svgText), { density: 216 }).png({ compressionLevel: 9 }).toBuffer();
  await writeFile(path, buffer);
  return { path, bytes: buffer.length, scale: "216 dpi, 3x the 72 dpi authoring scale" };
}

async function main() {
  const contract = JSON.parse(await readFile(join(DATA_DIR, "contract.json"), "utf8"));

  // Fail closed on provenance before anything is drawn.
  const digests = [];
  for (const entry of contract.files) {
    const path = join(DATA_DIR, entry.path);
    const measured = await sha256(path);
    const match = measured === entry.sha256;
    digests.push({ file: entry.path, declared: entry.sha256, measured, match });
    if (!match) {
      throw new Error(
        `provenance: ${entry.path} has SHA-256 ${measured}, contract.json declares ${entry.sha256}`,
      );
    }
  }

  const scenarios = await loadData("f01_f02_scenarios");
  const biasSweep = await loadData("f03_bias_sweep");
  const progressive = await loadData("f04_progressive");
  const holdout = await loadData("f05_holdout");
  const detection = await loadData("f06_detection");
  const zMismatch = await loadData("f07_z_mismatch");
  const refinement = await loadData("f08_refinement");

  const a1Path = join(REPO_ROOT, "cases", "A1_volumetric_baseline", "results", "summary.json");
  const a3Path = join(REPO_ROOT, "cases", "A3_uncertainty_experiments", "results", "summary.json");
  const a1Summary = JSON.parse(await readFile(a1Path, "utf8"));
  const a3Summary = JSON.parse(await readFile(a3Path, "utf8"));

  const figures = [
    buildF01(scenarios),
    buildF01(scenarios, { observedRangeOnly: true }),
    buildF02(scenarios),
    buildF03(biasSweep),
    buildF04(progressive),
    buildF05(holdout),
    buildF06(detection),
    buildF07(zMismatch),
    buildF08(refinement),
    buildF09(contract, digests, "Every figure-data digest in the table was recomputed by the renderer at build time and matched."),
    buildA1(a1Summary),
    buildA3(a3Summary),
  ];

  await mkdir(OUT_DIR, { recursive: true });
  const rendererDigest = createHash("sha256")
    .update(await readFile(join(HERE, "render-figures.mjs")))
    .digest("hex");

  const pngOutcomes = [];
  const records = [];
  for (const figure of figures) {
    assertTextInside(figure.node, figure.meta.figure_id);
    const svgText = serialise(figure.node, { title: figure.title, description: figure.description });
    if (!MARK_PATTERN.test(svgText)) {
      throw new Error(`${figure.meta.figure_id}: emitted no marks (no path, circle, rect, line, polygon or ellipse)`);
    }
    if (svgText.includes("NaN")) {
      throw new Error(`${figure.meta.figure_id}: the emitted SVG contains the string NaN`);
    }
    if (svgText.includes("Infinity")) {
      throw new Error(`${figure.meta.figure_id}: the emitted SVG contains the string Infinity`);
    }
    if (!svgText.includes("<desc")) {
      throw new Error(`${figure.meta.figure_id}: the emitted SVG has no long description`);
    }
    const emitted = await emit(figure.id, svgText);
    const files = [
      { path: `${figure.id}.svg`, bytes: emitted.bytes, media_type: "image/svg+xml" },
    ];
    let png = { state: "BLOCKED", reason: null };
    try {
      const raster = await emitPng(figure.id, svgText);
      files.push({ path: `${figure.id}.png`, bytes: raster.bytes, media_type: "image/png", raster: raster.scale });
      png = { state: "emitted", rasteriser: "sharp (libvips + librsvg), imported dynamically" };
    } catch (error) {
      png = { state: "BLOCKED", reason: error.message };
    }
    pngOutcomes.push({ figure: figure.meta.figure_id, ...png });
    records.push({
      ...figure.meta,
      evidence_class: contract.evidence_class,
      units: contract.units,
      standard_conditions: contract.units.standard_conditions,
      numerical_run_id: contract.numerical_source.baseline_summary_sha256,
      numerical_run_id_basis:
        "the audited summary digest identifies the run; contract.json declares no separate run identifier and none is invented here",
      numerical_source_digests: {
        protocol_sha256: contract.numerical_source.protocol_sha256,
        case_source_sha256: contract.numerical_source.case_source_sha256,
        baseline_summary_sha256: contract.numerical_source.baseline_summary_sha256,
        baseline_summary_path: contract.numerical_source.baseline_summary_path,
      },
      export_code_revision: {
        exporter_path: contract.export.exporter_path,
        exporter_sha256: contract.export.exporter_sha256,
        reconciliation_checks_passed: contract.export.reconciliation_checks_passed,
        reconcile_relative_tolerance: contract.export.reconcile_relative_tolerance,
      },
      exported_data_hashes: figure.meta.data_files.map((name) => {
        const entry = digests.find((d) => d.file === name);
        if (entry) return { path: `site/src/data/figures/${name}`, sha256: entry.measured, matches_contract: entry.match };
        if (name === "contract.json") {
          return { path: "site/src/data/figures/contract.json", sha256: contractDigest, matches_contract: null };
        }
        if (name.startsWith("cases/")) {
          return { path: name, sha256: caseDigests[name], matches_contract: null, note: "committed case summary, outside the export contract" };
        }
        throw new Error(`manifest: no digest for data file ${name}`);
      }),
      accessibility: {
        role: "img",
        accessible_name: figure.title,
        long_description_chars: figure.description.length,
        non_colour_channels:
          "every series carries a dash pattern, a marker shape or a direct text label, and each figure's legend repeats them. Only two marks sit below 3:1 on the plot ground: the axis gridlines and the band fills, both aria-hidden, both of which passed a removal test -- every band boundary is also drawn in --c-border-strong at 3.51:1 and labelled in text, so the shading is redundant reinforcement. Every other rule, including the divider above the caveat lines, the separator between table rows and the boundary of a legend band swatch, carries information and is drawn at 3.51:1. The classification is recorded in docs/design/figure_spec.md.",
        minimum_label_px: TEXT_MIN_PX,
        colour_source: "docs/design/tokens.css, parsed at build time; no colour value is retyped in the renderer",
      },
      public_data_decision:
        "public. Every value is synthetic and already committed to this repository; there is no field, proprietary or personal data in the source, and the known inventory is evaluation-only information that exists because the history was generated.",
      png_status: png,
      files,
    });
  }

  const pngStatus = {
    emitted: pngOutcomes.filter((p) => p.state === "emitted").map((p) => p.figure),
    blocked: pngOutcomes.filter((p) => p.state !== "emitted"),
    rasteriser: "sharp 0.35.4 (libvips 8.18.6, librsvg 2.62.91), imported dynamically",
    caveat:
      "sharp is present as a transitive dependency of astro and is NOT declared in site/package.json. PNG emission is best-effort and never fails the build: if the import or the raster fails, the SVG still ships and the per-figure png_status records the reason. Text in the raster is set by the rasteriser's fontconfig, not by the reader's system font stack, so the PNG is a shareable export and the SVG is the authoritative artefact.",
  };

  const manifest = {
    manifest_version: "1.0.0",
    generated: {
      renderer: "site/scripts/render-figures.mjs",
      renderer_sha256: rendererDigest,
      note: "the renderer digest is the SITE BUILD revision and is distinct from the numerical-source digests below, which identify the run that produced the numbers",
    },
    site_build: {
      plot: "@observablehq/plot 0.6.17",
      dom: "linkedom 0.18.13",
      node: process.version,
      authoring_width_px: W,
      text_floor_px: TEXT_MIN_PX,
      png_status: pngStatus,
    },
    numerical_source: contract.numerical_source,
    export: contract.export,
    units: contract.units,
    evidence_class: contract.evidence_class,
    contract_version: contract.contract_version,
    case_id: contract.case_id,
    data_file_digests: digests,
    case_summary_digests: caseDigests,
    figures: records,
  };
  const manifestPath = join(OUT_DIR, "manifest.json");
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");

  const report = records.map((r) => ({
    figure: r.figure_id,
    files: r.files.map((f) => `${f.path} ${f.bytes} B`).join(", "),
  }));
  for (const line of report) console.log(`${line.figure.padEnd(6)} ${line.files}`);
  console.log(`manifest.json ${Buffer.byteLength(JSON.stringify(manifest, null, 2) + "\n")} B`);
  console.log(
    `${records.length} figures; PNG emitted for ${pngStatus.emitted.length}, blocked for ${pngStatus.blocked.length}`,
  );
  for (const blocked of pngStatus.blocked) console.log(`  PNG BLOCKED ${blocked.figure}: ${blocked.reason}`);
}

let contractDigest = null;
const caseDigests = {};

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
if (isMain) {
  contractDigest = await sha256(join(DATA_DIR, "contract.json"));
  caseDigests["cases/A1_volumetric_baseline/results/summary.json"] = await sha256(
    join(REPO_ROOT, "cases", "A1_volumetric_baseline", "results", "summary.json"),
  );
  caseDigests["cases/A3_uncertainty_experiments/results/summary.json"] = await sha256(
    join(REPO_ROOT, "cases", "A3_uncertainty_experiments", "results", "summary.json"),
  );
  await main();
}
