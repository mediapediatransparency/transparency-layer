"""Talk-page decisions about an article's text, read from its talk page and archives.

Each analysed article's talk page and all its subpages (archives, FAQ) are read as they stood
when the analysed revision was saved. Each level-2 section (== Heading ==) is one discussion.
Kept, by fixed rules:

- request for comment (RfC): the heading says "RfC" or "request for comment", or the section
  carries an {{rfc}} tag or an RfC closing box;
- discussion ban (moratorium): the heading or a sub-heading says "moratorium" (a discussion
  about a ban), or the text of the closing box does (a discussion closed with a ban mentioned,
  for example an edit request declined because of one);
- an edit request ("edit request" in the heading, or an {{edit extended-protected}} tag or
  similar) that quotes today's text;
- a closed discussion that quotes today's text: the section has a closing box ({{atop}},
  {{archive top}}, {{closed rfc top}}, {{discussion top}} and their redirects) and quotes eight or
  more words in a row of a sentence in the analysed revision;
- a discussion that a tag in the article links to ({{Disputed inline|talk=…}}).

For each: the page and heading (account names replaced with "[account]"), when it began (the
earliest signature date), whether it was closed and when (the first signature date after the
closing box opens), a ban length or end date when the closing text states one ("for one
year", "until February 21, 2026"), and which sentences of today's text it quotes. Who took part, and who closed it, is
not kept. The text of the closing statement is not kept either: only these facts, and a link.

Nothing here says whether a decision was right, or whether it was followed. A discussion that
quotes a sentence may be about a different version of it.
"""

import datetime as dt
import json
import re

from .config import ROOT
from .fetch import cache
from .fetch.mediawiki import api

TALK_JSON = ROOT / "data" / "talk.json"
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July",
                                      "August", "September", "October", "November", "December"], 1)}
SIG = re.compile(r"(\d{1,2}):(\d{2}), (\d{1,2}) (" + "|".join(MONTHS) + r") (\d{4}) \(UTC\)")
H2 = re.compile(r"^==(?!=)\s*(.*?)\s*==\s*$", re.M)
RFC_HEAD = re.compile(r"\bRfCs?\b|request for comments?", re.I)
RFC_TAG = re.compile(r"\{\{\s*(?:rfc|closed rfc top|rfc top|rfcquote)\b|"
                     r"archived record of a request for comment", re.I)
CLOSE = re.compile(r"\{\{\s*(?:atop|archive top|archivetop|closed rfc top|rfc top|discussion top|dtop|"
                   r"discussiontop|closed top|close top|hat top|cot|collapse top|closed rfc|archive-top|"
                   r"discussion-top|ctop)\s*[|}]", re.I)
CLOSE_FORMAL = re.compile(r"\{\{\s*(?:atop|archive top|archivetop|closed rfc top|rfc top|discussion top|"
                          r"dtop|discussiontop|archive-top|discussion-top)\s*[|}]", re.I)
MORATORIUM = re.compile(r"\bmoratori(?:um|a)\b", re.I)
NUM = {"one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "six": 6, "nine": 9, "twelve": 12,
       "eighteen": 18, "twenty-four": 24}
LENGTH = re.compile(r"\b(\d{1,2}|one|a|an|two|three|four|six|nine|twelve|eighteen|twenty-four)[ -]"
                    r"(years?|months?)\b", re.I)
MONTH_ALT = "|".join(MONTHS)
UNTIL = re.compile(r"\b(?:until|through|expir\w*(?: on)?|ends?(?: on)?)\s+(?:(\d{1,2})\s+(" + MONTH_ALT + r")|(" + MONTH_ALT
                   + r")\s+(\d{1,2}),?)\s+(\d{4})", re.I)
H_SUB = re.compile(r"^={3,}\s*(.*?)\s*={3,}\s*$", re.M)
EDIT_REQ = re.compile(r"\bedit request\b|\{\{\s*edit (?:extended|semi|fully|template)[- ]protected", re.I)
USER = re.compile(r"\[\[\s*(?:User|User talk|Special:Contributions)\s*:[^\]]*\]\]|"
                  r"\b(?:User|User talk)\s*:\s*[^\s\]|,;]+", re.I)
