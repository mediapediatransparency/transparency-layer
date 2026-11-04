"""Wikipedia's own records about a source, beyond the Perennial sources list.

- Reliable sources noticeboard: how many pages of the noticeboard and its archives mention the
  source (its web domain, or its name in quotation marks), found with Wikipedia's own search,
  with links. A mention is not a verdict: a discussion may conclude anything, or nothing.
- Spam blacklists: whether English Wikipedia's local spam blacklist or the Wikimedia-wide one
  blocks links to the domain, with the revision of each list used.

Lookups are cached per source; data/wp_discussions.json is rewritten after every run.
"""

import datetime as dt
import json
import re
import time

from .config import ROOT, user_agent
from .fetch import cache
from .fetch.mediawiki import api

WPD_JSON = ROOT / "data" / "wp_discussions.json"
RSN_PREFIX = "Wikipedia:Reliable sources/Noticeboard"
TITLES_KEPT = 10
BLACKLISTS = [("English Wikipedia spam blacklist", "en.wikipedia.org", "MediaWiki:Spam-blacklist"),
              ("Wikimedia global spam blacklist", "meta.wikimedia.org", "Spam blacklist")]


def terms_of(key: str, name: str | None) -> list[str]:
    """The web domain and the name, each searched as an exact phrase."""
    if key.startswith("name:"):
        return [name or key[5:]]
    t = [key]
    name = re.sub(r"^the\s+", "", name or "", flags=re.I)
    if name and name.lower() != key and len(name) >= 4:
        t.append(name)
    return t


def rsn(terms: list[str]) -> dict:
    q = " OR ".join(f'"{t}"' for t in terms)
    p = cache.path("wpdiscuss", "rsn", re.sub(r"\W+", "_", q.lower())[:120])
    hit = cache.load(p)
    if hit is not None:
        return hit
    d = api({"action": "query", "list": "search", "srsearch": f'{q} prefix:{RSN_PREFIX}',
             "srnamespace": "4", "srlimit": str(TITLES_KEPT), "srinfo": "totalhits", "srprop": ""})
    out = {"terms": terms, "pages": d["query"]["searchinfo"]["totalhits"],
           "titles": [x["title"] for x in d["query"]["search"]],
           "search_url": "https://en.wikipedia.org/w/index.php?" + __import__("urllib.parse").parse.urlencode(
               {"search": f'{q} prefix:{RSN_PREFIX}', "ns4": "1", "fulltext": "1"}),
           "checked": dt.date.today().isoformat()}
    cache.save(p, out)
    return out


def _blacklist(site: str, title: str) -> dict:
    import requests
    r = requests.get(f"https://{site}/w/api.php", params={
        "action": "query", "prop": "revisions", "titles": title, "rvprop": "ids|content",
        "rvslots": "main", "format": "json", "formatversion": "2"},
        headers={"User-Agent": user_agent()}, timeout=60).json()
    rev = r["query"]["pages"][0]["revisions"][0]
    pats = []
    for line in rev["slots"]["main"]["content"].splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            pats.append((line, re.compile(r"https?://+[a-z0-9_\-.]*(?:" + line + r")", re.I)))
        except re.error:
            continue
    return {"revision": rev["revid"], "url": f"https://{site}/w/index.php?oldid={rev['revid']}",
            "patterns": pats}


def build(keys_names: dict[str, str | None]) -> dict:
    """keys_names: {source key: name as cited or None}."""
    lists = []
    for label, site, title in BLACKLISTS:
        try:
            b = _blacklist(site, title)
            lists.append((label, b))
            print(f"  {label}: {len(b['patterns']):,} entries (revision {b['revision']})", flush=True)
        except Exception as ex:  # noqa: BLE001
            print(f"  {label} not read: {str(ex)[:100]}", flush=True)
    out = {}
    for i, (k, nm) in enumerate(sorted(keys_names.items()), 1):
        e = {}
        try:
            e["noticeboard"] = rsn(terms_of(k, nm))
        except Exception as ex:  # noqa: BLE001
            print(f"  {k}: {str(ex)[:100]}", flush=True)
        if not k.startswith("name:"):
            url = f"http://{k}/"
            hits = [{"list": label, "entry": pat, "list_revision": b["url"]}
                    for label, b in lists for pat, rx in b["patterns"] if rx.search(url)]
            if hits:
                e["blacklisted"] = hits[:3]
        out[k] = e
        if i % 500 == 0:
            print(f"  {i:,} of {len(keys_names):,}", flush=True)
        time.sleep(0.1)
    res = {"built": dt.date.today().isoformat(), "rule": __doc__.strip(),
           "blacklists": {label: b["url"] for label, b in lists}, "sources": out}
    WPD_JSON.write_text(json.dumps(res, ensure_ascii=False, indent=0, sort_keys=True) + "\n",
                        encoding="utf-8")
    n = sum(1 for v in out.values() if (v.get("noticeboard") or {}).get("pages"))
    b = sum(1 for v in out.values() if v.get("blacklisted"))
    print(f"wrote {WPD_JSON}: {len(out):,} sources; {n:,} mentioned on the noticeboard; "
          f"{b:,} on a spam blacklist", flush=True)
    return res


def load() -> dict:
    if not WPD_JSON.exists():
        return {}
    return json.loads(WPD_JSON.read_text(encoding="utf-8")).get("sources", {})
