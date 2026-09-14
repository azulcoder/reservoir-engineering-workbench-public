/**
 * Checks 7 and 10 -- the scenario explorer.
 *
 * All eight computed cases are exercised, by pointer and by keyboard. For each one the
 * test compares what the page displays against the case's own download, fetched over
 * HTTP from the same build: R-squared, fitted gas in place, the inventory error and the
 * bias in units of the standard error. That is the check that matters, because a
 * selector which swaps the charts but leaves the numbers behind -- or swaps the numbers
 * but leaves the downloads behind -- is the failure mode this component's design exists
 * to prevent, and asserting only that "something changed" would not catch it.
 *
 * The invalid-query behaviour is checked in the terms the component itself sets: nothing
 * is interpolated, the reader is told which cases exist, and the base case is shown.
 */
import { test, expect, type Page } from "@playwright/test";
import { BASE, CASES, BASE_CASE, slugFor, url } from "./support";

const A4 = url("/studies/a4/");

interface CaseExport {
  selected_case: {
    r_squared: number;
    fitted_gas_in_place_bscf: number;
    relative_gas_in_place_error: number;
    bias_over_stderr: number;
    n_observations: number;
    invaded_pore_volume_fraction: number;
    terminal_pressure_psia: number;
  };
  observations: unknown[];
}

async function exported(request: import("@playwright/test").APIRequestContext, key: string) {
  const res = await request.get(url(`/data/f01_f02_case-${slugFor(key)}.json`));
  expect(res.status(), `download for J = ${key}`).toBe(200);
  return (await res.json()) as CaseExport;
}

/** The value cell of one row of the visible metrics table. */
async function metric(page: Page, key: string, quantity: string): Promise<string> {
  const row = page.locator(`#metrics-${slugFor(key)} tbody tr`, { hasText: quantity }).first();
  return (await row.locator("td").first().innerText()).trim();
}

async function visibleCase(page: Page): Promise<string[]> {
  return page.locator("[data-case]:not([hidden])").evaluateAll((els) =>
    els.map((el) => el.getAttribute("data-case") ?? ""),
  );
}

