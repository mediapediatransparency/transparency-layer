"""Fingerprints of cited websites that do not depend on reading the live site, by fixed rules.

Five parts, each saved per site as soon as it is done (cache/sitetrace/<part>/), so a run can
stop and resume; `data/sitetrace.json` is rewritten from everything done so far after each run.

- citations: what the citations in the analysed articles record about each site: the names
  editors gave it (work, website, newspaper, publisher ...), the earliest access date stated,
  and the earliest saved copy of a cited page (Internet Archive address with its timestamp).
  Read from the stored revisions, no network.
- saved copies: for sites that could not be read live (see wtl/siteprobe.py), the same facts
  siteprobe reads (registration numbers, statements, tracking IDs, structured data), read
  instead from saved copies: the Internet Archive's most recent good copy of the home page
  (from its capture index), the archived copies of the cited pages that the citations link
  to, the site's own about/legal pages as archived, and failing those the most recent copy
  in Common Crawl's public crawl.
- DNS: the site's name servers, mail servers, the domains its SPF record authorises to send
  mail, and site-verification codes in its TXT records (Google, Facebook, Microsoft and
  others), asked of this machine's configured DNS server. Other TXT content is not kept.
- certificate logs (sites that could not be read live): certificates issued for the site, from the public Certificate
  Transparency logs (crt.sh): the earliest seen, how many, and the other domains named on
  the same certificate. Certificates naming more than MAX_CERT_DOMAINS registrable domains
  are left out of the "named together" lists, because hosting companies issue such shared
  certificates for unrelated customers.

Groups: sites that share a verification code, or that are named on the same certificate, or
whose name servers, mail servers or SPF-authorised senders are on the domain of another cited
site (servers run by a commercial provider are recorded per site but not grouped). Values shared by more
than siteprobe.MAX_GROUP sites are treated as a common service and left out of the groups.
A shared value records only that the same value appears; small hosting companies also
produce shared values.

Registration after citation: where the domain's current registration (RDAP) began after the
earliest Internet Archive copy of a page on that domain that a citation links to, that is
recorded with both dates and the copy. Access dates are not used, because editors who update a
link to a site's new domain often keep the old access date. For these domains the titles part
records the home page's title in the archived copy nearest that date and its title today, so a
reader can see whether the same site is still there. Some registries report a transfer or
renewal as the start of registration, so a later date alone does not show a change of owner.

Link history (domains registered after they were cited): for every link to such a domain in an
analysed article, the revision that first added that web address to the article (searching the
full history, including text later removed, so a link that was only moved or re-typed keeps its
original date) and the revision that set the
link's url-status mark, with dates, from WikiWho's word origins; whether each came after the
registration began; and whether the citation keeps an archived-copy link. Accounts appear only as
one-way IDs in an ID space of their own. For links first added after registration began, the
home page's title in the Internet Archive's copy nearest the day the link was added
(`wtl sitetrace --part at-addition`). Accounts that added links to two or more such domains
after registration began are listed, counting only domains whose home page title changed (no
shared word of two or more letters, beyond common short words, between the title then and today).

Holder groups: among those domains, the ones that share a tracking or advertising account, a DNS
verification code, or the domain their home page now redirects to.

Link marks: each citation's own url-status (live, dead, usurped ...), counted per site and
article, so a reader can see how Wikipedia itself marks links to a site whose state changed.
"""

import datetime as dt
import gzip
import json
import re
import threading
import time
from collections import Counter, defaultdict
from html import unescape

from . import siteprobe, sources
from .config import ROOT, user_agent
from .fetch import cache

SITETRACE_JSON = ROOT / "data" / "sitetrace.json"
MAX_CERT_DOMAINS = 10
CC_INDEXES = 4           # most recent Common Crawl indexes searched
KEEP = 5

ARCHIVE_URL_PARAM = re.compile(r"\|\s*archive-?url\s*=\s*(https?://[^\s|}<]+)", re.I)
ACCESS_DATE = re.compile(r"\|\s*access-?date\s*=\s*([^|}]*)", re.I)
WB_TS = re.compile(r"^https?://(?:web\.)?archive\.org/web/(\d{8,14})[a-z_]*/(https?://.+)$", re.I)
VERIFY = re.compile(r"^\s*([\w.-]*(?:verification|verify|validation)[\w.-]*|MS|docusign)\s*[=:]\s*(\S+)\s*$", re.I)
NOT_HTML = re.compile(r"\.(?:jpe?g|png|gif|svg|webp|pdf|mp[34]|docx?|xlsx?|zip)(?:[?#]|$)", re.I)
URL_STATUS = re.compile(r"\|\s*(url-status|dead-?url)\s*=\s*([^|}]*)", re.I)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
SPF_INCLUDE = re.compile(r"\b(?:include|redirect)[:=]([A-Za-z0-9._-]+)", re.I)

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                       "august", "september", "october", "november", "december"], 1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9


