"""The site's reader pages: Sources, Leaning, Editors, All articles and Which articles.

Each opens with a few figures and charts that give a feel for the whole set of analysed articles,
grouped by topic area, then points to the detailed page (the full tables and method notes, kept
whole at *-detail.html). Same figures as the detailed pages, drawn; no new measures and no
interpretation. Built from the records and data files the rest of the site uses.
"""

from collections import Counter, defaultdict
from html import escape

from . import story as st

# source kinds, folded into four families for charts (the detailed page keeps every kind)
FAMILIES = [
    ("news", "News: papers, broadcasters, magazines, agencies",
     {"newspaper or news website", "broadcaster", "magazine", "news agency", "news media"}),
    ("academic", "Books and scholarship: publishers, journals, universities",
     {"book publisher", "university press", "academic journal", "university or research institute"}),
    ("public", "Governments, NGOs and non-profits", {"government body", "NGO or non-profit"}),
    ("other", "Other websites, companies and people", None),
]
FAM_CATS = [(k, n, st.CAT[i]) for i, (k, n, _) in enumerate(FAMILIES)] + [("unknown", "Not identified", st.REST)]
RATING_CATS = [("gr", "Generally reliable", st.RAMP[0]), ("nc", "No consensus, or varies", st.RAMP[1]),
               ("gu", "Generally unreliable", st.RAMP[2]), ("d", "Deprecated or blacklisted", st.RAMP[3]),
               ("none", "Not on Wikipedia's list", st.REST)]


def _timing_lines(t) -> str:
    tot = sum(t.values())
    if not tot:
        return "<p class='q'>No text by sanctioned editors in the analysed articles.</p>"
    rows = [("before", "added before the sanction"), ("during", "added while the sanction was in force"),
            ("after", "added after the sanction ended")]
    return ("<ul class='q' style='margin:0 0 12px;padding-left:18px'>" + "".join(
        f"<li><b>{t[k]:,}</b> words ({100 * t[k] / tot:.1f}%) {d}</li>" for k, d in rows) + "</ul>")


def _family(kind):
    if not kind:
        return "unknown"
    for k, _, members in FAMILIES:
        if members is None or kind in members:
            return k
    return "other"


def _rating(o):
    s = ((o or {}).get("wikipedia_rating") or {}).get("status")
    return {"gr": "gr", "nc": "nc", "m": "nc", "gu": "gu", "d": "d", "b": "d"}.get(s, "none")


MIN_AREA = 5   # areas with fewer analysed articles are counted in "All areas" but get no row of their own


def _by_area(ctx, min_n=MIN_AREA):
    from .site import _area_order
    groups = defaultdict(list)
    for r in ctx.recs:
        groups[ctx.areas.get(r["article"], "") or ""].append(r)
    return [(a, groups[a]) for a in _area_order(ctx) if len(groups.get(a, ())) >= min_n]


def _all_recs(ctx):
    return ctx.recs


def _merge_by_name(counter, name_of):
    """Sources counted under several web addresses but with one name (bbc.com, bbc.co.uk) as one."""
    out, keys = Counter(), {}
    for k, v in counter.items():
        n = name_of(k)
        out[n] += v
        keys.setdefault(n, k)
    return out, keys


def _area_label(a, recs):
    """(short area name, small line under it): the bracketed part of a long name goes underneath."""
    from .site import area_name
    n = area_name(a)
    count = f"{len(recs):,} article{'s' if len(recs) != 1 else ''}"
    if "(" in n:
        main, rest = n.split("(", 1)
        rest = rest.rstrip(")").strip()
        rest = rest.replace("Wikipedia's topic; ", "").replace("includes ", "incl. ")
        return main.strip(), f"{count} · {rest[:38]}{'…' if len(rest) > 38 else ''}"
    return n, count


