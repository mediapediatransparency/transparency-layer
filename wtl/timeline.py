"""Edit timeline for an article page: edits per year as bars, with the periods of page protection
drawn as a band on the same time axis (data/activity.json, wtl/activity.py). Plain SVG, no
script: every bar and band has its exact figure on hover or keyboard focus, and the same figures
are in a table below it.
"""

import datetime as dt
from html import escape

LEVELS = [   # (level in the protection log, plain name, colour token); more restrictive is stronger
    ("autoconfirmed", "accounts at least 4 days old with 10 edits", "var(--tl-p1)"),
    ("extendedconfirmed", "accounts at least 30 days old with 500 edits", "var(--tl-p2)"),
    ("sysop", "administrators only", "var(--tl-p3)"),
    ("unknown", "level not recorded in the log entry", "var(--g-rest)"),
]
NAME = {k: n for k, n, _ in LEVELS}
COLOUR = {k: c for k, _, c in LEVELS}

CSS = """<style>
:root{--tl-bar:#2a78d6;--tl-p1:#f19a62;--tl-p2:#d95926;--tl-p3:#9c3e14}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--tl-bar:#3987e5;--tl-p1:#a8461a;--tl-p2:#e2662d;--tl-p3:#f7a678}}
:root[data-theme="dark"]{--tl-bar:#3987e5;--tl-p1:#a8461a;--tl-p2:#e2662d;--tl-p3:#f7a678}
.tl{margin:10px 0 6px}
.tl svg{width:100%;height:auto;display:block;overflow:visible}
.tl .bar{fill:var(--tl-bar)}
.tl .bar.part{fill:var(--tl-bar);fill-opacity:.45}
.tl g.hit:hover .bar,.tl g.hit:focus .bar{fill-opacity:.75}
.tl g.hit:focus{outline:none}
.tl g.hit:focus rect.hl{stroke:var(--fg);stroke-width:1.5}
.tl .grid{stroke:var(--line);stroke-width:1}
.tl .axis{fill:var(--muted);font-size:11px}
.tl .val{fill:var(--fg);font-size:11px}
.tl .lbl{fill:var(--muted);font-size:11px}
.tl .mark{stroke:var(--fg);stroke-width:1;stroke-dasharray:3 3}
.tl .key{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:.82rem;color:var(--muted);margin:4px 0 0}
.tl .key i{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-2px;margin-right:5px}
.tl .tip{font-size:.82rem;color:var(--muted);min-height:1.3em;margin:2px 0 0}
</style>"""


def _yfrac(d: str) -> float:
    """A date as a fractional year (2024-07-01 -> about 2024.5)."""
    t = dt.date.fromisoformat(d[:10])
    start = dt.date(t.year, 1, 1)
    return t.year + (t - start).days / ((dt.date(t.year + 1, 1, 1) - start).days)


