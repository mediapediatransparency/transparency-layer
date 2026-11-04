"""Books cited by ISBN: what the ISBN itself says, and what Open Library records about the book.

Two outside inputs, both fixed in files and fingerprinted in every record:

- data/isbn_ranges.xml: the International ISBN Agency's range file. It splits an ISBN into its
  registration group (the national or language-area agency that issued it, e.g. "Israel",
  "German language") and the registrant (publisher) prefix. The group says where the publisher
  registered, not what language the book is in.
- data/books.json: for each ISBN cited in the analysed articles, Open Library's record of the
  book (publishers, places of publication, languages, date), or a note that Open Library has no
  record; and for each publisher prefix, the Wikidata item that records that prefix ("ISBN
  publisher prefix", P3035). Built by `wtl books`; Open Library and Wikidata data are CC0.

An ISBN whose check digit is wrong is recorded as invalid and not looked up.
"""

import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET

from .config import ROOT, user_agent

RANGES_XML = ROOT / "data" / "isbn_ranges.xml"
BOOKS_JSON = ROOT / "data" / "books.json"
RANGES_URL = "https://www.isbn-international.org/export_rangemessage.xml"
OL_API = "https://openlibrary.org/api/books"

ISBN_PARAM = re.compile(r"\|\s*isbn(?:13|10)?\s*=\s*([0-9Xx][0-9Xx\-‐-― ]{8,22})", re.I)
ISBN_TPL = re.compile(r"\{\{\s*ISBNT?\s*\|\s*([0-9Xx\-‐-― ]{10,22})", re.I)
ISBN_FREE = re.compile(r"\bISBN(?:-1[03])?[\s:]*((?:97[89][\-‐-― ]?)?[0-9][0-9\-‐-― ]{8,16}[0-9Xx])\b")

# Open Library language codes (MARC) to English names, for display; unknown codes are shown as is
LANG = {"eng": "English", "heb": "Hebrew", "ara": "Arabic", "per": "Persian", "tur": "Turkish",
        "rus": "Russian", "ukr": "Ukrainian", "pol": "Polish", "ger": "German", "fre": "French",
        "spa": "Spanish", "ita": "Italian", "por": "Portuguese", "dut": "Dutch", "swe": "Swedish",
        "nor": "Norwegian", "dan": "Danish", "fin": "Finnish", "hun": "Hungarian", "cze": "Czech",
        "slo": "Slovak", "rum": "Romanian", "bul": "Bulgarian", "srp": "Serbian", "hrv": "Croatian",
        "bos": "Bosnian", "slv": "Slovenian", "alb": "Albanian", "gre": "Greek", "arm": "Armenian",
        "geo": "Georgian", "aze": "Azerbaijani", "lit": "Lithuanian", "lav": "Latvian",
        "est": "Estonian", "bel": "Belarusian", "chi": "Chinese", "jpn": "Japanese", "kor": "Korean",
        "hin": "Hindi", "urd": "Urdu", "ben": "Bengali", "tam": "Tamil", "tel": "Telugu",
        "mar": "Marathi", "pan": "Punjabi", "guj": "Gujarati", "kan": "Kannada", "mal": "Malayalam",
        "nep": "Nepali", "sin": "Sinhala", "pus": "Pashto", "kur": "Kurdish", "yid": "Yiddish",
        "lat": "Latin", "mul": "several languages", "und": "undetermined", "ind": "Indonesian",
        "may": "Malay", "vie": "Vietnamese", "tha": "Thai", "tib": "Tibetan", "mon": "Mongolian",
        "kaz": "Kazakh", "uzb": "Uzbek", "tgk": "Tajik", "kir": "Kyrgyz", "tuk": "Turkmen"}


# ---------- ISBN arithmetic ----------

def _digits(raw: str) -> str:
    return re.sub(r"[^0-9Xx]", "", raw).upper()


