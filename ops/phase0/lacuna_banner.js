/* Drop-in for /registry/lacuna/index.html — include after the existing script tag:
 *   <script src="/registry/lacuna/lacuna_banner.js" defer></script>
 *
 * Reads the post-processed lacuna_candidates.json and, when observation is
 * paused, prepends an honest status banner and greys out stale rows. Uses only
 * fields added by truth_lacuna_candidates.py; harmless if they are absent.
 */
(function () {
  var SRC = "/registry/data/substrate/lacuna_candidates.json";

  function fmt(iso) { return iso ? iso.slice(0, 10) : "unknown"; }

  function banner(d) {
    var st = d.observation_status || {};
    var el = document.createElement("div");
    el.setAttribute("role", "status");
    el.style.cssText = "margin:16px auto;max-width:960px;padding:14px 18px;border-radius:10px;font:14px/1.5 system-ui,sans-serif;" +
      (st.state === "paused" ? "background:#fff7e6;border:1px solid #f0c36d;color:#5c3d00" : "background:#eefaf0;border:1px solid #9bd7a6;color:#124a1e");
    if (st.state === "paused") {
      el.innerHTML = "<strong>Observation paused since " + fmt(st.paused_since) + ".</strong> " +
        "The " + (d.n || 0) + " candidates below reflect the last completed observation cycle; no silence has been " +
        "added since. Figures on this page do not grow while observation is paused " +
        "(<a href='/registry/api/#silence' style='color:inherit'>how silence is counted</a>).";
    } else {
      el.innerHTML = "<strong>Observation active.</strong> Last negative observation " + fmt(st.last_observation_at) +
        "; " + (d.n_fresh || 0) + " of " + (d.n || 0) + " candidates observed in the last 7 days.";
    }
    el.id = "lacuna-observation-banner";
    el.style.cssText += ";position:relative;z-index:9999;display:block;max-width:none;margin:0;border-radius:0;text-align:center";
    document.body.insertBefore(el, document.body.firstChild);
  }

  function greyStale(d) {
    var stale = {};
    (d.candidates || []).forEach(function (c) { if (c.stale) stale[c.target_id] = true; });
    document.querySelectorAll("tr, li, .card").forEach(function (row) {
      var t = row.textContent || "";
      for (var id in stale) { if (t.indexOf(id) !== -1) { row.style.opacity = "0.55"; row.title = "stale: not observed in the last 7 days"; break; } }
    });
  }

  function start(d) {
    if (!d || !d.observation_status) return;
    banner(d);
    greyStale(d);
    // the table is rendered asynchronously by the page's own script: re-apply as rows appear
    var obs = new MutationObserver(function () { greyStale(d); });
    obs.observe(document.body, { childList: true, subtree: true });
    setTimeout(function () { obs.disconnect(); }, 30000);
  }

  fetch(SRC, { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (d) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", function () { start(d); });
    } else {
      start(d);
    }
  }).catch(function () { /* page keeps working without the banner */ });
})();
