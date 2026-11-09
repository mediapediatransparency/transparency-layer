"""The article's cited authors next to the scholarly field on its topic (pilot; not on the site).

The field: the 2,000 most-cited works in OpenAlex (the open catalogue of scholarly works) whose
title or abstract contains the topic's search words. What the field relies on: the works those
2,000 cite (their reference lists), counted once per citing work.

1. Coverage: of the 50 works the field cites most, how many have an author the article cites;
   and, for each author the article cites most, their rank among the authors the field cites.
2. Clusters: works the field cites at least MIN_COCITED times are linked when the same field work
   cites both (co-citation), with the number of such works as the link's weight. Groups are found
   by the Louvain method with a fixed seed, so a run is repeatable. Groups come from citation
   patterns alone; no label or side is given to any group. Each author is placed in the group
   holding most of their field citations. The article's cited authors are then counted by group,
   next to the field's own share of citations in each group.

Authors are matched by surname and first initial, within the field only. Nothing is fetched
about Wikipedia editors.
"""

import json
import re
import unicodedata
from collections import Counter, defaultdict

from .fetch import cache
from .fetch.http import get_json

OA = "https://api.openalex.org/works"
N_FIELD, MIN_COCITED, TOP_REFS = 2000, 3, 3000


def _get(params: dict, key: str) -> dict:
    p = cache.path("field", key)
    hit = cache.load(p)
    if hit is not None:
        return hit
    d = get_json(OA, params)
    cache.save(p, d)
    return d


def corpus(search: str, tag: str, log=print) -> list[dict]:
    out = []
    for page in range(1, N_FIELD // 100 + 1):
        d = _get({"filter": f"title_and_abstract.search:{search}", "sort": "cited_by_count:desc",
                  "per_page": "100", "page": str(page),
                  "select": "id,display_name,publication_year,cited_by_count,authorships,referenced_works,type"},
                 f"{tag}_corpus_{page}")
        out += d.get("results", [])
        if len(d.get("results", [])) < 100:
            break
    log(f"  field {tag}: {len(out):,} works (of {d.get('meta', {}).get('count', 0):,} matching)")
    return out


def works_meta(ids: list[str], tag: str) -> dict:
    out = {}
    for i in range(0, len(ids), 50):
        part = ids[i:i + 50]
        d = _get({"filter": "openalex_id:" + "|".join(x.rsplit("/", 1)[-1] for x in part), "per_page": "50",
                  "select": "id,display_name,publication_year,authorships,type"}, f"{tag}_refs_{i}")
        for w in d.get("results", []):
            out[w["id"]] = w
    return out


def name_key(name: str) -> str:
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)|[^a-z\s-]", " ", n)
    parts = [p for p in n.replace("-", " ").split() if p]
    if not parts:
        return ""
    return f"{parts[-1]} {parts[0][0]}"


def _authors(w: dict) -> list[str]:
    return [a["author"]["display_name"] for a in (w.get("authorships") or []) if a.get("author", {}).get("display_name")]