def parse_date(s: str) -> str | None:
    """A full date written in a citation, as YYYY-MM-DD; None unless day, month and year are all given."""
    s = re.sub(r"<!--.*?-->|\{\{[^}]*\}\}", " ", s or "").strip()
    tries = [(r"(\d{4})-(\d{1,2})-(\d{1,2})", (1, 2, 3)),
             (r"(\d{1,2})\s+([A-Za-z]+)\.?,?\s+(\d{4})", (3, 2, 1)),
             (r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", (3, 1, 2))]
    for rx, (yi, mi, di) in tries:
        m = re.match(rx, s)
        if not m:
            continue
        mo = m.group(mi)
        mo = MONTHS.get(mo.lower()) if not mo.isdigit() else int(mo)
        try:
            return dt.date(int(m.group(yi)), mo, int(m.group(di))).isoformat() if mo else None
        except ValueError:
            return None
    return None


def _ts_date(ts: str) -> str | None:
    try:
        return dt.date(int(ts[:4]), int(ts[4:6]), int(ts[6:8])).isoformat()
    except ValueError:
        return None


# ---------------------------------------------------------------- citations (no network)

def citation_facts(records: list[dict], domains: set[str]) -> dict:
    """{domain: {citations, names, earliest_access, earliest_saved_copy, saved_copies, cited_urls}}."""
    from .fetch import mediawiki as mw
    out = defaultdict(lambda: {"citations": 0, "names": Counter(), "saved_copies": [], "cited_urls": [],
                               "marks": defaultdict(Counter)})
    for r in records:
        try:
            rev = mw.get_revision(r["revision"])
        except Exception:  # noqa: BLE001
            continue
        text, art = rev["content"], rev["title"]
        bodies = [text[s:e] for s, e in sources._templates(text, 0, len(text), sources.CITE_START)]
        bodies += [x.group(1) for x in sources.REF.finditer(text)
                   if not sources.CITE_START.search(x.group(1))]
        for body in bodies:
            m = sources.URL_PARAM.search(body) or sources.BARE_URL.search(body)
            if not m:
                continue
            url = m.group(1) if m.re is sources.URL_PARAM else m.group(0)
            arch = ARCHIVE_URL_PARAM.search(body)
            arch = arch.group(1) if arch else None
            wb = WB_TS.match(url)
            if wb:
                arch, url = url, wb.group(2)
            host = sources.host_of(url)
            dom = sources.registrable(host) if host else ""
            if dom not in domains:
                continue
            o = out[dom]
            o["citations"] += 1
            o["marks"][art][link_mark(body)] += 1
            for nm in sources.NAME_PARAM.finditer(body):
                v = sources.clean_name(nm.group(2))
                if v:
                    o["names"][v] += 1
            ev = {"article": art, "revision": r["revision"]}
            ad = ACCESS_DATE.search(body)
            ad = parse_date(ad.group(1)) if ad else None
            if ad and (not o.get("earliest_access") or ad < o["earliest_access"]["date"]):
                o["earliest_access"] = {"date": ad, **ev}
            wbm = WB_TS.match(arch or "")
            # only a saved copy of a page on this same domain is evidence about this domain
            if wbm and sources.registrable(sources.host_of(wbm.group(2)) or "x") != dom:
                wbm = None
            if wbm:
                d0 = _ts_date(wbm.group(1))
                if d0 and (not o.get("earliest_saved_copy") or d0 < o["earliest_saved_copy"]["date"]):
                    o["earliest_saved_copy"] = {"date": d0, "url": arch, **ev}
                if arch not in o["saved_copies"] and len(o["saved_copies"]) < KEEP:
                    o["saved_copies"].append(arch)
            if url not in o["cited_urls"] and len(o["cited_urls"]) < KEEP:
                o["cited_urls"].append(url)
    res = {}
    for d, o in out.items():
        res[d] = {**o, "names": [{"name": n, "citations": c} for n, c in o["names"].most_common(3)],
                  "marks": {a: dict(c) for a, c in o["marks"].items()}}
    return res


def link_mark(body: str) -> str:
    """How the citation itself marks its link: Wikipedia's url-status (live, dead, usurped, unfit,
    deviated), the older dead-url=yes/no, or "none" when the citation says nothing."""
    m = URL_STATUS.search(body)
    if not m:
        return "none"
    v = re.sub(r"<!--.*?-->", "", m.group(2), flags=re.S).strip().lower()
    if m.group(1).lower().startswith("dead"):
        return {"yes": "dead", "true": "dead", "y": "dead", "no": "live", "false": "live"}.get(v, v or "none")
    return v or "none"


def _title(html: str) -> str:
    m = TITLE.search(html or "")
    return " ".join(unescape(m.group(1)).split())[:200] if m else ""


def then_now(domain: str, e: dict) -> dict:
    """For a domain registered after it was cited: the home page's title in the Internet Archive's
    copy nearest the cited copy's date, and the title the home page shows today."""
    ev = e["registered_after_citation"]["earlier"][0]
    ts = WB_TS.match(ev["url"]).group(1)
    old = _wb(f"https://web.archive.org/web/{ts}id_/http://{domain}/")
    now = siteprobe._get(f"https://{domain}/")
    if not (now.get("status") and now["status"] < 400):
        now = siteprobe._get(f"http://{domain}/")
    r = {"domain": domain, "checked": dt.date.today().isoformat(),
         "then_url": f"https://web.archive.org/web/{ts}/http://{domain}/",
         "then_title": _title(old.get("text")) if (old.get("status") or 0) < 400 else "",
         "now_status": now.get("status") or (now.get("error") or "")[:80],
         "now_url": now.get("url") or "",
         "now_title": _title(now.get("text")) if (now.get("status") or 0) < 400 else ""}
    if not (old.get("status") or 0):   # the archive did not answer: not saved, tried again later
        raise RuntimeError("no answer from the Internet Archive; try again later")
    cache.save(cache.path("sitetrace", "titles", domain), r)
    return r


# ---------------------------------------------------------------- saved copies

_WB = threading.Semaphore(2)
_wb_last, _wb_lock = [0.0], threading.Lock()


def _wb(url: str) -> dict:
    """GET from the Internet Archive, two at a time and two seconds apart."""
    with _WB:
        with _wb_lock:
            wait = siteprobe._ARCHIVE_GAP - (time.monotonic() - _wb_last[0])
            if wait > 0:
                time.sleep(wait)
            _wb_last[0] = time.monotonic()
        return siteprobe._get(url)


def _raw_copy(url: str) -> str:
    """The archived page itself, without the archive's toolbar (the id_ form)."""
    m = WB_TS.match(url)
    return f"https://web.archive.org/web/{m.group(1)}id_/{m.group(2)}" if m else url


def _cdx_latest(domain: str) -> list[tuple[str, str]]:
    import requests
    out = []
    for target in (f"{domain}/", f"www.{domain}/"):
        try:
            with _WB:
                time.sleep(siteprobe._ARCHIVE_GAP)
                r = requests.get("https://web.archive.org/cdx/search/cdx", params={
                    "url": target, "output": "json", "filter": ["statuscode:200", "mimetype:text/html"],
                    "fl": "timestamp,original", "limit": "-1"}, headers={"User-Agent": user_agent()},
                    timeout=60)
            rows = r.json() if r.status_code == 200 and r.text.strip() else []
        except Exception:  # noqa: BLE001
            rows = []
        out += [(t, o) for t, o in rows[1:]]
    return sorted(out, reverse=True)[:1]


_cc_index = []


def _cc_indexes() -> list[str]:
    import requests
    if not _cc_index:
        p = cache.path("sitetrace_meta", "cc_collinfo_" + dt.date.today().strftime("%Y-%m"))
        d = cache.load(p)
        if d is None:
            d = requests.get("https://index.commoncrawl.org/collinfo.json",
                             headers={"User-Agent": user_agent()}, timeout=60).json()
            cache.save(p, d)
        _cc_index.extend(x["cdx-api"] for x in d[:CC_INDEXES])
    return _cc_index


def _cc_get(domain: str) -> dict | None:
    """The most recent copy of the home page in Common Crawl, read from its public WARC files."""
    import requests
    for api in _cc_indexes():
        for target in (f"{domain}/", f"www.{domain}/"):
            try:
                r = requests.get(api, params={"url": target, "output": "json", "filter": "status:200",
                                              "limit": "1"}, headers={"User-Agent": user_agent()}, timeout=60)
                time.sleep(1)
                if r.status_code != 200 or not r.text.strip():
                    continue
                x = json.loads(r.text.splitlines()[0])
                off, ln = int(x["offset"]), int(x["length"])
                w = requests.get("https://data.commoncrawl.org/" + x["filename"],
                                 headers={"User-Agent": user_agent(), "Range": f"bytes={off}-{off + ln - 1}"},
                                 timeout=60)
                raw = gzip.decompress(w.content)
                parts = raw.split(b"\r\n\r\n", 2)        # WARC headers, HTTP headers, body
                if len(parts) < 3:
                    continue
                head, body = parts[1].decode("latin-1"), parts[2][:siteprobe.MAX_BYTES]
                m = re.search(r"charset=([\w-]+)", head, re.I) or re.search(
                    r"<meta[^>]+charset=[\"']?([\w-]+)", body[:4000].decode("latin-1"), re.I)
                try:
                    text = body.decode(m.group(1) if m else "utf-8", errors="replace")
                except LookupError:
                    text = body.decode("utf-8", errors="replace")
                return {"url": x["url"], "captured": x["timestamp"], "text": text,
                        "copy": "Common Crawl", "index": api.rsplit("/", 1)[-1]}
            except Exception:  # noqa: BLE001
                continue
    return None


def saved_copies(domain: str, cited: dict) -> dict:
    p = cache.path("sitetrace", "copies", domain)
    hit = cache.load(p)
    if hit is not None:
        return hit
    pages, read = [], []
    home = None
    for ts, orig in _cdx_latest(domain):
        g = _wb(f"https://web.archive.org/web/{ts}id_/{orig}")
        if g.get("status") and g["status"] < 400 and g.get("text"):
            home = {"url": f"https://web.archive.org/web/{ts}/{orig}", "captured": ts, "text": g["text"],
                    "copy": "Internet Archive", "original": orig}
    if home is None:
        home = _cc_get(domain)
    if home:
        pages.append({"kind": "home", "url": home["url"], "text": home["text"]})
        read.append({k: home[k] for k in ("url", "captured", "copy") if k in home} | {"kind": "home"})
        base = home.get("original") or f"https://{domain}/"
        html = re.sub(r"https?://web\.archive\.org/web/[^/]+/", "", home["text"])
        for kind, u in siteprobe._about_links(base, html):
            g = _wb(siteprobe.ARCHIVE_PREFIX + u)
            if g.get("status") and g["status"] < 400 and g.get("text"):
                pages.append({"kind": kind, "url": u, "text": g["text"]})
                read.append({"kind": kind, "url": "https://web.archive.org/web/2026/" + u,
                             "copy": "Internet Archive"})
    # cited pages are articles, not self-descriptions: only the site-wide parts are read from them
    # (tracking IDs, copyright line, declared organisation), not statements or registry numbers
    cited_pages = []
    for u in [x for x in (cited.get("saved_copies") or []) if not NOT_HTML.search(x)][:2]:
        g = _wb(_raw_copy(u))
        if g.get("status") and g["status"] < 400 and g.get("text"):
            cited_pages.append({"kind": "cited page", "url": u, "text": g["text"]})
            read.append({"kind": "cited page", "url": u, "copy": "Internet Archive",
                         "captured": (WB_TS.match(u) or [None, None])[1]})
    facts = siteprobe.extract(pages) if pages else {}
    if cited_pages:
        more = siteprobe.extract(cited_pages)
        def key(k, v):     # the same ID or text found on another page is not counted twice
            return (v["service"], v["id"]) if k == "trackers" else json.dumps(
                {a: b for a, b in v.items() if a != "page"} if isinstance(v, dict) else v, sort_keys=True)
        for k in ("trackers", "copyright", "declared_organisation"):
            seen = {key(k, v) for v in facts.get(k, [])}
            facts[k] = facts.get(k, []) + [v for v in more.get(k, []) if key(k, v) not in seen]
    out = {"domain": domain, "checked": dt.date.today().isoformat(), "pages": read,
           "status": "read from saved copies" if pages or cited_pages else "no saved copy found",
           **facts}
    cache.save(p, out)
    return out


# ---------------------------------------------------------------- DNS

def _dig(name: str, rtype: str) -> list[str]:
    import subprocess
    from .fetch import dnsfallback
    ns = dnsfallback._nameserver()
    cmd = ["dig", "+short", "+time=5", "+tries=2"] + ([f"@{ns}"] if ns else []) + [name, rtype]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.splitlines()
    except Exception:  # noqa: BLE001
        return []


def _reg(host: str) -> str:
    h = host.strip().rstrip(".").lower()
    return sources.registrable(h) if "." in h else ""


def dns(domain: str) -> dict:
    p = cache.path("sitetrace", "dns", domain)
    hit = cache.load(p)
    if hit is not None:
        return hit
    ns = sorted({_reg(x) for x in _dig(domain, "NS") if _reg(x)})
    mx = sorted({_reg(x.split()[-1]) for x in _dig(domain, "MX") if x.split() and _reg(x.split()[-1])})
    txt = [" ".join(re.findall(r'"([^"]*)"', x)) or x for x in _dig(domain, "TXT")]
    codes, spf = set(), set()
    for t in txt:
        m = VERIFY.match(t)
        if m:
            codes.add(f"{m.group(1).lower()}={m.group(2)}")
        if t.lower().startswith("v=spf1"):
            spf |= {_reg(x) for x in SPF_INCLUDE.findall(t) if _reg(x)}
    out = {"domain": domain, "checked": dt.date.today().isoformat(),
           "name_servers": [x for x in ns if x != domain], "mail_servers": [x for x in mx if x != domain],
           "spf_domains": sorted(x for x in spf if x != domain), "verification_codes": sorted(codes),
           "own_name_servers": domain in ns}
    cache.save(p, out)
    return out


# ---------------------------------------------------------------- certificate logs

_CT = threading.Semaphore(2)


def certificates(domain: str) -> dict:
    import requests
    p = cache.path("sitetrace", "ct", domain)
    hit = cache.load(p)
    if hit is not None:
        return hit
    rows, err = None, None
    for attempt in range(3):
        try:
            with _CT:
                r = requests.get("https://crt.sh/", params={"q": domain, "output": "json"},
                                 headers={"User-Agent": user_agent()}, timeout=120)
                time.sleep(1)
            if r.status_code == 200:
                rows = r.json()
                break
            err = f"HTTP {r.status_code}"
        except Exception as ex:  # noqa: BLE001
            err = f"{type(ex).__name__}"
        time.sleep(10 * (attempt + 1))
    if rows is None:
        return {"domain": domain, "error": err}      # not cached: tried again in a later run
    seen, together = set(), {}
    first = None
    for c in rows:
        if c.get("id") in seen:
            continue
        seen.add(c.get("id"))
        nb = (c.get("not_before") or "")[:10]
        first = min(first, nb) if first and nb else (first or nb or None)
        regs = {_reg(n.lstrip("*.")) for n in (c.get("name_value") or "").split("\n")} - {""}
        if len(regs) > MAX_CERT_DOMAINS:
            continue
        for o in regs - {domain}:
            t = together.setdefault(o, {"domain": o, "certificates": 0, "first": nb,
                                        "example": f"https://crt.sh/?id={c.get('id')}"})
            t["certificates"] += 1
            if nb and nb < t["first"]:
                t["first"], t["example"] = nb, f"https://crt.sh/?id={c.get('id')}"
    out = {"domain": domain, "checked": dt.date.today().isoformat(), "certificates": len(seen),
           "first_seen": first, "search": f"https://crt.sh/?q={domain}",
           "named_with": sorted(together.values(), key=lambda t: (-t["certificates"], t["domain"]))[:20]}
    cache.save(p, out)
    return out


# ---------------------------------------------------------------- runs and summary

PARTS = ("copies", "dns", "ct", "titles")


def _probed() -> dict:
    s = json.loads(siteprobe.SITEPROBE_JSON.read_text(encoding="utf-8")) if siteprobe.SITEPROBE_JSON.exists() else {}
    return s.get("sites", {})


def _order(probed: dict) -> list[str]:
    """Unreadable sites first, then those read only from a saved copy, then the rest."""
    def rank(d):
        s = probed[d].get("status", "")
        return (0 if s.startswith("not reachable") else 1 if "Archive" in s else 2, d)
    return sorted(probed, key=rank)


def run(records: list[dict], part: str, batch: int) -> None:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    probed = _probed()
    order = _order(probed)
    if part in ("copies", "ct"):   # certificate logs only for sites that could not be read live
        order = [d for d in order if probed[d].get("status", "").startswith("not reachable")]
    if part == "titles":   # only for domains registered after they were cited
        traced = load().get("sites", {})
        order = [d for d in order if (traced.get(d) or {}).get("registered_after_citation")]
    if part == "copies":
        cited = citation_facts(records, set(order))
    todo = [d for d in order if cache.load(cache.path("sitetrace", part, d)) is None]
    print(f"  {part}: {len(todo):,} sites still to do; this batch: {min(batch, len(todo)):,}", flush=True)
    fn = {"copies": lambda d: saved_copies(d, cited.get(d, {})), "dns": dns, "ct": certificates,
          "titles": lambda d: then_now(d, traced[d])}[part]
    workers = {"copies": 4, "dns": 8, "ct": 2, "titles": 3}[part]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, d): d for d in todo[:batch]}
        for i, f in enumerate(as_completed(futs), 1):
            d = futs[f]
            try:
                r = f.result()
            except Exception as e:  # noqa: BLE001  not cached; tried again next run
                print(f"  [{i}] {d}: error {str(e)[:100]}", flush=True)
                continue
            if part == "copies":
                print(f"  [{i}] {d}: {r['status']}, {len(r.get('registry_ids', []))} registry IDs, "
                      f"{len(r.get('trackers', []))} tracking IDs", flush=True)
            elif part == "ct" and r.get("error"):
                print(f"  [{i}] {d}: certificate search failed ({r['error']}); tried again later", flush=True)
            elif i % 100 == 0:
                print(f"  [{i}] done", flush=True)
    s = write_summary(records)
    print(f"wrote {SITETRACE_JSON}: {len(s['sites']):,} sites", flush=True)


