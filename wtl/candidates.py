"""Choose which articles to analyse by a fixed rule, not by hand.

Rule: every article Wikipedia itself tags as being in a political contentious topic area, sorted
into kinds (people, news outlets, organisations, ideas and movements, events) by Wikidata, and
ranked by readership over the last 60 days. The top N of each kind in each area are taken.
Pages a person asks for are added on top and marked as requested.

Second rule, for subjects Wikipedia has no contentious-topic tag for (SUBJECTS below): every
article whose talk page carries the banner of the named WikiProjects, the groups of editors who
look after a subject. Kinds and ranking are the same. These areas are labelled "chosen by
subject" throughout, because here the project picks the subject, not Wikipedia.

Sources, all public:
- Talk pages in Category:Wikipedia pages about contentious topics, and the Arab-Israeli
  extended-confirmed category; the topic codes are read from their talk-page notices.
- Page views and Wikidata IDs from the MediaWiki API (prop=pageviews|pageprops).
- Kinds from the Wikidata Query Service (instance of / subclass of).
"""

import csv
import re
import sys
import time

from .config import ROOT
from .fetch import cache
from .fetch.http import get_json
from .fetch.mediawiki import api

CANDIDATES_CSV = ROOT / "data" / "candidates.csv"
REQUESTED_CSV = ROOT / "data" / "requested.csv"
SPARQL = "https://query.wikidata.org/sparql"

CT_CATEGORY = "Category:Wikipedia pages about contentious topics"
ECR_CATEGORY = "Category:Wikipedia pages subject to the extended confirmed restriction"
GS_TEMPLATE = "Template:Gs/talk notice"   # community-authorised general sanctions
AI_CATEGORY = "Category:Wikipedia pages subject to the extended confirmed restriction related to the Arab-Israeli conflict"

# Topic codes from Template:Contentious topics/list, grouped into the political areas we cover.
AREAS = {
    "A-I": ("Arab–Israeli conflict", {"a-i"}),
    "AP": ("US politics (includes DEI)", {"ap", "tpm", "ap2"}),
    "GS": ("Gender and sexuality (includes transgender topics)", {"gg", "ggtf", "gas", "pa", "gap"}),
    "EE": ("Eastern Europe and the Balkans (includes Russia and Ukraine)", {"ee", "e-e", "b", "rusukr"}),
    "AB": ("Abortion", {"ab"}),
    "RI": ("Race and intelligence", {"r-i"}),
    "IR": ("Iranian politics", {"irp", "iranpol"}),
    "KU": ("Kurds and Kurdistan", {"kurd"}),
    "SA": ("South Asia", {"sa", "ipa", "sl", "sasg", "caste"}),
    "AA": ("Armenia and Azerbaijan", {"aa2", "a-a", "gsaa", "aa", "acas"}),
    "CN": ("China: Uyghurs and Xinjiang", {"uyghur"}),
    "SY": ("Syrian civil war and ISIL", {"scwisil", "scw", "syria", "isil"}),
    "HA": ("Horn of Africa", {"horn"}),
    "TT": ("The Troubles (Northern Ireland)", {"tt"}),
}
# Second rule: areas chosen by subject. WikiProject banners on talk pages place an article under
# a subject; Wikipedia gives these subjects no contentious-topic designation.
SUBJECTS = {
    "CNX": ("China, Taiwan, Hong Kong and Tibet (chosen by subject)",
            ["Category:WikiProject China articles", "Category:WikiProject Taiwan articles",
             "Category:WikiProject Hong Kong articles", "Category:WikiProject Tibet articles"]),
    "SOC": ("Socialism, communism and Marxism (chosen by subject)",
            ["Category:WikiProject Socialism articles"]),
    "ISL": ("Islam (chosen by subject)", ["Category:WikiProject Islam articles"]),
}
AREAS.update({k: (name, set()) for k, (name, _) in SUBJECTS.items()})
RULE = {k: ("subject" if k in SUBJECTS else "contentious tag") for k in AREAS}
CODE_AREA = {c: k for k, (_, cs) in AREAS.items() for c in cs}
AI_TEMPLATES = re.compile(r"\{\{\s*(?:ArbCom Arab-Israeli enforcement|Contentious topics/Arab-Israeli"
                          r"|ARBPIA|Arab-Israeli Arbitration Enforcement)", re.I)
NOTICE = re.compile(r"\{\{\s*(?:Contentious topics?/[^|}]*|Ct/tn|CTOP|Ds/talk notice|Gs/[^|}]*|"
                    r"Discretionary sanctions|General sanctions[^|}]*)\s*(\|[^{}]*)?\}\}", re.I)

