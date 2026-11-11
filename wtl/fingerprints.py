"""Two reader pages of profiles ("fingerprints"):

- editors-across.html: the editors who wrote at least 1% of the most analysed articles, across
  two or more topic areas. One row each, under the pattern ID used everywhere else on the site
  (never an account name): the topic areas they write in, and the sources they cite (kinds,
  Wikipedia's reliability list, independent quality score). The audience leaning and media-bias
  labels of their cited sources are shown by default (owner reversed the 2026-11-06 ruling for
  this page on 2026-11-11); WTL_EDITOR_LEANING=0 hides them.
- sources-affiliations.html: the most-cited sources, each with what Wikidata and Wikipedia
  record about it (kind, owner/publisher, founders, memberships, political labels) and the topic
  areas citing it, beside Wikipedia's rating, the quality score and audience leaning.

Descriptions only: every figure is a count or share of citations; nothing is interpreted.
"""

import os
from collections import Counter, defaultdict
from html import escape

from . import story as st
from .readers import FAM_CATS, RATING_CATS, _family, _rating

N_EDITORS = 40
N_SOURCES = 60
MIN_AREAS = 2

CSS = """<style>
.fp{font:.84rem/1.35 system-ui,-apple-system,"Segoe UI",sans-serif}
.fp .row{display:grid;gap:0 14px;align-items:center;padding:9px 0;border-top:1px solid var(--line)}
.fp .row.h{border-top:0;align-items:end;color:var(--muted);font-size:.74rem;padding-bottom:4px}
.fp.ed .row{grid-template-columns:120px minmax(0,var(--hw)) minmax(90px,1fr) minmax(90px,1fr) 64px var(--lw)}
.fp.so .row{grid-template-columns:minmax(150px,1.2fr) 64px minmax(0,var(--hw)) 130px 52px 90px minmax(160px,1.2fr)}
.fp.so .row .assoc{grid-column:1/-1;margin-top:6px}
.fp .id a{font:600 .9rem ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.04em}
.fp small{display:block;color:var(--muted);font-size:.72rem}
.fp .heat{display:grid;grid-template-columns:repeat(var(--na),minmax(0,1fr));gap:2px}
.fp .heat i{display:block;height:22px;border-radius:3px;background:var(--g-soft);font-style:normal;
 font-size:.66rem;line-height:22px;text-align:center;color:var(--fg);font-variant-numeric:tabular-nums}
.fp .heat i.on{color:#fff}
.fp .heat.hd i{height:auto;background:none;writing-mode:vertical-rl;transform:rotate(180deg);text-align:left;
 line-height:1.1;font-size:.68rem;color:var(--muted);max-height:120px;overflow:hidden;white-space:nowrap;margin:0 auto}
.fp .mini{display:flex;gap:1px;height:14px;border-radius:3px;overflow:hidden}
.fp .mini span{display:block;min-width:0}
.fp .num{font-variant-numeric:tabular-nums;text-align:right}
.fp .ln{position:relative;height:14px;border-radius:3px;background:linear-gradient(90deg,var(--g-c1) 0,var(--g-soft) 50%,var(--g-c2) 100%);opacity:.9}
.fp .ln::after{content:"";position:absolute;left:50%;top:-3px;bottom:-3px;border-left:1px solid var(--muted)}
.fp .ln b{position:absolute;top:-3px;width:10px;height:20px;margin-left:-5px;border-radius:3px;background:var(--fg);
 box-shadow:0 0 0 2px var(--bg)}
.fp .lv{display:flex;justify-content:space-between;font-size:.68rem;color:var(--muted)}
.fp .chips .lbl{font-size:.74rem}
.fp .assoc{font-size:.76rem;color:var(--muted)}.fp .assoc b{color:var(--fg);font-weight:500}
.fp .tag{display:inline-block;padding:0 6px;border-radius:999px;font-size:.7rem;border:1px solid var(--line)}
.fp .tag.sanc{border-color:var(--g-sanc);color:var(--g-sanc)}
.fp-scroll{overflow-x:auto}.fp-scroll>.fp{min-width:1000px}
@media (max-width:760px){.fp-scroll>.fp{min-width:900px}}
</style>"""