def _nice(m: int) -> int:
    for step in (1, 2, 5):
        for p in range(0, 7):
            s = step * 10 ** p
            if m / s <= 4:
                return s
    return max(1, m // 4)


def svg(e: dict, analysed: str) -> str:
    """The chart for one article's activity entry; analysed is the analysed revision's date."""
    by = {int(k): v for k, v in (e.get("edits_by_year") or {}).items()}
    if not by:
        return ""
    y0, y1 = min(by), max(max(by), int(analysed[:4]))
    years = list(range(y0, y1 + 1))
    W, L, R, T = 760, 44, 8, 16
    BH = 170                     # bar area height
    band_y = T + BH + 26         # protection band
    H = band_y + 30
    cw = (W - L - R) / len(years)
    x = lambda yf: L + (yf - y0) * cw   # noqa: E731
    top = max(by.values()) or 1
    step = _nice(top)
    ymax = step * -(-top // step)
    out = [f"<svg viewBox='0 0 {W} {H}' role='img' aria-label='Edits per year from {y0} to {y1}, "
           f"with page protection below'>"]
    for g in range(0, ymax + 1, step):                    # recessive grid and y labels
        yy = T + BH - BH * g / ymax
        out.append(f"<line class='grid' x1='{L}' x2='{W - R}' y1='{yy:.1f}' y2='{yy:.1f}'/>"
                   f"<text class='axis' x='{L - 6}' y='{yy + 4:.1f}' text-anchor='end'>{g:,}</text>")
    peak = max(by, key=lambda k: by[k])
    for i, yr in enumerate(years):
        n = by.get(yr, 0)
        h = BH * n / ymax
        bx, bw = L + i * cw + 1, cw - 2                    # 2px gap between bars
        part = yr == int(analysed[:4])
        note = f" (up to {analysed}, part of the year)" if part else ""
        r = min(4, bw / 2, h)
        bar = (f"<path class='bar{' part' if part else ''}' d='M{bx:.1f},{T + BH:.1f} v{-(h - r):.1f} "
               f"q0,{-r:.1f} {r:.1f},{-r:.1f} h{bw - 2 * r:.1f} q{r:.1f},0 {r:.1f},{r:.1f} v{h - r:.1f} z'/>"
               if h > 0 else "")
        out.append(f"<g class='hit' tabindex='0'><title>{yr}: {n:,} edits{note}</title>"
                   f"<rect class='hl' x='{bx:.1f}' y='{T}' width='{bw:.1f}' height='{BH}' fill='transparent'/>{bar}</g>")
        if yr == peak or part:                             # selective direct labels
            out.append(f"<text class='val' x='{bx + bw / 2:.1f}' y='{T + BH - h - 5:.1f}' "
                       f"text-anchor='middle'>{n:,}</text>")
    lab_every = 1 if len(years) <= 12 else 2 if len(years) <= 24 else 5
    for i, yr in enumerate(years):                         # x axis
        if yr % lab_every == 0 or i == 0:
            out.append(f"<text class='axis' x='{L + (i + .5) * cw:.1f}' y='{T + BH + 15}' "
                       f"text-anchor='middle'>{yr}</text>")
    # protection band
    pr = e.get("protection") or {}
    out.append(f"<text class='lbl' x='{L - 6}' y='{band_y + 13}' text-anchor='end'>Protected</text>"
               f"<rect x='{L}' y='{band_y}' width='{W - L - R}' height='18' rx='4' fill='var(--g-soft)'/>")
    for p in pr.get("periods") or []:
        a, b = _yfrac(p["from"]), _yfrac(p.get("to") or analysed)
        px, pw = x(a), max(2.0, x(b) - x(a))
        out.append(f"<g class='hit' tabindex='0'><title>{escape(p['from'])} to {escape(p.get('to') or analysed)}: "
                   f"protected, {escape(NAME.get(p['level'], p['level']))}</title><rect x='{px:.1f}' y='{band_y}' "
                   f"width='{pw:.1f}' height='18' rx='2' fill='{COLOUR.get(p['level'], 'var(--g-rest)')}'/></g>")
    out.append("</svg>")
    used = [k for k, _, _ in LEVELS if any(p["level"] == k for p in pr.get("periods") or [])]
    key = ("<div class='key'><span><i style='background:var(--tl-bar)'></i>edits in the year</span>"
           f"<span><i style='background:var(--tl-bar);opacity:.45'></i>{escape(analysed[:4])}, up to the analysed revision</span>"
           + "".join(f"<span><i style='background:{COLOUR[k]}'></i>protected, {escape(NAME[k])}</span>" for k in used)
           + "</div>")
    table = ("<details><summary class='small'>The same figures as a table</summary><div class='scroll'><table>"
             "<tr><th>Year</th><th class='n'>Edits</th></tr>"
             + "".join(f"<tr><td>{yr}</td><td class='n'>{by.get(yr, 0):,}</td></tr>" for yr in years)
             + "</table>"
             + ("<table><tr><th>Protected from</th><th>to</th><th>Who could edit</th></tr>"
                + "".join(f"<tr><td>{escape(p['from'])}</td><td>{escape(p.get('to') or analysed)}</td>"
                          f"<td>{escape(NAME.get(p['level'], p['level']))}</td></tr>" for p in pr.get("periods") or [])
                + "</table>" if pr.get("periods") else "")
             + "</div></details>")
    return (f"<div class='tl'>{''.join(out)}{key}<p class='tip'>Point at or tab to a bar or band for its "
            f"exact figure.</p>{table}</div>")
