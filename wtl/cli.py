"""Command line: python -m wtl <command>.

  analyze TITLE [--revid N] [--area A-I]   one article -> out/<article>/<revid>.json + .html
  testset [--refresh]                      every article in data/articles.csv, then summary
  render                                   rebuild HTML and summary from the stored JSON
  verify-sanctions                         check every seed-list row against its link
  check                                    totals, anonymity and reproducibility checks
  spotcheck [--n 20] [--seed 1]            sentence-level authorship hand-check helper
  site                                     build the public website in site/ from the stored JSON
  candidates [--per-kind 25]               choose articles by rule -> data/candidates.csv
  batch [--n 25] [--area A-I]              analyse the next N candidates not yet done, then rebuild
"""

import argparse
import csv
import json
import sys

from . import checks, pipeline
from .config import ARTICLES_CSV, OUT_DIR
from .report import html, json_writer, summary

TESTSET = OUT_DIR / "testset.json"


def article_rows():
    with open(ARTICLES_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def area_for(title: str) -> str:
    for r in article_rows():
        if r["title"].lower() == title.lower():
            return r["topic_area"]
    return ""


def write_outputs(rec: dict, baseline=None) -> None:
    p = json_writer.write(rec)
    p.with_suffix(".html").write_text(
        html.render(rec, baseline, summary_href="../summary.html" if TESTSET.exists() else None),
        encoding="utf-8")
    print(f"wrote {p} and {p.with_suffix('.html').name}")


def cmd_analyze(a):
    area = a.area if a.area is not None else area_for(a.title)
    rec = pipeline.analyse(a.title, a.revid, area=area)
    if not a.area and not area:
        area = area_for(rec["article"])
        if area:
            rec = pipeline.analyse(revid=rec["revision"], area=area)
    write_outputs(rec)


def load_testset():
    if not TESTSET.exists():
        return {}
    return json.loads(TESTSET.read_text(encoding="utf-8"))


def cmd_testset(a):
    pinned = {} if a.refresh else load_testset()
    entries = dict(load_testset())   # keep batch-added articles; test-set rows are refreshed below
    for row in article_rows():
        t = row["title"]
        print(f"[{row['group']}] {t}", file=sys.stderr)
        revid = pinned.get(t, {}).get("revision")
        rec = pipeline.analyse(t, revid, area=row["topic_area"])
        json_writer.write(rec)
        entries[t] = {**entries.get(t, {}), "article": rec["article"], "revision": rec["revision"],
                      "group": row["group"], "topic_area": row["topic_area"]}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TESTSET.write_text(json.dumps(entries, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    cmd_render(a)


def stored_records():
    recs, groups = [], {}
    for t, e in load_testset().items():
        p = OUT_DIR / json_writer.slug(e["article"]) / f"{e['revision']}.json"
        rec = json.loads(p.read_text(encoding="utf-8"))
        rec["_href"] = f"{json_writer.slug(e['article'])}/{e['revision']}.html"
        recs.append(rec)
        groups[rec["article"]] = e["group"]
    return recs, groups


def cmd_render(a):
    recs, groups = stored_records()
    base = summary.baseline(recs, groups)
    for r in recs:
        clean = {k: v for k, v in r.items() if not k.startswith("_")}
        b = base if groups[r["article"]] == "topic" else summary.baseline(
            [x for x in recs if x["article"] != r["article"]], groups)
        p = OUT_DIR / json_writer.slug(r["article"]) / f"{r['revision']}.html"
        p.write_text(html.render(clean, b, summary_href="../summary.html"), encoding="utf-8")
    (OUT_DIR / "summary.html").write_text(summary.render(recs, groups), encoding="utf-8")
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary.summary_json(recs, groups), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print(f"rendered {len(recs)} reports and {OUT_DIR / 'summary.html'}")


def cmd_site(a):
    from . import site
    recs, groups = stored_records()
    areas = {e["article"]: e.get("topic_area") or "" for e in load_testset().values()}
    kinds = {e["article"]: e.get("kind") or "" for e in load_testset().values()}
    d = site.build(recs, groups, areas, elsewhere=a.elsewhere, kinds=kinds)
    print(f"built site in {d} ({len(recs)} article pages); open {d / 'index.html'}")


def cmd_candidates(a):
    from . import candidates as cd
    chosen, counts = cd.build(a.per_kind)
    for area, (name, _) in cd.AREAS.items():
        row = ", ".join(f"{cd.KIND_NAMES[k].split(',')[0].lower()} {counts.get((area, k), 0):,}"
                        for k in cd.KINDS)
        print(f"{area:4} {name}: {row}")
    print(f"wrote {cd.CANDIDATES_CSV} ({len(chosen):,} articles)")


def cmd_batch(a):
    """Next N rule-chosen candidates, interleaved so each batch spans every kind: area order,
    then rank, then kind. Results join out/testset.json, so the site and checks include them."""
    from . import candidates as cd
    with open(cd.CANDIDATES_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    area_order = {k: i for i, k in enumerate(cd.AREAS)}
    kind_order = {k: i for i, k in enumerate(cd.KINDS)}
    rows.sort(key=lambda r: (area_order.get(r["area"], 99), r["reason"] != "requested",
                             int(r["rank"] or 0), kind_order.get(r["kind"], 9)))
    entries = load_testset()
    done = {e["article"] for e in entries.values()} | set(entries)
    todo = [r for r in rows if r["title"] not in done and (not a.area or r["area"] == a.area)]
    picked = []
    for r in todo:
        if len(picked) >= a.n:
            break
        if any(p["title"] == r["title"] for p in picked):
            continue
        picked.append(r)
    for i, r in enumerate(picked, 1):
        print(f"[{i}/{len(picked)}] {r['area']} {r['kind']} {r['title']}", file=sys.stderr)
        try:
            rec = pipeline.analyse(r["title"], None, area=r["area"])
        except Exception as e:   # one bad page must not stop the batch
            print(f"  skipped: {e}", file=sys.stderr)
            continue
        json_writer.write(rec)
        entries[r["title"]] = {"article": rec["article"], "revision": rec["revision"],
                               "group": "topic" if r["area"] == "A-I" else r["area"],
                               "topic_area": r["area"], "kind": r["kind"], "reason": r["reason"]}
        TESTSET.write_text(json.dumps(entries, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"analysed {len(picked)}; {len(todo) - len(picked)} candidates left"
          + (f" in {a.area}" if a.area else ""))
    cmd_render(a)


def cmd_reanalyse(a):
    """Recompute every stored record at its pinned revision (cached data; few or no requests),
    so all records carry the current pipeline's fields."""
    entries = load_testset()
    for i, (t, e) in enumerate(entries.items(), 1):
        print(f"[{i}/{len(entries)}] {t}", file=sys.stderr)
        try:
            rec = pipeline.analyse(revid=e["revision"], area=e.get("topic_area") or "")
        except Exception as ex:   # keep going; the old record stays in place
            print(f"  skipped: {ex}", file=sys.stderr)
            continue
        json_writer.write(rec)
    cmd_render(a)


def cmd_source_names(a):
    """Rebuild data/source_names.json from the citation templates of every analysed article."""
    from .config import ROOT
    from .fetch import mediawiki as mw
    from . import sources
    entries = load_testset()
    texts = []
    for e in entries.values():
        try:
            texts.append(mw.get_revision(e["revision"])["content"])
        except Exception as ex:
            print(f"  skipped {e['article']}: {ex}", file=sys.stderr)
    names = sources.build_names(texts)
    p = ROOT / "data" / "source_names.json"
    p.write_text(json.dumps(names, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {p}: {len(names['periodicals']):,} publications, {len(names['publishers']):,} "
          f"publishers, {len(names['domains']):,} linked to a website, from {names['articles']:,} articles")


def cmd_outlets(a):
    from . import outlets
    recs, _ = stored_records()
    snap = outlets.build(recs)
    s = snap["sources"].values()
    print(f"wrote {outlets.OUTLETS_JSON}: {len(snap['sources']):,} sources; "
          f"{sum(1 for x in s if x['wikipedia_rating']):,} on Wikipedia's list, "
          f"{sum(1 for x in s if x['independent_quality']):,} with an independent quality score, "
          f"{sum(1 for x in s if x['audience_leaning']):,} with an audience score, "
          f"{sum(1 for x in s if x['wikidata']):,} matched on Wikidata")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="wtl", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("analyze")
    p.add_argument("title")
    p.add_argument("--revid", type=int)
    p.add_argument("--area", help="topic area code (A-I, EE, SA); default from data/articles.csv")
    p.set_defaults(fn=cmd_analyze)
    p = sub.add_parser("testset")
    p.add_argument("--refresh", action="store_true", help="re-pin every article to its latest revision")
    p.set_defaults(fn=cmd_testset)
    sub.add_parser("render").set_defaults(fn=cmd_render)
    sub.add_parser("reanalyse").set_defaults(fn=cmd_reanalyse)
    sub.add_parser("outlets").set_defaults(fn=cmd_outlets)
    sub.add_parser("source-names").set_defaults(fn=cmd_source_names)
    p = sub.add_parser("site")
    p.add_argument("--elsewhere", action="store_true",
                   help="also fetch each listed editor's recent edits across Wikipedia (slow)")
    p.set_defaults(fn=cmd_site)
    p = sub.add_parser("batch")
    p.add_argument("--n", type=int, default=25)
    p.add_argument("--area", help="only candidates from this area code")
    p.set_defaults(fn=cmd_batch)
    p = sub.add_parser("candidates")
    p.add_argument("--per-kind", type=int, default=25)
    p.set_defaults(fn=cmd_candidates)
    sub.add_parser("verify-sanctions").set_defaults(fn=lambda a: checks.verify_sanctions())
    sub.add_parser("check").set_defaults(fn=lambda a: checks.run_checks(load_testset()))
    p = sub.add_parser("spotcheck")
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--seed", type=int, default=1)
    p.set_defaults(fn=lambda a: checks.spotcheck(load_testset(), a.n, a.seed))
    a = ap.parse_args(argv)
    a.fn(a)
