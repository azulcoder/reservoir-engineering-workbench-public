/**
 * Build-time SVG for the scenario explorer's three panels.
 *
 * What these panels are, and what they are not
 * -------------------------------------------
 * F01, F01b and F02 as the case publishes them are drawn by
 * `site/scripts/render-figures.mjs`, recorded in the generated manifest with their byte
 * counts and digests, and inlined on the case page under "Evidence". Those are the
 * case's exhibits and they show the base case, J = 2.0 bbl/day/psi.
 *
 * The explorer needs the same three views for each of the other seven computed cases, and
 * the case does not publish those. So they are drawn here instead, at build time, from the
 * same committed export, and they are labelled on the page as what they are: a view this
 * site draws, not an audited exhibit. Every panel is real markup in the delivered HTML —
 * there is no client-side charting, no canvas and no runtime data fetch — so switching
 * cases reveals markup that was already there rather than computing a picture in the
 * browser.
 *
 * Two deliberate constraints follow from what the case is about.
 *
 *  - The axes of panel 1 and panel 3 do not move between cases. A reader comparing J = 2
 *    with J = 60 is comparing pictures on one scale; an axis that rescaled itself per case
 *    would flatten every case into the same-looking chart, which is the exact misreading
 *    this case exists to refute. Panel 2 is the truncated view and its axis is per case by
 *    definition, which is why it says so in its own subtitle.
 *  - Colour is never the only channel. Observed is solid with round markers, the fit is
 *    long-dashed, the extrapolation is the same dash at half stroke, the truth is a fine
 *    dotted rule with a diamond. Colours come from `docs/design/tokens.css` through CSS
 *    custom properties, so no colour value is retyped here either.
 */

import type { Scenario } from "./scenarios";

const W = 660;
const H = 300;
const M = { top: 34, right: 18, bottom: 54, left: 74 };
const IW = W - M.left - M.right;
const IH = H - M.top - M.bottom;

/** Fixed across all eight cases: see the note above. */
const X_MAX = 185;
const X_MIN = -3;
const PZ_MAX = 4650;

const FS = 13;
/** Vertical step between wrapped subtitle lines, in the panel's own units. */
const SUBTITLE_LEADING = 15;

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function r2(n: number): string {
  const v = Math.round(n * 100) / 100;
  return Object.is(v, -0) ? "0" : String(v);
}

interface Scale {
  (v: number): number;
}

function linear(d0: number, d1: number, r0: number, r1: number): Scale {
  const m = (r1 - r0) / (d1 - d0);
  return (v: number) => r0 + (v - d0) * m;
}

/** Tick values at a round step covering [lo, hi]. */
function ticks(lo: number, hi: number, target: number): number[] {
  const span = hi - lo;
  const raw = span / target;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag;
  const out: number[] = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi + step * 1e-9; t += step) {
    out.push(Math.abs(t) < step * 1e-9 ? 0 : t);
  }
  return out;
}

function tickLabel(v: number): string {
  if (Number.isInteger(v)) return String(v);
  return String(Number(v.toFixed(2)));
}

function path(xs: number[], ys: number[], x: Scale, y: Scale): string {
  return xs.map((v, i) => `${i === 0 ? "M" : "L"}${r2(x(v))} ${r2(y(ys[i] as number))}`).join("");
}

interface Axis {
  x: Scale;
  y: Scale;
  xTicks: number[];
  yTicks: number[];
  xLabel: string;
  yLabel: string;
}