WORDS = re.compile(r"[a-z0-9]+")
QUOTE_RUN = 8


def _date(m) -> str:
    return f"{int(m.group(5)):04d}-{MONTHS[m.group(4)]:02d}-{int(m.group(3)):02d}"


def _pages(title: str) -> list[str]:
    """Talk page and its subpages (current titles)."""
    p = cache.path("talk", "pages", re.sub(r"\W+", "_", title)[:120])
    hit = cache.load(p)
    if hit is not None:
        return hit
    out, cont = [f"Talk:{title}"], {}
    while True:
        d = api({"action": "query", "list": "allpages", "apnamespace": "1", "apprefix": f"{title}/",
                 "aplimit": "500", **cont})
        out += [x["title"] for x in d.get("query", {}).get("allpages", [])]
        if "continue" not in d:
            break
        cont = d["continue"]
    cache.save(p, out)
    return out


def page_at(page: str, timestamp: str) -> dict | None:
    p = cache.path("talk", "text", re.sub(r"\W+", "_", page)[:150] + "_" + timestamp.replace(":", ""))
    hit = cache.load(p)
    if hit is not None:
        return hit or None
    d = api({"action": "query", "prop": "revisions", "titles": page, "rvlimit": "1",
             "rvstart": timestamp, "rvdir": "older", "rvprop": "ids|content", "rvslots": "main"})
    pg = d["query"]["pages"][0]
    revs = pg.get("revisions")
    out = ({"revid": revs[0]["revid"], "content": revs[0]["slots"]["main"].get("content", "")}
           if revs else {})
    cache.save(p, out)
    return out or None


def _norm_words(s: str) -> list[str]:
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    return WORDS.findall(s.lower())


def _shingles(ws, n=QUOTE_RUN):
    return {" ".join(ws[i:i + n]) for i in range(len(ws) - n + 1)}


def _anchor(heading: str) -> str:
    h = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", heading)
    h = re.sub(r"'''?|<[^>]+>|\{\{[^{}]*\}\}", "", h).strip()
    return h.replace(" ", "_")


def _clean_heading(heading: str, names: set[str]) -> str:
    h = USER.sub("[account]", heading)
    h = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", h)
    h = re.sub(r"'''?|<[^>]+>|\{\{[^{}]*\}\}", "", h).strip()
    for n in sorted(names, key=len, reverse=True):
        if len(n) >= 4 and n in h:
            h = re.sub(r"(?<!\w)" + re.escape(n) + r"(?!\w)", "[account]", h)
    return h[:200]


def sections(text: str):
    heads = list(H2.finditer(text))
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        yield m.group(1), text[m.end():end]


def read_section(heading: str, body: str) -> dict:
    sigs = list(SIG.finditer(body))
    close = CLOSE_FORMAL.search(body) or CLOSE.search(body)
    closed_on, close_text = None, ""
    if close:
        after = next((m for m in sigs if m.start() > close.start()), None)
        closed_on = _date(after) if after else None
        close_text = body[close.start(): after.start() if after else close.start() + 3000]
    heads = " | ".join([heading] + H_SUB.findall(body))
    in_heads, in_close = bool(MORATORIUM.search(heads)), bool(MORATORIUM.search(close_text))
    months, until = None, None
    if in_heads or in_close:
        src = close_text if in_close else body[:4000]
        for m in LENGTH.finditer(src):
            k = m.group(1).lower()
            n = int(k) if k.isdigit() else NUM.get(k)
            if n:
                months = n * (12 if m.group(2).lower().startswith("year") else 1)
                break
        u = UNTIL.search(src)
        if u:
            day = u.group(1) or u.group(4)
            mon = (u.group(2) or u.group(3)).capitalize()
            until = f"{int(u.group(5)):04d}-{MONTHS[mon]:02d}-{int(day):02d}"
    return {
        "rfc": bool(RFC_HEAD.search(heads) or RFC_TAG.search(body)),
        "moratorium_discussed": in_heads,
        "moratorium_in_closing": in_close,
        "edit_request": bool(EDIT_REQ.search(heading) or EDIT_REQ.search(body[:2000])),
        "closed": bool(close),
        "closed_on": closed_on,
        "started": min((_date(m) for m in sigs), default=None),
        "ban_months": months,
        "ban_until": until,
    }


