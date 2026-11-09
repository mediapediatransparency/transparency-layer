// Holds the data (data.js, built by `wtl site`) and answers each Wikipedia page with the entry for
// its own article only. Nothing is fetched or sent: the data is part of the add-on.
importScripts("data.js");
try { importScripts("local.js"); } catch (err) { /* no local copy of the site linked */ }

chrome.runtime.onMessage.addListener(function (msg, sender, reply) {
  if (!msg) return;
  if (typeof msg.get === "string") {
    var D = self.WTL_DATA || {articles: {}};
    reply({e: D.articles[msg.get] || null, n: Object.keys(D.articles).length,
           site: typeof self.WTL_SITE === "string" ? self.WTL_SITE : null,
           meta: {built: D.built, min_cover: D.min_cover, baseline_lean: D.baseline_lean,
                  baseline_rob: D.baseline_rob, labels: D.labels}});
    return;
  }
  // Open the full report in a new tab (a Wikipedia page cannot open a file:// link itself).
  if (typeof msg.open === "string" && /\/articles\/[^/]+\.html$/.test(msg.open)) {
    chrome.tabs.create({url: msg.open});
  }
});
