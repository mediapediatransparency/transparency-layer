"""The opening section then and now, by fixed rules.

For every analysed article, the version in force on 1 January 2015, 1 January 2019 and
1 January 2023 (the last revision saved before midnight UTC that day) is read, and its opening
section is split into sentences with the same code as the analysed version. The same dates are
used for every article; a date before the article existed is left out.

- First paragraph: the opening section's sentences up to the first paragraph break, at each date
  and in the analysed version.
- Most-changed sentences: each sentence of today's opening section is paired with the sentence
  of the earliest of those versions (the baseline) with which it shares most content words
  (Dice similarity, 0 to 1: twice the shared words over the words in both; common words such as
  "the" and "of" left out). Pairs with similarity from 0.3 up to 0.9 (the same sentence,
  rewritten) are kept; below 0.3 the sentence counts as new, from 0.9 as nearly unchanged. The three pairs with the lowest similarity are shown, each old sentence
  used once. Both sentences need at least six words. Each pair is also traced through the
  other dates: at each, the opening sentence most similar to today's or to the one found at the
  date before (similarity at least 0.3).

- First paragraph then and now: the first paragraph of the baseline and of the analysed
  version, compared word by word (Python's difflib): words still there in the same order,
  taken out and added. Also, at each date, the page's short description (the line Wikipedia
  shows under the title in its search box and apps), the first sentence (joined to the next one
  when shorter than six words), and the sources
  cited in footnotes inside the first paragraph.
- Sources: the footnotes of each version are read with the same code as the analysed version
  (wtl/sources.py), giving the number of citations of each source at each date. The ratings
  joined to them on the site are today's (data/outlets.json): what raters say of a source now,
  not what they said at the time.

Nothing here says whether a change made the article better or worse.
`wtl then-now` writes data/then_now.json.
"""

import datetime as dt
import difflib
import json
import re

from .config import ROOT
from .fetch import cache
from .fetch.mediawiki import api
from .text import sentences, wikitext

THEN_NOW_JSON = ROOT / "data" / "then_now.json"
DATES = ["2015-01-01", "2019-01-01", "2023-01-01"]
LOW, HIGH, MIN_WORDS, SHOWN = 0.3, 0.9, 6, 3
TOKEN = re.compile(r"\S+")


def version_at(pageid: int, date: str) -> dict | None:
    p = cache.path("then_now", f"{pageid}_{date}")
    hit = cache.load(p)
    if hit is not None:
        return hit or None
    d = api({"action": "query", "prop": "revisions", "pageids": str(pageid), "rvlimit": "1",
             "rvstart": f"{date}T00:00:00Z", "rvdir": "older", "rvprop": "ids|timestamp|content",
             "rvslots": "main"})
    pg = (d.get("query", {}).get("pages") or [{}])[0]
    revs = pg.get("revisions")
    out = ({"revision": revs[0]["revid"], "timestamp": revs[0]["timestamp"],
            "content": revs[0]["slots"]["main"].get("content", "")} if revs else {})
    cache.save(p, out)
    return out or None


def lead_of(text: str, span: bool = False):
    """(opening-section sentences, first-paragraph sentences) of a wikitext; with span=True also
    (start, end) of the first paragraph in the wikitext."""
    lay = wikitext.layout(text)
    lead = [s for s in sentences.split(text, lay) if s.id.startswith("lead")]
    if not lead:
        return ([], [], (0, 0)) if span else ([], [])
    first = min(lead[0].offsets) if lead[0].offsets else 0
    m = re.compile(r"\n[ \t]*\n").search(text, first)
    cut = m.start() if m else len(text)
    para = [s.text for s in lead if s.offsets and min(s.offsets) < cut]
    out = ([s.text for s in lead], para)
    return (*out, (first, cut)) if span else out


SHORT_DESC = re.compile(r"\{\{\s*short[ _]description\s*\|\s*(?:1\s*=\s*)?([^|}]*)", re.I)


def short_description(text: str) -> str | None:
    """The page's short description ({{Short description|...}}): the line Wikipedia shows under
    the title in its search box and apps. None when absent or set to "none"."""
    m = SHORT_DESC.search(text)
    v = m.group(1).strip() if m else ""
    return None if not v or v.lower() == "none" else v


def _words(s: str) -> list[str]:
    return TOKEN.findall(s)


STOP = set("""a an the and or but of in on at to for from by with as is are was were be been being it its
this that these those which who whom whose what when where while than then there their they them
he she his her we our you your i not no nor so such also into onto over under about after before
between during within without against among through since until upon has have had do does did can
could may might must shall should will would one two more most other some any all each both
""".split())
WORDY = re.compile(r"[a-z0-9]+")


def content_words(s: str) -> set[str]:
    return {w for w in WORDY.findall(s.lower()) if w not in STOP and len(w) > 1}


