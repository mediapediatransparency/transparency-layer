"""What each cited website says about itself, read by fixed rules (no AI, no judgement).

For each chosen source website, fetch its home page and up to three of its own pages that
usually name the body behind it (about, legal notice or imprint, privacy policy), and record:

- identifiers printed on the pages: charity, company and tax registration numbers in the
  formats listed in REGISTRY_PATTERNS, each with a link to the official register where one
  can be searched by number;
- the copyright line and any sentence of the form "a project of ...", "published by ...",
  "owned by ...", "funded by ..." (quoted as printed, at most 160 characters);
- what the site declares in its structured data (schema.org JSON-LD): organisation name,
  parent organisation, funder, founding date, and the ownership/funding page news sites can
  declare (ownershipFundingInfo);
- tracking and advertising account IDs embedded in the pages (Google Analytics and Tag
  Manager, Google AdSense, Facebook pixel, Yandex Metrica). Sites that carry the same account
  ID are run from the same account; this is how researchers find networks of websites;
- the domain's registration date and registrant organisation from RDAP, where the registry
  publishes them (an organisation's name only; a person's name is never recorded).

Results are saved per site as soon as each site is done (cache/siteprobe/), so a run can stop
and resume. `wtl siteprobe --batch N` probes the next N sites; `data/siteprobe.json` is
rewritten from everything probed so far after every batch.

A page this machine's filter blocks is recorded as blocked and not read. Nothing found is
recorded as "not found on the pages read", which is not the same as absent.
"""

import datetime as dt
import hashlib
import json
import re
import time
from html import unescape
from urllib.parse import urljoin, urlsplit

from .config import ROOT, user_agent
from .fetch import cache

SITEPROBE_JSON = ROOT / "data" / "siteprobe.json"
MAX_BYTES = 2_000_000
TIMEOUT = 15
EXCERPT = 160

# links to pages that usually name the body behind a site, in several languages
ABOUT_LINK = re.compile(
    r"about|who-?we-?are|our-?story|mission|impressum|imprint|legal|mentions-?legales|"
    r"aviso-?legal|privacy|datenschutz|contact|kontakt|o-?nas|o-?nama|o-?proekte|"
    r"chi-?siamo|quienes-?somos|qui-?sommes|sobre|over-?ons|hakkimizda|hakkinda|"
    r"%D7%90%D7%95%D7%93%D7%95%D7%AA|%D9%85%D9%86-%D9%86%D8%AD%D9%86|"
    r"%D0%BE-%D0%BD%D0%B0%D1%81|%E0%A4%B9%E0%A4%AE%E0%A4%BE%E0%A4%B0%E0%A5%87", re.I)
ABOUT_TEXT = re.compile(r"^\s*(about( us)?|who we are|our story|impressum|imprint|legal notice|"
                        r"privacy( policy)?|contact( us)?|о нас|о проекте|про нас|אודות|"
                        r"מי אנחנו|من نحن|عن الموقع|همارے بارے میں|हमारे बारे में|hakkımızda|"
                        r"chi siamo|quiénes somos|qui sommes-nous|über uns|o nas|o nama)\s*$", re.I)
PAGE_KIND_ORDER = [("about", re.compile(r"about|who|story|mission|o-?nas|o-?nama|o-?proekte|chi-?siamo|"
                                        r"quienes|qui-?sommes|sobre|over-?ons|hakk|%D7%90|%D9%85|%D0%BE|%E0%A4", re.I)),
                   ("legal", re.compile(r"impressum|imprint|legal|mentions|aviso", re.I)),
                   ("privacy", re.compile(r"privacy|datenschutz", re.I)),
                   ("contact", re.compile(r"contact|kontakt", re.I))]

