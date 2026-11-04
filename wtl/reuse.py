"""Other uses of the same work across English Wikipedia.

For cited works that are harder to check or come from sources no assessor rates, how many
English Wikipedia articles (main namespace) cite the same work:

- a web page: Wikipedia's record of external links (list=exturlusage), for the address with and
  without "www.", over http and https. Counts up to CAP.
- a book: a full-text search for its ISBN written four ways (ISBN-13 and ISBN-10, each with and
  without the standard hyphens). An ISBN hyphenated another way is missed, so the count is a
  lower bound.

Works chosen (see `wanted`): web pages and books whose source no assessor rates, or that are
flagged as opinion or not in English; and every book whose ISBN was issued outside the
English-language groups. Results go to data/reuse.json with the date checked; each lookup is
cached.
"""

import datetime as dt
import hashlib
import json

from . import books as bk
from .config import ROOT
from .fetch import cache
from .fetch.mediawiki import api

REUSE_JSON = ROOT / "data" / "reuse.json"
CAP = 500
TITLES_KEPT = 25
RATED = ("wikipedia_rating", "independent_quality", "audience_leaning", "allsides_2018", "mbfc",
         "academic_level")
FLAGS = {"opinion", "not_english"}


def wanted(records: list[dict], outlets: dict) -> list[str]:
    """Works to look up, highest priority first: books with ISBNs issued outside the
    English-language groups, then works flagged opinion or not in English, then works from
    unrated sources, most-cited source first."""
    from collections import Counter
    ids, prio, src_cites = set(), {}, Counter()
    for r in records:
        for x in (r.get("sources") or {}).get("list", []):
            src_cites[x["source"]] += x["citations"]
    for r in records:
        for it in (r.get("sources") or {}).get("items", []):
            kind = it["id"].split(":", 1)[0]
            if kind not in ("url", "isbn"):
                continue
            o = outlets.get(it["source"]) or {}
            unrated = not any(o.get(x) for x in RATED)
            flagged = bool(FLAGS & set(it.get("flags", [])))
            foreign = False
            if kind == "isbn":
                sp = bk.split(it["id"][5:])
                foreign = bool(sp and sp["agency"] not in ("English language", "United States"))
            if unrated or flagged or foreign:
                ids.add(it["id"])
                p = (0 if foreign else 1 if flagged else 2, -src_cites[it["source"]])
                prio[it["id"]] = min(prio.get(it["id"], p), p)
    return sorted(ids, key=lambda i: (prio[i], i))


def _isbn10(isbn13: str) -> str | None:
    if not isbn13.startswith("978"):
        return None
    core = isbn13[3:12]
    s = sum((10 - i) * int(c) for i, c in enumerate(core)) % 11
    return core + ("X" if (11 - s) % 11 == 10 else str((11 - s) % 11))


def _hy10(isbn13: str, isbn10: str) -> str | None:
    h = bk.hyphenated(isbn13)
    if h == isbn13 or not h.startswith("978-"):
        return None
    parts = h[4:].split("-")
    return "-".join(parts[:-1] + [isbn10[-1]])


def isbn_forms(isbn13: str) -> list[str]:
    i10 = _isbn10(isbn13)
    forms = [isbn13, bk.hyphenated(isbn13)]
    if i10:
        forms += [i10, _hy10(isbn13, i10)]
    return sorted({f for f in forms if f})


def lookup(iid: str) -> dict:
    p = cache.path("reuse", hashlib.sha1(iid.encode()).hexdigest())
    hit = cache.load(p)
    if hit is not None:
        return hit
    kind, _, v = iid.partition(":")
    titles = set()
    if kind == "url":
        bare = v[4:] if v.startswith("www.") else v
        for q in (bare, "www." + bare):
            d = api({"action": "query", "list": "exturlusage", "euquery": q, "euprotocol": "",
                     "eunamespace": "0", "eulimit": str(CAP), "euprop": "title"})
            titles |= {x["title"] for x in d["query"]["exturlusage"]}
        method = "external links"
    else:
        q = " OR ".join(f'"{f}"' for f in isbn_forms(v))
        d = api({"action": "query", "list": "search", "srsearch": q, "srnamespace": "0",
                 "srlimit": str(CAP), "srinfo": "totalhits", "srprop": ""})
        titles = {x["title"] for x in d["query"]["search"]}
        method = "ISBN search"
    out = {"articles": len(titles), "capped": len(titles) >= CAP, "method": method,
           "titles": sorted(titles)[:TITLES_KEPT], "checked": dt.date.today().isoformat()}
    cache.save(p, out)
    return out


def build(records: list[dict], outlets: dict, limit: int = 3000) -> dict:
    """Look up at most `limit` works not yet cached (highest priority first), then write every
    work looked up so far. Run again to continue."""
    ids = wanted(records, outlets)
    cached = [i for i in ids if cache.load(cache.path("reuse", hashlib.sha1(i.encode()).hexdigest())) is not None]
    todo = [i for i in ids if i not in set(cached)][:limit]
    print(f"  {len(ids):,} works wanted; {len(cached):,} already looked up; {len(todo):,} this run",
          flush=True)
    ids = cached + todo
    works = {}
    for i, iid in enumerate(ids, 1):
        try:
            works[iid] = lookup(iid)
        except Exception as ex:  # noqa: BLE001  keep going; the work is left out this run
            print(f"  {iid[:80]}: {str(ex)[:100]}", flush=True)
        if i % 500 == 0:
            print(f"  {i:,} of {len(ids):,}", flush=True)
    out = {"built": dt.date.today().isoformat(), "rule": __doc__.strip(),
           "works": dict(sorted(works.items()))}
    REUSE_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=0, sort_keys=True) + "\n",
                          encoding="utf-8")
    print(f"wrote {REUSE_JSON}: {len(works):,} works", flush=True)
    return out


def load() -> dict:
    if not REUSE_JSON.exists():
        return {}
    return json.loads(REUSE_JSON.read_text(encoding="utf-8")).get("works", {})
