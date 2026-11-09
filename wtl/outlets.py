"""What outside records say about each cited source: a snapshot in data/outlets.json.

Several assessors are shown side by side, each attributed; none is treated as the truth, and
the project adds no rating of its own:

- Wikipedia's own ratings: the Perennial sources list (WP:RSP), as of the revisions stored in
  the snapshot. Wikipedia editors' consensus about sources they discuss often; most sources are
  not on it, which means "not discussed there", not "unreliable".
- Independent quality: Lin et al. (2023), PNAS Nexus 2(9) pgad286, an aggregate of six
  independent expert rating sets for 11,520 news domains (0 = lowest, 1 = highest quality).
  Wikipedia is not one of the six.
- Audience leaning: Robertson et al. (2018), Proc. ACM HCI 2(CSCW) 148: whether a domain's links
  were shared more by registered Democrats (-1) or Republicans (+1) in a 2017 US Twitter panel.
  It measures who shared the site, not its content.
- AllSides ratings, as included in the Robertson et al. release (2018; CC BY-NC 4.0).
- Wikidata facts: country, owner, recorded political alignment and ideology, and whether
  Wikidata classes it as state media, a public broadcaster or a state-owned enterprise.

Source keys are those produced by wtl/sources.py: a registrable domain, or "name:<publication>".
"""

import csv
import datetime as dt
import io
import json
import re
import tarfile
import time

from .config import ROOT
from .fetch import cache
from .fetch.http import get_json
from .fetch.mediawiki import api

OUTLETS_JSON = ROOT / "data" / "outlets.json"
RSP_PAGES = [f"Wikipedia:Reliable sources/Perennial sources/{p}" for p in [*"12345678", "X"]]
RSP_URL = "https://en.wikipedia.org/wiki/Wikipedia:Reliable_sources/Perennial_sources"
RSP_STATUS = {"gr": "generally reliable", "nc": "no consensus", "gu": "generally unreliable",
              "d": "deprecated", "b": "blacklisted", "m": "varies (see entry)"}
LIN_URL = "https://raw.githubusercontent.com/hauselin/domain-quality-ratings/main/data/domain_pc1.csv"
LIN_REF = ("Lin, H., Lasser, J., Lewandowsky, S., Cole, R., Gully, A., Rand, D. G. & Pennycook, G. "
           "(2023). High level of correspondence across different news domain quality rating sets. "
           "PNAS Nexus 2(9), pgad286. https://doi.org/10.1093/pnasnexus/pgad286")
ROB_URL = "https://personalization.ccs.neu.edu/static/archive/bias_scores.tar.gz"
ROB_REF = ("Robertson, R. E., Jiang, S., Joseph, K., Friedland, L., Lazer, D. & Wilson, C. (2018). "
           "Auditing partisan audience bias within Google Search. Proc. ACM Hum.-Comput. Interact. "
           "2(CSCW), 148. https://doi.org/10.1145/3274417")
DD_COMMIT = "a2a834400ad582d1c8a5150338a146f2af2a95b0"   # LazerLab/DomainDemo, 2025-12-01
DD_URL = (f"https://raw.githubusercontent.com/LazerLab/DomainDemo/{DD_COMMIT}/data/derived_metrics/"
          "derived_party_leaning.csv.gz")
DD_REF = ("Yang, K.-C., Goel, P., Quintana-Mathé, A., Horgan, L., McCabe, S. D., Grinberg, N., "
          "Joseph, K. & Lazer, D. (2025). DomainDemo: a dataset of domain-sharing activities among "
          "different demographic groups on Twitter. Scientific Data 12, 1251. "
          "https://doi.org/10.1038/s41597-025-05604-6 (derived party-leaning scores; the data "
          "repository states no licence)")
# Sites that host books and scholarly papers from many publishers: who shares links to them says
# nothing about a given book or paper, so website ratings are not applied to them (rule A,
# 2026-11-06). Publishers and journals themselves are recognised by their Wikidata kind.
SCHOLARLY_HOSTS = {"jstor.org", "doi.org", "muse.jhu.edu", "academia.edu", "researchgate.net",
                   "semanticscholar.org", "ncbi.nlm.nih.gov", "europepmc.org", "ssrn.com",
                   "philpapers.org", "persee.fr", "cairn.info", "erudit.org", "oup.com",
                   "taylorfrancis.com", "brill.com", "degruyter.com", "sagepub.com",
                   "scholar.archive.org", "openlibrary.org", "worldcat.org", "hathitrust.org",
                   "books.google.com"}
WEBSITE_RATINGS = ("independent_quality", "audience_leaning", "audience_leaning_dd",
                   "allsides_2018", "mbfc")
ALLSIDES_REF = ("AllSides Media Bias Ratings (2018 values as included in the Robertson et al. "
                "release), AllSides.com, licensed CC BY-NC 4.0.")
SPARQL = "https://query.wikidata.org/sparql"
STATE_CLASSES = {"Q2324556": "state media", "Q1126006": "public broadcaster",
                 "Q270791": "state-owned enterprise"}


