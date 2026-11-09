"""The same article in other Wikipedias: do they cite the English article's main authors?
(pilot; not on the site)

For each language edition linked from the English article (Wikipedia's own interlanguage links),
its current wikitext is read and, for each of the English article's most-cited authors, we
check whether the author's surname appears inside that edition's footnotes or bibliography,
written as Wikidata spells the person's name in that language (and in Latin letters, for works
cited in their original language). Also: the number of footnotes, and the DOIs and ISBNs cited
there that the English article also cites.

A name found is a name found: it does not say how the work is used. Nothing is fetched about
Wikipedia editors.
"""

import re
from collections import Counter

from .fetch import cache
from .fetch.http import get_json

LANGS = ["he", "ar", "de", "fr", "es", "ru"]
REF = re.compile(r"<ref[^>/]*>(.*?)</ref>", re.S | re.I)
DOI = re.compile(r"10\.\d{4,9}/[^\s|}<\]]+", re.I)
ISBN = re.compile(r"(?:97[89][\d-]{10,14}|\b\d[\d-]{8,11}[\dXx]\b)")


def _api(lang: str, params: dict) -> dict:
    return get_json(f"https://{lang}.wikipedia.org/w/api.php", {"format": "json", "formatversion": "2", **params})


def langlinks(title: str) -> dict[str, str]:
    d = _api("en", {"action": "query", "titles": title, "prop": "langlinks", "lllimit": "max", "redirects": "1"})
    return {x["lang"]: x["title"] for x in d["query"]["pages"][0].get("langlinks", [])}


def wikitext(lang: str, title: str) -> tuple[str, int]:
    p = cache.path("crosswiki", f"{lang}_{title}")
    hit = cache.load(p)
    if hit is None:
        d = _api(lang, {"action": "query", "titles": title, "prop": "revisions", "rvprop": "ids|content",
                        "rvslots": "main", "redirects": "1"})
        r = d["query"]["pages"][0]["revisions"][0]
        hit = {"text": r["slots"]["main"]["content"], "revision": r["revid"]}
        cache.save(p, hit)
    return hit["text"], hit["revision"]


FOOT_TPL = re.compile(r"\{\{\s*(?:הערה|הערות שוליים|efn|sfn)\s*\|", re.I)   # Hebrew Wikipedia's footnote template


def _template_bodies(text: str) -> list[str]:
    out = []
    for m in FOOT_TPL.finditer(text):
        depth, i = 2, m.end()
        while i < len(text) and depth:
            if text.startswith("{{", i):
                depth += 2
                i += 2
            elif text.startswith("}}", i):
                depth -= 2
                i += 2
            else:
                i += 1
        out.append(text[m.end():i - 2])
    return out


def footnotes_of(text: str) -> list[str]:
    return REF.findall(text) + _template_bodies(text)


def _cited_part(text: str) -> str:
    """Footnotes, plus everything from the first bibliography-like heading on."""
    refs = " ".join(footnotes_of(text))
    m = re.search(r"^==+[^=\n]*(Bibliograph|Literatur|Sources|ספרות|מקורות|לקריאה|المراجع|مراجع|Литература|"
                  r"Источники|Bibliografía|Referencias|Notes|Références)[^=\n]*==+", text, re.M | re.I)
    return refs + " " + (text[m.start():] if m else "")


def names_in(qids: list[str], langs: list[str]) -> dict[str, dict[str, str]]:
    """{qid: {lang: label}} from Wikidata, with English as the Latin-letter form."""
    out = {}
    for i in range(0, len(qids), 50):
        d = get_json("https://www.wikidata.org/w/api.php", {"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]),
                                                            "props": "labels", "languages": "|".join(["en"] + langs),
                                                            "format": "json"})
        for q, e in d.get("entities", {}).items():
            out[q] = {k: v["value"] for k, v in e.get("labels", {}).items()}
    return out


def _surname(name: str) -> str:
    parts = re.sub(r"\(.*?\)", "", name).replace(",", " ").split()
    return parts[-1] if parts else name


