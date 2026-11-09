"""Recorded political affiliation of a cited source (rule of 2026-11-06).

What Wikidata and English Wikipedia already record about the outlet or publisher itself:
- Wikidata: political alignment (P1387) and political ideology (P1142);
- Wikipedia: categories on the source's own article that name it as a political outlet or
  publisher ("Left-wing book publishing companies", "Conservative media in Israel",
  "Liberal mass media in the United Kingdom", "Right-wing think tanks"), or as state media.
  Topic categories ("Liberalism in Israel", "Anarchism in Illinois") are not used: they say the
  article is about a subject, not that the source belongs to a side.

Labels are kept as recorded; only the word form is unified (conservatism -> conservative).
"liberal" is never merged into "left" or anything else, because the words mean different things
in different countries. A source with no label has "none recorded"; one with neither a Wikidata
item nor a Wikipedia article has "no entry". Nothing here is this project's own judgement.
"""
from __future__ import annotations

import re
import time

from .fetch import cache

LABEL_WORDS = [
    "far-left", "far-right", "centre-left", "center-left", "centre-right", "center-right",
    "left-wing", "right-wing", "neoconservative", "conservative", "liberal", "progressive",
    "social democratic", "socialist", "communist", "marxist", "anarchist", "libertarian",
    "nationalist", "islamist", "zionist", "anti-zionist", "fascist", "alt-right", "populist",
]
TYPE_WORDS = (r"(?:book )?publishing (?:companies|houses)|publishers|(?:mass )?media|newspapers|"
              r"magazines|periodicals|publications|journals|television(?: channels| networks| stations)?|"
              r"radio(?: stations| networks)?|(?:news )?websites|blogs|podcasts|news agencies|"
              r"think tanks|organi[sz]ations|broadcasters")
# an optional nationality or place word first ("American conservative websites")
CAT_RX = re.compile(r"^(?:[A-Z][a-z]+ )?(?:modern )?(" + "|".join(re.escape(w) for w in LABEL_WORDS) + r")(?: mass)? ("
                    + TYPE_WORDS + r")\b", re.I)
STATE_RX = re.compile(r"^(?:[A-Z][a-z]+ )?(?i:state media|state-owned media|state-run media|"
                      r"state broadcasters)$")
PROP_RX = re.compile(r"^(?:[A-Z][a-z]+ )?(?:[A-Z][a-z]+ )?(?:government )?propaganda organi[sz]ations$")

# word forms of Wikidata labels -> the adjective used in category names
FORMS = {
    "conservatism": "conservative", "liberalism": "liberal", "progressivism": "progressive",
    "socialism": "socialist", "communism": "communist", "marxism": "marxist",
    "anarchism": "anarchist", "libertarianism": "libertarian", "nationalism": "nationalist",
    "islamism": "islamist", "zionism": "zionist", "anti-zionism": "anti-zionist",
    "fascism": "fascist", "populism": "populist", "neoconservatism": "neoconservative",
    "social democracy": "social democratic", "centrism": "centrist",
    "left-wing politics": "left-wing", "right-wing politics": "right-wing",
    "far-left politics": "far-left", "far-right politics": "far-right",
    "centre-left politics": "centre-left", "centre-right politics": "centre-right",
    "center-left politics": "centre-left", "center-right politics": "centre-right",
    "center-left": "centre-left", "center-right": "centre-right",
}
NONE = "none recorded"
NO_ENTRY = "no entry"


def norm_label(s: str) -> str:
    s = s.strip().lower()
    return FORMS.get(s, s)


# Display spelling of the stored (lower-case) labels. Stored labels stay lower case so the same
# word from Wikidata and from a category matches; pages show proper names with their capitals.
# Category words that are proper adjectives, used when Wikidata gives no spelling.
PROPER = {"zionist": "Zionist", "anti-zionist": "anti-Zionist", "marxist": "Marxist",
          "islamist": "Islamist"}
_DISPLAY: dict[str, str] = {}


def load_display(outlets: dict) -> None:
    """Learn display spellings from the Wikidata labels as entered: for each stored label, the
    most common spelling with capitals ("Frankfurt School"); a converted word form keeps the
    capital of its source ("Marxism" -> "Marxist"). Ordinary words stay as Wikidata writes them
    (lower case). Ties go to the alphabetically first spelling, so builds are reproducible."""
    from collections import Counter
    seen: dict[str, Counter] = {}
    for o in (outlets or {}).values():
        for raw in (o.get("political_alignment") or []) + (o.get("political_ideology") or []):
            raw = raw.strip()
            key = norm_label(raw)
            spell = raw if key == raw.lower() else (key[:1].upper() + key[1:] if raw[:1].isupper() else key)
            seen.setdefault(key, Counter())[spell] += 1
    _DISPLAY.clear()
    for key, c in seen.items():
        caps = sorted(((-n, s) for s, n in c.items() if s != key))
        if caps and sum(n for s, n in c.items() if s != key) >= c.get(key, 0):
            _DISPLAY[key] = caps[0][1]


def show(label: str) -> str:
    """The display spelling of a stored label."""
    return _DISPLAY.get(label) or PROPER.get(label) or label


