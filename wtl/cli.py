"""Command line: python -m wtl <command>.

  analyze TITLE [--revid N] [--area A-I]   one article -> out/<article>/<revid>.json + .html
  testset [--refresh]                      every article in data/articles.csv, then summary
  render                                   rebuild HTML and summary from the stored JSON
  verify-sanctions                         check every seed-list row against its link
  check                                    totals, anonymity and reproducibility checks
  spotcheck [--n 20] [--seed 1]            sentence-level authorship hand-check helper
  site                                     build the public website in site/ from the stored JSON
  activity                                  how often each analysed article changes -> data/activity.json
  stale                                     edits since each analysed revision -> data/stale.json
  refresh [--n N]                           re-analyse articles with >= 20 edits since, or 90 days old
  candidates [--per-kind 25] [--subjects SOC,ISL] choose articles by rule -> data/candidates.csv
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


def _save_entry(key, entry):
    """Write one test-set entry, re-reading the file first so that two commands writing it
    (a batch and a refresh) do not undo each other's entries."""
    entries = load_testset()
    entries[key] = entry
    tmp = TESTSET.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(TESTSET)


REFRESH_EDITS = 20     # re-analyse after this many edits since the analysed revision
REFRESH_DAYS = 90      # or when the analysis is this old, whichever comes first


def cmd_refresh(a):
    """Re-analyse articles that meet the refresh rule (data/stale.json from `wtl stale`): at least
    REFRESH_EDITS edits since the analysed revision, or an analysis REFRESH_DAYS days old."""
    import datetime as dt
    from . import activity
    if not activity.STALE_JSON.exists():
        sys.exit("run `wtl stale` first")
    stale = json.loads(activity.STALE_JSON.read_text(encoding="utf-8"))["articles"]
    today = dt.date.today()
    due = []
    for key, e in load_testset().items():
        st = stale.get(e["article"]) or {}
        p = OUT_DIR / json_writer.slug(e["article"]) / f"{e['revision']}.json"
        computed = json.loads(p.read_text(encoding="utf-8")).get("computed", "") if p.exists() else ""
        age = (today - dt.date.fromisoformat(computed)).days if computed else 0
        edits = st.get("edits_since", 0) if st.get("analysed_revision") == e["revision"] else 0
        if edits >= REFRESH_EDITS or age >= REFRESH_DAYS:
            due.append((key, e, edits, age))
    due.sort(key=lambda x: (-x[2], -x[3]))
    print(f"{len(due)} articles due (>= {REFRESH_EDITS} edits since analysis, or >= {REFRESH_DAYS} days old)"
          + (f"; doing {a.n}" if a.n and a.n < len(due) else ""))
    for i, (key, e, edits, age) in enumerate(due[:a.n or None], 1):
        print(f"[{i}] {e['article']}: {edits} edits since, analysis {age} days old", file=sys.stderr)
        try:
            rec = pipeline.analyse(e["article"], None, area=e.get("topic_area") or "")
        except Exception as err:  # one bad page must not stop the run
            print(f"  skipped: {err}", file=sys.stderr)
            continue
        json_writer.write(rec)
        _save_entry(key, {**e, "revision": rec["revision"], "article": rec["article"]})
    cmd_render(a)


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
    d = site.build(recs, groups, areas, elsewhere=a.elsewhere_sample or a.elsewhere, kinds=kinds)
    print(f"built site in {d} ({len(recs)} article pages); open {d / 'index.html'}")


def cmd_candidates(a):
    from . import candidates as cd
    chosen, counts = cd.build(a.per_kind, a.subjects.split(",") if a.subjects else None)
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
        _save_entry(r["title"], entries[r["title"]])
    print(f"analysed {len(picked)}; {len(todo) - len(picked)} candidates left"
          + (f" in {a.area}" if a.area else ""))
    cmd_render(a)


def cmd_reanalyse(a):
    """Recompute every stored record at its pinned revision (cached data; few or no requests),
    so all records carry the current pipeline's fields."""
    entries = load_testset()
    if getattr(a, "missing", None):   # only records that lack a given top-level field
        def has(e):
            p = OUT_DIR / json_writer.slug(e["article"]) / f"{e['revision']}.json"
            try:
                return a.missing in json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return False
        entries = {t: e for t, e in entries.items() if not has(e)}
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


def cmd_books(a):
    """Look up every ISBN cited in the analysed articles on Open Library (data/books.json)."""
    from .fetch import mediawiki as mw
    from . import books, sources
    names, _ = sources.load_names()
    isbns = set()
    for e in load_testset().values():
        try:
            text = mw.get_revision(e["revision"])["content"]
        except Exception as ex:
            print(f"  skipped {e['article']}: {ex}", file=sys.stderr)
            continue
        for c in sources.find(text, names):
            i, _ = books.isbn_in(text[c["start"]:c["end"]])
            if i:
                isbns.add(i)
    books.build(isbns)


