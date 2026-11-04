"""Editors across articles.

Three levels:
1. Article overlap (public): how much of one article's text is by editors who also wrote in
   another. Describes articles, not people.
2. Sanctioned editors across articles (public): Wikipedia has already ruled on them.
3. Substantial contributors across articles (public, with friction): every editor with at least
   MIN_SHARE of the text in at least MIN_ARTICLES analysed articles, under a pattern ID.

Friction for level 3, stated openly on the page because it is not real anonymity:
- pattern IDs are a keyed hash of the account, with a secret key kept only locally
  (.wtl-secret), so they cannot be reversed by trying account numbers;
- no links, and no connection to the per-article "Editor N" labels;
- shares are shown as ranges, not exact figures.
The same rule applies to every editor. No pattern is labelled or interpreted.
"""

import hashlib
import hmac
import secrets

from . import pipeline
from .config import ROOT
from .fetch import cache

SECRET_FILE = ROOT / ".wtl-secret"
MIN_SHARE = 0.01
MIN_ARTICLES = 2
BUCKETS = [0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.0001]


def _secret() -> bytes:
    import os
    env = os.environ.get("WTL_SECRET", "").strip()
    if env:   # cloud runs: the same key, stored as an encrypted repository secret
        return bytes.fromhex(env)
    if not SECRET_FILE.exists():
        SECRET_FILE.write_text(secrets.token_hex(32) + "\n", encoding="utf-8")
        SECRET_FILE.chmod(0o600)
    return bytes.fromhex(SECRET_FILE.read_text(encoding="utf-8").strip())


def pattern_id(key: str, secret: bytes) -> str:
    d = hmac.new(secret, key.encode("utf-8"), hashlib.sha256).digest()
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    n = int.from_bytes(d[:5], "big")
    return "".join(alphabet[(n >> (5 * i)) & 31] for i in range(6))


def share_range(s: float) -> str:
    if s < BUCKETS[0]:
        return "under 1%"
    for lo, hi in zip(BUCKETS, BUCKETS[1:]):
        if s < hi:
            return f"{lo * 100:.0f}–{min(hi, 1) * 100:.0f}%"
    return "90–100%"


def editor_shares(rec: dict, area: str) -> dict:
    """{account key: {words, share, sanctioned, types}} for one stored record. Account keys never
    leave this machine; they are cached under cache/ (git-ignored)."""
    p = cache.path("patterns", str(rec["revision"]))
    hit = cache.load(p)
    if hit is None:
        _, intr = pipeline.analyse(revid=rec["revision"], area=area, internals=True)
        by_label = {v: k for k, v in intr["labels"].items()}
        hit = {by_label[e["label"]]: {"words": e["words"], "share": e["share"],
                                      "sanctioned": e["sanctioned"],
                                      "types": sorted({s["type"] for s in e["sanctions"]})}
               for e in rec["authorship"]["editors"]}
        cache.save(p, hit)
    return hit


EDIT_CAP = 10000


def editor_sources(rec: dict, area: str) -> dict:
    """{account key: {source key: citations}} for one stored record (cached, never published)."""
    if not (rec.get("sources") or {}).get("list"):
        return {}   # record predates source data (run `wtl reanalyse`); don't cache an empty map
    p = cache.path("patterns", "sources", str(rec["revision"]))
    hit = cache.load(p)
    if hit is None:
        _, intr = pipeline.analyse(revid=rec["revision"], area=area, internals=True)
        by_label = {v: k for k, v in {**intr["labels"], **intr.get("source_labels", {})}.items()}
        hit = {}
        for x in (rec.get("sources") or {}).get("list", []):
            for lbl, n in x["added_by"].items():
                k = by_label.get(lbl)
                if k:
                    hit.setdefault(k, {})[x["source"]] = n
        cache.save(p, hit)
    return hit


def citations_range(n: int) -> str:
    for lo, hi in ((1, 10), (10, 50), (50, 100), (100, 500), (500, 1000)):
        if n < hi:
            return f"{lo}–{hi - 1}"
    return "1,000 or more"