def similarity(a: str, b: str) -> float:
    """Share of content words in common (Dice: 2 × shared ÷ (words in a + words in b)); common
    words such as "the" and "of" are left out."""
    x, y = content_words(a), content_words(b)
    return 2 * len(x & y) / (len(x) + len(y)) if x or y else 0.0


def diff_ops(old: str, new: str) -> list[list]:
    """Word-level diff: [["=", text] | ["-", text] | ["+", text], ...] in reading order."""
    a, b = _words(old), _words(new)
    sm = difflib.SequenceMatcher(None, [w.lower() for w in a], [w.lower() for w in b], autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.append(["=", " ".join(b[j1:j2])])
        else:
            if i2 > i1:
                out.append(["-", " ".join(a[i1:i2])])
            if j2 > j1:
                out.append(["+", " ".join(b[j1:j2])])
    return out


def most_changed(then: list[str], now: list[tuple[str, str]]) -> dict:
    """now: [(sentence id, text)]."""
    pairs = []
    for sid, t in now:
        if len(_words(t)) < MIN_WORDS:
            continue
        best = max(((similarity(o, t), o) for o in then if len(_words(o)) >= MIN_WORDS),
                   default=(0.0, None))
        pairs.append((best[0], sid, t, best[1]))
    kept, used = [], set()
    for sim, sid, t, o in sorted(pairs, key=lambda x: (x[0], x[1])):
        if o is None or not (LOW <= sim < HIGH) or o in used:
            continue
        used.add(o)
        kept.append({"new_id": sid, "old": o, "new": t, "similarity": round(sim, 3),
                     "diff": diff_ops(o, t)})
        if len(kept) == SHOWN:
            break
    return {"pairs": kept,
            "new_sentences": sum(1 for p in pairs if p[0] < LOW),
            "nearly_unchanged": sum(1 for p in pairs if p[0] >= HIGH),
            "rewritten": sum(1 for p in pairs if LOW <= p[0] < HIGH)}


def add_paths(mc: dict, leads: list[list[str]], dates: list[str]) -> dict:
    """Each most-changed pair traced through every earlier date: at each date, the opening
    sentence most similar to today's or to the one found at the date before (similarity at least
    0.3; the baseline's is the pair's own old sentence), then today's; with the word diff from the
    previous date that has one."""
    for p in mc.get("pairs", []):
        path, prev = [], None
        for i, (d, lead) in enumerate(zip(dates, leads)):
            if i == 0:
                text = p["old"]
            else:
                sim, text = max(((max(similarity(o, p["new"]), similarity(o, prev) if prev else 0.0), o)
                                 for o in lead if len(_words(o)) >= MIN_WORDS), default=(0.0, None))
                text = text if sim >= LOW else None
            path.append({"date": d, "text": text,
                         "diff_from_previous": diff_ops(prev, text) if prev and text and prev != text else None})
            prev = text or prev
        path.append({"date": "analysed", "text": p["new"],
                     "diff_from_previous": diff_ops(prev, p["new"]) if prev and prev != p["new"] else None})
        p["path"] = path
    return mc


def paths_for(rec: dict, t: dict) -> dict:
    """add_paths for an existing then-and-now entry, from cached versions (no new fetches for
    articles already built)."""
    from .fetch import mediawiki as mw
    pageid = mw.get_revision(rec["revision"])["pageid"]
    dates = [v["date"] for v in t["versions"][:-1]]
    leads = [_version(version_at(pageid, d)["content"])[1] for d in dates]
    return add_paths(t["most_changed"], leads, dates)


_REF = {}


def _sources_of(text: str, span: tuple[int, int] | None = None) -> list[list]:
    """[[source key, citations], ...] of a wikitext, most cited first. With span, only the
    footnotes placed inside that stretch of text (a re-used named footnote counts there too)."""
    from collections import Counter
    from . import books, sources
    from .metrics.stability import NAME_ATTR, REF_TAG
    if not _REF:
        _REF["names"] = sources.load_names()[0]
        _REF["books"] = books.load()[0]
    found = sources.find(text, _REF["names"], _REF["books"])
    if span is None:
        c = Counter(x["source"] for x in found)
    else:
        a, b = span
        c, by_name = Counter(), {}
        for m in REF_TAG.finditer(text):
            nm = NAME_ATTR.search(m.group(1) or "")
            name = next((g for g in nm.groups() if g is not None), "").strip() if nm else ""
            if m.group(3) is not None:
                inside = [x["source"] for x in found if m.start() <= x["start"] < m.end()]
                if name:
                    by_name.setdefault(name, inside)
                if a <= m.start() < b:
                    c.update(inside)
            elif name and a <= m.start() < b:
                c.update(("@" + name,))
        for k in [k for k in c if k.startswith("@")]:
            n = c.pop(k)
            for src in by_name.get(k[1:], []):
                c[src] += n
        c.update(x["source"] for x in found if a <= x["start"] < b and x.get("short")
                 and not any(m.start() <= x["start"] < m.end() for m in REF_TAG.finditer(text, a, b)))
    return [[k, n] for k, n in sorted(c.items(), key=lambda x: (-x[1], x[0]))]


def _version(text: str) -> tuple[dict, list[str]]:
    """Fields read from one version's wikitext, and its opening-section sentences."""
    lead, para, span = lead_of(text, span=True)
    first = []
    for x in para:   # a fragment cut at an abbreviation ("translit.") joins the next sentence
        first.append(x)
        if sum(len(_words(y)) for y in first) >= MIN_WORDS:
            break
    return {"short_description": short_description(text),
            "first_sentence": " ".join(first),
            "first_paragraph": " ".join(para),
            "first_paragraph_sentences": len(para),
            "first_paragraph_words": sum(len(_words(s)) for s in para),
            "first_paragraph_sources": _sources_of(text, span) if para else [],
            "lead_sentences": len(lead), "lead_words": sum(len(_words(s)) for s in lead)}, lead


def paragraph_change(old: str, new: str) -> dict:
    """Word counts of the first paragraph then and now: words of the old one still there (in
    the same order, as the word diff finds them), taken out and added."""
    ops = diff_ops(old, new)
    n = lambda op: sum(len(_words(t)) for o, t in ops if o == op)  # noqa: E731
    then_words = len(_words(old))
    return {"words_then": then_words, "words_now": len(_words(new)), "kept": n("="),
            "taken_out": n("-"), "added": n("+"),
            "share_kept": round(n("=") / then_words, 3) if then_words else None,
            "similarity": round(similarity(old, new), 3), "diff": ops}


def for_record(rec: dict, pageid: int, current_text: str) -> dict:
    versions = []
    for d in DATES:
        if d >= rec["revision_timestamp"][:10]:
            continue
        v = version_at(pageid, d)
        if not v:
            continue
        f, lead = _version(v["content"])
        versions.append({"date": d, "revision": v["revision"], "timestamp": v["timestamp"], **f,
                         "_lead": lead, "sources": _sources_of(v["content"])})
    f, _ = _version(current_text)
    versions.append({"date": rec["revision_timestamp"][:10], "revision": rec["revision"],
                     "timestamp": rec["revision_timestamp"], **f, "analysed": True,
                     "sources": [[x["source"], x["citations"]] for x in (rec.get("sources") or {}).get("list", [])]})
    for i in range(1, len(versions)):   # first paragraph compared with the previous date
        versions[i]["diff_from_previous"] = diff_ops(versions[i - 1]["first_paragraph"],
                                                     versions[i]["first_paragraph"])
    out = {"revision": rec["revision"], "versions": versions}
    base = versions[0] if len(versions) > 1 else None
    if base:
        now = [(s["id"], s["text"]) for s in rec["sentences"] if s["id"].startswith("lead")]
        out["baseline"] = {"date": base["date"], "revision": base["revision"]}
        out["most_changed"] = most_changed(base["_lead"], now)
        add_paths(out["most_changed"], [v["_lead"] for v in versions[:-1]], [v["date"] for v in versions[:-1]])
        out["first_paragraph_change"] = paragraph_change(base["first_paragraph"],
                                                         versions[-1]["first_paragraph"])
    for v in versions:
        v.pop("_lead", None)
    return out


def build(records: list[dict], log=print) -> dict:
    from .fetch import mediawiki as mw
    old = json.loads(THEN_NOW_JSON.read_text(encoding="utf-8")) if THEN_NOW_JSON.exists() else {}
    arts = old.get("articles", {})
    for i, r in enumerate(records):
        if (arts.get(r["article"]) or {}).get("revision") == r["revision"]:
            continue
        try:
            rev = mw.get_revision(r["revision"])
            arts[r["article"]] = for_record(r, rev["pageid"], rev["content"])
        except Exception as ex:   # noqa: BLE001 - network: left for the next run
            log(f"  then-now: {r['article']}: {str(ex)[:100]}")
        if i % 50 == 0:
            log(f"  then-now: {i + 1:,} of {len(records):,}")
            _write(arts)
    return _write(arts)


def _write(arts):
    d = {"built": dt.date.today().isoformat(), "dates": DATES, "rule": __doc__.strip(),
         "articles": dict(sorted(arts.items()))}
    from . import redact
    for _a, _e in d["articles"].items():   # disclosing quoted text is not kept (wtl/redact.py)
        redact.then_now_entry(_e, _a)
    THEN_NOW_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=0, sort_keys=True) + "\n",
                             encoding="utf-8")
    return d
