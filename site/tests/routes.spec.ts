/**
 * Check 1 -- routing under the base path.
 *
 * Every route resolves, every in-page anchor has a target, every link and download the
 * pages emit is prefixed with the base and answers 200, and a direct refresh of a deep
 * route works. The last one is the check that catches a site which only ever worked
 * because the reader arrived through a client-side navigation.
 */
import { test, expect } from "@playwright/test";
import { BASE, ROUTES, NOT_FOUND_FILE, url } from "./support";

test.describe("routes", () => {
  for (const route of ROUTES) {
    test(`${route} responds 200 and carries one h1`, async ({ page }) => {
      const res = await page.goto(url(route), { waitUntil: "load" });
      expect(res?.status(), `status for ${route}`).toBe(200);
      await expect(page.locator("h1")).toHaveCount(1);
      await expect(page.locator("h1")).not.toBeEmpty();
      await expect(page).toHaveTitle(/.+/);
      /* The layout's own guarantees. */
      await expect(page.locator("html")).toHaveAttribute("lang", "en");
      await expect(page.locator("main#main")).toHaveCount(1);
      await expect(page.locator("a.skip-link")).toHaveAttribute("href", "#main");
    });
  }

  test("404.html is served for an unknown path, under a 404 status", async ({ page }) => {
    const res = await page.goto(url("/no/such/page/"), { waitUntil: "load" });
    expect(res?.status()).toBe(404);
    await expect(page.locator("h1")).toHaveCount(1);
    /* The 404 must offer a way back that is itself base-prefixed. */
    const hrefs = await page.locator("main a[href]").evaluateAll((as) =>
      as.map((a) => a.getAttribute("href") ?? ""),
    );
    const internal = hrefs.filter((h) => h.startsWith("/"));
    expect(internal.length).toBeGreaterThan(0);
    for (const h of internal) expect(h.startsWith(BASE), `404 link ${h}`).toBe(true);
  });

  test("the 404 document is also reachable as a file", async ({ request }) => {
    const res = await request.get(url(NOT_FOUND_FILE));
    expect(res.status()).toBe(200);
  });

  test("a direct refresh of a deep route works", async ({ page }) => {
    await page.goto(url("/studies/a4/"));
    await expect(page.locator("h1")).toContainText("straight p/Z line");
    const res = await page.reload({ waitUntil: "load" });
    expect(res?.status()).toBe(200);
    await expect(page.locator("h1")).toContainText("straight p/Z line");
    /* And with a query string and a fragment on the address, which is how a shared
       explorer link arrives. */
    const deep = await page.goto(url("/studies/a4/") + "?case=20#explorer", {
      waitUntil: "load",
    });
    expect(deep?.status()).toBe(200);
    await expect(page.locator("#explorer")).toBeVisible();
  });

  test("every internal link and asset on every route is base-prefixed and answers 200", async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000);
    const seen = new Map<string, string[]>();

    for (const route of ROUTES) {
      await page.goto(url(route));
      const refs = await page.evaluate(() => {
        const out: string[] = [];
        for (const a of Array.from(document.querySelectorAll<HTMLAnchorElement>("a[href]")))
          out.push(a.getAttribute("href") ?? "");
        for (const l of Array.from(document.querySelectorAll<HTMLLinkElement>("link[href]")))
          out.push(l.getAttribute("href") ?? "");
        for (const i of Array.from(document.querySelectorAll<HTMLImageElement>("img[src]")))
          out.push(i.getAttribute("src") ?? "");
        for (const s of Array.from(document.querySelectorAll<HTMLScriptElement>("script[src]")))
          out.push(s.getAttribute("src") ?? "");
        return out;
      });
      for (const ref of refs) {
        if (ref === "" || ref.startsWith("#") || ref.startsWith("mailto:")) continue;
        if (/^https?:\/\//i.test(ref)) continue; // external, checked separately
        if (!seen.has(ref)) seen.set(ref, []);
        seen.get(ref)!.push(route);
      }
    }

    const notPrefixed: string[] = [];
    const broken: string[] = [];

    for (const [ref, where] of seen) {
      if (!ref.startsWith("/")) {
        /* A relative reference is not wrong in itself, but this site's own rule is that
           every site URL goes through the helper, which emits absolute-with-base. */
        notPrefixed.push(`${ref} (relative) on ${where.join(", ")}`);
        continue;
      }
      if (!ref.startsWith(BASE)) {
        notPrefixed.push(`${ref} on ${where.join(", ")}`);
        continue;
      }
      const res = await request.get(ref, { maxRedirects: 5 });
      if (res.status() !== 200) broken.push(`${ref} -> ${res.status()} on ${where.join(", ")}`);
    }

    expect(notPrefixed, "references that do not carry the base").toEqual([]);
    expect(broken, "references that do not answer 200").toEqual([]);
    expect(seen.size).toBeGreaterThan(30);
  });

  test("no word runs into a link, and no link runs into a word", async ({ request }) => {
    /* Astro trims the whitespace between a word and an element that starts on the next
       source line, so `The\n<a>references section</a>` ships as `Thereferences section`.
       One such collision was in the delivered HTML of /studies/a4/ and is fixed with an
       explicit {" "}; this check is here so the next one is caught in the build rather
       than in a printout. SVG blocks are stripped first: their text runs are laid out by
       coordinate, not by whitespace. */
    const collisions: string[] = [];
    for (const route of ROUTES) {
      const body = (await (await request.get(url(route))).text()).replace(
        /<svg[\s\S]*?<\/svg>/g,
        "",
      );
      for (const m of body.matchAll(/[A-Za-z,;:)]<a\s[^>]*>[^<]{0,40}/g)) {
        collisions.push(`${route}: "${m[0].replace(/<[^>]*>/g, " ").slice(0, 50)}"`);
      }
      for (const m of body.matchAll(/<\/a>[A-Za-z][^<]{0,40}/g)) {
        collisions.push(`${route}: "${m[0].replace(/<[^>]*>/g, "").slice(0, 50)}"`);
      }
    }
    expect(collisions, "words touching a link with no space between them").toEqual([]);
  });

  test("every in-page anchor has a target on the page it is on", async ({ page }) => {
    const missing: string[] = [];
    for (const route of ROUTES) {
      await page.goto(url(route));
      const dangling = await page.evaluate(() => {
        const out: string[] = [];
        for (const a of Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href^="#"]'))) {
          const id = decodeURIComponent((a.getAttribute("href") ?? "#").slice(1));
          if (id === "") continue;
          if (!document.getElementById(id)) out.push(id);
        }
        return out;
      });
      for (const id of dangling) missing.push(`${route} -> #${id}`);
    }
    expect(missing, "anchors whose target id does not exist").toEqual([]);
  });

  test("an in-page anchor actually moves focus context to its section", async ({ page }) => {
    await page.goto(url("/studies/a4/"));
    /* The contents rail is a <details>; open it before operating its links. */
    const rail = page.locator("nav.contents details");
    if (await rail.count()) await rail.first().evaluate((d: HTMLDetailsElement) => (d.open = true));
    const link = page.locator('nav.contents a[href="#limits"]');
    await link.click();
    await expect(page).toHaveURL(/#limits$/);
    /* html { scroll-behavior: smooth } means the position is still moving when the click
       resolves. Wait for it to settle rather than sampling mid-flight. */
    await page.waitForFunction(() => {
      const w = window as unknown as { __y?: number; __n?: number };
      const y = Math.round(window.scrollY);
      if (w.__y === y) w.__n = (w.__n ?? 0) + 1;
      else {
        w.__y = y;
        w.__n = 0;
      }
      return (w.__n ?? 0) > 3;
    }, null, { polling: 100, timeout: 10_000 });
    const onScreen = await page.locator("#limits").evaluate((el) => {
      const r = el.getBoundingClientRect();
      return r.top >= -2 && r.top < window.innerHeight;
    });
    expect(onScreen, "#limits is in view after the anchor is followed").toBe(true);
  });

  test("navigation between routes works both directions, and history restores", async ({
    page,
  }) => {
    await page.goto(url("/"));
    await page.locator('a[href="' + url("/studies/") + '"]').first().click();
    await expect(page).toHaveURL(url("/studies/"));
    await page.locator('a[href="' + url("/studies/a4/") + '"]').first().click();
    await expect(page).toHaveURL(new RegExp(url("/studies/a4/").replace(/\//g, "\\/")));
    await page.goBack();
    await expect(page).toHaveURL(url("/studies/"));
    await page.goForward();
    await expect(page.locator("h1")).toContainText("straight p/Z line");
  });
});
