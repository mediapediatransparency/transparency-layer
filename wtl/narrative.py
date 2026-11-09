"""How an article uses its cited authors, by fixed rules (pilot; not yet on the site).

From the analysed revision's wikitext, each citation is placed after the sentence it follows
(the same placement as the footnote bundles in wtl/metrics/stability.py), and its authors are
read as in wtl/sources.py (a short footnote counts for the authors of the work it points to).
For each cited author:
- weight: the sentences resting on at least one of their works, and how many of those are in
  the opening section;
- sole support: sentences whose footnotes cite no other author;
- voice: of those sentences, how many name the author in the sentence itself (by surname; for
  example "According to Morris ..." or "Morris argues ...", called "attributed"), and how many
  state the content without naming them (called "in Wikipedia's voice");
- contested: sentences taken out and put back at least once, or tagged as disputed, that rest on
  the author.
Nothing here says whether a use is right or wrong. Counts only.
"""

import re
from collections import Counter, defaultdict

from . import sources as src
from .fetch import mediawiki as mw
from .metrics import stability as stab
from .text import sentences, wikitext

DISPUTE = {"Disputed inline", "Dubious", "Disputed", "POV statement", "Failed verification",
           "Better source needed", "Neutrality disputed", "Contradictory inline"}


def _surname(name: str) -> str:
    parts = re.sub(r"\(.*?\)", "", name).replace(",", " ").split()
    return parts[-1] if parts else name


def sentence_authors(rec: dict) -> tuple[list, dict[str, list[str]]]:
    """(sentence list as split from the wikitext, {sentence id: [author name, ...]})."""
    text = mw.get_revision(rec["revision"])["content"]
    lay = wikitext.layout(text)
    sents = sentences.split(text, lay)
    sent_of = [-1] * len(text)
    for i, s in enumerate(sents):
        for o in s.offsets:
            sent_of[o] = i
    names, _ = src.load_names()
    from . import books
    cites = src.find(text, names, books.load()[0])
    skip = stab._skip_spans(text)
    # a citation's footnote starts at the <ref> tag holding it; place it like the bundles do
    ref_at = [(m.start(), m.end()) for m in stab.REF_TAG.finditer(text)]
    out: dict[str, list[str]] = defaultdict(list)
    for c in cites:
        pos = next((a for a, b in ref_at if a <= c["start"] < b), c["start"])
        i = stab._sentence_before(text, sent_of, pos, skip)
        if i < 0:
            continue
        for name, link in dict.fromkeys(c.get("authors") or []):
            out[sents[i].id].append(link or name)
    return sents, out


def usage(rec: dict, top: int = 30) -> dict:
    sents, by_sent = sentence_authors(rec)
    info = {s["id"]: s for s in rec["sentences"]}
    text_of = {s.id: s.text for s in sents}
    au_rows = {}
    totals = Counter()
    for sid, names in by_sent.items():
        uniq = list(dict.fromkeys(names))
        s = info.get(sid) or {}
        h = s.get("history") or {}
        contested = bool(h.get("removed")) or any(t.get("template") in DISPUTE for t in s.get("tags") or [])
        t = text_of.get(sid, "")
        totals["sentences"] += 1
        totals["lead"] += sid.startswith("lead")
        totals["contested"] += contested
        for n in uniq:
            r = au_rows.setdefault(n, Counter())
            r["sentences"] += 1
            r["lead"] += sid.startswith("lead")
            r["sole"] += len(uniq) == 1
            r["contested"] += contested
            named = re.search(r"\b" + re.escape(_surname(n)) + r"\b", t) is not None
            r["attributed"] += named
            r["unattributed"] += not named
    rows = [{"author": n, **dict(c)} for n, c in au_rows.items()]
    rows.sort(key=lambda r: (-r["sentences"], r["author"]))
    sole = Counter()
    for sid, names in by_sent.items():
        u = set(names)
        if len(u) == 1:
            sole[next(iter(u))] += 1
    return {"sentences_with_an_author": totals["sentences"], "lead_sentences_with_an_author": totals["lead"],
            "contested_sentences_with_an_author": totals["contested"],
            "authors": rows[:top],
            "sentences_resting_on_one_author": sum(sole.values()),
            "top5_share_of_author_sentences": round(sum(r["sentences"] for r in rows[:5]) /
                                                    max(1, sum(r["sentences"] for r in rows)), 3)}


def authors_over_time(rec: dict, top: int = 30) -> dict:
    """Citations naming each author in the article on 1 January 2015, 2019 and 2023 and in the
    analysed version (versions read as for the then-and-now section; cached, no network)."""
    from . import books
    from . import then_now as tn
    names, _ = src.load_names()
    bk = books.load()[0]
    pageid = mw.get_revision(rec["revision"])["pageid"]
    texts = []
    for d in tn.DATES:
        if d >= rec["revision_timestamp"][:10]:
            continue
        v = tn.version_at(pageid, d)
        if v:
            texts.append((d, v["content"]))
    texts.append((rec["revision_timestamp"][:10], mw.get_revision(rec["revision"])["content"]))
    per = {}
    for d, t in texts:
        c = Counter()
        for x in src.find(t, names, bk):
            for name, link in dict.fromkeys(x.get("authors") or []):
                c[link or name] += 1
        per[d] = c
    last = per[texts[-1][0]]
    keys = [k for k, _ in last.most_common(top)]
    gone = Counter()
    for d, c in per.items():
        for k, n in c.items():
            if k not in last:
                gone[k] = max(gone[k], n)
    return {"dates": [d for d, _ in texts],
            "citations_naming_an_author": {d: sum(c.values()) for d, c in per.items()},
            "authors": {k: {d: per[d].get(k, 0) for d, _ in texts} for k in keys},
            "dropped_since": {k: {d: per[d].get(k, 0) for d, _ in texts} for k, _ in gone.most_common(15)}}