def compare(title: str, en_text: str, authors: list[dict], langs=LANGS) -> dict:
    """authors: [{"name", "wikidata" or None, "sentences"}] for the English article's top authors."""
    ll = langlinks(title)
    qids = [a["wikidata"] for a in authors if a.get("wikidata")]
    loc = names_in(qids, langs) if qids else {}
    en_doi = {x.lower() for x in DOI.findall(en_text)}
    en_isbn = {re.sub(r"[^\dXx]", "", x).upper() for x in ISBN.findall(en_text)}
    rows = {}
    for lang in langs:
        if lang not in ll:
            continue
        text, rev = wikitext(lang, ll[lang])
        part = _cited_part(text)
        found = []
        for a in authors:
            forms = {_surname(a["name"])}
            if a.get("wikidata") and loc.get(a["wikidata"], {}).get(lang):
                forms.add(_surname(loc[a["wikidata"]][lang]))
            hit = any(len(f) > 2 and re.search(r"(?<!\w)" + re.escape(f) + r"(?!\w)", part) for f in forms)
            found.append(hit)
        doi = {x.lower() for x in DOI.findall(text)}
        isbn = {re.sub(r"[^\dXx]", "", x).upper() for x in ISBN.findall(text)}
        rows[lang] = {"title": ll[lang], "revision": rev, "footnotes": len(footnotes_of(text)),
                      "authors_found": [a["name"] for a, h in zip(authors, found) if h],
                      "authors_not_found": [a["name"] for a, h in zip(authors, found) if not h],
                      "share_of_top_authors_found": round(sum(found) / max(1, len(found)), 3),
                      "dois_shared_with_english": len(doi & en_doi), "dois": len(doi),
                      "isbns_shared_with_english": len(isbn & en_isbn), "isbns": len(isbn)}
    return {"article": title, "languages": rows}


AU_PARAM = re.compile(r"\|\s*(last|surname|author|first|given)(\d*)\s*=\s*([^|}\n]+)", re.I)


def latin_authors(text: str) -> list[tuple[str, int]]:
    """[(author, citations)] from the citation templates in an edition's footnotes, for names
    written in Latin letters (the scholarly catalogue used for the field holds names in Latin
    letters, so names in other scripts cannot be matched and are left out)."""
    c = Counter()
    for body in footnotes_of(text):
        parts = {}
        for kind, n, v in AU_PARAM.findall(body):
            parts.setdefault(n or "1", {})[kind.lower()] = v.strip()
        seen = set()
        for p in parts.values():
            name = p.get("author") or " ".join(x for x in (p.get("first") or p.get("given"), p.get("last") or p.get("surname")) if x)
            name = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", name).strip()
            if name and re.match(r"^[A-Za-zÀ-ž .'-]+$", name) and name not in seen:
                seen.add(name)
                c[name] += 1
    return c.most_common()


WLINK = re.compile(r"\[\[([^|\]#]+)(?:\|[^\]]*)?\]\]")


def linked_people(lang: str, text: str) -> list[tuple[str, int]]:
    """[(English name, footnotes)] for people linked by name inside an edition's footnotes: each
    link is followed to its Wikidata item, kept if Wikidata says it is a human, and named by its
    English label. Names written without a link are not counted."""
    c = Counter()
    for body in footnotes_of(text):
        for t in dict.fromkeys(x.strip() for x in WLINK.findall(body)):
            c[t] += 1
    titles = [t for t in c if ":" not in t]
    qid = {}
    for i in range(0, len(titles), 50):
        d = _api(lang, {"action": "query", "titles": "|".join(titles[i:i + 50]), "prop": "pageprops",
                        "ppprop": "wikibase_item", "redirects": "1"})
        q = d.get("query", {})
        back = {}
        for r in q.get("normalized", []) + q.get("redirects", []):
            back.setdefault(r["to"], []).append(r["from"])
        for p in q.get("pages", []):
            w = (p.get("pageprops") or {}).get("wikibase_item")
            if w:
                for n in [p["title"]] + back.get(p["title"], []) + [f for b in back.get(p["title"], []) for f in back.get(b, [])]:
                    qid[n] = w
    ids = sorted(set(qid.values()))
    human, en = set(), {}
    for i in range(0, len(ids), 50):
        d = get_json("https://www.wikidata.org/w/api.php", {"action": "wbgetentities", "ids": "|".join(ids[i:i + 50]),
                                                            "props": "labels|claims", "languages": "en", "format": "json"})
        for q, e in d.get("entities", {}).items():
            p31 = {(s.get("mainsnak", {}).get("datavalue", {}).get("value") or {}).get("id")
                   for s in e.get("claims", {}).get("P31", [])}
            if "Q5" in p31:
                human.add(q)
                en[q] = e.get("labels", {}).get("en", {}).get("value")
    out = Counter()
    for t, n in c.items():
        q = qid.get(t)
        if q in human and en.get(q):
            out[en[q]] += n
    return out.most_common()