def source_profile(cites: dict, outlets: dict) -> dict:
    """Across-article profile of the sources one editor cited, coarsened like the rest of the
    page: counts as ranges, shares as ranges, medians to one decimal place."""
    from collections import Counter
    tot = sum(cites.values())
    rating, q, a, align, kinds = Counter(), [], [], Counter(), Counter()
    for k, n in cites.items():
        o = outlets.get(k) or {}
        wr = o.get("wikipedia_rating")
        rating[wr["status"] if wr else "not listed"] += n
        if o.get("independent_quality"):
            q += [o["independent_quality"]["score"]] * n
        if o.get("audience_leaning"):
            a += [o["audience_leaning"]["score"]] * n
        for x in o.get("political_alignment") or ["none recorded"]:
            align[x] += n
        kinds[o.get("kind") or "not classified"] += n

    def med(v):
        v = sorted(v)
        m = len(v) // 2
        return round((v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2), 1) if v else None
    named = [(k, n) for k, n in cites.items()
             if (outlets.get(k) or {}).get("wikidata") or (outlets.get(k) or {}).get("wikipedia_rating")]
    top = sorted(named, key=lambda x: (-x[1], x[0]))[:5]
    return {
        "citations": citations_range(tot),
        "wikipedia_rating": {k: share_range(v / tot) for k, v in rating.most_common()},
        "independent_quality_median": med(q),
        "independent_quality_coverage": share_range(len(q) / tot),
        "audience_leaning_median": med(a),
        "audience_leaning_coverage": share_range(len(a) / tot),
        "alignment": {k: share_range(v / tot) for k, v in align.most_common() if v / tot >= MIN_SHARE},
        "kinds": {k: share_range(v / tot) for k, v in kinds.most_common() if v / tot >= MIN_SHARE},
        "most_cited": {(outlets.get(k) or {}).get("name") or k: share_range(n / tot) for k, n in top},
    }


def _topic_counts(articles: list[str], buckets: dict) -> dict:
    """{group label: [articles of this editor in it, articles in the group]}; groups too small
    to show are left out."""
    out = {}
    for a in articles:
        b = buckets.get(a)
        if b:
            out.setdefault(b[0], [0, b[1]])[0] += 1
    return dict(sorted(out.items(), key=lambda x: (-x[1][0], x[0])))


def area_map() -> dict[str, set]:
    """Article -> political contentious areas, from the talk-page tags gathered by
    `wtl candidates`. Empty if that has not been run."""
    from . import candidates as cd
    p = cache.path("candidates", "areas_v2")
    hit = cache.load(p)
    if hit is not None:
        return {k: set(v) for k, v in hit.items()}
    talk = {}
    for cat in (cd.CT_CATEGORY, cd.ECR_CATEGORY, cd.GS_TEMPLATE, cd.AI_CATEGORY):
        got = cache.load(cache.path("candidates", "talk", cd.re.sub(r"\W+", "_", cat)[:80]))
        if got is None:
            return {}
        for t, w in got.items():
            talk[t] = talk.get(t, "") + "\n" + w + (
                "\n{{ArbCom Arab-Israeli enforcement}}" if cat == cd.AI_CATEGORY else "")
    out = {t[len("Talk:"):]: sorted(cd.codes_in(w)) for t, w in talk.items()}
    out = {k: v for k, v in out.items() if v}
    cache.save(p, out)
    return {k: set(v) for k, v in out.items()}


def recent_article_edits(uid: str) -> list[str]:
    """Titles of the account's most recent EDIT_CAP article (namespace 0) edits. Cached per
    account and month; never published."""
    import datetime as dt
    from .fetch.mediawiki import api
    p = cache.path("patterns", "contribs", f"{uid}_{dt.date.today().strftime('%Y-%m')}")  # monthly snapshot
    hit = cache.load(p)
    if hit is not None:
        return hit
    titles, cont = [], {}
    while len(titles) < EDIT_CAP:
        d = api({"action": "query", "list": "usercontribs", "ucuserids": uid, "ucnamespace": "0",
                 "uclimit": "500", "ucprop": "title", **cont})
        titles += [c["title"] for c in d.get("query", {}).get("usercontribs", [])]
        if "continue" not in d:
            break
        cont = d["continue"]
    titles = titles[:EDIT_CAP]
    cache.save(p, titles)
    return titles


def edit_spread(titles: list[str], amap: dict) -> dict:
    """Share of the edits that fall in each political area (an edit can count in two areas when
    an article is tagged with both), plus edits outside all of them."""
    from collections import Counter
    c = Counter()
    for t in titles:
        ars = amap.get(t)
        if ars:
            for a in ars:
                c[a] += 1
        else:
            c["outside"] += 1
    n = len(titles)
    return {k: v / n for k, v in c.most_common()} if n else {}


def edits_range(n: int) -> str:
    for hi in (100, 500, 1000, 5000, EDIT_CAP):
        if n < hi:
            lo = {100: 1, 500: 100, 1000: 500, 5000: 1000, EDIT_CAP: 5000}[hi]
            return f"{lo:,}–{hi:,}"
    return f"{EDIT_CAP:,} or more (most recent {EDIT_CAP:,} counted)"