def cmd_siteprobe(a):
    """Read what cited websites say about themselves, in batches (data/siteprobe.json)."""
    from . import outlets, siteprobe
    recs, _ = stored_records()
    snap = json.loads(outlets.OUTLETS_JSON.read_text(encoding="utf-8")) if outlets.OUTLETS_JSON.exists() else {}
    if a.fill_rdap:
        print(f"  RDAP looked up again for {siteprobe.fill_rdap():,} sites")
    if a.summary_only or a.fill_rdap:
        s = siteprobe.write_summary()
        print(f"wrote {siteprobe.SITEPROBE_JSON}: {len(s['sites']):,} sites")
        return
    siteprobe.run(recs, snap.get("sources", {}), a.batch, retry=a.retry)


def cmd_sitetrace(a):
    """Fingerprints of cited websites that do not need the live site (data/sitetrace.json)."""
    from . import sitetrace
    recs, _ = stored_records()
    if a.summary_only or not a.part:
        s = sitetrace.write_summary(recs)
        print(f"wrote {sitetrace.SITETRACE_JSON}: {len(s['sites']):,} sites")
        return
    if a.part == "at-addition":
        n = sitetrace.titles_at_addition(sitetrace.load().get("sites", {}))
        print(f"  looked up {n} archived home pages")
        s = sitetrace.write_summary(recs)
        print(f"wrote {sitetrace.SITETRACE_JSON}: {len(s['sites']):,} sites")
        return
    sitetrace.run(recs, a.part, a.batch)


def cmd_activity(a):
    """How often each analysed article changes (data/activity.json), from cached histories."""
    from . import activity
    recs, _ = stored_records()
    d = activity.write(recs)
    print(f"wrote {activity.ACTIVITY_JSON}: {len(d['articles']):,} articles")


def cmd_stale(a):
    """Edits to each analysed article since its analysed revision (data/stale.json)."""
    from . import activity
    recs, _ = stored_records()
    d = activity.stale(recs)
    rows = sorted(d["articles"].items(), key=lambda x: -x[1]["edits_since"])
    print(f"wrote {activity.STALE_JSON}: {len(rows):,} articles; most edited since analysis:")
    for t, x in rows[:15]:
        print(f"  {x['edits_since']:5d} edits  {t}")


def cmd_wpdiscuss(a):
    """Wikipedia's noticeboard mentions and spam-blacklist entries for cited sources."""
    from collections import Counter
    from . import wpdiscuss
    from .sources import NOT_A_SOURCE
    recs, _ = stored_records()
    cites, names = Counter(), {}
    for r in recs:
        for x in (r.get("sources") or {}).get("list", []):
            if x["source"] in NOT_A_SOURCE:
                continue
            cites[x["source"]] += x["citations"]
            nm = x.get("name_as_cited") or x.get("publisher_name_from_isbn")
            if nm:
                names.setdefault(x["source"], Counter())[nm] += x["citations"]
    from . import outlets
    snap = json.loads(outlets.OUTLETS_JSON.read_text(encoding="utf-8")).get("sources", {}) \
        if outlets.OUTLETS_JSON.exists() else {}
    keys = {}
    for k, n in cites.items():
        if n < a.min_citations:
            continue
        nm = min(names[k], key=lambda s: (-names[k][s], s)) if k in names else None
        o = snap.get(k) or {}
        if not k.startswith("name:") and o.get("wikidata") and o.get("name") and o["name"] != k:
            nm = o["name"]          # the name Wikidata gives the site
        keys[k] = nm
    wpdiscuss.build(keys)


def cmd_reuse(a):
    """Count other English Wikipedia articles citing the same works (data/reuse.json)."""
    from . import outlets, reuse
    recs, _ = stored_records()
    snap = json.loads(outlets.OUTLETS_JSON.read_text(encoding="utf-8")) if outlets.OUTLETS_JSON.exists() else {}
    reuse.build(recs, snap.get("sources", {}))


def cmd_talk(a):
    """Talk-page decisions about each analysed article's text (data/talk.json)."""
    from . import talk
    recs, _ = stored_records()
    d = talk.build(recs)
    c = [x["counts"] for x in d["articles"].values()]
    print(f"wrote {talk.TALK_JSON}: {len(c):,} articles; {sum(x['rfcs'] for x in c):,} requests for "
          f"comment, {sum(x['moratorium_discussions'] for x in c):,} discussions about a moratorium")


def cmd_then_now(a):
    """The opening section on fixed dates, and its most-changed sentences (data/then_now.json)."""
    from . import then_now
    recs, _ = stored_records()
    d = then_now.build(recs)
    print(f"wrote {then_now.THEN_NOW_JSON}: {len(d['articles']):,} articles")


def cmd_shortdesc(a):
    """Every change to each article's short description (data/shortdesc.json)."""
    from . import shortdesc
    recs, _ = stored_records()
    d = shortdesc.build(recs, only=set(a.only.split("|")) if a.only else None)
    print(f"wrote {shortdesc.SHORTDESC_JSON} ({len(d['articles']):,} articles)")