def _short(code):
    from .site import area_name
    if code == "CN":
        return "Uyghurs, Xinjiang"
    if code == "CNX":
        return "China, Taiwan, HK, Tibet"
    n = area_name(code)
    n = n.split("(")[0].split(":")[0].split(",")[0].strip()
    return {"US politics": "US politics", "Eastern Europe and the Balkans": "Eastern Europe",
            "Arab–Israeli conflict": "Arab–Israeli", "Gender and sexuality": "Gender & sexuality",
            "Discrimination": "Discrimination", "Antisemitism in Poland": "Antisemitism in Poland",
            "Syrian civil war and ISIL": "Syria and ISIL", "Conservatism and the right": "Conservatism",
            "Socialism": "Socialism", "Added on request": "On request"}.get(n, n)


def _areas(ctx):
    from .site import _area_order
    have = Counter(ctx.areas.get(r["article"], "") for r in ctx.recs)
    return [a for a in _area_order(ctx) if a and have.get(a)]


def _heat_head(areas):
    return (f"<div class='heat hd' style='--na:{len(areas)}'>"
            + "".join(f"<i title='{escape(a)}'>{escape(_short(a))}</i>" for a in areas) + "</div>")


def _heat(areas, counts, total, fmt):
    """One cell per area, shaded by its share of `total`; the figure printed inside."""
    from .site import area_name
    cells = []
    for a in areas:
        v = counts.get(a, 0)
        if not v:
            cells.append(f"<i title='{escape(area_name(a))}: none'></i>")
            continue
        sh = v / total if total else 0
        alpha = 0.18 + 0.82 * min(1, sh / 0.5)
        cells.append(f"<i class='{'on' if alpha > .55 else ''}' style='background:color-mix(in srgb,var(--g-o1) "
                     f"{alpha * 100:.0f}%,transparent)' data-tip='{escape(area_name(a), quote=True)}: "
                     f"{escape(fmt(v, sh), quote=True)}' tabindex='0'>{escape(fmt(v, sh, True))}</i>")
    return f"<div class='heat' style='--na:{len(areas)}'>" + "".join(cells) + "</div>"


def _mini(mix, cats, what):
    tot = sum(mix.get(k, 0) for k, _, _ in cats)
    if not tot:
        return "<span class='fnote'>–</span>"
    segs = "".join(f"<span style='flex:{mix.get(k, 0) / tot * 100:.2f};background:{c}' "
                   f"data-tip='{escape(what, quote=True)}: {escape(n, quote=True)}, {100 * mix.get(k, 0) / tot:.0f}%' "
                   f"tabindex='0'></span>" for k, n, c in cats if mix.get(k, 0) > 0)
    return f"<div class='mini'>{segs}</div>"


def _lean(v, tip):
    if v is None:
        return "<span class='fnote'>–</span>"
    r = round((1 + v) / 2 * 100)
    pos = (max(-1, min(1, v)) + 1) / 2 * 100
    return (f"<div class='ln' data-tip='{escape(tip, quote=True)}: of every 100 people sharing these websites, "
            f"{100 - r} Democrats and {r} Republicans (DomainDemo)' tabindex='0'><b style='left:{pos:.1f}%'></b></div>"
            f"<div class='lv'><span>D {100 - r}</span><span>R {r}</span></div>")


def _cites_by_editor(ctx):
    """pattern ID -> {source: citations}, from the cached per-revision maps (never published)."""
    from .patterns import _secret, editor_sources, pattern_id
    secret = _secret()
    out = defaultdict(Counter)
    for r in ctx.recs:
        for k, d in editor_sources(r, ctx.areas.get(r["article"], "")).items():
            out[pattern_id(k, secret)].update(d)
    return out