function frame(a: Axis): string {
  const parts: string[] = [];
  // Gridlines and the plot ground are information-free and are hidden from assistive
  // technology, per docs/design/decisions.md D13.
  parts.push(
    `<g aria-hidden="true">` +
      `<rect x="${M.left}" y="${M.top}" width="${IW}" height="${IH}" fill="var(--c-plot-bg)"/>` +
      a.yTicks
        .map(
          (t) =>
            `<line x1="${M.left}" x2="${M.left + IW}" y1="${r2(a.y(t))}" y2="${r2(a.y(t))}" stroke="var(--c-gridline)" stroke-width="1"/>`,
        )
        .join("") +
      a.xTicks
        .map(
          (t) =>
            `<line y1="${M.top}" y2="${M.top + IH}" x1="${r2(a.x(t))}" x2="${r2(a.x(t))}" stroke="var(--c-gridline)" stroke-width="1"/>`,
        )
        .join("") +
      `</g>`,
  );
  parts.push(
    `<line x1="${M.left}" x2="${M.left + IW}" y1="${M.top + IH}" y2="${M.top + IH}" stroke="var(--c-border-strong)" stroke-width="1.25"/>` +
      `<line x1="${M.left}" x2="${M.left}" y1="${M.top}" y2="${M.top + IH}" stroke="var(--c-border-strong)" stroke-width="1.25"/>`,
  );
  parts.push(
    a.xTicks
      .map(
        (t) =>
          `<text x="${r2(a.x(t))}" y="${M.top + IH + 18}" text-anchor="middle" font-size="${FS}" fill="var(--c-ink-2)">${tickLabel(t)}</text>`,
      )
      .join(""),
  );
  parts.push(
    a.yTicks
      .map(
        (t) =>
          `<text x="${M.left - 8}" y="${r2(a.y(t) + 4)}" text-anchor="end" font-size="${FS}" fill="var(--c-ink-2)">${tickLabel(t)}</text>`,
      )
      .join(""),
  );
  parts.push(
    `<text x="${M.left + IW / 2}" y="${H - 10}" text-anchor="middle" font-size="${FS}" fill="var(--c-ink-2)">${esc(a.xLabel)}</text>`,
  );
  parts.push(
    `<text x="14" y="${M.top + IH / 2}" text-anchor="middle" font-size="${FS}" fill="var(--c-ink-2)" transform="rotate(-90 14 ${M.top + IH / 2})">${esc(a.yLabel)}</text>`,
  );
  return parts.join("");
}

function markers(xs: number[], ys: number[], x: Scale, y: Scale, every: number): string {
  const out: string[] = [];
  for (let i = 0; i < xs.length; i += every) {
    out.push(
      `<circle cx="${r2(x(xs[i] as number))}" cy="${r2(y(ys[i] as number))}" r="2.6" fill="var(--c-series-observed)"/>`,
    );
  }
  return `<g aria-hidden="true">${out.join("")}</g>`;
}


/**
 * Split a line of panel text so it fits a given pixel width.
 *
 * This module emits SVG as a string, with no layout engine, so the advance has to be
 * estimated. 0.52 em per character is a conservative average for the system sans stack at
 * weight 400-600 -- conservative in the direction that matters, because overestimating wraps
 * a line early while underestimating paints text off the panel. That is what happened to the
 * observed-range panel's subtitle, which ran 81 to 85 CSS px past the edge on every engine.
 *
 * Nothing is truncated. A qualification that does not fit gets another line, and the caller
 * grows the panel to hold it.
 */
function wrapText(text: string, maxPx: number, fontPx: number): string[] {
  const perChar = 0.52 * fontPx;
  const budget = Math.max(8, Math.floor(maxPx / perChar));
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let line = "";
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (candidate.length <= budget || !line) {
      line = candidate;
    } else {
      lines.push(line);
      line = word;
    }
  }
  if (line) lines.push(line);
  return lines;
}

function wrap(id: string, title: string, subtitle: string, body: string, desc: string): string {
  const subtitleLines = wrapText(subtitle, W - M.left - M.right, FS);
  // One subtitle line fits the existing top margin. A second or third makes the panel taller,
  // which is cheaper than losing a sentence that tells the reader how to read the axis.
  const extra = Math.max(0, subtitleLines.length - 1) * SUBTITLE_LEADING;
  const height = H + extra;
  const subtitleText = subtitleLines
    .map(
      (line, index) =>
        `<text x="${M.left}" y="${M.top - 6 + index * SUBTITLE_LEADING}" font-size="${FS}" ` +
        `fill="var(--c-ink-2)">${esc(line)}</text>`,
    )
    .join("");
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${height}" width="${W}" height="${height}" ` +
    `role="img" aria-labelledby="${id}-t" aria-describedby="${id}-d">` +
    `<title id="${id}-t">${esc(title)}</title>` +
    `<desc id="${id}-d">${esc(desc)}</desc>` +
    `<rect x="0" y="0" width="${W}" height="${height}" fill="var(--c-surface)"/>` +
    `<text x="${M.left}" y="16" font-size="${FS}" font-weight="600" fill="var(--c-ink)">${esc(title)}</text>` +
    subtitleText +
    `<g transform="translate(0 ${extra})">${body}</g>` +
    `</svg>`
  );
}

/* ------------------------------------------------------------------ *
 * Panel 1 — the F01 view: p/Z, the fit, and where it extrapolates to
 * ------------------------------------------------------------------ */

