"""Building blocks for the site's reader pages (Sources, Leaning, Editors, the article lists):
a page opening, figure tiles, sections that open with one plain line, and charts drawn as plain
HTML/SVG with an exact figure on hover or keyboard focus and a table view where it helps.

Colours come from the article charts (wtl/glance.py): a blue ramp for ordered groups, fixed
categorical hues in a fixed order (never cycled; a sixth group folds into "Other"), grey for
"not known" or "the rest". Text never takes a series colour. Nothing here interprets a figure.
"""

from html import escape

from .glance import GLANCE_CSS

CAT = ["var(--g-c1)", "var(--g-c2)", "var(--g-c3)", "var(--g-c4)", "var(--g-c5)"]
REST = "var(--g-rest)"
RAMP = ["var(--g-o1)", "var(--g-o2)", "var(--g-o3)", "var(--g-o4)"]

CSS = GLANCE_CSS + """<style>
.st-hero{padding:22px 0 6px}
.st-hero .kicker{font:600 .72rem/1 system-ui,-apple-system,"Segoe UI",sans-serif;letter-spacing:.16em;
 text-transform:uppercase;color:var(--accent);margin:0 0 12px}
.st-hero h1{font-size:clamp(1.9rem,3.6vw,2.8rem);line-height:1.1;letter-spacing:-.012em;margin:0 0 14px;max-width:24ch}
.st-hero .lede{font-size:1.1rem;color:var(--muted);max-width:68ch;margin:0}
.st-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:0;
 border:1px solid var(--line);border-radius:14px;overflow:hidden;margin:22px 0 0}
.st-stats div{background:var(--bg);padding:16px 18px;box-shadow:1px 0 0 var(--line),0 1px 0 var(--line)}
.st-stats b{display:block;font:600 1.7rem/1.1 Georgia,"Iowan Old Style",serif;font-variant-numeric:tabular-nums}
.st-stats span{font:.8rem/1.35 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted)}
.st-toc{display:flex;flex-wrap:wrap;gap:6px;margin:22px 0 0;font:.86rem system-ui,-apple-system,"Segoe UI",sans-serif}
.st-toc a{padding:6px 12px;border:1px solid var(--line);border-radius:999px;text-decoration:none;color:var(--fg)}
.st-toc a:hover{background:var(--soft)}
.st-sec{margin:52px 0 0;scroll-margin-top:20px}
.st-sec>h2{border:0;font-size:1.45rem;margin:0 0 4px}
.st-sec>.one{color:var(--muted);margin:0 0 16px;max-width:80ch}
.st-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.st-grid.three{grid-template-columns:repeat(3,minmax(0,1fr))}
.st-card{border:1px solid var(--line);border-radius:14px;padding:18px 20px;background:var(--bg);min-width:0;overflow-x:auto}
.st-card.wide{grid-column:1/-1}
.st-card h3{font-size:1.05rem;margin:0 0 4px;line-height:1.3;border:0}
.st-card .q{font-size:.88rem;color:var(--muted);margin:0 0 14px;max-width:none}
.st-card .fnote{font-size:.8rem;color:var(--muted);margin:12px 0 0;max-width:none}
.st-more{display:inline-block;margin:14px 0 0;font:.88rem system-ui,-apple-system,"Segoe UI",sans-serif;text-decoration:none}
.st-more::after{content:" →"}
.hb{display:grid;grid-template-columns:minmax(120px,max-content) minmax(0,1fr) auto;gap:5px 12px;align-items:center;
 font-size:.88rem}
.hb .l{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px}
.hb .t{height:14px;background:var(--g-soft);border-radius:4px;position:relative;min-width:0}
.hb .t i{position:absolute;left:0;top:0;bottom:0;border-radius:4px;background:var(--g-o2)}
.hb .v{font:600 .82rem system-ui,-apple-system,"Segoe UI",sans-serif;font-variant-numeric:tabular-nums;text-align:right}
.hb .s{grid-column:1/-1;font-size:.74rem;color:var(--muted);margin:-3px 0 4px}
.sr{display:grid;grid-template-columns:minmax(110px,220px) minmax(0,1fr);gap:6px 14px;align-items:center;font-size:.86rem}
.sr .l{line-height:1.25}
.sr .l small{display:block;color:var(--muted);font-size:.74rem}
.sr .bar{display:flex;gap:2px;height:22px;margin:0}
.sr .seg{border-radius:3px;min-width:0;cursor:default}
.sr .seg:focus-visible{outline:2px solid var(--fg);outline-offset:1px}
.st-legend{display:flex;flex-wrap:wrap;gap:4px 14px;font:.8rem system-ui,-apple-system,"Segoe UI",sans-serif;
 color:var(--muted);margin:0 0 12px;padding:0;list-style:none}
.st-legend li{display:flex;align-items:center;gap:6px}
.st-legend i{width:10px;height:10px;border-radius:3px;display:inline-block}
.ds{width:100%;height:auto;display:block;overflow:visible}
.ds .lab{fill:var(--fg);font-size:12px}
.ds .sub{fill:var(--muted);font-size:10.5px}
.ds .ax{fill:var(--muted);font-size:10.5px}
.ds .trk{stroke:var(--line);stroke-width:1}
.ds .ref{stroke:var(--fg);stroke-width:1;stroke-dasharray:3 3;opacity:.7}
.ds .med{stroke:var(--fg);stroke-width:2.5;stroke-linecap:round}
.ds circle{fill:var(--g-o2);fill-opacity:.55;stroke:var(--bg);stroke-width:.8}
.ds a:hover circle,.ds a:focus circle{fill-opacity:1;stroke:var(--fg)}
.ds.db circle.d1{fill:var(--bg);fill-opacity:1;stroke:var(--g-o2);stroke-width:2.2}
.ds.db circle.d2{fill:var(--g-c2);fill-opacity:1;stroke:var(--bg);stroke-width:1}
.ds.db g:focus{outline:none}.ds.db g:focus .lab,.ds.db g:hover .lab{text-decoration:underline}
:root{--lr-l:#2a78d6;--lr-c:#b4b3ad;--lr-r:#e34948}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--lr-l:#3987e5;--lr-c:#56554f;--lr-r:#e66767}}
:root[data-theme="dark"]{--lr-l:#3987e5;--lr-c:#56554f;--lr-r:#e66767}
.hist{width:100%;height:auto;display:block}
.hist .b{fill:var(--g-o2)}
.hist g:hover .b,.hist g:focus .b{fill:var(--g-o1)}
.hist g:focus{outline:none}
.hist text{fill:var(--muted);font-size:10.5px}
.hist .val{fill:var(--fg)}
.st-tech{margin:56px 0 0;padding:20px 24px;border-radius:14px;background:var(--soft)}
.st-tech h2{border:0;font-size:1.1rem;margin:0 0 6px}
.st-tech p{margin:0 0 10px;color:var(--muted)}
.st-tech .links{display:flex;flex-wrap:wrap;gap:8px}
.st-tech .links a{padding:7px 12px;border-radius:999px;background:var(--bg);border:1px solid var(--line);
 text-decoration:none;font:.86rem system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--fg)}
#stip{position:fixed;pointer-events:none;background:var(--fg);color:var(--bg);font:.8rem/1.35 system-ui,-apple-system,"Segoe UI",sans-serif;
 padding:5px 8px;border-radius:6px;max-width:280px;display:none;z-index:60}
@media (max-width:900px){.st-grid,.st-grid.three{grid-template-columns:1fr}}
@media (max-width:560px){.sr{grid-template-columns:1fr}.hb .l{max-width:150px}}
@media (max-width:760px){.ds{min-width:720px}}
</style>"""