def _groups(values: dict[str, list[str]]) -> tuple[list[dict], list[dict]]:
    by = defaultdict(set)
    for d, vs in values.items():
        for v in vs:
            by[v].add(d)
    keep = [{"value": v, "sites": sorted(s)} for v, s in sorted(by.items()) if 2 <= len(s) <= siteprobe.MAX_GROUP]
    common = [{"value": v, "sites": len(s)} for v, s in sorted(by.items()) if len(s) > siteprobe.MAX_GROUP]
    return keep, common


def summary(records: list[dict]) -> dict:
    probed = _probed()
    cited = citation_facts(records, set(probed))
    sites = {}
    for d in probed:
        e = {}
        if d in cited:
            e["citations_record"] = cited[d]
        for part in PARTS:
            x = cache.load(cache.path("sitetrace", part, d))
            if x is not None:
                e[part] = {k: v for k, v in x.items() if k != "domain"}
        reg = ((probed[d].get("rdap") or {}).get("registered") or "")[:10]
        c = cited.get(d, {})
        # access dates are not used: editors who update a link to a site's new domain often keep
        # the old access date, so only an archived copy of a page on this very domain counts
        ev = [("the Internet Archive's copy of a page cited from it", c.get("earliest_saved_copy"))]
        after = [{"evidence": what, **x} for what, x in ev if x and reg and reg > x["date"]]
        if after:
            e["registered_after_citation"] = {"registered": reg, "rdap": (probed[d].get("rdap") or {}).get("url"),
                                              "earlier": after}
        if e:
            sites[d] = e
    dnsv = {d: e["dns"] for d, e in sites.items() if "dns" in e}
    groups = {}
    for label, field in (("verification code", "verification_codes"), ("name-server domain", "name_servers"),
                         ("SPF-authorised domain", "spf_domains"), ("mail-server domain", "mail_servers")):
        own = field != "verification_codes"
        # name, mail and SPF domains are grouped only when the domain is itself a cited site, i.e.
        # the sites use servers run on another cited site's domain; commercial providers are not
        keep, common = _groups({d: [v for v in x.get(field, []) if not own or v in probed]
                                for d, x in dnsv.items()})
        groups[label] = {"groups": keep, "common_left_out": common}
    cited_set = set(probed)
    pairs = set()
    for d, e in sites.items():
        for t in (e.get("ct") or {}).get("named_with", []):
            o = t["domain"]
            # a domain and its own subdomain (or a public suffix taken for a site) are not a pair
            if o in cited_set and o != d and not (o.endswith("." + d) or d.endswith("." + o)):
                pairs.add(tuple(sorted((d, t["domain"]))))
    groups["named on the same certificate"] = {"pairs": [list(p) for p in sorted(pairs)]}
    for d, links in link_history(records, sites).items():
        sites[d]["links"] = links
        at = cache.load(cache.path("sitetrace", "at_addition", d)) or {}
        for x in links:
            if x["added"] in at:
                x["home_title_when_added"] = at[x["added"]]
    for d, e in sites.items():
        ra, tn = e.get("registered_after_citation"), e.get("titles")
        if ra and tn:
            ra["title_changed"] = title_changed(tn.get("then_title"), tn.get("now_title"))
    return {"built": dt.date.today().isoformat(), "rule": __doc__.strip(), "sites": sites,
            "groups": groups, "reregistered_groups": holder_groups(sites),
            "accounts_adding_after_registration": accounts_adding(sites)}


