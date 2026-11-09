"""Article page: each main figure beside the same figure for the other analysed articles in the
same topic area. Every peer is a faint tick, the middle article a dark line, this article a dot.
The same figures as elsewhere on the page; nothing is ranked or judged.
"""

import math
from html import escape

MIN_PEERS = 5
LEAN_MIN_COVER = 0.10

# (key, label, scale, what it is); scale: pct 0-1, log for counts, lean -0.8..0.8
WRITERS = [("t1", "Written by the main writer", "pct", "Share of today's text by the single biggest contributor."),
           ("n50", "Editors who wrote half the text", "log", "The fewest editors whose words make up half of today's text."),
           ("sc", "Written by editors Wikipedia sanctioned", "pct", "Topic ban in this area, site ban, or sockpuppetry."),
           ("sv", "New text still there a year later", "pct", "Of all words ever added, the share that lasted a year.")]
SOURCES = [("ci", "Citations", "log", "Footnotes in the article."),
           ("ln", "Citations with a link to follow", "pct", "Footnotes a reader can open."),
           ("wl", "Citations to sources on Wikipedia's reliability list", "pct",
            "Wikipedia's list of perennial sources: reliable, no consensus, unreliable, deprecated."),
           ("le", "Who shares its cited websites", "lean",
            "Audience leaning of its cited websites: −1 mostly Democrats, +1 mostly Republicans (DomainDemo). "
            f"Shown when at least {int(LEAN_MIN_COVER * 100)}% of citations are rated.")]

CSS = """<style>
.gl .card.wide{grid-column:1/-1}
.pr{display:grid;grid-template-columns:minmax(150px,240px) minmax(0,1fr) minmax(90px,150px);gap:4px 16px;align-items:center;
 margin:6px 0 0}
.pr .l{font-size:.86rem;line-height:1.25}
.pr .l small{display:block;color:var(--muted);font-size:.72rem}
.pr svg{width:100%;height:auto;display:block;overflow:visible}
.pr .tk{stroke:var(--muted);stroke-width:1;opacity:.35}
.pr .md{stroke:var(--fg);stroke-width:2}
.pr .me{fill:var(--g-c2);stroke:var(--bg);stroke-width:1.5}
.pr .ax{fill:var(--muted);font-size:11px}
.pr .v{font:.82rem/1.3 system-ui,-apple-system,"Segoe UI",sans-serif;font-variant-numeric:tabular-nums}
.pr .v small{display:block;color:var(--muted);font-size:.72rem}
.pr-key{display:flex;flex-wrap:wrap;gap:4px 16px;font:.76rem system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted);
 margin:8px 0 2px}
.pr-key i{display:inline-block;vertical-align:-1px;margin-right:5px}
@media (max-width:640px){.pr{grid-template-columns:1fr 1fr}.pr svg{grid-column:1/-1;order:3}}
</style>"""


def _values(rec, ctx):
    from .site import cited_figures
    from .readers import _rating
    au, ac, so = rec["authorship"], rec["accountability"], rec.get("sources") or {}
    out = {"t1": (au.get("top_shares") or {}).get("1"), "n50": au.get("editors_for_50pct"),
           "sc": au.get("sanctioned_share"), "sv": ((au.get("survival_article") or {}).get("365d") or {}).get("rate"),
           "ci": so.get("citations"),
           "ln": so.get("with_link", 0) / so["citations"] if so.get("citations") else None}
    tot = sum(x["citations"] for x in so.get("list", []))
    if tot and ctx.outlets:
        out["wl"] = sum(x["citations"] for x in so.get("list", [])
                        if _rating(ctx.outlets.get(x["source"])) != "none") / tot
        le = cited_figures(rec, ctx).get("audience_leaning_dd") or {}
        out["le"] = le.get("mean") if le.get("citations_covered", 0) >= LEAN_MIN_COVER else None
    return out


def _table(ctx):
    """{area: {article: values}}, worked out once per build."""
    if not hasattr(ctx, "_peers"):
        from .site import _is_thin
        t = {}
        for r in ctx.recs:
            v = _values(r, ctx)
            if _is_thin(r):
                v["sc_thin"] = True
            t.setdefault(ctx.areas.get(r["article"], "") or "", {})[r["article"]] = v
        ctx._peers = t
    return ctx._peers