JS = """<div id="stip" role="tooltip"></div><script>
(function(){var t=document.getElementById('stip');
function show(e){var s=e.target.closest('[data-tip]');if(!s)return;t.textContent=s.dataset.tip;t.style.display='block';
 var r=s.getBoundingClientRect(),x=(e.clientX||r.left+r.width/2)+12,y=(e.clientY||r.bottom)+14;
 t.style.left=Math.max(8,Math.min(x,innerWidth-t.offsetWidth-8))+'px';t.style.top=Math.min(y,innerHeight-t.offsetHeight-8)+'px';}
function hide(){t.style.display='none';}
document.querySelectorAll('.st [data-tip]').forEach(function(s){if(!s.getAttribute('aria-label'))s.setAttribute('aria-label',s.dataset.tip);
 s.addEventListener('mousemove',show);s.addEventListener('mouseleave',hide);s.addEventListener('focus',show);s.addEventListener('blur',hide);});})();
</script>"""


def pct(x, d=0):
    return "–" if x is None else f"{100 * x:.{d}f}%"


def num(n):
    return f"{n:,}" if isinstance(n, int) else f"{n:,.0f}"


def hero(kicker: str, title: str, lede: str) -> str:
    return (f"<section class='st-hero'><p class='kicker'>{escape(kicker)}</p><h1>{escape(title)}</h1>"
            f"<p class='lede'>{lede}</p></section>")