def to13(raw: str) -> str | None:
    """The ISBN-13 of an ISBN as written, or None if it is not a valid ISBN (length or check
    digit)."""
    d = _digits(raw)
    if len(d) == 10:
        if not d[:9].isdigit() or not (d[9].isdigit() or d[9] == "X"):
            return None
        s = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(d))
        if s % 11:
            return None
        d = "978" + d[:9]
        return d + str((10 - sum((1, 3)[i % 2] * int(c) for i, c in enumerate(d)) % 10) % 10)
    if len(d) == 13 and d.isdigit() and d[:3] in ("978", "979"):
        if sum((1, 3)[i % 2] * int(c) for i, c in enumerate(d)) % 10:
            return None
        return d
    return None


def isbn_in(body: str) -> tuple[str | None, str | None]:
    """(ISBN-13, as written) for the first ISBN in a citation's wikitext; (None, raw) when one
    is written but invalid; (None, None) when there is none."""
    m = ISBN_PARAM.search(body) or ISBN_TPL.search(body) or ISBN_FREE.search(body)
    if not m:
        return None, None
    raw = m.group(1).strip()
    return to13(raw), raw


# ---------- registration groups ----------

_RANGES = None


def _load_ranges():
    global _RANGES
    if _RANGES is None:
        if not RANGES_XML.exists():
            _RANGES = ({}, None, None)
            return _RANGES
        raw = RANGES_XML.read_bytes()
        root = ET.fromstring(raw)
        groups = {}
        for g in root.iter("Group"):
            pre = g.findtext("Prefix")          # e.g. "978-965"
            rules = [(r.findtext("Range"), int(r.findtext("Length"))) for r in g.iter("Rule")]
            groups[pre.replace("-", "")] = (pre, g.findtext("Agency"), rules)
        _RANGES = (groups, hashlib.sha256(raw).hexdigest(), root.findtext("MessageDate"))
    return _RANGES


def split(isbn13: str) -> dict | None:
    """{"group": "978-965", "agency": "Israel", "registrant": "978-965-229"} or None."""
    groups, _, _ = _load_ranges()
    for n in range(4, 9):           # registration group prefixes are 1 to 5 digits after 978/979
        g = groups.get(isbn13[:n])
        if not g:
            continue
        pre, agency, rules = g
        rest = isbn13[n:]
        key = int(rest[:7].ljust(7, "0"))
        for rng, length in rules:
            lo, hi = (int(x) for x in rng.split("-"))
            if lo <= key <= hi:
                reg = rest[:length] if length else ""
                return {"group": pre, "agency": agency,
                        "registrant": f"{pre}-{reg}" if reg else None}
        return {"group": pre, "agency": agency, "registrant": None}
    return None


def hyphenated(isbn13: str) -> str:
    s = split(isbn13)
    if not s or not s["registrant"]:
        return isbn13
    head = s["registrant"]
    body = isbn13[len(head.replace("-", "")):]
    return f"{head}-{body[:-1]}-{body[-1]}"


# ---------- Open Library ----------