# (name, regex with one group for the number, register search URL template or None)
REGISTRY_PATTERNS = [
    ("UK registered charity", re.compile(r"(?:registered\s+)?charity\s*(?:no\.?|number|reg(?:istration)?\.?\s*(?:no\.?|number)?)\s*[:#]?\s*(\d{6,7}(?:-\d{1,2})?)\b", re.I),
     "https://register-of-charities.charitycommission.gov.uk/charity-search/-/charity-details/{digits}"),
    ("Scottish charity", re.compile(r"\b(SC0\d{5})\b"),
     "https://www.oscr.org.uk/about-charities/search-the-register/charity-details?number={v}"),
    ("UK company", re.compile(r"compan(?:y|ies)\s*(?:registration\s*)?(?:no\.?|number|reg(?:istration)?\.?\s*(?:no\.?|number)?)\s*[:#]?\s*((?:[A-Z]{2})?\d{6,8})\b", re.I),
     "https://find-and-update.company-information.service.gov.uk/company/{v}"),
    ("US employer identification number (EIN)", re.compile(r"(?:\bEIN\b|tax\s*id(?:entification)?(?:\s*(?:no\.?|number))?|federal\s+tax\s+id(?:\s*(?:no\.?|number))?)\s*[:#]?\s*(\d{2}-\d{7})\b", re.I),
     "https://projects.propublica.org/nonprofits/organizations/{digits}"),
    ("US 501(c)(3) status stated", re.compile(r"(501\s*\(\s*c\s*\)\s*\(\s*3\s*\))", re.I), None),
    ("Israeli non-profit (amuta) or public benefit company", re.compile(r"(?:ע\"ר|עמותה|amuta|\bR\.\s?A\.|registered\s+(?:non-?profit|association)|non-?profit\s+(?:association|organi[sz]ation)\s+(?:no\.?|number))\D{0,30}(58-?\d{7})", re.I),
     "https://www.guidestar.org.il/organization/{digits}"),
    ("Israeli company", re.compile(r"(?:ח\.?פ\.?|company\s*(?:no\.?|number))\s*[:#]?\s*(5[1-6]-?\d{7})", re.I), None),
    ("Indian company (CIN)", re.compile(r"\b([LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})\b"), None),
    ("German commercial register (HRB/HRA)", re.compile(r"\b(HR[AB]\s?\d{3,6}(?:\s?[A-Z]{1,2})?)\b"), None),
    ("Australian Business Number (ABN)", re.compile(r"\bABN\s*[:#]?\s*(\d{2}\s?\d{3}\s?\d{3}\s?\d{3})\b"),
     "https://abr.business.gov.au/ABN/View?abn={digits}"),
    ("Canadian charity (BN)", re.compile(r"\b(\d{9}\s?RR\s?\d{4})\b"), None),
    ("French SIREN/SIRET", re.compile(r"\b(?:SIREN|SIRET|RCS)\s*[:#]?\s*((?:\d{3}\s?){3}(?:\d{5})?)", re.I), None),
    ("EU VAT number", re.compile(r"\b(?:VAT|USt-?IdNr\.?|TVA|IVA|BTW)\s*(?:no\.?|number|reg\.?)?\s*[:#]?\s*([A-Z]{2}\s?[0-9A-Z]{8,12})\b"), None),
    ("Russian state registration (OGRN)", re.compile(r"(?:ОГРН|OGRN)\s*[:#]?\s*(\d{13,15})"), None),
    ("Russian mass-media registration", re.compile(r"((?:ЭЛ|ПИ)\s*№\s*ФС\s*\d{2}\s*-\s*\d{4,6})"), None),
    ("Turkish trade registry (MERSIS)", re.compile(r"MERS[İI]S\s*(?:No\.?)?\s*[:#]?\s*(\d{16})", re.I), None),
]

TRACKERS = [
    ("Google Analytics (UA)", re.compile(r"\b(UA-\d{4,10})-\d{1,4}\b")),       # the account, not the property
    ("Google Analytics 4", re.compile(r"\b(G-[A-Z0-9]{8,12})\b")),
    ("Google Tag Manager", re.compile(r"\b(GTM-[A-Z0-9]{5,8})\b")),
    ("Google AdSense", re.compile(r"\b(?:ca-)?(pub-\d{16})\b")),
    ("Facebook pixel", re.compile(r"fbq\(\s*['\"]init['\"]\s*,\s*['\"](\d{12,20})['\"]")),
    ("Yandex Metrica", re.compile(r"(?:mc\.yandex\.ru/watch/|ym\(\s*)(\d{6,10})")),
]

STATEMENT = re.compile(
    r"((?:is\s+)?(?:a|an)\s+(?:project|initiative|programme|program|publication|service|"
    r"affiliate|subsidiary|division|member)\s+of\s+|(?:published|owned|operated|run|funded|"
    r"supported|sponsored|financed|founded)\s+by\s+)([^.<>\n|]{3,140})", re.I)