export function panelIntercept(s: Scenario): string {
  const x = linear(X_MIN, X_MAX, M.left, M.left + IW);
  const y = linear(0, PZ_MAX, M.top + IH, M.top);
  const a: Axis = {
    x,
    y,
    xTicks: ticks(0, X_MAX, 6),
    yTicks: ticks(0, PZ_MAX, 5),
    xLabel: "cumulative gas produced, Bscf",
    yLabel: "p/Z, psia",
  };

  const intercept = s.fittedBscf;
  const a0 = s.pz[0] as number;
  // The fitted line is evaluated from its own endpoints in p/Z space, not by extending a
  // drawn path: at G_p = 0 it is the fitted value there, and at the x-intercept it is zero.
  const fit0 = s.fittedPz[0] as number;
  const observedEnd = s.observedExtentBscf;
  const fitAtEnd = s.fittedPz[s.fittedPz.length - 1] as number;

  const body =
    frame(a) +
    // extrapolation: the same dash at half stroke, beyond the last observation
    `<line x1="${r2(x(observedEnd))}" y1="${r2(y(fitAtEnd))}" x2="${r2(x(intercept))}" y2="${r2(y(0))}" ` +
    `stroke="var(--c-series-model)" stroke-width="1.25" stroke-dasharray="10 5" stroke-linecap="round"/>` +
    // fitted line over the observed interval
    `<line x1="${r2(x(0))}" y1="${r2(y(fit0))}" x2="${r2(x(observedEnd))}" y2="${r2(y(fitAtEnd))}" ` +
    `stroke="var(--c-series-model)" stroke-width="2.5" stroke-dasharray="10 5"/>` +
    // observed
    `<path d="${path(s.gBscf, s.pz, x, y)}" fill="none" stroke="var(--c-series-observed)" stroke-width="2"/>` +
    markers(s.gBscf, s.pz, x, y, 6) +
    // truth
    `<line x1="${r2(x(s.trueBscf))}" x2="${r2(x(s.trueBscf))}" y1="${M.top}" y2="${M.top + IH}" ` +
    `stroke="var(--c-series-truth)" stroke-width="1.5" stroke-dasharray="2 3"/>` +
    `<path d="M${r2(x(s.trueBscf))} ${M.top + 4}l6 6-6 6-6-6z" fill="var(--c-series-truth)"/>` +
    `<text x="${r2(x(s.trueBscf) + 10)}" y="${M.top + 14}" font-size="${FS}" fill="var(--c-ink-2)">true G ${s.trueBscf.toFixed(1)}</text>` +
    `<text x="${r2(Math.min(x(intercept) + 8, W - 150))}" y="${r2(y(0) - 8)}" font-size="${FS}" fill="var(--c-ink-2)">fitted intercept ${s.fittedBscf.toFixed(2)}</text>`;

  const desc =
    `p/Z against cumulative gas produced for the case with aquifer productivity index ` +
    `J = ${s.key} bbl/day/psi. ${s.observations} observed points run from ${a0.toFixed(1)} psia at zero ` +
    `cumulative gas to ${(s.pz[s.pz.length - 1] as number).toFixed(1)} psia at ${observedEnd.toFixed(1)} Bscf, which is where ` +
    `observation stops. The volumetric straight-line fit is extrapolated to the horizontal axis and ` +
    `crosses it at ${s.fittedBscf.toFixed(2)} Bscf against a true ${s.trueBscf.toFixed(1)} Bscf. R-squared is ` +
    `${s.rSquared.toFixed(6)}. The horizontal axis runs to ${X_MAX} Bscf and the vertical axis includes zero, ` +
    `on the same scale for every case. Full values in the data table below.`;

  return wrap(
    `xp-a-${s.slug}`,
    `p/Z and the inventory the fit extrapolates to — J = ${s.key}`,
    `R-squared ${s.rSquared.toFixed(6)}; intercept ${s.fittedBscf.toFixed(2)} Bscf against a true ${s.trueBscf.toFixed(1)} Bscf.`,
    body,
    desc,
  );
}

/* ------------------------------------------------------------------ *
 * Panel 2 — the F01b view: the observed interval only
 * ------------------------------------------------------------------ */

