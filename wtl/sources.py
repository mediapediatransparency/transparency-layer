"""Sources cited in an article, and who added each citation.

Everything here comes from the analysed revision itself, so records stay reproducible:
- a citation is a <ref>…</ref> footnote, or a citation template ({{cite …}}, {{citation …}})
  outside footnotes (for example in a bibliography). Re-uses of a named footnote
  (<ref name="x" />) are not counted again, and {{sfn}} short footnotes point to a bibliography
  entry that is counted once;
- the source of a citation is the website it links to (url=, or the first link in the
  footnote), reduced to its main domain; without a link, the publication name it gives
  (work=, newspaper=, publisher=, …); a name that the fixed name list (data/source_names.json)
  links to one website counts as that website;
- a footnote written as plain text, without a citation template, is matched in this order:
  a link to a bibliography anchor ([[#id|…]]); an author and year that match a bibliography
  entry ("Morris, 2001, p. 259"); a publication in italics that is on the name list
  (''New York Times''); a publisher on the name list named in the text; an ISBN (a book with
  no publisher given); otherwise "unidentified";
- a citation is credited to the editor who added the words of its domain (or of its
  publication name), using the same WikiWho token authorship as the prose.

What outside records say about each source (Wikipedia's own ratings, independent ratings,
Wikidata facts) is kept separately, in data/outlets.json (see wtl/outlets.py), and joined only
when the site is built.
"""

import re
from collections import Counter
from urllib.parse import urlsplit

from . import books
from .metrics import authorship as au

REF = re.compile(r"<ref(?:\s[^>]*)?(?<!/)>(.*?)</ref\s*>", re.I | re.S)
CITE_START = re.compile(r"\{\{\s*(?:cite\s+[a-z ]+?|citation|vcite\s+\w+)\s*\|", re.I)
URL_PARAM = re.compile(r"\|\s*(?:url|chapter-url|contribution-url)\s*=\s*(https?://[^\s|}<\]]+)", re.I)
BARE_URL = re.compile(r"https?://[^\s|}<\]\"']+", re.I)
NAME_PARAM = re.compile(r"\|\s*(work|website|newspaper|magazine|journal|periodical|agency|publisher)"
                        r"\s*=\s*((?:\[\[[^\]]*\]\]|[^|}\[]|\[(?!\[))*)", re.I)   # piped links kept whole
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


_PSL = None   # (rules, wildcards, exceptions, sha256) from data/public_suffix_list.dat