COPYRIGHT = re.compile(r"(?:©|&copy;|(?<!501)\(c\)(?=\s*\d)|\bcopyright\b)\s*(?:\d{4}\s*(?:[-–]\s*\d{4})?\s*,?\s*)?"
                       r"([^<>\n|]{3,120})", re.I)
JSONLD = re.compile(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.I | re.S)
LINK = re.compile(r"<a\s[^>]*href\s*=\s*[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
TAGS = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.I | re.S)
BLOCK_MARKERS = re.compile(r"webchaver|covenant\s*eyes|this site is blocked|blocked by your", re.I)


def _get(url: str):
    import requests
    try:
        r = requests.get(url, headers={"User-Agent": user_agent(), "Accept-Language": "en,*;q=0.5"},
                         timeout=TIMEOUT, stream=True, allow_redirects=True)
        body = r.raw.read(MAX_BYTES, decode_content=True)
        r.close()
        enc = r.encoding or "utf-8"
        if "charset" not in (r.headers.get("content-type") or "").lower():
            m = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", body[:4000], re.I)
            enc = m.group(1).decode() if m else "utf-8"
        try:
            text = body.decode(enc, errors="replace")
        except LookupError:
            text = body.decode("utf-8", errors="replace")
        return {"url": r.url, "status": r.status_code, "text": text,
                "sha256": hashlib.sha256(body).hexdigest()}
    except Exception as ex:  # noqa: BLE001
        return {"url": url, "status": None, "error": f"{type(ex).__name__}: {str(ex)[:120]}"}


ARCHIVE_PREFIX = "https://web.archive.org/web/2026id_/"
import threading  # noqa: E402
_ARCHIVE = threading.Semaphore(2)      # the Internet Archive refuses clients that ask too fast
_ARCHIVE_GAP = 2.0
_archive_last = [0.0]
_archive_lock = threading.Lock()


def _archive_get(url: str):
    with _ARCHIVE:
        with _archive_lock:
            wait = _ARCHIVE_GAP - (time.monotonic() - _archive_last[0])
            if wait > 0:
                time.sleep(wait)
            _archive_last[0] = time.monotonic()
        a = _get(ARCHIVE_PREFIX + url)
    if (a.get("error") and "ConnectionError" in a["error"]) or a.get("status") == 429:
        a["archive_unavailable"] = True
    return a


def _get_or_archive(url: str):
    """The page itself, or else the Internet Archive's latest saved copy (marked "archive")."""
    g = _get(url)
    if g.get("status") and g["status"] < 400 and g.get("text") is not None:
        return g
    a = _archive_get(url)
    if a.get("status") and a["status"] < 400 and a.get("text") is not None:
        a["archive"] = True
        a["live_error"] = g.get("error") or f"HTTP {g.get('status')}"
        return a
    if a.get("archive_unavailable"):
        g["archive_unavailable"] = True
    return g


def _visible(html: str) -> str:
    return " ".join(unescape(TAGS.sub(" ", html)).split())


def _excerpt(text: str, a: int, b: int) -> str:
    return text[max(0, a):min(len(text), b)].strip()[:EXCERPT]


def _jsonld(html: str) -> list[dict]:
    out = []
    for m in JSONLD.finditer(html):
        try:
            d = json.loads(m.group(1).strip())
        except ValueError:
            continue
        stack = d if isinstance(d, list) else [d]
        while stack:
            x = stack.pop()
            if isinstance(x, list):
                stack += x
                continue
            if not isinstance(x, dict):
                continue
            stack += x.get("@graph", []) if isinstance(x.get("@graph"), list) else []
            t = x.get("@type")
            t = t if isinstance(t, list) else [t]
            if any(isinstance(y, str) and ("Organization" in y or y in ("Corporation", "NGO",
                                                                         "NewsMediaOrganization"))
                   for y in t):
                def nm(v):
                    if isinstance(v, dict):
                        return v.get("name") or v.get("@id") or ""
                    if isinstance(v, list):
                        return "; ".join(nm(i) for i in v if nm(i))
                    return v if isinstance(v, str) else ""
                rec = {k: nm(x.get(k))[:EXCERPT] for k in ("name", "legalName", "parentOrganization",
                                                           "funder", "foundingDate", "ownershipFundingInfo",
                                                           "publishingPrinciples", "taxID", "vatID",
                                                           "leiCode", "duns")
                       if nm(x.get(k))}
                rec = {k: v for k, v in rec.items() if "%%" not in v and "{{" not in v}
                rec["type"] = ", ".join(y for y in t if isinstance(y, str))
                if len(rec) > 1:
                    out.append(rec)
    return out