def _profile(cites, outl):
    fam, rate, q, lean = Counter(), Counter(), [0.0, 0], [0.0, 0]
    mb = Counter()
    for k, n in cites.items():
        o = outl.get(k) or {}
        fam[_family(o.get("kind"))] += n
        rate[_rating(o)] += n
        if o.get("independent_quality"):
            q[0] += o["independent_quality"]["score"] * n
            q[1] += n
        dd = (o.get("audience_leaning_dd") or {}).get("score")
        if dd is not None:
            lean[0] += dd * n
            lean[1] += n
        if o.get("mbfc"):
            b = o["mbfc"].get("bias") if isinstance(o["mbfc"], dict) else o["mbfc"]
            if b:
                mb[b] += n
    tot = sum(cites.values())
    return {"citations": tot, "fam": fam, "rate": rate,
            "quality": q[0] / q[1] if q[1] else None, "quality_cover": q[1] / tot if tot else 0,
            "lean": lean[0] / lean[1] if lean[1] else None, "lean_cover": lean[1] / tot if tot else 0, "mbfc": mb}


MBFC_CATS = [("left", "Left", "var(--g-c1)"), ("left-center", "Left-centre", "color-mix(in srgb,var(--g-c1) 55%,transparent)"),
             ("least biased", "Least biased", "var(--g-rest)"),
             ("right-center", "Right-centre", "color-mix(in srgb,var(--g-c2) 55%,transparent)"),
             ("right", "Right", "var(--g-c2)")]