KINDS = ["journalist", "person", "media", "organisation", "idea", "event"]
KIND_NAMES = {"journalist": "Journalists and commentators", "person": "Other public figures",
              "media": "News outlets and media", "organisation": "Organisations",
              "idea": "Ideas, ideologies and movements", "event": "Events"}
# Wikidata classes: an item is of a kind if it is an instance of the class or of a subclass of it.
# Checked in this order; the first match wins. Broad classes (e.g. "concept", "occurrence") are
# left out because Wikidata files far too much under them.
CLASSES = [
    ("person", ["Q5"]),
    ("media", ["Q11033", "Q1193236", "Q1002697", "Q11032", "Q41298", "Q192283", "Q15265344",
               "Q2001305", "Q1153191"]),
    ("event", ["Q350604", "Q198", "Q178561", "Q645883", "Q2223653", "Q3199915", "Q40231",
               "Q273120", "Q124734", "Q2334719"]),
    ("place", ["Q6256", "Q3624078", "Q7275", "Q486972", "Q2221906", "Q17334923"]),
    ("organisation", ["Q43229"]),
    ("idea", ["Q7257", "Q12909644", "Q49773", "Q2738074", "Q9174", "Q2198855", "Q2915955",
              "Q1387659"]),
]
# Occupations (P106) that make a person a journalist or commentator; labels checked on Wikidata:
# journalist, columnist, political commentator, news presenter, pundit.
JOURNALIST_OCCUPATIONS = ["Q1930187", "Q1086863", "Q11499163", "Q270389", "Q1642960"]



def log(msg):
    print(msg, file=sys.stderr, flush=True)


def codes_in(wikitext: str) -> set[str]:
    """Political-area codes named in a talk page's contentious-topic notices."""
    areas = set()
    if AI_TEMPLATES.search(wikitext):
        areas.add("A-I")
    for m in NOTICE.finditer(wikitext):
        for part in (m.group(1) or "").split("|"):
            v = part.split("=", 1)
            key, val = (v[0].strip().lower(), v[1]) if len(v) == 2 else ("", v[0])
            if key not in ("", "topic", "topic2", "topic3", "1", "2", "3"):
                continue
            for tok in re.split(r"[,\s]+", val.strip().lower()):
                if tok in CODE_AREA:
                    areas.add(CODE_AREA[tok])
    return areas


def _api_retry(params: dict, tries: int = 6) -> dict:
    """Wikipedia occasionally returns a transient internal/database error; wait and retry."""
    for n in range(tries):
        try:
            return api(params)
        except Exception as e:
            if "internal_api_error" not in str(e) or n == tries - 1:
                raise
            wait = 15 * (n + 1)
            log(f"  transient API error, retrying in {wait}s: {str(e)[:80]}")
            time.sleep(wait)


def tagged_talk_pages(category: str) -> dict[str, str]:
    """Talk title -> wikitext for every article talk page (namespace 1) in the category.
    Progress is saved as it goes, so an interrupted run resumes where it stopped."""
    name = re.sub(r"\W+", "_", category)[:80]
    p = cache.path("candidates", "talk", name)
    hit = cache.load(p)
    if hit is not None:
        return hit
    part = cache.path("candidates", "talk", name + ".partial")
    saved = cache.load(part) or {"pages": {}, "cont": {}}
    out, cont = saved["pages"], saved["cont"]
    if out:
        log(f"  resuming {category[:40]}… at {len(out):,} talk pages")
    n = 0
    while True:
        gen = ({"generator": "embeddedin", "geititle": category, "geinamespace": "1",
                "geilimit": "50"} if category.startswith("Template:") else
               {"generator": "categorymembers", "gcmtitle": category, "gcmnamespace": "1",
                "gcmlimit": "50"})
        d = _api_retry({"action": "query", **gen, "prop": "revisions",
                        "rvprop": "content", "rvslots": "main", **cont})
        for pg in d.get("query", {}).get("pages", []):
            revs = pg.get("revisions")
            if revs:
                out[pg["title"]] = revs[0]["slots"]["main"].get("content", "")
        if "continue" not in d:
            break
        cont = d["continue"]
        n += 1
        if n % 20 == 0:
            cache.save(part, {"pages": out, "cont": cont})
            log(f"  {category[:40]}…: {len(out):,} talk pages")
    cache.save(p, out)
    part.unlink(missing_ok=True)
    return out