def _ol_batch(isbns: list[str]) -> dict:
    import requests
    keys = ",".join(f"ISBN:{i}" for i in isbns)
    for attempt in range(5):
        try:
            r = requests.get(OL_API, params={"bibkeys": keys, "format": "json", "jscmd": "details"},
                             headers={"User-Agent": user_agent()}, timeout=60)
            if r.status_code == 200:
                return r.json()
            print(f"  Open Library HTTP {r.status_code}; retrying", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  Open Library {type(e).__name__}; retrying", flush=True)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("Open Library did not answer")


def _ol_fields(d: dict) -> dict:
    x = d.get("details") or {}
    return {
        "title": x.get("title", ""),
        "publishers": x.get("publishers") or [],
        "places": x.get("publish_places") or [],
        "languages": [l["key"].rsplit("/", 1)[-1] for l in x.get("languages") or []],
        "date": x.get("publish_date", ""),
        "url": "https://openlibrary.org" + x["key"] if x.get("key") else d.get("info_url", ""),
    }


def prefix_publishers(prefixes: list[str]) -> dict:
    """Publisher prefix (e.g. "978-965-229") -> {"wikidata", "label"} for prefixes that a
    Wikidata item records as its ISBN publisher prefix (P3035), in either the 13- or the
    10-digit form. A prefix recorded on more than one item is left out."""
    import requests
    found = {}
    for k in range(0, len(prefixes), 150):
        chunk = prefixes[k:k + 150]
        forms = {}
        for p in chunk:
            forms[p] = p
            if p.startswith("978-"):
                forms[p[4:]] = p
        vals = " ".join(json.dumps(f) for f in forms)
        q = (f"SELECT ?x ?p ?pLabel WHERE {{ VALUES ?x {{ {vals} }} ?p wdt:P3035 ?x . "
             f"SERVICE wikibase:label {{ bd:serviceParam wikibase:language \"en,mul\". }} }}")
        for attempt in range(5):
            try:
                r = requests.post("https://query.wikidata.org/sparql", data={"query": q},
                                  headers={"User-Agent": user_agent(),
                                           "Accept": "application/sparql-results+json"}, timeout=120)
                if r.status_code == 200:
                    break
                print(f"  Wikidata query HTTP {r.status_code}; retrying", flush=True)
            except Exception as ex:  # noqa: BLE001
                print(f"  Wikidata query {type(ex).__name__}; retrying", flush=True)
            time.sleep(10 * (attempt + 1))
        else:
            raise RuntimeError("Wikidata query service did not answer")
        for b in r.json()["results"]["bindings"]:
            pre = forms[b["x"]["value"]]
            qid = b["p"]["value"].rsplit("/", 1)[1]
            found.setdefault(pre, {})[qid] = b["pLabel"]["value"]
        time.sleep(1)
    return {p: {"wikidata": next(iter(v)), "label": next(iter(v.values()))}
            for p, v in sorted(found.items()) if len(v) == 1}


def build(isbns: set[str]) -> dict:
    """Write data/books.json for the given ISBN-13s, reusing what it already holds."""
    if not RANGES_XML.exists():
        import requests
        RANGES_XML.write_bytes(requests.get(RANGES_URL, headers={"User-Agent": user_agent()}, timeout=60).content)
    old = json.loads(BOOKS_JSON.read_text(encoding="utf-8")) if BOOKS_JSON.exists() else {}
    have = old.get("books", {})
    todo = sorted(i for i in isbns if i not in have)
    print(f"  {len(isbns):,} ISBNs, {len(todo):,} to look up on Open Library", flush=True)
    for k in range(0, len(todo), 40):
        chunk = todo[k:k + 40]
        got = _ol_batch(chunk)
        for i in chunk:
            hit = got.get(f"ISBN:{i}")
            have[i] = _ol_fields(hit) if hit else None
        if (k // 40) % 10 == 0:
            print(f"  Open Library: {min(k + 40, len(todo)):,} of {len(todo):,}", flush=True)
        time.sleep(1)
    _, sha, date = _load_ranges()
    prefixes = sorted({s["registrant"] for i in isbns if (s := split(i)) and s["registrant"]})
    print(f"  {len(prefixes):,} publisher prefixes to look up on Wikidata", flush=True)
    pp = prefix_publishers(prefixes)
    out = {"source": "Open Library (openlibrary.org), CC0", "api": OL_API,
           "isbn_ranges": {"source": RANGES_URL, "message_date": date, "sha256": sha},
           "prefix_source": "Wikidata, ISBN publisher prefix (P3035), retrieved " +
                            time.strftime("%Y-%m-%d"),
           "books": dict(sorted(have.items())), "prefixes": pp}
    BOOKS_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=0, sort_keys=True) + "\n",
                          encoding="utf-8")
    found = sum(1 for v in have.values() if v)
    print(f"wrote {BOOKS_JSON}: {len(have):,} ISBNs, {found:,} found on Open Library; "
          f"{len(pp):,} of {len(prefixes):,} publisher prefixes on Wikidata", flush=True)
    return out


def load():
    """({"books": {isbn13: record or None}, "prefixes": {...}}, fingerprint) or ({}, None)."""
    if not BOOKS_JSON.exists():
        return {}, None
    raw = BOOKS_JSON.read_bytes()
    _, rsha, _ = _load_ranges()
    d = json.loads(raw)
    return ({"books": d["books"], "prefixes": d.get("prefixes", {})},
            hashlib.sha256(raw + (rsha or "").encode()).hexdigest())


def lang_name(code: str) -> str:
    return LANG.get(code, code)
