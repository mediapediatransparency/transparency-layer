"""Sources cited in an article, and who added each citation.

Everything here comes from the analysed revision itself, so records stay reproducible:
- a citation is a <ref>…</ref> footnote, or a citation template ({{cite …}}, {{citation …}})
  outside footnotes (for example in a bibliography). Re-uses of a named footnote
  (<ref name="x" />) are not counted again, and {{sfn}} short footnotes point to a bibliography
  entry that is counted once;
- the source of a citation is the website it links to (url=, or the first link in the
  footnote), reduced to its main domain; without a link, the publication name it gives
  (work=, newspaper=, publisher=, …); otherwise "unidentified";
- a citation is credited to the editor who added the words of its domain (or of its
  publication name), using the same WikiWho token authorship as the prose.

What outside records say about each source (Wikipedia's own ratings, independent ratings,
Wikidata facts) is kept separately, in data/outlets.json (see wtl/outlets.py), and joined only
when the site is built.
"""

import re
from collections import Counter
from urllib.parse import urlsplit

from .metrics import authorship as au

REF = re.compile(r"<ref(?:\s[^>]*)?(?<!/)>(.*?)</ref\s*>", re.I | re.S)
CITE_START = re.compile(r"\{\{\s*(?:cite\s+[a-z ]+?|citation|vcite\s+\w+)\s*\|", re.I)
URL_PARAM = re.compile(r"\|\s*(?:url|chapter-url|contribution-url)\s*=\s*(https?://[^\s|}<\]]+)", re.I)
BARE_URL = re.compile(r"https?://[^\s|}<\]\"']+", re.I)
NAME_PARAM = re.compile(r"\|\s*(work|website|newspaper|magazine|journal|periodical|agency|publisher)"
                        r"\s*=\s*([^|}]*)", re.I)
ISBN = re.compile(r"\|\s*isbn\s*=|\{\{\s*cite\s+book", re.I)
ARCHIVE = re.compile(r"^https?://(?:web\.)?archive\.(?:org|today|is|ph)/(?:web/)?[\d*a-z_]*/?(https?://.+)$", re.I)
WIKILINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]")

# Second-level registries under which the registrable domain has three labels (bbc.co.uk).
MULTI_SUFFIX = {"co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk", "co.il", "org.il", "ac.il",
                "gov.il", "co.in", "net.in", "org.in", "gov.in", "com.au", "net.au", "org.au",
                "gov.au", "co.nz", "co.za", "com.br", "com.cn", "com.hk", "com.sg", "com.tr",
                "com.pk", "gov.pk", "com.eg", "com.sa", "com.lb", "co.jp", "or.jp", "ne.jp",
                "com.mx", "com.ar", "com.ua", "org.ua", "gov.ua", "co.kr", "com.tw", "edu.au",
                "ac.in", "edu.pk", "gc.ca", "qc.ca", "gov.ru", "msk.ru", "spb.ru", "com.ru"}
SKIP_HOST = ("www.", "m.", "amp.", "mobile.", "en.m.")