TOKEN = re.compile(r"\w+|[^\w\s]")


def _param_before(tokens, i):
    """Name of the template parameter whose value holds token i ('' for a bare link)."""
    j = i - 1
    while j >= 0 and tokens[j][0] not in ("|", "{{", "[", "<"):
        j -= 1
    if j < 0 or tokens[j][0] != "|":
        return ""
    k = j + 1
    name = []
    while k < i and tokens[k][0] != "=":
        name.append(tokens[k][0])
        k += 1
    return "".join(name).strip().lower() if k < i else ""


def _template_span(tokens, i, reach=400):
    """Token range of the citation around token i: back to '{{' or '<ref', on to '}}' or '</'."""
    a = i
    while a > max(0, i - reach) and tokens[a][0] not in ("{{", "<"):
        a -= 1
    b = i
    while b < min(len(tokens), i + reach) and tokens[b][0] not in ("}}", "<"):
        b += 1
    return a, b


def _mark_in(tokens, a, b):
    """(mark, origin revision of the mark's value) for a url-status / dead-url parameter in a..b."""
    for j in range(a, b):
        if tokens[j][0] != "|":
            continue
        k, name = j + 1, []
        while k < b and tokens[k][0] not in ("=", "|"):
            name.append(tokens[k][0])
            k += 1
        nm = "".join(name).lower()
        if k < b and tokens[k][0] == "=" and nm in ("url-status", "urlstatus", "dead-url", "deadurl"):
            v = k + 1
            if v < b and tokens[v][0] not in ("|", "}}"):
                val = tokens[v][0].lower()
                if nm.startswith("dead"):
                    val = {"yes": "dead", "true": "dead", "y": "dead", "no": "live", "false": "live"}.get(val, val)
                return val, tokens[v][1]
    return None, None