MIN_BUCKET = 5


def topic_buckets(arts: list[str], areas: dict, kinds: dict) -> dict:
    """Article -> topic group label (area and kind), such that every group holds at least
    MIN_BUCKET analysed articles, so a group never stands in for a single article. Small groups
    merge into their area, then into "other analysed articles"; groups still too small are
    dropped (article -> None)."""
    from collections import Counter
    from .candidates import AREAS, KIND_NAMES
    b = {a: (areas.get(a) or "", kinds.get(a) or "") for a in arts}
    for coarsen in (lambda x: (x[0], ""), lambda x: ("", "")):
        size = Counter(b.values())
        b = {a: (x if size[x] >= MIN_BUCKET else coarsen(x)) for a, x in b.items()}
    size = Counter(b.values())

    def label(x):
        area, kind = x
        if not area:
            return "Other analysed articles"
        name = AREAS.get(area, (area,))[0]
        return f"{name}: {KIND_NAMES[kind].lower()}" if kind else f"{name}: other analysed articles"
    return {a: (label(x), size[x]) if size[x] >= MIN_BUCKET else None for a, x in b.items()}


def compute(recs: list[dict], groups: dict, areas: dict, elsewhere: bool = False,
            kinds: dict | None = None, outlets: dict | None = None) -> dict:
    secret = _secret()
    arts = [r["article"] for r in recs]
    per = {r["article"]: editor_shares(r, areas.get(r["article"], "")) for r in recs}
    cites = {}
    if outlets:
        for r in recs:
            for k, d in editor_sources(r, areas.get(r["article"], "")).items():
                c = cites.setdefault(k, {})
                for src, n in d.items():
                    c[src] = c.get(src, 0) + n

    # level 1: overlap between articles
    overlap = {a: {b: round(sum(v["share"] for k, v in per[a].items() if k in per[b]), 6)
                   for b in arts if b != a} for a in arts}

    # levels 2 and 3: one row per editor that qualifies
    buckets = topic_buckets(arts, areas, kinds or {})
    keys = set().union(*per.values()) if per else set()
    rows = []
    for k in keys:
        present = {a: per[a][k] for a in arts if k in per[a]}
        sanctioned = any(v["sanctioned"] for v in present.values())
        substantial = [a for a, v in present.items() if v["share"] >= MIN_SHARE]
        # Sanctioned editors (level 2) show when they wrote in more than one analysed article or
        # a substantial share of one; everyone else (level 3) needs a substantial share in at
        # least MIN_ARTICLES articles.
        if sanctioned:
            if len(present) < 2 and not substantial:
                continue
        elif len(substantial) < MIN_ARTICLES:
            continue
        shown = {a: v for a, v in present.items() if v["share"] >= MIN_SHARE or sanctioned}
        rows.append({
            "id": pattern_id(k, secret),
            "sanctioned": sanctioned,
            "types": sorted({t for v in present.values() for t in v["types"]}),
            "articles_with_text": len(present),
            "articles_substantial": len(substantial),
            # Sanctioned editors (Wikipedia's own findings) are shown by article. Everyone else
            # is shown only by topic group, so the row cannot be matched to an article page.
            "shares": {a: share_range(v["share"]) for a, v in sorted(
                shown.items(), key=lambda x: -x[1]["share"])} if sanctioned else {},
            "topics": {} if sanctioned else _topic_counts(substantial, buckets),
            "groups": sorted({groups.get(a, "") for a in substantial}),
            "sources": source_profile(cites[k], outlets) if cites.get(k) else None,
            "_key": k,
            "_order": (-len(substantial), -sum(v["share"] for v in present.values())),
        })
    rows.sort(key=lambda r: (r["_order"], r["id"]))
    amap = area_map() if elsewhere else {}
    for r in rows:
        k = r.pop("_key")
        del r["_order"]
        if amap and k.startswith("u"):
            titles = recent_article_edits(k[1:])
            spread = edit_spread(titles, amap)
            r["elsewhere"] = {"edits": edits_range(len(titles)),
                              "areas": {a: share_range(v) for a, v in spread.items()
                                        if v >= MIN_SHARE}}
    return {"overlap": overlap, "editors": rows,
            "rule": {"min_share": MIN_SHARE, "min_articles": MIN_ARTICLES, "edit_cap": EDIT_CAP,
                     "min_group": MIN_BUCKET,
                     "elsewhere": bool(amap),
                     "articles_analysed": len(arts)}}