def project_articles(category: str) -> list[str]:
    """Article titles whose talk pages are in a WikiProject's article category (namespace 1)."""
    name = re.sub(r"\W+", "_", category)[:80]
    p = cache.path("candidates", "projects", name)
    hit = cache.load(p)
    if hit is not None:
        return hit
    out, cont = [], {}
    while True:
        d = _api_retry({"action": "query", "list": "categorymembers", "cmtitle": category,
                        "cmnamespace": "1", "cmlimit": "500", "cmprop": "title", **cont})
        out += [m["title"][len("Talk:"):] for m in d["query"]["categorymembers"]]
        if "continue" not in d:
            break
        cont = d["continue"]
        if len(out) % 10000 < 500:
            log(f"  {category[9:]}: {len(out):,}")
    out = sorted(set(out))
    cache.save(p, out)
    return out


def subject_rows(per_kind: int) -> list[dict]:
    """Rows for the subject areas. Kinds are looked up from the most-read article down until
    every kind has per_kind articles (or the subject runs out), so the result is the same as
    classifying every article, at a fraction of the Wikidata queries."""
    rows = []
    for area, (_, cats) in SUBJECTS.items():
        titles = sorted({t for c in cats for t in project_articles(c)})
        log(f"{area}: {len(titles):,} articles under {len(cats)} WikiProject banner(s)")
        info = article_info(titles)
        pool, seen = [], set()
        for t in titles:
            i = info.get(t)
            if (not i or i["missing"] or i["title"].startswith(("List of ", "Lists of "))
                    or i["title"] in seen):
                continue
            seen.add(i["title"])
            pool.append(i)
        pool.sort(key=lambda i: (-i["views"], i["title"]))
        got, j, step = {k: 0 for k in KINDS}, 0, 1500
        while j < len(pool) and min(got.values()) < per_kind:
            chunk = pool[j:j + step]
            kd = kinds([i["qid"] for i in chunk if i["qid"]])
            for i in chunk:
                k = (kd.get(i["qid"]) if i["qid"] else None) or {"kind": "other", "journalist": False}
                kind = "journalist" if k["kind"] == "person" and k["journalist"] else k["kind"]
                rows.append({"area": area, "kind": kind, "title": i["title"], "views_60d": i["views"],
                             "wikidata": i["qid"] or "", "journalist": k["journalist"]})
                if kind in got:
                    got[kind] += 1
            j += step
        # kinds still short were classified to the end of the pool; the rest are not needed
        log(f"  {area}: classified {min(j, len(pool)):,} of {len(pool):,} by readership")
    return rows


