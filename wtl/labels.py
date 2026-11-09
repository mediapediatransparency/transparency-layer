"""Recorded labels of cited sources and cited authors, each with Wikipedia's own definition.

A label is a word Wikidata or English Wikipedia already attaches to a source or a person; this
project never assigns one. Sources: the labels of wtl/affiliation.py. Authors (only those a
citation links to a Wikipedia article, as in wtl/people.py):
- Wikidata: political ideology (P1142) and member of political party (P102);
- categories on the person's own Wikipedia article (visible ones only) of these forms:
  - an ideology word for people, with or without a nationality before it: "Israeli Zionists",
    "American socialists", "Jewish anti-Zionists";
  - an ideology adjective and one plural noun: "Marxist historians", "Anti-Zionist Jews";
  - "Critics of X": shown as "critic of X";
  - a school of thought or movement: a category whose name is also the title of a Wikipedia
    article that Wikidata records as a school of thought, movement or ideology ("New Historians").
  Topic categories ("Anti-Islam sentiment in Israel", "Liberalism in Israel") are not used: they
  say an article is about a subject, not that the person holds a view.

Definition: for each label, the English Wikipedia article it names (the ideology, party,
school or subject), its short description and the first sentence of its opening, with the
version read. Labels are shown as recorded, side by side, never added up into a side.
`wtl labels` writes data/labels.json.
"""

import datetime as dt
import json
import re
import time

from .affiliation import FORMS, fetch_categories, norm_label
from .config import ROOT

LABELS_JSON = ROOT / "data" / "labels.json"

# plural word for people -> the label (adjective form, as used for sources)
PEOPLE = {"zionists": "zionist", "anti-zionists": "anti-zionist", "post-zionists": "post-zionist",
          "socialists": "socialist", "democratic socialists": "democratic socialist",
          "social democrats": "social democratic", "communists": "communist", "marxists": "marxist",
          "trotskyists": "trotskyist", "maoists": "maoist", "anarchists": "anarchist",
          "conservatives": "conservative", "neoconservatives": "neoconservative",
          "liberals": "liberal", "libertarians": "libertarian", "progressives": "progressive",
          "feminists": "feminist", "islamists": "islamist", "nationalists": "nationalist",
          "pacifists": "pacifist", "fascists": "fascist", "monarchists": "monarchist",
          "centrists": "centrist"}
ADJ = sorted({v for v in PEOPLE.values()} | {"far-left", "far-right", "left-wing", "right-wing"},
             key=len, reverse=True)
NAT = r"(?-i:(?:[A-Z][\w'’.-]+ ){0,2})"   # nationality or place words: capitalised
PEOPLE_RX = re.compile(r"^" + NAT + r"(" + "|".join(re.escape(k) for k in
                                                    sorted(PEOPLE, key=len, reverse=True)) + r")$", re.I)
ADJ_RX = re.compile(r"^" + NAT + r"(" + "|".join(re.escape(a) for a in ADJ) + r") ([A-Za-z]+s|Jews)$", re.I)
CRITIC_RX = re.compile(r"^Critics of (.+)$")
TOPIC_RX = re.compile(r"\b(in|of|by|from|and|on|about|for|against|to|with)\b")   # topics, not views
SCHOOL_TYPES = {"Q1387659": "school of thought", "Q2738074": "political movement",
                "Q49773": "social movement", "Q12909644": "political ideology", "Q7257": "ideology",
                "Q1150070": "historiographical school", "Q3427021": "school of thought (historiography)"}
NOUN = {v: k for k, v in FORMS.items()}   # adjective -> the ideology's name ("zionist" -> "zionism")
NOUN.update({"feminist": "feminism", "pacifist": "pacifism", "trotskyist": "trotskyism",
             "maoist": "maoism", "monarchist": "monarchism", "post-zionist": "post-zionism",
             "democratic socialist": "democratic socialism", "left-wing": "left-wing politics",
             "right-wing": "right-wing politics", "far-left": "far-left politics",
             "far-right": "far-right politics", "centre-left": "centre-left politics",
             "centre-right": "centre-right politics", "centrist": "centrism"})