def log(msg):
    import sys
    print(msg, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- Wikipedia's ratings
ROW = re.compile(r'^\|-[^\n]*?class="s-(\w+)"[^\n]*$', re.M)   # class and id in either order
ROW_ID = re.compile(r'\bid="([^"]*)"')
LINK = re.compile(r"\[\[([^|\]#]+)(?:\|[^\]]*)?\]\]")
STATUS = re.compile(r"\{\{\s*WP:RSPSTATUS\|(\w+)")
USES = re.compile(r"\{\{\s*WP:RSPUSES\|([^}]*)\}\}")


def rsp() -> dict:
    """{"revisions": {page: revid}, "rows": [{id, article, status, statuses, domains}]}."""
    p = cache.path("outlets", "rsp", dt.date.today().isoformat())
    hit = cache.load(p)
    if hit:
        return hit
    d = api({"action": "query", "prop": "revisions", "titles": "|".join(RSP_PAGES),
             "rvprop": "ids|content", "rvslots": "main"})
    revs, rows = {}, []
    for pg in d["query"]["pages"]:
        if "revisions" not in pg:
            continue
        r = pg["revisions"][0]
        revs[pg["title"]] = r["revid"]
        t = r["slots"]["main"]["content"]
        ms = list(ROW.finditer(t))
        for i, m in enumerate(ms):
            body = t[m.end(): ms[i + 1].start() if i + 1 < len(ms) else len(t)]
            body = body.split("\n|}")[0]
            first = body.split("\n|", 2)
            src_cell = first[1] if len(first) > 1 else body
            lk = LINK.search(src_cell)
            doms = []
            for u in USES.findall(body):
                doms += [x.strip().lower() for x in u.split("|") if x.strip()]
            rid = ROW_ID.search(m.group(0))
            rows.append({"id": (rid.group(1) if rid else "") or (lk.group(1) if lk else ""),
                         "article": lk.group(1).strip() if lk else "",
                         "status": m.group(1),
                         "statuses": sorted(set(STATUS.findall(body))),
                         "domains": doms})
    out = {"revisions": dict(sorted(revs.items())), "rows": rows}
    cache.save(p, out)
    return out


# ---------------------------------------------------------------- independent datasets
def _download(url, name, timeout=120):
    p = cache.path("outlets", "raw", name)
    hit = cache.load(p)
    if hit is not None:
        return hit
    from .fetch.http import session
    resp = session().get(url, timeout=timeout)
    resp.raise_for_status()
    data = resp.content
    if name.endswith(".tar.gz"):
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            m = next(x for x in tf.getmembers() if x.name.endswith("bias_scores.csv"))
            data = tf.extractfile(m).read()
    text = data.decode("utf-8")
    cache.save(p, text)
    return text


def lin() -> dict:
    rows = csv.DictReader(io.StringIO(_download(LIN_URL, "lin2023_domain_pc1.csv")))
    return {r["domain"].lower(): float(r["pc1"]) for r in rows if r.get("pc1")}


def robertson() -> dict:
    rows = csv.DictReader(io.StringIO(_download(ROB_URL, "robertson2018_bias_scores.tar.gz")))
    out = {}
    for r in rows:
        out[r["domain"].lower()] = {
            "score": float(r["score"]),
            "accounts": int(float(r["rounded_n_accts"] or 0)),
            "allsides": float(r["allsides_score"]) if r.get("allsides_score") else None,
        }
    return out


def domaindemo() -> dict:
    """{domain: partisan audience score}, Yang et al. 2025 (−1 shared mostly by Democratic-
    leaning users, +1 by Republican-leaning; domains shared by at least 50 panel users)."""
    p = cache.path("outlets", "raw", f"domaindemo_party_{DD_COMMIT[:12]}")
    text = cache.load(p)
    if text is None:
        from .fetch.http import session
        import gzip
        resp = session().get(DD_URL, timeout=120)
        resp.raise_for_status()
        text = gzip.decompress(resp.content).decode("utf-8")
        cache.save(p, text)
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        try:
            v = float(r["leaning_score"])
        except (TypeError, ValueError):
            continue
        if -1 <= v <= 1:
            out[r["domain"].strip().lower()] = v
    return out


def write_rated_subdomains() -> int:
    """data/rated_subdomains.txt: sub-domains that the leaning and quality datasets score as
    sites of their own, read by sources.source_domain. Changing it changes source keys, so
    records must be re-analysed (wtl reanalyse) after it changes."""
    from .config import ROOT
    from .sources import registrable
    # Only where the main domain has no leaning score of its own (go.com, sky.com): there the
    # sub-domains are rated as different sites (abcnews.go.com, espn.go.com). Where the main
    # domain is rated (cnn.com), its sub-domains stay with it. DomainDemo rates main domains
    # only, so it adds no sub-domains.
    rb = robertson()
    subs = set()
    for table in (rb, lin(), mbfc()):
        for d in table:
            d = d.strip().lower()
            if "/" in d or d.startswith(("www.", "m.", "amp.", "mobile.")) or "." not in d:
                continue
            reg = registrable(d)
            if reg != d and reg not in rb:
                subs.add(d)
    (ROOT / "data" / "rated_subdomains.txt").write_text("\n".join(sorted(subs)) + "\n", encoding="utf-8")
    return len(subs)


def is_scholarly(key: str, e: dict) -> bool:
    """A book publisher, a journal, or a site hosting books and papers (rule A)."""
    if e.get("kind") in ACADEMIC_KINDS:
        return True
    if key.startswith("name:"):
        return bool(e.get("books")) and e.get("kind") not in NEWS_KINDS
    return key in SCHOLARLY_HOSTS or any(key.endswith("." + h) for h in SCHOLARLY_HOSTS)


NEWS_KINDS = {"newspaper or news website", "broadcaster", "magazine", "news agency", "news media",
              "website"}


def lookup(host: str, table: dict):
    """Value for the host or its nearest parent domain present in the table."""
    parts = host.split(".")
    for i in range(len(parts) - 1):
        k = ".".join(parts[i:])
        if k in table:
            return k, table[k]
    return None, None


MBFC_URL = ("https://raw.githubusercontent.com/idiap/Factual-Reporting-and-Political-Bias-Web-"
            "Interactions/main/data/mbfc_raw.csv")
MBFC_REF = ("Media Bias/Fact Check ratings (bias and factual reporting), as collected in the Idiap "
            "Research Institute's open dataset (Factual-Reporting-and-Political-Bias-Web-Interactions, "
            "Apache-2.0).")


def mbfc() -> dict:
    rows = csv.DictReader(io.StringIO(_download(MBFC_URL, "mbfc_raw.csv")))
    out = {}
    for r in rows:
        d = r["source"].lower().strip()
        d = d[4:] if d.startswith("www.") else d
        if d:
            out[d] = {"bias": r["bias"] or None, "factual_reporting": r["factual_reporting"] or None,
                      "country": re.sub(r"\s*\(.*\)", "", r["country"] or "") or None}
    return out


# Finland's Publication Forum (JUFO): expert panels grade academic publishers and journals
# 0 (assessed, does not meet the criteria) to 3 (highest). Records also carry Denmark's level.
JUFO_API = "https://jufo-rest.csc.fi/v1.1"
JUFO_REF = ("Publication Forum (JUFO), Federation of Finnish Learned Societies: levels 0 to 3 "
            "assigned by panels of researchers to academic publishers, journals and series.")
JUFO_TYPES = {"publisher": "2", "journal": "1"}


def jufo(name: str, kind: str | None) -> dict | None:
    """The JUFO record whose name (or other title) matches `name` exactly after normalising."""
    p = cache.path("outlets", "jufo", re.sub(r"\W+", "_", _norm(name))[:80] + "_" + (kind or "any"))
    hit = cache.load(p)
    if hit is not None:
        return hit or None
    found = None
    for t in ([JUFO_TYPES[kind]] if kind in JUFO_TYPES else ["2", "1"]):
        res = get_json(f"{JUFO_API}/etsi.php", {"nimi": name, "tyyppi": t}, retries=3, timeout=60) or []
        for r in res:
            if _norm(r.get("Name", "")) == _norm(name):
                found = r
                break
        if found:
            break
    rec = None
    if found:
        full = (get_json(f"{JUFO_API}/kanava/{found['Jufo_ID']}", retries=3, timeout=60) or [{}])[0]
        others = [x.strip() for x in (full.get("Other_Title") or "").split(";") if x.strip()]
        rec = {"id": found["Jufo_ID"], "name": full.get("Name") or found["Name"],
               "type": "publisher" if full.get("Type") == "Kirjakustantaja" else "journal or series",
               "level": int(full["Level"]) if str(full.get("Level", "")).isdigit() else None,
               "denmark_level": (int(full["Denmark_Level"])
                                 if str(full.get("Denmark_Level", "")).isdigit() else None),
               "in_doaj": full.get("DOAJ_Index") == "1",
               "url": f"https://jfp.csc.fi/en/web/haku/julkaisukanavahaku#!/kanava/{found['Jufo_ID']}",
               "other_titles": others}
    cache.save(p, rec or {})
    return rec


ALLSIDES_LABEL = {-1.0: "left", -0.5: "lean left", 0.0: "centre", 0.5: "lean right", 1.0: "right"}


# ---------------------------------------------------------------- Wikidata
def _sparql(q):
    """POST, so long VALUES lists are not cut off by URL length limits; back off on errors."""
    from .fetch.http import session
    for attempt in range(6):
        try:
            r = session().post(SPARQL, data={"query": q, "format": "json"},
                               headers={"Accept": "application/sparql-results+json"}, timeout=120)
            if r.status_code == 200:
                return r.json()["results"]["bindings"]
            log(f"  Wikidata query: HTTP {r.status_code}, retrying")
        except Exception as e:   # noqa: BLE001 - timeouts happen; back off and retry
            log(f"  Wikidata query: {type(e).__name__}, retrying")
        time.sleep(10 * (attempt + 1))
    raise RuntimeError("Wikidata query failed repeatedly")


def qids_for_titles(titles: list[str]) -> dict:
    """Wikipedia article title -> Wikidata ID (redirects followed, disambiguation pages dropped)."""
    out = {}
    for i in range(0, len(titles), 50):
        b = titles[i:i + 50]
        d = api({"action": "query", "titles": "|".join(b), "redirects": "1", "prop": "pageprops",
                 "ppprop": "wikibase_item|disambiguation"})
        q = d["query"]
        back = {}
        for n in q.get("normalized", []):
            back[n["to"]] = n["from"]
        for r in q.get("redirects", []):
            back[r["to"]] = back.get(r["from"], r["from"])
        for pg in q.get("pages", []):
            pp = pg.get("pageprops", {})
            if pg.get("missing") or "disambiguation" in pp or "wikibase_item" not in pp:
                continue
            orig = back.get(pg["title"], pg["title"])
            out[orig] = pp["wikibase_item"]
            out[pg["title"]] = pp["wikibase_item"]
        time.sleep(0.2)
    return out


def organisations(qids: list[str]) -> set:
    """The given Wikidata items that are organisations (instance of a subclass of Q43229)."""
    p = cache.path("outlets", "is_org")
    known = cache.load(p) or {}
    todo = [q for q in qids if q not in known]
    for i in range(0, len(todo), 100):
        b = todo[i:i + 100]
        rows = _sparql("SELECT DISTINCT ?item WHERE { VALUES ?item { " + " ".join("wd:" + q for q in b)
                       + " } ?item wdt:P31/wdt:P279* wd:Q43229 . }")
        yes = {r["item"]["value"].rsplit("/", 1)[1] for r in rows}
        for q in b:
            known[q] = q in yes
        cache.save(p, known)
        time.sleep(1)
    return {q for q in qids if known.get(q)}


SHARED_SITE = 3   # this many Wikidata items or more give the same website: a shared host, not matched


def qids_for_domains(domains: list[str]) -> dict:
    """Domain -> Wikidata ID via "official website" (P856). When two items give the same site, an
    item that is not a person is preferred, then the lowest numeric ID. When three or more do, the
    site is a shared host (a journal platform such as tandfonline.com, where each journal lists the
    platform) and is not matched: picking one of them would name the wrong publication."""
    claim = {}
    for i in range(0, len(domains), 40):
        b = domains[i:i + 40]
        vals = " ".join(f"<{s}://{w}{d}{e}>" for d in b for s in ("http", "https")
                        for w in ("", "www.") for e in ("", "/"))
        rows = _sparql(f"SELECT ?item ?site ?human WHERE {{ VALUES ?site {{ {vals} }} ?item wdt:P856 ?site . "
                       f"OPTIONAL {{ ?item wdt:P31 wd:Q5 . BIND(1 AS ?human) }} }}")
        for r in rows:
            dom = re.sub(r"^https?://(www\.)?", "", r["site"]["value"]).rstrip("/")
            q = r["item"]["value"].rsplit("/", 1)[1]
            claim.setdefault(dom, {})[q] = "human" in r
        if i // 40 % 10 == 0:
            log(f"  Wikidata websites: {min(i + 40, len(domains)):,} of {len(domains):,}")
        time.sleep(1)
    out = {}
    for dom, items in claim.items():
        if len(items) >= SHARED_SITE:
            continue
        out[dom] = min(items, key=lambda q: (items[q], int(q[1:])))
    shared = sum(1 for v in claim.values() if len(v) >= SHARED_SITE)
    if shared:
        log(f"  Wikidata websites: {shared:,} shared by {SHARED_SITE} or more items, left unmatched")
    return out


WD_API = "https://www.wikidata.org/w/api.php"
FACT_PROPS = {"P495": "country", "P17": "country", "P127": "owned_by", "P1387": "political_alignment",
              "P1142": "political_ideology"}
# Associations recorded on Wikidata, shown as facts with a link to the statement.
ASSOC_PROPS = {"P112": "founded by", "P749": "parent organisation", "P463": "member of",
               "P1416": "affiliation", "P8324": "funded by", "P859": "sponsor", "P488": "chair",
               "P3461": "designated as terrorist by", "P123": "publisher", "P8875": "indexed in"}
ASSOC_PROPS.update({"P1037": "director or manager", "P169": "chief executive"})
# Identifiers in public registries, recorded on Wikidata: (name, link to the official record).
REGISTRY_PROPS = {
    "P1297": ("US tax ID (EIN), US non-profit records",
              "https://projects.propublica.org/nonprofits/organizations/{digits}"),
    "P3057": ("Charity Commission for England and Wales",
              "https://register-of-charities.charitycommission.gov.uk/charity-search/-/charity-details/{v}"),
    "P3163": ("Scottish Charity Regulator", "https://www.oscr.org.uk/about-charities/search-the-register/charity-details?number={v}"),
    "P3200": ("Charity Commission for Northern Ireland", "https://www.charitycommissionni.org.uk/charity-details/?regId={v}"),
    "P10377": ("Charities Regulator (Ireland)", "https://www.charitiesregulator.ie/en/information-for-the-public/search-the-register-of-charities/charity/{v}"),
    "P3914": ("GuideStar Israel (registered Israeli non-profits)", "https://www.guidestar.org.il/organization/{v}"),
    "P2657": ("EU Transparency Register", "https://transparency-register.europa.eu/searchregister-or-update/organisation-detail_en?id={v}"),
    "P3548": ("Australian Business Register", "https://abr.business.gov.au/ABN/View?abn={digits}"),
    "P10301": ("Lobbying Register of the German Bundestag", "https://www.lobbyregister.bundestag.de/suche/{v}"),
}
JOURNAL_ID_PROPS = {"P236": "issn", "P1156": "scopus_id", "P5115": "doaj_id"}
# Kind of source: Wikidata classes, checked in this order (instance of, or of a subclass);
# the first match wins. Labels checked on Wikidata.
SOURCE_KINDS = [
    ("predatory journal", ["Q65770378"]),
    ("self-publishing company or platform", ["Q149985", "Q16856825"]),
    ("academic journal", ["Q737498", "Q5633421"]),
    ("university press", ["Q479716"]),
    ("news agency", ["Q192283"]),
    ("newspaper or news website", ["Q11032", "Q1110794", "Q1153191", "Q17232649"]),
    ("magazine", ["Q41298"]),
    ("broadcaster", ["Q15265344", "Q2001305", "Q14350"]),
    ("book publisher", ["Q2085381"]),
    ("news media", ["Q1193236", "Q11033", "Q1331793"]),
    ("court or tribunal", ["Q41487"]),
    ("intergovernmental organisation", ["Q245065", "Q484652"]),
    ("legislature", ["Q11204"]),
    ("government body", ["Q327333", "Q2659904", "Q192350", "Q7188"]),
    ("political party", ["Q7278"]),
    ("armed organisation", ["Q17149090"]),
    ("religious organisation", ["Q1530022"]),
    ("university or research institute", ["Q3918", "Q31855"]),
    ("think tank", ["Q155271"]),
    ("human rights organisation", ["Q1920810"]),
    ("advocacy or activist group", ["Q431603", "Q1887898", "Q1666019"]),
    ("trade union", ["Q178790"]),
    ("charity or foundation", ["Q708676", "Q157031"]),
    ("NGO or non-profit", ["Q79913", "Q163740"]),
    ("encyclopedia or reference work", ["Q5292"]),
    ("social media platform", ["Q3220391"]),
    ("blog", ["Q30849"]),
    ("individual person", ["Q5"]),
    ("company", ["Q783794", "Q4830453"]),
    ("website", ["Q35127"]),
]
ORG_KINDS = {"think tank", "human rights organisation", "advocacy or activist group",
             "religious organisation", "trade union", "charity or foundation", "NGO or non-profit",
             "political party", "armed organisation"}
ACADEMIC_KINDS = {"predatory journal": "journal", "academic journal": "journal",
                  "university press": "publisher", "book publisher": "publisher",
                  "self-publishing company or platform": "publisher"}
PUBLISHER_KINDS = {"university press", "book publisher", "self-publishing company or platform"}
# kinds a book publisher's name may be matched to by an exact Wikidata search (see _search_publishers)
SEARCH_OK_KINDS = PUBLISHER_KINDS | {"company", "university or research institute", "think tank",
                                     "religious organisation", "NGO or non-profit",
                                     "charity or foundation", "advocacy or activist group",
                                     "government body", "political party", "news media",
                                     "newspaper or news website", "magazine",
                                     "intergovernmental organisation", "human rights organisation"}
# Open Library (MARC) language codes to Wikidata search languages
MARC_TO_WIKI = {"heb": "he", "ara": "ar", "per": "fa", "tur": "tr", "rus": "ru", "ukr": "uk",
                "pol": "pl", "ger": "de", "fre": "fr", "spa": "es", "ita": "it", "por": "pt",
                "dut": "nl", "hin": "hi", "urd": "ur", "ben": "bn", "chi": "zh", "jpn": "ja",
                "srp": "sr", "hrv": "hr", "bos": "bs", "alb": "sq", "gre": "el", "arm": "hy",
                "aze": "az", "geo": "ka", "lit": "lt", "lav": "lv", "est": "et", "bul": "bg",
                "rum": "ro", "cze": "cs", "hun": "hu", "swe": "sv", "nor": "nb", "fin": "fi",
                "dan": "da", "kor": "ko", "tam": "ta", "mar": "mr", "nep": "ne", "pus": "ps",
                "kur": "ku", "yid": "yi", "slo": "sk", "slv": "sl", "bel": "be", "ind": "id"}
WIKI_SITE = re.compile(r"^([a-z_]{2,12})wiki$")
NON_LANGUAGE_WIKIS = {"commons", "species", "meta", "mediawiki", "wikidata", "sources", "outreach",
                      "incubator", "wikimania", "test", "test2", "foundation", "wikifunctions"}


def _entities(ids: list[str], props: str) -> dict:
    out = {}
    for i in range(0, len(ids), 50):
        d = get_json(WD_API, {"action": "wbgetentities", "ids": "|".join(ids[i:i + 50]),
                              "props": props, "languages": "en", "format": "json"})
        out.update(d.get("entities", {}))
        time.sleep(0.2)
    return out


def facts(qids: list[str]) -> dict:
    """Facts recorded on Wikidata for each item (current statements, labels in English)."""
    ents = _entities(qids, "labels|claims|sitelinks")
    out, value_ids = {}, set()
    for q in qids:
        e = ents.get(q, {})
        c = e.get("claims", {})
        f = {"label": e.get("labels", {}).get("en", {}).get("value", q), "websites": [],
             "_vals": {}, "_ref": set(), "registries": [], "ids": {},
             "enwiki": (e.get("sitelinks", {}).get("enwiki") or {}).get("title"),
             "wikipedias": sorted(m.group(1).replace("_", "-") for k in e.get("sitelinks", {})
                                  if (m := WIKI_SITE.match(k)) and m.group(1) not in NON_LANGUAGE_WIKIS)}
        for pid, (rname, tmpl) in REGISTRY_PROPS.items():
            for st in c.get(pid, []):
                v = st.get("mainsnak", {}).get("datavalue", {}).get("value")
                if st.get("rank") != "deprecated" and isinstance(v, str):
                    f["registries"].append({"registry": rname, "id": v, "property": pid,
                                            "url": tmpl.format(v=v, digits=re.sub(r"\D", "", v))})
        for pid, key in JOURNAL_ID_PROPS.items():
            vals = [st.get("mainsnak", {}).get("datavalue", {}).get("value") for st in c.get(pid, [])
                    if st.get("rank") != "deprecated"]
            vals = sorted(v for v in vals if isinstance(v, str))
            if vals:
                f["ids"][key] = vals
        for pid in list(FACT_PROPS) + list(ASSOC_PROPS) + ["P856"]:
            for st in c.get(pid, []):
                if st.get("rank") == "deprecated" or "P582" in st.get("qualifiers", {}):
                    continue   # deprecated, or ended (an "end time" is recorded): past owners etc.
                dv = st.get("mainsnak", {}).get("datavalue", {}).get("value")
                if pid == "P856" and isinstance(dv, str):
                    f["websites"].append(dv)
                elif isinstance(dv, dict) and "id" in dv:
                    key = FACT_PROPS.get(pid) or ("assoc", pid)
                    f["_vals"].setdefault(key, set()).add(dv["id"])
                    if _sourced(st):
                        f["_ref"].add((pid, dv["id"]))
                    value_ids.add(dv["id"])
        out[q] = f
    labels = {k: v.get("labels", {}).get("en", {}).get("value", k)
              for k, v in _entities(sorted(value_ids), "labels").items()}
    cls = " ".join(f"wd:{c}" for c in STATE_CLASSES)
    classed = {}
    for i in range(0, len(qids), 200):
        vals = " ".join(f"wd:{q}" for q in qids[i:i + 200])
        for r in _sparql(f"SELECT ?item ?c WHERE {{ VALUES ?item {{ {vals} }} VALUES ?c {{ {cls} }} "
                         f"?item wdt:P31/wdt:P279* ?c . }}"):
            classed.setdefault(r["item"]["value"].rsplit("/", 1)[1], set()).add(
                STATE_CLASSES[r["c"]["value"].rsplit("/", 1)[1]])
        time.sleep(1)
    kind_of = _kinds(qids)
    res = {}
    for q, f in out.items():
        v = f.pop("_vals")
        refd = f.pop("_ref")
        res[q] = {"label": f["label"], "websites": sorted(f["websites"]),
                  "registries": sorted(f["registries"], key=lambda r: (r["registry"], r["id"])),
                  "journal_ids": f["ids"], "enwiki": f["enwiki"], "wikipedias": f["wikipedias"],
                  **{k: sorted({labels.get(x, x) for x in v.get(k, ())})
                     for k in ("country", "owned_by", "political_alignment", "political_ideology")},
                  "classed_as": sorted(classed.get(q, ())),
                  "kind": kind_of.get(q),
                  "associations": {ASSOC_PROPS[pid]: sorted(({"label": labels.get(x, x), "wikidata": x,
                                                              "sourced": (pid, x) in refd}
                                                             for x in v[("assoc", pid)]),
                                                            key=lambda d: (d["label"], d["wikidata"]))
                                   for pid in ASSOC_PROPS if ("assoc", pid) in v}}
    log(f"  Wikidata facts for {len(res):,} items")
    return res


# References that only say where a statement was copied from (a Wikipedia edition) are not sources.
IMPORT_PROPS = {"P143", "P4656", "P813", "P3452"}   # imported from, Wikimedia import URL, retrieved, inferred from


def _sourced(st: dict) -> bool:
    """True when a Wikidata statement cites at least one reference beyond an import note."""
    return any(set(r.get("snaks", {})) - IMPORT_PROPS for r in st.get("references", []))


def _kinds(qids: list[str]) -> dict:
    """Wikidata ID -> kind of source (SOURCE_KINDS), or absent when no class matches."""
    order = {k: i for i, (k, _) in enumerate(SOURCE_KINDS)}
    values = " ".join(f'(wd:{c} "{k}")' for k, cs in SOURCE_KINDS for c in cs)
    out = {}
    for i in range(0, len(qids), 100):
        vals = " ".join(f"wd:{q}" for q in qids[i:i + 100])
        for r in _sparql(f"SELECT ?item ?k WHERE {{ VALUES ?item {{ {vals} }} "
                         f"VALUES (?c ?k) {{ {values} }} ?item wdt:P31/wdt:P279* ?c . }}"):
            q, k = r["item"]["value"].rsplit("/", 1)[1], r["k"]["value"]
            if q not in out or order[k] < order[out[q]]:
                out[q] = k
        time.sleep(1)
    log(f"  kinds of source for {len(out):,} of {len(qids):,} items")
    return out


def _reachable(host: str) -> bool:
    import socket
    try:
        socket.getaddrinfo(host, 443)
        return True
    except OSError:
        return False


def propublica(ein: str) -> dict | None:
    """Latest Form 990 filing with financial data in ProPublica's Nonprofit Explorer."""
    p = cache.path("outlets", "propublica", ein)
    hit = cache.load(p)
    if hit is not None:
        return hit or None
    try:
        d = get_json(f"https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json",
                     retries=3)
    except Exception:
        d = None
    rec = None
    fs = (d or {}).get("filings_with_data") or []
    if fs:
        f = max(fs, key=lambda x: x.get("tax_prd_yr") or 0)
        rec = {"year": f.get("tax_prd_yr"), "total_revenue": f.get("totrevenue"),
               "form": {0: "990", 1: "990-EZ", 2: "990-PF"}.get(f.get("formtype"), str(f.get("formtype"))),
               "url": f"https://projects.propublica.org/nonprofits/organizations/{ein}"}
    cache.save(p, rec or {})
    return rec


def crossref_journal(issn: str) -> dict | None:
    """Crossref's record for a journal ISSN: publisher and how many DOIs it has registered."""
    p = cache.path("outlets", "crossref", issn)
    hit = cache.load(p)
    if hit is not None:
        return hit or None
    try:
        d = get_json(f"https://api.crossref.org/journals/{issn}", retries=3)
    except Exception:
        d = None
    m = (d or {}).get("message") or {}
    rec = ({"title": m.get("title"), "publisher": m.get("publisher"),
            "dois": (m.get("counts") or {}).get("total-dois"),
            "url": f"https://api.crossref.org/journals/{issn}"} if m else None)
    cache.save(p, rec or {})
    return rec


JOURNAL_KINDS = {"academic journal", "predatory journal"}


def checklist(e: dict) -> dict | None:
    """The same mechanical checklist for every organisation or journal: each item is found
    (with its evidence) or not found in these records. No total, no score."""
    A = e.get("associations") or {}
    names = lambda rel: [v["label"] for v in A.get(rel, [])]  # noqa: E731
    is_org = e.get("kind") in ORG_KINDS or "designated as terrorist by" in A
    is_journal = (e.get("kind") in JOURNAL_KINDS
                  or (e.get("academic_level") or {}).get("type") == "journal or series")
    is_publisher = not (is_org or is_journal) and (e.get("kind") in PUBLISHER_KINDS or e.get("books"))
    if not (is_org or is_journal or is_publisher):
        return None
    wr = e.get("wikipedia_rating")
    independent = [x for x, ok in (("independent quality", e.get("independent_quality")),
                                   ("audience score", e.get("audience_leaning")),
                                   ("MBFC", e.get("mbfc")), ("AllSides", e.get("allsides_2018"))) if ok]
    items = []
    add = lambda label, found, detail="", links=(): items.append(  # noqa: E731
        {"check": label, "found": bool(found), "detail": detail if found else "", "links": list(links) if found else []})
    if is_org:
        regs = e.get("registries") or []
        add("registered in a public registry", regs,
            "; ".join(f"{r['registry']} {r['id']}" for r in regs), [r["url"] for r in regs])
        add("funders recorded", names("funded by") + names("sponsor"),
            ", ".join(names("funded by") + names("sponsor")))
        add("founders recorded", names("founded by"), ", ".join(names("founded by")))
        lead = names("chair") + names("director or manager") + names("chief executive")
        add("leadership recorded", lead, ", ".join(lead))
        aff = names("parent organisation") + names("affiliation") + names("member of")
        add("parent organisation, affiliation or membership recorded", aff, ", ".join(aff))
        pol = (e.get("political_alignment") or []) + (e.get("political_ideology") or [])
        add("political alignment or ideology recorded", pol, ", ".join(pol))
        add("designated as terrorist by a government or international body",
            names("designated as terrorist by"), ", ".join(names("designated as terrorist by")))
        filings = [r["filings"] for r in regs if r.get("filings")]
        if any(r["property"] == "P1297" for r in regs):
            f = filings[0] if filings else None
            add("US public tax filing (Form 990) found", f,
                f"{f['form']} for {f['year']}, total revenue ${f['total_revenue']:,}" if f and f.get("total_revenue") is not None
                else (f"{f['form']} for {f['year']}" if f else ""), [f["url"]] if f else [])
    if is_journal:
        ids = e.get("journal_ids") or {}
        ac = e.get("academic_level") or {}
        add("ISSN recorded", ids.get("issn"), ", ".join(ids.get("issn", [])))
        add("publisher recorded", names("publisher"), ", ".join(names("publisher")))
        idx = names("indexed in")
        add("indexed in Scopus", ids.get("scopus_id") or any("Scopus" in x for x in idx),
            ", ".join(ids.get("scopus_id", [])) or "listed on Wikidata")
        others = [x for x in idx if "Scopus" not in x]
        add("indexed elsewhere (e.g. Web of Science, PubMed)", others, ", ".join(others))
        add("listed in the Directory of Open Access Journals", ids.get("doaj_id") or ac.get("in_doaj"),
            ", ".join(ids.get("doaj_id", [])) or "per JUFO")
        add("academic level assigned (JUFO, Finland)", ac.get("level") is not None,
            f"level {ac.get('level')}" + (f"; Denmark level {ac['denmark_level']}" if ac.get("denmark_level") is not None else ""),
            [ac["url"]] if ac.get("url") else [])
        cr = e.get("crossref")
        add("registers DOIs with Crossref", cr and cr.get("dois"),
            f"{cr['dois']:,} DOIs, publisher {cr.get('publisher')}" if cr and cr.get("dois") else "",
            [cr["url"]] if cr else [])
        add("classed as a predatory journal on Wikidata", e.get("kind") == "predatory journal", "yes")
    if is_publisher:
        bk = e.get("books") or {}
        ac = e.get("academic_level") or {}
        add("found on Wikidata", e.get("wikidata"), e.get("wikidata") or "",
            [f"https://www.wikidata.org/wiki/{e['wikidata']}"] if e.get("wikidata") else [])
        add("classed as a self-publishing company or platform on Wikidata",
            e.get("kind") == "self-publishing company or platform", "yes")
        own = (e.get("owned_by") or []) + names("parent organisation")
        add("owner or parent organisation recorded", own, ", ".join(own))
        add("founders recorded", names("founded by"), ", ".join(names("founded by")))
        aff = names("affiliation") + names("member of")
        add("affiliation or membership recorded", aff, ", ".join(aff))
        pol = (e.get("political_alignment") or []) + (e.get("political_ideology") or [])
        add("political alignment or ideology recorded", pol, ", ".join(pol))
        add("academic level assigned (JUFO, Finland)", ac.get("level") is not None,
            f"level {ac.get('level')}", [ac["url"]] if ac.get("url") else [])
        wp = e.get("wikipedias") or []
        add("has a Wikipedia article in any language", wp,
            f"{len(wp)} language edition{'s' if len(wp) != 1 else ''}: {', '.join(wp[:12])}"
            + ("…" if len(wp) > 12 else ""))
        if bk.get("books"):
            add("cited books found on Open Library", bk.get("on_open_library"),
                f"{bk['on_open_library']} of {bk['books']}; languages: "
                + ", ".join(f"{k} {v}" for k, v in bk.get("languages_open_library", {}).items()))
    add("rated on Wikipedia's list", wr, (RSP_STATUS.get(wr["status"], wr["status"]) if wr else ""))
    add("rated by an independent assessor", independent, ", ".join(independent))
    add("has an English Wikipedia article", e.get("enwiki"), e.get("enwiki") or "",
        [f"https://en.wikipedia.org/wiki/{e['enwiki'].replace(' ', '_')}"] if e.get("enwiki") else [])
    return {"type": "organisation" if is_org else "journal" if is_journal else "book publisher",
            "items": items}


# Domain endings reserved by their registries for one kind of body. Read from the domain alone.
DOMAIN_CLASSES = [
    ("government", re.compile(r"(^|\.)(gov|mil|gouv|gob|govt|go|gv|gub|gc|nic|government|admin|"
                              r"mil|kormany|vlada|gov\.[a-z]{2})\.[a-z]{2}$|\.(gov|mil)$|"
                              r"(^|\.)(gov|gouv|gob|govt)\.[a-z]{2}$")),
    ("academic", re.compile(r"\.edu$|(^|\.)(ac|edu)\.[a-z]{2}$")),
    ("international organisation", re.compile(r"\.int$")),
]


def domain_class(key: str) -> str | None:
    """'government', 'academic' or 'international organisation' when the domain's ending is
    reserved for that kind of body (e.g. .gov, gov.az, nic.in, .edu, ac.uk, .int)."""
    if key.startswith("name:"):
        return None
    suffix = key.split(".", 1)[1] if "." in key else key
    for name, rx in DOMAIN_CLASSES:
        if rx.search(key) or rx.search("x." + suffix):
            return name
    return None


def _search_publishers(names: dict) -> dict:
    """Book publishers named in citations but not found as Wikipedia titles: search Wikidata
    labels and aliases in English and in the languages of their books (per Open Library).
    A name is matched only when exactly one item's label or alias equals it (ignoring case,
    punctuation and a leading "the") and that item is an organisation of a kind in
    SEARCH_OK_KINDS. names: {name: [search languages]}. Returns {name: qid}. Cached."""
    cand = {}
    for i, (name, langs) in enumerate(sorted(names.items())):
        p = cache.path("outlets", "wdsearch", re.sub(r"\W+", "_", name.lower())[:80] + "_" +
                       "-".join(langs))
        hits = cache.load(p)
        if hits is None:
            hits = []
            for lang in langs:
                d = get_json(WD_API, {"action": "wbsearchentities", "search": name, "language": lang,
                                      "uselang": "en", "type": "item", "limit": "10", "format": "json"})
                hits += [[x["id"], (x.get("match") or {}).get("text", "")] for x in d.get("search", [])]
                time.sleep(0.2)
            cache.save(p, hits)
        exact = {q for q, t in hits if _norm(t) == _norm(name)}
        if len(exact) == 1:
            cand[name] = next(iter(exact))
        if i % 200 == 199:
            log(f"  Wikidata search: {i + 1:,} of {len(names):,} publisher names")
    kinds = _kinds(sorted(set(cand.values()))) if cand else {}
    return {n: q for n, q in cand.items() if kinds.get(q) in SEARCH_OK_KINDS}


def book_stats(records: list[dict], books_data: dict) -> dict:
    """Per source key: the books cited from it (by ISBN), where their ISBNs were issued, and
    their languages per Open Library."""
    from collections import Counter
    from . import books as bk
    B = (books_data or {}).get("books", {})
    out = {}
    for r in records:
        for it in (r.get("sources") or {}).get("items", []):
            if not it["id"].startswith("isbn:"):
                continue
            isbn = it["id"][5:]
            st = out.setdefault(it["source"], {"isbns": set(), "groups": Counter(), "languages": Counter(),
                                               "open_library": 0, "invalid": 0})
            if isbn in st["isbns"]:
                continue
            st["isbns"].add(isbn)
            sp = bk.split(isbn)
            st["groups"][sp["agency"] if sp else "not in the ISBN range file"] += 1
            ol = B.get(isbn)
            if ol:
                st["open_library"] += 1
                for lang in ol.get("languages") or ["not recorded"]:
                    st["languages"][bk.lang_name(lang)] += 1
    return {k: {"books": len(v["isbns"]), "on_open_library": v["open_library"],
                "isbn_issued_by": dict(v["groups"].most_common()),
                "languages_open_library": dict(v["languages"].most_common())}
            for k, v in out.items()}


# ---------------------------------------------------------------- build
def _norm(name: str) -> str:
    n = name.lower().strip()
    n = re.sub(r"^the\s+", "", n)
    return re.sub(r"[^\w]+", " ", n).strip()


def combined_status(rows: list[dict]) -> str:
    """One rating for a source that several list entries match. Each entry counts with its own
    row status (a status quoted inside an entry's text, e.g. a past rating, is not used).
    When one entry is the plain name and the others are separate parts of the site named after
    it without a qualifier in brackets ("The Guardian" and "The Guardian blogs"), the plain entry
    rates the source. Entries qualified by topic or period in brackets ("Fox News (talk
    shows)"), or otherwise different, give "m" (varies) unless they all agree."""
    if not rows:
        return None
    sts = {r["status"] for r in rows}
    if len(sts) == 1:
        return sts.pop()
    names = sorted((r["id"] for r in rows), key=lambda n: (len(n), n))
    base = names[0]
    others = names[1:]
    if base and all(o.startswith(base + " ") and "(" not in o for o in others):
        return next(r["status"] for r in rows if r["id"] == base)
    return "m"


def build(records: list[dict], min_citations_for_wikidata: int = 2) -> dict:
    from collections import Counter
    cited, spelled = Counter(), {}
    for r in records:
        for s in r.get("sources", {}).get("list", []):
            cited[s["source"]] += s["citations"]
            nm = s.get("name_as_cited") or s.get("publisher_name_from_isbn")
            if nm:
                spelled.setdefault(s["source"], Counter())[nm] += s["citations"]
    # keys are lower-cased; Wikipedia titles are case-sensitive, so look names up as cited
    as_cited = {k: min(v, key=lambda x: (-v[x], x)) for k, v in spelled.items()}
    keys = sorted(k for k in cited if k.startswith("name:") or "." in k)
    log(f"{len(keys):,} distinct sources cited across {len(records)} articles")

    R = rsp()
    by_dom, by_name = {}, {}
    for row in R["rows"]:
        for d in row["domains"]:
            if "/" not in d:   # entries for one section of a site (a path) are not matched by domain
                by_dom.setdefault(d, []).append(row)
        for n in (row["article"], row["id"]):
            if n:
                by_name.setdefault(_norm(n), []).append(row)
    L, Rb, MB, DD = lin(), robertson(), mbfc(), domaindemo()

    # Wikidata items: from RSP articles, from names as Wikipedia titles, from domains (P856)
    names = sorted({as_cited.get(k, k[5:]) for k in keys if k.startswith("name:") and cited[k] >= min_citations_for_wikidata})
    rsp_titles = sorted({row["article"] for row in R["rows"] if row["article"]})
    log(f"  looking up {len(names) + len(rsp_titles):,} titles")
    tq = qids_for_titles(rsp_titles + [n for n in names])
    tq_norm = {_norm(t): q for t, q in tq.items()}
    # book publishers: the Wikidata item holding a cited ISBN's publisher prefix (P3035), and an
    # exact Wikidata search for publishers named in book citations but not found as titles
    from . import books as bk
    books_data, _ = bk.load()
    BS = book_stats(records, books_data)
    for v in (books_data or {}).get("prefixes", {}).values():
        tq_norm.setdefault(_norm(v["label"]), v["wikidata"])
    B = (books_data or {}).get("books", {})
    langs_of = {}
    for r in records:
        for it in (r.get("sources") or {}).get("items", []):
            if it["id"].startswith("isbn:") and it["source"].startswith("name:"):
                for l in (B.get(it["id"][5:]) or {}).get("languages") or []:
                    if l in MARC_TO_WIKI:
                        langs_of.setdefault(it["source"], set()).add(MARC_TO_WIKI[l])
    unfound = {as_cited.get(k, k[5:]): ["en"] + sorted(langs_of.get(k, ()))[:3]
               for k in keys if k.startswith("name:") and k in BS
               and cited[k] >= min_citations_for_wikidata
               and _norm(as_cited.get(k, k[5:])) not in tq_norm}
    log(f"  Wikidata search for {len(unfound):,} book publishers not found as titles")
    searched = _search_publishers(unfound)
    for n, q in searched.items():
        tq_norm.setdefault(_norm(n), q)
    log(f"  {len(searched):,} matched")
    doms = [k for k in keys if not k.startswith("name:") and cited[k] >= min_citations_for_wikidata]
    dq = qids_for_domains(doms)
    # websites whose official address on Wikidata is the cited subdomain (academic.oup.com)
    hosts = {}
    for r in records:
        for it in (r.get("sources") or {}).get("items", []):
            if it["id"].startswith("url:") and it["source"] in cited and it["source"] not in dq:
                h = it["id"][4:].split("/", 1)[0].split("?", 1)[0]
                if h != it["source"]:
                    hosts.setdefault(it["source"], Counter())[h] += 1
    sub = [h for k, c in hosts.items() if cited[k] >= min_citations_for_wikidata
           for h, _ in c.most_common(3)]
    log(f"  looking up {len(sub):,} cited subdomains on Wikidata")
    sq = qids_for_domains(sorted(set(sub))) if sub else {}
    for k, c in hosts.items():
        for h, _ in c.most_common(3):
            if h in sq:
                dq.setdefault(k, sq[h])
                break
    want_names = {_norm(as_cited.get(k, k[5:])) for k in keys if k.startswith("name:")}
    all_q = sorted(set(tq.values()) | set(dq.values())
                   | {q for n, q in tq_norm.items() if n in want_names}, key=lambda q: int(q[1:]))
    # A name cited as a book publisher that matched a Wikipedia title which is not an
    # organisation (the publisher "Verso" -> "Recto and verso") is matched again by the exact
    # publisher search instead (rule of 2026-11-06).
    pub_names = {k: as_cited.get(k, k[5:]) for k in keys if k.startswith("name:") and k in BS}
    pub_q = {k: tq_norm.get(_norm(n)) for k, n in pub_names.items() if tq_norm.get(_norm(n))}
    orgs = organisations(sorted(set(pub_q.values())))
    wrong = {k: q for k, q in pub_q.items() if q not in orgs}
    if wrong:
        log(f"  {len(wrong):,} publisher names matched a non-organisation; searching again")
        want = {pub_names[k]: ["en"] + sorted(langs_of.get(k, ()))[:3] for k in wrong}
        again = _search_publishers(want)
        # a short imprint name ("Verso", "Penguin") is often labelled with its trade word on
        # Wikidata; try those forms, still requiring one exact, unique publisher match
        for suffix in (" Books", " Publishing", " Press"):
            left = {n + suffix: l for n, l in want.items() if n not in again and not n.lower().endswith(suffix.lower())}
            for n2, q2 in _search_publishers(left).items():
                again.setdefault(n2[: -len(suffix)], q2)
        for k in wrong:
            n = _norm(pub_names[k])
            tq_norm.pop(n, None)
            if pub_names[k] in again:
                tq_norm[n] = again[pub_names[k]]
        all_q = sorted(set(all_q) | set(again.values()), key=lambda q: int(q[1:]))
    F = facts(all_q)

    def rsp_for(key):
        if key.startswith("name:"):
            return by_name.get(_norm(key[5:]), [])
        parts = key.split(".")
        for i in range(len(parts) - 1):
            got = by_dom.get(".".join(parts[i:]))
            if got:
                return got
        return []

    out = {}
    for k in keys:
        rows = rsp_for(k)
        q = None
        if rows and rows[0]["article"]:
            q = tq.get(rows[0]["article"])
        if q is None:
            q = tq_norm.get(_norm(k[5:])) if k.startswith("name:") else dq.get(k)
        f = F.get(q) if q else None
        dom = None if k.startswith("name:") else k
        if dom is None and f:   # a named publication: use its official website for domain ratings
            for w in f["websites"]:
                cand = re.sub(r"^https?://(www\.)?", "", w).split("/")[0].lower()
                if lookup(cand, L)[0] or lookup(cand, Rb)[0] or lookup(cand, DD)[0]:
                    dom = cand
                    break
        lk, lv = lookup(dom, L) if dom else (None, None)
        rk, rv = lookup(dom, Rb) if dom else (None, None)
        mk, mv = lookup(dom, MB) if dom else (None, None)
        dk, dv = lookup(dom, DD) if dom else (None, None)
        status = combined_status(rows)
        e = {
            "name": f["label"] if f else (as_cited.get(k, k[5:]) if k.startswith("name:") else k),
            "wikidata": q,
            "wikipedia_rating": ({"status": status,
                                  "statuses": sorted({row["status"] for row in rows}),
                                  "entries": sorted([row["id"], row["status"]] for row in rows)}
                                 if rows else None),
            "independent_quality": {"domain": lk, "score": round(lv, 4)} if lv is not None else None,
            "audience_leaning": ({"domain": rk, "score": rv["score"], "accounts": rv["accounts"]}
                                 if rv else None),
            "audience_leaning_dd": {"domain": dk, "score": round(dv, 4)} if dv is not None else None,
            "allsides_2018": (ALLSIDES_LABEL.get(rv["allsides"]) if rv and rv["allsides"] is not None
                              else None),
            "mbfc": ({"domain": mk, "bias": mv["bias"], "factual_reporting": mv["factual_reporting"]}
                     if mv else None),
        }
        if k in BS:
            e["books"] = BS[k]
        dc = domain_class(k)
        if dc:
            e["domain_class"] = dc
        if f:
            e.update({x: f[x] for x in ("country", "owned_by", "political_alignment",
                                        "political_ideology", "classed_as", "kind", "associations",
                                        "registries", "journal_ids", "enwiki", "wikipedias")})
        out[k] = e

    # Rule A (2026-11-06): ratings of a website (who shares it, how reliable its pages are) are
    # applied to the website itself and to a news outlet cited by name, never to books or
    # scholarly papers: those are left unrated and the ratings are kept under "not_applied".
    for k, e in out.items():
        if is_scholarly(k, e):
            held = {x: e[x] for x in WEBSITE_RATINGS if e.get(x)}
            if held:
                e["website_ratings_not_applied"] = held
            for x in WEBSITE_RATINGS:
                e[x] = None
    # The same organisation under another web address (same Wikidata item, e.g. a site that
    # moved from .co.uk to .com): an unrated domain takes the ratings of the rated one, marked "via".
    by_q = {}
    for k, e in out.items():
        if e.get("wikidata") and not k.startswith("name:"):
            by_q.setdefault(e["wikidata"], []).append(k)
    for q, ks in by_q.items():
        if len(ks) < 2:
            continue
        for x in ("audience_leaning", "audience_leaning_dd", "independent_quality", "mbfc"):
            rated = sorted((k for k in ks if out[k].get(x)), key=lambda k: (-cited.get(k, 0), k))
            if not rated:
                continue
            for k in ks:
                if not out[k].get(x) and not is_scholarly(k, out[k]):
                    out[k][x] = {**out[rated[0]][x], "via": rated[0]}

    # recorded political affiliation: Wikidata alignment/ideology and the political categories
    # of the source's own English Wikipedia article (wtl/affiliation.py)
    from . import affiliation as af
    cats = af.fetch_categories([e.get("enwiki") for e in out.values() if e.get("enwiki")], log=log)
    for k, e in out.items():
        e["affiliation"] = af.labels_for(e, cats.get(e.get("enwiki")) if e.get("enwiki") else None)

    # academic level (JUFO) for publishers and journals, and for named sources without a kind
    todo = [k for k, e in out.items()
            if (e.get("kind") in ACADEMIC_KINDS or (k.startswith("name:") and not e.get("kind")))
            and cited[k] >= min_citations_for_wikidata]
    log(f"  JUFO lookups for {len(todo):,} publishers and journals")
    import socket
    try:
        socket.getaddrinfo("jufo-rest.csc.fi", 443)
        jufo_ok = True
    except OSError:
        log("  JUFO host cannot be resolved on this machine; academic levels left out this run")
        jufo_ok = False
    jufo_fails = 0
    for i, k in enumerate(todo):
        if not jufo_ok:
            break
        e = out[k]
        try:
            e["academic_level"] = (jufo(e["name"], ACADEMIC_KINDS.get(e.get("kind")))
                                   or (jufo(as_cited[k], ACADEMIC_KINDS.get(e.get("kind")))
                                       if as_cited.get(k) and as_cited[k] != e["name"] else None))
            jufo_fails = 0
        except Exception as ex:   # this name failed; after five failures in a row, stop asking
            jufo_fails += 1
            log(f"  JUFO lookup failed for {e['name'][:60]}: {str(ex)[:100]}")
            if jufo_fails >= 5:
                log("  JUFO failing repeatedly; academic levels not looked up for the rest of this run")
                jufo_ok = False
        if i % 200 == 199:
            log(f"  JUFO: {i + 1:,} of {len(todo):,}")
    # Wikipedia's whole list next to the independent datasets (every entry with a web domain,
    # cited or not), so the list itself can be compared with outside assessments.
    listed = []
    for row in R["rows"]:
        doms = [d for d in row["domains"] if "/" not in d and "." in d]
        q = rq = None
        for d in doms:
            q = q or (lookup(d, L)[0] and (d, lookup(d, L)[1]))
            rq = rq or (lookup(d, Rb)[0] and (d, lookup(d, Rb)[1]))
        listed.append({"entry": row["id"], "article": row["article"], "status": row["status"],
                       "statuses": row["statuses"], "domains": doms,
                       "independent_quality": round(q[1], 4) if q else None,
                       "audience_leaning": rq[1]["score"] if rq else None,
                       "allsides_2018": (ALLSIDES_LABEL.get(rq[1]["allsides"])
                                         if rq and rq[1]["allsides"] is not None else None)})
    listed.sort(key=lambda x: (x["entry"].lower(), x["status"]))
    # outside records for the checklist: US tax filings (ProPublica) and Crossref journal records
    if _reachable("projects.propublica.org"):
        for k, e in out.items():
            for r in e.get("registries") or []:
                if r["property"] == "P1297":
                    r["filings"] = propublica(re.sub(r"\D", "", r["id"]))
    else:
        log("  ProPublica host cannot be resolved; US tax filings left out this run")
    if _reachable("api.crossref.org"):
        for k, e in out.items():
            if e.get("kind") in ("academic journal", "predatory journal") or \
                    (e.get("academic_level") or {}).get("type") == "journal or series":
                for issn in (e.get("journal_ids") or {}).get("issn", [])[:2]:
                    cr = crossref_journal(issn)
                    if cr:
                        e["crossref"] = cr
                        break
    else:
        log("  Crossref host cannot be resolved; DOI registration left out this run")
    for e in out.values():
        cl = checklist(e)
        if cl:
            e["checklist"] = cl

    snap = {
        "built": dt.date.today().isoformat(),
        "wikipedia_list_compared": listed,
        "assessors": {
            "wikipedia_rating": {"name": "Wikipedia's Perennial sources list", "url": RSP_URL,
                                 "revisions": R["revisions"], "statuses": RSP_STATUS},
            "independent_quality": {"name": "Lin et al. 2023 aggregate of six expert rating sets",
                                    "reference": LIN_REF, "data": LIN_URL},
            "audience_leaning": {"name": "Robertson et al. 2018 partisan audience score",
                                 "reference": ROB_REF, "data": ROB_URL},
            "audience_leaning_dd": {"name": "DomainDemo 2025 partisan audience score (Yang et al.)",
                                    "reference": DD_REF, "data": DD_URL},
            "allsides_2018": {"name": "AllSides (2018)", "reference": ALLSIDES_REF},
            "affiliation": {"name": "Recorded political affiliation: Wikidata political alignment "
                                    "and ideology, and the political categories of the source's "
                                    "own English Wikipedia article",
                            "rule": "wtl/affiliation.py (2026-11-06)"},
            "mbfc": {"name": "Media Bias/Fact Check", "reference": MBFC_REF, "data": MBFC_URL},
            "academic_level": {"name": "Publication Forum (JUFO), Finland", "reference": JUFO_REF,
                               "data": JUFO_API},
            "wikidata": {"name": "Wikidata", "url": "https://www.wikidata.org/",
                         "retrieved": dt.date.today().isoformat()},
        },
        "sources": out,
    }
    OUTLETS_JSON.write_text(json.dumps(snap, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                            encoding="utf-8")
    return snap