def analyse(search: str, tag: str, article_authors: list[tuple[str, int]], log=print) -> dict:
    import networkx as nx
    works = corpus(search, tag, log)
    ref_n = Counter(r for w in works for r in set(w.get("referenced_works") or []))
    top = [r for r, _ in ref_n.most_common(TOP_REFS)]
    meta = works_meta(top, tag)
    log(f"  field {tag}: {len(ref_n):,} distinct works cited by the field; metadata for {len(meta):,}")
    # authors the field cites, weighted by field citations to their works
    au_cit, au_name, au_works = Counter(), {}, defaultdict(set)
    for r in top:
        for a in _authors(meta.get(r, {})):
            k = name_key(a)
            au_cit[k] += ref_n[r]
            au_name.setdefault(k, a)
            au_works[k].add(r)
    rank = {k: i + 1 for i, (k, _) in enumerate(sorted(au_cit.items(), key=lambda x: (-x[1], x[0])))}
    # co-citation graph
    keep = {r for r in top if ref_n[r] >= MIN_COCITED}
    g = nx.Graph()
    for w in works:
        rs = sorted(set(w.get("referenced_works") or []) & keep)
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                a, b = rs[i], rs[j]
                g.add_edge(a, b, weight=g[a][b]["weight"] + 1 if g.has_edge(a, b) else 1)
    comms = nx.community.louvain_communities(g, weight="weight", seed=1, resolution=1.0) if g.number_of_edges() else []
    comms = sorted(comms, key=lambda c: (-sum(ref_n[r] for r in c), min(c)))
    group_of = {r: i for i, c in enumerate(comms) for r in c}
    field_share = Counter()
    for r in keep:
        if r in group_of:
            field_share[group_of[r]] += ref_n[r]
    au_group = {}
    for k, ws in au_works.items():
        c = Counter()
        for r in ws:
            if r in group_of:
                c[group_of[r]] += ref_n[r]
        if c:   # the group with most of the author's field citations; a tie goes to the larger group
            au_group[k] = min(c, key=lambda g: (-c[g], g))
    # the article's authors
    art = []
    for name, n in article_authors:
        k = name_key(name)
        art.append({"author": name, "weight": n, "field_rank": rank.get(k), "group": au_group.get(k),
                    "field_citations": au_cit.get(k, 0)})
    art_group = Counter()
    for a in art:
        if a["group"] is not None:
            art_group[a["group"]] += a["weight"]
    tot_f, tot_a = sum(field_share.values()) or 1, sum(art_group.values()) or 1
    groups = []
    for i, c in enumerate(comms):
        if field_share[i] / tot_f < 0.02 and not art_group[i]:
            continue
        lead = Counter()
        for r in sorted(c):
            for a in _authors(meta.get(r, {})):
                lead[name_key(a)] += ref_n[r]
        groups.append({"group": i + 1, "field_share": round(field_share[i] / tot_f, 3),
                       "article_share": round(art_group[i] / tot_a, 3),
                       "works": len(c),
                       "most_cited_authors": [au_name[k] for k, _ in sorted(lead.items(), key=lambda x: (-x[1], x[0]))[:8]],
                       "most_cited_works": [f"{(_authors(meta[r]) or ['?'])[0]} ({meta[r].get('publication_year')}): "
                                            f"{meta[r].get('display_name')}" for r in
                                            sorted(c, key=lambda r: (-ref_n[r], r))[:4] if r in meta]})
    art_keys = {name_key(n) for n, _ in article_authors}
    top50 = [r for r in top[:50]]
    covered = [r for r in top50 if any(name_key(a) in art_keys for a in _authors(meta.get(r, {})))]
    missing = [r for r in top50 if r not in covered]
    matched_w = sum(a["weight"] for a in art if a["field_rank"])
    return {"search": search, "field_works": len(works), "cited_by_field": len(ref_n), "_group_of": group_of,
            "groups": groups,
            "top50_with_an_author_the_article_cites": len(covered),
            "top50_missing": [f"{(_authors(meta[r]) or ['?'])[0]} ({meta[r].get('publication_year')}): "
                              f"{meta[r].get('display_name')} — cited by {ref_n[r]} field works"
                              for r in missing if r in meta][:20],
            "article_author_weight_found_in_field": round(matched_w / max(1, sum(a["weight"] for a in art)), 3),
            "article_authors": art}


def run(title: str, search: str, tag: str, log=print) -> dict:
    import glob
    from . import narrative
    from .config import ROOT
    rec = json.loads(open(sorted(glob.glob(str(ROOT / "out" / title.replace(" ", "_") / "*.json")))[-1]).read())
    u = narrative.usage(rec, top=200)
    authors = [(a["author"], a["sentences"]) for a in u["authors"]]
    return analyse(search, tag, authors, log)