def person_labels(cats: list[str], facts: dict, schools: set[str], sitelinks: dict | None = None) -> list[dict]:
    """[{label, article, from}] for one cited author."""
    out = {}
    for key, src in (("political_ideology", "Wikidata: political ideology"),
                     ("political_party", "Wikidata: member of political party"),
                     ("former_political_party", "Wikidata: member of political party (ended)")):
        for v in facts.get(key) or []:
            lab = norm_label(v["label"])
            out.setdefault(lab, {"label": lab, "display": v["label"],
                                 "article": (sitelinks or {}).get(v["label"]) or (v["label"] if "party" in key else None),
                                 "from": src})
    for c in cats:
        m = PEOPLE_RX.match(c)
        a = ADJ_RX.match(c) if not m else None
        if m or (a and not TOPIC_RX.search(c)):
            lab = PEOPLE[m.group(1).lower()] if m else norm_label(a.group(1))
            out.setdefault(lab, {"label": lab, "article": None, "from": f"Wikipedia category: {c}"})
        elif CRITIC_RX.match(c):
            x = CRITIC_RX.match(c).group(1)
            out.setdefault(f"critic of {x}", {"label": f"critic of {x}", "display": f"critic of {x}", "article": x,
                                              "from": f"Wikipedia category: {c}"})
        elif c in schools:
            out.setdefault(c, {"label": c, "display": c, "article": c, "from": f"Wikipedia category: {c}"})
    return sorted(out.values(), key=lambda d: d["label"])


def _schools(cats: set[str], log=print) -> set[str]:
    """Category names that are also titles of articles Wikidata records as a school of thought,
    movement or ideology."""
    from .fetch.http import get_json
    from .fetch.mediawiki import api
    cands = sorted(c for c in cats if not TOPIC_RX.search(c) and not re.search(r"\d", c)
                   and len(c.split()) <= 4 and c[:1].isupper())
    qid = {}
    for i in range(0, len(cands), 50):
        d = api({"action": "query", "titles": "|".join(cands[i:i + 50]), "prop": "pageprops",
                 "ppprop": "wikibase_item|disambiguation"})
        for p in d.get("query", {}).get("pages", []):
            pp = p.get("pageprops") or {}
            if not p.get("missing") and "disambiguation" not in pp and pp.get("wikibase_item"):
                qid[p["title"]] = pp["wikibase_item"]
        time.sleep(0.3)
    log(f"  labels: {len(cands):,} candidate categories, {len(qid):,} also article titles")
    out, ids = set(), sorted(set(qid.values()))
    for i in range(0, len(ids), 50):
        d = get_json("https://www.wikidata.org/w/api.php", {"action": "wbgetentities", "ids": "|".join(ids[i:i + 50]),
                                                            "props": "claims", "format": "json"})
        for q, e in d.get("entities", {}).items():
            p31 = {(s.get("mainsnak", {}).get("datavalue", {}).get("value") or {}).get("id")
                   for s in e.get("claims", {}).get("P31", [])}
            if p31 & set(SCHOOL_TYPES):
                out.update(t for t, x in qid.items() if x == q)
    return out


def _value_sitelinks(qids: list[str], log=print) -> dict:
    """{value label: English Wikipedia title} for the political ideology and party values of
    these people, from Wikidata's own link between the value's item and its article."""
    from .fetch.http import get_json
    api = "https://www.wikidata.org/w/api.php"
    vids = set()
    for i in range(0, len(qids), 50):
        d = get_json(api, {"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]), "props": "claims",
                           "format": "json"})
        for e in d.get("entities", {}).values():
            for pid in ("P1142", "P102"):
                for st in e.get("claims", {}).get(pid, []):
                    v = (st.get("mainsnak", {}).get("datavalue", {}).get("value") or {})
                    if isinstance(v, dict) and v.get("id"):
                        vids.add(v["id"])
    out, ids = {}, sorted(vids)
    for i in range(0, len(ids), 50):
        d = get_json(api, {"action": "wbgetentities", "ids": "|".join(ids[i:i + 50]),
                           "props": "labels|sitelinks", "sitefilter": "enwiki", "languages": "en", "format": "json"})
        for e in d.get("entities", {}).values():
            lab = e.get("labels", {}).get("en", {}).get("value")
            t = e.get("sitelinks", {}).get("enwiki", {}).get("title")
            if lab and t:
                out[lab] = t
    log(f"  labels: {len(out):,} ideology and party values linked to an English Wikipedia article")
    return out