def _first_seen_index(allc: dict, revid: int):
    """A function: token sequence -> the earliest origin revision (up to revid) of that exact
    sequence anywhere in the article's full token history, including removed text; or None.
    WikiWho numbers tokens in the order it first saw them, so text added together is contiguous."""
    import bisect
    toks = [t for t in allc["tokens"] if len(t) > 3]
    starts, pos, parts = [], 0, []
    for t in toks:
        starts.append(pos)
        parts.append(t[3])
        pos += len(t[3]) + 1
    joined = "\x00".join(parts)
    def first(seq):
        if not seq:
            return None
        needle = "\x00".join(seq)
        best, at = None, joined.find(needle)
        while at >= 0:
            j = bisect.bisect_right(starts, at) - 1
            if starts[j] == at:
                o = toks[j][0]
                if o <= revid and (best is None or o < best):
                    best = o
            at = joined.find(needle, at + 1)
        return best
    return first


def link_history(records: list[dict], sites: dict) -> dict:
    """For each domain registered after it was cited: every link to it in the analysed articles,
    with the revision that added the domain to the article's text and the revision that set the
    link's url-status mark (WikiWho origin revisions, read from cache; no network). Accounts are
    kept only as one-way IDs, in an ID space of their own (not the editors page's pattern IDs)."""
    from . import patterns
    from .fetch import mediawiki as mw
    from .fetch import wikiwho as ww
    from .metrics import authorship as au
    targets = {d: e["registered_after_citation"]["registered"] for d, e in sites.items()
               if e.get("registered_after_citation")}
    seqs = {d: [t for t in TOKEN.findall(d.lower())] for d in targets}
    secret = patterns._secret()
    out = defaultdict(list)
    for r in records:
        doms = {x["source"] for x in (r.get("sources") or {}).get("list", [])} & set(targets)
        if not doms:
            continue
        try:
            rc = ww.rev_content(r["revision"])
            hist = au.History(mw.get_history(rc["page_id"], r["revision"]))
        except Exception:  # noqa: BLE001
            continue
        toks = rc["tokens"]
        strs = [t[0] for t in toks]
        allc = cache.load(cache.path("wikiwho", "all_content_v2", str(rc["page_id"])))
        first_seen = _first_seen_index(allc, r["revision"]) if allc else None
        for d in doms:
            sq, n = seqs[d], len(seqs[d])
            for i in range(1, len(strs) - n):
                if strs[i:i + n] != sq or strs[i - 1] not in (".", "/") or (
                        i + n < len(strs) and strs[i + n] not in ("/", "|", "]", " ", "}}", "?", "#", ":")
                        and not strs[i + n].startswith(("/", "|", "]"))):
                    continue
                param = _param_before(toks, i)
                if param.startswith("archive") or not (param.endswith("url") or param == ""):
                    continue
                if param == "" and "http" not in strs[max(0, i - 8):i]:
                    continue
                a, b = _template_span(toks, i)
                mark, mark_rev = _mark_in(toks, a, b)
                has_arch = any(strs[j] == "archive" and j + 2 < b and strs[j + 1] == "-" and strs[j + 2] == "url"
                               for j in range(a, b))
                o_rev = toks[i][1]
                # the same web address may have been in the article before, and only moved or
                # re-typed in this revision; date the link from its first appearance
                url_seq = []
                k = i
                while k < len(strs) and strs[k] not in ("|", "]", "}}", "<", "{{") and len(url_seq) < 40:
                    url_seq.append(strs[k])
                    k += 1
                first = first_seen(url_seq) if first_seen else None
                text_rev = o_rev
                if first and first < o_rev:
                    o_rev = first
                h = hist.by_id.get(o_rev) or {}
                key = au.editor_key(o_rev, toks[i][2], hist)[0]
                ent = {"article": r["article"], "revision": r["revision"], "added_revision": o_rev,
                       **({"text_revision": text_rev} if text_rev != o_rev else {}),
                       "added": (h.get("timestamp") or "")[:10],
                       # a separate ID space from the editors page, so the two cannot be matched
                       "added_by_id": patterns.pattern_id("links:" + key, secret),
                       "mark": mark or "none", "archive_link": has_arch}
                if mark_rev:
                    mh = hist.by_id.get(mark_rev) or {}
                    ent["mark_revision"] = mark_rev
                    ent["mark_set"] = (mh.get("timestamp") or "")[:10]
                ent["added_after_registration"] = bool(ent["added"] and ent["added"] > targets[d])
                ent["mark_set_after_registration"] = bool(ent.get("mark_set") and ent["mark_set"] > targets[d])
                out[d].append(ent)
    return dict(out)