# Labels that are themselves positions on the left-right line (Wikidata's "political alignment"
# values and the matching category words).
POSITIONS = {"far-left": -3, "left-wing": -2, "centre-left": -1, "centrist": 0,
             "centre-right": 1, "right-wing": 2, "far-right": 3}
BINS = {-3: "far left", -2: "left", -1: "left", 0: "centre", 1: "right", 2: "right", 3: "far right"}
_RULES: dict = {}


def position_rules() -> dict:
    """data/position_rules.json: other labels placed by what English Wikipedia's article on the
    ideology says (with the quote and the article version), and those left unplaced, with why.
    Returns {"ideology": {label: [positions]}, "by_country": {label: {country: [positions]}}}."""
    if not _RULES:
        import json
        from .config import ROOT
        p = ROOT / "data" / "position_rules.json"
        d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"placed": []}
        ide, byc = {}, {}
        for r in d.get("placed", []):
            if r.get("country"):
                byc.setdefault(r["label"], {})[r["country"]] = r["positions"]
            else:
                ide[r["label"]] = r["positions"]
        _RULES.update({"ideology": ide, "by_country": byc, "file": d})
    return _RULES


# Recorded stances counted on their own, not placed on the left-right line (owner, 2026-11-08):
# (name shown, labels counted, opposing labels counted alongside). Shown wherever a cited source
# carries one of the labels.
STANCES = [("Zionist / anti-Zionist", ["zionist"], ["anti-zionist"]),
           ("Islamist", ["islamist"], []),
           ("Nationalist", ["nationalist"], [])]


def position_split(labels, countries=None) -> dict[str, float]:
    """{"far left", "left", "centre", "right", "far right": share} for one source. Position labels
    are used when the source has any; otherwise labels placed by data/position_rules.json, each
    label counting equally (and a label with two positions half for each). Empty when nothing
    places the source."""
    labels = list(labels or [])
    direct = [[l] for l in labels if l in POSITIONS]
    if not direct:
        rules, cs = position_rules(), set(countries or [])
        for l in labels:
            if l in rules["ideology"]:
                direct.append(rules["ideology"][l])
            elif l in rules["by_country"] and len(cs) == 1 and next(iter(cs)) in rules["by_country"][l]:
                direct.append(rules["by_country"][l][next(iter(cs))])
    out = {}
    for ps in direct:
        for pname in ps:
            k = BINS[POSITIONS[pname]]
            out[k] = out.get(k, 0) + 1 / len(direct) / len(ps)
    return out


def category_labels(cats: list[str]) -> list[str]:
    out = set()
    for c in cats:
        m = CAT_RX.match(c)
        if m:
            out.add(norm_label(m.group(1)))
        elif STATE_RX.search(c):
            out.add("state media")
        elif PROP_RX.search(c):
            out.add("propaganda organisation")
    return sorted(out)


def labels_for(e: dict, cats: list[str] | None) -> dict:
    """{"labels": [...], "wikidata": [...], "wikipedia_categories": [...]} for one source."""
    wd = sorted({norm_label(x) for x in (e.get("political_alignment") or [])
                 + (e.get("political_ideology") or [])})
    cl = category_labels(cats or [])
    used = [c for c in (cats or []) if CAT_RX.match(c) or STATE_RX.search(c) or PROP_RX.search(c)]
    labels = sorted(set(wd) | set(cl))
    if not labels:
        labels = [NONE] if (e.get("wikidata") or e.get("enwiki")) else [NO_ENTRY]
    return {"labels": labels, "wikidata": wd, "wikipedia_categories": sorted(used)}


def fetch_categories(titles: list[str], log=print) -> dict:
    """{title: [category names]} for English Wikipedia articles (visible categories only),
    following redirects. Cached per title for 30 days' worth of runs (monthly key)."""
    import datetime as dt
    from .fetch.mediawiki import api
    month = dt.date.today().strftime("%Y-%m")
    p = cache.path("outlets", f"enwiki_categories_{month}")
    have = cache.load(p) or {}
    todo = sorted({t for t in titles if t and t not in have})
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        got, cont = {t: [] for t in batch}, {}
        back = {}
        for attempt in range(6):
            try:
                while True:
                    d = api({"action": "query", "prop": "categories", "cllimit": "max",
                             "clshow": "!hidden", "redirects": "1", "titles": "|".join(batch), **cont})
                    q = d.get("query", {})
                    for r in q.get("redirects", []) + q.get("normalized", []):
                        back.setdefault(r["to"], []).append(r["from"])
                    for pg in q.get("pages", []):
                        names = [c["title"].split(":", 1)[1] for c in pg.get("categories", [])]
                        for t in [pg["title"]] + back.get(pg["title"], []):
                            if t in got:
                                got[t] += names
                    if "continue" not in d:
                        break
                    cont = d["continue"]
                break
            except Exception as ex:   # rate limits and blips: wait longer each time
                log(f"  categories: retry {attempt + 1} after {str(ex)[:80]}")
                time.sleep(10 * (attempt + 1))
                cont = {}
        else:
            log("  categories: giving up on a batch; its sources get no category labels this run")
            continue
        for t, names in got.items():
            have[t] = sorted(set(names))
        if (i // 50) % 10 == 0:
            log(f"  categories: {min(i + 50, len(todo)):,} of {len(todo):,}")
            cache.save(p, have)
        time.sleep(1)
    cache.save(p, have)
    return have