# ------------------------------------------------------------------ editors
def editors_across(ctx) -> str:
    from .site import NAME, area_name, page
    show_lean = os.environ.get("WTL_EDITOR_LEANING", "1") != "0"
    outl = ctx.outlets or {}
    areas = _areas(ctx)
    eds = (ctx.patterns or {}).get("editors", [])
    rows = []
    for e in eds:
        by_area = Counter(ctx.areas.get(a, "") for a in e["shares"])
        by_area.pop("", None)
        if len([a for a in by_area if by_area[a]]) >= MIN_AREAS:
            rows.append((e, by_area))
    rows.sort(key=lambda x: (-x[0]["articles_substantial"], -len(x[1]), x[0]["id"]))
    rows = rows[:N_EDITORS]
    cites = _cites_by_editor(ctx)
    profs = {e["id"]: _profile(cites.get(e["id"], {}), outl) for e, _ in rows}
    n_art = len({a for e, _ in rows for a in e["shares"]})
    n_cit = sum(p["citations"] for p in profs.values())
    lw = "150px" if show_lean else "0"
    hw = f"{max(260, 22 * len(areas))}px"

    head = (f"<div class='row h'><div>Editor (pattern ID)</div>{_heat_head(areas)}<div>Kinds of sources cited</div>"
            "<div>On Wikipedia's reliability list</div><div class='num'>Quality score</div>"
            + ("<div>Who shares the cited websites</div>" if show_lean else "<div></div>") + "</div>")
    body = []
    for e, by_area in rows:
        p = profs[e["id"]]
        tot = sum(by_area.values())
        fmt = lambda v, sh, short=False: str(v) if short else f"{v} article{'s' if v != 1 else ''} ({sh * 100:.0f}% of theirs)"  # noqa: E731
        san = "<span class='tag sanc'>sanctioned</span>" if e["sanctioned"] else ""
        body.append(
            f"<div class='row'><div class='id'><a href='editor.html#id={escape(e['id'])}'>{escape(e['id'])}</a> {san}"
            f"<small>{e['articles_substantial']} articles ≥1% · {len(by_area)} areas</small>"
            f"<small>{p['citations']:,} citations added</small></div>"
            + _heat(areas, by_area, tot, fmt)
            + "<div>" + _mini(p["fam"], FAM_CATS, "Kinds of sources") + "</div>"
            + "<div>" + _mini(p["rate"], RATING_CATS, "Wikipedia's list") + "</div>"
            + (f"<div class='num' data-tip='Mean independent quality score (Lin and colleagues, 0 to 1) of the "
               f"rated websites they cite; covers {p['quality_cover'] * 100:.0f}% of their citations' tabindex='0'>"
               f"{p['quality']:.2f}</div>" if p["quality"] is not None else "<div class='num fnote'>–</div>")
            + (f"<div>{_lean(p['lean'], e['id'])}</div>" if show_lean else "<div></div>")
            + "</div>")
    table = (f"<div class='fp-scroll'><div class='fp ed' style='--hw:{hw};--lw:{lw}'>{head}{''.join(body)}</div></div>")
    legends = (st.legend([(n, c) for _, n, c in FAM_CATS]) + st.legend([(n, c) for _, n, c in RATING_CATS]))

    # how the top writers' cited sources spread, side by side
    fam_all, rate_all = Counter(), Counter()
    for p in profs.values():
        fam_all.update(p["fam"])
        rate_all.update(p["rate"])
    sections = [
        st.hero("Editors across topics", "The editors who write across many topic areas",
                f"The {len(rows)} editors who wrote at least 1% of the most analysed articles, in at least "
                f"{MIN_AREAS} topic areas. Each row is one editor's fingerprint: where they write, and what kinds of "
                "sources they cite. Editors appear under the same pattern ID as on the rest of the site, never by "
                "account name; open an ID for its articles."),
        st.stats([(f"{len(rows)}", "editors shown", None),
                  (f"{n_art:,}", "analysed articles they wrote at least 1% of", None),
                  (f"{n_cit:,}", "citations they added to analysed articles", None)]),
        st.toc([("rows", "Fingerprints"), ("together", "All of them together"), ("method", "How it is worked out")]),
        st.section("rows", "Fingerprints",
                   "One row per editor. The shaded cells count the analysed articles they wrote at least 1% of, in "
                   "each topic area; darker means a larger share of their articles. The bars split the citations "
                   "they added, across all analysed articles. Point at any cell or bar for its figure.",
                   st.card("Editors, by number of analysed articles", legends + table, wide=True,
                           note=("Quality score: the mean of the rated news websites they cite. "
                                 + ("Who shares the cited websites: the DomainDemo audience figure, averaged over "
                                    "their citations of rated websites; the centre line is half Democrats, half "
                                    "Republicans. " if show_lean else "")
                                 + "Citations are counted where the editor added them, in analysed articles only."))),
        st.section("together", "All of them together",
                   "The citations these editors added, pooled, beside every citation in the analysed articles.",
                   st.card("Kinds of sources", st.stacks([("These editors", f"{n_cit:,} citations", fam_all)]
                                                        + [("All analysed articles", "", _all(ctx, "fam"))], FAM_CATS),
                           wide=True)
                   + "<div style='height:14px'></div>"
                   + st.card("Wikipedia's reliability list", st.stacks(
                       [("These editors", f"{n_cit:,} citations", rate_all)]
                       + [("All analysed articles", "", _all(ctx, "rate"))], RATING_CATS), wide=True)),
        st.section("method", "How it is worked out",
                   "Each word of today's text is credited to the editor who first added it (WikiWho); each "
                   "citation to the editor who added it. An editor is shown if they wrote at least 1% of analysed "
                   f"articles in {MIN_AREAS} or more topic areas; the {N_EDITORS} with the most such articles are "
                   "listed. Areas follow Wikipedia's own contentious-topic notices and WikiProject banners. "
                   "No account names, no personal details and nothing from outside Wikipedia is used.",
                   st.more("how-it-works.html#steps", "How authorship is worked out")),
    ]
    return page(f"Editors across topics · {NAME}", CSS + st.wrap("".join(sections)), "editors-across.html",
                description="Profiles of the editors who write across many topic areas: where they write and what they cite.")


_ALL = {}


def _all(ctx, what):
    if not _ALL:
        fam, rate = Counter(), Counter()
        for r in ctx.recs:
            for x in (r.get("sources") or {}).get("list", []):
                o = (ctx.outlets or {}).get(x["source"])
                fam[_family((o or {}).get("kind"))] += x["citations"]
                rate[_rating(o)] += x["citations"]
        _ALL.update(fam=fam, rate=rate)
    return _ALL[what]