TITLE_STOP = {"the", "of", "and", "in", "on", "for", "to", "a", "an", "at", "by", "with", "from", "is",
              "home", "page", "welcome", "index", "official", "site", "website", "news", "online",
              "de", "la", "le", "les", "el", "los", "las", "et", "en", "di", "da", "do", "der", "die",
              "das", "und", "og", "och", "i", "na", "za", "www", "com", "org", "net"}


def titles_at_addition(sites: dict) -> int:
    """For links first added after the domain's registration began: the home page's title in the
    Internet Archive's copy nearest the day the link was added (cache/sitetrace/at_addition/).
    Returns how many dates were looked up."""
    n = 0
    for d, e in sites.items():
        days = sorted({x["added"] for x in e.get("links", []) if x.get("added_after_registration") and x["added"]})
        if not days:
            continue
        p = cache.path("sitetrace", "at_addition", d)
        got = cache.load(p) or {}
        for day in days:
            if day in got:
                continue
            ts = day.replace("-", "")
            r = _wb(f"https://web.archive.org/web/{ts}id_/http://{d}/")
            if not r.get("status"):
                continue           # the archive did not answer; tried again next run
            got[day] = {"title": _title(r.get("text")) if r["status"] < 400 else "",
                        "status": r["status"], "copy": f"https://web.archive.org/web/{ts}/http://{d}/"}
            n += 1
            cache.save(p, got)
    return n