export function panelObserved(s: Scenario): string {
  const lo = Math.min(...s.pz, ...s.fittedPz);
  const hi = Math.max(...s.pz, ...s.fittedPz);
  const pad = (hi - lo) * 0.08;
  const y = linear(lo - pad, hi + pad, M.top + IH, M.top);
  const xMax = Math.ceil(s.observedExtentBscf / 5) * 5;
  const x = linear(0, xMax, M.left, M.left + IW);
  const a: Axis = {
    x,
    y,
    xTicks: ticks(0, xMax, 6),
    yTicks: ticks(lo - pad, hi + pad, 5),
    xLabel: "cumulative gas produced, Bscf",
    yLabel: "p/Z, psia",
  };

  const body =
    frame(a) +
    `<path d="${path(s.gBscf, s.fittedPz, x, y)}" fill="none" stroke="var(--c-series-model)" stroke-width="2.5" stroke-dasharray="10 5"/>` +
    `<path d="${path(s.gBscf, s.pz, x, y)}" fill="none" stroke="var(--c-series-observed)" stroke-width="2"/>` +
    markers(s.gBscf, s.pz, x, y, 3);

  const desc =
    `The same fit as the previous panel over the observed interval only, for J = ${s.key} bbl/day/psi. ` +
    `The vertical axis is truncated to the observed range, roughly ${(lo - pad).toFixed(0)} to ${(hi + pad).toFixed(0)} psia, ` +
    `so that departures of a few psia between the observations and the fit are visible. The largest ` +
    `residual is ${s.residualMaxAbs.toFixed(2)} psia. The vertical axis does not include zero, so the ` +
    `intercept geometry must be read from the previous panel and not from this one.`;

  return wrap(
    `xp-b-${s.slug}`,
    `The same fit over the observed interval only — J = ${s.key}`,
    `Vertical axis truncated to the observed range, and rescaled per case. Read the intercept from the panel above.`,
    body,
    desc,
  );
}

/* ------------------------------------------------------------------ *
 * Panel 3 — the F02 view: residuals against the judgement band
 * ------------------------------------------------------------------ */

export function panelResiduals(s: Scenario, allMaxAbs: number): string {
  const bound = Math.max(55, Math.ceil((allMaxAbs * 1.08) / 10) * 10);
  const y = linear(-bound, bound, M.top + IH, M.top);
  const xMax = Math.ceil(s.observedExtentBscf / 5) * 5;
  const x = linear(0, xMax, M.left, M.left + IW);
  const a: Axis = {
    x,
    y,
    xTicks: ticks(0, xMax, 6),
    yTicks: ticks(-bound, bound, 5),
    xLabel: "cumulative gas produced, Bscf",
    yLabel: "observed minus fitted p/Z, psia",
  };

  const band =
    `<g aria-hidden="true">` +
    `<rect x="${M.left}" y="${r2(y(50))}" width="${IW}" height="${r2(y(10) - y(50))}" fill="var(--c-band-neutral)"/>` +
    `<rect x="${M.left}" y="${r2(y(-10))}" width="${IW}" height="${r2(y(-50) - y(-10))}" fill="var(--c-band-neutral)"/>` +
    `</g>`;

  const body =
    frame(a) +
    band +
    `<line x1="${M.left}" x2="${M.left + IW}" y1="${r2(y(0))}" y2="${r2(y(0))}" stroke="var(--c-border-strong)" stroke-width="1.25"/>` +
    `<path d="${path(s.gBscf, s.residual, x, y)}" fill="none" stroke="var(--c-series-observed)" stroke-width="2"/>` +
    markers(s.gBscf, s.residual, x, y, 3) +
    `<text x="${M.left + 8}" y="${r2(y(50) - 6)}" font-size="${FS}" fill="var(--c-ink-2)">10 to 50 psia: the band this case takes as realistic average-pressure error</text>`;

  const desc =
    `All ${s.observations} observation-minus-fit residuals in psia of p/Z against cumulative gas, for ` +
    `J = ${s.key} bbl/day/psi. They run from ${s.residualMin.toFixed(2)} to ${s.residualMax.toFixed(2)} psia with ` +
    `a root-mean-square of ${s.residualRms.toFixed(2)} psia, and they sweep rather than scatter. Two shaded ` +
    `bands mark plus and minus 10 to 50 psia, the range this case takes as the realistic error on a ` +
    `volume-averaged reservoir pressure; that band is the case author's judgement and not a retrieved figure. ` +
    `The vertical axis is plus or minus ${bound} psia for every case.`;

  return wrap(
    `xp-c-${s.slug}`,
    `Residuals of that fit — J = ${s.key}`,
    `RMS ${s.residualRms.toFixed(2)} psia, largest excursion ${s.residualMaxAbs.toFixed(2)} psia. Residuals are not uncertainty bars.`,
    body,
    desc,
  );
}

/** All three panels for one case. */
export function panelsFor(s: Scenario, allMaxAbs: number): {
  intercept: string;
  observed: string;
  residuals: string;
} {
  return {
    intercept: panelIntercept(s),
    observed: panelObserved(s),
    residuals: panelResiduals(s, allMaxAbs),
  };
}