def article_info(titles: list[str]) -> dict[str, dict]:
    """Article -> {views, qid}. Page views are the last 60 days (MediaWiki PageViewInfo)."""
    p = cache.path("candidates", "info_v2")
    info = cache.load(p) or {}
    todo = [t for t in titles if t not in info]
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        # PageViewInfo returns views for only part of a batch at a time and signals the rest with
        # a continuation; follow it, or the remaining pages wrongly get zero views.
        params = {"action": "query", "titles": "|".join(batch), "prop": "pageviews|pageprops",
                  "ppprop": "wikibase_item", "pvipdays": "60", "redirects": "1"}
        d, cont = None, {}
        while True:
            part = _api_retry({**params, **cont})
            if d is None:
                d = part
            else:
                got = {pg["title"]: pg for pg in part.get("query", {}).get("pages", [])}
                for pg in d["query"]["pages"]:
                    extra = got.get(pg["title"], {}).get("pageviews")
                    if extra:
                        pg["pageviews"] = {**(pg.get("pageviews") or {}), **extra}
            if "continue" not in part:
                break
            cont = part["continue"]
        q = d.get("query", {})
        back = {r["to"]: r["from"] for r in q.get("redirects", [])}
        back.update({n["to"]: n["from"] for n in q.get("normalized", [])})
        for pg in q.get("pages", []):
            src = back.get(pg["title"], pg["title"])
            info[src] = {"title": pg["title"], "missing": pg.get("missing", False),
                         "views": sum(v or 0 for v in (pg.get("pageviews") or {}).values()),
                         "qid": (pg.get("pageprops") or {}).get("wikibase_item")}
        for t in batch:
            info.setdefault(t, {"title": t, "missing": True, "views": 0, "qid": None})
        if (i // 50) % 40 == 0:
            log(f"  page views: {min(i + 50, len(todo)):,} of {len(todo):,}")
            cache.save(p, info)
    cache.save(p, info)
    return info


def kinds(qids: list[str]) -> dict[str, dict]:
    """Wikidata ID -> {kind, journalist}."""
    p = cache.path("candidates", "kinds_v2")
    known = cache.load(p) or {}
    todo = sorted({q for q in qids if q and q not in known})
    order = {k: i for i, (k, _) in enumerate(CLASSES)}
    values = " ".join(f"(wd:{c} \"{k}\")" for k, cs in CLASSES for c in cs)
    for i in range(0, len(todo), 150):
        batch = todo[i:i + 150]
        query = (f"SELECT ?item ?kind ?j WHERE {{ VALUES ?item {{ {' '.join('wd:' + q for q in batch)} }} "
                 f"{{ VALUES (?c ?kind) {{ {values} }} ?item wdt:P31/wdt:P279* ?c . }} "
                 f"OPTIONAL {{ VALUES ?occ {{ {' '.join('wd:' + o for o in JOURNALIST_OCCUPATIONS)} }} "
                 f"?item wdt:P106 ?occ . BIND(true AS ?j) }} }}")
        d = get_json(SPARQL, {"query": query, "format": "json"}, timeout=120)
        found = {}
        for b in d["results"]["bindings"]:
            q = b["item"]["value"].rsplit("/", 1)[1]
            k = b["kind"]["value"]
            cur = found.get(q)
            if cur is None or order[k] < order[cur["kind"]]:
                found[q] = {"kind": k, "journalist": "j" in b}
            if "j" in b:
                found[q]["journalist"] = True
        for q in batch:
            known[q] = found.get(q, {"kind": "other", "journalist": False})
        if (i // 150) % 10 == 0:
            log(f"  Wikidata kinds: {min(i + 150, len(todo)):,} of {len(todo):,}")
            cache.save(p, known)
        time.sleep(1)
    cache.save(p, known)
    return known


def requested() -> list[dict]:
    if not REQUESTED_CSV.exists():
        return []
    with open(REQUESTED_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build(per_kind: int = 25) -> list[dict]:
    talk = tagged_talk_pages(CT_CATEGORY)
    for src in (ECR_CATEGORY, GS_TEMPLATE):
        for t, w in tagged_talk_pages(src).items():
            talk.setdefault(t, w)
    for t, w in tagged_talk_pages(AI_CATEGORY).items():
        # Membership of the Arab-Israeli restriction category is itself the A-I designation.
        talk[t] = talk.get(t, "") + "\n{{ArbCom Arab-Israeli enforcement}}"
    areas = {}
    for t, w in talk.items():
        a = codes_in(w)
        if a:
            areas[t[len("Talk:"):]] = a
    log(f"{len(talk):,} tagged talk pages; {len(areas):,} articles in the political areas")
    info = article_info(sorted(areas))
    kd = kinds([i["qid"] for i in info.values() if i["qid"]])
    rows, seen_title = [], set()
    for art, ars in sorted(areas.items()):
        i = info.get(art)
        if not i or i["missing"] or i["title"].startswith(("List of ", "Lists of ")):
            continue
        k = kd.get(i["qid"]) if i["qid"] else None
        k = k or {"kind": "other", "journalist": False}
        kind = "journalist" if k["kind"] == "person" and k["journalist"] else k["kind"]
        for a in ars:
            if (a, i["title"]) in seen_title:   # several talk pages can redirect to one article
                continue
            seen_title.add((a, i["title"]))
            rows.append({"area": a, "kind": kind, "title": i["title"], "views_60d": i["views"],
                         "wikidata": i["qid"] or "", "journalist": k["journalist"]})
    rows += subject_rows(per_kind)
    chosen, seen = [], set()
    for a in AREAS:
        for kind in KINDS:
            pool = sorted((r for r in rows if r["area"] == a and r["kind"] == kind),
                          key=lambda r: (-r["views_60d"], r["title"]))
            for rank, r in enumerate(pool[:per_kind], 1):
                # subject pools are classified only as far down as needed, so their size per
                # kind is not known and is left blank
                chosen.append({**r, "rank": rank, "of": "" if a in SUBJECTS else len(pool),
                               "reason": "most-read",
                               "rule": RULE[a]})
                seen.add((a, r["title"]))
    for q in requested():
        if (q["area"], q["title"]) not in seen:
            chosen.append({"area": q["area"], "kind": q.get("kind", ""), "title": q["title"],
                           "views_60d": "", "wikidata": "", "journalist": "", "rank": "", "of": "",
                           "reason": "requested", "rule": RULE.get(q["area"], "")})
    cols = ["area", "kind", "rank", "of", "title", "views_60d", "journalist", "wikidata", "reason",
            "rule"]
    with open(CANDIDATES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(chosen)
    counts = {}
    for r in rows:
        counts[(r["area"], r["kind"])] = counts.get((r["area"], r["kind"]), 0) + 1
    return chosen, counts
