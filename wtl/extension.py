"""Data for the browser add-on (extension/): one compact entry per analysed article.

The add-on carries this file inside it and never asks a server about the page being read.
Every figure here is also on the article's page on the site, defined the same way; nothing about
a single editor is included (editors appear only as counts and shares of the text).
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import ROOT

EXT_DIR = ROOT / "extension"
MIN_COVER = 0.25   # a source dial's needle is drawn only when this share of citations is rated
ACADEMIC_KINDS = {"academic journal", "university press", "university or research institute"}
FLAGS = ("dead_link_no_archive", "not_english_no_quote", "book_without_page",
         "paywall_or_registration", "opinion", "not_english", "no_link")


def _median(v):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def article_figures(rec: dict, ctx) -> dict:
    """The add-on's figures for one article (numbers only; the add-on words them)."""
    from .site import cited_figures
    a = rec["authorship"]
    s = rec.get("sources") or {}
    n = s.get("citations") or 0
    c = cited_figures(rec, ctx)
    w = ((ctx.patterns or {}).get("by_article", {}).get(rec["article"]) or {}).get("writers") or {}
    acad = sum(x["citations"] for x in s.get("list", [])
               if (ctx.outlets.get(x["source"]) or {}).get("kind") in ACADEMIC_KINDS)
    from .outlets import is_scholarly
    books = sum(x["citations"] for x in s.get("list", [])
                if x["source"] == "book (no publisher given)"
                or is_scholarly(x["source"], ctx.outlets.get(x["source"]) or {}))
    fl = s.get("flags") or {}
    return {
        "top1": a["top_shares"].get("1"), "top5": a["top_shares"].get("5"),
        "editors": a.get("editor_count"), "for50": a.get("editors_for_50pct"),
        "sanctioned": a.get("sanctioned_share"),
        "citations": n, "sources": s.get("distinct_sources"),
        "with_link": (s.get("with_link") or 0) / n if n else None,
        "academic": acad / n if n else None,
        "flags": {k: fl.get(k, 0) for k in FLAGS},
        "books": books / n if n else None,
        "lean_c": c.get("audience_leaning_dd"), "lean_w": w.get("audience_leaning_dd"),
        "rob_c": c.get("audience_leaning"), "rob_w": w.get("audience_leaning"),
        "qual_c": c.get("independent_quality"), "acad_c": c.get("academic_level"),
        "mbfc_c": c.get("mbfc"), "mbfc_w": w.get("mbfc"),
        "as_c": c.get("allsides_2018"), "as_w": w.get("allsides_2018"),
        "wp": c.get("wikipedia_rating"),
        "aff_c": c.get("affiliation"), "aff_w": w.get("affiliation"),
    }


def build(ctx) -> dict:
    from .site import area_name, kind_name, slug
    figs = {r["article"]: article_figures(r, ctx) for r in ctx.recs}

    def typical(rec, get):
        peers = ctx.peers(rec)
        from .site import MIN_PEERS
        if len(peers) < MIN_PEERS:
            peers = ctx.peers(rec, same_area=False)
        if len(peers) < MIN_PEERS:
            return None, 0
        return _median(get(figs[p["article"]]) for p in peers), len(peers)

    from .site import baseline_leaning
    bl = baseline_leaning(ctx)
    getters = {
        "top5": lambda f: f["top5"],
        "lean_c": lambda f: (f["lean_c"] or {}).get("mean") if (f["lean_c"] or {}).get("citations_covered", 0) >= MIN_COVER else None,
        "qual_c": lambda f: (f["qual_c"] or {}).get("mean") if (f["qual_c"] or {}).get("citations_covered", 0) >= MIN_COVER else None,
        "acad_c": lambda f: (f["acad_c"] or {}).get("mean") if (f["acad_c"] or {}).get("citations_covered", 0) >= MIN_COVER else None,
        "academic": lambda f: f["academic"], "with_link": lambda f: f["with_link"],
    }
    arts = {}
    for r in ctx.recs:
        t = r["article"]
        f = figs[t]
        typ, n_peers = {}, 0
        for k, g in getters.items():
            typ[k], n_peers = typical(r, g)
        group = (f"{kind_name(ctx.kinds.get(t) or '', plural=True).lower()}"
                 + (f" in {area_name(ctx.areas.get(t))}" if ctx.areas.get(t) else ""))
        arts[t] = {"slug": slug(t), "rev": r["revision"], "at": r.get("revision_timestamp", "")[:10],
                   "computed": r.get("computed"), "area": area_name(ctx.areas.get(t) or ""),
                   "kind": kind_name(ctx.kinds.get(t) or "", plural=False),
                   "caveats": sorted({c["code"] for c in r.get("caveats") or []}),
                   "f": f, "typical": typ, "peers": n_peers, "group": group}
    from .patterns import LEAN_LABELS
    return {"built": max((r.get("computed") or "") for r in ctx.recs),
            "min_cover": MIN_COVER, "min_scored": (ctx.patterns or {}).get("rule", {}).get("min_scored"),
            "baseline_lean": bl.get("audience_leaning_dd"), "baseline_rob": bl.get("audience_leaning"),
            "labels": {k: list(v) for k, v in LEAN_LABELS.items()},
            "articles": arts}


def _round(x, nd=3):
    if isinstance(x, float):
        return round(x, nd)
    if isinstance(x, dict):
        return {k: _round(v, nd) for k, v in x.items()}
    if isinstance(x, list):
        return [_round(v, nd) for v in x]
    return x


def write(ctx, site_dir: Path) -> None:
    """data/extension.json on the site, and extension/data.js inside the add-on. A local copy
    of the site is linked through extension/local.js (git-ignored), never through data.js."""
    d = _round(build(ctx))
    body = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    (site_dir / "data" / "extension.json").write_text(body, encoding="utf-8")
    if EXT_DIR.exists():
        (EXT_DIR / "data.js").write_text("self.WTL_DATA=" + body + ";\n", encoding="utf-8")
        (EXT_DIR / "local.js").write_text(
            "self.WTL_SITE=" + json.dumps((ROOT / "site").as_uri() + "/") + ";\n", encoding="utf-8")
