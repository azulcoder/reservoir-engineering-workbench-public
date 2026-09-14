/**
 * Check 4 -- the things axe cannot decide, made mechanical where they can be.
 *
 * Keyboard operability end to end, a visible focus indicator on every interactive
 * element, an accessible name on every control, a text or data alternative for every
 * chart, and a second non-colour channel on every figure that draws more than one series.
 *
 * Where a judgement is unavoidable -- is that alternative *accurate*, does that dash
 * pattern actually separate two lines on screen -- this file checks the structural
 * precondition and the written review in docs/release/UI_QA.md carries the judgement. The
 * two are kept apart on purpose: a passing test here is not a claim that a reader can use
 * the page, only that the mechanism a reader would need is present.
 */
import { test, expect, type Page } from "@playwright/test";
import {
  CAPABILITY,
  keyboardScrollIsExpressible,
  notApplicable,
  recordCapability,
  ROUTES,
  settleScroll,
  tabRingIncludesLinks,
  url,
} from "./support";

/** Tab forward once and describe where focus landed and how it is indicated. */
async function focusState(page: Page) {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el || el === document.body) return null;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    /* Stamp each stop so the walker can tell a genuinely new stop from a second visit
       to one it has already had. Two different links can share a tag, a class and a
       label, so text is not an identity. */
    const first = el.hasAttribute("data-qa-stop");
    if (!first) el.setAttribute("data-qa-stop", "1");
    return {
      revisited: first,
      tag: el.tagName.toLowerCase(),
      id: el.id,
      cls: typeof el.className === "string" ? el.className : "",
      text: (el.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 50),
      outlineStyle: cs.outlineStyle,
      outlineWidth: parseFloat(cs.outlineWidth) || 0,
      outlineColor: cs.outlineColor,
      boxShadow: cs.boxShadow,
      matchesFocusVisible: el.matches(":focus-visible"),
      w: Math.round(r.width),
      h: Math.round(r.height),
    };
  });
}

/** Walk the tab ring forward, collecting each stop, until it wraps or a cap is hit. */
async function tabRing(page: Page, cap = 600) {
  const stops: Array<NonNullable<Awaited<ReturnType<typeof focusState>>>> = [];
  for (let i = 0; i < cap; i += 1) {
    await page.keyboard.press("Tab");
    const s = await focusState(page);
    if (!s) break; // focus left the document (browser chrome)
    if (s.revisited) break; // the ring has come back round
    stops.push(s);
  }
  return stops;
}

