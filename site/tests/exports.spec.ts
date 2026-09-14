/**
 * Check 11 -- what an exported figure carries once it leaves the page, plus the integrity
 * of every published download, and the two states from check 7 that are not the explorer:
 * the unavailable-reference page and long labels.
 *
 * The test that matters most here is the last kind: the downloadable SVG is asserted to be
 * byte-identical to the SVG the page inlines. `public/data/index.json` claims exactly that
 * of every exhibit copy -- "byte-identical to the file the page inlines" -- and the build
 * verifies each download against its recorded digest but never against the figure it is a
 * copy of, so the two can drift with nothing failing. This file closes that gap from the
 * outside.
 */
import { test, expect } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { url } from "./support";

const FIGURES = [
  "f01",
  "f01b-observed-range",
  "f02",
  "f03",
  "f04",
  "f05",
  "f06",
  "f07",
  "f08",
  "f09",
  "a1-01",
  "a3-01",
];

/** Text content of an SVG, in document order, whitespace collapsed. */
function svgText(svg: string): string {
  return (svg.match(/>([^<>]+)</g) ?? [])
    .map((m) => m.slice(1, -1))
    .join(" ")
    .replace(/\s+/g, " ");
}

test.describe("exported figures", () => {
  for (const id of FIGURES) {
    test(`${id}.svg carries its title, units, legend and caveat`, async ({ request }) => {
      const res = await request.get(url(`/data/figures/${id}.svg`));
      expect(res.status()).toBe(200);
      const svg = await res.text();
      const text = svgText(svg);

      /* It is a standalone document: namespace, its own accessible name, its own long
         description. A stripped chart fragment would have none of these. */
      expect(svg).toContain('xmlns="http://www.w3.org/2000/svg"');
      expect(svg).toMatch(/role="img"/);
      const label = svg.match(/aria-label="([^"]+)"/)?.[1] ?? "";
      expect(label.length, `${id} accessible name`).toBeGreaterThan(20);
      const desc = svg.match(/<desc[^>]*>([\s\S]*?)<\/desc>/)?.[1] ?? "";
      expect(desc.length, `${id} long description`).toBeGreaterThan(120);

      /* The figure number is drawn on the image, not only in the attribute, so a
         screenshot of it identifies itself. */
      const number = id.split("-")[0].toUpperCase();
      expect(text.toUpperCase(), `${id} prints its number`).toContain(number);

      /* Units and the standard-condition basis (D03). */
      expect(text, `${id} prints its units basis`).toMatch(
        /Standard conditions|psia|Bscf|percent|dimensionless/,
      );

      /* How many of the four series roles the drawing actually uses. A single-series
         figure and a provenance diagram are held to different rules than a plot with an
         observed series, a fitted line and a truth mark. */
      const seriesColours = new Set(
        (svg.match(/#(14181c|17518f|c04e13|7f868c)/gi) ?? []).map((c) => c.toLowerCase()),
      ).size;

      /* A legend or direct labels on the drawing itself: short text items that are not
         the title, not the subtitle and not a numeric tick. Two of them is the floor for
         a drawing that uses more than one series colour, because that is the point at
         which a reader has to be told which mark is which. */
      const labels = (svg.match(/<text[^>]*>([^<]{3,80})<\/text>/g) ?? [])
        .map((t) => t.replace(/<[^>]+>/g, "").trim())
        .filter((t) => /[A-Za-z]/.test(t) && !/^[−\-\d.,\s]+$/.test(t))
        .slice(2); // drop the title and subtitle, which are not labels
      expect(labels.length, `${id} labels its marks on the drawing`).toBeGreaterThanOrEqual(
        seriesColours >= 2 ? 2 : 1,
      );

      /* And the redundant, non-colour channel is in the markup, not only in the prose:
         a dash pattern or a marker shape. decisions.md section 9 makes this mandatory
         rather than decorative, on the strength of a measured 1.31:1 greyscale
         separation between two of the series. */
      if (seriesColours >= 2) {
        const redundant = /stroke-dasharray/.test(svg) || /<circle/.test(svg);
        expect(redundant, `${id} carries a dash pattern or a marker shape`).toBe(true);
      }

      /* The material caveat and the evidence class travel with the image. */
      expect(text, `${id} carries its synthetic-data statement`).toMatch(/[Ss]ynthetic/);
      expect(text.length, `${id} carries substantive text`).toBeGreaterThan(400);

    });
  }

  test("every downloadable SVG is byte-identical to the one the page inlines", async ({
    request,
  }) => {
    const drift: string[] = [];
    for (const id of FIGURES) {
      const served = await (await request.get(url(`/data/figures/${id}.svg`))).text();
      const generated = readFileSync(join("src", "generated", "figures", `${id}.svg`), "utf8");
      /* The generator writes a trailing newline into the file; the page inlines the
         markup. Compare the markup. */
      if (served.trim() !== generated.trim()) {
        drift.push(
          `${id}: download ${served.length} B vs generated ${generated.length} B ` +
            `(sha ${createHash("sha256").update(served.trim()).digest("hex").slice(0, 12)} vs ` +
            `${createHash("sha256").update(generated.trim()).digest("hex").slice(0, 12)})`,
        );
      }
    }
    expect(drift, "downloads that have drifted from the figure they copy").toEqual([]);
  });

  test("the inlined SVG on the page is the same drawing as the download", async ({
    page,
    request,
  }) => {
    await page.goto(url("/studies/a4/"));
    const inlined = await page
      .locator("#f01 .figure__frame > svg")
      .evaluate((el) => el.outerHTML.replace(/\s+/g, " "));
    const downloaded = (await (await request.get(url("/data/figures/f01.svg"))).text()).replace(
      /\s+/g,
      " ",
    );
    /* Compare the drawn content: the same description and the same number of marks. */
    const marks = (s: string) => (s.match(/<(path|circle|line|rect|text)\b/g) ?? []).length;
    expect(marks(inlined)).toBe(marks(downloaded));
    const desc = (s: string) => s.match(/<desc[^>]*>([\s\S]*?)<\/desc>/)?.[1]?.trim() ?? "";
    expect(desc(inlined)).toBe(desc(downloaded));
  });

  test("every published download matches its recorded digest and size", async ({ request }) => {
    const index = (await (await request.get(url("/data/index.json"))).json()) as {
      files: Array<{ name: string; bytes: number; sha256: string }>;
    };
    expect(index.files.length).toBeGreaterThan(30);
    const bad: string[] = [];
    for (const f of index.files) {
      const res = await request.get(url(`/data/${f.name}`));
      if (res.status() !== 200) {
        bad.push(`${f.name}: HTTP ${res.status()}`);
        continue;
      }
      const body = await res.body();
      const sha = createHash("sha256").update(body).digest("hex");
      if (body.length !== f.bytes) bad.push(`${f.name}: ${body.length} B, index says ${f.bytes}`);
      if (sha !== f.sha256) bad.push(`${f.name}: digest ${sha.slice(0, 12)} != ${f.sha256.slice(0, 12)}`);
    }
    expect(bad, "downloads that do not match the published index").toEqual([]);
  });

  test("the figure manifest's PNG record matches what is on disk", async () => {
    const manifest = JSON.parse(
      readFileSync(join("src", "generated", "figures", "manifest.json"), "utf8"),
    ) as {
      site_build: { png_status: { emitted: string[]; blocked: string[]; caveat: string } };
      figures: Array<{ id: string; svg: { bytes: number }; png?: { bytes: number } }>;
    };
    expect(manifest.site_build.png_status.blocked).toEqual([]);
    expect(manifest.site_build.png_status.emitted.length).toBe(FIGURES.length);
    /* The PNGs are build artifacts, not published downloads. Record that plainly rather
       than implying the site serves them. */
    for (const f of manifest.figures) {
      if (!f.png) continue;
      expect(f.png.bytes, `${f.id} PNG has real content`).toBeGreaterThan(50_000);
    }
  });

  test("no PNG is offered as a download anywhere on the site", async ({ request }) => {
    /* Stated as a check so the report can say it rather than guess: the exported PNGs
       exist in site/src/generated/figures/ and are NOT published. Only the SVGs are. */
    const body = await (await request.get(url("/studies/a4/"))).text();
    expect(body).not.toMatch(/href="[^"]+\.png"/);
  });
});

test.describe("the unavailable-reference page", () => {
  test("A2 states what is blocked, in its own words, with no fabricated exhibit", async ({
    page,
  }) => {
    await page.goto(url("/studies/a2/"));
    await expect(page.locator("h1")).toContainText("withheld");

    /* No figure, no chart, no number standing in for the run that did not happen. */
    expect(await page.locator("figure.figure").count()).toBe(0);
    expect(await page.locator("svg").count()).toBe(0);

    /* The status table carries a result for every check, and says which are blocked. */
    const statuses = await page.locator(".status-table td .status, .status-table .status").allInnerTexts();
    expect(statuses.length).toBeGreaterThan(2);
    const text = await page.locator("main").innerText();
    expect(text).toContain("BLOCKED");
    expect(text).toContain("NOT RUN");
    expect(text).toMatch(/20 tests/);
    /* And it tells the reader how to obtain the inputs themselves. */
    expect(text).toMatch(/fetch_nist_reference|NIST/);
  });

  test("A2 offers no download of data it does not have", async ({ page }) => {
    await page.goto(url("/studies/a2/"));
    const downloads = await page
      .locator("a[download]")
      .evaluateAll((as) => as.map((a) => a.getAttribute("href") ?? ""));
    expect(downloads, "A2 publishes no reference-derived download").toEqual([]);
  });
});

test.describe("long labels", () => {
  /* EXPECTED TO FAIL -- finding F3 in docs/release/UI_QA.md. The diagnosis is a chain of
     three rules, each defensible alone: `tbody th[scope="row"] { white-space: nowrap }`
     stops a row label wrapping, so a three-column table is intrinsically ~700px wide;
     DataTable decides whether to wrap a table in a scroll region from its COLUMN COUNT
     (`wide = columns.length > 6`), so a wide three-column table gets none; and
     `html { overflow-x: hidden }` then turns the resulting overflow into clipping the
     reader cannot scroll to. The check below is written to the design target and left
     failing. */
  test("a long row label wraps instead of widening the page", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await page.goto(url("/studies/a4/"));
    const before = await page.evaluate(() => document.documentElement.scrollWidth);
    await page.evaluate(() => {
      /* Long the way this subject is long: many real words, not one 180-character
         token. An unbroken token of that length is not content this site produces, and a
         table that widened for one would be a different finding from this one. */
      const h = document.querySelector("#metrics-2 tbody th, #metrics-2 tbody td");
      if (h)
        h.textContent =
          "pseudo-pressure normalised deviation factor evaluated at the reservoir datum " +
          "under the same standard conditions as every other quantity on this page";
      const cap = document.querySelector("#metrics-2 caption");
      if (cap) cap.textContent = "A caption that keeps going ".repeat(30);
    });
    await page.waitForTimeout(100);
    const after = await page.evaluate(() => document.documentElement.scrollWidth);
    /* The long label must not make the document wider than it already was. */
    expect(after, "a long label widened the document").toBeLessThanOrEqual(before + 1);
  });

  test("the site's own longest labels are not clipped at 320", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await page.goto(url("/studies/a4/"));
    const clipped = await page.evaluate(() => {
      const out: string[] = [];
      for (const el of Array.from(
        document.querySelectorAll<HTMLElement>("h1, h2, h3, .eyebrow, .figure__title, legend"),
      )) {
        if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflowX !== "auto") {
          out.push(`${el.tagName.toLowerCase()} "${(el.textContent ?? "").slice(0, 40)}"`);
        }
      }
      return out;
    });
    expect(clipped, "headings and labels clipped at 320").toEqual([]);
  });
});
