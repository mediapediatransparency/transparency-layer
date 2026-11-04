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
        res = get_json(f"{JUFO_API}/etsi.php", {"nimi": name, "tyyppi": t}) or []
        for r in res:
            if _norm(r.get("Name", "")) == _norm(name):
                found = r
                break
        if found:
            break
    rec = None
    if found:
        full = (get_json(f"{JUFO_API}/kanava/{found['Jufo_ID']}") or [{}])[0]
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


def qids_for_domains(domains: list[str]) -> dict:
    """Domain -> Wikidata ID via "official website" (P856). Picks the item with the fewest
    alternatives deterministically (lowest numeric ID) when several claim the same site."""
    out = {}
    for i in range(0, len(domains), 40):
        b = domains[i:i + 40]
        vals = " ".join(f"<{s}://{w}{d}{e}>" for d in b for s in ("http", "https")
                        for w in ("", "www.") for e in ("", "/"))
        rows = _sparql(f"SELECT ?item ?site WHERE {{ VALUES ?site {{ {vals} }} ?item wdt:P856 ?site . }}")
        for r in rows:
            site = r["site"]["value"]
            dom = re.sub(r"^https?://(www\.)?", "", site).rstrip("/")
            q = r["item"]["value"].rsplit("/", 1)[1]
            if dom not in out or int(q[1:]) < int(out[dom][1:]):
                out[dom] = q
        if i // 40 % 10 == 0:
            log(f"  Wikidata websites: {min(i + 40, len(domains)):,} of {len(domains):,}")
        time.sleep(1)
    return out


WD_API = "https://www.wikidata.org/w/api.php"
FACT_PROPS = {"P495": "country", "P17": "country", "P127": "owned_by", "P1387": "political_alignment",
              "P1142": "political_ideology"}
# Associations recorded on Wikidata, shown as facts with a link to the statement.
ASSOC_PROPS = {"P112": "founded by", "P749": "parent organisation", "P463": "member of",
               "P1416": "affiliation", "P8324": "funded by", "P859": "sponsor", "P488": "chair",
               "P3461": "designated as terrorist by", "P123": "publisher", "P8875": "indexed in"}
# Kind of source: Wikidata classes, checked in this order (instance of, or of a subclass);
# the first match wins. Labels checked on Wikidata.
SOURCE_KINDS = [
    ("predatory journal", ["Q65770378"]),
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
                  "university press": "publisher", "book publisher": "publisher"}


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
    ents = _entities(qids, "labels|claims")
    out, value_ids = {}, set()
    for q in qids:
        e = ents.get(q, {})
        c = e.get("claims", {})
        f = {"label": e.get("labels", {}).get("en", {}).get("value", q), "websites": [],
             "_vals": {}, "_ref": set()}
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
            if s.get("name_as_cited"):
                spelled.setdefault(s["source"], Counter())[s["name_as_cited"]] += s["citations"]
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
    L, Rb, MB = lin(), robertson(), mbfc()

    # Wikidata items: from RSP articles, from names as Wikipedia titles, from domains (P856)
    names = sorted({as_cited.get(k, k[5:]) for k in keys if k.startswith("name:") and cited[k] >= min_citations_for_wikidata})
    rsp_titles = sorted({row["article"] for row in R["rows"] if row["article"]})
    log(f"  looking up {len(names) + len(rsp_titles):,} titles")
    tq = qids_for_titles(rsp_titles + [n for n in names])
    tq_norm = {_norm(t): q for t, q in tq.items()}
    doms = [k for k in keys if not k.startswith("name:") and cited[k] >= min_citations_for_wikidata]
    dq = qids_for_domains(doms)
    all_q = sorted(set(tq.values()) | set(dq.values()), key=lambda q: int(q[1:]))
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
                if lookup(cand, L)[0] or lookup(cand, Rb)[0]:
                    dom = cand
                    break
        lk, lv = lookup(dom, L) if dom else (None, None)
        rk, rv = lookup(dom, Rb) if dom else (None, None)
        mk, mv = lookup(dom, MB) if dom else (None, None)
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
            "allsides_2018": (ALLSIDES_LABEL.get(rv["allsides"]) if rv and rv["allsides"] is not None
                              else None),
            "mbfc": ({"domain": mk, "bias": mv["bias"], "factual_reporting": mv["factual_reporting"]}
                     if mv else None),
        }
        if f:
            e.update({x: f[x] for x in ("country", "owned_by", "political_alignment",
                                        "political_ideology", "classed_as", "kind", "associations")})
        out[k] = e

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
    for i, k in enumerate(todo):
        if not jufo_ok:
            break
        e = out[k]
        try:
            e["academic_level"] = (jufo(e["name"], ACADEMIC_KINDS.get(e.get("kind")))
                                   or (jufo(as_cited[k], ACADEMIC_KINDS.get(e.get("kind")))
                                       if as_cited.get(k) and as_cited[k] != e["name"] else None))
        except Exception as ex:   # not reachable (e.g. DNS): leave the assessor out this run
            log(f"  JUFO not reachable, skipped: {str(ex)[:120]}")
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
            "allsides_2018": {"name": "AllSides (2018)", "reference": ALLSIDES_REF},
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
