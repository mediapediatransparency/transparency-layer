"""Every change to an article's short description ({{Short description|...}}: the line Wikipedia
shows under the title in its search box and apps), up to the analysed revision.

Method, by fixed rules:
- The page history from 1 January 2017 (cached revision IDs) is checked at up to 128 evenly
  spaced revisions, always including the first of that period and the analysed one; a short
  description already there at the first is reported as present on that date. Only the opening section's wikitext is read
  (the template sits there), 50 revisions per request.
- Also checked: every edit whose summary mentions the short description, and every edit
  Wikipedia tagged as later reverted (summaries are read only to choose these and are not kept).
- Wherever two neighbouring checkpoints differ, the revisions between them are checked the same
  way, narrowing down until the exact edit is found: the revision whose short description differs
  from its predecessor's.
- Limits: a change undone before the next checkpoint (for example vandalism and its repair) can
  be missed when both checkpoints show the same text; the gap between checkpoints is stated with
  the result. A revision whose text Wikipedia has hidden is skipped. A maintenance tag inside the
  description (such as {{Disputed inline}}) is shown by name. Until about 2018 most short
  descriptions came from Wikidata rather than the article; those are not in the article's
  history and are not tracked here.
`wtl shortdesc` writes data/shortdesc.json. No usernames are stored.
"""

import datetime as dt
import json
import re

from .config import ROOT
from .fetch import cache
from .fetch import mediawiki as mw
from .then_now import short_description

START = "2017-01-01"     # the article-side template came into use around 2018; Wikidata before


def _clean(v: str | None) -> str | None:
    """A maintenance tag left inside the description ("... {{Disputed inline") is named, not shown
    as text."""
    if v and "{{" in v:
        text, tag = v.split("{{", 1)
        name = tag.split("|")[0].strip().lower()
        return f"{text.strip()} [tagged: {name}]"
    return v

SHORTDESC_JSON = ROOT / "data" / "shortdesc.json"
CHECKPOINTS = 128
BATCH = 50
HIDDEN = "\x00hidden"


def _fetch(revids: list[int]) -> dict[int, str | None]:
    """Short description at each revision (None when absent), opening section only; cached."""
    out, todo = {}, []
    for r in revids:
        hit = cache.load(cache.path("shortdesc", str(r)))
        if hit is not None:
            out[r] = hit["sd"] if hit["sd"] == HIDDEN else _clean(hit["sd"])
        else:
            todo.append(r)
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        data = mw.api({"action": "query", "prop": "revisions", "revids": "|".join(map(str, chunk)),
                       "rvprop": "ids|content", "rvslots": "main", "rvsection": "0"})
        got = {}
        for pg in data["query"].get("pages", []):
            for rv in pg.get("revisions", []):
                main = (rv.get("slots") or {}).get("main") or {}
                got[rv["revid"]] = (HIDDEN if rv.get("texthidden") or "content" not in main
                                    else _clean(short_description(main["content"])))
        for r in chunk:
            v = got.get(r, HIDDEN)
            cache.save(cache.path("shortdesc", str(r)), {"sd": v})
            out[r] = v
    return out


HINT = re.compile(r"short[ _-]?desc|\bSD\b|shortdesc", re.I)


def _hints(pageid: int, start: str, upto: int) -> set[int]:
    """Revisions worth checking besides the evenly spaced ones: an edit summary that mentions the
    short description, or an edit Wikipedia tagged as later reverted (the edit after it is added
    by the caller). Summaries are read only to choose checkpoints; they are not kept."""
    p = cache.path("shortdesc_hints", f"{pageid}_{upto}")
    hit = cache.load(p)
    if hit is not None:
        return set(hit)
    params = {"action": "query", "prop": "revisions", "pageids": str(pageid), "rvprop": "ids|comment|tags",
              "rvlimit": "max", "rvdir": "newer", "rvstart": f"{start}T00:00:00Z", "rvendid": str(upto)}
    out = set()
    while True:
        data = mw.api(params)
        for r in data["query"]["pages"][0].get("revisions", []):
            if HINT.search(r.get("comment") or "") or "mw-reverted" in (r.get("tags") or []):
                out.add(r["revid"])
        if not data.get("continue"):
            break
        params.update(data["continue"])
    cache.save(p, sorted(out))
    return out