def _about_links(base: str, html: str) -> list[tuple[str, str]]:
    host = urlsplit(base).hostname or ""
    reg = host.split(".", 1)[-1] if host.count(".") > 1 else host
    found = {}
    for m in LINK.finditer(html):
        href, label = m.group(1).strip(), _visible(m.group(2))[:60]
        if href.startswith(("mailto:", "javascript:", "tel:")):
            continue
        u = urljoin(base, href)
        h = urlsplit(u).hostname or ""
        if not (h == host or h.endswith("." + reg) or h == reg):
            continue
        if not (ABOUT_LINK.search(urlsplit(u).path) or ABOUT_TEXT.match(label)):
            continue
        for kind, rx in PAGE_KIND_ORDER:
            if rx.search(urlsplit(u).path) or rx.search(label):
                found.setdefault(kind, u)
                break
    return [(k, found[k]) for k, _ in PAGE_KIND_ORDER if k in found][:3]


def extract(pages: list[dict]) -> dict:
    """The facts read from fetched pages: [{"kind", "url", "text"}]."""
    regs, trackers, statements, copyright_, org = {}, {}, [], [], []
    for p in pages:
        html = p["text"]
        vis = _visible(html)
        for name, rx, tmpl in REGISTRY_PATTERNS:
            for m in rx.finditer(vis):
                v = " ".join(m.group(1).split())
                key = (name, v)
                if key in regs:
                    continue
                digits = re.sub(r"\D", "", v)
                regs[key] = {"registry": name, "id": v, "page": p["url"],
                             "excerpt": _excerpt(vis, m.start() - 60, m.end() + 40),
                             **({"register_url": tmpl.format(v=v.replace(" ", ""), digits=digits)} if tmpl else {})}
        for name, rx in TRACKERS:
            for m in rx.finditer(html):
                trackers.setdefault((name, m.group(1)), {"service": name, "id": m.group(1), "page": p["url"]})
        for m in STATEMENT.finditer(vis):
            s = _excerpt(vis, m.start(), m.end())
            if s not in [x["text"] for x in statements] and len(statements) < 8:
                statements.append({"text": s, "page": p["url"]})
        if p["kind"] == "home":
            for m in COPYRIGHT.finditer(vis):
                c = re.split(r"\.\s|\s\|\s|\s{2,}", " ".join(m.group(1).split()))[0][:120]
                if c and c not in copyright_ and len(copyright_) < 3:
                    copyright_.append(c)
        for o in _jsonld(html):
            if o not in org and len(org) < 5:
                org.append({**o, "page": p["url"]})
    return {"registry_ids": list(regs.values()), "trackers": list(trackers.values()),
            "statements": statements, "copyright": copyright_, "declared_organisation": org}


IANA_RDAP = "https://data.iana.org/rdap/dns.json"
_rdap_servers = None
_rdap_lock = threading.Lock()
_rdap_last = {}


def _rdap_base(tld: str) -> str | None:
    """The registry's own RDAP server for a top-level domain, from IANA's bootstrap file."""
    global _rdap_servers
    with _rdap_lock:
        if _rdap_servers is None:
            p = cache.path("siteprobe_meta", "iana_rdap_dns")
            d = cache.load(p)
            if d is None:
                import requests
                d = requests.get(IANA_RDAP, headers={"User-Agent": user_agent()}, timeout=60).json()
                cache.save(p, d)
            _rdap_servers = {t: urls[0] for tlds, urls in d.get("services", []) for t in tlds if urls}
    return _rdap_servers.get(tld)


