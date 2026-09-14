/**
 * Check 2 -- what the pages do at runtime, and what they carry in their bytes.
 *
 * Console errors and page errors, failed requests, requests to any host that is not the
 * server under test, credential-shaped strings in the delivered HTML, developer-machine
 * paths, and the presence of the marks each figure is supposed to draw. A figure that
 * renders an empty frame is a broken exhibit even when nothing logs an error, so the
 * mark counts are asserted rather than assumed.
 */
import { test, expect } from "@playwright/test";
import { ROUTES, url, watch } from "./support";

const SECRET_PATTERNS: Array<[string, RegExp]> = [
  ["AWS access key id", /\bAKIA[0-9A-Z]{16}\b/],
  ["private key block", /-----BEGIN [A-Z ]*PRIVATE KEY-----/],
  ["GitHub token", /\bgh[pousr]_[A-Za-z0-9]{20,}\b/],
  ["Slack token", /\bxox[abprs]-[A-Za-z0-9-]{10,}\b/],
  ["bearer header", /\bAuthorization:\s*Bearer\s+[A-Za-z0-9._-]{12,}/i],
  ["assigned api key", /\b(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*["'][^"']{8,}["']/i],
  ["developer home path", /\/Users\/[a-z0-9._-]+\//i],
  ["linux home path", /\/home\/[a-z0-9._-]+\//i],
];

test.describe("runtime", () => {
  for (const route of ROUTES) {
    test(`${route} logs nothing and requests nothing off-origin`, async ({ page, baseURL }) => {
      const noise = watch(page);
      await page.goto(url(route), { waitUntil: "load" });
      /* Give any deferred work a moment to fail loudly if it is going to. */
      await page.waitForTimeout(300);

      expect(noise.consoleErrors, `console errors on ${route}`).toEqual([]);
      expect(noise.pageErrors, `uncaught exceptions on ${route}`).toEqual([]);
      expect(noise.failed, `failed requests on ${route}`).toEqual([]);

      const offOrigin = noise.requests.filter((u) => !u.startsWith(baseURL!));
      expect(offOrigin, `off-origin requests on ${route}`).toEqual([]);
    });
  }

  test("the delivered HTML carries no credential-shaped string and no local path", async ({
    request,
  }) => {
    const hits: string[] = [];
    for (const route of ROUTES) {
      const body = await (await request.get(url(route))).text();
      for (const [name, re] of SECRET_PATTERNS) {
        const m = body.match(re);
        if (m) hits.push(`${route}: ${name} -> ${m[0].slice(0, 60)}`);
      }
    }
    expect(hits, "credential-shaped or machine-local strings in the output").toEqual([]);
  });

  test("the only external host string in the output is the SVG namespace", async ({ request }) => {
    const found = new Map<string, string[]>();
    for (const route of ROUTES) {
      const body = await (await request.get(url(route))).text();
      for (const m of body.matchAll(/https?:\/\/([a-z0-9.-]+)/gi)) {
        const host = m[1].toLowerCase();
        if (!found.has(host)) found.set(host, []);
        if (!found.get(host)!.includes(route)) found.get(host)!.push(route);
      }
    }
    const hosts = [...found.keys()].sort();
    /* www.w3.org appears as xmlns="http://www.w3.org/2000/svg", which is an identifier
       and not a request. Anything else would be a third-party dependency. */
    expect(hosts).toEqual(["www.w3.org"]);
  });

  test("no page ships an external script, a remote font or a stylesheet from elsewhere", async ({
    page,
  }) => {
    const problems: string[] = [];
    for (const route of ROUTES) {
      await page.goto(url(route));
      const found = await page.evaluate(() => {
        const out: string[] = [];
        for (const s of Array.from(document.querySelectorAll("script[src]")))
          out.push(`script src ${s.getAttribute("src")}`);
        for (const l of Array.from(document.querySelectorAll("link[rel~=preconnect], link[rel~=dns-prefetch]")))
          out.push(`preconnect ${l.getAttribute("href")}`);
        for (const sheet of Array.from(document.styleSheets)) {
          let rules: CSSRuleList | null = null;
          try {
            rules = sheet.cssRules;
          } catch {
            out.push("cross-origin stylesheet");
            continue;
          }
          for (const rule of Array.from(rules ?? [])) {
            if (rule.constructor.name === "CSSFontFaceRule") out.push("@font-face");
            if (rule.constructor.name === "CSSImportRule") out.push("@import");
          }
        }
        return out;
      });
      for (const f of found) problems.push(`${route}: ${f}`);
    }
    expect(problems).toEqual([]);
  });

  test("no cookie is set and no storage is written", async ({ page, context }) => {
    for (const route of ROUTES) await page.goto(url(route));
    expect(await context.cookies()).toEqual([]);
    const stored = await page.evaluate(() => ({
      local: Object.keys(localStorage).length,
      session: Object.keys(sessionStorage).length,
    }));
    expect(stored).toEqual({ local: 0, session: 0 });
  });

  /* EXPECTED TO FAIL -- finding F7 in docs/release/UI_QA.md. Two annotations on
     /studies/a4/ are drawn starting far enough to the right that they run past the edge
     of their own canvas and are cut off mid-sentence, in the page, in the downloadable
     SVG and in the PNG. Left failing: where the label should go instead is a figure
     design decision, not a markup fix. */
  test("no figure paints text outside its own drawing", async ({ page }) => {
    /* Swept across the four widths this suite tests rather than measured at one. The
       exhibits keep their authored canvas at every viewport, so the result is expected to
       be width-invariant, and measuring it is how that expectation is checked rather than
       asserted: as measured, the same two annotations on /studies/a4/ are clipped at 320,
       375, 768, 1440 and 1600, by the same 62px and 81px. A clipping that appeared only at
       one width would be a layout fault; one that appears at all of them is in the drawing. */
    const clipped: string[] = [];
    for (const width of [320, 375, 768, 1440, 1600]) {
      await page.setViewportSize({ width, height: 900 });
      for (const route of ROUTES) {
        await page.goto(url(route));
        const found = await page.evaluate(() => {
          const out: Array<{ fig: string; text: string; over: number }> = [];
          for (const frame of Array.from(
            document.querySelectorAll(".figure__frame, .explorer__frame"),
          )) {
            if (frame.closest("[data-case][hidden]")) continue;
            const root = frame.querySelector("svg");
            if (!root) continue;
            const rb = root.getBoundingClientRect();
            const name =
              root.getAttribute("aria-label") ??
              root.querySelector("title")?.textContent ??
              "(unnamed)";
            for (const t of Array.from(root.querySelectorAll("text"))) {
              const tb = t.getBoundingClientRect();
              if (tb.width === 0) continue;
              const over = Math.max(tb.right - rb.right, rb.left - tb.left);
              if (over > 1) {
                out.push({
                  fig: name.slice(0, 40),
                  text: (t.textContent ?? "").slice(0, 50),
                  over: Math.round(over),
                });
              }
            }
          }
          return out;
        });
        for (const f of found) {
          const line = `${route} @${width} [${f.fig}] +${f.over}px: "${f.text}"`;
          if (!clipped.includes(line)) clipped.push(line);
        }
      }
    }
    expect(clipped, "figure text painted outside the figure").toEqual([]);
  });

  test("every figure frame draws marks, not an empty box", async ({ page }) => {
    const empty: string[] = [];
    for (const route of ROUTES) {
      await page.goto(url(route));
      const frames = await page.locator(".figure__frame, .explorer__frame").evaluateAll((els) =>
        /* The explorer ships all eight cases and hides seven. A hidden region measures
           0x0, which is correct, not broken -- only what is on screen is judged here.
           The hidden regions get their own check in explorer.spec.ts. */
        els
          .filter((el) => !el.closest("[data-case][hidden]"))
          .map((el) => {
          const svg = el.querySelector("svg");
          const labelled = svg?.getAttribute("aria-labelledby");
          const label =
            svg?.getAttribute("aria-label") ??
            (labelled ? (document.getElementById(labelled)?.textContent ?? labelled) : null) ??
            svg?.querySelector("title")?.textContent ??
            el.getAttribute("aria-label") ??
            "?";
          if (!svg) return { label, marks: -1, box: [0, 0] as [number, number] };
          const marks = svg.querySelectorAll(
            "path, circle, rect, line, polyline, polygon",
          ).length;
          const r = svg.getBoundingClientRect();
          return { label, marks, box: [Math.round(r.width), Math.round(r.height)] as [number, number] };
        }),
      );
      for (const f of frames) {
        if (f.marks < 5 || f.box[0] < 40 || f.box[1] < 40) {
          empty.push(`${route}: "${f.label}" marks=${f.marks} box=${f.box.join("x")}`);
        }
      }
      /* A page that claims figures must actually have them. */
      if (route === "/studies/a4/") expect(frames.length).toBeGreaterThanOrEqual(10);
    }
    expect(empty, "figure frames with no marks or no size").toEqual([]);
  });
});