def _spread(lo: int, hi: int, n: int) -> list[int]:
    """Up to n indices strictly between lo and hi, evenly spaced."""
    span = hi - lo - 1
    if span <= n:
        return list(range(lo + 1, hi))
    return sorted({lo + 1 + round(k * (span - 1) / (n - 1)) for k in range(n)})


def changes(pageid: int, upto: int) -> dict:
    hist = [h for h in mw.get_history(pageid, upto) if h["timestamp"][:10] >= START]
    revs = [h["revid"] for h in hist]
    if not revs:
        return {"changes": [], "checkpoints": 0}
    sd: dict[int, str | None] = {}

    def val(i):
        return sd[revs[i]]

    def load(idx):
        need = [revs[i] for i in idx if revs[i] not in sd]
        if need:
            sd.update(_fetch(need))

    def known(i, step):   # nearest revision whose text is not hidden
        while 0 <= i < len(revs) and val(i) == HIDDEN:
            i += step
            if 0 <= i < len(revs):
                load([i])
        return i

    top = [0] + _spread(0, len(revs) - 1, CHECKPOINTS - 2) + [len(revs) - 1] if len(revs) > 1 else [0]
    pos = {r: i for i, r in enumerate(revs)}
    for r in _hints(pageid, START, upto):
        if r in pos:
            top.append(pos[r])     # a change there differs from its neighbours; narrowing finds both ends
    top = sorted(set(top))
    load(top)
    found = []

    def narrow(lo, hi):
        while hi - lo > 1:
            mid = _spread(lo, hi, BATCH - 1)
            load(mid)
            seq = [lo] + [i for i in mid if val(i) != HIDDEN] + [hi]
            diff = [(a, b) for a, b in zip(seq, seq[1:]) if val(a) != val(b)]
            if not diff:
                return
            if len(diff) > 1:
                for a, b in diff:
                    narrow(a, b)
                return
            lo, hi = diff[0]
        found.append(hi)

    seq = [i for i in top if val(i) != HIDDEN]
    for a, b in zip(seq, seq[1:]):
        if val(a) != val(b):
            narrow(a, b)
    out = []
    if val(0) not in (None, HIDDEN):
        out.append({"revision": revs[0], "parent": None, "timestamp": hist[0]["timestamp"],
                    "from": None, "to": val(0), "present_at_start": True})
    for i in sorted(set(found)):
        p = known(i - 1, -1)
        out.append({"revision": revs[i], "parent": revs[p] if p >= 0 else None,
                    "timestamp": hist[i]["timestamp"], "from": val(p) if p >= 0 else None, "to": val(i)})
    gap = round(len(revs) / max(1, min(len(top), CHECKPOINTS) - 1))
    return {"changes": out, "checkpoints": len(top), "edits": len(revs), "edits_between_checkpoints": gap,
            "first_revision_checked": revs[0]}


def build(records: list[dict], log=print, only: set | None = None) -> dict:
    old = json.loads(SHORTDESC_JSON.read_text(encoding="utf-8")) if SHORTDESC_JSON.exists() else {}
    arts = old.get("articles", {})
    for i, r in enumerate(records):
        if only and r["article"] not in only:
            continue
        if (arts.get(r["article"]) or {}).get("revision") == r["revision"]:
            continue
        try:
            pageid = mw.get_revision(r["revision"])["pageid"]
            arts[r["article"]] = {"revision": r["revision"], **changes(pageid, r["revision"])}
        except Exception as ex:   # noqa: BLE001 - network: left for the next run
            log(f"  shortdesc: {r['article']}: {str(ex)[:100]}")
        if i % 25 == 0:
            log(f"  shortdesc: {i + 1:,} of {len(records):,}")
            _write(arts)
    return _write(arts)


def _write(arts):
    d = {"built": dt.date.today().isoformat(), "rule": __doc__.strip(), "articles": dict(sorted(arts.items()))}
    SHORTDESC_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    return d