def rdap(domain: str) -> dict | None:
    """Registration date and registrant organisation from the registry's RDAP server (found
    through IANA's bootstrap list); None when the registry publishes no RDAP. Requests to each
    server are spaced one second apart."""
    import requests
    base = _rdap_base(domain.rsplit(".", 1)[-1])
    if not base:
        return None
    host = urlsplit(base).hostname
    r = d = None
    for attempt in range(3):
        with _rdap_lock:
            wait = 1.0 - (time.monotonic() - _rdap_last.get(host, 0))
            _rdap_last[host] = time.monotonic() + max(wait, 0)
        if wait > 0:
            time.sleep(wait)
        try:
            r = requests.get(base.rstrip("/") + f"/domain/{domain}", headers={
                "User-Agent": user_agent(), "Accept": "application/rdap+json"}, timeout=TIMEOUT)
        except Exception:  # noqa: BLE001
            return None
        if r.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code != 200:
            return None
        try:
            d = r.json()
        except ValueError:
            return None
        break
    if d is None:
        return None
    out = {"url": r.url}
    for e in d.get("events", []):
        if e.get("eventAction") == "registration":
            out["registered"] = e.get("eventDate", "")[:10]
    for ent in d.get("entities", []):
        if "registrant" in (ent.get("roles") or []):
            for f in (ent.get("vcardArray") or [None, []])[1]:
                # organisations only: a registrant's personal name is never recorded
                if f[0] == "org" and isinstance(f[3], str) and f[3].strip():
                    v = f[3].strip()
                    if not re.search(r"redacted|privacy|proxy|withheld|domains by proxy|whois", v, re.I):
                        out.setdefault("registrant", v[:EXCERPT])
    return out


def fill_rdap() -> int:
    """Look up RDAP again for sites read before the direct registry lookup (no date recorded)."""
    from .config import CACHE_DIR
    n = 0
    for f in sorted((CACHE_DIR / "siteprobe").glob("*.json.gz")):
        x = cache.load(f)
        if not isinstance(x, dict) or (x.get("rdap") or {}).get("registered") or x.get("rdap_checked"):
            continue
        x["rdap"] = rdap(x["domain"])
        x["rdap_checked"] = dt.date.today().isoformat()
        cache.save(f, x)
        n += 1
    return n


def probe(domain: str) -> dict:
    """Probe one site (cached; the cached result is returned if present)."""
    p = cache.path("siteprobe", domain)
    hit = cache.load(p)
    if hit is not None:
        return hit
    pages, fetched = [], []
    home = None
    for u in (f"https://{domain}/", f"https://www.{domain}/", f"http://{domain}/"):
        home = _get(u)
        if home.get("status") and home["status"] < 400:
            break
    if not (home and home.get("status") and home["status"] < 400):
        home = _get_or_archive(f"https://{domain}/")
    if home and home.get("text") is not None and home.get("status") and home["status"] < 400:
        if BLOCK_MARKERS.search(home["text"][:20000]) and len(home["text"]) < 30000:
            out = {"domain": domain, "probed": dt.date.today().isoformat(), "status": "blocked by this computer's filter"}
            cache.save(p, out)
            return out
        pages.append({"kind": "home", "url": home["url"], "text": home["text"]})
        fetched.append({"kind": "home", "url": home["url"], "status": home["status"], "sha256": home["sha256"],
                        **({"from_archive": True, "live_error": home["live_error"]} if home.get("archive") else {})})
        base = home["url"]
        if home.get("archive"):     # links on an archived page point into the archive
            m = re.match(r"https://web\.archive\.org/web/[^/]+/(.+)$", base)
            base = m.group(1) if m else f"https://{domain}/"
        for kind, u in _about_links(base, re.sub(r"https?://web\.archive\.org/web/[^/]+/", "", home["text"])):
            g = _get_or_archive(u) if home.get("archive") is None else _archive_get(u)
            fetched.append({"kind": kind, "url": g["url"], "status": g.get("status"),
                            **({"sha256": g["sha256"]} if g.get("sha256") else {}),
                            **({"from_archive": True} if g.get("archive") or "web.archive.org" in g["url"] else {}),
                            **({"error": g["error"]} if g.get("error") else {})})
            if g.get("text") is not None and g.get("status") and g["status"] < 400:
                pages.append({"kind": kind, "url": g["url"], "text": g["text"]})
            time.sleep(0.5)
        status = "read from the Internet Archive's saved copy" if home.get("archive") else "read"
    else:
        status = ("not reachable: " + (home.get("error") or f"HTTP {home.get('status')}")) if home else "not reachable"
    out = {"domain": domain, "probed": dt.date.today().isoformat(), "status": status,
           "pages": fetched, **(extract(pages) if pages else {}), "rdap": rdap(domain),
           **({"retry": "the Internet Archive was not available"} if not pages and home
              and home.get("archive_unavailable") else {})}
    cache.save(p, out)
    return out