def stats(items) -> str:
    """items: [(value text, label, tooltip or None)]."""
    return "<div class='st-stats'>" + "".join(
        f"<div{f' data-tip={chr(39)}{escape(tip, quote=True)}{chr(39)} tabindex=0' if tip else ''}>"
        f"<b>{escape(v)}</b><span>{escape(l)}</span></div>" for v, l, tip in items) + "</div>"


def toc(items) -> str:
    """items: [(anchor, label)]."""
    return "<nav class='st-toc' aria-label='On this page'>" + "".join(
        f"<a href='#{a}'>{escape(l)}</a>" for a, l in items) + "</nav>"


def section(anchor: str, title: str, one: str, body: str) -> str:
    return (f"<section class='st-sec' id='{anchor}'><h2>{escape(title)}</h2><p class='one'>{one}</p>{body}</section>")


def card(title: str, body: str, q: str = "", note: str = "", wide: bool = False) -> str:
    return (f"<div class='st-card{' wide' if wide else ''}'><h3>{escape(title)}</h3>"
            + (f"<p class='q'>{q}</p>" if q else "") + body
            + (f"<p class='fnote'>{note}</p>" if note else "") + "</div>")


def grid(*cards, three=False) -> str:
    return f"<div class='st-grid{' three' if three else ''}'>" + "".join(cards) + "</div>"


def more(href: str, text: str) -> str:
    return f"<a class='st-more' href='{href}'>{escape(text)}</a>"


def legend(cats) -> str:
    """cats: [(name, colour)]."""
    return "<ul class='st-legend'>" + "".join(
        f"<li><i style='background:{c}'></i>{escape(n)}</li>" for n, c in cats) + "</ul>"


def hbars(rows, fmt=lambda v: f"{v:,}", top=None, colour=None) -> str:
    """Ranked horizontal bars. rows: [(label html, value, tooltip, sub html or "")]."""
    if not rows:
        return "<p class='fnote'>Nothing to show.</p>"
    top = top or max(v for _, v, _, _ in rows) or 1
    out = ["<div class='hb'>"]
    for lab, v, tip, sub in rows:
        w = 100 * v / top
        out.append(f"<div class='l' title='{escape(_plain(lab), quote=True)}'>{lab}</div>"
                   f"<div class='t' data-tip='{escape(tip, quote=True)}' tabindex='0'>"
                   f"<i style='width:{w:.1f}%{f';background:{colour}' if colour else ''}'></i></div>"
                   f"<div class='v'>{escape(fmt(v))}</div>" + (f"<div class='s'>{sub}</div>" if sub else ""))
    out.append("</div>")
    return "".join(out)