def _fmt(v, scale):
    if v is None:
        return "–"
    if scale == "pct":
        return f"{100 * v:.0f}%"
    if scale == "lean":
        r = round((1 + v) / 2 * 100)
        return f"{v:+.2f} ({100 - r} D / {r} R)"
    return f"{v:,.0f}"


def _x(v, scale, lo, hi, W=560):
    if scale == "log":
        v, lo, hi = math.log10(max(v, 1)), math.log10(max(lo, 1)), math.log10(max(hi, 1))
    if hi <= lo:
        return W / 2
    return (min(max(v, lo), hi) - lo) / (hi - lo) * W


def _strip(mine, vals, scale):
    W = 560
    if scale == "pct":
        lo, hi, ticks = 0, 1, [(0, "0%"), (1, "100%")]
    elif scale == "lean":
        lo, hi, ticks = -0.8, 0.8, [(-0.8, "D"), (0, "0"), (0.8, "R")]
    else:
        lo, hi = 1, max(vals + [mine or 1])
        ticks = [(1, "1"), (hi, f"{hi:,.0f}")]
    s = sorted(vals)
    med = s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2
    out = [f"<svg viewBox='-8 0 {W + 16} 32' aria-hidden='true'>"]
    for v in vals:
        x = _x(v, scale, lo, hi)
        out.append(f"<line class='tk' x1='{x:.1f}' x2='{x:.1f}' y1='6' y2='18'/>")
    xm = _x(med, scale, lo, hi)
    out.append(f"<line class='md' x1='{xm:.1f}' x2='{xm:.1f}' y1='3' y2='21'/>")
    if mine is not None:
        out.append(f"<circle class='me' cx='{_x(mine, scale, lo, hi):.1f}' cy='12' r='5.5'/>")
    for v, t in ticks:
        out.append(f"<text class='ax' x='{_x(v, scale, lo, hi):.1f}' y='31' text-anchor='middle'>{escape(t)}</text>")
    out.append("</svg>")
    return "".join(out), med


def card(rec, ctx, which: str) -> str:
    """which: "writers" or "sources"."""
    from .site import area_name
    area = ctx.areas.get(rec["article"], "") or ""
    peers = _table(ctx).get(area, {})
    others = {a: v for a, v in peers.items() if a != rec["article"]}
    if len(others) < MIN_PEERS:
        return ""
    mine = peers.get(rec["article"]) or _values(rec, ctx)
    rows = []
    for key, label, scale, what in (WRITERS if which == "writers" else SOURCES):
        vals = [v[key] for v in others.values() if v.get(key) is not None and not (key == "sc" and v.get("sc_thin"))]
        if len(vals) < MIN_PEERS:
            continue
        m = mine.get(key)
        svg, med = _strip(m, vals, scale)
        thin = key == "sc" and mine.get("sc_thin")
        rows.append(f"<div class='l' title='{escape(what, quote=True)}'>{escape(label)}"
                    f"<small>{len(vals)} other articles</small></div>{svg}"
                    f"<div class='v'><b>{escape(_fmt(m, scale))}</b>{' †' if thin else ''}"
                    f"<small>middle article {escape(_fmt(med, scale))}</small></div>")
    if not rows:
        return ""
    name = area_name(area).split(" (")[0]
    title = ("How its writing compares" if which == "writers" else "How its sourcing compares")
    note = ("† The sanctions list for this area is less complete, so the real figure is probably higher. "
            if which == "writers" and mine.get("sc_thin") else "")
    return (f"<div class='card wide'><h3>{escape(title)}</h3><p class='big'>This article beside the other analysed "
            f"articles in {escape(name)}. Hover a figure's name for what it measures.</p>"
            "<div class='pr-key'><span><svg width='12' height='12' style='vertical-align:-1px;margin-right:5px'>"
            "<circle cx='6' cy='6' r='5' fill='var(--g-c2)'/></svg>this article</span>"
            "<span><svg width='10' height='12' style='vertical-align:-1px;margin-right:5px'><line x1='5' x2='5' y1='0' "
            "y2='12' stroke='var(--fg)' stroke-width='2'/></svg>middle article</span>"
            "<span><svg width='10' height='12' style='vertical-align:-1px;margin-right:5px'><line x1='5' x2='5' y1='2' "
            "y2='10' stroke='var(--muted)' stroke-width='1'/></svg>each other article</span></div>"
            f"<div class='pr'>{''.join(rows)}</div>"
            + (f"<p class='what'>{escape(note)}</p>" if note else "") + "</div>")