# ------------------------------------------------------------------ sources
ASSOC_SHOWN = [("publisher", "Publisher"), ("owned by", "Owner"), ("parent organization", "Parent"),
               ("founded by", "Founded by"), ("member of", "Member of"), ("funded by", "Funded by"),
               ("sponsor", "Sponsor"), ("affiliation", "Affiliated with")]
NONE_LABELS = {"none recorded", "no entry"}


def _assoc(o):
    a = o.get("associations") or {}
    parts = []
    for k, name in ASSOC_SHOWN:
        xs = a.get(k) or []
        if not xs:
            continue
        names = ", ".join(escape(x["label"]) + ("" if x.get("sourced") else "†") for x in xs[:3])
        more = f" +{len(xs) - 3}" if len(xs) > 3 else ""
        parts.append(f"<b>{name}:</b> {names}{more}")
    return "<div class='assoc'>" + " · ".join(parts) + "</div>" if parts else ""


def sources_affiliations(ctx) -> str:
    from .site import NAME, area_name, label_chip, page, src_name
    outl = ctx.outlets or {}
    areas = _areas(ctx)
    cites, by_area = Counter(), defaultdict(Counter)
    for r in ctx.recs:
        a = ctx.areas.get(r["article"], "")
        for x in (r.get("sources") or {}).get("list", []):
            cites[x["source"]] += x["citations"]
            if a:
                by_area[x["source"]][a] += x["citations"]
    # one row per name: sources counted under several web addresses (bbc.com, bbc.co.uk) merged
    by_name, main = Counter(), {}
    for k, n in cites.most_common():
        if k in outl:
            nm = outl[k].get("name") or k
            by_name[nm] += n
            main.setdefault(nm, k)
    merged = {}
    for k in list(cites):
        if k in outl:
            m = main[outl[k].get("name") or k]
            if m != k:
                merged.setdefault(m, []).append(k)
    for m, ks in merged.items():
        for k in ks:
            by_area[m].update(by_area[k])
    ncites = {main[nm]: n for nm, n in by_name.items()}
    top = [main[nm] for nm, _ in by_name.most_common(N_SOURCES)]
    tot_all = sum(cites.values())
    hw = f"{max(260, 22 * len(areas))}px"

    # who stands behind the cited sources: owners/publishers and recorded labels, over all citations
    owners, labels = Counter(), Counter()
    with_label = 0
    for k, n in cites.items():
        o = outl.get(k) or {}
        a = o.get("associations") or {}
        for key in ("owned by", "parent organization", "publisher"):
            if a.get(key):
                owners[a[key][0]["label"]] += n
                break
        labs = [l for l in ((o.get("affiliation") or {}).get("labels") or []) if l not in NONE_LABELS]
        if labs:
            with_label += n
            for l in labs:
                labels[l] += n / len(labs)
    from .affiliation import show

    head = (f"<div class='row h'><div>Source</div><div class='num'>Citations</div>{_heat_head(areas)}"
            "<div>Wikipedia's list</div><div class='num'>Quality</div><div>Who shares it</div>"
            "<div>Recorded political labels</div></div>")
    rows = []
    for k in top:
        o = outl.get(k) or {}
        n = ncites[k]
        fmt = lambda v, sh, short=False: ((f"{sh * 100:.0f}" if sh >= .005 else "<1") if short else f"{v:,} citations ({sh * 100:.0f}% of its citations)")  # noqa: E731
        rate = _rating(o)
        rname = next((nm for kk, nm, _ in RATING_CATS if kk == rate), "")
        q = (o.get("independent_quality") or {}).get("score")
        dd = (o.get("audience_leaning_dd") or {}).get("score")
        labs = [l for l in ((o.get("affiliation") or {}).get("labels") or []) if l not in NONE_LABELS]
        chips = "".join(label_chip(l, ctx, o.get("name") or src_name(k, ctx)) for l in labs[:6])
        rows.append(
            f"<div class='row'><div><b>{escape(o.get('name') or src_name(k, ctx))}</b>"
            f"<small>{escape(o.get('kind') or 'kind not recorded')}{(' · ' + escape(', '.join(o['country']) if isinstance(o['country'], list) else o['country'])) if o.get('country') else ''}</small></div>"
            f"<div class='num'>{n:,}</div>" + _heat(areas, by_area[k], n, fmt)
            + f"<div><span class='tag'>{escape(rname)}</span></div>"
            + (f"<div class='num'>{q:.2f}</div>" if q is not None else "<div class='num fnote'>–</div>")
            + f"<div>{_lean(dd, o.get('name') or k) if dd is not None else '<span class=fnote>–</span>'}</div>"
            + f"<div class='chips'>{chips or '<span class=fnote>no political label recorded</span>'}</div>{_assoc(o)}</div>")
    table = f"<div class='fp-scroll'><div class='fp so' style='--hw:{hw}'>{head}{''.join(rows)}</div></div>"

    sections = [
        st.hero("Sources and their affiliations", "Who stands behind the most-cited sources",
                f"The {len(top)} sources cited most often across the analysed articles, each with what Wikidata and "
                "Wikipedia record about it: its owner or publisher, founders, memberships and any political label, "
                "beside Wikipedia's own rating, an independent quality score and who shares it. We add nothing of our "
                "own; a label shows Wikipedia's definition when you point at it."),
        st.stats([(f"{len(top)}", "sources shown", None),
                  (st.pct(sum(ncites[k] for k in top) / tot_all if tot_all else 0), "of all citations go to them", None),
                  (st.pct(with_label / tot_all if tot_all else 0), "of all citations go to a source with a recorded "
                   "political label", "From Wikidata's political alignment and ideology, and the source's own Wikipedia categories.")]),
        st.toc([("rows", "The most-cited sources"), ("owners", "Owners and publishers"), ("labels", "Recorded labels"),
                ("method", "Where this comes from")]),
        st.section("rows", "The most-cited sources",
                   "One row per source. The shaded cells show which topic areas cite it: the share of its citations "
                   "in each. Point at a cell, bar or label for its figure or definition.",
                   st.card("Sources, by citations", table, wide=True,
                           note="† not backed by a reference on Wikidata. Who shares it: of every 100 people sharing "
                                "the website on social media, how many are Democrats and how many Republicans "
                                "(DomainDemo, 2025); websites only.")),
        st.section("owners", "Owners and publishers",
                   "Citations across all analysed articles, grouped by the owner, parent organisation or publisher "
                   "Wikidata records for each source (the first of these that is recorded).",
                   st.card("Owners and publishers with the most citations",
                           st.hbars([(escape(nm), v, f"{v:,} citations", "") for nm, v in owners.most_common(20)]), wide=True)),
        st.section("labels", "Recorded political labels",
                   "Citations to sources that carry a recorded political label, by label. A source with several "
                   "labels is split equally between them. Labels are kept as recorded and never merged.",
                   st.card("Labels with the most citations",
                           st.hbars([(escape(show(l)), round(v), f"{v:,.0f} citations", "") for l, v in labels.most_common(20)]),
                           wide=True, note="Most citations go to sources with no political label recorded.")),
        st.section("method", "Where this comes from",
                   "Associations and labels come from Wikidata (owner, parent organisation, publisher, founder, "
                   "member of, funder, sponsor, affiliation, political alignment, ideology) and the political "
                   "categories on the source's own Wikipedia article. Ratings: Wikipedia's reliability list, Lin "
                   "and colleagues' quality score (news websites), DomainDemo's audience figure (websites).",
                   st.more("sources-detail.html", "Sources in detail")),
    ]
    return page(f"Sources and their affiliations · {NAME}", CSS + st.wrap("".join(sections)),
                "sources-affiliations.html",
                description="The most-cited sources with their recorded owners, publishers, memberships and political labels.")