def stacks(rows, cats, show_legend=True) -> str:
    """100% stacked bars, one per row. rows: [(label, sub, {cat key: value})];
    cats: [(key, name, colour)] in a fixed order."""
    out = [legend([(n, c) for _, n, c in cats]) if show_legend else "", "<div class='sr'>"]
    for lab, sub, vals in rows:
        tot = sum(vals.get(k, 0) for k, _, _ in cats)
        out.append(f"<div class='l'>{escape(lab)}" + (f"<small>{escape(sub)}</small>" if sub else "") + "</div>")
        if not tot:
            out.append("<div class='bar'><span class='fnote'>none</span></div>")
            continue
        segs = []
        for k, n, c in cats:
            v = vals.get(k, 0)
            if v <= 0:
                continue
            tip = f"{lab}: {n}, {100 * v / tot:.0f}% ({v:,.0f})"
            segs.append(f"<div class='seg' tabindex='0' style='flex:{100 * v / tot:.2f};background:{c}' "
                        f"data-tip='{escape(tip, quote=True)}'></div>")
        out.append(f"<div class='bar' role='img' aria-label='{escape(lab, quote=True)}'>{''.join(segs)}</div>")
    out.append("</div>")
    return "".join(out)


def dotstrip(groups, lo, hi, ticks, ref=None, ref_label="", fmt=lambda v: f"{v:+.2f}") -> str:
    """One row per group, each article a dot on a common axis, with the group's median as a tick.
    groups: [(label, sub, [(value, tooltip, href)])]."""
    W, L, R, rowh, top = 900, 230, 20, 30, 22
    H = top + rowh * len(groups) + 26
    x = lambda v: L + (min(max(v, lo), hi) - lo) / (hi - lo) * (W - L - R)  # noqa: E731
    out = [f"<svg class='ds' viewBox='0 0 {W} {H}' role='img' aria-label='Each dot is one article'>"]
    for t in ticks:
        out.append(f"<line class='trk' x1='{x(t):.1f}' x2='{x(t):.1f}' y1='{top - 6}' y2='{H - 22}'/>"
                   f"<text class='ax' x='{x(t):.1f}' y='{H - 6}' text-anchor='middle'>{escape(fmt(t))}</text>")
    if ref is not None:
        out.append(f"<line class='ref' x1='{x(ref):.1f}' x2='{x(ref):.1f}' y1='{top - 14}' y2='{H - 22}'/>"
                   f"<text class='ax' x='{x(ref):.1f}' y='{top - 16}' text-anchor='middle'>{escape(ref_label)}</text>")
    for i, (lab, sub, pts) in enumerate(groups):
        cy = top + rowh * i + rowh / 2
        out.append(f"<text class='lab' x='{L - 12}' y='{cy + 1}' text-anchor='end'>{escape(lab[:34])}</text>"
                   + (f"<text class='sub' x='{L - 12}' y='{cy + 12}' text-anchor='end'>{escape(_clip(sub, 34))}</text>" if sub else ""))
        out.append(f"<line class='trk' x1='{L}' x2='{W - R}' y1='{cy:.1f}' y2='{cy:.1f}' opacity='.5'/>")
        vals = sorted(v for v, _, _ in pts)
        for k, (v, tip, href) in enumerate(pts):
            jitter = ((k * 7) % 5 - 2) * 2.2
            dot = f"<circle cx='{x(v):.1f}' cy='{cy + jitter:.1f}' r='4.2'><title>{escape(tip)}</title></circle>"
            out.append(f"<a href='{escape(href, quote=True)}'>{dot}</a>" if href else dot)
        if vals:
            m = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
            out.append(f"<line class='med' x1='{x(m):.1f}' x2='{x(m):.1f}' y1='{cy - 9:.1f}' y2='{cy + 9:.1f}'>"
                       f"<title>{escape(lab)}: middle article {fmt(m)}</title></line>")
    out.append("</svg>")
    return "".join(out)


def histogram(bins, label="", fmt=lambda v: f"{v:,}") -> str:
    """Column chart. bins: [(bin label, count, tooltip)]."""
    if not bins:
        return ""
    W, H, B, T = 640, 180, 24, 18
    top = max(c for _, c, _ in bins) or 1
    cw = W / len(bins)
    out = [f"<svg class='hist' viewBox='0 0 {W} {H}' role='img' aria-label='{escape(label, quote=True)}'>"]
    for i, (lab, c, tip) in enumerate(bins):
        h = (H - B - T) * c / top
        bx = i * cw + 2
        bw = cw - 4
        r = min(4, bw / 2, h)
        path = (f"M{bx:.1f},{H - B} v{-(h - r):.1f} q0,{-r:.1f} {r:.1f},{-r:.1f} h{bw - 2 * r:.1f} "
                f"q{r:.1f},0 {r:.1f},{r:.1f} v{h - r:.1f} z") if h > 0 else ""
        out.append(f"<g tabindex='0'><title>{escape(tip)}</title>"
                   + (f"<path class='b' d='{path}'/>" if path else "")
                   + f"<text class='val' x='{bx + bw / 2:.1f}' y='{H - B - h - 5:.1f}' text-anchor='middle'>{escape(fmt(c))}</text>"
                   + f"<text x='{bx + bw / 2:.1f}' y='{H - 7}' text-anchor='middle'>{escape(lab)}</text></g>")
    out.append("</svg>")
    return "".join(out)