def for_article(rec: dict, names: set[str]) -> dict:
    title, ts = rec["article"], rec["revision_timestamp"]
    sents = [(s["id"], _norm_words(s["text"])) for s in rec["sentences"]]
    sh = {sid: _shingles(ws) for sid, ws in sents if len(ws) >= QUOTE_RUN}
    linked = set()
    for s in rec["sentences"]:
        for t in s.get("tags") or []:
            if t.get("talk"):
                linked.add(t["talk"].replace("_", " ").strip())
    pages_used, found = [], []
    for page in _pages(title):
        got = page_at(page, ts)
        if not got:
            continue
        pages_used.append({"page": page, "revision": got["revid"]})
        for heading, body in sections(got["content"]):
            info = read_section(heading, body)
            anchor = _anchor(heading)
            is_linked = f"{page}#{anchor.replace('_', ' ')}" in linked
            words = _norm_words(body)
            sec_sh = _shingles(words)
            quotes = sorted(sid for sid, s in sh.items() if s & sec_sh)
            keep = (info["rfc"] or info["moratorium_discussed"] or info["moratorium_in_closing"]
                    or is_linked or (info["closed"] and quotes) or (info["edit_request"] and quotes))
            if not keep:
                continue
            found.append({"page": page, "heading": _clean_heading(heading, names), "anchor": anchor,
                          "url": "https://en.wikipedia.org/wiki/" + page.replace(" ", "_") + "#" + anchor,
                          **{k: info[k] for k in ("rfc", "moratorium_discussed", "moratorium_in_closing",
                                                  "edit_request", "started", "closed", "closed_on",
                                                  "ban_months", "ban_until")},
                          "linked_from_article": is_linked,
                          "quotes_sentences": quotes})
    found.sort(key=lambda x: (x["started"] or "9999", x["page"], x["anchor"]))
    return {"revision": rec["revision"], "read_as_of": ts, "pages": pages_used,
            "counts": {"talk_pages": len(pages_used), "rfcs": sum(x["rfc"] for x in found),
                       "moratorium_discussions": sum(x["moratorium_discussed"] for x in found),
                       "closed_with_moratorium_mentioned": sum(x["moratorium_in_closing"] for x in found),
                       "edit_requests_quoting_text": sum(1 for x in found if x["edit_request"] and x["quotes_sentences"]),
                       "closed_discussions_quoting_text": sum(1 for x in found if x["closed"] and x["quotes_sentences"]),
                       "linked_from_article": sum(x["linked_from_article"] for x in found)},
            "discussions": found}


def build(records: list[dict], log=print) -> dict:
    import csv
    from .fetch import mediawiki as mw
    from .config import SANCTIONS_CSV as DEFAULT_CSV
    sanc = {r["username"] for r in csv.DictReader(open(DEFAULT_CSV, encoding="utf-8"))}
    old = json.loads(TALK_JSON.read_text(encoding="utf-8")) if TALK_JSON.exists() else {"articles": {}}
    arts = old.get("articles", {})
    for i, r in enumerate(records):
        prev = arts.get(r["article"])
        if prev and prev.get("revision") == r["revision"]:
            continue
        try:
            rev = mw.get_revision(r["revision"])
            names = {h["user"] for h in mw.get_history(rev["pageid"], r["revision"]) if h.get("user")} | sanc
            arts[r["article"]] = for_article(r, names)
        except Exception as ex:   # noqa: BLE001 - network: left for the next run
            log(f"  talk: {r['article']}: {str(ex)[:100]}")
            continue
        if i % 25 == 0:
            log(f"  talk: {i + 1:,} of {len(records):,}")
            _write(arts)
    return _write(arts)


def _write(arts):
    d = {"built": dt.date.today().isoformat(), "rule": __doc__.strip(),
         "articles": dict(sorted(arts.items()))}
    TALK_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    return d