test.describe("scenario explorer", () => {
  test("the controls are hidden in the delivered HTML and revealed by the script", async ({
    page,
    request,
  }) => {
    const html = await (await request.get(A4)).text();
    /* In the bytes: hidden. */
    expect(html).toMatch(/data-explorer-controls\s+hidden/);
    expect(html).toMatch(/data-explorer-static/);
    /* In the browser: revealed, and the note explaining their absence retired. */
    await page.goto(A4);
    await expect(page.locator("[data-explorer-controls]")).toBeVisible();
    await expect(page.locator("[data-explorer-static]")).toBeHidden();
    await expect(page.locator('input[name="explorer-case"]')).toHaveCount(CASES.length);
  });

  for (const key of CASES) {
    test(`case J = ${key} displays what its own download contains`, async ({ page, request }) => {
      const export_ = await exported(request, key);
      const data = export_.selected_case;
      await page.goto(A4);
      await page.locator(`label[for="case-${slugFor(key)}"]`).click();

      /* Exactly one case region on screen, and it is the one asked for. */
      expect(await visibleCase(page)).toEqual([key]);

      /* The metrics table agrees with the export, at the precision the page prints. */
      expect(await metric(page, key, "R-squared of the volumetric fit")).toBe(
        data.r_squared.toFixed(6),
      );
      expect(await metric(page, key, "Fitted gas in place")).toBe(
        `${data.fitted_gas_in_place_bscf.toFixed(3)} Bscf`,
      );
      const errPct = data.relative_gas_in_place_error * 100;
      expect(await metric(page, key, "Inventory error")).toBe(
        `${errPct >= 0 ? "+" : ""}${errPct.toFixed(3)} %`,
      );
      expect(await metric(page, key, "Bias in units of that standard error")).toBe(
        data.bias_over_stderr.toFixed(2),
      );
      expect(await metric(page, key, "Terminal pressure")).toBe(
        `${data.terminal_pressure_psia.toFixed(1)} psia`,
      );

      /* The prose above the panels carries the same two numbers as the table. */
      const lede = await page.locator(`[data-case="${key}"] .lede`).innerText();
      expect(lede).toContain(data.r_squared.toFixed(6));
      expect(lede).toContain(data.fitted_gas_in_place_bscf.toFixed(3));

      /* Three panels, each with marks, all belonging to this case. */
      const panels = page.locator(`[data-case="${key}"] .explorer__frame svg`);
      await expect(panels).toHaveCount(3);
      const marks = await panels.evaluateAll((svgs) =>
        svgs.map((s) => s.querySelectorAll("path, circle, rect, line, polyline").length),
      );
      for (const m of marks) expect(m).toBeGreaterThan(5);

      /* The per-case downloads are this case's files and nothing else. */
      const hrefs = await page
        .locator(`[data-case="${key}"] .explorer__downloads a`)
        .evaluateAll((as) => as.map((a) => a.getAttribute("href") ?? ""));
      expect(hrefs).toEqual([
        url(`/data/f01_f02_case-${slugFor(key)}.csv`),
        url(`/data/f01_f02_case-${slugFor(key)}.json`),
      ]);

      /* The address reflects the selection -- and drops the parameter on the base case,
         so the canonical address of the default view has no query string. */
      const current = new URL(page.url());
      if (key === BASE_CASE) expect(current.searchParams.get("case")).toBeNull();
      else expect(current.searchParams.get("case")).toBe(key);

      /* The observations disclosure carries this case's rows, and the count the caption
         claims is the count the export has. */
      const caption = await page
        .locator(`#obs-${slugFor(key)} caption`)
        .evaluate((el) => el.textContent ?? "");
      expect(caption).toContain(String(data.n_observations));
      expect(export_.observations.length).toBe(data.n_observations);
    });
  }

  test("the status region announces the change, and says it is not a rerun", async ({ page }) => {
    await page.goto(A4);
    const status = page.locator("[data-explorer-status]");
    await expect(status).toHaveAttribute("role", "status");
    await expect(status).toHaveText("");
    await page.locator('label[for="case-60"]').click();
    await expect(status).toContainText("J = 60");
    await expect(status).toContainText("not a rerun");
  });

  test("the keyboard drives the whole control: arrows select, reset returns", async ({ page }) => {
    await page.goto(A4);
    /* Focus the checked radio the way a reader would: tab to the group. */
    await page.locator(`#case-${slugFor(BASE_CASE)}`).focus();
    await expect(page.locator(`#case-${slugFor(BASE_CASE)}`)).toBeFocused();

    await page.keyboard.press("ArrowRight");
    expect(await visibleCase(page)).toEqual(["6"]);
    await page.keyboard.press("ArrowRight");
    expect(await visibleCase(page)).toEqual(["20"]);
    await page.keyboard.press("ArrowLeft");
    expect(await visibleCase(page)).toEqual(["6"]);

    /* Wrapping at the end of a radio group is native behaviour; confirm it lands on a
       real case rather than nothing. */
    await page.locator("#case-0").focus();
    await page.keyboard.press("ArrowLeft");
    expect((await visibleCase(page)).length).toBe(1);

    /* The reset button is reachable by keyboard and returns to the base case. */
    const reset = page.locator("[data-explorer-reset]");
    await reset.focus();
    await page.keyboard.press("Enter");
    expect(await visibleCase(page)).toEqual([BASE_CASE]);
    await expect(page.locator(`#case-${slugFor(BASE_CASE)}`)).toBeFocused();
    expect(new URL(page.url()).searchParams.get("case")).toBeNull();
  });

  test("a deep link opens on the case it names", async ({ page }) => {
    for (const key of ["0", "0.05", "60"]) {
      await page.goto(`${A4}?case=${encodeURIComponent(key)}`);
      expect(await visibleCase(page)).toEqual([key]);
      await expect(page.locator(`#case-${slugFor(key)}`)).toBeChecked();
      await expect(page.locator("[data-explorer-invalid]")).toBeHidden();
    }
  });

  for (const bad of ["999", "3", "abc", "", "2.0", "J=2", "<script>"]) {
    test(`an invalid ?case=${bad || "(empty)"} falls back to the base case and says so`, async ({
      page,
    }) => {
      await page.goto(`${A4}?case=${encodeURIComponent(bad)}`);
      const invalid = page.locator("[data-explorer-invalid]");
      await expect(invalid).toBeVisible();
      const text = await invalid.innerText();
      /* It must name the eight that exist and refuse to invent a ninth. */
      expect(text).toContain("Nothing was interpolated");
      for (const key of CASES) expect(text).toContain(key);
      expect(await visibleCase(page)).toEqual([BASE_CASE]);
      /* And the injected string is rendered as text, never as markup. */
      expect(await page.locator("[data-explorer-invalid] script").count()).toBe(0);
    });
  }

  test("the invalid notice clears once a real case is chosen", async ({ page }) => {
    await page.goto(`${A4}?case=999`);
    await expect(page.locator("[data-explorer-invalid]")).toBeVisible();
    await page.locator('label[for="case-0p6"]').click();
    await expect(page.locator("[data-explorer-invalid]")).toBeHidden();
    expect(await visibleCase(page)).toEqual(["0.6"]);
  });

  test("browser back and forward restore a consistent state", async ({ page }) => {
    await page.goto(A4);
    await page.locator('label[for="case-60"]').click();
    expect(new URL(page.url()).searchParams.get("case")).toBe("60");

    /* Leave the page and come back the way a reader does. */
    await page.goto(url("/studies/"));
    await page.goBack();
    await expect(page.locator("#explorer")).toBeVisible();
    expect(new URL(page.url()).searchParams.get("case")).toBe("60");
    expect(await visibleCase(page)).toEqual(["60"]);
    await expect(page.locator("#case-60")).toBeChecked();
    /* Everything on screen belongs to that case, not a mixture. */
    await expect(page.locator("#metrics-60")).toBeVisible();
    await expect(page.locator("#metrics-2")).toBeHidden();

    await page.goForward();
    await expect(page.locator("h1")).toHaveText("Studies");
  });

  test("only one case is ever on screen, across a long sequence of changes", async ({ page }) => {
    await page.goto(A4);
    const order = ["60", "0", "0.05", "20", "0.2", "2", "6", "0.6", "0"];
    for (const key of order) {
      await page.locator(`label[for="case-${slugFor(key)}"]`).click();
      expect(await visibleCase(page)).toEqual([key]);
      const visibleTables = await page
        .locator("table[id^='metrics-']:visible")
        .evaluateAll((els) => els.map((e) => e.id));
      expect(visibleTables).toEqual([`metrics-${slugFor(key)}`]);
    }
  });

  test("the full-dataset downloads never change with the selector", async ({ page }) => {
    await page.goto(A4);
    const full = page.locator(".explorer__downloads--full a");
    const before = await full.evaluateAll((as) => as.map((a) => a.getAttribute("href") ?? ""));
    await page.locator('label[for="case-20"]').click();
    const after = await full.evaluateAll((as) => as.map((a) => a.getAttribute("href") ?? ""));
    expect(after).toEqual(before);
    expect(before.every((h) => h.startsWith(BASE))).toBe(true);
    expect(before.some((h) => h.includes("scenarios_all"))).toBe(true);
  });

  test("the caveat travels with the case", async ({ page }) => {
    await page.goto(A4);
    await page.locator('label[for="case-0"]').click();
    await expect(page.locator('[data-case="0"] .callout')).toContainText("volumetric control");
    await page.locator('label[for="case-60"]').click();
    await expect(page.locator('[data-case="60"] .callout')).toContainText("extrapolation");
    await expect(page.locator('[data-case="60"] .callout')).toContainText(
      "not a mapped surface",
    );
  });
});