def tech(title: str, text: str, links) -> str:
    """The way into the detailed pages. links: [(href, label)]."""
    return (f"<aside class='st-tech'><h2>{escape(title)}</h2><p>{text}</p><div class='links'>"
            + "".join(f"<a href='{h}'>{escape(l)}</a>" for h, l in links) + "</div></aside>")


def wrap(body: str) -> str:
    return f"{CSS}<div class='st'>{body}</div>{JS}"


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def _plain(s: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", s)


def dumbbell(rows, lo, hi, ticks, names, fmt=lambda v: f"{v:+.2f}", ref=None, ref_label="") -> str:
    """Two values per row joined by a line: names = (first, second); first is a hollow dot, second solid.
    rows: [(label, sub, first or None, second or None, tooltip)]."""
    W, L, R, rowh, top = 900, 230, 20, 30, 26
    H = top + rowh * len(rows) + 26
    x = lambda v: L + (min(max(v, lo), hi) - lo) / (hi - lo) * (W - L - R)  # noqa: E731
    out = [f"<svg class='ds db' viewBox='0 0 {W} {H}' role='img' aria-label='{escape(names[0])} and {escape(names[1])}'>"]
    for t in ticks:
        out.append(f"<line class='trk' x1='{x(t):.1f}' x2='{x(t):.1f}' y1='{top - 6}' y2='{H - 22}'/>"
                   f"<text class='ax' x='{x(t):.1f}' y='{H - 6}' text-anchor='middle'>{escape(fmt(t))}</text>")
    if ref is not None:
        out.append(f"<line class='ref' x1='{x(ref):.1f}' x2='{x(ref):.1f}' y1='{top - 14}' y2='{H - 22}'/>"
                   f"<text class='ax' x='{x(ref):.1f}' y='{top - 16}' text-anchor='middle'>{escape(ref_label)}</text>")
    for i, (lab, sub, a, b, tip) in enumerate(rows):
        cy = top + rowh * i + rowh / 2
        out.append(f"<g tabindex='0'><title>{escape(tip)}</title>"
                   f"<text class='lab' x='{L - 12}' y='{cy + 1}' text-anchor='end'>{escape(lab[:34])}</text>"
                   + (f"<text class='sub' x='{L - 12}' y='{cy + 12}' text-anchor='end'>{escape(_clip(sub, 34))}</text>" if sub else ""))
        if a is not None and b is not None:
            out.append(f"<line x1='{x(a):.1f}' x2='{x(b):.1f}' y1='{cy:.1f}' y2='{cy:.1f}' stroke='var(--muted)' stroke-width='2'/>")
        if a is not None:
            out.append(f"<circle class='d1' cx='{x(a):.1f}' cy='{cy:.1f}' r='5.5'/>")
        if b is not None:
            out.append(f"<circle class='d2' cx='{x(b):.1f}' cy='{cy:.1f}' r='5.5'/>")
        out.append("</g>")
    out.append("</svg>")
    return (legend_dots(names) + "".join(out))


def legend_dots(names) -> str:
    return ("<ul class='st-legend'><li><svg width='12' height='12'><circle cx='6' cy='6' r='4.5' fill='var(--bg)' "
            f"stroke='var(--g-o2)' stroke-width='2'/></svg>{escape(names[0])}</li><li><svg width='12' height='12'>"
            f"<circle cx='6' cy='6' r='5' fill='var(--g-c2)'/></svg>{escape(names[1])}</li></ul>")
