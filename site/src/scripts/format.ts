/**
 * Display precision for public numerical values.
 *
 * The rule this file implements, in one sentence: a published number carries the digits
 * its engineering meaning, its experimental resolution and its cross-platform stability
 * justify, and no more. Raw scientific output is unchanged; only its presentation is
 * decided here.
 *
 * There is deliberately no single global decimal rule. A permeability-thickness, a skin,
 * an R-squared and a relative error are physically different quantities with different
 * resolutions, and rounding them alike would be a formatting convention masquerading as a
 * measurement claim. Each helper below states what justifies its digits.
 *
 * The measured basis for the stability half of the rule is in the B1 case report section
 * 10 and in docs/release/portability_envelope.json: across macOS arm64 and the canonical
 * Linux container, every quantity this site publishes is bit-identical, and the worst
 * difference anywhere in B1's 1100 compared values is 1.11e-10 relative. Nine significant
 * figures are therefore stable; the reason most values below use far fewer is engineering
 * meaning, not instability.
 */

/** Permeability-thickness, md·ft. Reported to 1 decimal: the recovery is exact to ~6
 *  significant figures, but no well test resolves kh better than a few percent, so extra
 *  digits describe the arithmetic rather than the reservoir. */
export function kh(value: number): string {
  return value.toFixed(1);
}

/** Permeability, md. Same reasoning as kh. */
export function permeability(value: number): string {
  return value.toFixed(1);
}

/** Total skin, dimensionless. Two decimals: skin is read off an intercept and a tenth is
 *  already below what a real gauge and a real rate history support. */
export function skin(value: number): string {
  return value.toFixed(2);
}

/** Gas volumes in Bscf. One decimal: the A4 comparison turns on 12.5 Bscf out of 100. */
export function bscf(value: number): string {
  return value.toFixed(1);
}

/** R-squared. Six decimals, because the whole point of the A4 and B1 findings is that
 *  this statistic stays indistinguishable from 1 while the answer is wrong; rounding it
 *  to 2 decimals would delete the evidence. */
export function rSquared(value: number): string {
  return value.toFixed(6);
}

/** A relative error shown as a percentage. One decimal by default. */
export function percent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)} percent`;
}

/** A small relative error, shown in scientific notation with two significant digits.
 *  Used where the magnitude is the message and the mantissa is not. */
export function small(value: number): string {
  const [mantissa, exponent] = value.toExponential(1).split("e");
  const power = Number(exponent);
  return `${mantissa}×10${superscript(power)}`;
}

/** Unicode superscript for an integer exponent, so scientific notation reads as
 *  scientific notation rather than as programming syntax. */
function superscript(power: number): string {
  const digits: Record<string, string> = {
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
    "-": "⁻",
  };
  return String(power)
    .split("")
    .map((c) => digits[c] ?? c)
    .join("");
}

/** An elapsed duration in hours, to three significant figures and never in scientific
 *  notation.
 *
 *  `toPrecision(3)` switches to exponential above 999, so a column of test durations read
 *  31.6, 398, 1.26e+3, 4.47e+3 on the live site -- three significant figures throughout and
 *  two different notations inside one column. Hours are a quantity a reader compares by
 *  scanning, so the notation has to stay still. Above 999 the third significant figure is
 *  already past what the measurement carries, and this rounds to a whole hour there. */
export function hours(value: number): string {
  if (!Number.isFinite(value)) throw new Error(`hours(): not a finite number: ${value}`);
  return value >= 999.5 ? Math.round(value).toString() : value.toPrecision(3);
}

/** A count out of a total, e.g. "5 of 10". Both are integers; no formatting decision. */
export function outOf(count: number, total: number): string {
  return `${count} of ${total}`;
}