def chosen(records: list[dict], outlets: dict) -> list[str]:
    """Websites to probe: web sources cited at least twice, or in a lead section, or in a
    flagged citation, that no assessor rates or that Wikidata classes as an organisation
    (think tanks, NGOs, advocacy groups and so on, whose backers matter most). Ordered by
    citations, most first."""
    from collections import Counter
    from .outlets import ORG_KINDS
    from .sources import PLATFORMS
    rated = ("wikipedia_rating", "independent_quality", "audience_leaning", "allsides_2018", "mbfc",
             "academic_level")
    cites, lead, flagged = Counter(), Counter(), Counter()
    for r in records:
        for x in (r.get("sources") or {}).get("list", []):
            k = x["source"]
            if k.startswith("name:") or "." not in k or " " in k or k in PLATFORMS:
                continue
            cites[k] += x["citations"]
            lead[k] += x.get("lead_citations", 0)
            flagged[k] += sum((x.get("flags") or {}).values())
    out = []
    for k, n in cites.items():
        o = outlets.get(k) or {}
        if not (n >= 2 or lead[k] or flagged[k]):
            continue
        if any(o.get(x) for x in rated) and o.get("kind") not in ORG_KINDS:
            continue
        out.append(k)
    return sorted(out, key=lambda k: (-cites[k], k))


def summary() -> dict:
    """Everything probed so far, from the cache, plus operator networks: groups of sites that
    share a tracking or advertising account ID."""
    from .config import CACHE_DIR
    sites = {}
    for f in sorted((CACHE_DIR / "siteprobe").glob("*.json.gz")):
        try:
            x = cache.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(x, dict) and x.get("domain"):
            sites[x["domain"]] = x
    by_id = {}
    for dom, x in sites.items():
        for t in x.get("trackers", []):
            by_id.setdefault((t["service"], t["id"]), set()).add(dom)
    networks = [{"service": s, "id": i, "sites": sorted(v)} for (s, i), v in sorted(by_id.items())
                if len(v) >= 2]
    return {"built": dt.date.today().isoformat(), "rule": __doc__.strip(), "sites": sites,
            "shared_ids": networks}


def write_summary() -> dict:
    s = summary()
    SITEPROBE_JSON.write_text(json.dumps(s, ensure_ascii=False, indent=0, sort_keys=True) + "\n",
                              encoding="utf-8")
    return s


def run(records: list[dict], outlets: dict, batch: int, retry: bool = False) -> None:
    def pending(k):
        hit = cache.load(cache.path("siteprobe", k))
        if hit is None:
            return True
        if retry and hit.get("retry"):
            cache.path("siteprobe", k).unlink()
            return True
        return False
    todo = [k for k in chosen(records, outlets) if pending(k)]
    print(f"  {len(todo):,} sites still to probe; this batch: {min(batch, len(todo)):,}", flush=True)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=16) as ex:   # sixteen sites at a time; each site's pages in turn
        futs = {ex.submit(probe, k): k for k in todo[:batch]}
        for i, f in enumerate(as_completed(futs), 1):
            k = futs[f]
            try:
                r = f.result()
            except Exception as e:  # noqa: BLE001  not cached; tried again next batch
                print(f"  [{i}] {k}: error {str(e)[:100]}", flush=True)
                continue
            print(f"  [{i}] {k}: {r['status'][:60]}, {len(r.get('registry_ids', []))} registry IDs, "
                  f"{len(r.get('trackers', []))} tracking IDs", flush=True)
    s = write_summary()
    print(f"wrote {SITEPROBE_JSON}: {len(s['sites']):,} sites probed in all; "
          f"{len(s['shared_ids']):,} tracking IDs shared by two or more sites", flush=True)