def cmd_voice(a):
    """Wikipedia's voice check of every opening section (data/voice.json)."""
    from . import voice
    recs, _ = stored_records()
    d = voice.build(recs)
    print(f"wrote {voice.VOICE_JSON} ({len(d['articles']):,} articles)")


def cmd_policies(a):
    """Wikipedia's own standards, quoted with their versions (data/policies.json)."""
    from . import policies
    policies.build()


def cmd_labels(a):
    """Recorded labels of cited sources and authors, with Wikipedia's definitions (data/labels.json)."""
    from . import labels
    labels.build([])


def cmd_authors(a):
    """What Wikidata records about cited authors linked to Wikipedia (data/authors.json)."""
    from . import people
    recs, _ = stored_records()
    people.build(recs)


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
    from .fetch import dnsfallback
    dnsfallback.install()   # see wtl/fetch/dnsfallback.py
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
    p = sub.add_parser("reanalyse")
    p.add_argument("--missing", metavar="FIELD",
                   help="only records that lack this top-level field, e.g. --missing changes")
    p.set_defaults(fn=cmd_reanalyse)
    sub.add_parser("outlets").set_defaults(fn=cmd_outlets)
    sub.add_parser("talk").set_defaults(fn=cmd_talk)
    sub.add_parser("authors").set_defaults(fn=cmd_authors)
    sub.add_parser("labels").set_defaults(fn=cmd_labels)
    sub.add_parser("voice").set_defaults(fn=cmd_voice)
    sp = sub.add_parser("shortdesc", help="every change to each article's short description")
    sp.add_argument("--only", help="article titles separated by |")
    sp.set_defaults(fn=cmd_shortdesc)
    sub.add_parser("policies").set_defaults(fn=cmd_policies)
    sub.add_parser("then-now").set_defaults(fn=cmd_then_now)
    sub.add_parser("source-names").set_defaults(fn=cmd_source_names)
    sub.add_parser("books").set_defaults(fn=cmd_books)
    sub.add_parser("reuse").set_defaults(fn=cmd_reuse)
    p = sub.add_parser("wpdiscuss")
    p.add_argument("--min-citations", type=int, default=2)
    p.set_defaults(fn=cmd_wpdiscuss)
    p = sub.add_parser("siteprobe")
    p.add_argument("--batch", type=int, default=100, help="sites to probe in this run")
    p.add_argument("--summary-only", action="store_true", help="only rewrite data/siteprobe.json")
    p.add_argument("--retry", action="store_true",
                   help="also probe again sites marked for retry (archive unavailable)")
    p.add_argument("--fill-rdap", action="store_true",
                   help="look up domain registration again where none was recorded")
    p.set_defaults(fn=cmd_siteprobe)
    p = sub.add_parser("sitetrace")
    p.add_argument("--part", choices=["copies", "dns", "ct", "titles", "at-addition"],
                   help="saved copies of unreadable sites, DNS records, or certificate logs")
    p.add_argument("--batch", type=int, default=100, help="sites to do in this run")
    p.add_argument("--summary-only", action="store_true", help="only rewrite data/sitetrace.json")
    p.set_defaults(fn=cmd_sitetrace)
    p = sub.add_parser("activity")
    p.set_defaults(fn=cmd_activity)
    p = sub.add_parser("stale")
    p.set_defaults(fn=cmd_stale)
    p = sub.add_parser("refresh")
    p.add_argument("--n", type=int, default=0, help="at most this many articles (0 = all due)")
    p.set_defaults(fn=cmd_refresh)
    p = sub.add_parser("site")
    p.add_argument("--elsewhere", action="store_true",
                   help="also fetch each listed editor's recent edits across Wikipedia (slow)")
    p.add_argument("--elsewhere-sample", type=int, default=0, metavar="N",
                   help="fetch them only for the N editors with the most text in each area")
    p.set_defaults(fn=cmd_site)
    p = sub.add_parser("batch")
    p.add_argument("--n", type=int, default=25)
    p.add_argument("--area", help="only candidates from this area code")
    p.set_defaults(fn=cmd_batch)
    p = sub.add_parser("candidates")
    p.add_argument("--per-kind", type=int, default=25)
    p.add_argument("--subjects", help="only these subject areas, e.g. SOC,ISL (default: all)")
    p.set_defaults(fn=cmd_candidates)
    sub.add_parser("verify-sanctions").set_defaults(fn=lambda a: checks.verify_sanctions())
    sub.add_parser("check").set_defaults(fn=lambda a: checks.run_checks(load_testset()))
    p = sub.add_parser("spotcheck")
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--seed", type=int, default=1)
    p.set_defaults(fn=lambda a: checks.spotcheck(load_testset(), a.n, a.seed))
    a = ap.parse_args(argv)
    a.fn(a)
