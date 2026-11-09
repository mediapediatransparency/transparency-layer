// Wikipedia Transparency Layer: a badge of three dials on analysed articles, opening a panel.
// All data is inside the add-on (data.js); nothing is fetched and nothing is sent anywhere.
(function () {
  "use strict";
  var body = document.body;
  if (!body || !body.classList.contains("ns-0") || !body.classList.contains("action-view")) return;

  // The article shown, and the revision shown (from Wikipedia's own page settings).
  var title = null, rev = null;
  var can = document.querySelector('link[rel="canonical"]');
  if (can) {
    var m = can.href.match(/\/wiki\/([^?#]+)/);
    if (m) title = decodeURIComponent(m[1]).replace(/_/g, " ");
  }
  var scripts = document.querySelectorAll("script:not([src])");
  for (var i = 0; i < scripts.length && rev === null; i++) {
    var r = /"wgRevisionId":(\d+)/.exec(scripts[i].textContent);
    if (r) rev = +r[1];
  }
  if (!title) return;
  // The data stays in the add-on's background; this page receives only its own article's entry.
  chrome.runtime.sendMessage({get: title}, function (res) {
    if (chrome.runtime.lastError || !res) return;
    show(res.meta, res.e, res.site, res.n);
  });

  function show(D, e, SITE, nArticles) {

  // ---------------------------------------------------------------- helpers
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]; }); }
  function pc(x) { return x == null ? "–" : (x < 0.01 && x > 0 ? "<1%" : Math.round(x * 100) + "%"); }
  function sg(x, d) { return x == null ? "–" : (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(d == null ? 2 : d); }
  function ok(x, key) { return x && x[key] != null && x[key] >= D.min_cover; }

  // A half-circle dial. Needles: {v, cls}; ticks: {v}. Values outside the range sit at its ends.
  function dial(o) {
    var cx = 40, cy = 38, rad = 30;
    function pt(v, rr) {
      var t = (Math.max(o.min, Math.min(o.max, v)) - o.min) / (o.max - o.min), a = Math.PI * (1 - t);
      return [(cx + rr * Math.cos(a)).toFixed(1), (cy - rr * Math.sin(a)).toFixed(1)];
    }
    var s = '<svg viewBox="0 0 80 54" width="80" height="54" aria-hidden="true">' +
      '<path class="arc" d="M' + (cx - rad) + "," + cy + " A" + rad + "," + rad + " 0 0 1 " + (cx + rad) + "," + cy + '"/>';
    (o.ticks || []).forEach(function (t) {
      if (t.v == null) return;
      var a = pt(t.v, rad - 6), b = pt(t.v, rad + 5);
      s += '<line class="tick" x1="' + a[0] + '" y1="' + a[1] + '" x2="' + b[0] + '" y2="' + b[1] + '"/>';
    });
    (o.needles || []).forEach(function (n) {
      if (n.v == null) return;
      // the second needle is shorter and ends in a ring, so two close values stay apart
      var p = pt(n.v, n.cls === "n2" ? rad - 14 : rad - 4);
      s += '<line class="' + n.cls + '" x1="' + cx + '" y1="' + cy + '" x2="' + p[0] + '" y2="' + p[1] + '"/>' +
        (n.cls === "n2" ? '<circle class="ring" cx="' + p[0] + '" cy="' + p[1] + '" r="3.2"/>' : "");
    });
    s += '<circle class="hub" cx="' + cx + '" cy="' + cy + '" r="2.5"/>' +
      '<text class="end" x="' + (cx - rad) + '" y="' + (cy + 12) + '" text-anchor="middle">' + esc(o.lo) + "</text>" +
      '<text class="end" x="' + (cx + rad) + '" y="' + (cy + 12) + '" text-anchor="middle">' + esc(o.hi) + "</text>" +
      '<text class="mid" x="' + cx + '" y="' + (cy + 13) + '" text-anchor="middle">' + esc(o.mid) + "</text></svg>";
    return '<div class="dial">' + s + '<div class="cap">' + esc(o.cap) +
      (o.cov != null ? '<div class="cov">' + esc(o.cov) + "</div>" : "") + "</div></div>";
  }

  // ---------------------------------------------------------------- styles
  var CSS = [
    ":host{all:initial}",
    ".w{--bg:#fff;--fg:#202122;--mute:#54595d;--line:#c8ccd1;--soft:#f8f9fa;--n1:#202122;--n2:#72777d;--tick:#a2a9b1;",
    "font:13px/1.4 system-ui,-apple-system,'Segoe UI',sans-serif;color:var(--fg);position:fixed;right:16px;bottom:16px;z-index:2147483000;",
    "display:flex;flex-direction:column;align-items:flex-end;gap:8px;max-width:calc(100vw - 32px)}",
    ".w.dark{--bg:#101418;--fg:#eaecf0;--mute:#a2a9b1;--line:#54595d;--soft:#202122;--n1:#eaecf0;--n2:#a2a9b1;--tick:#72777d}",
    ".badge{display:flex;align-items:flex-end;gap:2px;background:var(--bg);border:1px solid var(--line);border-radius:10px;",
    "padding:4px 6px 4px 8px;box-shadow:0 2px 8px rgba(0,0,0,.15);cursor:pointer;user-select:none}",
    ".badge:focus-visible{outline:2px solid var(--n2);outline-offset:2px}",
    ".dial{display:flex;flex-direction:column;align-items:center;width:80px}",
    ".cap{font-size:10.5px;color:var(--mute);margin-top:-2px;text-align:center;line-height:1.15}.cov{font-size:9.5px;opacity:.85}",
    ".arc{fill:none;stroke:var(--line);stroke-width:5;stroke-linecap:round}",
    ".tick{stroke:var(--tick);stroke-width:2}",
    ".n1{stroke:var(--n1);stroke-width:2.5;stroke-linecap:round}",
    ".n2{stroke:var(--n2);stroke-width:2.5;stroke-linecap:round}.ring{fill:var(--bg);stroke:var(--n2);stroke-width:2}",
    ".hub{fill:var(--n1)}.end{font-size:8px;fill:var(--mute)}.mid{font-size:9.5px;fill:var(--fg);font-weight:600}",
    ".tag{font-size:10px;color:var(--mute);writing-mode:vertical-rl;transform:rotate(180deg);margin-right:2px;letter-spacing:.04em}",
    ".x{border:0;background:none;color:var(--mute);font-size:15px;cursor:pointer;padding:0 2px;align-self:flex-start}",
    ".panel{width:380px;max-width:100%;max-height:70vh;overflow:auto;background:var(--bg);border:1px solid var(--line);",
    "border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,.2);padding:12px 14px}",
    ".panel h2{font-size:14px;margin:0 0 4px}.panel h3{font-size:12.5px;margin:12px 0 4px;text-transform:uppercase;letter-spacing:.04em;color:var(--mute)}",
    ".panel p{margin:4px 0}.small{font-size:11.5px;color:var(--mute)}",
    ".panel table{border-collapse:collapse;width:100%}.panel td{padding:3px 4px;border-top:1px solid var(--line);vertical-align:top}",
    ".panel td.n{text-align:right;white-space:nowrap}.key{display:inline-block;width:18px;vertical-align:middle}",
    ".panel a{color:inherit}.pill{background:var(--bg);border:1px solid var(--line);border-radius:999px;padding:3px 10px;",
    "font-size:11px;color:var(--mute);cursor:pointer}"
  ].join("");

  // ---------------------------------------------------------------- build
  var host = document.createElement("div");
  host.id = "wtl-host";
  var root = host.attachShadow({mode: "open"});
  var w = document.createElement("div");
  w.className = "w";
  var html = document.documentElement.classList;
  var dark = html.contains("skin-theme-clientpref-night") ||
    (html.contains("skin-theme-clientpref-os") && window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches);
  if (dark) w.classList.add("dark");
  root.innerHTML = "<style>" + CSS + "</style>";
  root.appendChild(w);
  document.body.appendChild(host);

  if (!e) {
    w.innerHTML = '<button class="pill" title="Hide">Transparency Layer: this article is not among the ' +
      nArticles.toLocaleString() + " analysed ×</button>";
    w.firstChild.onclick = function () { host.remove(); };
    return;
  }

  var f = e.f, T = e.typical || {};
  var leanC = ok(f.lean_c, "citations_covered") ? f.lean_c.mean : null;
  var leanW = ok(f.lean_w, "text_covered") ? f.lean_w.mean : null;
  var qual = ok(f.qual_c, "citations_covered") ? f.qual_c.mean : null;
  var acad = ok(f.acad_c, "citations_covered") ? f.acad_c.mean : null;
  var robC = ok(f.rob_c, "citations_covered") ? f.rob_c.mean : null;
  var robW = ok(f.rob_w, "text_covered") ? f.rob_w.mean : null;
  function cv(x) { return x ? pc(x.citations_covered) + " rated" : "none rated"; }

  var badge =
    '<div class="badge" role="button" tabindex="0" aria-expanded="false" title="Transparency Layer: open the details">' +
    '<span class="tag">WTL</span>' +
    dial({min: -1, max: 1, lo: "left", hi: "right", mid: leanC == null ? "few rated" : sg(leanC),
          cap: "Source leaning", cov: cv(f.lean_c), needles: [{v: leanW, cls: "n2"}, {v: leanC, cls: "n1"}], ticks: [{v: D.baseline_lean}]}) +
    dial({min: 0, max: 1, lo: "0", hi: "1", mid: qual == null ? "few rated" : qual.toFixed(2),
          cap: "Website quality", cov: cv(f.qual_c), needles: [{v: qual, cls: "n1"}], ticks: [{v: T.qual_c}]}) +
    dial({min: 0, max: 3, lo: "0", hi: "3", mid: acad == null ? "few rated" : acad.toFixed(1),
          cap: "Academic level", cov: cv(f.acad_c), needles: [{v: acad, cls: "n1"}], ticks: [{v: T.acad_c}]}) +
    dial({min: 0, max: 1, lo: "0%", hi: "100%", mid: pc(f.top5),
          cap: "Top 5 editors wrote", needles: [{v: f.top5, cls: "n1"}], ticks: [{v: T.top5}]}) +
    '<button class="x" title="Hide for this page" aria-label="Hide">×</button></div>';

  function typ(k, fmt) {
    return T[k] == null ? "" : '<div class="small">similar: ' + (fmt || pc)(T[k]) + "</div>";
  }
  function mix(x, f2) {
    if (!x) return "none rated";
    return D.labels[f2].filter(function (l) { return x.mix[l]; })
      .map(function (l) { return esc(l) + " " + pc(x.mix[l]); }).join(", ") +
      (x.citations_covered != null ? " (" + pc(x.citations_covered) + " of citations rated)"
                                   : " (writers of " + pc(x.text_covered) + " of the text)");
  }
  function amix(x) {
    if (!x) return "–";
    return Object.keys(x.mix).sort(function (a, b) { return x.mix[b] - x.mix[a]; })
      .filter(function (l) { return x.mix[l] >= 0.005; })
      .map(function (l) { return esc(l) + " " + pc(x.mix[l]); }).join(", ");
  }
  var WP = {gr: "generally reliable", nc: "no consensus", gu: "generally unreliable", m: "varies",
            d: "deprecated", b: "blacklisted", "not listed": "not on the list"};
  var wp = f.wp ? Object.keys(WP).filter(function (k) { return f.wp.mix[k]; })
    .map(function (k) { return WP[k] + " " + pc(f.wp.mix[k]); }).join(", ") : "–";
  var FL = [["dead_link_no_archive", "Dead link, no archived copy"],
            ["not_english_no_quote", "Not in English, no quote or translation"],
            ["book_without_page", "Book with no page number"],
            ["paywall_or_registration", "Behind a paywall or registration"],
            ["opinion", "Opinion, comment or blog section"],
            ["not_english", "Not in English (all)"]];
  var same = rev === e.rev;
  var version = same
    ? "This version was analysed (" + esc(e.at) + ")."
    : "Figures describe the version of " + esc(e.at) + '; the page has been edited since (<a href="https://en.wikipedia.org/w/index.php?diff=cur&amp;oldid=' +
      e.rev + '">changes</a>).';
  var minF = (e.caveats || []).indexOf("minimum_figure") >= 0 || (e.caveats || []).indexOf("thin_sanctions_list") >= 0;
  var KEY1 = '<svg class="key" viewBox="0 0 18 8"><line x1="1" y1="4" x2="17" y2="4" stroke="currentColor" stroke-width="2.5"/></svg>';
  var KEY2 = '<svg class="key" viewBox="0 0 18 8"><line x1="1" y1="4" x2="12" y2="4" stroke="currentColor" stroke-width="2.5" opacity=".6"/><circle cx="14" cy="4" r="2.8" fill="none" stroke="currentColor" stroke-width="1.6" opacity=".6"/></svg>';
  var KEYT = '<svg class="key" viewBox="0 0 18 8"><line x1="9" y1="0" x2="9" y2="8" stroke="currentColor" stroke-width="2" opacity=".5"/></svg>';

  var panel =
    '<div class="panel" hidden>' +
    "<h2>" + esc(title) + "</h2>" +
    '<p class="small">' + version + " " + esc(e.kind) + (e.area ? " · " + esc(e.area) : "") + "</p>" +

    "<h3>Source leaning: audience left–right</h3>" +
    (f.books != null ? '<p class="small">' + pc(f.books) + " of this article's citations are books, journals or scholarly sites, which no open dataset rates for leaning; the figures below describe the rest.</p>" : "") +
    "<table><tr><td>" + KEY1 + " Cited in the article</td><td class='n'>" + sg(leanC) +
    '<div class="small">' + cv(f.lean_c) + "</div></td></tr>" +
    "<tr><td>" + KEY2 + " Cited by its writers, everywhere in the analysed articles</td><td class='n'>" + sg(leanW) +
    '<div class="small">' + (f.lean_w ? "writers of " + pc(f.lean_w.text_covered) + " of the text" : "too few rated") + "</div></td></tr>" +
    "<tr><td>" + KEYT + " All analysed articles</td><td class='n'>" + sg(D.baseline_lean) + "</td></tr>" +
    "<tr><td class='small'>Second measure (Robertson et al. 2018): cited / by its writers / all analysed</td><td class='n small'>" +
    sg(robC) + " / " + sg(robW) + " / " + sg(D.baseline_rob) + "</td></tr></table>" +
    '<p class="small">Audience leaning: where a site\'s audience of US Twitter users matched to voter records sits, from −1 (shared mostly by Democrats) to +1 (mostly by Republicans). Dial: DomainDemo (Yang et al. 2025). It describes who shares a site, not what it publishes, and zero is not a political centre: most sites fall below it, so compare with the line for all analysed articles. A needle is drawn only when ' +
    pc(D.min_cover) + " or more is rated. The writers' figure blends each writer's own sources by their share of this article's text; no single editor's figure is shown.</p>" +
    "<h3>Recorded political affiliation of the sources</h3>" +
    '<p class="small">What Wikidata and Wikipedia\'s categories record about each outlet or publisher (books included). Cited: ' + amix(f.aff_c) +
    ". By its writers: " + amix(f.aff_w) + ".</p>" +
    '<p class="small"><b>Media Bias/Fact Check</b> labels, cited: ' + mix(f.mbfc_c, "mbfc") + "; by its writers: " + mix(f.mbfc_w, "mbfc") + ".</p>" +
    '<p class="small"><b>AllSides (2018)</b> labels, cited: ' + mix(f.as_c, "allsides_2018") + "; by its writers: " + mix(f.as_w, "allsides_2018") + ".</p>" +

    "<h3>Evidence</h3><table>" +
    "<tr><td>Citations</td><td class='n'>" + (f.citations || 0).toLocaleString() + '<div class="small">' + (f.sources || 0).toLocaleString() + " sources</div></td></tr>" +
    "<tr><td>With a web link</td><td class='n'>" + pc(f.with_link) + typ("with_link") + "</td></tr>" +
    "<tr><td>Academic (journals, university presses, research institutes)</td><td class='n'>" + pc(f.academic) + typ("academic") + "</td></tr>" +
    "<tr><td>Website quality (Lin et al., 0–1)</td><td class='n'>" + (qual == null ? "–" : qual.toFixed(2)) +
    '<div class="small">' + cv(f.qual_c) + "</div>" + typ("qual_c", function (x) { return x.toFixed(2); }) + "</td></tr>" +
    "<tr><td>Academic level of publishers and journals (Finnish Publication Forum, 0–3)</td><td class='n'>" + (acad == null ? "–" : acad.toFixed(1)) +
    '<div class="small">' + cv(f.acad_c) + "</div>" + typ("acad_c", function (x) { return x.toFixed(1); }) + "</td></tr>" +
    "<tr><td>Wikipedia's own source ratings</td><td class='n small' style='white-space:normal'>" + wp + "</td></tr>" +
    FL.map(function (x) { return "<tr><td>" + x[1] + "</td><td class='n'>" + (f.flags[x[0]] || 0).toLocaleString() + "</td></tr>"; }).join("") +
    "</table>" +

    "<h3>Who wrote it</h3><table>" +
    "<tr><td>Top editor's share of the text</td><td class='n'>" + pc(f.top1) + "</td></tr>" +
    "<tr><td>Top 5 editors' share</td><td class='n'>" + pc(f.top5) + typ("top5") + "</td></tr>" +
    "<tr><td>Editors with text in it</td><td class='n'>" + (f.editors || 0).toLocaleString() +
    '<div class="small">' + (f.for50 || "–") + " wrote half</div></td></tr>" +
    "<tr><td>Written by editors Wikipedia sanctioned" + (minF ? '<div class="small">a minimum: the sanctions list is incomplete for this topic</div>' : "") +
    "</td><td class='n'>" + pc(f.sanctioned) + "</td></tr></table>" +

    '<p class="small">“Similar” is the middle value for ' + esc(e.group) + " (" + e.peers + " articles); the grey line on a dial marks it. " +
    "These figures are defined on the full report and draw no conclusions about the article or its editors.</p>" +
    (SITE ? '<p><a href="#" class="full">Full report →</a></p>' : "") +
    '<p class="small">Data from ' + esc(D.built) + ", carried inside the add-on. Nothing about the pages you read is sent anywhere.</p></div>";

  w.innerHTML = panel + badge;
  var b = w.querySelector(".badge"), p = w.querySelector(".panel");
  function toggle() { p.hidden = !p.hidden; b.setAttribute("aria-expanded", String(!p.hidden)); }
  b.addEventListener("click", function (ev) {
    if (ev.target.classList.contains("x")) { host.remove(); return; }
    toggle();
  });
  b.addEventListener("keydown", function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); toggle(); } });
  var full = w.querySelector(".full");
  if (full) full.addEventListener("click", function (ev) {
    ev.preventDefault();
    chrome.runtime.sendMessage({open: SITE + "articles/" + encodeURIComponent(e.slug) + ".html"});
  });
  }
})();