# ------------------------------------------------------------------ sources
def sources_overview(ctx) -> str:
    from .site import NAME, RATING_NAMES, page, src_name
    outl = ctx.outlets or {}
    cites = Counter()            # source -> citations, all articles
    arts = Counter()             # source -> articles citing it
    art_sets = defaultdict(set)
    flags = Counter()
    from .sources import NOT_A_SOURCE
    tot = linked = 0
    area_rows_fam, area_rows_rate, area_rows_link = [], [], []
    shown = {a for a, _ in _by_area(ctx)}
    allfam_small, allrate_small = Counter(), Counter()
    for a, recs in _by_area(ctx, min_n=1):
        fam, rate = Counter(), Counter()
        n_c = n_link = 0
        for r in recs:
            s = r.get("sources") or {}
            n_c += s.get("citations", 0)
            n_link += s.get("with_link", 0)
            for f, v in (s.get("flags") or {}).items():
                flags[f] += v
            for x in s.get("list", []):
                c = x["citations"]
                o = outl.get(x["source"])
                cites[x["source"]] += c
                arts[x["source"]] += 1
                art_sets[x["source"]].add(r["article"])
                fam[_family((o or {}).get("kind"))] += c
                rate[_rating(o)] += c
        tot += n_c
        linked += n_link
        if a not in shown:
            allfam_small.update(fam)
            allrate_small.update(rate)
            continue
        lab, sub = _area_label(a, recs)
        area_rows_fam.append((lab, sub, fam))
        area_rows_rate.append((lab, sub, rate))
        area_rows_link.append((lab, n_link / n_c if n_c else 0, n_c, sub))
    allfam, allrate = Counter(allfam_small), Counter(allrate_small)
    for _, _, f in area_rows_fam:
        allfam.update(f)
    for _, _, f in area_rows_rate:
        allrate.update(f)
    on_list = sum(v for k, v in allrate.items() if k != "none")
    acad = allfam.get("academic", 0)

    body = [st.hero("What the articles rest on", "The sources behind the analysed articles",
                    "Every footnote in the analysed articles, matched to the newspaper, publisher, journal or "
                    "organisation it points to, with what Wikipedia's own list and outside raters say about "
                    "each. We add no rating of our own."),
            st.stats([(f"{tot:,}", "citations read", None),
                      (f"{len(cites):,}", "different sources cited", None),
                      (st.pct(acad / tot if tot else 0), "of citations go to books and scholarship",
                       "Book publishers, university presses, academic journals and universities."),
                      (st.pct(on_list / tot if tot else 0), "go to sources on Wikipedia's own reliability list",
                       "Wikipedia's list of perennial sources: generally reliable, no consensus, generally "
                       "unreliable, deprecated or blacklisted."),
                      (st.pct(linked / tot if tot else 0), "have a link a reader can follow", None)]),
            st.toc([("kinds", "What kinds of sources"), ("ratings", "How Wikipedia rates them"),
                    ("most", "Most-cited sources"), ("check", "Can a reader check them?"),
                    ("differ", "Where raters differ")])]

    body.append(st.section(
        "kinds", "What kinds of sources",
        "The mix of news, scholarship, official and other sources each topic area cites, as a share of its "
        "citations. Point at a bar for its figure.",
        st.card("All analysed articles", st.stacks([("All areas", f"{tot:,} citations", allfam)], FAM_CATS))
        + "<div style='height:16px'></div>"
        + st.card("By topic area", st.stacks(area_rows_fam, FAM_CATS, show_legend=False),
                  note="“Not identified”: footnotes whose source could not be matched to a known publisher, "
                       f"outlet or organisation. Areas with fewer than {MIN_AREA} analysed articles are counted in "
                       "“All analysed articles” only.")))

    body.append(st.section(
        "ratings", "How Wikipedia rates them",
        "Wikipedia keeps its own list of frequently discussed sources and how far editors trust each. "
        "Here is how each area's citations fall on that list. Most sources are not on it at all.",
        st.card("By topic area", st.stacks([("All areas", f"{tot:,} citations", allrate)] + area_rows_rate,
                                           RATING_CATS),
                note="The ratings are today's, applied to every citation. “No consensus, or varies” includes "
                     "sources rated differently by period or topic.")))

    named, key_of = _merge_by_name(Counter({k: v for k, v in cites.items() if k not in NOT_A_SOURCE}),
                                   lambda k: src_name(k, ctx))
    by_name = defaultdict(set)
    for k, v in art_sets.items():
        if k not in NOT_A_SOURCE:
            by_name[src_name(k, ctx)] |= v
    n_arts = Counter({n: len(v) for n, v in by_name.items()})
    top = [(key_of[n], c) for n, c in named.most_common(20)]
    arts = Counter({key_of[n]: v for n, v in n_arts.items()})
    rows = []
    for k, c in top:
        o = outl.get(k) or {}
        r = _rating(o)
        sub = (f"cited in {arts[k]:,} article{'s' if arts[k] != 1 else ''} · "
               f"{escape((o.get('kind') or 'kind not identified'))} · Wikipedia: "
               f"{escape(dict((a, b) for a, b, _ in RATING_CATS)[r].lower())}")
        rows.append((escape(src_name(k, ctx)), c, f"{src_name(k, ctx)}: {c:,} citations in {arts[k]:,} articles", sub))
    body.append(st.section(
        "most", "Most-cited sources",
        "The twenty sources cited most often across all analysed articles.",
        st.card("By number of citations", st.hbars(rows))))

    flag_names = [("no_link", "No link to follow"), ("paywall_or_registration", "Behind a paywall or registration"),
                  ("not_english", "Not in English"), ("not_english_no_quote", "Not in English, with no quotation"),
                  ("book_without_page", "Book cited without a page number"), ("opinion", "Opinion pieces"),
                  ("dead_link_no_archive", "Dead link with no archived copy")]
    frows = [(escape(n), flags.get(k, 0) / tot if tot else 0,
              f"{n}: {flags.get(k, 0):,} of {tot:,} citations", "") for k, n in flag_names if flags.get(k)]
    lrows = sorted(area_rows_link, key=lambda x: x[1])
    body.append(st.section(
        "check", "Can a reader check them?",
        "Some footnotes are harder to check than others: no link, a paywall, another language, a book with no "
        "page. These are not faults; they are what a reader would meet.",
        st.grid(st.card("All analysed articles", st.hbars(frows, fmt=lambda v: st.pct(v, 1), top=1),
                        q="Share of all citations"),
                st.card("Share of citations with a link, by area",
                        st.hbars([(escape(l), v, f"{l}: {st.pct(v)} of {n:,} citations have a link", "")
                                  for l, v, n, _ in lrows], fmt=lambda v: st.pct(v), top=1, colour="var(--g-o3)")))))

    hi, lo, seen = [], [], set()
    for k, c in cites.most_common():
        if src_name(k, ctx) in seen:
            continue
        seen.add(src_name(k, ctx))
        o = outl.get(k) or {}
        q = (o.get("independent_quality") or {}).get("score")
        r = _rating(o)
        if q is None or r == "none":
            continue
        if r == "gr" and q < 0.6 and len(hi) < 8:
            hi.append((k, c, q, r))
        if r in ("gu", "d") and q >= 0.6 and len(lo) < 8:
            lo.append((k, c, q, r))

    def dlist(xs):
        if not xs:
            return "<p class='note'>None among the cited sources.</p>"
        return st.hbars([(escape(src_name(k, ctx)), q, f"{src_name(k, ctx)}: independent quality {q:.2f}; "
                          f"Wikipedia: {RATING_NAMES.get((outl.get(k) or {}).get('wikipedia_rating', {}).get('status'))}; "
                          f"{c:,} citations", f"{c:,} citations") for k, c, q, r in xs],
                        fmt=lambda v: f"{v:.2f}", top=1, colour="var(--g-c2)")
    body.append(st.section(
        "differ", "Where raters differ",
        "Wikipedia's list and an independent quality score (Lin et al., 0 to 1, for news websites) mostly agree. "
        "These are the most-cited sources where they do not. Neither rater is taken as right.",
        st.grid(st.card("Wikipedia: generally reliable · independent score below 0.6", dlist(hi)),
                st.card("Wikipedia: unreliable or deprecated · independent score 0.6 or above", dlist(lo)))))

    body.append(st.tech("The full detail",
                        "Every rater and what it measures, the most-cited sources in each area with every rating, "
                        "organisations and their recorded associations, journals, books by where their ISBN was "
                        "issued, works cited in several articles, and what cited websites say about themselves.",
                        [("sources-detail.html", "Sources in detail"), ("categories.html", "Categories"),
                         ("how-it-works.html#numbers", "What each rating means")]))
    return page(f"Sources · {NAME}", st.wrap("".join(body)), "sources.html",
                description="The sources the analysed Wikipedia articles cite, and what raters say about them.")