# ---------------------------------------------------------------- one author's works, placed by who cites them
def _norm_title(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", "", t).strip()[:30]


def _citing_group(refs, group_of) -> int | None:
    c = Counter(group_of[r] for r in refs or [] if r in group_of)
    return min(c, key=lambda g: (-c[g], g)) if c else None


def author_works(name: str, cited_titles: list[str], group_of: dict, tag: str, top: int = 10,
                 pages: int = 5) -> dict:
    """The author's most-cited works in OpenAlex, each placed by the field groups of the works that
    cite it: a citing work counts for the group it cites most. The OpenAlex author record is
    accepted only if one of its works has a title matching a work the article cites (the first
    30 letters, ignoring case and punctuation); otherwise nothing is returned."""
    want = {_norm_title(t) for t in cited_titles if t}
    d = get_json("https://api.openalex.org/authors", {"search": name, "per_page": "5",
                                                       "select": "id,display_name,works_count,cited_by_count"})
    for a in d.get("results", []):
        aid = a["id"].rsplit("/", 1)[-1]
        ws = _get({"filter": f"author.id:{aid}", "sort": "cited_by_count:desc", "per_page": "100",
                   "select": "id,display_name,publication_year,cited_by_count,type"}, f"{tag}_author_{aid}")
        works = ws.get("results", [])
        confirm = [w["display_name"] for w in works if _norm_title(w["display_name"]) in want]
        if not confirm:
            continue
        rows = []
        for w in works[:top]:
            wid = w["id"].rsplit("/", 1)[-1]
            groups, n = Counter(), 0
            for p in range(1, pages + 1):
                c = _get({"filter": f"cites:{wid}", "per_page": "100", "page": str(p),
                          "select": "id,referenced_works"}, f"{tag}_cites_{wid}_{p}")
                for cw in c.get("results", []):
                    n += 1
                    g = _citing_group(cw.get("referenced_works"), group_of)
                    if g is not None:
                        groups[g] += 1
                if len(c.get("results", [])) < 100:
                    break
            placed = sum(groups.values())
            rows.append({"title": w["display_name"], "year": w.get("publication_year"),
                         "cited_by": w.get("cited_by_count"), "citing_works_read": n, "placed": placed,
                         "cited_in_article": _norm_title(w["display_name"]) in want,
                         "groups": {g + 1: round(k / placed, 3) for g, k in groups.most_common()} if placed else {}})
        return {"author": a["display_name"], "openalex": a["id"], "confirmed_by": confirm[:3], "works": rows}
    return {"author": name, "openalex": None, "works": []}


KEEP_TYPES = {"book", "article", "book-chapter", "review", "preprint", "report", "dissertation"}


def _confirmed_author(name: str, cited_titles: list[str], tag: str):
    """(OpenAlex author id, that author's works) when one of the works matches a cited title."""
    want = {main_title(t) for t in cited_titles if t}
    p = cache.path("field", f"authors_search_{_norm_title(name).replace(' ', '_')}")
    d = cache.load(p)
    if d is None:
        d = get_json("https://api.openalex.org/authors", {"search": name, "per_page": "5", "select": "id,display_name"})
        cache.save(p, d)
    for a in d.get("results", []):
        aid = a["id"].rsplit("/", 1)[-1]
        works = []
        for page in (1, 2, 3):
            ws = _get({"filter": f"author.id:{aid}", "sort": "publication_year:desc", "per_page": "100",
                       "page": str(page), "select": "id,display_name,publication_year,cited_by_count,type,primary_topic"},
                      f"works_by_{aid}" + ("" if page == 1 else f"_{page}"))
            works += ws.get("results", [])
            if len(ws.get("results", [])) < 100:
                break
        if any(main_title(w["display_name"]) in want for w in works):
            return a, works
    return None, []


STOP_T = set("a an the of and in on for to from with by at its his her their as or is are was were "
             "history study new essays toward towards".split())


def main_title(t: str) -> str:
    """The title before any subtitle, lower case, letters and digits only."""
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    t = re.split(r"[:.?]\s", t + " ", maxsplit=1)[0]
    return re.sub(r"[^a-z0-9 ]", "", t).strip()


def title_words(t: str) -> set[str]:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return {w for w in re.findall(r"[a-z]{3,}", t) if w not in STOP_T}


def newer_works(name: str, cited: list[tuple[str, int]], tag: str = "") -> dict:
    """For each cited (title, year) by this author: later editions of the same title (the first 30
    letters match) and later works whose main OpenAlex topic is the cited work's main topic."""
    a, works = _confirmed_author(name, [t for t, _ in cited], tag)
    if not a:
        return {"author": name, "openalex": None, "cited": []}
    by_title = defaultdict(list)
    for w in works:
        by_title[main_title(w["display_name"])].append(w)
    rows = []
    for title, year in cited:
        k = main_title(title)
        me = by_title.get(k, [])
        tw = title_words(title)
        topic = next(((w.get("primary_topic") or {}).get("id") for w in me if w.get("primary_topic")), None)
        y = year or min((w.get("publication_year") or 9999 for w in me), default=None)
        ed, same = [], []
        for w in works:
            wy = w.get("publication_year")
            if not y or not wy or wy <= y or w.get("type") not in KEEP_TYPES or w.get("type") == "review":
                continue
            if main_title(w["display_name"]) == k:
                ed.append(w)
            else:
                ww = title_words(w["display_name"])
                shared = tw & ww
                if len(shared) >= 2 and 2 * len(shared) / (len(tw) + len(ww)) >= 0.3:
                    same.append(w)
        rows.append({"title": title, "year": y, "found_in_catalogue": bool(me),
                     "topic": next(((w.get("primary_topic") or {}).get("display_name") for w in me if w.get("primary_topic")), None),
                     "later_editions": sorted({(w["display_name"], w["publication_year"]) for w in ed}, key=lambda x: x[1]),
                     "later_same_subject": sorted({(w["display_name"], w["publication_year"], w.get("cited_by_count")) for w in same},
                                                key=lambda x: -x[1])[:6]})
    return {"author": a["display_name"], "openalex": a["id"], "cited": rows}