def _psl():
    """The Public Suffix List (publicsuffix.org), pinned in data/. Without the file, the short
    MULTI_SUFFIX list is used."""
    global _PSL
    if _PSL is None:
        import hashlib
        from .config import ROOT
        p = ROOT / "data" / "public_suffix_list.dat"
        if not p.exists():
            _PSL = (None, None, None, None)
            return _PSL
        raw = p.read_bytes()
        rules, wild, exc = set(), set(), set()
        for line in raw.decode("utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            line = line.split()[0].lower()
            if line.startswith("!"):
                exc.add(line[1:])
            elif line.startswith("*."):
                wild.add(line[2:])
            else:
                rules.add(line)
        _PSL = (rules, wild, exc, hashlib.sha256(raw).hexdigest())
    return _PSL


def psl_sha256():
    return _psl()[3]


def registrable(host: str) -> str:
    """The registrable domain of a host: one label below its public suffix (bbc.co.uk,
    pib.nic.in, example.blogspot.com), per the Public Suffix List."""
    parts = host.split(".")
    rules, wild, exc, _ = _psl()
    if rules is None:
        if len(parts) >= 3 and ".".join(parts[-2:]) in MULTI_SUFFIX:
            return ".".join(parts[-3:])
        return ".".join(parts[-2:]) if len(parts) >= 2 else host
    n = len(parts)
    suffix_len = 1                      # the default rule "*": the last label
    for i in range(n):                  # longest candidate first; the first match prevails
        cand = ".".join(parts[i:])
        if cand in exc:
            suffix_len = n - i - 1
            break
        if cand in rules or (i + 1 < n and ".".join(parts[i + 1:]) in wild):
            suffix_len = n - i
            break
    if suffix_len >= n:
        return host
    return ".".join(parts[n - suffix_len - 1:])


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


# ------------------------------------------------------------- fixed name list (free text)
PERIODICAL_FIELDS = ("journal", "newspaper", "magazine", "work", "website", "periodical", "agency")
MIN_ARTICLES_PERIODICAL = 3
MIN_ARTICLES_PUBLISHER = 5
MIN_DOMAIN_SHARE = 0.8
ITALIC = re.compile(r"(?<!')''(?!')(.+?)(?<!')''(?!')")
ANCHOR_LINK = re.compile(r"\[\[\s*#([^|\]]+)")
REF_PLAIN = re.compile(r"\|\s*ref\s*=\s*([^|{}\n]+?)\s*(?=\||\}\})", re.I)
CAP_WORD = re.compile(r"\b[A-Z][\w'’-]{2,}")
ISBN_TEXT = re.compile(r"\{\{\s*ISBN\s*\||\bISBN(?:-1[03])?[\s:]", re.I)
# Opinion, comment and blog sections, recognised from the web address or the template.
OPINION_PATH = re.compile(r"/(opinions?|commentisfree|comment|commentary|op-?eds?|editorials?|"
                          r"columnists?|columns?|blogs?|voices|views|perspectives?|ideas)(/|$)",
                          re.I)
OPINION_HOST = re.compile(r"^(blogs?|opinion|opinions)\.", re.I)
OPINION_PARAM = re.compile(r"\|\s*(?:type|department|section)\s*=\s*[^|}]*\b(op-?ed|opinion|editorial|"
                           r"column|commentary|blog)", re.I)
PAGE_PARAM = re.compile(r"\|\s*(?:pages?|p|pp|at|loc|location|quote)\s*=\s*[^|}\s]", re.I)
LANG_PARAM = re.compile(r"\|\s*language\s*=\s*([^|}]*)", re.I)
DEAD = re.compile(r"\|\s*url-status\s*=\s*(dead|usurped|unfit)", re.I)
ARCHIVED = re.compile(r"\|\s*archive-?url\s*=\s*\S", re.I)
ACCESS = re.compile(r"\|\s*(?:url-access|access)\s*=\s*(subscription|registration|limited)", re.I)
BOOKISH = re.compile(r"\{\{\s*(?:cite\s+book|citation)\b|\|\s*isbn\s*=", re.I)
CHECK_FLAGS = ["opinion", "no_link", "book_without_page", "not_english", "not_english_no_quote",
               "dead_link_no_archive", "paywall_or_registration"]
# a quotation of the supporting passage, or its translation, given in the citation itself
QUOTE_PARAM = re.compile(r"\|\s*(?:quote|trans-quote|trans_quote|script-quote)\s*=\s*[^|}\s]", re.I)


def flags_of(text: str, c: dict) -> set[str]:
    """Facts about a citation that make it opinion, or harder for a reader to check. Read from
    its own wikitext (template parameters and web address)."""
    body = text[c["start"]:c["end"]]
    f = set()
    url = None
    m = URL_PARAM.search(body) or BARE_URL.search(body)
    if m:
        url = m.group(1) if m.re is URL_PARAM else m.group(0)
    path = ""
    if url:
        a = ARCHIVE.match(url)
        u = a.group(1) if a else url
        try:
            sp = urlsplit(u)
            path, host = sp.path or "", (sp.hostname or "").lower()
        except ValueError:
            host = ""
        if OPINION_PATH.search(path) or OPINION_HOST.match(host):
            f.add("opinion")
    if OPINION_PARAM.search(body):
        f.add("opinion")
    if not url and not c.get("url_host"):
        f.add("no_link")
    if (BOOKISH.search(body) or c["source"] == "book (no publisher given)") and not url \
            and not PAGE_PARAM.search(body):
        f.add("book_without_page")
    lm = LANG_PARAM.search(body)
    if lm and lm.group(1).strip().lower() not in ("", "en", "english", "en-us", "en-gb"):
        f.add("not_english")
    if DEAD.search(body) and not ARCHIVED.search(body):
        f.add("dead_link_no_archive")
    if ACCESS.search(body):
        f.add("paywall_or_registration")
    return f


UNMATCHED = ("unidentified", "book (no publisher given)")
NOT_FOUND = "short footnote (entry not found)"
BIB_UNKNOWN = "in the article's bibliography, source not named"
NOT_A_SOURCE = UNMATCHED + (NOT_FOUND, BIB_UNKNOWN)   # shown as coverage, never ranked
PLAIN_BIB_LINE = re.compile(r"^\*+[ \t]*(.+)$", re.M)
ANCHOR_TPL = re.compile(r"\{\{\s*[Aa]nchor\s*\|([^}]*)\}\}|\bid\s*=\s*\"([^\"]+)\"")


def _head_surname(text: str):
    """(first capitalised word before the first year, year or "") at the start of a citation."""
    head = WIKILINK.sub(r"\1", text[:160])
    head = re.sub(r"\{\{[^{}]*\}\}", " ", head)
    y = YEAR_IN.search(head)
    w = CAP_WORD.search(head[:80])
    if not w or (y and w.start() > y.start()):
        return None, None
    return w.group(0).lower(), (y.group(1) if y else "")
_NAMES = None   # the name list in use by find(); None = no list
_BOOKS = {}     # Open Library records by ISBN-13 in use by find() (wtl/books.py)


def norm_name(name: str) -> str:
    n = clean_name(name).lower().strip()
    n = re.sub(r"^the\s+", "", n)
    return re.sub(r"[^\w]+", " ", n).strip()


def build_names(texts: list[str]) -> dict:
    """The fixed name list, from citation templates in the given article texts: publications
    named in at least MIN_ARTICLES_PERIODICAL articles, publishers in at least
    MIN_ARTICLES_PUBLISHER, and for each name the one website it links to in at least
    MIN_DOMAIN_SHARE of its linked uses (at least 3)."""
    per_art = {"p": Counter(), "pub": Counter()}
    spell = {}
    doms = {}
    for text in texts:
        seen_p, seen_pub = set(), set()
        for s0, e0 in _templates(text, 0, len(text), CITE_START):
            body = text[s0:e0]
            m = URL_PARAM.search(body)
            host = host_of(m.group(1)) if m else ""
            reg = registrable(host) if host else ""
            for nm in NAME_PARAM.finditer(body):
                field, v = nm.group(1).lower(), clean_name(nm.group(2))
                n = norm_name(v)
                if len(n) < 4 or n.isdigit():
                    continue
                spell.setdefault(n, Counter())[v] += 1
                (seen_p if field in PERIODICAL_FIELDS else seen_pub).add(n)
                if reg and reg not in PLATFORMS and host not in PLATFORMS:
                    doms.setdefault(n, Counter())[reg] += 1
        per_art["p"].update(seen_p)
        per_art["pub"].update(seen_pub)
    canon = lambda n: min(spell[n], key=lambda x: (-spell[n][x], x))  # noqa: E731
    periodicals = {n: canon(n) for n, k in per_art["p"].items() if k >= MIN_ARTICLES_PERIODICAL}
    publishers = {n: canon(n) for n, k in per_art["pub"].items()
                  if k >= MIN_ARTICLES_PUBLISHER and len(n) >= 6 and n not in periodicals}
    domains = {}
    for n, c in doms.items():
        if n not in periodicals and n not in publishers:
            continue
        d, k = min(c.items(), key=lambda x: (-x[1], x[0]))
        if k >= 3 and k / sum(c.values()) >= MIN_DOMAIN_SHARE:
            domains[n] = d
    return {"rule": {"min_articles_periodical": MIN_ARTICLES_PERIODICAL,
                     "min_articles_publisher": MIN_ARTICLES_PUBLISHER,
                     "min_domain_share": MIN_DOMAIN_SHARE},
            "articles": len(texts), "periodicals": dict(sorted(periodicals.items())),
            "publishers": dict(sorted(publishers.items())), "domains": dict(sorted(domains.items()))}


def load_names():
    import json
    from .config import ROOT
    p = ROOT / "data" / "source_names.json"
    if not p.exists():
        return None, None
    raw = p.read_bytes()
    import hashlib
    names = json.loads(raw)
    pubs = sorted(names["publishers"].values(), key=lambda x: (-len(x), x))
    names["_pub_re"] = (re.compile(r"(?<![\w&])(" + "|".join(re.escape(x) for x in pubs) + r")(?![\w&])")
                        if pubs else None)
    return names, hashlib.sha256(raw).hexdigest()


def _named(name: str) -> str:
    """Source key for a publication name: its website when the name list links it to one."""
    n = norm_name(name)
    if _NAMES and n in _NAMES["domains"]:
        return _NAMES["domains"][n]
    return "name:" + name.lower()


def _free(text, a, b, bib, anchors):
    """A footnote without a citation template: see the module notes for the order of matching."""
    c = _one(text, a, b)
    if c["source"] not in UNMATCHED:
        return c
    body = text[a:b]
    m = ANCHOR_LINK.search(body)
    if m and m.group(1).strip() in anchors:
        return {**anchors[m.group(1).strip()], "start": a, "end": b,
                "attr": (a + m.start(1), a + m.end(1)), "short": True}
    head = WIKILINK.sub(r"\1", body[:160])
    y = YEAR_IN.search(head)
    for n, w in enumerate(CAP_WORD.finditer(head[:80])):
        if n >= 2 or (y and w.start() > y.start()):   # the author's name only
            break
        t = bib.get((w.group(0).lower(), y.group(1) if y else ""))
        if t:
            i = body.find(w.group(0))
            span = (a + i, a + i + len(w.group(0))) if i >= 0 else (a, b)
            return {**t, "start": a, "end": b, "attr": span, "short": True}
    if _NAMES:
        for m in ITALIC.finditer(body):
            n = norm_name(m.group(1))
            if n in _NAMES["periodicals"]:
                return {**c, "source": _named(_NAMES["periodicals"][n]),
                        "name": _NAMES["periodicals"][n], "attr": (a + m.start(1), a + m.end(1))}
        if _NAMES.get("_pub_re"):
            m = _NAMES["_pub_re"].search(body)
            if m:
                return {**c, "source": _named(m.group(1)), "name": m.group(1),
                        "attr": (a + m.start(1), a + m.end(1))}
    if ISBN_TEXT.search(body):
        return {**c, "source": "book (no publisher given)"}
    return c


def find(text: str, names: dict | None = None, books_data: dict | None = None) -> list[dict]:
    """Citations in the wikitext, one per source cited: each cite template or short footnote
    inside a footnote, else the footnote itself; plus bibliography entries outside footnotes
    that no short footnote points to. Each: {start, end, source, name, url_host, attr, short}.
    `names` is the fixed name list (load_names()); without it, free text is only matched by
    bibliography and ISBN. `books_data` (wtl/books.py load()) gives the publisher of a book
    cited by ISBN without one; such citations carry "publisher_from": "Open Library"."""
    global _NAMES, _BOOKS
    _NAMES = names
    _BOOKS = books_data or {}
    refs = [(m.start(1), m.end(1)) for m in REF.finditer(text)]
    in_ref = lambda x: any(a <= x < b for a, b in refs)  # noqa: E731
    outside = [(s, e) for s, e in _templates(text, 0, len(text), CITE_START) if not in_ref(s)]
    bib, bib_entry, anchors = {}, [], {}
    for s, e in outside:
        c = _one(text, s, e)
        bib_entry.append(c)
        rm = REF_PLAIN.search(text[s:e])
        if rm:
            anchors.setdefault(rm.group(1).strip(), c)
        for k in _bib_keys(text, s, e):
            bib.setdefault(k, c)
            bib.setdefault((k[0], ""), c)
    # bibliography written as plain text: bulleted lines outside footnotes without a citation
    # template, used only when a short reference points to them and they name a known source
    for m in PLAIN_BIB_LINE.finditer(text):
        s0, e0 = m.start(1), m.end(1)
        if in_ref(s0) or CITE_START.search(text, s0, e0) or not YEAR_IN.search(text, s0, e0):
            continue
        c = _free(text, s0, e0, {}, {})
        if c["source"] in UNMATCHED:
            c = {**c, "source": BIB_UNKNOWN}
        sn, yr = _head_surname(re.sub(ANCHOR_TPL, " ", text[s0:e0]))
        if sn:
            bib.setdefault((sn, yr), c)
            bib.setdefault((sn, ""), c)
        for am in ANCHOR_TPL.finditer(text, s0, e0):
            for x in (am.group(1) or am.group(2) or "").split("|"):
                if x.strip():
                    anchors.setdefault(x.strip(), c)
    used = set()
    cites = []

    def short_cite(s, e):
        k, span = _short_key(text, s, e)
        target = bib.get(k) or bib.get((k[0], ""))
        if target:
            used.add(id(target))
            return {**target, "start": s, "end": e, "attr": span, "short": True}
        return {"start": s, "end": e, "source": NOT_FOUND, "name": "",
                "url_host": "", "attr": span, "short": True, "surname": k[0]}

    for a, b in refs:
        items = []
        for s, e in _templates(text, a, b, CITE_START):
            items.append(_one(text, s, e))
        for s, e in _templates(text, a, b, SHORT):
            items.append(short_cite(s, e))
        if not items:
            c = _free(text, a, b, bib, anchors)
            for t in bib_entry:   # resolved to a bibliography entry: that entry is now cited
                if c.get("short") and t["start"] == c.get("bib_start"):
                    used.add(id(t))
            items = [c]
        cites += items
    for s, e in _templates(text, 0, len(text), SHORT):   # {{sfn}} outside <ref> makes its own footnote
        if not in_ref(s):
            cites.append(short_cite(s, e))
    cites += [c for c in bib_entry if id(c) not in used]
    # a short reference that names only an author ("Poe, pp. 171–172") counts as the source of
    # that author's full citation elsewhere in the article, when the author has exactly one
    by_author = {}
    for c in cites:
        if c["source"] not in NOT_A_SOURCE and c.get("surname"):
            by_author.setdefault(c["surname"], set()).add((c["source"], c["name"]))
    for i, c in enumerate(cites):
        if c["source"] in UNMATCHED or c["source"] == NOT_FOUND:
            sn = c.get("surname") or (_head_surname(text[c["start"]:c["end"]])[0]
                                      if c["end"] - c["start"] <= 120 else None)
            hit = by_author.get(sn) if sn else None
            if hit and len(hit) == 1:
                src, nm = next(iter(hit))
                cites[i] = {**c, "source": src, "name": nm, "short": True}
    # a book cited by ISBN with no publisher named: the publisher Open Library records for that
    # ISBN, else the Wikidata item that holds the ISBN's publisher prefix
    for i, c in enumerate(cites):
        if c["source"] == "book (no publisher given)" and _BOOKS:
            isbn, _ = books.isbn_in(text[c["start"]:c["end"]])
            if not isbn:
                continue
            rec = _BOOKS.get("books", {}).get(isbn)
            pubs = [p for p in (rec or {}).get("publishers", []) if clean_name(p)]
            sp = books.split(isbn)
            pre = _BOOKS.get("prefixes", {}).get(sp["registrant"]) if sp and sp["registrant"] else None
            if pubs:
                cites[i] = {**c, "source": _named(clean_name(pubs[0])), "name": "",
                            "ol_name": clean_name(pubs[0]), "publisher_from": "Open Library"}
            elif pre:
                cites[i] = {**c, "source": _named(pre["label"]), "name": "",
                            "ol_name": pre["label"], "publisher_from": "ISBN prefix (Wikidata)"}
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
        source, attr = _named(name), npos
    elif ISBN.search(body):
        source, attr = "book (no publisher given)", (a, b)
    else:
        source, attr = "unidentified", (a, b)
    am = AUTHOR.search(body) if CITE_START.match(body) else None
    surname = (clean_name(am.group(1)).split(",")[0].strip().lower() if am
               else _head_surname(body)[0] if source not in UNMATCHED else None)
    return {"start": a, "end": b, "source": source, "name": name, "url_host": host, "attr": attr,
            "short": False, "bib_start": a, "surname": surname}


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


DOI = re.compile(r"\|\s*doi\s*=\s*(10\.\d{4,9}/[^\s|}]+)|\bdoi\.org/(10\.\d{4,9}/[^\s|}\]<]+)", re.I)


def item_id(body: str) -> str | None:
    """The cited work's identifier: isbn:<ISBN-13>, doi:<DOI>, url:<host/path>, or
    isbn-invalid:<digits> for an ISBN that fails its check digit; None if there is none."""
    isbn, raw = books.isbn_in(body)
    if isbn:
        return "isbn:" + isbn
    m = DOI.search(body)
    if m:
        return "doi:" + (m.group(1) or m.group(2)).rstrip(".,;").lower()
    m = URL_PARAM.search(body) or BARE_URL.search(body)
    if m:
        u = m.group(1) if m.re is URL_PARAM else m.group(0)
        a = ARCHIVE.match(u)
        u = a.group(1) if a else u
        try:
            sp = urlsplit(u)
        except ValueError:
            sp = None
        if sp and sp.hostname:
            h = sp.hostname.lower()
            for p in SKIP_HOST:
                if h.startswith(p):
                    h = h[len(p):]
            path = (sp.path or "").rstrip("/")
            q = ("?" + sp.query) if sp.query and not re.fullmatch(r"(utm_[^&]*&?)+", sp.query) else ""
            return "url:" + h + path + q
    if raw:
        return "isbn-invalid:" + re.sub(r"[^0-9Xx]", "", raw).upper()
    return None


def compute(text, lay, tokens, spans, hist, who, labels, names=None, books_data=None):
    """The record's "sources" block and per-editor citation counts. `labels` maps editor key to
    label for prose editors; editors who only added citations get further labels, numbered on
    from the last prose editor in order of citations added. Returns (block, labels_added,
    count_by_key)."""
    cites = find(text, names, books_data)
    keys = credit(cites, tokens, spans, hist, who)
    by_key = Counter(k for k in keys if k)
    extra = {}
    n = len(labels)
    for k in sorted((k for k in by_key if k not in labels), key=lambda k: (-by_key[k], k)):
        n += 1
        extra[k] = f"Editor {n}"
    lab = {**labels, **extra}
    per = {}
    flag_tot = Counter()
    by_ed = {}
    items = {}
    for c, k in zip(cites, keys):
        s = per.setdefault(c["source"], {"source": c["source"], "names": Counter(), "citations": 0,
                                         "lead_citations": 0, "added_by": Counter(),
                                         "opinion_citations": 0, "flags": Counter(),
                                         "ol_names": Counter(), "publisher_from_isbn": Counter()})
        s["citations"] += 1
        body = text[c["start"]:c["end"]]
        fl = flags_of(text, c)
        isbn, _ = books.isbn_in(body)
        ol = (books_data or {}).get("books", {}).get(isbn) if isbn else None
        if ol and ol.get("languages") and "eng" not in ol["languages"]:
            fl.add("not_english")      # Open Library records the book in other languages only
        if "not_english" in fl and not QUOTE_PARAM.search(body):
            fl.add("not_english_no_quote")
        if "opinion" in fl:
            s["opinion_citations"] += 1
        s["flags"].update(fl)
        if c.get("publisher_from"):
            s["publisher_from_isbn"][c["publisher_from"]] += 1
            s["ol_names"][c["ol_name"]] += 1
        iid = item_id(body)
        if iid:
            it = items.setdefault(iid, {"id": iid, "source": c["source"], "citations": 0,
                                        "flags": set(), "editors": Counter(), "language": ""})
            it["citations"] += 1
            it["flags"] |= fl
            it["editors"][lab[k] if k else "unknown"] += 1
            lm = LANG_PARAM.search(body)
            if lm and not it["language"]:
                it["language"] = clean_name(lm.group(1))[:40]
        flag_tot.update(fl)
        e = by_ed.setdefault(lab[k] if k else "unknown", Counter())
        e["citations"] += 1
        e.update(fl)
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
            "opinion_citations": s["opinion_citations"],
            "flags": {f: s["flags"][f] for f in CHECK_FLAGS if s["flags"][f]},
            # citations naming no publisher whose publisher was found from the ISBN
            **({"publisher_from_isbn": dict(sorted(s["publisher_from_isbn"].items())),
                "publisher_name_from_isbn": min(s["ol_names"], key=lambda x: (-s["ol_names"][x], x))}
               if s["publisher_from_isbn"] else {}),
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
        # opinion and harder-to-check citations (see flags_of), for the article and per editor
        "flags": {f: flag_tot[f] for f in CHECK_FLAGS},
        "flags_by_editor": {l: {x: e[x] for x in ["citations"] + CHECK_FLAGS}
                            for l, e in sorted(by_ed.items(), key=lambda x: (-x[1]["citations"], _label_no(x[0])))},
        "list": rows,
        # each cited work with an identifier (ISBN, DOI or web address), so the same work can be
        # followed across articles
        "items": [{"id": it["id"], "source": it["source"], "citations": it["citations"],
                   "flags": sorted(it["flags"]), **({"language_as_cited": it["language"]} if it["language"] else {}),
                   "added_by": dict(sorted(it["editors"].items(), key=lambda x: (-x[1], _label_no(x[0]))))}
                  for it in sorted(items.values(), key=lambda x: x["id"])],
    }
    return block, extra, by_key


def _label_no(label: str) -> int:
    try:
        return int(label.split()[-1])
    except ValueError:
        return 10 ** 9
