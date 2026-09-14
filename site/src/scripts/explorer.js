/**
 * The scenario explorer's behaviour. Enhancement only.
 *
 * Everything this file does is reveal markup the build already produced. It computes no
 * value, draws nothing, fetches nothing and re-runs nothing; if it never executes, the
 * page still carries the base case in full, with its panels, both tables, its caveat and
 * its downloads. That is why the controls ship `hidden` and are revealed here: a control
 * that cannot work should not be on the page at all.
 *
 * The one rule worth stating as a rule: `apply()` is the only function that changes what
 * is visible, and it walks every `[data-case]` region in one pass. There is no code path
 * that can leave the metrics on one case and the charts on another.
 *
 * Plain JavaScript, and inlined verbatim by `ExplorerScenarios.astro`. It is written as
 * JavaScript rather than TypeScript so that the bytes a reader sees in the page are the
 * bytes in this file — no build step stands between them, and there is no second copy of
 * the logic to drift. `BaseLayout.astro` audits every `src` attribute on the page against
 * the URLs its helper issued, and a bundler-generated script URL is not one of them, so an
 * inline script is also the form this site's own build rules allow.
 */
(function () {
  var PARAM = "case";

  function init() {
    var root = document.querySelector("#explorer");
    if (!root) return;

    var controls = root.querySelector("[data-explorer-controls]");
    var staticNote = root.querySelector("[data-explorer-static]");
    var status = root.querySelector("[data-explorer-status]");
    var invalid = root.querySelector("[data-explorer-invalid]");
    var resetButton = root.querySelector("[data-explorer-reset]");
    var radios = Array.prototype.slice.call(
      root.querySelectorAll('input[name="explorer-case"]'),
    );
    var regions = Array.prototype.slice.call(root.querySelectorAll("[data-case]"));

    if (!controls || radios.length === 0 || regions.length === 0) return;

    var keys = radios.map(function (r) {
      return r.value;
    });
    /* The default case is named once, in the markup, by the build that knows which case
       the export flags as the base case. Reading it from the attribute rather than from
       which radio happens to carry `checked` keeps one source of truth, and keeps the
       fallback honest when the attribute names a case the control does not offer. */
    var declared = root.getAttribute("data-explorer-default");
    var defaultKey =
      declared !== null && keys.indexOf(declared) !== -1
        ? declared
        : (radios.filter(function (r) {
            return r.defaultChecked;
          })[0] || radios[0]).value;

    /* Reveal the controls, and retire the note that explains their absence. */
    controls.hidden = false;
    if (staticNote) staticNote.hidden = true;

    function radioFor(key) {
      return radios.filter(function (r) {
        return r.value === key;
      })[0];
    }

    /**
     * Show one case and hide the other seven, in a single pass.
     *
     * Focus is preserved deliberately. If the reader's focus is inside a region about to
     * be hidden — a disclosure control in the previous case's table, say — the browser
     * would otherwise drop focus to the document body and lose the reader's place, so it
     * is moved to the control for the case now showing.
     */
    function apply(key, announce) {
      var active = document.activeElement;
      var focusWasHidden = false;
      var i;

      for (i = 0; i < regions.length; i += 1) {
        var show = regions[i].getAttribute("data-case") === key;
        if (!show && active && regions[i].contains(active)) focusWasHidden = true;
        regions[i].hidden = !show;
      }

      for (i = 0; i < radios.length; i += 1) {
        radios[i].checked = radios[i].value === key;
      }

      var url = new URL(window.location.href);
      if (key === defaultKey) url.searchParams.delete(PARAM);
      else url.searchParams.set(PARAM, key);
      window.history.replaceState(null, "", url.pathname + url.search + url.hash);

      if (focusWasHidden) {
        var target = radioFor(key);
        if (target) target.focus();
      }

      if (status && announce) {
        status.textContent =
          "Showing the computed case J = " +
          key +
          " bbl/day/psi. This is a presentation change, not a rerun: every panel and number" +
          " it revealed was produced by the build.";
      }
    }

    /* Read `?case=` and validate it against the eight computed cases. */
    var requested = new URL(window.location.href).searchParams.get(PARAM);
    if (requested !== null && keys.indexOf(requested) === -1) {
      if (invalid) {
        invalid.textContent =
          'The address asked for case "' +
          requested +
          '", which is not one of the eight cases this study computed (' +
          keys.join(", ") +
          "). Nothing was interpolated. The base case, J = " +
          defaultKey +
          ", is shown instead.";
        invalid.hidden = false;
      }
      apply(defaultKey, false);
    } else {
      apply(requested === null ? defaultKey : requested, false);
    }

    radios.forEach(function (radio) {
      radio.addEventListener("change", function () {
        if (!radio.checked) return;
        if (invalid) invalid.hidden = true;
        apply(radio.value, true);
      });
    });

    if (resetButton) {
      resetButton.addEventListener("click", function () {
        if (invalid) invalid.hidden = true;
        apply(defaultKey, true);
        var target = radioFor(defaultKey);
        if (target) target.focus();
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