test.describe("keyboard and alternatives", () => {
  /* macOS WebKit keeps links out of the tab ring unless the system preference "Press Tab
     to highlight each item" (WebKit's tabsToLinks) is on, and Playwright's WebKit inherits
     that default. A tab walk there would be measuring the engine's setting, not the site.
     That is an engine limitation and NOT a statement about Safari on a real device, which
     is not tested here at all.

     It is also not taken on trust. `tabRingIncludesLinks` loads a control page holding one
     link and one button and reports what Tab actually reached, in this engine, in this
     run, and the skip below is decided by that measurement. If a future engine or a
     different environment does reach the link, these checks arm themselves again with no
     edit here; if the probe stops reaching even the button it fails in measure.spec.ts
     rather than silently excusing everything. */
  async function skipUnlessLinksAreTabbable(page: Page, testInfo: { annotations: Array<{ type: string; description?: string }> }) {
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
  }

  test("the skip link is the first stop and it works", async ({ page }, testInfo) => {
    await skipUnlessLinksAreTabbable(page, testInfo);
    await page.goto(url("/studies/a4/"));
    await page.keyboard.press("Tab");
    const first = await focusState(page);
    expect(first?.cls).toContain("skip-link");
    /* It must become visible when focused, not merely exist. */
    const onScreen = await page.locator("a.skip-link").evaluate((el) => {
      const r = el.getBoundingClientRect();
      return r.top >= 0 && r.left >= 0 && r.width > 0 && r.height > 0;
    });
    expect(onScreen, "the skip link is on screen while focused").toBe(true);
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/#main$/);
    const nowFocused = await page.evaluate(() => document.activeElement?.id);
    expect(nowFocused).toBe("main");
  });

  for (const route of ROUTES) {
    test(`${route} is operable by keyboard, with a visible indicator at every stop`, async ({
      page,
    }, testInfo) => {
      await skipUnlessLinksAreTabbable(page, testInfo);
      await page.goto(url(route));
      const stops = await tabRing(page);
      expect(stops.length, `focusable stops on ${route}`).toBeGreaterThan(3);

      const noIndicator: string[] = [];
      const zeroSize: string[] = [];
      for (const s of stops) {
        const outlined = s.outlineStyle !== "none" && s.outlineWidth >= 1;
        const shadowed = s.boxShadow !== "none" && s.boxShadow !== "";
        if (!outlined && !shadowed) {
          noIndicator.push(`${s.tag}#${s.id}.${s.cls} "${s.text}"`);
        }
        if (s.w === 0 || s.h === 0) zeroSize.push(`${s.tag}#${s.id}.${s.cls} "${s.text}"`);
      }
      expect(noIndicator, `focus stops with no visible indicator on ${route}`).toEqual([]);
      /* A focus stop with no box on screen is a stop a sighted keyboard reader loses. The
         radio inputs are the known exception: they are clipped to 1px and their label
         carries the indicator, which is the pattern the component documents. */
      expect(
        zeroSize.filter((s) => !s.startsWith("input#case-")),
        `zero-sized focus stops on ${route}`,
      ).toEqual([]);
    });
  }

  test("no keyboard trap: the tab ring leaves every disclosure and every scroll region", async ({
    page,
  }, testInfo) => {
    await skipUnlessLinksAreTabbable(page, testInfo);
    await page.goto(url("/studies/a4/"));
    /* Open everything first: a closed <details> hides the trap. */
    await page.evaluate(() =>
      document.querySelectorAll("details").forEach((d) => ((d as HTMLDetailsElement).open = true)),
    );
    const stops = await tabRing(page, 600);
    const tags = new Set(stops.map((s) => s.tag));
    expect(tags.has("a")).toBe(true);
    expect(stops.length).toBeGreaterThan(20);
    /* The ring terminates: the last stop is reached without repeating one stop forever. */
    const last = stops[stops.length - 1];
    expect(last).toBeTruthy();
    /* Shift+Tab walks back out of wherever it ended. */
    await page.keyboard.press("Shift+Tab");
    const back = await focusState(page);
    expect(back).not.toBeNull();
  });

  test("every figure frame is reachable and labelled, and really is a scroll container", async ({
    page,
  }) => {
    await page.goto(url("/studies/a4/"));
    const frames = page.locator(".figure__frame");
    const count = await frames.count();
    expect(count).toBeGreaterThan(5);
    for (let i = 0; i < count; i += 1) {
      const f = frames.nth(i);
      await expect(f).toHaveAttribute("tabindex", "0");
      await expect(f).toHaveAttribute("role", "group");
      const name = await f.getAttribute("aria-label");
      expect(name && name.length > 4, `figure frame ${i} has an accessible name`).toBe(true);
    }

    /* Focusable and labelled is half the claim. The other half is that the frame is a real
       scroll container, which is checked by scrolling it -- from script, so that the
       property of the ELEMENT is separated from the engine's willingness to drive it from
       the keyboard. The keyboard half is the next test. */
    await page.setViewportSize({ width: 375, height: 800 });
    const moved = await frames.evaluateAll((els) =>
      els
        .filter((el) => el.scrollWidth > el.clientWidth + 1)
        .map((el) => {
          el.scrollLeft = 0;
          el.scrollBy(80, 0);
          const at = el.scrollLeft;
          el.scrollLeft = 0;
          return { id: el.getAttribute("aria-label") ?? "", at };
        }),
    );
    expect(moved.length, "figure frames that overflow at 375").toBeGreaterThan(5);
    expect(
      moved.filter((m) => m.at <= 0).map((m) => m.id),
      "frames that overflow but do not scroll",
    ).toEqual([]);

    /* The explorer panels DO overflow by design (min-width: 460px), so at 375 at least
       one labelled scroll container on this page must be genuinely operable. */
    const panel = page.locator("[data-case]:not([hidden]) .explorer__frame").first();
    const panelScrolls = await panel.evaluate((el) => el.scrollWidth > el.clientWidth + 1);
    expect(panelScrolls, "an explorer panel scrolls inside its own region at 375").toBe(true);
  });

  test("a figure frame that overflows scrolls with the arrow keys", async ({
    page,
  }, testInfo) => {
    /* NOT APPLICABLE, not skipped on faith.
     *
     * This check failed on WebKit and only on WebKit. The control fixture in support.ts --
     * a 300px box with a 2000px child, a tabindex, no stylesheet and no script -- settles
     * which side the fault is on: in Playwright's WebKit that box takes focus and accepts
     * scrollBy(60) but does not move one pixel on ArrowRight or End, while Chromium and
     * Firefox both scroll it. The engine in this environment cannot express keyboard
     * scrolling of a focused overflow container at all, so a figure frame that does not
     * respond is failing the environment and not the site. The finding is recorded on the
     * test, the reason is measured in the same run, and the check arms itself again the
     * moment the engine can express the behaviour.
     *
     * This is deliberately narrow. It classifies ONE behaviour on whatever engine cannot
     * express it, not "keyboard tests on WebKit": the reachable-and-labelled check above,
     * the scroll-container check above, and the focus-indicator checks all still run here. */
    const cap = await keyboardScrollIsExpressible(page);
    recordCapability(testInfo, CAPABILITY.keyboardScrollOverflow, cap);
    test.skip(
      !cap.available,
      notApplicable(
        CAPABILITY.keyboardScrollOverflow,
        "this engine does not scroll a focused overflow container with the arrow keys, " +
          "measured on a control fixture carrying nothing of the site.",
      ),
    );

    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto(url("/studies/a4/"));
    const frames = page.locator(".figure__frame");
    const overflowing = await frames.evaluateAll((els) =>
      els
        .filter((el) => el.scrollWidth > el.clientWidth + 1)
        .map((el) => el.getAttribute("aria-label") ?? ""),
    );
    expect(overflowing.length, "figure frames that overflow at 375").toBeGreaterThan(5);

    const stuck: string[] = [];
    for (const id of overflowing) {
      const frame = page.locator(`.figure__frame[aria-label="${id}"]`).first();
      await frame.evaluate((el) => {
        (el as HTMLElement).focus();
        el.scrollLeft = 0;
      });
      await page.keyboard.press("ArrowRight");
      /* Poll for the scroll on the same budget the capability probe uses. Reading once
         after a flat 400 ms made this test disagree with its own probe about the same
         engine in the same run: the probe measured the control fixture as scrollable and
         these frames as stuck, which is not a coherent statement about anything. */
      const after = await settleScroll(page, () => frame.evaluate((el) => el.scrollLeft));
      if (after <= 0) stuck.push(`${id}: scrollLeft still ${after}`);
    }
    expect(stuck, "focused frames that do not scroll on ArrowRight").toEqual([]);
  });

  test("only a region that scrolls is given a focus stop, measured across widths", async ({
    page,
  }, testInfo) => {
    /* The design rule: a genuinely scrollable region needs keyboard access, and a focus
     * stop on something with nothing to scroll is a stop a keyboard reader pays for and
     * gets nothing from.
     *
     * The complication, measured rather than argued: the SAME region scrolls at one width
     * and not at another. `table { width: 100% }` means a three-column table overflows a
     * 375px viewport and fits a 1440px one, so at 375 nine of these regions scroll and at
     * 1440 nine of them do not. No static tabindex can be right at both widths, and the
     * two ways of being wrong are not equal: a region that scrolls and cannot be focused
     * is a 2.1.1 failure, and a region that is focusable with nothing to scroll is an
     * inert stop. The markup takes the second, and this check pins the consequence in both
     * directions -- every region that CAN scroll at any tested width is reachable and
     * named, and the inert count at each width is recorded rather than hidden. */
    const WIDTHS = [320, 375, 768, 1440];
    const unreachable: string[] = [];
    const inertByWidth: string[] = [];

    for (const width of WIDTHS) {
      await page.setViewportSize({ width, height: 900 });
      let scrolls = 0;
      let inert = 0;
      for (const route of ROUTES) {
        await page.goto(url(route));
        await page.evaluate(() =>
          document
            .querySelectorAll("details")
            .forEach((d) => ((d as HTMLDetailsElement).open = true)),
        );
        const regions = await page.evaluate(() =>
          Array.from(document.querySelectorAll(".scroll-region, .figure__frame, .explorer__frame"))
            .filter((el) => !el.closest("[data-case][hidden]"))
            .map((el) => ({
              name:
                el.getAttribute("aria-label") ??
                el.querySelector("caption")?.textContent?.replace(/\s+/g, " ").trim().slice(0, 40) ??
                el.className,
              scrolls: el.scrollWidth > el.clientWidth + 1,
              tabindex: el.getAttribute("tabindex"),
              labelled: Boolean(el.getAttribute("aria-label") ?? el.getAttribute("aria-labelledby")),
            })),
        );
        for (const r of regions) {
          if (r.scrolls) {
            scrolls += 1;
            if (r.tabindex !== "0") unreachable.push(`${route} @${width} "${r.name}": no focus stop`);
            if (!r.labelled) unreachable.push(`${route} @${width} "${r.name}": no accessible name`);
          } else if (r.tabindex === "0") {
            inert += 1;
          }
        }
      }
      inertByWidth.push(`${width}px: ${scrolls} scrolling, ${inert} inert focus stops`);
    }

    testInfo.annotations.push({
      type: "focus stops on scroll regions",
      description: inertByWidth.join("; "),
    });
    expect(unreachable, "a region that scrolls but cannot be reached or named").toEqual([]);
  });

  test("every link and control has a non-empty, non-generic accessible name", async ({ page }) => {
    const bad: string[] = [];
    for (const route of ROUTES) {
      await page.goto(url(route));
      await page.evaluate(() =>
        document.querySelectorAll("details").forEach((d) => ((d as HTMLDetailsElement).open = true)),
      );
      const found = await page.evaluate(() => {
        const GENERIC = ["click here", "here", "read more", "more", "link", "this", "download"];
        const out: string[] = [];
        const name = (el: Element) => {
          const labelled = el.getAttribute("aria-labelledby");
          if (labelled) {
            const parts = labelled
              .split(/\s+/)
              .map((id) => document.getElementById(id)?.textContent ?? "")
              .join(" ");
            if (parts.trim()) return parts.trim();
          }
          return (
            el.getAttribute("aria-label") ??
            (el as HTMLElement).innerText ??
            el.textContent ??
            ""
          ).trim();
        };
        for (const el of Array.from(
          document.querySelectorAll("a[href], button, summary, [role=button]"),
        )) {
          const n = name(el).replace(/\s+/g, " ");
          if (!n) out.push(`${el.tagName.toLowerCase()}: EMPTY NAME`);
          else if (GENERIC.includes(n.toLowerCase()))
            out.push(`${el.tagName.toLowerCase()}: generic name "${n}"`);
        }
        return out;
      });
      for (const f of found) bad.push(`${route}: ${f}`);
    }
    expect(bad, "controls with an empty or generic accessible name").toEqual([]);
  });

  test("every chart carries a text or data alternative", async ({ page }) => {
    const missing: string[] = [];
    for (const route of ROUTES) {
      await page.goto(url(route));
      const report = await page.evaluate(() => {
        const out: Array<{
          id: string;
          desc: string;
          rows: number;
          caption: string;
          pointsTo: string | null;
          dataDownload: boolean;
        }> = [];
        for (const fig of Array.from(document.querySelectorAll("figure.figure"))) {
          const id = fig.id || "(unnamed figure)";
          const descId = fig.getAttribute("aria-describedby") ?? "";
          const desc = (document.getElementById(descId)?.textContent ?? "").trim();
          const table = fig.querySelector("table");
          const rows = table ? table.querySelectorAll("tbody tr").length : 0;
          const caption = (table?.querySelector("caption")?.textContent ?? "").trim();
          /* Some exhibits share one table -- F01b and F02 are drawn from F01's 49 rows --
             and point at it instead of repeating it. That is a valid alternative as long
             as the target is a real table that exists where the reader is sent. */
          let pointsTo: string | null = null;
          const dataDownload = fig.querySelector(".figure__meta a[download]") !== null;
          for (const a of Array.from(fig.querySelectorAll<HTMLAnchorElement>("a[href*='#']"))) {
            const frag = (a.getAttribute("href") ?? "").split("#")[1] ?? "";
            const target = frag ? document.getElementById(frag) : null;
            if (target && (target.tagName === "TABLE" || target.querySelector("table"))) {
              pointsTo = frag;
              break;
            }
          }
          out.push({ id, desc, rows, caption, pointsTo, dataDownload });
        }
        return out;
      });
      for (const f of report) {
        if (f.desc.length < 80) missing.push(`${route} ${f.id}: long description too short`);
        /* One of the three has to be there: the numbers in a table on this page, a
           pointer to the table that holds them, or the download that carries them. The
           home page's F01 takes the third route -- its alternative is the visually
           hidden long description plus the full CSV, with the 49-row table one link
           away on the case page. */
        if (f.rows < 1 && !f.pointsTo && !f.dataDownload) {
          missing.push(`${route} ${f.id}: no table, no pointer to one, no data download`);
        }
        if (f.rows > 0 && !f.caption) missing.push(`${route} ${f.id}: data table has no caption`);
      }
      if (route === "/studies/a4/") expect(report.length).toBeGreaterThanOrEqual(9);
    }
    expect(missing, "figures without a usable alternative").toEqual([]);
  });

  test("every multi-series figure encodes series by more than colour", async ({ page }) => {
    const SERIES = ["#14181c", "#17518f", "#c04e13", "#7f868c"];
    const weak: string[] = [];
    for (const route of ROUTES) {
      await page.goto(url(route));
      const figs = await page.evaluate((SERIES) => {
        const out: Array<{
          id: string;
          colours: string[];
          dashes: number;
          markers: number;
          labels: number;
        }> = [];
        for (const fig of Array.from(document.querySelectorAll("figure.figure"))) {
          const svg = fig.querySelector("svg");
          if (!svg) continue;
          const colours = new Set<string>();
          let dashes = 0;
          let markers = 0;
          for (const el of Array.from(svg.querySelectorAll("*"))) {
            if (el.closest("[aria-hidden=true]")) continue;
            const stroke = (el.getAttribute("stroke") ?? "").toLowerCase();
            const fill = (el.getAttribute("fill") ?? "").toLowerCase();
            for (const c of [stroke, fill]) if (SERIES.includes(c)) colours.add(c);
            if (el.getAttribute("stroke-dasharray")) dashes += 1;
            const tag = el.tagName.toLowerCase();
            if (tag === "circle" || tag === "path" || tag === "rect") {
              /* A marker shape: a small closed mark, as distinct from a long trace. */
              const d = el.getAttribute("d") ?? "";
              if (tag === "circle" || (d && d.length < 120)) markers += 1;
            }
          }
          const labels = svg.querySelectorAll("text").length;
          out.push({ id: fig.id, colours: [...colours], dashes, markers, labels });
        }
        return out;
      }, SERIES);
      for (const f of figs) {
        if (f.colours.length < 2) continue; // one series: no separation problem to solve
        const second = f.dashes > 0 || f.markers > 0;
        if (!second) weak.push(`${route} ${f.id}: ${f.colours.length} series, no dash or marker`);
        if (f.labels < 4) weak.push(`${route} ${f.id}: only ${f.labels} text labels`);
      }
    }
    expect(weak, "figures separated by colour alone").toEqual([]);
  });

  test("heading order steps by one on every route", async ({ page }) => {
    const broken: string[] = [];
    for (const route of ROUTES) {
      await page.goto(url(route));
      const levels = await page
        .locator("h1, h2, h3, h4, h5, h6")
        .evaluateAll((els) =>
          els.map((e) => ({ level: Number(e.tagName[1]), text: (e.textContent ?? "").slice(0, 40) })),
        );
      expect(levels[0]?.level, `${route} starts at h1`).toBe(1);
      for (let i = 1; i < levels.length; i += 1) {
        if (levels[i].level > levels[i - 1].level + 1) {
          broken.push(`${route}: h${levels[i - 1].level} -> h${levels[i].level} at "${levels[i].text}"`);
        }
      }
    }
    expect(broken, "skipped heading levels").toEqual([]);
  });

  test("the contents rail is actually painted at desktop width, and is a control below it", async ({
    page,
  }) => {
    /* The rail is a <details>. At >= 64rem its summary is display:none and the list is
       forced visible, which is the design; below that it is a disclosure the reader
       operates. Engines now hide a closed disclosure's content through
       `::details-content { content-visibility: hidden }` rather than through `display`
       on the children, so "forced visible" has to reach the pseudo-element. It did not,
       and the rail painted nothing at 1440 while still holding a 240px column. Both
       states are asserted here. */
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(url("/studies/a4/"));
    const wide = await page.evaluate(() => {
      const nav = document.querySelector("nav.contents")!;
      const list = document.querySelector(".contents__list")!;
      const summary = document.querySelector(".contents__summary")!;
      return {
        navHeight: Math.round(nav.getBoundingClientRect().height),
        painted: list.checkVisibility({ contentVisibilityAuto: true, visibilityProperty: true }),
        items: list.querySelectorAll("li a").length,
        summaryShown: getComputedStyle(summary).display !== "none",
      };
    });
    expect(wide.painted, "the contents list is painted at 1440").toBe(true);
    expect(wide.navHeight, "the rail has height at 1440").toBeGreaterThan(100);
    expect(wide.items).toBeGreaterThan(4);
    expect(wide.summaryShown, "no dead control at desktop width").toBe(false);

    /* Below the breakpoint it is a disclosure again: summary visible, list closed until
       the reader opens it, and opening it works. */
    await page.setViewportSize({ width: 900, height: 900 });
    const narrow = await page.evaluate(() => {
      const list = document.querySelector(".contents__list")!;
      const summary = document.querySelector(".contents__summary")!;
      return {
        painted: list.checkVisibility({ contentVisibilityAuto: true, visibilityProperty: true }),
        summaryShown: getComputedStyle(summary).display !== "none",
      };
    });
    expect(narrow.summaryShown).toBe(true);
    expect(narrow.painted, "closed at 900 until the reader opens it").toBe(false);
    await page.locator(".contents__summary").click();
    await expect(page.locator(".contents__list")).toBeVisible();
  });

  test("the contents rail and primary nav are labelled landmarks", async ({ page }) => {
    await page.goto(url("/studies/a4/"));
    await expect(page.locator('nav[aria-label="Primary"]')).toHaveCount(1);
    const rail = page.locator("nav.contents");
    await expect(rail).toHaveAttribute("aria-labelledby", /.+/);
    const labelId = await rail.getAttribute("aria-labelledby");
    await expect(page.locator(`#${labelId}`)).not.toBeEmpty();
    await expect(page.locator("main#main")).toHaveCount(1);
    await expect(page.locator("footer")).toHaveCount(1);
    await expect(page.locator("header")).toHaveCount(1);
  });
});