def title_changed(then: str, now: str) -> bool | None:
    """True when the home page titles then and today share no word of two or more letters (common
    short words such as "the", "of", "and" do not count); None when either title is missing."""
    w = lambda t: {x.casefold() for x in re.findall(r"\w{2,}", t or "")} - TITLE_STOP
    a, b = w(then), w(now)
    if not a or not b:
        return None
    return not (a & b)


def accounts_adding(sites: dict) -> list[dict]:
    """Accounts (one-way IDs) that added links to two or more domains after the domain's
    registration began, counting only domains whose home page title changed (title_changed)."""
    by = defaultdict(lambda: {"domains": set(), "articles": set(), "links": 0})
    for d, e in sites.items():
        if not (e.get("registered_after_citation") or {}).get("title_changed"):
            continue
        for x in e.get("links", []):
            if x["added_after_registration"]:
                b = by[x["added_by_id"]]
                b["domains"].add(d)
                b["articles"].add(x["article"])
                b["links"] += 1
    return [{"id": k, "domains": sorted(v["domains"]), "articles": sorted(v["articles"]), "links": v["links"]}
            for k, v in sorted(by.items(), key=lambda kv: (-len(kv[1]["domains"]), kv[0]))
            if len(v["domains"]) >= 2]


def holder_groups(sites: dict) -> dict:
    """Among domains registered after they were cited: the ones sharing a tracking or advertising
    account read from the live site, a DNS verification code, or the domain their home page
    redirects to. Any size; this set is small."""
    probed = _probed()
    rereg = [d for d, e in sites.items() if e.get("registered_after_citation")]
    vals = {"tracking or advertising account": {}, "verification code": {}, "redirect target": {}}
    for d in rereg:
        e = sites[d]
        vals["tracking or advertising account"][d] = [f"{t['service']} {t['id']}" for t in
                                                      (probed.get(d) or {}).get("trackers", [])]
        vals["verification code"][d] = (e.get("dns") or {}).get("verification_codes", [])
        now = (e.get("titles") or {}).get("now_url") or ""
        h = sources.host_of(now) if now else ""
        tgt = sources.registrable(h) if h else ""
        vals["redirect target"][d] = [tgt] if tgt and tgt != d else []
    res = {}
    for label, v in vals.items():
        by = defaultdict(set)
        for d, xs in v.items():
            for x in xs:
                by[x].add(d)
        res[label] = [{"value": x, "sites": sorted(ds)} for x, ds in sorted(by.items()) if len(ds) >= 2]
    return res


def write_summary(records: list[dict]) -> dict:
    s = summary(records)
    SITETRACE_JSON.write_text(json.dumps(s, ensure_ascii=False, indent=0, sort_keys=True) + "\n",
                              encoding="utf-8")
    return s


def load() -> dict:
    if not SITETRACE_JSON.exists():
        return {}
    return json.loads(SITETRACE_JSON.read_text(encoding="utf-8"))