def host_of(url: str) -> str:
    """Lower-cased host of a URL, unwrapping web-archive links to the original."""
    m = ARCHIVE.match(url)
    if m:
        url = m.group(1)
    try:
        h = (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""
    for p in SKIP_HOST:
        if h.startswith(p):
            h = h[len(p):]
    return h


def registrable(host: str) -> str:
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in MULTI_SUFFIX:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def clean_name(v: str) -> str:
    v = WIKILINK.sub(r"\1", v)
    v = re.sub(r"\{\{[^{}]*\}\}|<[^>]+>|'''?|&nbsp;", " ", v)
    return re.sub(r"\s+", " ", v).strip(" .,;:")


def _template_end(text: str, start: int) -> int:
    depth, i, n = 0, start, len(text)
    while i < n - 1:
        two = text[i:i + 2]
        if two == "{{":
            depth += 1
            i += 2
            continue
        if two == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return i
            continue
        i += 1
    return n


SHORT = re.compile(r"\{\{\s*(sfnp?|harvnb|harvp|harv|harvtxt|harvcoltxt|sfnm)\s*\|", re.I)
YEAR = re.compile(r"^\s*(\d{4})[a-z]?\s*$")
YEAR_IN = re.compile(r"(\d{4})")
AUTHOR = re.compile(r"\|\s*(?:last1?|author1?|surname1?|editor1?-last|editor-last1?|editor1?|"
                    r"last-author-amp)\s*=\s*([^|}]*)", re.I)
DATE = re.compile(r"\|\s*(?:year|date|orig-date)\s*=\s*([^|}]*)", re.I)
REF_KEY = re.compile(r"\|\s*ref\s*=\s*\{\{\s*(?:sfnref|harvid)\s*\|([^}]*)\}\}", re.I)
TWEET = re.compile(r"\{\{\s*cite\s+tweet", re.I)
# Hosting platforms: a link there says where a copy is, not who published it. When the
# citation names the publication, that name is the source.
PLATFORMS = {"google.com", "archive.org", "doi.org", "jstor.org", "worldcat.org", "semanticscholar.org",
             "researchgate.net", "academia.edu", "youtube.com", "youtu.be", "ghostarchive.org",
             "archive.ph", "archive.today", "archive.is", "muse.jhu.edu", "jhu.edu", "ssrn.com",
             "proquest.com", "ebscohost.com", "books.google.com", "google.co.uk", "hathitrust.org",
             "nih.gov", "europepmc.org", "scribd.com", "issuu.com", "wikiwix.com", "webcitation.org",
             "yahoo.com", "msn.com", "pressreader.com", "newsbank.com", "newspapers.com"}


def _templates(text, a, b, pattern):
    """(start, end) of each template matching `pattern` that starts in text[a:b], outermost only."""
    out, pos = [], a
    for m in pattern.finditer(text, a, b):
        s = m.start()
        if s < pos:
            continue
        e = _template_end(text, s)
        out.append((s, min(e, b) if e <= b else e))
        pos = e
    return out


def _short_key(text, s, e):
    """(first surname, year) of a short footnote such as {{sfn|Morris|2004|p=12}}, and the span
    of its first name for attribution."""
    inner = text[s + 2:e - 2]
    parts = inner.split("|")[1:]
    pos = s + 2 + len(inner.split("|")[0]) + 1
    names, year, first_span = [], None, None
    for raw in parts:
        if "=" in raw:
            pos += len(raw) + 1
            continue
        if YEAR.match(raw):
            year = YEAR.match(raw).group(1)
            break
        if first_span is None and raw.strip():
            off = len(raw) - len(raw.lstrip())
            first_span = (pos + off, pos + off + len(raw.strip()))
        names.append(raw.strip().lower())
        pos += len(raw) + 1
    return ((names[0] if names else "", year or ""), first_span or (s, e))


def _bib_keys(text, s, e):
    body = text[s:e]
    keys = []
    m = REF_KEY.search(body)
    if m:
        ps = [x.strip() for x in m.group(1).split("|") if x.strip() and "=" not in x]
        if ps:
            y = next((x for x in ps if YEAR.match(x)), "")
            keys.append((ps[0].lower(), YEAR.match(y).group(1) if y else ""))
    am, dm = AUTHOR.search(body), DATE.search(body)
    if am:
        name = clean_name(am.group(1)).split(",")[0].strip().lower()
        yr = YEAR_IN.search(dm.group(1)).group(1) if dm and YEAR_IN.search(dm.group(1)) else ""
        if name:
            keys.append((name, yr))
    return keys


def find(text: str) -> list[dict]:
    """Citations in the wikitext, one per source cited: each cite template or short footnote
    inside a footnote, else the footnote itself; plus bibliography entries outside footnotes
    that no short footnote points to. Each: {start, end, source, name, url_host, attr, short}."""
    refs = [(m.start(1), m.end(1)) for m in REF.finditer(text)]
    in_ref = lambda x: any(a <= x < b for a, b in refs)  # noqa: E731
    outside = [(s, e) for s, e in _templates(text, 0, len(text), CITE_START) if not in_ref(s)]
    bib, bib_entry = {}, []
    for s, e in outside:
        c = _one(text, s, e)
        bib_entry.append(c)
        for k in _bib_keys(text, s, e):
            bib.setdefault(k, c)
            bib.setdefault((k[0], ""), c)
    used = set()
    cites = []

    def short_cite(s, e):
        k, span = _short_key(text, s, e)
        target = bib.get(k) or bib.get((k[0], ""))
        if target:
            used.add(id(target))
            return {**target, "start": s, "end": e, "attr": span, "short": True}
        return {"start": s, "end": e, "source": "short footnote (entry not found)", "name": "",
                "url_host": "", "attr": span, "short": True}

    for a, b in refs:
        items = []
        for s, e in _templates(text, a, b, CITE_START):
            items.append(_one(text, s, e))
        for s, e in _templates(text, a, b, SHORT):
            items.append(short_cite(s, e))
        cites += items or [_one(text, a, b)]
    for s, e in _templates(text, 0, len(text), SHORT):   # {{sfn}} outside <ref> makes its own footnote
        if not in_ref(s):
            cites.append(short_cite(s, e))
    cites += [c for c in bib_entry if id(c) not in used]
    cites.sort(key=lambda c: (c["start"], c["end"]))
    return cites


NAME_ORDER = ["journal", "newspaper", "magazine", "work", "website", "periodical", "agency", "publisher"]


def _one(text: str, a: int, b: int) -> dict:
    body = text[a:b]
    url, upos = None, None
    m = URL_PARAM.search(body)
    if m:
        url, upos = m.group(1), a + m.start(1)
    else:
        m = BARE_URL.search(body)
        if m:
            url, upos = m.group(0), a + m.start(0)
    found = {}
    for nm in NAME_PARAM.finditer(body):
        v = clean_name(nm.group(2))
        if v and nm.group(1).lower() not in found:
            found[nm.group(1).lower()] = (v, (a + nm.start(2), a + nm.end(2)))
    name, npos = next((found[k] for k in NAME_ORDER if k in found), ("", None))
    host = host_of(url) if url else ""
    reg = registrable(host) if host else ""
    platform = reg in PLATFORMS or host in PLATFORMS
    if TWEET.search(body):
        source, attr = "twitter.com", (a, b)
    elif platform and not name and host.startswith("books.google."):
        # a book read on Google Books, publisher not given: the host is not the source
        source, attr = "book (no publisher given)", (a, b)
    elif host and not (platform and name):
        source = reg
        hs = text.find(host, upos, b) if not ARCHIVE.match(url) else -1
        attr = (hs, hs + len(host)) if hs >= 0 else (upos, upos + len(url))
    elif name:
        source, attr = "name:" + name.lower(), npos
    elif ISBN.search(body):
        source, attr = "book (no publisher given)", (a, b)
    else:
        source, attr = "unidentified", (a, b)
    return {"start": a, "end": b, "source": source, "name": name, "url_host": host, "attr": attr,
            "short": False}


def credit(cites, tokens, spans, hist, who):
    """Editor key for each citation: the editor of most of the tokens in its attribution span
    (ties: earliest origin revision, then key). Adds new keys to `who`."""
    starts = sorted((sp[0], sp[1], i) for i, sp in enumerate(spans) if sp is not None)
    out = []
    j0 = 0
    for c in cites:
        a, b = c["attr"]
        while j0 < len(starts) and starts[j0][1] <= a:
            j0 += 1
        cnt, first = Counter(), {}
        j = j0
        while j < len(starts) and starts[j][0] < b:
            s, o_rev, ed = tokens[starts[j][2]]
            key, name, acct = au.editor_key(o_rev, ed, hist)
            who.setdefault(key, (name, acct))
            cnt[key] += 1
            first[key] = min(first.get(key, o_rev), o_rev)
            j += 1
        out.append(min(cnt, key=lambda k: (-cnt[k], first[k], k)) if cnt else None)
    return out


def compute(text, lay, tokens, spans, hist, who, labels):
    """The record's "sources" block and per-editor citation counts. `labels` maps editor key to
    label for prose editors; editors who only added citations get further labels, numbered on
    from the last prose editor in order of citations added. Returns (block, labels_added,
    count_by_key)."""
    cites = find(text)
    keys = credit(cites, tokens, spans, hist, who)
    by_key = Counter(k for k in keys if k)
    extra = {}
    n = len(labels)
    for k in sorted((k for k in by_key if k not in labels), key=lambda k: (-by_key[k], k)):
        n += 1
        extra[k] = f"Editor {n}"
    lab = {**labels, **extra}
    per = {}
    for c, k in zip(cites, keys):
        s = per.setdefault(c["source"], {"source": c["source"], "names": Counter(), "citations": 0,
                                         "lead_citations": 0, "added_by": Counter()})
        s["citations"] += 1
        if lay.section_of[min(c["start"], len(lay.section_of) - 1)] == 0:
            s["lead_citations"] += 1
        if c["name"]:
            s["names"][c["name"]] += 1
        s["added_by"][lab[k] if k else "unknown"] += 1
    rows = []
    for s in sorted(per.values(), key=lambda s: (-s["citations"], s["source"])):
        rows.append({
            "source": s["source"],
            "name_as_cited": (min(s["names"], key=lambda x: (-s["names"][x], x)) if s["names"] else ""),
            "citations": s["citations"],
            "lead_citations": s["lead_citations"],
            "added_by": dict(sorted(s["added_by"].items(),
                                    key=lambda x: (-x[1], _label_no(x[0])))),
        })
    block = {
        "citations": len(cites),
        "lead_citations": sum(1 for c in cites
                              if lay.section_of[min(c["start"], len(lay.section_of) - 1)] == 0),
        "short_footnotes": sum(1 for c in cites if c["short"]),
        "with_link": sum(1 for c in cites if c["url_host"]),
        "distinct_sources": len(per),
        "editors_adding_citations": len(by_key),
        "citation_only_editors": len(extra),
        "list": rows,
    }
    return block, extra, by_key


def _label_no(label: str) -> int:
    try:
        return int(label.split()[-1])
    except ValueError:
        return 10 ** 9
