"""Word lists for tracking wording changes, and matching them in WikiWho token streams.

Two lists, both published with the site and fingerprinted in every record:

- data/words_to_watch.json: Wikipedia's own guideline "Manual of Style/Words to watch", read
  mechanically from one pinned revision (`wtl words-to-watch`). Only the sections on words that
  may introduce bias are used (puffery, contentious labels, unsupported attributions,
  expressions of doubt, editorializing, synonyms for "said") plus euphemisms. The guideline's
  second editorializing box (but, despite, however, though, although, furthermore, while) is
  left out: those words are in almost every sentence.
- data/contested_terms.json: groups of alternative terms for the same thing on contested
  subjects, chosen by this project and published so anyone can check or propose changes. Every
  member of a group is counted the same way, so a change in either direction shows.

Matching is on lower-cased word tokens (punctuation ignored), so "so-called" matches
so + called. Single words also match simple inflections (s, es, ed, d, ly, ing; y to ies,
ied, ily). The words are counted; what a word means in context is not judged.
"""

import hashlib
import json
import re

from .config import ROOT

WTW_JSON = ROOT / "data" / "words_to_watch.json"
CONTESTED_JSON = ROOT / "data" / "contested_terms.json"
WTW_PAGE = "Wikipedia:Manual of Style/Words to watch"
WTW_SECTIONS = {"Puffery": "puffery", "Contentious labels": "contentious labels",
                "Unsupported attributions": "unsupported attributions",
                "Expressions of doubt": "expressions of doubt", "Editorializing": "editorializing",
                "Synonyms for said": "synonyms for said", "Euphemisms": "euphemisms"}
SKIP_BOX = re.compile(r"^\s*but, despite, however")
WORD = re.compile(r"\w", re.UNICODE)


def build_wtw() -> dict:
    """Read the guideline at its current revision and write data/words_to_watch.json."""
    from .fetch.mediawiki import api
    d = api({"action": "query", "prop": "revisions", "titles": WTW_PAGE,
             "rvprop": "ids|content", "rvslots": "main"})
    r = d["query"]["pages"][0]["revisions"][0]
    text = r["slots"]["main"]["content"]
    heads = [(m.start(), re.sub(r"<[^>]+>|''", "", m.group(1)).strip())
             for m in re.finditer(r"^=+\s*(.+?)\s*=+\s*$", text, re.M)]
    cats = {}
    for m in re.finditer(r"Words to watch:?\s*\{\{strong\|(.+?)&nbsp;", text):
        sec = next((h for pos, h in reversed(heads) if pos < m.start()), "")
        sec = re.sub(r"\s+", " ", sec).replace("Synonyms for said", "Synonyms for said")
        key = next((v for k, v in WTW_SECTIONS.items() if k.lower() in sec.lower()), None)
        if not key or SKIP_BOX.match(m.group(1).replace("''", "")):
            continue
        body = re.sub(r"\{\{var\|[^}]*\}\}", " ", m.group(1))
        body = re.sub(r"\{\{nobreak\|([^}]*)\}\}", r"\1", body)
        body = body.replace("''", "")
        terms = []
        for t in body.split(","):
            t = t.strip().strip(".").strip()
            if not t or t.startswith("-"):
                continue   # suffixes such as "-gate" match too many ordinary words
            if "/" in t:   # "it is believed/regarded/considered"
                head, _, alts = t.rpartition(" ")
                for a in alts.split("/"):
                    terms.append(f"{head} {a}".strip())
            else:
                terms.append(t)
        cats.setdefault(key, [])
        cats[key] += [x for x in terms if x not in cats[key]]
    out = {"source": WTW_PAGE, "revision": r["revid"],
           "url": f"https://en.wikipedia.org/w/index.php?oldid={r['revid']}",
           "note": "Sections on words that may introduce bias, plus euphemisms; the box of "
                   "conjunctions (but, despite, however, though, although, furthermore, while) "
                   "is left out.",
           "categories": cats}
    WTW_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


def _variants(w: str) -> set[str]:
    v = {w, w + "s", w + "es", w + "d", w + "ed", w + "ly", w + "ing"}
    if w.endswith("y"):
        v |= {w[:-1] + "ies", w[:-1] + "ied", w[:-1] + "ily"}
    if w.endswith("e"):
        v |= {w[:-1] + "ing", w + "ly"}
    return v


def words_of(phrase: str) -> list[str]:
    return [t for t in re.split(r"[^\w]+", phrase.lower()) if t]


class Matcher:
    """Finds listed terms in a sequence of word tokens. Each match: (start, length, group, term)."""

    def __init__(self, groups: dict[str, list[str]]):
        self.first = {}
        for g, terms in groups.items():
            for term in terms:
                ws = words_of(term)
                if not ws:
                    continue
                if term.endswith("-"):           # prefix such as "pseudo-"
                    self.first.setdefault(("prefix", ws[0]), []).append(((), g, term))
                    continue
                forms = _variants(ws[0]) if len(ws) == 1 else {ws[0]}
                for f in forms:
                    self.first.setdefault(f, []).append((tuple(ws[1:]), g, term))
        self.prefixes = [k[1] for k in self.first if isinstance(k, tuple)]

    def find(self, toks: list[str]):
        out, i, n = [], 0, len(toks)
        while i < n:
            t = toks[i]
            best = None
            for rest, g, term in self.first.get(t, ()):
                L = len(rest)
                if tuple(toks[i + 1:i + 1 + L]) == rest and (best is None or L + 1 > best[1]):
                    best = (i, L + 1, g, term)
            if best is None:
                for p in self.prefixes:
                    if t.startswith(p) and len(t) > len(p):
                        for _, g, term in self.first[("prefix", p)]:
                            best = (i, 1, g, term)
                        break
            if best:
                out.append(best)
                i += best[1]
            else:
                i += 1
        return out


def load():
    """(Matcher, {"words_to_watch": {...}, "contested_terms": {...}}) or (None, None) if the
    lists have not been built. Group names: "WTW: <category>" and "contested: <group>"."""
    if not WTW_JSON.exists():
        return None, None
    wtw_raw = WTW_JSON.read_bytes()
    wtw = json.loads(wtw_raw)
    lists = [Matcher({f"WTW: {k}": v for k, v in wtw["categories"].items()})]
    info = {"words_to_watch": {"revision": wtw["revision"], "url": wtw["url"],
                               "sha256": hashlib.sha256(wtw_raw).hexdigest()}}
    if CONTESTED_JSON.exists():
        c_raw = CONTESTED_JSON.read_bytes()
        c = json.loads(c_raw)
        lists.append(Matcher({f"contested: {g['name']}": g["terms"] for g in c["groups"]}))
        info["contested_terms"] = {"sha256": hashlib.sha256(c_raw).hexdigest()}
    return Lists(lists), info


class Lists:
    """Several lists matched independently, so a term on two lists counts on each."""

    def __init__(self, matchers):
        self.matchers = matchers

    def find(self, toks):
        return [m for x in self.matchers for m in x.find(toks)]


def is_word(s: str) -> bool:
    return bool(WORD.search(s))