VIEW_HEAD = re.compile(r"\b(views?|politic\w*|positions?|opinions?|reception|criticism|critiques?|"
                       r"controvers\w*|debates?|ideolog\w*|stance)\b", re.I)


def author_sections(title: str) -> list[dict]:
    """Sections of the author's own Wikipedia article whose headings name views, reception or
    criticism (and the sections inside them), as links. Headings only: nothing is summarised."""
    from html import unescape
    d = mw.api({"action": "parse", "page": title, "prop": "sections|revid", "redirects": "1"})
    p = d.get("parse", {})
    out, inside = [], None
    for s in p.get("sections", []):
        lvl, head = int(s["level"]), unescape(re.sub(r"<[^>]+>", "", s["line"]))
        if inside is not None and lvl <= inside:
            inside = None
        if VIEW_HEAD.search(head) and inside is None:
            inside = lvl
            out.append({"heading": head, "anchor": s["anchor"], "level": lvl, "under": None})
        elif inside is not None:
            out.append({"heading": head, "anchor": s["anchor"], "level": lvl, "under": out[-1]["heading"] if out else None})
    return [{**x, "revision": p.get("revid")} for x in out]


TITLE_P = re.compile(r"\|\s*(?:title|chapter)\s*=\s*([^|}]+)", re.I)
YEAR_P = re.compile(r"\|\s*(?:year|date|orig-date|orig-year)\s*=\s*[^|}]*?(\d{4})", re.I)


def _title_year(text: str, start: int) -> tuple[str | None, int | None]:
    body = text[start:start + 1500]
    end = body.find("}}")
    body = body[:end] if end > 0 else body[:600]
    t, y = TITLE_P.search(body), YEAR_P.search(body)
    title = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", t.group(1)).strip(" '\"") if t else None
    return title, (int(y.group(1)) if y else None)


def sentence_works(rec: dict, text: str | None = None) -> tuple[list, dict[str, list[dict]]]:
    """(sentences, {sentence id: [{source, flags, authors, title, year}]}) for the analysed
    revision, or for any other wikitext of the article when given. A short footnote takes the
    authors, title and year of the bibliography entry it points to."""
    from . import books
    text = text or mw.get_revision(rec["revision"])["content"]
    lay = wikitext.layout(text)
    sents = sentences.split(text, lay)
    sent_of = [-1] * len(text)
    for i, s in enumerate(sents):
        for o in s.offsets:
            sent_of[o] = i
    names, _ = src.load_names()
    cites = src.find(text, names, books.load()[0])
    skip = stab._skip_spans(text)
    ref_at = [(m.start(), m.end()) for m in stab.REF_TAG.finditer(text)]
    out: dict[str, list[dict]] = defaultdict(list)
    for c in cites:
        pos = next((a for a, b in ref_at if a <= c["start"] < b), c["start"])
        i = stab._sentence_before(text, sent_of, pos, skip)
        if i < 0:
            continue
        title, year = _title_year(text, c.get("bib_start", c["start"]))
        w = {"source": c.get("source"), "flags": sorted(src.flags_of(text, c)),
             "authors": list(dict.fromkeys(link or name for name, link in c.get("authors") or [])),
             "title": title, "year": year}
        if w not in out[sents[i].id]:
            out[sents[i].id].append(w)
    return sents, out

OPENING_DATES = ["2015-01-01", "2019-01-01", "2023-01-01", "2023-07-01", "2024-01-01", "2024-07-01",
                 "2024-10-01", "2025-01-01", "2025-07-01", "2026-01-01", "2026-07-01"]


def _work_key(w: dict) -> tuple:
    from .field import main_title
    from .field import name_key
    au = tuple(sorted(name_key(a).split(" ")[0] for a in w.get("authors") or []))   # surnames
    t = main_title(w.get("title") or "")
    return ("t", t, au) if t else ("s", w.get("source"), au)


def removed_from_opening(rec: dict, now_works: dict, dates=OPENING_DATES) -> list[dict]:
    """Works cited in the opening section on any of these dates (the version in force at the start
    of the day) and not cited there in the analysed version: the last date each was seen, the
    sentence it followed then, and whether today's article still cites it elsewhere."""
    from . import then_now as tn
    pageid = mw.get_revision(rec["revision"])["pageid"]
    today = {_work_key(w) for sid, ws in now_works.items() if sid.startswith("lead") for w in ws}
    anywhere = {_work_key(w) for ws in now_works.values() for w in ws}
    seen = {}
    for d in dates:
        if d >= rec["revision_timestamp"][:10]:
            continue
        v = tn.version_at(pageid, d)
        if not v:
            continue
        ss, ws = sentence_works(rec, v["content"])
        text_of = {x.id: x.text for x in ss}
        for sid, lst in ws.items():
            if not sid.startswith("lead"):
                continue
            for w in lst:
                k = _work_key(w)
                if k in today:
                    continue
                e = seen.setdefault(k, {**w, "first_seen": d, "revision_then": v["revision"]})
                e.update({"last_seen": d, "sentence_then": text_of.get(sid, ""), "revision_then": v["revision"],
                          "still_cited_elsewhere": k in anywhere})
    return sorted(seen.values(), key=lambda e: (e["last_seen"], e.get("title") or ""), reverse=True)