# ------------------------------------------------------------------ placeholders until each page is redesigned
LEAN_MIN_COVER = 0.10   # an article is drawn when at least this share of its citations is rated
GAP_MIN_TEXT, GAP_MIN_CITED = 0.30, 0.20   # "largest differences": both figures must speak for this much


def _dr(v):
    """Audience leaning in plain terms: out of 100 people sharing the site, Democrats / Republicans."""
    r = round((1 + v) / 2 * 100)
    return f"{100 - r} D / {r} R"


def leaning_overview(ctx) -> str:
    from .site import NAME, baseline_leaning, cited_figures, page, slug
    from .affiliation import position_split
    outl = ctx.outlets or {}
    by = (ctx.patterns or {}).get("by_article", {})
    F = "audience_leaning_dd"
    bl = baseline_leaning(ctx).get(F)
    groups, pairs, lr_rows, gaps = [], [], [], []
    drawn = rated = tot_c = 0
    lr_all, placed_all, cites_all = Counter(), 0.0, 0
    for a, recs in _by_area(ctx, min_n=1):
        pts, cv, wv, lr = [], [], [], Counter()
        placed = cites = 0
        for r in recs:
            c = cited_figures(r, ctx).get(F) or {}
            w = (((by.get(r["article"]) or {}).get("writers") or {}).get(F)) or {}
            for x in (r.get("sources") or {}).get("list", []):
                n = x["citations"]
                cites += n
                o = outl.get(x["source"]) or {}
                ps = position_split((o.get("affiliation") or {}).get("labels"), o.get("country"))
                if ps:
                    placed += n
                    for side, f in ps.items():
                        lr[side] += n * f
            if c.get("mean") is None:
                continue
            rated += 1
            if c.get("citations_covered", 0) < LEAN_MIN_COVER:
                continue
            drawn += 1
            tip = (f"{r['article']}: {c['mean']:+.2f} ({_dr(c['mean'])} among those sharing its cited websites); "
                   f"{st.pct(c['citations_covered'])} of its citations rated")
            pts.append((c["mean"], tip, f"articles/{slug(r['article'])}.html#sec-sources"))
            cv.append(c["mean"])
            if w.get("mean") is not None:
                wv.append(w["mean"])
            if (w.get("mean") is not None and (w.get("text_covered") or 0) >= GAP_MIN_TEXT
                    and c["citations_covered"] >= GAP_MIN_CITED):
                gaps.append((abs(w["mean"] - c["mean"]), r["article"], c["mean"], w["mean"],
                             c["citations_covered"], w.get("text_covered")))
        lr_all.update(lr)
        placed_all += placed
        cites_all += cites
        if len(recs) < MIN_AREA:
            continue
        lab, sub = _area_label(a, recs)
        if pts:
            groups.append((lab, f"{len(pts)} of {len(recs)} drawn", pts))
        sub = f"{len(recs):,} articles"
        med = lambda xs: sorted(xs)[len(xs) // 2] if xs else None  # noqa: E731
        if cv:
            pairs.append((lab, sub, med(cv), med(wv),
                          f"{lab}: middle article {med(cv):+.2f} for the sources it cites"
                          + (f", {med(wv):+.2f} for the sources its writers cite" if wv else "")))
        lr_rows.append((lab, f"{st.pct(placed / cites if cites else 0)} of citations placed", {
            "l": lr.get("far left", 0) + lr.get("left", 0), "c": lr.get("centre", 0),
            "r": lr.get("far right", 0) + lr.get("right", 0)}))
    ticks = [-0.6, -0.3, 0, 0.3, 0.6]
    LR = [("l", "Left (incl. far left)", "var(--lr-l)"), ("c", "Centre", "var(--lr-c)"),
          ("r", "Right (incl. far right)", "var(--lr-r)")]
    gaps.sort(reverse=True)
    vals = [v for _, _, a_, b_, _ in pairs for v in (a_, b_) if v is not None] + ([bl] if bl is not None else [])
    d_lo = (min(vals) // 0.1) * 0.1 - 0.1 if vals else -0.8
    d_hi = -((-max(vals)) // 0.1) * 0.1 + 0.1 if vals else 0.8
    d_ticks = [round(d_lo + 0.1 * i, 1) for i in range(int(round((d_hi - d_lo) / 0.1)) + 1)]
    body = [st.hero("Leaning of the sources", "Who shares the websites each article cites",
                    "Researchers have measured, for tens of thousands of websites, whether the people who share "
                    "them on social media are mostly Democrats or mostly Republicans. Here is where each article's "
                    "cited websites fall on that measure. It describes who shares a site, not what it publishes, "
                    "and it is not applied to books or journals."),
            st.stats([(f"{drawn:,}", "articles drawn below",
                       f"Articles with at least {st.pct(LEAN_MIN_COVER)} of their citations going to rated websites."),
                      (f"{bl:+.2f}" if bl is not None else "–", "average across all rated citations",
                       f"{_dr(bl)} among those sharing the average cited website. Compare articles with this, not with zero."
                       if bl is not None else None),
                      (st.pct(placed_all / cites_all if cites_all else 0), "of citations go to a source with a "
                       "recorded left–right position", "From Wikidata and the source's own Wikipedia article.")]),
            st.toc([("dots", "Each article on one scale"), ("writers", "Article and writers"),
                    ("lr", "Recorded left–right position"), ("gaps", "Largest differences")])]
    body.append(st.section(
        "dots", "Each article on one scale",
        "Each dot is one article: the average for the websites it cites (DomainDemo, 2025). Left means the people "
        "sharing those sites are mostly Democrats, right mostly Republicans. The dark tick is the middle article "
        "of each area; the dashed line is the average across everything cited. Click a dot to open the article.",
        st.card("By topic area", st.dotstrip(groups, -0.8, 0.8, ticks, ref=bl, ref_label="average", fmt=lambda v: _dr(v),
                            axis="← sites shared mostly by Democrats · sites shared mostly by Republicans →",
                            ref_key="the average across all rated citations, on every analysed article"),
                note=f"Only articles where at least {st.pct(LEAN_MIN_COVER)} of citations go to rated websites are "
                     "drawn; many articles rest mostly on books, which no open dataset rates. Most large news "
                     "sites fall left of the middle on this measure, so compare with the average line.",
                wide=True)))
    body.append(st.section(
        "writers", "The article's sources, and its writers' sources",
        "For each area: the middle article's figure for the websites it cites, and for the websites its writers "
        "cite across all analysed articles (each writer weighted by how much of the article they wrote). The "
        "writers' figure describes sources, not anyone's views, and no editor's own figure is published.",
        st.card("Middle article, by topic area", st.dumbbell(pairs, d_lo, d_hi, d_ticks,
                                                             ("Sources the article cites", "Sources its writers cite"),
                                                             fmt=lambda v: _dr(v), ref=bl, ref_label="average"),
                wide=True)))
    body.append(st.section(
        "lr", "Recorded left–right position",
        "Some cited sources have a recorded political position, from Wikidata and their own Wikipedia article. "
        "Of the citations that go to such sources, the share recorded as left, centre or right.",
        st.card("By topic area", st.stacks([("All areas", f"{st.pct(placed_all / cites_all if cites_all else 0)} "
                                             "of citations placed", {
                                                 "l": lr_all.get("far left", 0) + lr_all.get("left", 0),
                                                 "c": lr_all.get("centre", 0),
                                                 "r": lr_all.get("far right", 0) + lr_all.get("right", 0)})] + lr_rows, LR),
                note="Only a small share of citations go to sources with a recorded position, so these bars "
                     "describe that small part. The placement rules, with Wikipedia's own words for each label, "
                     "are on the detailed page.")))
    grows = []
    for d, art, c, w, cc, tc in gaps[:12]:
        grows.append((f"<a href='articles/{slug(art)}.html'>{escape(art)}</a>", d,
                      f"{art}: its cited websites {c:+.2f}, its writers' cited websites {w:+.2f}",
                      f"article {c:+.2f} ({_dr(c)}) · writers {w:+.2f} ({_dr(w)}) · {st.pct(cc)} of citations rated"
                      + (f" · {st.pct(tc)} of text covered" if tc is not None else "")))
    body.append(st.section(
        "gaps", "Largest differences between an article and its writers",
        "Articles whose own cited websites sit furthest from the websites their writers cite elsewhere. A gap can "
        "come from the subject, from what sources exist, or from who wrote the article; this does not say which. "
        f"Listed only where at least {st.pct(GAP_MIN_CITED)} of the article's citations are rated and the writers "
        f"counted wrote at least {st.pct(GAP_MIN_TEXT)} of its text.",
        st.card("Gap on the −1 to +1 scale", st.hbars(grows, fmt=lambda v: f"{v:.2f}", top=max(
            [g[0] for g in gaps[:12]] or [1]), colour="var(--g-c2)"))))
    body.append(st.tech("The full detail",
                        "Rank every article by any rater (both audience measures, Media Bias/Fact Check, AllSides, "
                        "recorded affiliation), how the writers' figure is worked out, and every limit of these figures.",
                        [("leaning-detail.html", "Leaning in detail"), ("leaning-detail.html#method", "How the writers' figure is worked out"),
                         ("leaning-detail.html#limits", "Limits")]))
    return page(f"Leaning · {NAME}", st.wrap("".join(body)), "leaning.html",
                description="Where each analysed article's cited websites fall on measures of audience leaning.")


def editors_overview(ctx) -> str:
    """Who writes the analysed articles, by counts only: no account names and no editor IDs here."""
    from .site import NAME, page, slug
    pt = ctx.patterns or {}
    eds = pt.get("editors", [])
    subst = [e for e in eds if e["articles_substantial"] >= 1]
    sanc = [e for e in eds if e["sanctioned"]]
    conc, sgroups, pairs_lead = [], [], []
    halves = Counter()
    types_area, timing, timing_area = [], Counter(), []
    one_wrote_half = 0
    TYPES = [("topic_ban", "Banned from the topic", st.CAT[0]), ("site_ban", "Banned from Wikipedia", st.CAT[1]),
             ("sockpuppet", "Ran extra accounts (sockpuppets)", st.CAT[2])]
    hbins = [(1, 1, "1"), (2, 2, "2"), (3, 3, "3"), (4, 5, "4–5"), (6, 10, "6–10"), (11, 20, "11–20"), (21, 10**9, "21+")]
    for a, recs in _by_area(ctx, min_n=1):
        pts, spts, sa, sl, ty, tma = [], [], [], [], Counter(), Counter()
        for r in recs:
            au, ac = r["authorship"], r["accountability"]
            t1 = (au.get("top_shares") or {}).get("1")
            n50 = au.get("editors_for_50pct")
            if n50:
                halves[next(l for lo, hi, l in hbins if lo <= n50 <= hi)] += 1
                one_wrote_half += n50 == 1
            href = f"articles/{slug(r['article'])}.html"
            if t1 is not None:
                pts.append((t1, f"{r['article']}: the main writer wrote {st.pct(t1)} of today's text; "
                                f"{n50} editor{'s' if n50 != 1 else ''} wrote half", href + "#sec-writers"))
            ss = ac.get("sanctioned_share") or 0
            spts.append((ss, f"{r['article']}: {st.pct(ss, 1)} of today's text by editors Wikipedia later sanctioned "
                             f"({st.pct(ac.get('sanctioned_lead_share') or 0, 1)} of the opening section)", href + "#sec-writers"))
            sa.append(ss)
            sl.append(ac.get("sanctioned_lead_share") or 0)
            for k, _, _ in TYPES:
                ty[k] += ((ac.get("by_type") or {}).get(k) or {}).get("words", 0)
            tm = ac.get("timing") or {}
            tma["before"] += tm.get("added_before_sanction_words", 0)
            tma["during"] += tm.get("added_during_sanction_words", 0) + tm.get("added_during_open_ended_sanction_words", 0)
            tma["after"] += tm.get("added_after_sanction_ended_words", 0)
        timing.update(tma)
        if len(recs) < MIN_AREA:
            continue
        lab, sub = _area_label(a, recs)
        conc.append((lab, sub, pts))
        sgroups.append((lab, sub, spts))
        mean = lambda xs: sum(xs) / len(xs) if xs else 0  # noqa: E731
        pairs_lead.append((lab, sub, mean(sa), mean(sl), f"{lab}: on average {st.pct(mean(sa), 1)} of the whole "
                           f"text and {st.pct(mean(sl), 1)} of the opening section by editors Wikipedia sanctioned"))
        types_area.append((lab, sub, ty))
        timing_area.append((lab, sub, tma))
    many = Counter()
    mbins = [(1, 1, "1"), (2, 2, "2"), (3, 4, "3–4"), (5, 9, "5–9"), (10, 19, "10–19"), (20, 10**9, "20+")]
    for e in subst:
        n = e["articles_substantial"]
        many[next(l for lo, hi, l in mbins if lo <= n <= hi)] += 1
    n_art = len(ctx.recs)
    body = [st.hero("Who wrote it", "How the writing of each article is spread across editors",
                    "Every word of today's text is credited to the editor who first added it. From that: how few "
                    "people wrote most of an article, how much was written by editors Wikipedia itself later "
                    "sanctioned, and how many editors write across many articles. Counts only; no editor is "
                    "named on this page."),
            st.stats([(f"{len(subst):,}", "editors wrote at least 1% of an analysed article", None),
                      (f"{sum(1 for e in subst if e['articles_substantial'] >= 2):,}", "did so in two or more", None),
                      (st.pct(one_wrote_half / n_art if n_art else 0), "of articles: one editor wrote half or more",
                       "The share of analysed articles where a single editor wrote at least half of today's text."),
                      (f"{len(sanc):,}", "editors Wikipedia sanctioned have text in an analysed article",
                       "Banned from the topic or from Wikipedia, or found running extra accounts.")]),
            st.toc([("conc", "How concentrated"), ("sanc", "Sanctioned editors' text"),
                    ("lead", "Whole article and opening"), ("many", "Editors across articles")])]
    body.append(st.section(
        "conc", "How concentrated the writing is",
        "Each dot is one article: the share of today's text written by its main writer. A dot at 50% means one editor "
        "wrote half of the words readers see today.",
        st.card("Main writer's share of today's text, by topic area",
                st.dotstrip(conc, 0, 1, [0, .25, .5, .75, 1], fmt=lambda v: st.pct(v),
                            axis="Share of today's text written by the article's main writer → further right, more of the text is one person's"), wide=True)
        + "<div style='height:16px'></div>"
        + st.grid(st.card("How many editors wrote half of the text",
                          st.histogram([(l, halves[l], f"{halves[l]:,} articles where {l} editor"
                                         f"{'s' if l != '1' else ''} wrote half the text") for _, _, l in hbins],
                                        label="Articles by number of editors who wrote half"),
                          q="Number of articles, by the fewest editors who together wrote half of today's text"),
                  st.card("What “wrote” means", "<p class='q' style='margin:0'>A word is credited to the editor who "
                          "first typed it, followed through the whole history by WikiWho. Moving or restoring text "
                          "does not make someone its author. Footnotes, tables and captions are left out.</p>"))))
    body.append(st.section(
        "sanc", "Text by editors Wikipedia later sanctioned",
        "Wikipedia's administrators ban some editors from a topic or from the site, or find them running extra "
        "accounts. Each dot is one article: the share of its text written by such editors. A sanction is about how "
        "someone behaved on Wikipedia, not proof that what they wrote is wrong.",
        st.card("Share of today's text by sanctioned editors, by topic area",
                st.dotstrip(sgroups, 0, 0.5, [0, .1, .2, .3, .4, .5], fmt=lambda v: st.pct(v),
                            axis="Share of today's text written by editors Wikipedia later sanctioned → further right, more"), wide=True,
                note="Articles above 50% are drawn at the right edge.")
        + "<div style='height:16px'></div>"
        + st.grid(st.card("By kind of sanction", st.stacks(types_area, TYPES),
                          q="Words by sanctioned editors, split by the kind of sanction"),
                  st.card("When it was written", _timing_lines(timing) + st.stacks(
                      [("All areas", "", timing)] + timing_area, [
                      ("before", "Before the sanction", st.RAMP[1]), ("during", "While it was in force", st.RAMP[0]),
                      ("after", "After it ended", st.RAMP[3])]),
                          q="Words by sanctioned editors in today's text, by when they were added. "
                            "Point at a bar for its figures."))))
    body.append(st.section(
        "lead", "The whole article and its opening section",
        "The opening section is what most readers, search engines and AI assistants see first. For each area, the "
        "average share written by sanctioned editors in the whole text and in the opening.",
        st.card("Average share by sanctioned editors", st.dumbbell(
            pairs_lead, 0, max([0.2] + [max(a_, b_) for _, _, a_, b_, _ in pairs_lead]) * 1.1,
            [0, .05, .1, .15, .2, .25, .3][:1 + int(max([0.2] + [max(a_, b_) for _, _, a_, b_, _ in pairs_lead]) * 1.1 / .05)],
            ("Whole article", "Opening section"), fmt=lambda v: st.pct(v)), wide=True)))
    body.append(st.section(
        "many", "Editors who write across many articles",
        "How many analysed articles each editor wrote at least 1% of. Most write in one; a few write in many.",
        st.card("Editors, by number of articles", st.histogram(
            [(l, many[l], f"{many[l]:,} editors wrote at least 1% of {l} analysed article{'s' if l != '1' else ''}")
             for _, _, l in mbins], label="Editors by number of articles"),
                q="Number of editors")))
    body.append(st.tech("The full detail",
                        "Editors by topic area, the editors with the most articles and the sanctioned editors, each "
                        "under a pattern ID (never an account name), and a look-up for any article or ID.",
                        [("editors-detail.html", "Editors in detail"), ("editor.html", "Look up an editor"),
                         ("how-it-works.html#steps", "How authorship is worked out")]))
    return page(f"Editors · {NAME}", st.wrap("".join(body)), "editors.html",
                description="How the writing of the analysed articles is spread across editors.")


LIST_CSS = """<style>
.al-ctl{display:grid;grid-template-columns:minmax(0,2fr) repeat(3,minmax(0,1fr));gap:10px;margin:22px 0 10px}
.al-ctl input,.al-ctl select{width:100%;font:inherit;font-size:.95rem;padding:9px 12px;border:1px solid var(--line);
 border-radius:10px;background:var(--bg);color:var(--fg)}
.al-ctl label{font:.74rem system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted);display:block}
.al-count{font:.85rem system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted);margin:6px 0 10px}
.al{border:1px solid var(--line);border-radius:14px;overflow:hidden}
.al .r{display:grid;grid-template-columns:minmax(0,2.2fr) repeat(5,minmax(0,1fr));gap:14px;align-items:center;
 padding:10px 16px;border-top:1px solid var(--line)}
.al .r.h{border-top:0;background:var(--soft);font:600 .76rem system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted);
 padding:9px 16px}
.al .r.h span{cursor:help;border-bottom:1px dotted var(--muted)}
.al .r:not(.h):hover{background:color-mix(in srgb,var(--soft) 55%,transparent)}
.al .t a{font-weight:600;font-size:.97rem;text-decoration:none;color:var(--fg)}
.al .t a:hover{text-decoration:underline}
.al .t small{display:block;font:.74rem system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted)}
.al .m{font:.82rem system-ui,-apple-system,"Segoe UI",sans-serif;font-variant-numeric:tabular-nums}
.al .m .tr{height:6px;border-radius:3px;background:var(--g-soft);margin-top:4px;position:relative}
.al .m .tr i{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--g-o2)}
.al .m .tr.sc i{background:var(--g-sanc)}
.al .m .tr.dot b{position:absolute;top:-3px;width:12px;height:12px;margin-left:-6px;border-radius:50%;background:var(--g-o2)}
.al .m .tr.dot::after{content:"";position:absolute;left:50%;top:-2px;bottom:-2px;border-left:1px solid var(--muted)}
.al .m.na{color:var(--muted)}
.al-more{display:block;margin:14px auto 0;font:.9rem system-ui,-apple-system,"Segoe UI",sans-serif;padding:9px 18px;
 border-radius:999px;border:1px solid var(--line);background:var(--bg);color:var(--fg);cursor:pointer}
@media (max-width:860px){.al-ctl{grid-template-columns:1fr 1fr}.al .r{grid-template-columns:1fr 1fr 1fr}
 .al .r .t{grid-column:1/-1}.al .r.h .t{display:none}}
</style>"""

LIST_JS = """<script>
(function(){var D=__DATA__,A=__AREAS__,K=__KINDS__,COLS=__COLS__;
var q=document.getElementById('alq'),fa=document.getElementById('ala'),fk=document.getElementById('alk'),
    so=document.getElementById('als'),box=document.getElementById('alb'),cnt=document.getElementById('alc'),
    more=document.getElementById('alm'),shown=60;
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function pc(v){return Math.round(v*100)+'%'}
function cell(r,c){var v=r[c.k];if(v===null||v===undefined)return '<div class="m na">–</div>';
 if(c.t==='pct')return '<div class="m">'+pc(v)+(c.k==='sc'&&r.th?' †':'')+'<div class="tr'+(c.k==='sc'?' sc':'')+'"><i style="width:'+Math.min(100,v*100)+'%"></i></div></div>';
 if(c.t==='lean'){var R=Math.round((1+v)/2*100);return '<div class="m" title="'+(100-R)+' D / '+R+' R among people sharing its cited websites">'+(v>0?'+':'')+v.toFixed(2)+'<div class="tr dot"><b style="left:'+((Math.max(-1,Math.min(1,v))+1)/2*100)+'%"></b></div></div>';}
 return '<div class="m">'+Number(v).toLocaleString()+'<div class="tr"><i style="width:'+Math.min(100,v/c.max*100)+'%"></i></div></div>';}
function draw(){var t=q.value.toLowerCase(),a=fa.value,k=fk.value,s=so.value,dir=s.charAt(0)==='-'?-1:1,key=s.replace('-','');
 var rows=D.filter(function(r){return(!t||r.n.toLowerCase().indexOf(t)>-1)&&(a==='*'||r.a===a)&&(k==='*'||r.k===k)});
 rows.sort(function(x,y){var u=x[key],w=y[key];if(key==='n')return dir*u.localeCompare(w);
  if(u===null||u===undefined)return 1;if(w===null||w===undefined)return -1;return dir*(u-w)});
 cnt.textContent=rows.length.toLocaleString()+' article'+(rows.length===1?'':'s');
 box.innerHTML=rows.slice(0,shown).map(function(r){return '<div class="r"><div class="t"><a href="articles/'+r.s+'.html">'+esc(r.n)+'</a><small>'+esc(A[r.a]||'')+' · '+esc(K[r.k]||'')+'</small></div>'+COLS.map(function(c){return cell(r,c)}).join('')+'</div>'}).join('');
 more.style.display=rows.length>shown?'block':'none';}
[q,fa,fk,so].forEach(function(e){e.addEventListener('input',function(){shown=60;draw()})});
more.addEventListener('click',function(){shown+=120;draw()});
var m=location.hash.match(/^#area-(.*)$/);if(m){var v=decodeURIComponent(m[1]);fa.value=(v==='none'?'':v);if(fa.value!==(v==='none'?'':v))fa.value='*';}
draw();})();
</script>"""


def compare_overview(ctx) -> str:
    """All articles: one list to search, filter and sort, with each figure drawn as a small bar."""
    import json
    from .site import NAME, cited_figures, kind_name, page, slug, _is_thin, area_name
    from .candidates import KINDS
    rows = []
    for r in ctx.recs:
        au, ac, so = r["authorship"], r["accountability"], r.get("sources") or {}
        lean = cited_figures(r, ctx).get("audience_leaning_dd") or {}
        rows.append({"n": r["article"], "s": slug(r["article"]), "a": ctx.areas.get(r["article"], "") or "",
                     "k": ctx.kinds.get(r["article"]) or "",
                     "t1": (au.get("top_shares") or {}).get("1"), "sc": au.get("sanctioned_share"),
                     "th": bool(_is_thin(r)), "sv": ((au.get("survival_article") or {}).get("365d") or {}).get("rate"),
                     "ci": so.get("citations"),
                     "ln": round(so.get("with_link", 0) / so["citations"], 3) if so.get("citations") else None,
                     "le": lean.get("mean") if lean.get("citations_covered", 0) >= LEAN_MIN_COVER else None})
    cols = [{"k": "t1", "t": "pct", "h": "Main writer", "x": "Share of today's text written by the single biggest contributor."},
            {"k": "sc", "t": "pct", "h": "By sanctioned editors", "x": "Share of today's text by editors Wikipedia "
             "sanctioned. † the sanctions list for this area is less complete, so the real figure is probably higher."},
            {"k": "sv", "t": "pct", "h": "New text lasting a year", "x": "Of all words ever added, the share still there a year later."},
            {"k": "ci", "t": "int", "h": "Citations", "x": "Footnotes in the article.",
             "max": max([x["ci"] or 0 for x in rows] or [1])},
            {"k": "le", "t": "lean", "h": "Cited sites' audience", "x": "Audience leaning of the websites it cites "
             "(−1 mostly Democrats, +1 mostly Republicans, DomainDemo). Shown when at least 10% of citations are rated."}]
    order = [a for a, _ in _by_area(ctx, min_n=1)]
    areas = {a: area_name(a) for a in order}
    kinds = {k: kind_name(k, plural=False) for k in KINDS + [""]}
    head = ("<div class='r h'><div class='t'>Article</div>" + "".join(
        f"<div><span title='{escape(c['x'], quote=True)}'>{escape(c['h'])}</span></div>" for c in cols) + "</div>")
    ctl = ("<div class='al-ctl'><div><label for='alq'>Find an article</label><input id='alq' type='search' "
           "placeholder='Type part of a title' autocomplete='off'></div>"
           "<div><label for='ala'>Topic area</label><select id='ala'><option value='*'>All areas</option>"
           + "".join(f"<option value='{escape(a, quote=True)}'>{escape(areas[a])}</option>" for a in order)
           + "</select></div><div><label for='alk'>Kind of subject</label><select id='alk'><option value='*'>All kinds</option>"
           + "".join(f"<option value='{escape(k, quote=True)}'>{escape(kind_name(k))}</option>" for k in KINDS + [""])
           + "</select></div><div><label for='als'>Sort by</label><select id='als'>"
           "<option value='n'>Title</option><option value='-t1'>Main writer's share, highest first</option>"
           "<option value='-sc'>Sanctioned editors' text, highest first</option>"
           "<option value='sv'>New text lasting a year, lowest first</option>"
           "<option value='-ci'>Citations, most first</option><option value='le'>Cited sites' audience, left to right</option>"
           "</select></div></div>")
    body = [st.hero("All articles", f"{len(rows):,} articles, side by side",
                    "Every analysed article with five of its figures, each drawn as a small bar so you can scan down "
                    "a column. Search, filter by topic or kind of subject, and sort. Hover a column name for what "
                    "it measures."),
            ctl, "<div class='al-count' id='alc'></div><div class='al' role='table'>", head,
            "<div id='alb'></div></div><button class='al-more' id='alm' type='button'>Show more</button>",
            st.tech("The full detail",
                    "Every figure for every article, grouped like with like (by topic area, then kind of subject), "
                    "with the typical value for each group and what each figure means.",
                    [("compare-detail.html", "Every figure, every article"), ("articles.html", "Which articles, and why"),
                     ("data/summary.json", "All figures as JSON")])]
    js = (LIST_JS.replace("__DATA__", json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
          .replace("__AREAS__", json.dumps(areas, ensure_ascii=False)).replace("__KINDS__", json.dumps(kinds, ensure_ascii=False))
          .replace("__COLS__", json.dumps([{k: v for k, v in c.items() if k != "x"} for c in cols])))
    return page(f"All articles · {NAME}", LIST_CSS + st.wrap("".join(body)) + js, "compare.html",
                json_alt="data/summary.json", description="Every analysed Wikipedia article with its main figures.")


FLOW_CSS = """<style>
.flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;margin:8px 0 0;counter-reset:f}
.flow>div{position:relative;padding:18px 26px 18px 20px;border:1px solid var(--line);background:var(--bg);margin-right:18px;
 border-radius:14px}
.flow>div:not(:last-child)::after{content:"";position:absolute;right:-17px;top:50%;width:16px;height:2px;background:var(--line)}
.flow>div:not(:last-child)::before{content:"";position:absolute;right:-17px;top:calc(50% - 4px);border:5px solid transparent;
 border-left-color:var(--line);transform:translateX(9px)}
.flow .n{font:600 .7rem system-ui,-apple-system,"Segoe UI",sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.flow h3{font-size:1.02rem;margin:8px 0 6px;line-height:1.3;border:0}
.flow p{font-size:.88rem;color:var(--muted);margin:0}
.flow b.big{display:block;font:600 1.5rem/1.1 Georgia,"Iowan Old Style",serif;margin:12px 0 0;color:var(--fg)}
@media (max-width:900px){.flow{grid-template-columns:1fr;gap:12px}.flow>div{margin:0}.flow>div::after,.flow>div::before{display:none}}
</style>"""


def choose_overview(ctx) -> str:
    from .site import NAME, area_name, page
    from .candidates import AREAS, KINDS, SUBJECTS
    cands = ctx.candidates or []
    done = {r["article"] for r in ctx.recs}
    titles = {c["title"] for c in cands}
    by_area = defaultdict(list)
    for c in cands:
        by_area[c["area"]].append(c)
    tagged_areas = [a for a in AREAS if by_area.get(a) and a not in SUBJECTS]
    subject_areas = [a for a in AREAS if by_area.get(a) and a in SUBJECTS]
    KIND_FAM = {"journalist": "people", "person": "people", "media": "media", "organisation": "org",
                "idea": "idea", "event": "event"}
    KCATS = [("people", "People: journalists, commentators, public figures", st.CAT[0]),
             ("media", "News outlets and media", st.CAT[1]), ("org", "Organisations", st.CAT[2]),
             ("idea", "Ideas, ideologies and movements", st.CAT[3]), ("event", "Events", st.CAT[4]),
             ("other", "Other", st.REST)]
    rows = []
    for a in tagged_areas + subject_areas:
        cs = by_area[a]
        n_done = sum(1 for c in cs if c["title"] in done)
        if len(cs) < MIN_AREA:
            continue
        lab = area_name(a).split(" (")[0]
        mix = Counter(KIND_FAM.get(c.get("kind") or "", "other") for c in cs)
        rows.append((lab, f"{n_done:,} of {len(cs):,} analysed" + (" · chosen by subject" if a in SUBJECTS else ""), mix))
    flow = ("<div class='flow'>"
            "<div><span class='n'>Step 1</span><h3>Wikipedia marks contested subjects</h3><p>A notice on an "
            "article's talk page puts it under special editing rules for a contentious topic area. For a few "
            "subjects Wikipedia does not mark, a WikiProject's own tags are used instead.</p>"
            f"<b class='big'>{len(tagged_areas) + len(subject_areas)}</b><p>topic areas</p></div>"
            "<div><span class='n'>Step 2</span><h3>Sorted by kind of subject</h3><p>Journalist or commentator, "
            "other public figure, news outlet, organisation, idea or movement, event; from Wikidata. Lists and "
            "articles that fit none are left out.</p>"
            f"<b class='big'>{len(KINDS)}</b><p>kinds of subject</p></div>"
            "<div><span class='n'>Step 3</span><h3>The most read are chosen</h3><p>In each area, for each kind, "
            "the 25 articles read most over the previous 60 days. A few are added on request, and marked.</p>"
            f"<b class='big'>{len(titles):,}</b><p>articles chosen</p></div>"
            "<div><span class='n'>Step 4</span><h3>Analysed in batches</h3><p>Each chosen article is analysed "
            "from one exact version, with the same code and rules as every other.</p>"
            f"<b class='big'>{len(done & titles):,}</b><p>analysed so far</p></div></div>")
    body = [FLOW_CSS,
            st.hero("Which articles, and why", "Chosen by a fixed rule, not by hand",
                    "So that the selection does not depend on what anyone expects to find, articles are picked by "
                    "the same four steps in every topic area."),
            st.section("rule", "The rule", "Four steps, the same for every area.", flow),
            st.section("chosen", "What was chosen in each area",
                       "The chosen articles in each topic area, by kind of subject, with how many are analysed so far. "
                       "Some areas have few news outlets or ideas tagged, so their mix differs.",
                       st.card("Chosen articles, by kind of subject", st.stacks(rows, KCATS),
                               note="Areas marked “chosen by subject” use a WikiProject's tags, because Wikipedia "
                                    "does not mark those subjects as contentious; here we chose the subjects.")),
            st.tech("The full detail",
                    "The rule in full, with its exceptions, and every chosen article ranked by page views in each "
                    "area and kind, with its status. How the categories are drawn, and which articles each rule moves.",
                    [("articles-detail.html", "Full article lists"), ("categories.html", "Categories"),
                     ("compare.html", "All analysed articles")])]
    return page(f"Which articles · {NAME}", st.wrap("".join(body)), "articles.html",
                description="How articles are chosen for analysis.")