FIRST = re.compile(r"^(.+?[.!?])(?=\s+[A-Z\"“(]|\s*$)", re.S)


def definitions(titles: dict[str, str], log=print) -> dict:
    """{label: {article, revision, short_description, first_sentence}} for label -> article title."""
    from .fetch.mediawiki import api
    want = sorted(set(titles.values()))
    got = {}
    for i in range(0, len(want), 20):
        batch = want[i:i + 20]
        d = api({"action": "query", "titles": "|".join(batch), "redirects": "1",
                 "prop": "extracts|pageprops|info", "exintro": "1", "explaintext": "1", "exlimit": "20",
                 "ppprop": "wikibase-shortdesc|disambiguation"})
        q = d.get("query", {})
        back = {}
        for r in q.get("normalized", []) + q.get("redirects", []):
            back.setdefault(r["to"], []).append(r["from"])
        for p in q.get("pages", []):
            if p.get("missing") or "disambiguation" in (p.get("pageprops") or {}):
                continue
            ext = re.sub(r"\s+", " ", (p.get("extract") or "").strip())
            m = FIRST.match(ext)
            rec = {"article": p["title"], "revision": p.get("lastrevid"),
                   "short_description": (p.get("pageprops") or {}).get("wikibase-shortdesc"),
                   "first_sentence": (m.group(1) if m else ext)[:400]}
            names = {p["title"]}
            for n in list(names):
                for f in back.get(n, []):
                    names.add(f)
                    names.update(back.get(f, []))
            for n in names:
                got[n] = rec
        time.sleep(0.3)
    return {lab: got[t] for lab, t in titles.items() if t in got}


def article_for(label: str) -> str:
    noun = NOUN.get(label, label)
    return noun[:1].upper() + noun[1:]


def build(records: list[dict], log=print) -> dict:
    from .outlets import OUTLETS_JSON
    src = json.loads(OUTLETS_JSON.read_text(encoding="utf-8"))["sources"]
    authors = json.loads((ROOT / "data" / "authors.json").read_text(encoding="utf-8"))["authors"]
    src_labels = {l for v in src.values() for l in (v.get("affiliation") or {}).get("labels", [])
                  if l not in ("none recorded", "no entry")}
    titles = [t for t, v in authors.items() if v.get("wikidata")]
    log(f"  labels: {len(src_labels):,} source labels; categories of {len(titles):,} authors")
    cats = fetch_categories(titles, log)
    schools = _schools({c for t in titles for c in cats.get(t, [])}, log)
    links = _value_sitelinks([authors[t]["wikidata"] for t in titles], log)
    per_author = {t: person_labels(cats.get(t, []), authors[t], schools, links) for t in titles}
    per_author = {t: v for t, v in per_author.items() if v}
    arts = {l: article_for(l) for l in src_labels}
    for v in per_author.values():
        for x in v:
            arts.setdefault(x["label"], x["article"] or article_for(x["label"]))
    defs = definitions(arts, log)
    d = {"built": dt.date.today().isoformat(), "rule": __doc__.strip(),
         "schools": sorted(schools), "definitions": dict(sorted(defs.items())),
         "no_definition": sorted(l for l in arts if l not in defs),
         "authors": dict(sorted(per_author.items()))}
    LABELS_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    log(f"wrote {LABELS_JSON}: {len(defs):,} labels defined, {len(d['no_definition']):,} without an "
        f"article; {len(per_author):,} authors with at least one label")
    return d
