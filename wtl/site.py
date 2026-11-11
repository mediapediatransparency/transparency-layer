"""Public website (GitHub Pages) built from the stored records: home, article pages, comparison,
how it works, objective, about. Written for journalists and general readers: every figure is a
full sentence that names what it is a share *of*, with the comparison figures beside it.

Anonymity: editors appear only as per-article labels. Usernames may appear only inside link
targets (diffs, decisions) that Wikipedia already publishes; `wtl check` scans these pages too.
"""

import json
import os
import re
import shutil
from collections import Counter
from html import escape
from urllib.parse import quote
from pathlib import Path

from .config import OUT_DIR
from .report import json_writer
from .report.html import TYPE_NAMES, get, link, pct

ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
DOCS = ROOT / "docs"
NAME = "Wikipedia Transparency Layer"
REPO = "https://github.com/mediapediatransparency/wikipedia-transparency"
WIKI = "https://en.wikipedia.org"

GROUP_NAMES = {"topic": "Arab–Israeli conflict articles", "control": "comparison articles"}
GROUP_ONE = {"topic": "Arab–Israeli conflict article", "control": "Comparison article"}
MIN_PEERS = 3   # fewest other articles of the same kind before a "typical" figure is given


def area_name(code):
    from .candidates import AREAS
    return AREAS.get(code, (code,))[0] if code else "No contentious topic area"


def kind_name(kind, plural=True):
    from .candidates import KIND_NAMES
    n = KIND_NAMES.get(kind, "Other articles")
    if plural:
        return n
    return {"journalist": "Journalist or commentator", "person": "Public figure",
            "media": "News outlet or media", "organisation": "Organisation",
            "idea": "Idea, ideology or movement", "event": "Event"}.get(kind, "Article")


def cap(s):
    return s[:1].upper() + s[1:]

CSS = """
:root{--bg:#fbfbf9;--fg:#1d1d1b;--muted:#5d5d58;--line:#dcdbd5;--soft:#f1f0eb;--link:#1f4e8c;--accent:#2a78d6;
--bar:#4a6fa5;--bar2:#b9c7dc;--note:#fff8e6;--noteline:#e2c46f}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#171715;--fg:#e9e8e3;
--muted:#a8a79f;--line:#3a3935;--soft:#22221f;--link:#93b8ec;--bar:#7f9fd0;--bar2:#3b4a62;
--note:#2a2516;--noteline:#7a6524;--accent:#5598e7}}
:root[data-theme="dark"]{--bg:#171715;--fg:#e9e8e3;--muted:#a8a79f;--line:#3a3935;--soft:#22221f;
--link:#93b8ec;--bar:#7f9fd0;--bar2:#3b4a62;--note:#2a2516;--noteline:#7a6524;--accent:#5598e7}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 Georgia,"Iowan Old Style",serif}
header.site{border-bottom:1px solid var(--line);background:color-mix(in srgb,var(--bg) 92%,var(--soft));
position:relative;z-index:50}
header.site .in{max-width:1240px;margin:0 auto;padding:0 16px;min-height:64px;display:flex;align-items:center;
gap:8px 28px;flex-wrap:wrap;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
header.site .brand{display:flex;align-items:center;gap:10px;color:var(--fg);text-decoration:none;margin-right:auto;
padding:10px 0}
header.site .mark{width:26px;height:26px;flex:none;color:var(--fg)}
header.site .bt{display:flex;flex-direction:column;line-height:1.05;font:600 1.06rem/1.1 Georgia,"Iowan Old Style",serif;
letter-spacing:-.005em}
header.site .bt small{font:600 .62rem/1.2 system-ui,-apple-system,"Segoe UI",sans-serif;letter-spacing:.14em;
text-transform:uppercase;color:var(--muted)}
header.site nav{display:flex;align-items:center;gap:2px;flex-wrap:wrap}
header.site .top{display:inline-block;padding:8px 12px;border-radius:8px;color:var(--fg);text-decoration:none;
font-size:.92rem;cursor:pointer;list-style:none;position:relative}
header.site .top::-webkit-details-marker{display:none}
header.site summary.top::after{content:"";display:inline-block;width:6px;height:6px;margin-left:7px;
border-right:1.5px solid var(--muted);border-bottom:1.5px solid var(--muted);transform:translateY(-3px) rotate(45deg)}
header.site .top:hover,header.site details[open]>.top{background:var(--soft)}
header.site .top[aria-current]::before,header.site .top[data-here]::before{content:"";position:absolute;left:12px;
right:12px;bottom:2px;height:2px;border-radius:2px;background:var(--accent)}
header.site details.dd{position:relative}
header.site .menu{position:absolute;top:calc(100% + 6px);left:0;min-width:230px;padding:6px;background:var(--bg);
border:1px solid var(--line);border-radius:12px;box-shadow:0 12px 32px rgba(0,0,0,.14)}
header.site .menu a{display:block;padding:8px 10px;border-radius:8px;color:var(--fg);text-decoration:none;font-size:.9rem}
header.site .menu a:hover{background:var(--soft)}
header.site .menu a[aria-current]{color:var(--link);font-weight:600}
header.site .srch{display:inline-flex;align-items:center;gap:7px;padding:7px 14px;border:1px solid var(--line);
border-radius:999px;color:var(--muted);text-decoration:none;font-size:.88rem;background:var(--bg)}
header.site .srch:hover,header.site .srch[aria-current]{color:var(--fg);border-color:var(--muted)}
header.site a:focus-visible,header.site summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (max-width:760px){header.site .in{gap:0 8px;padding-bottom:4px}header.site nav{order:3;width:100%;
flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;margin:0 -8px}header.site nav::-webkit-scrollbar{display:none}
header.site .top{padding:8px 9px;white-space:nowrap}header.site .srch span{display:none}header.site .srch{padding:8px 10px}
header.site .menu{position:fixed;left:16px;right:16px;top:auto}}
main{max-width:1240px;margin:0 auto;padding:24px 16px 64px}
details.pop{display:inline-block;position:relative;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
details.pop>summary{cursor:pointer;list-style:none;color:var(--link);font-size:.8rem;white-space:nowrap}
details.pop>summary::-webkit-details-marker{display:none}
details.pop .popb{position:absolute;z-index:40;left:0;top:1.6em;width:min(360px,80vw);background:var(--bg);
color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:8px 12px;box-shadow:0 6px 22px rgba(0,0,0,.18);
font:.86rem/1.45 Georgia,"Iowan Old Style",serif;text-transform:none;letter-spacing:0}
details.pop .popb p{margin:4px 0}details.pop .popb a{font-size:.78rem;white-space:nowrap}
h1{font-size:2rem;line-height:1.2;margin:8px 0 6px}
h2{font-size:1.35rem;margin:40px 0 10px;padding-top:14px;border-top:1px solid var(--line)}
h3{font-size:1.08rem;margin:24px 0 6px}
p,li{max-width:none;line-height:1.75}
a{color:var(--link)}
.sans,table,.meta,.small,.note,.fig,details summary,footer{font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
.meta{color:var(--muted);font-size:.9rem}
.small{font-size:.88rem;color:var(--muted)}
tr.sum td{background:var(--soft);border-top:1px solid var(--line)}
.lede{font-size:1.12rem}
sup a{text-decoration:none;font-size:.75em;padding:0 1px}
.detail-banner{max-width:none;margin:0 0 18px;padding:10px 14px;border-radius:10px;background:var(--soft);
font:.88rem/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted)}
ol.refs li{margin:0 0 8px;max-width:none}
.brief{background:var(--soft);border:1px solid var(--line);border-radius:8px;padding:6px 20px;margin:18px 0}
.brief li{margin:8px 0}
.fig{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}
.fig .box{flex:1 1 180px;border:1px solid var(--line);border-radius:8px;padding:10px 14px}
.fig .num{font-size:1.7rem;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.2}
.fig .lbl{font-size:.88rem}
.fig .cmp{font-size:.82rem;color:var(--muted);margin-top:4px}
.note{background:var(--note);border-left:4px solid var(--noteline);padding:8px 14px;margin:12px 0;
font-size:.92rem;border-radius:0 6px 6px 0;max-width:none}
.note b{font-weight:600}
.scroll,.ft{overflow:auto;-webkit-overflow-scrolling:touch;margin:10px 0;max-height:75vh;
border:1px solid var(--line);border-radius:6px}
.scroll table,.ft table{border-collapse:separate;border-spacing:0}
.scroll tr:first-child>th,.ft tr:first-child>th{position:sticky;top:0;background:var(--soft);z-index:2}
.scroll td:first-child,.scroll th:first-child,.ft td:first-child,.ft th:first-child{position:sticky;
left:0;background:var(--bg);z-index:1;max-width:38vw}
.scroll tr:first-child>th:first-child,.ft tr:first-child>th:first-child{background:var(--soft);z-index:3}
.clamp{display:-webkit-box;-webkit-line-clamp:3;line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.clamp.open{display:block;overflow:visible}
.inshort{background:var(--soft);border-left:3px solid var(--bar);padding:6px 10px;border-radius:4px;margin:6px 0 10px}
dl.gloss dt{font-weight:600;margin-top:8px}dl.gloss dd{margin:0 0 4px 0}
button.more{border:0;background:none;color:var(--link);padding:0;margin-top:2px;cursor:pointer;
font:inherit;font-size:.78rem;text-decoration:underline}
table{border-collapse:collapse;width:100%;font-size:.88rem}
th,td{text-align:left;vertical-align:top;padding:6px 8px;border-bottom:1px solid var(--line)}
th{font-weight:600;color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.03em}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.expl{color:var(--muted);font-size:.82rem;min-width:220px}
.tag{display:inline-block;border:1px solid var(--muted);border-radius:3px;padding:0 5px;font-size:.76rem;white-space:nowrap}
.bars{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:.85rem;margin:10px 0}
.bars .row{display:grid;grid-template-columns:84px 1fr 54px;gap:8px;align-items:center;margin:3px 0}
.bars .track{background:var(--soft);border-radius:3px;height:14px;overflow:hidden}
.bars .fill{background:var(--bar);height:100%}
.bars .fill.s{background:repeating-linear-gradient(45deg,var(--bar) 0 4px,var(--bar2) 4px 8px)}
.bars .v{text-align:right;font-variant-numeric:tabular-nums}
details{margin:12px 0}
details summary{cursor:pointer;color:var(--link)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px;margin:12px 0}
.card{border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.card h3{margin:0 0 4px}
.card p{margin:4px 0;font-size:.92rem}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:.82rem}
footer .in{max-width:1240px;margin:0 auto;padding:16px}
@media (max-width:520px){h1{font-size:1.6rem}.bars .row{grid-template-columns:70px 1fr 48px}}
.lbl{position:relative;display:inline-block;padding:1px 8px;margin:1px 2px;border:1px solid var(--line);border-radius:999px;
 background:var(--soft);font-size:.82rem;cursor:help;white-space:nowrap}
.lbl:focus{outline:2px solid var(--link);outline-offset:1px}
.pill{display:inline-block;padding:1px 8px;margin:1px 2px;border:1px solid var(--line);border-radius:999px;font-size:.8rem;cursor:help}
.pill.rate{background:var(--soft)}.pill.cflag{border-style:dashed}
.lbl .def{display:none;position:absolute;left:0;top:calc(100% + 6px);z-index:30;width:min(320px,80vw);white-space:normal;
 padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg);
 box-shadow:0 6px 18px rgba(0,0,0,.18);font-size:.82rem;line-height:1.4;cursor:auto}
.lbl:hover .def,.lbl:focus .def,.lbl:focus-within .def{display:block}
.lbl .def b{font-weight:600}.lbl .def .src{display:block;margin-top:6px;color:var(--muted);font-size:.75rem}
"""

# the top bar: (label, [(page, name)]); a group of one is a plain link
NAV_GROUPS = [
    ("Articles", [("compare.html", "All articles and their figures"), ("articles.html", "Which articles, and why"),
                  ("categories.html", "Categories")]),
    ("Editors", [("editors.html", "Overview"), ("editors-across.html", "Editors across topics"),
                 ("editor.html", "Look up an editor")]),
    ("Sources", [("sources.html", "Overview"), ("sources-affiliations.html", "Affiliations")]),
    ("Leaning", [("leaning.html", "Leaning")]),
    ("About", [("about.html", "About this project"), ("objective.html", "Why this matters for AI"),
               ("how-it-works.html", "How it works")]),
    ("Data & method", [("how-it-works.html", "How it works"), ("compare-detail.html", "Every figure, every article"),
                       ("sources-detail.html", "Sources in detail"), ("leaning-detail.html", "Leaning in detail"),
                       ("editors-detail.html", "Editors in detail"), ("articles-detail.html", "Full article lists"),
                       ("categories.html", "Categories")]),
]
MARK_SVG = ("<svg class='mark' viewBox='0 0 24 24' aria-hidden='true'><rect x='2.5' y='2.5' width='19' height='19' "
            "rx='5' fill='none' stroke='currentColor' stroke-width='1.6'/><path d='M7 8.5h10M7 12h7M7 15.5h8.5' "
            "stroke='currentColor' stroke-width='1.6' stroke-linecap='round'/><path d='M7 12h7' "
            "stroke='var(--accent)' stroke-width='2.6' stroke-linecap='round'/></svg>")
SEARCH_SVG = ("<svg viewBox='0 0 24 24' width='16' height='16' aria-hidden='true'><circle cx='10.5' cy='10.5' r='6.5' "
              "fill='none' stroke='currentColor' stroke-width='2'/><path d='M15.5 15.5 20 20' stroke='currentColor' "
              "stroke-width='2' stroke-linecap='round'/></svg>")
NAV_JS = """document.querySelectorAll('header.site details.dd').forEach(function(d){
 d.addEventListener('toggle',function(){if(d.open)document.querySelectorAll('header.site details.dd[open]')
  .forEach(function(o){if(o!==d)o.open=false})})});
document.addEventListener('click',function(e){if(!e.target.closest('header.site details.dd'))
 document.querySelectorAll('header.site details.dd[open]').forEach(function(o){o.open=false})});
document.addEventListener('keydown',function(e){if(e.key==='Escape')document.querySelectorAll(
 'header.site details.dd[open]').forEach(function(o){o.open=false;o.querySelector('summary').focus()})});"""

PAGES = [("index.html", "Home"), ("search.html", "Search"), ("compare.html", "All articles"), ("articles.html", "Which articles"),
         ("editors.html", "Editors: overview"), ("editor.html", "Editors: look up"), ("leaning.html", "Leaning"), ("sources.html", "Sources"),
         ("categories.html", "Categories"),
         ("how-it-works.html", "How it works"), ("objective.html", "Objective"),
         ("about.html", "About")]


# ---------------------------------------------------------------- helpers
def p1(x):
    return pct(x, 1)


def p0(x):
    return pct(x, 0)


def num(n):
    return f"{n:,}"


def slug(title):
    return json_writer.slug(title)


def page(title, body, current, depth=0, json_alt=None, description=""):
    up = "../" * depth
    items = []
    for label, links in NAV_GROUPS:
        here = any(h == current for h, _ in links)
        if len(links) == 1:
            href = links[0][0]
            items.append(f"<a class='top' href='{up}{href}'" + (" aria-current='page'" if here else "")
                         + f">{escape(label)}</a>")
        else:
            items.append(f"<details class='dd'><summary class='top'" + (" data-here" if here else "")
                         + f">{escape(label)}</summary><div class='menu'>" + "".join(
                             f"<a href='{up}{h}'" + (" aria-current='page'" if h == current else "")
                             + f">{escape(n)}</a>" for h, n in links) + "</div></details>")
    nav = "".join(items)
    alt = (f'<link rel="alternate" type="application/json" href="{escape(json_alt, quote=True)}">'
           if json_alt else "")
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{escape(title)}</title>"
            f"<meta name='description' content='{escape(description, quote=True)}'>{alt}"
            f"<style>{CSS}</style></head><body>"
            f"<header class='site'><div class='in'><a class='brand' href='{up}index.html' aria-label='{escape(NAME)}, home'>"
            f"{MARK_SVG}<span class='bt'><small>Wikipedia</small>Transparency Layer</span></a>"
            f"<nav aria-label='Site'>{nav}</nav><a class='srch' href='{up}search.html'"
            + (" aria-current='page'" if current == "search.html" else "")
            + f">{SEARCH_SVG}<span>Search</span></a></div></header><main>{_in_short(body, current)}</main>"
            f"<footer><div class='in'>An independent project. Not affiliated with Wikipedia or "
            f"the Wikimedia Foundation. Figures are computed by open code from Wikipedia's public "
            f"records; {link(REPO, 'source code and data')}.</div></footer>"
            f"<script>{CLAMP_JS}{NAV_JS}</script></body></html>\n")


# "In short" lines: one plain sentence under a section heading, saying what the section shows
# before its detailed method notes. Keyed by page, then by the heading's exact text.
IN_SHORT = {
    "sources.html": {
        "The raters": "The outside organisations whose ratings we show, what each one measures, "
                      "and where its data comes from.",
        "Wikipedia's ratings next to independent ratings": "For sources on Wikipedia's own "
            "reliability list, Wikipedia's rating side by side with the outside raters' scores.",
        "Most-cited sources, by topic area": "The sources cited most often in each topic, with "
            "every rating we have for each.",
        "Organisations cited: checklist and recorded associations": "Think tanks, campaign "
            "groups, charities and other organisations that are cited, with public facts about "
            "each: official registration, funders, founders and links to other organisations.",
        "Journals cited: checklist": "Every academic journal cited, with basic facts: who "
            "publishes it, which research indexes list it, and its academic grade.",
        "Opinion and harder-to-check citations: the sources behind them": "Which sources the "
            "harder-to-check footnotes (opinion pieces, no link, paywall, no translation) point "
            "to.",
        "Books: publishers, where their ISBNs were issued, and languages": "The books cited, "
            "grouped by the country or language area that issued their ISBN, with their "
            "languages and publishers.",
        "Publishers of books not in English or registered outside the English-language ISBN "
        "groups": "Publishers of cited books that are not in English, or were registered outside "
            "English-speaking countries, with what is known about each.",
        "Works cited in several analysed articles": "Single books or web pages cited in more "
            "than one of the articles we analysed.",
        "What cited websites say about themselves": "What each cited website's own pages say "
            "about who runs it: company names, registration numbers, copyright owners and "
            "tracking accounts.",
        "Cited sites that share a tracking or advertising account": "Groups of different "
            "websites that use the same Google, Facebook or Yandex tracking account, which "
            "often means one owner or manager.",
        "Cited websites: records kept elsewhere": "Facts about cited websites from outside "
            "records (old saved copies, address records, security certificates), for sites that "
            "are gone or have changed.",
        "Domains whose current registration began after they were cited": "Website addresses "
            "registered after the article cited them, which can mean the address now belongs to "
            "someone else. The site's title then and now is shown.",
        "Cited sites that share a DNS or certificate value": "Different cited websites that "
            "share the same server records or security certificate, which can mean they are run "
            "together.",
    },
    "categories.html": {
        "Subject areas": "Which topics we cover, and how Wikipedia itself marks them.",
        "Kinds, from Wikidata": "How we sort articles into kinds (people, news outlets, "
            "organisations, ideas, events) and where that sorting comes from.",
        "Movements that Wikidata also records as organisations": "Our rule for things Wikidata "
            "calls both a movement and an organisation.",
        "Journalists and commentators": "Our rule for who counts as a journalist or "
            "commentator.",
        "Arts, entertainment and sport": "Actors, musicians and athletes that Wikipedia's own "
            "tags put under political subjects, listed so you can see them.",
        "Oddities in Wikipedia's own sorting": "Places where Wikipedia's own tags and categories "
            "are surprising or inconsistent, with links so you can check.",
        "Articles left out because they fit no kind": "Articles we did not analyse because they "
            "fit none of our kinds.",
        "Tags and banners on redirects": "Tags on pages that only forward you to another "
            "article. We do not count them.",
        "How cited sources are sorted": "How the sources behind footnotes are sorted into "
            "kinds.",
    },
    "leaning.html": {
        "Recorded political affiliation": "What Wikipedia and Wikidata say about each "
            "publisher's own politics: a second measure, next to audience leaning.",
        "How the writers' figure is worked out": "How the sources each editor cites are combined "
            "into one figure for the article, without publishing any editor's own figure.",
    },
    "editors.html": {
        "In how many articles each editor wrote at least 1%": "How many editors wrote a "
            "noticeable part (at least 1%) of one, two, three or more of the analysed articles.",
        "The 40 editors with the most articles": "The editors who wrote at least 1% of the most "
            "analysed articles, shown by code, not by name.",
    },
    "articles.html": {
        "The rule": "How we choose which articles to analyse.",
    },
}


def _in_short(body: str, current: str) -> str:
    import re as _re
    if "<div class='st'>" in body:   # reader pages open every section with their own plain line
        return body
    for head, text in IN_SHORT.get(current, {}).items():
        txt = _re.escape(escape(head, quote=False)).replace("'", "(?:'|&\\#x27;)")
        pat = _re.compile(r"(<h([23])[^>]*>" + txt + r"(?: \([^<]*\))?</h\2>)")
        body = pat.sub(lambda m: m.group(1) + f"<p class='inshort'><b>In short:</b> {escape(text)}</p>",
                       body, count=1)
    return body


# Long table cells show three lines and a "more" button; without JavaScript they show in full.
# Tables drawn later by a page's own script (sorting, look-ups) are handled as they appear.
CLAMP_JS = (
    "(function(){var L=200;function fit(td,d,b){if(d.clientHeight&&d.scrollHeight<=d.clientHeight+2"
    "&&!d.classList.contains('open')){td.removeChild(b);d.className='';}}"
    "function run(root){if(!root.querySelectorAll)return;root.querySelectorAll('td:not([data-c])')"
    ".forEach(function(td){td.setAttribute('data-c','');if(td.textContent.length<L)return;"
    "var d=document.createElement('div');d.className='clamp';while(td.firstChild)d.appendChild(td.firstChild);"
    "td.appendChild(d);var b=document.createElement('button');b.type='button';b.className='more';"
    "b.textContent='more';b.setAttribute('aria-expanded','false');b.onclick=function(){"
    "var o=d.classList.toggle('open');b.textContent=o?'less':'more';b.setAttribute('aria-expanded',o);};"
    "td.appendChild(b);requestAnimationFrame(function(){fit(td,d,b);});});}"
    "run(document);new MutationObserver(function(ms){ms.forEach(function(m){m.addedNodes.forEach(run);});})"
    ".observe(document.body,{childList:true,subtree:true});})();")


def median(vals):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    m = len(vals) // 2
    return vals[m] if len(vals) % 2 else (vals[m - 1] + vals[m]) / 2


class Context:
    """All records plus the typical (median) values per group, for comparisons."""

    def __init__(self, recs, groups, patterns=None, areas=None, kinds=None, candidates=None,
                 outlets=None):
        self.recs, self.groups, self.patterns = recs, groups, patterns
        self.areas, self.kinds = areas or {}, kinds or {}
        self.candidates = candidates or []
        self.outlets_snap = outlets or {}
        self.outlets = self.outlets_snap.get("sources", {})
        self.by_group = {g: [r for r in recs if groups[r["article"]] == g] for g in GROUP_NAMES}

    def peers(self, rec, same_area=True):
        """Other analysed articles of the same kind (and, by default, the same area)."""
        t = rec["article"]
        k = self.kinds.get(t)
        return [r for r in self.recs if r["article"] != t and self.kinds.get(r["article"]) == k
                and (not same_area or self.areas.get(r["article"]) == self.areas.get(t))]

    def med(self, group, path):
        return median([get(r, path) for r in self.by_group[group]])

    def thin(self, group):
        """True if any article in the group has a sanctions list not comparable with the
        best-covered area (thin list, or no topic area at all)."""
        return any(c["code"] in THIN for r in self.by_group[group] for c in r.get("caveats", []))

    def cmp(self, path, fmt=p1, rec=None):
        """'Typical: X in the six Arab–Israeli conflict articles, Y in the three comparison
        articles.' For sanction figures, a group is left out when its sanctions lists are not
        comparably thorough, and nothing is compared when the article's own list is thin."""
        sanction = path in SANCTION_PATHS
        if sanction and rec is not None and any(c["code"] in THIN for c in rec.get("caveats", [])):
            return ("Not compared: the sanctions list for this article's area is not yet as "
                    "thorough as for the Arab–Israeli conflict.")
        if rec is not None and self.kinds.get(rec["article"]):
            return self.cmp_like(path, fmt, rec, sanction)
        nt, nc = len(self.by_group["topic"]), len(self.by_group["control"])
        bits = []
        t = self.med("topic", path)
        if t is not None and not (sanction and self.thin("topic")):
            bits.append(f"{fmt(t)} across the {nt} Arab–Israeli conflict articles")
        c = self.med("control", path)
        if c is not None and not (sanction and self.thin("control")):
            bits.append(f"{fmt(c)} across the {nc} comparison articles")
        out = "In a typical similar article: " + " and ".join(bits) + "." if bits else ""
        if sanction and self.thin("control") and c is not None:
            out += (" Not compared with the comparison articles: their sanctions lists are not "
                    "yet as thorough.")
        return out.strip()


    def cmp_like(self, path, fmt, rec, sanction):
        """Like-for-like: the median over other analysed articles of the same kind, first in the
        same topic area, then across all areas (sanction figures only where lists are thorough)."""
        kind = self.kinds[rec["article"]]
        bits = []
        for same_area in (True, False):
            ps = self.peers(rec, same_area)
            if sanction:
                ps = [r for r in ps if not any(c["code"] in THIN for c in r.get("caveats", []))]
            m = median([get(r, path) for r in ps])
            if m is None or len(ps) < MIN_PEERS:
                continue
            where = (f"in {area_name(self.areas.get(rec['article']))}" if same_area
                     else "across all areas" + (" with thorough sanctions lists" if sanction else ""))
            bits.append(f"{fmt(m)} for the {len(ps)} other {kind_name(kind).lower()} analysed {where}")
        return ("In a typical similar article: " + "; ".join(bits) + ".") if bits else ""


THIN = {"thin_sanctions_list", "no_topic_area"}
SANCTION_PATHS = {"authorship.sanctioned_share", "authorship.sanctioned_lead_share",
                  "accountability.concentration.share_of_sanctioned_text",
                  "accountability.sanctioned_editors"}


def fig(number, label, compare=""):
    return (f"<div class='box'><div class='num'>{number}</div><div class='lbl'>{label}</div>"
            + (f"<div class='cmp'>{compare}</div>" if compare else "") + "</div>")


def note(text, title="Read with care"):
    return f"<div class='note'><b>{escape(title)}:</b> {escape(text)}</div>"


def caveats_for(rec, applies_to):
    return "".join(note(c["text"]) for c in rec.get("caveats", []) if c["applies_to"] == applies_to)


def sanctioned_sentence(rec):
    """The headline sanction figure as one unambiguous sentence (what it is a share of, how many
    editors, and how concentrated)."""
    a, acc = rec["authorship"], rec["accountability"]
    n = acc["sanctioned_editors"]
    if not n:
        return (f"None of the article's {num(a['total_words'])} words were written by an editor "
                f"Wikipedia is recorded as having sanctioned.")
    s = (f"{p1(acc['sanctioned_share'])} of the article's words ({num(acc['sanctioned_words'])} "
         f"of {num(a['total_words'])}) were written by {n} editor{'s' if n != 1 else ''} whom "
         f"Wikipedia sanctioned.")
    c = acc.get("concentration")
    if c and n > 1:
        rest = 1 - c["share_of_sanctioned_text"]
        s += (f" The one who wrote most of it, {c['editor']}, wrote "
              f"{p1(c['share_of_article'])} of the whole article. That is "
              f"{p0(c['share_of_sanctioned_text'])} of everything the sanctioned editors wrote; "
              f"the other {n - 1} wrote the remaining {p0(rest)}.")
    return s


# ---------------------------------------------------------------- article page
def article_page(rec, ctx: Context):
    a, acc = rec["authorship"], rec["accountability"]
    title = rec["article"]
    group = ctx.groups[title]
    eds = a["editors"]
    lead = a["lead"]
    lead_sents = [s for s in rec["sentences"] if s["id"].startswith("lead-")]
    lead_sanct = [s for s in lead_sents if s["author_sanctioned"]]
    sv30 = a["survival_article"]["30d"]["rate"]
    t = acc["timing"]
    tot_t = t["added_before_sanction_words"] + t["added_after_sanction_words"]
    date = rec["revision_timestamp"][:10]
    wp = f"{WIKI}/wiki/{title.replace(' ', '_')}"
    h = []
    kind = ctx.kinds.get(title)
    label = (f"{kind_name(kind, plural=False)} · {area_name(ctx.areas.get(title))}" if kind
             else GROUP_ONE.get(group, area_name(ctx.areas.get(title))))
    h.append(f"<p class='meta'>{escape(label)} · "
             f"{link(wp, 'Read it on Wikipedia')} · "
             f"<a href='../search.html#track={quote(title)}'>Track words in it over time</a></p>")
    h.append(f"<h1>{escape(title)}</h1>")
    h.append(f"<p class='meta'>Figures describe the article as it stood on {escape(date)} "
             f"({link(rec['permalink'], 'that exact version')}). Computed {escape(rec['computed'])}. "
             f"{link(f'../data/{slug(title)}.json', 'Full data (JSON)')}.</p>")

    # ---- the opening then and now (whole first paragraph, side by side)
    h.append(then_now_top(rec, ctx))
    h.append(voice_section(rec, ctx))

    # ---- at a glance: the main figures as bar charts (the same numbers as further down)
    h.append(glance_section(rec, ctx))

    # ---- who wrote it
    h.append("<h2>Who wrote the text</h2>")
    h.append("<p>Each word in today's article is credited to the editor who first added it. The "
             "shares below are shares of the article's current words.</p>")
    h.append("<div class='fig'>")
    h.append(fig(str(a["editors_for_50pct"]), "editors wrote half of the text",
                 ctx.cmp("authorship.editors_for_50pct", fmt=lambda v: f"{v:g} editors", rec=rec)))
    h.append(fig(p1(a["top_shares"]["1"]), "of the text is by the single largest contributor",
                 ctx.cmp("authorship.top_shares.1", rec=rec)))
    h.append(fig(p1(a["top_shares"]["10"]), "of the text is by the top 10 editors together",
                 ctx.cmp("authorship.top_shares.10", rec=rec)))
    h.append("</div>")
    h.append("<p class='small'>“Editors who wrote half” is the smallest number of editors whose "
             "words together make up half of the article's current text.</p>")
    h.append("<h3>The ten largest contributors</h3>")
    h.append("<p class='small'>Bar length is each editor's share of the article's current words. "
             "Striped bars are editors Wikipedia sanctioned.</p><div class='bars'>")
    top = eds[:10]
    scale = max(e["share"] for e in top) if top else 1
    for e in top:
        w = 100 * e["share"] / scale if scale else 0
        h.append(f"<div class='row'><span>{escape(e['label'])}</span><span class='track'>"
                 f"<span class='fill{' s' if e['sanctioned'] else ''}' style='display:block;"
                 f"width:{w:.1f}%'></span></span><span class='v'>{p1(e['share'])}</span></div>")
    h.append("</div>")

    h.append("<h3>When the largest contributors' text was added</h3>")
    h.append("<p class='small'>For each of the ten largest contributors: the years in which "
             "the words of theirs still in the article were first added, with the number of words "
             "from each year. Years with under 1% of that editor's surviving words are grouped "
             "as “other years”.</p>")
    h.append("<div class='scroll'><table><tr><th>Editor</th><th class='n'>Words</th>"
             "<th>First added, by year</th></tr>")
    for e in top:
        yrs = e.get("added_by_year") or {}
        tot = sum(yrs.values()) or 1
        main = [(y, n) for y, n in yrs.items() if n / tot >= 0.01]
        rest = tot - sum(n for _, n in main)
        cells = " · ".join(f"{escape(y)}: {num(n)}" for y, n in main)
        if rest > 0 and yrs:
            cells += f" · other years: {num(rest)}"
        h.append(f"<tr><td>{escape(e['label'])}{' <span class=\'tag\'>sanctioned</span>' if e['sanctioned'] else ''}"
                 f"</td><td class='n'>{num(e['words'])}</td><td class='small'>{cells or '–'}</td></tr>")
    h.append("</table></div>")

    # ---- lead
    h.append("<h2>The opening section</h2>")
    h.append(f"<p>The opening section (Wikipedia calls it the lead) is the summary at the top. "
             f"Search engines and AI assistants quote it most. Here it has "
             f"{num(a['lead_words'])} words by {a['lead_editor_count']} editors.</p>")
    h.append("<div class='fig'>")
    h.append(fig(p1(lead["top_shares"]["3"]), "of the opening was written by its top 3 editors",
                 ctx.cmp("authorship.lead.top_shares.3", rec=rec)))
    h.append(fig(str(lead["editors_for_50pct"]), "editors wrote half of the opening"))
    h.append(fig(p1(acc["sanctioned_lead_share"]), "of the opening's words are by sanctioned editors",
                 ctx.cmp("authorship.sanctioned_lead_share", rec=rec)))
    h.append("</div>")


    # ---- sanctions
    h.append("<h2>Text by editors Wikipedia sanctioned</h2>")
    h.append(f"<p class='lede'>{escape(sanctioned_sentence(rec))}</p>")
    h.append("<div class='fig'>")
    h.append(fig(p1(acc["sanctioned_share"]), "of the whole article", ctx.cmp("authorship.sanctioned_share", rec=rec)))
    h.append(fig(p1(acc["sanctioned_lead_share"]), "of the opening section"))
    h.append(fig(str(acc["sanctioned_editors"]), "sanctioned editors with text in the article"))
    h.append("</div>")
    h.append(caveats_for(rec, "sanctioned_share"))
    h.append("<h3>What kind of sanction</h3>")
    h.append("<p class='small'>One editor can have more than one kind, so the rows can add up to "
             "more than the total.</p>")
    h.append("<div class='scroll'><table><tr><th>Sanction</th><th>What it means</th>"
             "<th class='n'>Share of article</th><th class='n'>Share of opening</th></tr>")
    meaning = {
        "topic_ban": "Barred from editing this subject area. Counted only on articles in that area.",
        "site_ban": "Barred from editing Wikipedia at all. Counted on every article.",
        "sockpuppet": "Found to have run more than one account to deceive. Counted on every article.",
    }
    for k in ("topic_ban", "site_ban", "sockpuppet"):
        b = acc["by_type"][k]
        h.append(f"<tr><td>{TYPE_NAMES[k].capitalize()}</td><td class='expl'>{meaning[k]}</td>"
                 f"<td class='n'>{p1(b['share'])}</td><td class='n'>{p1(b['lead_share'])}</td></tr>")
    h.append(f"<tr><td><b>Any of these</b></td><td></td><td class='n'><b>{p1(acc['sanctioned_share'])}"
             f"</b></td><td class='n'><b>{p1(acc['sanctioned_lead_share'])}</b></td></tr>"
             "</table></div>")
    if tot_t:
        h.append("<h3>When the sanctioned editors' text was added</h3>")
        h.append("<p class='small'>Each word is dated by the edit that first added it, which was "
                 "made by the sanctioned editor's own account.</p>")
        h.append("<div class='scroll'><table><tr><th>Added</th><th class='n'>Words</th>"
                 "<th class='n'>Share of their words</th></tr>")
        for key, lbl in (("added_before_sanction_words", "Before the editor's first sanction"),
                         ("added_during_sanction_words", "While a sanction with a set end date was in force"),
                         ("added_during_open_ended_sanction_words",
                          "While an open-ended sanction was in force (no end on record)"),
                         ("added_after_sanction_ended_words", "After the editor's sanctions had ended")):
            n = t.get(key)
            if n is None:
                continue
            h.append(f"<tr><td>{lbl}</td><td class='n'>{num(n)}</td><td class='n'>{p1(n / tot_t)}</td></tr>")
        h.append("</table></div>")
        h.append(caveats_for(rec, "timing"))

    # ---- survival
    h.append("<h2>How long new text lasts</h2>")
    surv = a["survival_article"]
    h.append("<p>This counts every word ever added to the article, including words later removed, "
             "and asks how many were still there after a given time.</p>")
    h.append("<div class='fig'>")
    for key, lbl in (("48h", "still there after 2 days"), ("30d", "still there after 30 days"),
                     ("365d", "still there after a year")):
        h.append(fig(p1(surv[key]["rate"]), lbl, ctx.cmp(f"authorship.survival_article.{key}.rate", rec=rec)))
    h.append("</div>")
    h.append(persistence_html(rec, ctx))
    h.append(contested_section(rec, ctx))
    h.append(kept_section(rec, ctx))

    # ---- sources
    h.append(sources_section(rec, ctx))
    h.append(then_now_sources_block(rec, ctx))

    # ---- removals, wording changes, declared interests
    h.append(changes_section(rec, ctx))
    h.append(activity_section(rec, ctx))
    h.append(interests_section(rec))

    # ---- editors table
    h.append("<h2>Editors in detail</h2>")
    h.append("<p class='small'><b>Words</b> and <b>Share</b>: this editor's words in today's "
             "article, and what fraction of the whole article that is. <b>Opening</b>: their "
             "share of the opening section. <b>Text survival</b>: of all the words this editor "
             "ever added here, how many were still there 30 days later. “×1.20” means 1.2 times "
             "the article's average, so their additions lasted better than most. <b>Evidence</b>: "
             "the edits that contributed most of their surviving text, on Wikipedia.</p>")
    h.append("<div class='scroll'><table><tr><th>Editor</th><th class='n'>Words</th>"
             "<th class='n'>Share</th><th class='n'>Opening</th><th class='n'>Text survival</th>"
             "<th>Sanction</th><th>Evidence</th></tr>")
    shown = eds[:25] + [e for e in eds[25:] if e["sanctioned"]]
    for e in shown:
        s30 = e["survival"]["30d"]
        surv_txt = "–" if s30["rate"] is None else p0(s30["rate"]) + (
            "" if s30["vs_article"] is None else f" <span class='small'>×{s30['vs_article']:.2f}</span>")
        def period(s):
            if s.get("end"):
                how = " (lifted)" if s.get("end_basis") == "lifted" else ""
                return f"{escape(s['date'])} to {escape(s['end'])}{how}"
            return f"from {escape(s['date'])} (open-ended)"
        sanc = "<br>".join(
            f"<span class='tag'>{escape(TYPE_NAMES.get(s['type'], s['type']))}</span> "
            f"{period(s)} {link(s['evidence'], 'decision')}"
            + (f" {link(s['lift_evidence'], 'lifted')}" if s.get("lift_evidence") else "")
            + (f" <span class='small'>scope: {escape(s['scope'])}</span>" if s.get("scope") else "")
            for s in e["sanctions"])
        kind = "" if e["account_type"] == "registered" else f" <span class='small'>({escape(e['account_type'])})</span>"
        ev = " ".join(link(f"{WIKI}/w/index.php?diff=prev&oldid={r}", "edit") for r in e["top_revisions"])
        h.append(f"<tr><td>{escape(e['label'])}{kind}</td><td class='n'>{num(e['words'])}</td>"
                 f"<td class='n'>{p1(e['share'])}</td><td class='n'>{p1(e['lead_share'])}</td>"
                 f"<td class='n'>{surv_txt}</td><td>{sanc}</td><td>{ev}</td></tr>")
    h.append("</table></div>")
    if len(eds) > len(shown):
        h.append(f"<p class='small'>The top 25 editors are shown, plus every sanctioned editor. "
                 f"The other {num(len(eds) - len(shown))} are in the full data.</p>")

    # ---- sentences
    def sent_table(rows):
        out = ["<div class='scroll'><table><tr><th>Sentence</th><th>Written by (words each)</th>"
               "<th>Sanctioned editor's words</th><th>History</th><th>Edit</th></tr>"]
        for s in rows:
            authors = ", ".join(f"{escape(l)} ({n})" for l, n in zip(s["authors"][:4], s["author_words"][:4]))
            if len(s["authors"]) > 4:
                authors += f", and {len(s['authors']) - 4} more"
            sanc = ""
            if s["author_sanctioned"]:
                during = s.get("sanctioned_words_during", 0)
                when = {True: "added before the sanction", False: "added after the sanction started",
                        None: "some before, some after"}[s["added_before_sanction"]]
                if during:
                    when += f"; {during} while a sanction was in force"
                sanc = f"{s['sanctioned_words']} of {s['words']} <span class='small'>({when})</span>"
            x = s.get("history") or {}
            hist = []
            if s.get("works_cited"):
                hist.append(f"{s['works_cited']} work{'s' if s['works_cited'] != 1 else ''} cited")
            if x:
                hist.append(f"in place since {escape(x['in_place_since'] or '–')}")
                if x["removed"]:
                    hist.append(f"taken out {x['removed']}× by {x['removing_accounts']} "
                                f"account{'s' if x['removing_accounts'] != 1 else ''}")
            lk = sentence_locks(s, rec, ctx)
            if lk["bans"] or lk["notes"] or lk["tags"]:
                hist.append(lock_badges({**lk, "protection_days": {}, "rfcs": lk["rfcs"]}))
            out.append(f"<tr><td>{escape(s['text'])}</td><td class='small'>{authors}</td>"
                       f"<td class='small'>{sanc}</td><td class='small'>{'<br>'.join(hist) or '–'}</td><td class='small'>"
                       f"{link(WIKI + '/w/index.php?diff=prev&oldid=' + str(s['added_revision']), 'view')}</td></tr>")
        out.append("</table></div>")
        return "".join(out)

    h.append("<h2>Sentence by sentence</h2>")
    h.append("<p class='small'>For each sentence: who wrote its words, how many of them are by a "
             "sanctioned editor, its history (works cited after it, since when it has been in place, "
             "how often it was taken out, and rules that kept it in place), and a link to the edit that "
             "added most of it, so you can check it yourself. Text inside templates (for example unit conversions) is not counted, so a "
             "few sentences show small gaps such as empty brackets.</p>")
    h.append(f"<details open><summary>Opening section ({len(lead_sents)} sentences)</summary>"
             f"{sent_table(lead_sents)}</details>")
    body_s = [s for s in rec["sentences"] if not s["id"].startswith("lead-") and s["author_sanctioned"]]
    if body_s:
        h.append(f"<details><summary>Rest of the article: the {num(len(body_s))} sentences with "
                 f"words by sanctioned editors</summary>{sent_table(body_s)}</details>")

    if ctx.patterns and (ctx.patterns["by_article"].get(title) or {}).get("editors"):
        n = len(ctx.patterns["by_article"][title]["editors"])
        h.append("<h2>This article's editors elsewhere</h2>"
                 f"<p>{link('../editor.html#a=' + slug(title), f'See each of the {n} editors')} who wrote at "
                 "least 1% of this article (or whom Wikipedia has sanctioned), with the other analysed "
                 "articles they wrote in and the sources they cite.</p>")

    h.append("<h2>About these numbers</h2>")
    h.append(f"<p class='small'>Computed from {num(rec['inputs']['history_revisions'])} revisions of "
             f"the article's history, the word-level authorship service WikiWho, and a "
             f"hand-checked list of sanctions. No AI is used to produce any figure. See "
             f"{link('../how-it-works.html', 'How it works')} for the method and its limits, and "
             f"the {link(f'../data/{slug(title)}.json', 'full data')} for every number with its "
             f"source.</p>")
    desc = f"Who wrote the Wikipedia article {title}: authorship, concentration and sanctioned editors."
    body = "".join(h)
    if os.environ.get("WTL_LAYOUT") == "2":   # preview of the sectioned layout (wtl/layout.py)
        from . import glance as g
        from . import layout
        from . import peers
        cards = glance_section(rec, ctx, as_dict=True)
        cards["peers_w"] = peers.card(rec, ctx, "writers")
        cards["peers_s"] = peers.card(rec, ctx, "sources")
        body = layout.regroup(body, cards, g.GLANCE_CSS + peers.CSS, g.GLANCE_JS)
    return page(f"{title} · {NAME}", body, "", depth=1,
                json_alt=f"../data/{slug(title)}.json", description=desc)


# ---------------------------------------------------------------- compare page
COMPARE_ROWS = [
    ("authorship.total_words", "Words of readable text", "int",
     "Prose only: no references, tables, captions or lists of links."),
    ("authorship.editor_count", "Editors with text in the article", "int",
     "How many different editors wrote the words still there today."),
    ("authorship.editors_for_50pct", "Editors who wrote half the text", "int",
     "The smallest number of editors whose words together make up half the text."),
    ("authorship.top_shares.1", "Share by the largest contributor", "pct",
     "Share of the article's words written by the single biggest contributor."),
    ("authorship.top_shares.10", "Share by the top 10 editors", "pct", "Their combined share of the words."),
    ("authorship.lead.top_shares.3", "Opening: share by its top 3 editors", "pct",
     "The opening section is the summary readers, search engines and AI tools see first."),
    ("authorship.survival_article.30d.rate", "New text still there after 30 days", "pct",
     "Of all words ever added to the article, the share still there 30 days later."),
    ("authorship.survival_article.365d.rate", "New text still there after a year", "pct", ""),
    ("authorship.sanctioned_share", "Text by sanctioned editors", "pct",
     "Share of the article's words by editors Wikipedia sanctioned (topic ban in the article's "
     "area, site ban, or sockpuppetry)."),
    ("accountability.concentration.share_of_sanctioned_text", "… of which by the largest sanctioned editor",
     "pct", "The share of the line above that comes from the single largest sanctioned contributor."),
    ("accountability.sanctioned_editors", "Sanctioned editors with text", "int", ""),
    ("authorship.sanctioned_lead_share", "Opening text by sanctioned editors", "pct", ""),
    ("accountability.sanctions_list.seed_rows_in_topic_area", "Hand-checked sanctions for this topic area",
     "int", "How thoroughly sanctions were looked up. Compare sanction figures only between "
     "articles where this is similar."),
]


def fmt(v, kind):
    if v is None:
        return "–"
    return p1(v) if kind == "pct" else f"{v:,.0f}"


def _area_order(ctx):
    from .candidates import AREAS
    present = {ctx.areas.get(r["article"], "") for r in ctx.recs}
    return [a for a in list(AREAS) + [""] if a in present]


def _is_thin(r):
    return any(c["code"] in THIN for c in r.get("caveats", []))


TABLE_COLS = [
    ("authorship.total_words", "Words", "int"),
    ("authorship.editor_count", "Editors", "int"),
    ("authorship.editors_for_50pct", "Half the text by", "int"),
    ("authorship.top_shares.1", "Largest contributor", "pct"),
    ("authorship.top_shares.10", "Top 10 editors", "pct"),
    ("authorship.survival_article.30d.rate", "Still there after 30 days", "pct"),
    ("authorship.sanctioned_share", "Text by sanctioned editors", "pct"),
    ("accountability.sanctioned_editors", "Sanctioned editors", "int"),
]


def compare_page(ctx: Context):
    order = _area_order(ctx)
    h = ["<h1>All articles</h1>",
         f"<p class='lede'>{len(ctx.recs):,} articles analysed so far, grouped by Wikipedia's "
         "contentious topic area and, within each area, by kind of subject, so that people are "
         "shown next to people and news outlets next to news outlets.</p>",
         "<p>Every figure is computed the same way for every article. "
         f"{link('articles.html', 'Which articles are included, and why')}.</p>",
         note("Sanction figures are only comparable between articles whose sanctions lists were "
              "built equally thoroughly. Where an area's list is not yet as thorough as the "
              "Arab–Israeli conflict list, the figure is marked † and no median is given.",
              "Sanction figures"),
         "<p><b>Jump to:</b> " + " · ".join(
             f"<a href='#area-{escape(a or 'none')}'>{escape(area_name(a))}</a>" for a in order)
         + "</p>",
         "<details><summary>What each column means</summary><dl>"]
    for path, name, kind, expl in COMPARE_ROWS:
        if expl:
            h.append(f"<dt><b>{escape(name)}</b></dt><dd>{escape(expl)}</dd>")
    h.append("<dt><b>Typical</b></dt><dd>The median: the middle value of the articles in that "
             "table. Given only when the table has at least four articles.</dd></dl></details>")
    head = ("<tr><th>Article</th>" + "".join(f"<th class='n'>{escape(n)}</th>" for _, n, _ in TABLE_COLS)
            + "</tr>")
    for a in order:
        in_area = [r for r in ctx.recs if ctx.areas.get(r["article"], "") == a]
        h.append(f"<h2 id='area-{escape(a or 'none')}'>{escape(area_name(a))} "
                 f"<span class='small'>({len(in_area)} articles)</span></h2>")
        from .candidates import KINDS
        for kind in KINDS + [""]:
            rows = sorted((r for r in in_area if (ctx.kinds.get(r["article"]) or "") == kind),
                          key=lambda r: r["article"])
            if not rows:
                continue
            h.append(f"<h3>{escape(kind_name(kind))}</h3><div class='scroll'><table>{head}")
            for r in rows:
                h.append(f"<tr><td><a href='articles/{slug(r['article'])}.html'>{escape(r['article'])}</a></td>")
                for path, _, k in TABLE_COLS:
                    mark = " †" if path in SANCTION_PATHS and _is_thin(r) else ""
                    h.append(f"<td class='n'>{fmt(get(r, path), k)}{mark}</td>")
                h.append("</tr>")
            if len(rows) > MIN_PEERS:
                h.append("<tr><td><b>Typical similar article</b></td>")
                for path, _, k in TABLE_COLS:
                    if path in SANCTION_PATHS and any(_is_thin(r) for r in rows):
                        h.append("<td class='n small'>not compared</td>")
                    else:
                        h.append(f"<td class='n'><b>{fmt(median([get(r, path) for r in rows]), k)}</b></td>")
                h.append("</tr>")
            h.append("</table></div>")
    h.append("<p class='small'>† Our sanctions list for this topic is less complete than for the "
             "Arab–Israeli conflict (or the article is in no area with sanctions), so the real "
             "figure is probably higher.</p>")
    h.append(f"<p class='small'>{link('data/summary.json', 'All figures as JSON')}.</p>")
    return page(f"All articles · {NAME}", "".join(h), "compare.html",
                json_alt="data/summary.json", description="Wikipedia articles compared, like with like.")


def choose_page(ctx: Context):
    from .candidates import AREAS, KINDS, SUBJECTS
    done = {r["article"] for r in ctx.recs}
    where = {r["article"]: ctx.areas.get(r["article"], "") for r in ctx.recs}
    cands = ctx.candidates
    h = ["<h1>Which articles, and why</h1>",
         "<p class='lede'>Articles are chosen by a fixed rule, not by hand, so the selection does "
         "not depend on what anyone expects to find.</p>",
         "<h2>The rule</h2><ol>",
         "<li><b>Contentious topic areas.</b> Wikipedia itself marks articles in subject areas "
         "where editing is under special rules (for example the Arab–Israeli conflict, US "
         "politics, gender and sexuality, Eastern Europe). It does this with a notice on each "
         "article's talk page (the discussion page behind every article). Every article with "
         "such a notice is a candidate.</li>",
         "<li><b>Kind of subject.</b> Each candidate is classed as a journalist or commentator, "
         "another public figure, a news outlet, an organisation, an idea or movement, or an event, "
         "using Wikidata (Wikipedia's sister database). Articles that fit none of these, and "
         "“List of…” articles, are left out.</li>",
         "<li><b>Most read.</b> In each area, for each kind, we take the 25 articles that were "
         "read most often over the previous 60 days.</li>",
         "<li><b>On request.</b> A few articles are added on request. They are marked as such.</li>",
         "</ol>",
         "<p><b>Only an article's own talk page counts.</b> Notices and banners are sometimes placed "
         "on the talk page of a redirect (a page that only forwards readers to an article, such as "
         "a misspelling or an old title). Such a tag is not counted for the article it forwards to, "
         "because nobody placed it on that article. This rule was added on 5 November 2026; "
         f"{link('categories.html#redirects', 'the Categories page')} lists the articles it affects "
         "and the redirects that carry the tags.</p>"
         "<p><b>The lists are drawn again from time to time</b>, with fresh page views, so an "
         "article can enter or leave a list as readership changes. An article analysed earlier "
         "keeps its page on this site after it leaves a list.</p>",
         "<h2>A second rule, for subjects Wikipedia does not tag</h2>"
         "<p>Wikipedia does not mark some subjects as contentious, or marks only a small part of "
         "them. These are: China (beyond the Uyghur and Xinjiang area), socialism, Islam, "
         "conservatism and the right, discrimination (including antisemitism and the far right), "
         "and libertarianism (which on Wikipedia also covers liberalism).</p>"
         "<p>For these, we start from the articles that a WikiProject has tagged as its own. A "
         "WikiProject is a group of Wikipedia editors who look after one subject, and they decide "
         "which articles to tag. Steps 2 and 3 above are then the same. These areas are marked "
         "“chosen by subject”, because here we chose the subjects, not Wikipedia.</p><ul>"
         + "".join(f"<li><b>{escape(n.split(' (')[0])}</b>: "
                   + ", ".join(escape(c.split(':', 1)[1].replace(' articles', '')) for c in cats)
                   + "</li>" for n, cats in SUBJECTS.values())
         + "</ul>",
         note("Wikidata's classification is used as it stands, with two rules added on 5 November "
              "2026: movements that Wikidata also records as organisations are placed with ideas and "
              "movements unless Wikidata gives them a headquarters, chairperson or member count; and "
              "a journalist must be described as one in Wikidata, not only have journalism among "
              "their occupations. The Categories page lists the articles each rule moves. An "
              "article can appear in more than one area; it is analysed once and listed in each.",
              "About the classes"),
         f"<p>{link('categories.html', 'How the categories are drawn, and the articles each rule moves')}.</p>",
         f"<p>{len(done):,} articles analysed so far; the rest are queued and are analysed in "
         "batches.</p>",
         "<p><b>Jump to:</b> " + " · ".join(
             f"<a href='#list-{escape(a)}'>{escape(n)}</a>" for a, (n, _) in AREAS.items()
             if any(c["area"] == a for c in cands)) + "</p>"]
    for a, (name, _) in AREAS.items():
        in_area = [c for c in cands if c["area"] == a]
        if not in_area:
            continue
        h.append(f"<h2 id='list-{escape(a)}'>{escape(name)}</h2>")
        for kind in KINDS + [""]:
            rows = [c for c in in_area if (c.get("kind") or "") == kind]
            if not rows:
                continue
            of = next((c["of"] for c in rows if c.get("of")), "")
            h.append(f"<h3>{escape(kind_name(kind))}"
                     + (f" <span class='small'>(top {sum(1 for c in rows if c['reason'] == 'most-read')}"
                        f" of {int(of):,} tagged)</span>" if of else "") + "</h3>")
            h.append("<div class='scroll'><table><tr><th class='n'>Rank</th><th>Article</th>"
                     "<th class='n'>Page views, 60 days</th><th>Status</th></tr>")
            for c in rows:
                t = c["title"]
                if t in done:
                    st = f"<a href='articles/{slug(t)}.html'>analysed</a>"
                    if where.get(t) != a:
                        st += f" <span class='small'>(shown under {escape(area_name(where.get(t)))})</span>"
                else:
                    st = "<span class='small'>queued</span>"
                rank = c.get("rank") or "on request"
                views = f"{int(c['views_60d']):,}" if c.get("views_60d") else "–"
                h.append(f"<tr><td class='n'>{escape(str(rank))}</td><td>{escape(t)}</td>"
                         f"<td class='n'>{views}</td><td>{st}</td></tr>")
            h.append("</table></div>")
    return page(f"Which articles · {NAME}", "".join(h), "articles.html",
                description="How articles are chosen for analysis.")


# ---------------------------------------------------------------- sources
RATING_NAMES = {"gr": "generally reliable", "nc": "no consensus", "gu": "generally unreliable",
                "d": "deprecated", "b": "blacklisted", "m": "varies by period or topic",
                None: "not on Wikipedia's list"}
RATING_ORDER = ["gr", "nc", "m", "gu", "d", "b", None]
AUD_BINS = [(-1.0001, -0.6, "−1 to −0.6"), (-0.6, -0.2, "−0.6 to −0.2"), (-0.2, 0.2, "−0.2 to +0.2"),
            (0.2, 0.6, "+0.2 to +0.6"), (0.6, 1.0001, "+0.6 to +1")]
SOURCE_NOTES = [
    "Wikipedia's own list (Perennial sources) rates about 530 sources that its editors argue "
    "about often. Most sources are not on it; that is not a bad mark.",
    "The quality score (Lin and colleagues, 2023) runs from 0 to 1 and covers news websites. "
    "Books and journals have no score.",
    "Audience leaning says who shares a website, not what it publishes: −1 means only "
    "Democrats shared it, +1 only Republicans, 0 both equally. Out of every 100 people "
    "sharing it, Republicans = (1 + score) ÷ 2 × 100, so −0.4 is about 70 Democrats to 30 "
    "Republicans. It comes from US Twitter users matched to voter records (DomainDemo, 2025; "
    "Robertson and colleagues, 2018) and covers only websites shared widely enough.",
    "Few publishers have a recorded political affiliation, and those records are written by "
    "volunteers on Wikidata and Wikipedia.",
    "The ratings are today's ratings, not the ratings when the footnote was added.",
    "Links between organisations (owner, founder, member of) come from Wikidata, which anyone "
    "can edit. † marks a fact for which Wikidata gives no source.",
]


def categories_page(ctx: Context):
    """Where the site's categories come from, the rules applied on top, and where they place
    articles in ways a reader may not expect (data/categories.json, written by wtl candidates)."""
    from . import candidates as cd
    d = json.loads(cd.CATEGORIES_JSON.read_text(encoding="utf-8")) if cd.CATEGORIES_JSON.exists() else {}
    wd = "https://www.wikidata.org/wiki/"
    def wdl(q):
        return f"<a href='{wd}{escape(q)}'>{escape(q)}</a>"
    def table(items, show_kind=True):
        if not items:
            return "<p class='small'>None.</p>"
        t = ["<div class='scroll'><table><tr><th>Article</th><th>Area</th>"
             + ("<th>Placed as</th>" if show_kind else "") +
             "<th>Wikidata's description</th><th class='n'>Views, 60 days</th><th>In the list</th></tr>"]
        for x in items:
            t.append(f"<tr><td><a href='{WIKI}/wiki/{escape(x['title'].replace(' ', '_'), quote=True)}'>"
                     f"{escape(x['title'])}</a></td><td class='small'>{escape(x['area'])}</td>"
                     + (f"<td class='small'>{escape(kind_name(x['kind'], plural=False))}</td>" if show_kind else "")
                     + f"<td class='small'>{escape(x.get('description') or '–')} ({wdl(x['wikidata'])})</td>"
                     f"<td class='n'>{num(x['views_60d'])}</td><td>{'yes' if x['chosen'] else 'no'}</td></tr>")
        t.append("</table></div>")
        return "".join(t)
    sn_path = cd.ROOT / "data" / "sorting_notes.json"
    sn = json.loads(sn_path.read_text(encoding="utf-8")) if sn_path.exists() else {}
    h_notes = []
    if sn.get("notes"):
        h_notes.append("<h2>Oddities in Wikipedia's own sorting</h2><p>Found while choosing the "
                       "subject areas: places where Wikipedia's notices and WikiProject banners "
                       f"do not sort articles the way their names suggest. {escape(sn.get('note', ''))}</p><ul>")
        for n in sn["notes"]:
            evl = ", ".join(f"<a href='{escape(e['url'])}'>{escape(e['page'])}</a> ({escape(e['date'])})"
                            for e in n["evidence"])
            h_notes.append(f"<li><b>{escape(n['about'])}.</b> {escape(n['fact'])} "
                           f"<span class='small'>Read: {evl}.</span></li>")
        h_notes.append("</ul>")
    h = ["<h1>How articles and sources are sorted</h1>",
         "<p class='lede'>Every figure on this site is grouped by categories: the subject area an "
         "article belongs to, the kind of thing it is about, and the kind of source each citation "
         "is. The categories come from Wikipedia and Wikidata, which volunteers edit, with a few "
         "rules this project adds on top. This page shows where each category comes from, each "
         "added rule with the date it was set, and the articles each rule moves.</p>",
         note("A category decides which articles are compared with which. A different rule would "
              "put some articles in another group, and the group figures would change with it. The "
              "tables below list the articles a rule moves, so a reader can judge the effect.",
              "Why this matters for the figures"),
         "<h2>Subject areas</h2><p>Two sources. <b>Contentious-topic notices</b> are placed on "
         "talk pages under Wikipedia's arbitration and community decisions, and mark subject areas "
         "where editing is under special rules. <b>WikiProject banners</b> are placed by any editor "
         "who judges that an article falls under a group's subject; they are used only for the "
         f"subjects that have no notice (marked “chosen by subject”). {link('articles.html', 'The full rule and lists')}.</p>"]
    if d.get("areas"):
        h.append("<div class='scroll'><table><tr><th>Area</th><th>From</th>"
                 + "".join(f"<th class='n'>{escape(cd.KIND_NAMES[k].split(' and ')[0].split(',')[0])}</th>" for k in cd.KINDS)
                 + "<th class='n'>Places</th><th class='n'>No kind</th></tr>")
        for a, x in d["areas"].items():
            h.append(f"<tr><td>{escape(x['name'])}</td><td class='small'>"
                     f"{'WikiProject banner' if x['rule'] == 'subject' else 'contentious-topic notice'}</td>"
                     + "".join(f"<td class='n'>{num(x['kinds'].get(k, 0))}</td>" for k in cd.KINDS + ['place', 'other'])
                     + "</tr>")
        h.append("</table></div><p class='small'>Articles in each area by kind. For areas chosen "
                 "by subject, articles are classified from the most read down only until each kind "
                 "has its 25, so those counts are of the articles classified, not of the whole "
                 "subject.</p>")
    h.append("<h2>Kinds, from Wikidata</h2><p>Each article's Wikidata item is matched against these "
             "classes (an item belongs to a class if Wikidata records it as an instance of the "
             "class or of a narrower class within it). The first match in this order wins; the "
             "exception for movements is below.</p><div class='scroll'><table><tr><th>Kind</th>"
             "<th>Wikidata classes</th></tr>")
    for k, qs in cd.CLASSES:
        h.append(f"<tr><td>{escape(kind_name(k) if k in cd.KINDS else 'Places (left out)')}</td>"
                 f"<td class='small'>{', '.join(wdl(q) for q in qs)}</td></tr>")
    h.append("</table></div>")
    mv = d.get("movements") or {}
    h.append("<h2>Movements that Wikidata also records as organisations</h2><p>Wikidata records "
             "many social and political movements and ideologies (socialism, anarchism, the "
             "Cultural Revolution) as organisations as well as movements. <b>Rule, from 5 November "
             "2026:</b> an item in both classes stays with organisations only when Wikidata gives it "
             "a headquarters, a chairperson or a member count; otherwise it is placed with ideas and "
             "movements. Before that date every such item counted as an organisation. Under the "
             "rule, Hamas and the Taliban, which have a headquarters and a chairperson in Wikidata, stay "
             "organisations.</p>")
    if mv:
        h.append(f"<p>{num(mv['count'])} articles moved, {num(mv['chosen'])} of them now in the "
                 "lists. The most read:</p>" + table(mv["examples"]))
    jo = d.get("journalists") or {}
    h.append("<h2>Journalists and commentators</h2><p>Wikidata lists journalism among the "
             "occupations of many people known mainly for something else; Karl Marx, Mahatma Gandhi "
             "and Benito Mussolini all wrote for newspapers. <b>Rule, from 5 November 2026:</b> a "
             "person counts as a journalist or commentator when Wikidata lists one of the "
             "occupations journalist, columnist, political commentator, news presenter or pundit, "
             "<i>and</i> Wikidata's one-line English description of them names such a role "
             "(journalist, columnist, commentator, pundit, reporter, correspondent, news presenter "
             "or anchor). Others are placed with other public figures. Before that date the "
             "occupation alone counted. The description is itself written by volunteers.</p>")
    if jo:
        h.append(f"<p>People with a journalism occupation in Wikidata: {num(jo['by_occupation'])}; "
                 f"of them, described as such: {num(jo['by_occupation_and_description'])}. The most "
                 "read of those moved to other public figures:</p>" + table(jo["occupation_only_examples"], False))
    en = d.get("arts_entertainment_sport") or {}
    h.append("<h2>Arts, entertainment and sport</h2><p>WikiProject banners place well-known "
             "actors, musicians and athletes under subjects such as socialism or China, and they "
             "rank high by readership. They are kept as tagged: the rule takes the subject as "
             "Wikipedia's editors drew it. The table lists the articles in the lists whose "
             "Wikidata description names a career in the arts, entertainment or sport, so a reader "
             "can see how many there are.</p>")
    if en:
        by = ", ".join(f"{escape(a)} {n}" for a, n in en.get("by_area", {}).items() if n)
        h.append(f"<p>{num(en['chosen'])} such articles in the lists ({by or 'none'}).</p>"
                 + table(en["examples"]))
    h += h_notes
    lo = d.get("left_out") or {}
    h.append("<h2>Articles left out because they fit no kind</h2><p>Articles about places "
             "(countries, cities, regions) and articles whose Wikidata item matches none of the "
             "classes above are not analysed. Some of them are among the most read in their area.</p>")
    if lo:
        bk = lo.get("by_kind", {})
        h.append(f"<p>{num(lo['count'])} articles: {num(bk.get('place', 0))} places, "
                 f"{num(bk.get('other', 0))} with no matching class. The most read in each area:</p>")
        for a, items in lo.get("examples", {}).items():
            if items:
                h.append(f"<details><summary>{escape(cd.AREAS[a][0])}</summary>{table(items)}</details>")
    vr = d.get("via_redirect") or {}
    if vr:
        h.append("<h2 id='redirects'>Tags and banners on redirects</h2><p>A redirect is a page that sends readers to "
                 "another article, and its talk page can carry a contentious-topic notice or a "
                 "WikiProject banner of its own. Such a tag is not counted for the article the redirect "
                 "points to: an article is in an area only when its own talk page carries the tag. "
                 f"{num(vr.get('articles', 0))} articles would otherwise have been in an area only "
                 "through a redirect. The most read:</p>")
        for ar, items in (vr.get("examples") or {}).items():
            if items:
                def wpl(t, talk=False):
                    u = escape(("Talk:" if talk else "") + t.replace(" ", "_"), quote=True)
                    return f"<a href='{WIKI}/wiki/{u}'>{escape(t)}</a>"
                rows_ = "".join(f"<tr><td>{wpl(x['article'])}</td><td>{wpl(x['tagged_page'], talk=True)}</td>"
                                f"<td class='n'>{num(x['views_60d'])}</td></tr>" for x in items)
                h.append(f"<details><summary>{escape(cd.AREAS[ar][0])} ({num(vr['by_area'].get(ar, 0))})"
                         "</summary><div class='scroll'><table><tr><th>Article</th><th>Talk page of the "
                         "redirect that has the tag</th><th class='n'>Views, 60 days</th></tr>"
                         f"{rows_}</table></div></details>")
    h.append("<h2>How cited sources are sorted</h2><ul>"
             "<li><b>Web address to source.</b> A citation's web address is reduced to its "
             "registrable domain using the Public Suffix List, so news.bbc.co.uk and www.bbc.co.uk are "
             "one source, while blogspot.com subdomains stay separate sites.</li>"
             "<li><b>Wikipedia's rating.</b> The perennial sources list, kept by Wikipedia editors "
             "through discussion; it covers a few hundred of the most-discussed sources.</li>"
             "<li><b>Kind of source</b> (newspaper, publisher, NGO, government body ...), from the "
             "source's Wikidata classes, in the same way as article kinds above.</li>"
             "<li><b>Media Bias/Fact Check</b> labels and <b>JUFO</b> academic levels, each "
             "rater's own scheme, shown under its own name.</li>"
             "<li><b>Books</b> are grouped by the agency that issued the ISBN, which reflects the "
             "language area or country where the ISBN was registered, not necessarily where the "
             "publisher works.</li></ul>"
             f"<p>{link('sources.html', 'The Sources page')} has the full description of each.</p>")
    if d:
        h.append(f"<p class='small'>Built {escape(d.get('built', ''))}. "
                 f"{link('data/categories.json', 'Everything on this page, as JSON')}.</p>")
    return page("How articles and sources are sorted", "".join(h), "categories.html",
                description="Where the site's categories come from, and which articles each rule moves.")


def aud_bin(x):
    return next(lbl for lo, hi, lbl in AUD_BINS if lo <= x < hi)


def source_label(key, ctx):
    """Source name for a table cell, with the web domain underneath when the name is not it."""
    n = src_name(key, ctx)
    dom = "" if key.startswith("name:") or " " in key or n == key else key
    return escape(n) + (f"<br><span class='small'>{escape(dom)}</span>" if dom else "")


def src_name(key, ctx):
    o = ctx.outlets.get(key)
    if o and o.get("name") and not key.startswith("name:"):
        return o["name"]
    if not hasattr(ctx, "_cited_names"):   # most common spelling as cited, across all records
        from collections import Counter
        c = {}
        for r in ctx.recs:
            for x in (r.get("sources") or {}).get("list", []):
                nm = x.get("name_as_cited") or x.get("publisher_name_from_isbn")
                if nm:
                    c.setdefault(x["source"], Counter())[nm] += x["citations"]
        ctx._cited_names = {k: min(v, key=lambda s: (-v[s], s)) for k, v in c.items()}
    if key in ctx._cited_names and key.startswith("name:"):
        return ctx._cited_names[key]
    if o and o.get("name"):
        return o["name"]
    return key[5:] if key.startswith("name:") else key


def profile(pairs, ctx):
    """Citation-weighted summary of (source key, citations) pairs, one entry per rater."""
    from collections import Counter
    tot = sum(n for _, n in pairs)
    rating, align, cls, bins = Counter(), Counter(), Counter(), Counter()
    kinds, fact, acad = Counter(), Counter(), Counter()
    q, a = [], []
    pos, n_pos, pos_src = Counter(), 0, 0
    aff_n, aff_src = Counter(), Counter()
    from .affiliation import position_split
    for k, n in pairs:
        o = ctx.outlets.get(k) or {}
        for lab in (o.get("affiliation") or {}).get("labels") or []:
            aff_n[lab] += n
            aff_src[lab] += 1
        ps = position_split((o.get("affiliation") or {}).get("labels"), o.get("country"))
        if ps:
            n_pos += n
            pos_src += 1
            for side, f in ps.items():
                pos[side] += n * f
        wr = o.get("wikipedia_rating")
        rating[wr["status"] if wr else None] += n
        if o.get("independent_quality"):
            q += [o["independent_quality"]["score"]] * n
        if o.get("audience_leaning"):
            s = o["audience_leaning"]["score"]
            a += [s] * n
            bins[aud_bin(s)] += n
        al = o.get("political_alignment") or []
        for x in al:
            align[x] += n
        if not al:
            align[None] += n
        for x in o.get("classed_as") or []:
            cls[x] += n
        kinds[o.get("kind")] += n
        if (o.get("mbfc") or {}).get("factual_reporting"):
            fact[o["mbfc"]["factual_reporting"]] += n
        if (o.get("academic_level") or {}).get("level") is not None:
            acad[f"level {o['academic_level']['level']}"] += n
    return {"total": tot, "rating": rating, "quality": q, "audience": a, "bins": bins,
            "alignment": align, "classed": cls, "kinds": kinds, "factual": fact, "academic": acad,
            "pos": pos, "n_pos": n_pos, "pos_src": pos_src, "aff_n": aff_n, "aff_src": aff_src}


def _shares(counter, tot, order=None, names=None, none_label="none recorded"):
    keys = order or sorted(counter, key=lambda k: (k is None, -counter[k], str(k)))
    bits = []
    for k in keys:
        n = counter.get(k, 0)
        if n:
            lbl = (names or {}).get(k, k if k is not None else none_label)
            bits.append(f"{escape(str(lbl))} {p0(n / tot)}")
    return " · ".join(bits) or "–"


def profile_rows(pf):
    tot = pf["total"]
    if not tot:
        return []
    rows = [("Wikipedia's own rating", "Perennial sources list",
             _shares(pf["rating"], tot, RATING_ORDER, RATING_NAMES))]
    if pf["quality"]:
        rows.append(("Independent quality score", "Lin et al. 2023; 0 lowest, 1 highest",
                     f"median {median(pf['quality']):.2f}, for the {p0(len(pf['quality']) / tot)} of "
                     f"citations that have a score"))
    else:
        rows.append(("Independent quality score", "Lin et al. 2023", "no cited source has a score"))
    if pf["audience"]:
        rows.append(("Audience leaning", "Robertson et al. 2018; −1 shared only by Democrats, "
                     "+1 only by Republicans",
                     _shares(pf["bins"], len(pf["audience"]), [b[2] for b in AUD_BINS])
                     + f"; median {median(pf['audience']):+.2f}, for the "
                     f"{p0(len(pf['audience']) / tot)} of citations that have a score"))
    if pf.get("factual") and sum(pf["factual"].values()):
        n = sum(pf["factual"].values())
        rows.append(("Factual reporting (MBFC)", "Media Bias/Fact Check",
                     _shares(pf["factual"], n) + f"; for the {p0(n / tot)} of citations that have a label"))
    if pf.get("academic") and sum(pf["academic"].values()):
        n = sum(pf["academic"].values())
        rows.append(("Academic level (JUFO)", "Finnish Publication Forum; 0 to 3",
                     _shares(pf["academic"], n, sorted(pf["academic"]))
                     + f"; for the {p0(n / tot)} of citations to graded publishers and journals"))
    if pf.get("kinds"):
        rows.append(("Kind of source", "Wikidata classes", _shares(pf["kinds"], tot, none_label="not classified")))
    if pf["classed"]:
        rows.append(("Classed on Wikidata as", "state media, public broadcaster, state-owned",
                     _shares(pf["classed"], tot)))
    if pf.get("n_pos"):
        cov, split = position_text(pf["pos"], pf["n_pos"], tot, pf.get("pos_src", 0))
        rows.append(("Recorded left–right position", "Wikidata and Wikipedia categories, placed as "
                     "Wikipedia's articles on each ideology describe it (How it works)",
                     f"{split} out of every 100, for the {cov} of citations to sources with such a label"))
    for name, cell in stance_rows(pf.get("aff_n", Counter()), pf.get("aff_src", Counter()), tot):
        if cell:
            rows.append((f"Recorded as {name}", "Wikidata and Wikipedia categories; share of all "
                         "citations (and number of sources)", cell))
    return rows


def assoc_text(o, limit=None, links=False):
    """Associations recorded on Wikidata, as "founded by X; member of Y"."""
    bits = []
    for rel, vals in (o.get("associations") or {}).items():
        names = [(f"<a href='https://www.wikidata.org/wiki/{escape(v['wikidata'])}'>{escape(v['label'])}</a>"
                  if links else escape(v["label"])) + ("" if v.get("sourced", True) else "†")
                 for v in vals]
        bits.append(f"{escape(rel)} {', '.join(names)}")
    if limit and len(bits) > limit:
        bits = bits[:limit] + [f"and {len(bits) - limit} more"]
    return "; ".join(bits)


def checklist_cell(o):
    """The checklist as text: items found with their evidence, then those not found."""
    cl = o.get("checklist")
    if not cl:
        return "–"
    found, missing = [], []
    for it in cl["items"]:
        if it["found"]:
            links = " ".join(f"<a href='{escape(u)}'>record</a>" for u in it["links"][:3])
            found.append(f"✓ {escape(it['check'])}" + (f": {escape(it['detail'])}" if it["detail"] else "")
                         + (f" {links}" if links else ""))
        else:
            missing.append(escape(it["check"]))
    return ("<br>".join(found) + ("<div class='small'>Not found in these records: "
                                  + "; ".join(missing) + "</div>" if missing else ""))


def _extra(ctx):
    """Wikipedia noticeboard/blacklist records and site self-descriptions, loaded once."""
    if not hasattr(ctx, "_wpd"):
        from . import siteprobe, wpdiscuss
        ctx._wpd = wpdiscuss.load()
        sp = json.loads(siteprobe.SITEPROBE_JSON.read_text(encoding="utf-8")) \
            if siteprobe.SITEPROBE_JSON.exists() else {}
        ctx._probe = sp.get("sites", {})
        ctx._shared = {}
        for n in sp.get("shared_ids", []):
            for d in n["sites"]:
                ctx._shared.setdefault(d, []).append(n)
    return ctx._wpd, ctx._probe, ctx._shared


def wp_record_text(key, ctx, links=True):
    wpd, _, _ = _extra(ctx)
    w = wpd.get(key) or {}
    bits = []
    nb = w.get("noticeboard")
    if nb and nb.get("pages"):
        t = f"Reliable sources noticeboard: {nb['pages']} page{'s' if nb['pages'] != 1 else ''}"
        bits.append(f"<a href='{escape(nb['search_url'])}'>{escape(t)}</a>" if links else escape(t))
    for b in w.get("blacklisted", []):
        t = f"on the {b['list']}"
        bits.append(f"<a href='{escape(b['list_revision'])}'>{escape(t)}</a>" if links else escape(t))
    return " · ".join(bits)


def probe_text(key, ctx, limit=2):
    """What the site says about itself (statements, registry numbers), and whether it shares a
    tracking account with other cited sites."""
    _, probe, shared = _extra(ctx)
    x = probe.get(key)
    bits = []
    if x:
        for st in x.get("statements", [])[:limit]:
            bits.append(f"site says: “{escape(st['text'])}”")
        for r in x.get("registry_ids", [])[:limit]:
            t = f"{r['registry']} {r['id']}"
            bits.append(f"<a href='{escape(r['register_url'])}'>{escape(t)}</a>" if r.get("register_url")
                        else escape(t))
    if shared.get(key):
        others = sorted({d for n in shared[key] for d in n["sites"] if d != key})
        bits.append(f"shares a tracking account with {len(others)} other cited site"
                    f"{'s' if len(others) != 1 else ''}")
    t = _trace(ctx)["sites"].get(key) or {}
    cp = t.get("copies") or {}
    if not (x and (x.get("statements") or x.get("registry_ids"))):
        for st in cp.get("statements", [])[:limit]:
            bits.append(f"saved copy of the site says: “{escape(st['text'])}”")
        for r in cp.get("registry_ids", [])[:limit]:
            tx = f"{r['registry']} {r['id']} (saved copy)"
            bits.append(f"<a href='{escape(r['register_url'])}'>{escape(tx)}</a>" if r.get("register_url")
                        else escape(tx))
    ra = t.get("registered_after_citation")
    if ra:
        e = ra["earlier"][0]
        bits.append(f"domain registration began {escape(ra['registered'])}, after {escape(e['evidence'])} "
                    f"({escape(e['date'])})")
    n = len(_trace(ctx)["shared"].get(key, set()))
    if n:
        bits.append(f"shares a DNS or certificate value with {n} other cited site{'s' if n != 1 else ''}")
    return " · ".join(bits)


def unreachable_reason(status: str) -> str:
    """Plain words for why the site reader could not read a home page."""
    st = status.removeprefix("not reachable: ")
    m = re.match(r"HTTP (\d+)", st)
    if m:
        c = int(m.group(1))
        return {403: "the site refused the request (HTTP 403)", 401: "the site asked for a login (HTTP 401)",
                404: "page not found (HTTP 404)", 410: "page gone (HTTP 410)",
                429: "the site asked for fewer requests (HTTP 429)"}.get(
                    c, f"server error (HTTP {c})" if c >= 500 else f"refused (HTTP {c})")
    if "NameResolution" in st or "nodename" in st:
        return "the domain name does not resolve"
    if "Timeout" in st:
        return "no answer in time"
    if st.startswith("SSLError"):
        return "its security certificate could not be checked"
    if "TooManyRedirects" in st:
        return "redirects in a loop"
    return "the connection failed"


def _diff(rev, text):
    return f"<a href='{WIKI}/w/index.php?diff={int(rev)}'>{escape(text)}</a>"


def link_history_text(key, ctx, article):
    """When the links to a re-registered domain were added to this article and their marks set,
    against the date the registration began, with the diffs."""
    t = _trace(ctx)["sites"].get(key) or {}
    ra = t.get("registered_after_citation")
    links = [x for x in t.get("links", []) if x["article"] == article]
    if not ra or not links:
        return []
    out = []
    for x in sorted(links, key=lambda x: (x["added"], x["added_revision"])):
        bit = (f"link first {_diff(x['added_revision'], 'added ' + x['added'])}, "
               + ("<b>after</b>" if x["added_after_registration"] else "before")
               + " registration began")
        if x.get("text_revision"):
            bit += f" (its text last {_diff(x['text_revision'], 're-typed or moved')})"
        w = x.get("home_title_when_added")
        if w:
            shown = (f"“{escape(w['title'])}”" if w.get("title") else
                     f"no title (HTTP {int(w['status'])})" if w.get("status") else "no copy")
            bit += f"; <a href='{escape(w['copy'])}'>home page that day</a>: {shown}"
        if x.get("mark_revision"):
            bit += (f"; marked “{escape(x['mark'])}” {_diff(x['mark_revision'], 'on ' + x.get('mark_set', ''))}"
                    + (", <b>after</b> registration began" if x["mark_set_after_registration"] else ""))
        else:
            bit += "; no url-status mark"
        bit += "; archived-copy link kept" if x["archive_link"] else "; no archived-copy link"
        out.append(bit)
    return out


def link_flags(key, ctx, article=None):
    """Facts that make a link to this site worth checking: the site could not be read, or its
    domain was registered after it was cited. [] when there are none."""
    _, probe, _ = _extra(ctx)
    x = probe.get(key) or {}
    t = _trace(ctx)["sites"].get(key) or {}
    out = []
    st = x.get("status", "")
    if st.startswith("not reachable"):
        cp = (t.get("copies") or {}).get("status")
        out.append(f"home page could not be read on {escape(x.get('probed', ''))}: "
                   f"{escape(unreachable_reason(st))}"
                   + (f"; {escape(cp)}" if cp else ""))
    ra = t.get("registered_after_citation")
    if ra:
        e = ra["earlier"][0]
        reg = (f"<a href='{escape(ra['rdap'])}'>{escape(ra['registered'])}</a>" if ra.get("rdap")
               else escape(ra["registered"]))
        bit = (f"domain registration began {reg}, after the <a href='{escape(e['url'])}'>archived "
               f"copy of a cited page</a> ({escape(e['date'])})")
        tn = t.get("titles") or {}
        if tn:
            then = f"“{escape(tn['then_title'])}”" if tn.get("then_title") else "no title read"
            now = (f"“{escape(tn['now_title'])}”" if tn.get("now_title") else
                   "not reachable" if not isinstance(tn.get("now_status"), int) or tn["now_status"] >= 400
                   else "no title")
            bit += (f"; home page title <a href='{escape(tn['then_url'])}'>then</a>: {then}; "
                    f"today ({escape(tn['checked'])}): {now}")
            if tn.get("now_url") and sources_reg(tn["now_url"]) not in ("", key):
                bit += f", after a redirect to {escape(sources_reg(tn['now_url']))}"
            if ra.get("title_changed") is not None:
                bit += ("; the two titles share no word" if ra["title_changed"]
                        else "; the two titles share a word")
        names = [n["name"] for n in (t.get("citations_record") or {}).get("names", [])]
        if names:
            bit += "; the citations name it " + ", ".join(f"“{escape(n)}”" for n in names)
        out.append(bit)
        if article:
            out += link_history_text(key, ctx, article)
    if out:
        wp = wp_record_text(key, ctx)
        if wp:
            out.append("Wikipedia's records: " + wp)
    return out


def sources_reg(url):
    from .sources import host_of, registrable
    h = host_of(url) or ""
    return registrable(h) if h else ""


def marks_text(key, ctx, article=None):
    """How the citations themselves mark links to this site (url-status), in one article or all."""
    from collections import Counter
    m = ((_trace(ctx)["sites"].get(key) or {}).get("citations_record") or {}).get("marks") or {}
    c = Counter()
    for a, x in m.items():
        if article is None or a == article:
            c.update(x)
    order = ["live", "dead", "usurped", "unfit", "deviated", "none"]
    return ", ".join(f"{('no mark' if k == 'none' else k)} {v}" for k, v in
                     sorted(c.items(), key=lambda kv: (order.index(kv[0]) if kv[0] in order else 9, kv[0])))


LINKS_NOTE = ("A site our program could not open may work fine in a normal browser: many sites "
              "turn away automatic visitors, and some block whole countries or networks. A website "
              "address registered after the article cited it may have a new owner, or the "
              "registration may simply have been renewed or moved; the site's title then and now "
              "is shown so you can compare. “Wikipedia's mark” is what the footnote itself says "
              "about its link: live, dead, usurped (Wikipedia's word for an address taken over by "
              "someone else), or nothing.")


def links_section(rec, ctx):
    s = rec.get("sources") or {}
    rows = []
    for x in s.get("list", []):
        fl = link_flags(x["source"], ctx, rec["article"])
        if fl:
            rows.append((x, fl))
    if not rows:
        return ""
    h = ["<h3 id='links-to-check'>Links to check</h3><p class='small'>Cited websites whose home page could not be "
         "read, or whose domain was registered after the article cited it. "
         + escape(LINKS_NOTE) + "</p><div class='scroll'><table><tr><th>Source</th>"
         "<th class='n'>Citations</th><th>What was found</th><th>Wikipedia's mark on these citations</th></tr>"]
    rows.sort(key=lambda r: (not (_trace(ctx)["sites"].get(r[0]["source"]) or {}).get("registered_after_citation"),
                             -r[0]["citations"], r[0]["source"]))
    for x, fl in rows:
        h.append(f"<tr><td>{source_label(x['source'], ctx)}</td><td class='n'>{x['citations']}</td>"
                 f"<td class='small'>{'<br>'.join(fl)}</td>"
                 f"<td class='small'>{escape(marks_text(x['source'], ctx, rec['article']) or '–')}</td></tr>")
    h.append("</table></div>")
    return "".join(h)


def _trace(ctx):
    """Fingerprints that do not need the live site (wtl/sitetrace.py), loaded once."""
    if not hasattr(ctx, "_tr"):
        from . import sitetrace
        d = sitetrace.load()
        shared = {}
        for label, g in (d.get("groups") or {}).items():
            for grp in g.get("groups", []):
                for s in grp["sites"]:
                    shared.setdefault(s, set()).update(x for x in grp["sites"] if x != s)
            for a, b in g.get("pairs", []):
                shared.setdefault(a, set()).add(b)
                shared.setdefault(b, set()).add(a)
        ctx._tr = {"sites": d.get("sites", {}), "groups": d.get("groups", {}), "shared": shared}
    return ctx._tr


def _assessor_cells(key, ctx):
    o = ctx.outlets.get(key) or {}
    wr = o.get("wikipedia_rating")
    iq = o.get("independent_quality")
    al = o.get("audience_leaning")
    wd = []
    if o.get("kind"):
        wd.append(f"<b>{escape(o['kind'])}</b>")
    elif o.get("domain_class"):
        wd.append(f"<b>{escape(o['domain_class'])} website</b> (by its domain ending)")
    if o.get("country"):
        wd.append(escape(", ".join(o["country"])))
    if o.get("owned_by"):
        wd.append("owner: " + escape(", ".join(o["owned_by"][:2])))
    if o.get("political_alignment"):
        wd.append("alignment: " + escape(", ".join(o["political_alignment"])))
    if o.get("classed_as"):
        wd.append(escape(", ".join(o["classed_as"])))
    if o.get("associations"):
        wd.append(assoc_text(o, limit=3))
    pt = probe_text(key, ctx, limit=1)
    if pt:
        wd.append(pt)
    rating = RATING_NAMES[wr["status"]] if wr else "–"
    wpt = wp_record_text(key, ctx)
    ents = [e for e in (wr or {}).get("entries", []) if isinstance(e, list)]
    if len(ents) > 1:   # several list entries match this source: show each with its rating
        rating += " (" + "; ".join(f"{n}: {RATING_NAMES.get(st, st)}" for n, st in ents) + ")"
    quality = f"{iq['score']:.2f}" if iq else "–"
    audience = f"{al['score']:+.2f}" if al else "–"
    labels = []
    if o.get("allsides_2018"):
        labels.append(f"AllSides: {o['allsides_2018']}")
    mb = o.get("mbfc")
    if mb:
        labels.append("MBFC: " + ", ".join(x for x in (mb.get("bias"), (mb.get("factual_reporting") or "")
                                                       and f"{mb['factual_reporting']} factual") if x))
    ac = o.get("academic_level")
    acad = (f"{ac['level']}" + (f"<div class='small'>Denmark {ac['denmark_level']}</div>"
                                if ac.get("denmark_level") is not None else "")
            if ac and ac.get("level") is not None else "–")
    return (f"<td class='small'>{escape(rating)}{'<div class=small>' + wpt + '</div>' if wpt else ''}</td>"
            f"<td class='n'>{quality}</td>"
            f"<td class='n'>{audience}</td>"
            f"<td class='small'>{escape(' · '.join(labels) or '–')}</td>"
            f"<td class='n'>{acad}</td>"
            f"<td class='small'>{' · '.join(wd) or '–'}</td>")


ASSESSOR_HEAD = ("<th>Wikipedia's rating</th><th class='n'>Independent quality</th>"
                 "<th class='n'>Audience leaning</th><th>Bias labels</th>"
                 "<th class='n'>Academic level</th><th>Kind, Wikidata facts and the site's own statements</th>")


MEANS_NOTE = (
    "<p class='small'><b>How the summary rows are calculated.</b> For the sources in scope that "
    "have a score s (independent quality, 0 to 1; or audience leaning, −1 to +1), each cited c "
    "times: <b>mean per source</b> = (s<sub>1</sub> + … + s<sub>n</sub>) ÷ n, each source counted "
    "once; <b>mean per citation</b> = (c<sub>1</sub>·s<sub>1</sub> + … + c<sub>n</sub>·s<sub>n</sub>)"
    " ÷ (c<sub>1</sub> + … + c<sub>n</sub>), each source counted as often as it is cited. Both cover "
    "only scored sources: the share of citations they cover is given beside them. The rows "
    "cover every citation in scope, not only the sources listed in the table.</p>")


def _non_source_line(cites, tot):
    from .sources import NOT_A_SOURCE
    bits = [f"{escape(k)} {cites[k]:,} ({p0(cites[k] / tot)})" for k in NOT_A_SOURCE if cites.get(k)]
    if not bits:
        return ""
    return ("<p class='small'>Not listed as sources, because the citation does not identify one: "
            + "; ".join(bits) + f". Shares are of all {tot:,} citations.</p>")


def summary_rows(cites, ctx, lead, tail):
    """Summary rows for a sources table: `cites` is {source: citations} for everything in scope;
    `lead` columns come before the Wikipedia-rating column and `tail` after the audience column."""
    from collections import Counter
    tot = sum(cites.values())
    if not tot:
        return ""
    rating, q, a = Counter(), [], []
    for k, n in cites.items():
        o = ctx.outlets.get(k) or {}
        wr = o.get("wikipedia_rating")
        rating[wr["status"] if wr else None] += n
        if o.get("independent_quality"):
            q.append((o["independent_quality"]["score"], n))
        if o.get("audience_leaning"):
            a.append((o["audience_leaning"]["score"], n))

    def cells(v, fmt):
        if not v:
            return "<td class='n'>–</td>", "<td class='n'>–</td>"
        per_src = sum(x for x, _ in v) / len(v)
        cov = sum(n for _, n in v)
        per_cit = sum(x * n for x, n in v) / cov
        return (f"<td class='n'>{format(per_src, fmt)}<div class='small'>{len(v):,} sources</div></td>",
                f"<td class='n'>{format(per_cit, fmt)}<div class='small'>{p0(cov / tot)} of "
                f"citations</div></td>")
    q1, q2 = cells(q, ".2f")
    a1, a2 = cells(a, "+.2f")
    pad = "<td></td>" * tail
    lab = lambda t: f"<td colspan='{lead}'><b>{t}</b></td>"  # noqa: E731
    return ("<tr class='sum'>" + lab(f"All {tot:,} citations: share by Wikipedia's rating")
            + f"<td class='small' colspan='3'>{_shares(rating, tot, RATING_ORDER, RATING_NAMES)}</td>"
            + pad + "</tr>"
            + "<tr class='sum'>" + lab("Mean per source") + "<td></td>" + q1 + a1 + pad + "</tr>"
            + "<tr class='sum'>" + lab("Mean per citation") + "<td></td>" + q2 + a2 + pad + "</tr>")


FLAG_NAMES = {"opinion": "opinion, comment or blog section", "no_link": "no web link",
              "book_without_page": "book with no page number", "not_english": "not in English",
              "not_english_no_quote": "not in English, with no quote or translation",
              "dead_link_no_archive": "dead link with no archived copy",
              "paywall_or_registration": "behind a paywall or registration"}


def flags_html(s):
    f = s.get("flags")
    if not f:
        return ""
    tot = s["citations"]
    bits = " · ".join(f"{escape(FLAG_NAMES[k])} {num(v)} ({p0(v / tot)})" for k, v in f.items() if v)
    out = [f"<h3>Opinion and harder-to-check citations</h3><p class='small'>Of the article's "
           f"{num(tot)} citations: {bits or 'none'}. We spot opinion pieces "
           "from the web address (such as /opinion/ or a blog) or from the footnote's own label. A "
           "book counts as not in English when the footnote says so, or when Open Library lists the "
           "book only in other languages. <i>No quote or translation</i> means the footnote does not "
           "copy out the passage it relies on, so a reader who does not know the language cannot "
           "check it. Each of these makes a footnote harder to check, not wrong.</p>"]
    rows = [(l, e) for l, e in s.get("flags_by_editor", {}).items() if l != "unknown"][:10]
    if rows:
        out.append("<div class='scroll'><table><tr><th>Editor</th><th class='n'>Citations added</th>"
                   + "".join(f"<th class='n'>{escape(FLAG_NAMES[k])}</th>" for k in FLAG_NAMES) + "</tr>")
        for l, e in rows:
            out.append(f"<tr><td>{escape(l)}</td><td class='n'>{e['citations']}</td>"
                       + "".join(f"<td class='n'>{e.get(k) or '–'}</td>" for k in FLAG_NAMES) + "</tr>")
        out.append("</table></div><p class='small'>The ten editors who added the most citations "
                   "still in the article.</p>")
    return "".join(out)


def _activity(ctx):
    if not hasattr(ctx, "_act"):
        from . import activity
        ctx._act = activity.load().get("articles", {})
        p = activity.STALE_JSON
        ctx._stale = json.loads(p.read_text(encoding="utf-8")).get("articles", {}) if p.exists() else {}
    return ctx._act, ctx._stale


def activity_section(rec, ctx):
    act, stale = _activity(ctx)
    e = act.get(rec["article"])
    if not e or e.get("revision") != rec["revision"]:
        return ""
    y = e["last_365_days"]
    h = ["<h2>How often the article changes</h2>",
         f"<p>First edit {escape(e['first_edit'])}; {num(e['edits_total'])} edits up to the analysed "
         f"revision. In the year before it ({escape(y['from'])} to {escape(y['to'])}): "
         f"<b>{num(y['edits'])}</b> edits by {num(y['accounts'])} accounts"
         + (f", {p0(y['share_without_registered_account'])} of the edits without a registered account"
            if y.get("share_without_registered_account") is not None else "") + ".</p>"]
    from . import timeline
    h.append(timeline.CSS + timeline.svg(e, rec["revision_timestamp"][:10]))
    sd = e.get("subject_date")
    if sd and sd.get("date"):
        yr = sd["date"][:4].lstrip("0") or "0"
        h.append(f"<p class='small'>Subject's own date in Wikidata ({escape(sd['label'])}): "
                 f"<a href='https://www.wikidata.org/wiki/{escape(sd['wikidata'])}'>{escape(yr)}</a>.</p>")
    pr = e.get("protection")
    if pr:
        names = {"autoconfirmed": "accounts at least 4 days old with 10 edits",
                 "extendedconfirmed": "accounts at least 30 days old with 500 edits",
                 "sysop": "administrators only", "templateeditor": "template editors",
                 "none": "anyone"}
        if pr["events_up_to_revision"]:
            acts = ", ".join(f"{escape(k)} {v}" for k, v in sorted(pr["by_action"].items()))
            h.append(f"<p class='small'><b>Protection.</b> {pr['events_up_to_revision']} "
                     f"{'entry' if pr['events_up_to_revision'] == 1 else 'entries'} in "
                     f"Wikipedia's protection log up to the analysed revision ({acts}), "
                     + (f"on {escape(pr['first'])}." if pr['first'] == pr['latest'] else
                        f"from {escape(pr['first'])} to {escape(pr['latest'])}.") + f" Editing today ({escape(pr['checked'])}): "
                     f"{escape(names.get(pr['today'], pr['today']))}.</p>")
        else:
            h.append(f"<p class='small'><b>Protection.</b> No entries in Wikipedia's protection log up to "
                     f"the analysed revision. Editing today: {escape(names.get(pr['today'], pr['today']))}.</p>")
    b = e.get("back_and_forth")
    if b:
        h.append(f"<p><b>Back-and-forth.</b> Of the {num(b['words'])} words in the analysed text, "
                 f"<b>{num(b['words_removed_twice_or_more'])}</b> ({p1(b['share'])}) were taken out and "
                 "put back at least twice, each time staying out for a day or more; "
                 f"{num(b['words_removed_five_times_or_more'])} at least five times. Separately, "
                 f"{num(b['words_with_quick_repair'])} words ({p1(b['quick_repair_share'])}) were removed "
                 "and put back within a day at least once, which is how vandalism and its repair "
                 "usually look.</p>")
        if b.get("passages"):
            h.append("<div class='scroll'><table><tr><th>Passage (opening words, as wikitext)</th>"
                     "<th class='n'>Words</th><th class='n'>Times removed</th><th>Latest removal or "
                     "restoration</th></tr>")
            for p_ in b["passages"]:
                tr = (str(p_["times_removed_min"]) if p_["times_removed_min"] == p_["times_removed_max"]
                      else f"{p_['times_removed_min']}–{p_['times_removed_max']}")
                h.append(f"<tr><td class='small'>{escape(p_['start'])}</td><td class='n'>{p_['words']}</td>"
                         f"<td class='n'>{tr}</td><td class='small'>"
                         f"<a href='{WIKI}/w/index.php?diff={int(p_['latest_revision'])}'>{escape(p_['latest'])}</a></td></tr>")
            h.append("</table></div>")
    st = stale.get(rec["article"])
    if st and st.get("analysed_revision") == rec["revision"]:
        h.append(f"<p class='small'>Since the analysed revision: {num(st['edits_since'])} edits "
                 f"(checked {escape(st.get('checked', ''))}; latest {escape(st.get('latest') or '–')}).</p>")
    h.append("<p class='small'>Busy pages are not necessarily disputed: a subject in the news, "
             "vandalism and its repair, and routine tidying all add edits. The figures stop at the "
             f"analysed revision. {link('../data/activity.json', 'All articles, as JSON')}.</p>")
    return "".join(h)


# ---------------------------------------------------------------- the opening, then and now
TN_CSS = """<style>
:root{--del-bg:#fbe3df;--del-fg:#8a1c0b;--ins-bg:#dff3e6;--ins-fg:#0d5a2c}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--del-bg:#4a1f19;--del-fg:#ffb4a6;--ins-bg:#173a25;--ins-fg:#9fe3b8}}
:root[data-theme="dark"]{--del-bg:#4a1f19;--del-fg:#ffb4a6;--ins-bg:#173a25;--ins-fg:#9fe3b8}
del.d{background:var(--del-bg);color:var(--del-fg);text-decoration:line-through;text-decoration-thickness:1px}
ins.a{background:var(--ins-bg);color:var(--ins-fg);text-decoration:underline;text-decoration-thickness:1px}
.tn{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:12px 0}
@media (max-width:820px){.tn{grid-template-columns:1fr}}
.tn .pair{border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:.92rem}
.tn .when{font-size:.78rem;color:var(--muted);text-transform:uppercase;letter-spacing:.03em;margin:2px 0}
.tn p{margin:2px 0 10px}
.mini{display:inline-block;width:150px;max-width:100%;text-align:left;vertical-align:middle}
.mini .v{font-weight:600;font-variant-numeric:tabular-nums}
.mini .trk{position:relative;height:6px;border-radius:3px;background:var(--line);margin:5px 0 2px}
.mini .dot{position:absolute;top:50%;width:12px;height:12px;margin:-6px 0 0 -6px;border-radius:50%;background:var(--fg,#0b0b0b);border:2px solid var(--bg,#fff)}
.mini .ends{display:flex;justify-content:space-between;font-size:.68rem;color:var(--muted)}
.mini .cov{height:6px;border-radius:3px;background:var(--line);overflow:hidden;margin:7px 0 2px}
.mini .cov i{display:block;height:100%;background:var(--muted)}
.mini .split{display:flex;height:10px;border-radius:3px;overflow:hidden;gap:2px;margin:5px 0 2px}
.mini .split:not(.lcr) i:first-child{background:var(--g-dem,#2a78d6)}.mini .split:not(.lcr) i:last-child{background:var(--g-rep,#e34948)}
.mini .split.lcr i.l{background:var(--g-c1,#2a78d6)}.mini .split.lcr i.c{background:var(--muted)}.mini .split.lcr i.r{background:var(--g-c2,#eb6834)}
.mnote{font-size:.72rem;color:var(--muted);line-height:1.25}
.tn.four{width:100%}
.tn.four.n4{grid-template-columns:repeat(4,minmax(0,1fr))}
.tn.four.framed2{grid-template-columns:repeat(3,minmax(0,1fr))}
.tn.four.rows .pair{grid-row:span 8;display:grid;grid-template-rows:subgrid;row-gap:0;align-content:start}
.tn.rows .senx,.tn.rows .srcm{display:none}
.tn.rows.x-src .srcm{display:block}
.tn.rows.x-sen .senx{display:block}
.tn.rows .scell{padding:4px 0 2px}
.tn.rows .senx .scell{border-top:1px dashed var(--line);padding-top:6px}
.tn.rows .sno{float:left;font-size:.75rem;color:var(--muted);margin:3px 6px 0 0}
.tn.rows .xrow{border-top:1px solid var(--line);padding-top:4px;margin-top:4px}
.tn.rows .xbtn{font:inherit;font-size:.84rem;background:none;border:0;padding:2px 0;color:var(--link);cursor:pointer;text-align:left}
.tn.rows .xbtn::before{content:"▸ ";color:var(--muted)}
.tn.rows.x-src .xbtn[data-x=src]::before,.tn.rows.x-sen .xbtn[data-x=sen]::before{content:"▾ "}
.tn.rows .xb{display:none;font-size:.86rem;padding:4px 0 6px}
.tn.rows.x-src .src .xb,.tn.rows.x-sen .sen .xb
.tn .sdwhen{font-size:.75rem;color:var(--muted);font-variant-numeric:tabular-nums}
.tn.rows .sdl li{margin:0 0 8px;list-style:none}
.tn.rows .sdl{padding-left:0}
.tn.rows .slist{margin:2px 0 8px;padding-left:16px}
.tn.rows .slist li{margin:1px 0}
.tn.rows .ms{margin:6px 0;border-top:1px dashed var(--line);padding-top:4px}
.tn.rows .ml{font-size:.76rem;color:var(--muted)}
.tn.rows .sp{margin:0 0 8px}
.tn .pair.framed{background:var(--soft)}
.tn .fadd{background:var(--ins-bg);color:var(--ins-fg);border-radius:3px;padding:0 2px}
.tn .fback{background:color-mix(in srgb,#8a63d2 16%,transparent);border-radius:3px;padding:0 2px}
.tn.four.n3{grid-template-columns:repeat(3,minmax(0,1fr))}
.tn.four.n2{grid-template-columns:repeat(2,minmax(0,1fr))}
@media (max-width:1150px){.tn.four.n4{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:820px){.tn.four.n4,.tn.four.n3{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:620px){.tn.four.n4,.tn.four.n3,.tn.four.n2{grid-template-columns:1fr}}
.tn .when a{font-weight:600}
.tn .sd,.tl .sd{font-size:.85rem;color:var(--muted);margin:2px 0 6px}
.tl td.par{min-width:300px;font-size:.92rem}
.tl td:first-child{min-width:110px}
</style>"""


def _then_now(ctx):
    if not hasattr(ctx, "_tnd"):
        p = ROOT / "data" / "then_now.json"
        ctx._tnd = json.loads(p.read_text(encoding="utf-8")).get("articles", {}) if p.exists() else {}
    return ctx._tnd


def diff_html(ops, side):
    """side "old": unchanged and removed words; side "new": unchanged and added words."""
    out = []
    for op, txt in ops:
        if op == "=":
            out.append(escape(txt))
        elif op == "-" and side == "old":
            out.append(f"<del class='d'>{escape(txt)}</del>")
        elif op == "+" and side == "new":
            out.append(f"<ins class='a'>{escape(txt)}</ins>")
    return " ".join(out)


def glance_section(rec, ctx, as_dict=False):
    from . import glance as g
    out = ctx.outlets or {}
    links_n = sum(1 for x in (rec.get("sources") or {}).get("list", []) if link_flags(x["source"], ctx, rec["article"]))
    here = writers = everyone = None
    if out:
        c = cited_figures(rec, ctx).get("audience_leaning_dd")
        if c:
            here = (c["mean"], c["citations_covered"])
        w = (((ctx.patterns or {}).get("by_article", {}).get(rec["article"]) or {}).get("writers") or {}).get("audience_leaning_dd")
        if w and w.get("mean") is not None:
            writers = (w["mean"], None)
        if not hasattr(ctx, "_base_lean"):
            ctx._base_lean = baseline_leaning(ctx)
        if ctx._base_lean.get("audience_leaning_dd") is not None:
            everyone = (ctx._base_lean["audience_leaning_dd"], None)
    named = {"writers": g.card_writers(rec), "sanctioned": g.card_sanctioned(rec),
             "kinds": g.card_kinds(rec, out), "academic": g.card_academic(rec, out),
             "checkable": g.card_checkable(rec, links_n), "sharers": g.card_sharers(here, writers, everyone)}
    if as_dict:
        return named
    cards = [c for c in named.values() if c]
    if not cards:
        return ""
    return (g.GLANCE_CSS + "<h2 style='border:0;margin-top:20px'>At a glance</h2>"
            "<p class='small'>The main figures, drawn. Point at or tab to a bar for its exact number; "
            "each is explained in full further down. These are measurements with their sources, not verdicts.</p>"
            "<div class='gl'>" + "".join(cards) + "</div>" + g.GLANCE_JS)


def then_now_top(rec, ctx) -> str:
    """The first paragraph side by side on each date, then two template columns (wtl/framing.py).
    Each column has four rows: heading, paragraph, sources cited in it, and the sentences that
    changed most; the last two open together across all columns."""
    from . import glance as g
    t = _then_now(ctx).get(rec["article"]) or {}
    vs = t.get("versions") or []
    fc = t.get("first_paragraph_change")
    if t.get("revision") != rec["revision"] or len(vs) < 2 or not fc:
        return ""
    base, now_v = vs[0], vs[-1]
    by = base["date"][:4]
    dates = ", ".join(v["date"] for v in vs[:-1])
    mc = t.get("most_changed") or {}
    framed = _framed_cols(rec, ctx, vs)
    h = [TN_CSS, g.GLANCE_CSS, g.OPEN_CSS, "<h2 style='border:0;margin-top:20px'>How the opening has changed</h2>",
         f"<p class='small'>The whole first paragraph on {escape(dates)} and in the version analysed "
         f"here ({escape(now_v['date'])}), as each read. Press <b>Play</b> on a version to watch the one "
         "before it turn into it: <span style='background:var(--del-bg);color:var(--del-fg);text-decoration:line-through'>"
         "words taken out</span> fade in red, <span style='background:var(--ins-bg);color:var(--ins-fg)'>words "
         "added</span> appear in green. Above each, the short description: the line Wikipedia shows under "
         "the title in its search box and apps. Until about 2018 that line came from Wikidata, not from "
         "the article, so older versions often show none here. Under every paragraph, <b>short description changes</b>: each change to that line made since the "
         "column before (<b>Play</b> steps the line through them, with their dates, while the paragraph changes) (checked through the page history from 2017, when articles began to set it "
         f"themselves; {link('../how-it-works.html#shortdesc', 'how')}); changes put back within a day are "
         "folded. <b>Sources cited</b> opens, under every "
         "column, the footnotes placed inside that first paragraph, read the same way as the article's, "
         "with today's ratings; many first paragraphs cite nothing, because Wikipedia's guideline lets the "
         "opening rest on sources cited further down (the whole article's sources at each date are under "
         "<a href='#sources-then-now'>Sources cited</a>). <b>Sentences that changed most</b> opens three "
         f"rows: today's three most-changed opening sentences, each traced back through every date (at each, "
         f"the opening sentence with most words in common, by a fixed rule), and through the two template "
         "columns; <b>Play</b> on a sentence shows its change from the column before. "
         f"{link('../how-it-works.html#numbers', 'How this is compared')}.</p>"
         "<p class='playall'><button type='button' class='playb' id='tn-playall' style='font:inherit;"
         "border:1px solid var(--line);background:transparent;color:var(--link);border-radius:6px;"
         f"padding:3px 9px;cursor:pointer'>▶ Play all, {escape(by)} to today</button></p>"
         f"<div class='tn four rows n{len(vs)}{' framed2' if framed else ''}'>"]

    # sources row: the same measures in every column, so they line up
    have_src = bool(ctx.outlets) and any(v.get("first_paragraph_sources") for v in vs)
    src_lists = [v.get("first_paragraph_sources") or [] for v in vs]
    if framed:
        now_src = src_lists[-1]
        kept = dict(now_src)
        for w in framed[1]["back_works"]:
            if w.get("source"):
                kept[w["source"]] = kept.get(w["source"], 0) + 1
        src_lists += [now_src, sorted(kept.items(), key=lambda x: (-x[1], x[0]))]
    measures = _src_rows([_src_profile(x, ctx) for x in src_lists]) if have_src else []

    def src_cell(i, pairs, extra=""):
        if not have_src:
            return ""
        top = sorted(pairs, key=lambda x: (-x[1], x[0]))
        lst = ("<ul class='slist'>" + "".join(f"<li>{source_label(k, ctx)} <span class='mnote'>×{n}</span></li>"
                                             for k, n in top[:8])
               + (f"<li class='mnote'>and {len(top) - 8} more</li>" if len(top) > 8 else "") + "</ul>"
               if top else "<p class='mnote'>No footnote inside this first paragraph.</p>")
        ms = "".join(f"<div class='ms'><div class='ml'>{lbl}</div><div class='mv'>{cells[i]}</div></div>"
                     for lbl, cells in measures)
        return (f"<div class='xrow src'><button type='button' class='xbtn' data-x='src'>Sources cited "
                f"({sum(n for _, n in pairs)})</button><div class='xb'>{extra}{lst}</div></div>"
                f"<div class='xrow srcm'><p class='ml'>How these sources are rated (today's ratings)</p>{ms}</div>")

    pairs = mc.get("pairs") or []
    labels = ["1 January " + v["date"][:4] for v in vs[:-1]] + ["the analysed version"]
    sdh = _shortdesc_of(rec)
    sd_all = (sdh or {}).get("changes") or []
    sd_quick = _undone_within_a_day(sd_all)

    def sd_cell(i):
        if sdh is None:
            return ""
        lo = vs[i - 1]["date"] if i else ""
        hi = vs[i]["date"] if not vs[i].get("analysed") else "9999"
        idx = [k for k, c in enumerate(sd_all) if lo <= c["timestamp"][:10] < hi]
        main = [sd_all[k] for k in idx if k not in sd_quick]
        quick = [sd_all[k] for k in idx if k in sd_quick]
        since = f"since {labels[i - 1]}" if i else f"before {labels[0]}"
        body = ("<ul class='slist sdl'>" + "".join(_sd_change_html(c) for c in main) + "</ul>" if main else
                f"<p class='mnote'>No lasting change {escape(since)}.</p>")
        if quick:
            body += (f"<details><summary class='mnote'>{len(quick)} changes put back within a day (how vandalism "
                     "and its repair usually look)</summary><ul class='slist sdl'>"
                     + "".join(_sd_change_html(c) for c in quick) + "</ul></details>")
        return (f"<div class='xrow sdh'><p class='ml'>Short description changes {escape(since)} "
                f"({len(main)}{f', plus {len(quick)} put back within a day' if quick else ''})</p>{body}</div>")

    def sd_blank():
        return ("<div class='xrow sdh'><p class='ml'>Short description</p><p class='mnote'>Same short "
                "description as the analysed version.</p></div>") if sdh is not None else ""

    def sd_steps(i):
        """The lasting short-description changes between the column before and this one, for the
        animation: [{d: date, ops: word diff, to: wording after}]."""
        if sdh is None or not i:
            a, b = (vs[i - 1].get("short_description") if i else None), vs[i].get("short_description")
            return ([{"d": "", "ops": _exact_ops(a or "", b or "") if a and b else
                      ([["-", a]] if a else []) + ([["+", b]] if b else []), "to": b or "none"}]
                    if i and a != b else [])
        lo, hi = vs[i - 1]["date"], (vs[i]["date"] if not vs[i].get("analysed") else "9999")
        out = []
        for k, c in enumerate(sd_all):
            if k in sd_quick or c.get("present_at_start") or not (lo <= c["timestamp"][:10] < hi):
                continue
            a, b = c["from"] or "", c["to"] or ""
            ops = _exact_ops(a, b) if a and b else ([["-", a]] if a else []) + ([["+", b]] if b else [])
            out.append({"d": c["timestamp"][:10], "ops": ops, "to": b or "none"})
        return out

    def path_of(pr):
        if pr.get("path"):
            return pr["path"]
        mid = [{"text": None, "diff_from_previous": None} for _ in vs[1:-1]]
        return ([{"text": pr["old"], "diff_from_previous": None}] + mid
                + [{"text": pr["new"], "diff_from_previous": pr["diff"]}])

    def cell(k, text_html, play):
        return f"<div class='scell'{' data-play' if play else ''}><span class='sno'>{k}</span>{text_html}</div>"

    def version_cells(i):
        out = []
        for k, pr in enumerate(pairs, 1):
            st = path_of(pr)[i]
            if not st["text"]:
                out.append(cell(k, "<p class='mnote'>No similar sentence in this version's opening.</p>", False))
                continue
            prev = next((labels[j] for j in range(i - 1, -1, -1) if path_of(pr)[j]["text"]), "")
            play = ""
            if st.get("diff_from_previous"):
                play = (f"<button type='button' class='playb'>▶ Play the change from {escape(prev)}</button>"
                        f"<script type='application/json' class='ops'>{g.ops_json(st['diff_from_previous'])}</script>")
            out.append(cell(k, f"{play}<p class='para' data-plain='{escape(st['text'], quote=True)}'>"
                               f"{escape(st['text'])}</p>", bool(play)))
        return out

    def sen_rows(cells):
        if not cells:
            return ""
        return (f"<div class='xrow sen'><button type='button' class='xbtn' data-x='sen'>Sentences that "
                f"changed most</button><div class='xb'>{cells[0]}</div></div>"
                + "".join(f"<div class='xrow senx'>{c}</div>" for c in cells[1:]))

    for i, v in enumerate(vs):
        url = rec["permalink"] if v.get("analysed") else f"{WIKI}/w/index.php?oldid={v['revision']}"
        label = "Analysed version" if v.get("analysed") else f"1 January {v['date'][:4]}"
        sd = v.get("short_description")
        ns = v.get("first_paragraph_sentences", 0)
        par = v["first_paragraph"]
        play, data = "", ""
        if i and v.get("diff_from_previous"):
            data += f"<script type='application/json' class='ops'>{g.ops_json(v['diff_from_previous'])}</script>"
        steps = sd_steps(i)
        if i and steps:
            data += f"<script type='application/json' class='sdsteps'>{json.dumps(steps, ensure_ascii=False)}</script>"
        if data:
            prev = "1 January " + vs[i - 1]["date"][:4]
            play = f"<button type='button' class='playb'>▶ Play the change from {escape(prev)}</button>{data}"
        sen = version_cells(i)
        h.append(f"<div class='pair'{' data-play' if play else ''}><div class='hd'><div class='when'>{link(url, label)}</div>"
                 f"<div class='sd'>{num(v.get('first_paragraph_words', 0))} words, {ns} "
                 f"sentence{'s' if ns != 1 else ''}<br>Short description: "
                 f"<span class='sdt' data-plain='{escape(sd or 'none', quote=True)}'>{escape(sd) if sd else '<i>none</i>'}</span>"
                 f" <span class='sdwhen'></span></div>{play}</div>"
                 f"<p class='para' data-plain='{escape(par, quote=True)}'>{escape(par) or '–'}</p>"
                 f"{sd_cell(i)}{src_cell(i, src_lists[i])}{sen_rows(sen)}</div>")
    if framed:
        from . import framing
        v_ = _voice_of(rec)
        c_sent = []
        for pr in pairs:     # each most-changed sentence through the same two templates
            cs = framing.columns(pr["new"], v_, [], lambda k: src_name(k, ctx) if k else "")
            c_sent.append(("".join(_seg_html(x) for x in cs[0]), "".join(_seg_html(x) for x in cs[1]))
                          if cs else (escape(pr["new"]), escape(pr["new"])))
        from .layout import std_popup
        std = std_popup("opening")
        for j, c in enumerate(framed):
            extra = ("<p class='mnote'>The same as the analysed version.</p>" if j == 0 else
                     "<p class='mnote'>The analysed version's, plus the works put back:</p><ul class='slist'>"
                     + "".join(f"<li>{escape(_join_names(w['authors']) or src_name(w.get('source'), ctx) or '–')}"
                               f"{(' — <i>' + escape(w['title'][:90]) + '</i>') if w.get('title') else ''}</li>"
                               for w in c["back_works"]) + "</ul>" if c["back_works"] else
                     "<p class='mnote'>No work was put back.</p>")
            before = now_v["first_paragraph"] if j == 0 else _plain(framed[0]["para"])
            play, attrs = _playable(before, c["para"], "the analysed version" if j == 0 else "the column before")
            cells = []
            for k, (pr, (s5, s6)) in enumerate(zip(pairs, c_sent), 1):
                mine = s5 if j == 0 else s6
                pl, at = _playable(pr["new"] if j == 0 else _plain(s5), mine,
                                   "the analysed version" if j == 0 else "the column before")
                cells.append(cell(k, f"{pl}<p class='para'{at}>{mine}</p>", bool(pl)))
            h.append(f"<div class='pair framed'{' data-play' if play else ''}><div class='hd'><div class='when'>"
                     f"{escape(c['label'])}</div>"
                     f"<div class='sd'>{c['hint']} {link('../how-it-works.html#framed', 'How')} {std}</div>{play}</div>"
                     f"<p class='para'{attrs}>{c['para']}</p>{sd_blank()}"
                     f"{src_cell(len(vs) + j, src_lists[len(vs) + j], extra) if have_src else ''}"
                     f"{sen_rows(cells)}</div>")
    h.append("</div>" + g.OPEN_JS + XROW_JS)
    if fc.get("words_then"):
        h.append(f"<p class='small'>From {escape(by)} to the analysed version: of the "
                 f"{num(fc['words_then'])} words of the {escape(by)} first paragraph, "
                 f"{num(fc['kept'])} ({p0(fc['share_kept'])}) are still there in the same order; "
                 f"{num(fc['taken_out'])} were taken out and {num(fc['added'])} added. Content words in "
                 f"common: {fc['similarity']:.2f} (0 none, 1 all).</p>")
    return "".join(h)


_SD: dict = {}


def _shortdesc_of(rec):
    """This article's entry in data/shortdesc.json (wtl/shortdesc.py), for the analysed revision."""
    if "d" not in _SD:
        p = ROOT / "data" / "shortdesc.json"
        _SD["d"] = json.loads(p.read_text(encoding="utf-8")).get("articles", {}) if p.exists() else {}
    e = _SD["d"].get(rec["article"])
    return e if e and e.get("revision") == rec["revision"] else None


def _undone_within_a_day(chs):
    """Indices of changes put back to the earlier wording within 24 hours, and the changes that
    put it back (how vandalism and its repair usually look)."""
    import datetime as _dt
    t = [_dt.datetime.fromisoformat(c["timestamp"].replace("Z", "+00:00")) for c in chs]
    quick = set()
    for k, c in enumerate(chs):
        for j in range(k + 1, len(chs)):
            if (t[j] - t[k]).total_seconds() > 86400:
                break
            if chs[j]["to"] == c["from"]:
                quick.update(range(k, j + 1))
                break
    return quick


def _exact_ops(a: str, b: str) -> list:
    """Word diff that keeps capitals as written (a short description is short enough that a
    change of case is a change)."""
    import difflib
    x, y = a.split(), b.split()
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, x, y, autojunk=False).get_opcodes():
        if tag == "equal":
            out.append(["=", " ".join(x[i1:i2])])
        else:
            if i2 > i1:
                out.append(["-", " ".join(x[i1:i2])])
            if j2 > j1:
                out.append(["+", " ".join(y[j1:j2])])
    return out


def _sd_change_html(c):
    diff_ops = _exact_ops
    when = escape(c["timestamp"][:10])
    if c.get("present_at_start"):
        return (f"<li><span class='mnote'>already there on {when}</span><br>"
                f"{escape(c['to'])}</li>")
    url = f"{WIKI}/w/index.php?diff={c['revision']}" + (f"&oldid={c['parent']}" if c.get("parent") else "")
    a, b = c["from"] or "", c["to"] or ""
    ops = diff_ops(a, b) if a and b else []
    old = diff_html(ops, "old") if ops else ("<i>none</i>" if not a else f"<del class='d'>{escape(a)}</del>")
    new = diff_html(ops, "new") if ops else ("<i>none</i>" if not b else f"<ins class='a'>{escape(b)}</ins>")
    return (f"<li><span class='mnote'>{when} · <a href='{url}'>the edit</a></span><br>{old}<br>→ {new}</li>")


def _join_names(authors):
    return ", ".join(authors[:3]) + (f" and {len(authors) - 3} others" if len(authors) > 3 else "")


XROW_JS = """<script>
(function(){document.querySelectorAll('.tn.rows').forEach(function(box){
 box.addEventListener('click',function(e){var b=e.target.closest('.xbtn');if(!b)return;
  var on=box.classList.toggle('x-'+b.dataset.x);
  box.querySelectorAll('.xbtn[data-x="'+b.dataset.x+'"]').forEach(function(x){x.setAttribute('aria-expanded',on)});});
 box.querySelectorAll('.xbtn').forEach(function(x){x.setAttribute('aria-expanded','false')});});})();
</script>"""


def position_text(pos: dict, n_pos: float, tot: float, n_src: int = 0) -> tuple[str, str]:
    """(coverage, split) for citations placed on the left-right line by their recorded labels."""
    if not tot:
        return "–", "–"
    cov = p0(n_pos / tot) + (f" ({n_src} source{'s' if n_src != 1 else ''})" if n_src else "")
    if not n_pos:
        return cov, "–"
    left = pos.get("far left", 0) + pos.get("left", 0)
    right = pos.get("far right", 0) + pos.get("right", 0)
    L, C = round(100 * left / n_pos), round(100 * pos.get("centre", 0) / n_pos)
    R = 100 - L - C
    extra = []
    if pos.get("far left"):
        extra.append(f"far left {round(100 * pos['far left'] / n_pos)}")
    if pos.get("far right"):
        extra.append(f"far right {round(100 * pos['far right'] / n_pos)}")
    return cov, f"{L} L / {C} C / {R} R" + (f" <span class='small'>({', '.join(extra)})</span>" if extra else "")


def stance_rows(aff: Counter, aff_src: Counter, tot: float):
    """[(name, cell)] for the recorded stances (see affiliation.STANCES) present among citations."""
    from .affiliation import STANCES
    out = []
    for name, labs, opp in STANCES:
        a, b = sum(aff.get(l, 0) for l in labs), sum(aff.get(l, 0) for l in opp)
        sa, sb = sum(aff_src.get(l, 0) for l in labs), sum(aff_src.get(l, 0) for l in opp)
        if not (a or b) or not tot:
            out.append((name, None))
            continue
        if opp:
            cell = f"{p0(a / tot)} / {p0(b / tot)} <span class='small'>(sources: {sa} / {sb})</span>"
        else:
            cell = f"{p0(a / tot)} <span class='small'>({sa} source{'s' if sa != 1 else ''})</span>"
        out.append((name, cell))
    return out


def _src_profile(pairs, ctx):
    from collections import Counter
    tot = sum(n for _, n in pairs)
    known = [(k, n) for k, n in pairs if k in ctx.outlets]
    c = {"tot": tot, "distinct": len(pairs), "kt": sum(n for _, n in known), "rating": Counter(),
         "kinds": Counter(), "aff": Counter(), "acad1": 0, "acad_n": 0, "q": [], "a": [],
         "pos": Counter(), "n_pos": 0, "pos_src": 0, "aff_src": Counter()}
    from .affiliation import position_split
    for k, n in known:
        o = ctx.outlets[k]
        wr = o.get("wikipedia_rating")
        c["rating"][wr["status"] if wr else None] += n
        c["kinds"][o.get("kind")] += n
        lv = (o.get("academic_level") or {}).get("level")
        if lv is not None:
            c["acad_n"] += n
            c["acad1"] += n if lv >= 1 else 0
        if o.get("independent_quality"):
            c["q"] += [o["independent_quality"]["score"]] * n
        if o.get("audience_leaning"):
            c["a"] += [o["audience_leaning"]["score"]] * n
        for lab in (o.get("affiliation") or {}).get("labels") or []:
            c["aff"][lab] += n
            c["aff_src"][lab] += 1
        ps = position_split((o.get("affiliation") or {}).get("labels"), o.get("country"))
        if ps:
            c["n_pos"] += n
            c["pos_src"] += 1
            for side, f in ps.items():
                c["pos"][side] += n * f
    return c


def _src_table(heads, cols):
    h = [f"<div class='scroll'><table><tr><th>Measure</th>"
         + "".join(f"<th class='n'>{x}</th>" for x in heads) + "</tr>"]
    for lbl, cells in _src_rows(cols):
        h.append(f"<tr><td>{lbl}</td>" + "".join(f"<td class='n'>{c}</td>" for c in cells) + "</tr>")
    h.append("</table></div>")
    return "".join(h)


def _src_rows(cols):
    """[(measure label, [cell per column])] for source profiles (_src_profile), the same rows for
    every column."""
    from collections import Counter
    from .affiliation import NONE, NO_ENTRY, show

    def pc(n, d):
        return p0(n / d) if d else "–"
    sub = "<span class='small'>share of those citations</span>"
    rows = [("Citations", [num(c["tot"]) for c in cols]),
            ("Different sources", [num(c["distinct"]) for c in cols]),
            ("Citations to sources we have records for", [pc(c["kt"], c["tot"]) for c in cols])]
    for key in ["gr", "nc", "m", "gu", "d", "b"]:
        if any(c["rating"].get(key) for c in cols):
            rows.append((f"Wikipedia's rating: {RATING_NAMES[key]} {sub}",
                         [pc(c["rating"].get(key, 0), c["kt"]) for c in cols]))
    rows.append((f"Not on Wikipedia's list {sub}", [pc(c["rating"].get(None, 0), c["kt"]) for c in cols]))
    kind_tot = Counter()
    for c in cols:
        kind_tot.update({k: n for k, n in c["kinds"].items() if k})
    for k, _ in kind_tot.most_common(4):
        rows.append((f"Kind: {escape(k)} {sub}", [pc(c["kinds"].get(k, 0), c["kt"]) for c in cols]))
    rows.append(("Academic level 1 to 3 <span class='small'>share of citations to graded publishers "
                 "and journals</span>", [pc(c["acad1"], c["acad_n"]) for c in cols]))
    def cover(k, c, what):
        share = (len(c[k]) / c["tot"] if c["tot"] else 0) if isinstance(k, str) else k
        return (f"<div class='cov' title='{p0(share)} of citations {what}'><i style='width:{share * 100:.1f}%'>"
                f"</i></div><div class='mnote'>covers {p0(share)} of citations</div>")

    def quality(c):
        if not c["q"]:
            return "<span class='mnote'>no cited website has a score</span>"
        m = median(c["q"])
        return (f"<div class='mini'><span class='v'>{m:.2f}</span><div class='trk' title='middle score {m:.2f} "
                f"on a scale from 0 to 1'><span class='dot' style='left:{m * 100:.1f}%'></span></div>"
                f"<div class='ends'><span>0 lowest</span><span>1 highest</span></div>"
                + cover("q", c, "have a quality score") + "</div>")
    rows.append(("Quality score <span class='small'>of cited news websites, 0 to 1 (middle score); "
                 "grey bar: share of citations with a score</span>", [quality(c) for c in cols]))

    def people(c):
        if not c["a"]:
            return "<span class='mnote'>no cited website has this measure</span>"
        r = round((1 + median(c["a"])) / 2 * 100)
        return (f"<div class='mini'><span class='v'>{100 - r} D / {r} R</span><div class='split' "
                f"title='out of every 100 people sharing the middle website: {100 - r} Democrats, {r} "
                f"Republicans'><i style='flex:{100 - r}'></i><i style='flex:{r}'></i></div>"
                + cover("a", c, "have this measure") + "</div>")
    rows.append(("Who shares the cited websites <span class='small'>out of 100 people sharing the "
                 "middle website: Democrats / Republicans; grey bar: share of citations with this "
                 "measure</span>", [people(c) for c in cols]))
    rows.append((f"Recorded political affiliation: any {sub}",
                 [pc(sum(n for l, n in c["aff"].items() if l not in (NONE, NO_ENTRY)), c["kt"]) for c in cols]))
    aff_tot = Counter()
    for c in cols:
        aff_tot.update({l: n for l, n in c["aff"].items() if l not in (NONE, NO_ENTRY)})
    for lab, _ in aff_tot.most_common(4):
        rows.append((f"&nbsp;&nbsp;{label_chip(lab, None)} {sub}", [pc(c["aff"].get(lab, 0), c["kt"]) for c in cols]))
    sr = [stance_rows(c["aff"], c["aff_src"], c["kt"]) for c in cols]
    for i, (name, _) in enumerate(sr[0]):
        if any(x[i][1] for x in sr):
            rows.append((f"Recorded as {escape(name)} {sub}", [x[i][1] or "0%" for x in sr]))
    def lcr(c):
        if not c["n_pos"] or not c["kt"]:
            return "<span class='mnote'>no cited source has a recorded left–right position</span>"
        n, p = c["n_pos"], c["pos"]
        L = round(100 * (p.get("far left", 0) + p.get("left", 0)) / n)
        C = round(100 * p.get("centre", 0) / n)
        R = 100 - L - C
        src = c["pos_src"]
        return (f"<div class='mini'><span class='v'>{L} L / {C} C / {R} R</span><div class='split lcr' "
                f"title='out of every 100 of these citations: {L} left, {C} centre, {R} right'>"
                + "".join(f"<i class='{k}' style='flex:{v}'></i>" for k, v in (("l", L), ("c", C), ("r", R)) if v)
                + "</div>" + cover(n / c["tot"], c, "")
                + f"<div class='mnote'>{src} source{'s' if src != 1 else ''}</div></div>")
    rows.append(("Recorded left–right position <span class='small'>out of 100 citations to sources "
                 "with one: left / centre / right; grey bar: share of citations to sources with one</span>",
                 [lcr(c) for c in cols]))
    return rows


def then_now_sources(rec, ctx, vs) -> str:
    """The sources cited at each date, with today's ratings; and the sources dropped, kept and
    added between the earliest date and the analysed version."""
    from .sources import NOT_A_SOURCE
    if not ctx.outlets or not all("sources" in v for v in vs):
        return ""
    heads = ["Analysed version" if v.get("analysed") else "1 Jan " + v["date"][:4] for v in vs]
    h = ["<h3>The sources cited then and now</h3>",
         "<p class='small'>The footnotes of each version, read the same way as today's. The ratings are "
         "today's: what Wikipedia's list, researchers and Wikidata say about each source now, applied "
         "to the sources cited at each date. Past ratings are not on record, so a change here comes "
         "from different sources being cited, not from a source being rated differently. Old web "
         "addresses we have no record for are left out of the shares; the third row says how many "
         f"citations that covers. {link('../how-it-works.html#numbers', 'What each rating means')}.</p>",
         _src_table(heads, [_src_profile(v["sources"], ctx) for v in vs])]
    then = {k: n for k, n in vs[0]["sources"] if k not in NOT_A_SOURCE}
    now = {k: n for k, n in vs[-1]["sources"] if k not in NOT_A_SOURCE}
    dropped = sorted(((k, n) for k, n in then.items() if k not in now), key=lambda x: (-x[1], x[0]))
    added = sorted(((k, n) for k, n in now.items() if k not in then), key=lambda x: (-x[1], x[0]))
    kept = sorted(((k, n) for k, n in now.items() if k in then), key=lambda x: (-x[1], x[0]))
    y = vs[0]["date"][:4]
    h.append(f"<h3>Sources dropped and added since {escape(y)}</h3>"
             f"<p class='small'><b>Dropped</b>: cited on 1 January {escape(y)}, not cited in the analysed "
             f"version (counted by their citations then). <b>Kept</b>: cited in both. <b>Added</b>: cited "
             f"now, not on 1 January {escape(y)}. Kept and added are counted by their citations now. "
             "Footnotes whose source could not be identified are left out. A source counts as dropped "
             "even if the claim it supported is still there with a different source.</p>")
    h.append(_src_table([f"Dropped ({len(dropped)})", f"Kept ({len(kept)})", f"Added ({len(added)})"],
                        [_src_profile(x, ctx) for x in (dropped, kept, added)]))
    for name, lst in (("dropped", dropped), ("added", added)):
        if not lst:
            continue
        h.append(f"<details><summary>The {min(15, len(lst))} most-cited {name} sources</summary>"
                 "<div class='scroll'><table><tr><th>Source</th><th class='n'>Citations</th>"
                 "<th>Wikipedia's rating</th><th>Kind</th></tr>")
        for k, n in lst[:15]:
            o = ctx.outlets.get(k) or {}
            wr = o.get("wikipedia_rating")
            h.append(f"<tr><td>{source_label(k, ctx)}</td><td class='n'>{n}</td>"
                     f"<td class='small'>{escape(RATING_NAMES[wr['status']] if wr else ('not on the list' if o else 'no record'))}</td>"
                     f"<td class='small'>{escape(o.get('kind') or '–')}</td></tr>")
        h.append("</table></div></details>")
    return "".join(h)


def position_rules_html() -> str:
    """The placement rules for the left-right figure, with Wikipedia's words for each."""
    from .affiliation import position_rules, show
    d = position_rules()["file"]
    if not d.get("placed"):
        return ""
    h = ["<h2 id='positions'>How labels are placed from left to right</h2>",
         f"<p class='small'>{escape(d.get('rule', ''))} Checked {escape(d.get('checked', ''))}; each "
         "link opens the exact version of the Wikipedia article that was read.</p>",
         "<details><summary>Placed</summary><div class='scroll'><table><tr><th>Label</th>"
         "<th>Placed as</th><th>What Wikipedia says</th></tr>"]
    for r in d["placed"]:
        lbl = escape(show(r["label"])) + (f" <span class='small'>({escape(r['country'])})</span>" if r.get("country") else "")
        via = f" <span class='small'>(a form of “{escape(show(r['via']))}”)</span>" if r.get("via") else ""
        h.append(f"<tr><td>{lbl}</td><td>{escape(' / '.join(r['positions']))}{via}</td>"
                 f"<td class='small'>“{escape(r['quote'])}” {link(r['url'], r['article'])}</td></tr>")
    h.append("</table></div></details><details><summary>Not placed</summary><div class='scroll'><table>"
             "<tr><th>Label</th><th>Why not</th></tr>")
    for r in d.get("not_placed", []):
        lbl = escape(show(r["label"])) + (f" <span class='small'>({escape(r['country'])})</span>" if r.get("country") else "")
        h.append(f"<tr><td>{lbl}</td><td class='small'>{escape(r['why'])} {link(r['url'], r['article'])}</td></tr>")
    h.append("</table></div></details><p class='small'>“Liberal” in any country not listed is not "
             "placed. Labels not in either list are not placed.</p>")
    return "".join(h)


def then_now_sources_block(rec, ctx) -> str:
    """Under Sources cited: the whole article's sources on each date, and those dropped, kept and
    added since the earliest."""
    t = _then_now(ctx).get(rec["article"]) or {}
    vs = t.get("versions") or []
    if t.get("revision") != rec["revision"] or len(vs) < 2:
        return ""
    return "<span id='sources-then-now'></span>" + then_now_sources(rec, ctx, vs)


# ---------------------------------------------------------------- text kept in place
PROTECTION_NAMES = {"autoconfirmed": "accounts at least 4 days old with 10 edits",
                    "extendedconfirmed": "accounts at least 30 days old with 500 edits",
                    "sysop": "administrators only", "templateeditor": "template editors",
                    "unknown": "level not recorded (log entries before about 2008)"}
DISPUTE_TAGS = {"disputed inline", "disputed-inline", "dubious", "pov statement", "pov-statement",
                "pov-inline", "neutrality inline", "neutrality-inline", "contradict-inline",
                "disputed-section", "failed verification"}


def _talk(ctx):
    if not hasattr(ctx, "_talkd"):
        p = ROOT / "data" / "talk.json"
        ctx._talkd = json.loads(p.read_text(encoding="utf-8")).get("articles", {}) if p.exists() else {}
    return ctx._talkd


def _authors_db(ctx):
    if not hasattr(ctx, "_authd"):
        p = ROOT / "data" / "authors.json"
        ctx._authd = json.loads(p.read_text(encoding="utf-8")).get("authors", {}) if p.exists() else {}
    return ctx._authd


_LABD: dict = {}


def _labels_db(ctx=None):
    if "d" not in _LABD:
        p = ROOT / "data" / "labels.json"
        _LABD["d"] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _LABD["d"]


def label_chip(lab: str, ctx, where: str = "", display: str | None = None) -> str:
    """A recorded label; pointing at it (or tabbing to it) shows what English Wikipedia's article
    on it says, with the version read."""
    from .affiliation import show
    d = (_labels_db(ctx).get("definitions") or {}).get(lab)
    name = escape(display or show(lab))
    if not d:
        return f"<span class='lbl' tabindex='0'>{name}<span class='def' role='tooltip'>No Wikipedia " \
               f"article found for this label.{('<span class=src>' + escape(where) + '</span>') if where else ''}" \
               "</span></span>"
    sd = f" · {escape(d['short_description'])}" if d.get("short_description") else ""
    url = f"{WIKI}/w/index.php?oldid={d['revision']}" if d.get("revision") else f"{WIKI}/wiki/{quote(d['article'])}"
    return (f"<span class='lbl' tabindex='0'>{name}<span class='def' role='tooltip'><b>{escape(d['article'])}</b>{sd}"
            f"<br>{escape(d['first_sentence'])}<span class='src'>"
            + (f"Recorded as: {escape(where)}. " if where else "")
            + f"Definition: the opening of {link(url, 'Wikipedia’s article')}, as read.</span></span></span>")


TAG_HELP = {
    "rating": "Wikipedia's own reliability list (Perennial sources), as its editors rate the source.",
    "kind": "What kind of publisher or outlet Wikidata records the source as.",
    "academic": "Finland's Publication Forum (JUFO): panels of university researchers grade publishers "
                "and journals from 0 (below the scholarly bar) to 3 (top).",
    "quality": "Independent quality score of news websites (Lin and colleagues, 2023): expert ratings "
               "combined into one score from 0 (lowest) to 1 (highest).",
    "shares": "Who shares links to the website (DomainDemo, Yang and colleagues, 2025): out of every 100 "
              "people sharing it, how many are Democrats and how many Republicans.",
    "bias": "Bias labels from Media Bias/Fact Check and AllSides, as those raters give them.",
    "country": "Country Wikidata records for the source.",
    "owner": "Owner Wikidata records for the source.",
}


def _pill(text: str, help_: str, cls: str = "") -> str:
    return f"<span class='pill{(' ' + cls) if cls else ''}' title='{escape(help_, quote=True)}'>{text}</span>"


def source_tags(key: str, ctx, flags=()) -> str:
    """The tags the site shows for a source, as small labelled pills (point at one for what it
    means): kind, Wikipedia's rating, academic level, quality score, who shares it, bias labels,
    country, owner, recorded political labels (with Wikipedia's definitions), and this citation's
    own flags (no link, paywall, opinion ...)."""
    o = (ctx.outlets or {}).get(key) or {}
    out = []
    if o.get("kind"):
        out.append(_pill(escape(o["kind"]), TAG_HELP["kind"]))
    elif o.get("domain_class"):
        out.append(_pill(escape(o["domain_class"]) + " website", TAG_HELP["kind"]))
    wr = o.get("wikipedia_rating")
    if wr:
        out.append(_pill("Wikipedia: " + escape(RATING_NAMES.get(wr["status"], wr["status"])), TAG_HELP["rating"], "rate"))
    ac = o.get("academic_level")
    if ac and ac.get("level") is not None:
        out.append(_pill(f"academic level {ac['level']}", TAG_HELP["academic"]))
    iq = o.get("independent_quality")
    if iq:
        out.append(_pill(f"quality {iq['score']:.2f}", TAG_HELP["quality"]))
    dd = o.get("audience_leaning_dd")
    if dd and dd.get("score") is not None:
        r = round((1 + dd["score"]) / 2 * 100)
        out.append(_pill(f"shared by {100 - r} D / {r} R", TAG_HELP["shares"]))
    bias = []
    if o.get("mbfc") and o["mbfc"].get("bias"):
        bias.append("MBFC: " + o["mbfc"]["bias"])
    if o.get("allsides_2018"):
        bias.append("AllSides: " + o["allsides_2018"])
    if bias:
        out.append(_pill(escape(" · ".join(bias)), TAG_HELP["bias"]))
    if o.get("country"):
        out.append(_pill(escape(", ".join(o["country"][:2])), TAG_HELP["country"]))
    if o.get("owned_by"):
        out.append(_pill("owner: " + escape(", ".join(o["owned_by"][:2])), TAG_HELP["owner"]))
    for lab in (o.get("affiliation") or {}).get("labels") or []:
        if lab not in ("none recorded", "no entry"):
            out.append(label_chip(lab, ctx, "recorded for the source (Wikidata or its Wikipedia categories)"))
    for f in flags or ():
        if f in FLAG_NAMES:
            out.append(_pill(escape(FLAG_NAMES[f]), "A fact about this citation in the article's own text.", "cflag"))
    return "".join(out)


_VOICE: dict = {}


def _voice_of(rec):
    """This article's entry in data/voice.json, if it is for the analysed revision."""
    if "d" not in _VOICE:
        p = ROOT / "data" / "voice.json"
        _VOICE["d"] = json.loads(p.read_text(encoding="utf-8")).get("articles", {}) if p.exists() else {}
    v = _VOICE["d"].get(rec["article"])
    return v if v and v.get("revision") == rec["revision"] else None


def _seg_html(g) -> str:
    """One segment of a template column (wtl/framing.py) as HTML."""
    lead = escape(g["lead"])
    pre = f"<span class='fadd'>{escape(g['prefix'])}</span> " if g["prefix"] else ""
    if g.get("note") and g["prefix"]:
        pre = f"<span class='fadd' title='{escape(g['note'], quote=True)}'>{escape(g['prefix'])}</span> "
    body = escape(g["rest"])
    if g["kind"] == "back":
        return f" <span class='fback' title='{escape(g['note'], quote=True)}'>{lead}{pre}{body}</span>"
    return lead + pre + body


def _plain(html_: str) -> str:
    import html as _h
    return _h.unescape(re.sub(r"<[^>]+>", "", html_)).strip()


def _playable(old_text: str | None, new_html: str, label: str) -> tuple[str, str]:
    """(play button and diff data, paragraph attributes) for a cell animated from old_text to
    the text of new_html; empty when there is nothing to animate."""
    from . import glance as g
    from .then_now import diff_ops
    new = _plain(new_html)
    attrs = f" data-plain='{escape(new, quote=True)}' data-html='{escape(new_html, quote=True)}'"
    if not old_text or old_text == new:
        return "", attrs
    return (f"<button type='button' class='playb'>▶ Play the change from {escape(label)}</button>"
            f"<script type='application/json' class='ops'>{g.ops_json(diff_ops(old_text, new))}</script>"), attrs


def _framed_cols(rec, ctx, vs) -> list[dict]:
    """Columns 5 and 6 beside the dated first paragraphs: today's, with sources named and with
    removed sources kept, by the fixed templates of wtl/framing.py. [] when there is no check."""
    from . import framing
    v = _voice_of(rec)
    if not v:
        return []
    cols = framing.columns(vs[-1]["first_paragraph"], v, [x["first_paragraph"] for x in vs[:-1]],
                           lambda k: src_name(k, ctx) if k else "")
    if not cols:
        return []

    seg_html = _seg_html
    c5, c6 = cols
    n5 = sum(1 for g in c5 if g["prefix"])
    n6 = sum(1 for g in c6 if g["kind"] == "back")
    return [
        {"label": "Today, with sources named", "para": "".join(seg_html(g) for g in c5), "back_works": [],
         "hint": (f"Template: each sentence the check marks as contested and in Wikipedia's voice has its cited "
                  f"authors named in front, or its sources when no author is named ({n5} here; "
                  f"<span class='fadd'>names added</span>). Other sentences unchanged.")},
        {"label": "Today, with removed sources kept", "para": "".join(seg_html(g) for g in c6),
         "back_works": [w for g in c6 if g["kind"] == "back" for w in g.get("works", [])],
         "hint": (f"Template: as the column before, plus the sentences that works since taken out of the opening "
                  f"backed (<span class='fback'>put back</span>, {n6} here; point at one for its work), each "
                  f"framed by who wrote them.")},
    ]


def voice_section(rec, ctx) -> str:
    """Wikipedia's voice in the opening: the check of data/voice.json (wtl/voice.py), five columns."""
    from types import SimpleNamespace
    from . import voicepage, whosays
    v = _voice_of(rec)
    if not v:
        return ""
    if not getattr(ctx, "_display_loaded", False):
        from .affiliation import load_display
        load_display(ctx.outlets)
        ctx._display_loaded = True
    args = (_authors_db(ctx), _labels_db(), {}, {}, lambda l, w, d: label_chip(l, None, w, d),
            lambda k, f: source_tags(k, ctx, f) if k else "", lambda k: src_name(k, ctx))

    def row_html(w, sentence, removed):
        return ("<ul style='list-style:none;margin:0;padding:0'>"
                + whosays._row(w, sentence, *args, removed=removed) + "</ul>")
    dates = ", ".join(d[:4] for d in v.get("removed_dates", []))
    intro = ("<h2>Wikipedia's voice in the opening</h2>"
             "<p>Each sentence of the opening section checked against Wikipedia's neutrality policy. A sentence "
             "is marked (orange edge) when there is evidence it is contested (editors took it out for a day "
             "or more and put it back, tagged it as disputed, or argued over it on the talk page; or it uses a "
             "word from Wikipedia's own “Words to watch” guideline) and it is stated in Wikipedia's voice, naming "
             "no one who holds the view. That marks sentences to check against the rule, not a finding that a "
             "sentence breaks it. “With attribution” names the cited authors in front of the sentence by a "
             "fixed template; the last column shows the earlier wording of the same sentence as Wikipedia printed "
             f"it on 1 January of {dates}, with the works it cited then that are gone now. Nothing here is "
             "written by this project, and it proposes no edit to Wikipedia "
             f"({link('../how-it-works.html#voice', 'how')}).</p>")
    from .layout import std_popup
    return intro + whosays.CSS + voicepage.page(v, v["works"], v["removed"], row_html, [],
                                                std_html=std_popup("opening"))


def _days(a: str, b: str) -> int:
    import datetime as _dt
    try:
        return (_dt.date.fromisoformat(b[:10]) - _dt.date.fromisoformat(a[:10])).days
    except ValueError:
        return 0


def _add_months(d: str, n: int) -> str:
    import datetime as _dt
    y, m, day = int(d[:4]), int(d[5:7]), int(d[8:10])
    m0 = m - 1 + n
    y, m = y + m0 // 12, m0 % 12 + 1
    import calendar
    return _dt.date(y, m, min(day, calendar.monthrange(y, m)[1])).isoformat()


def ban_windows(t: dict) -> list[dict]:
    """Discussion bans on record: a discussion about a moratorium whose closing states an end date
    or a length; the ban runs from the closing date to that end. Discussions about a ban that state
    neither (for example a request to lift one) are not counted as bans."""
    out = []
    for d in (t or {}).get("discussions", []):
        if not d.get("moratorium_discussed") or not d.get("closed_on"):
            continue
        end = d.get("ban_until") or (_add_months(d["closed_on"], d["ban_months"]) if d.get("ban_months") else None)
        if not end:
            continue        # no end date or length stated: a discussion about a ban, not one set
        out.append({"from": d["closed_on"], "to": end, "sentences": d.get("quotes_sentences", []),
                    "url": d["url"], "heading": d["heading"]})
    return out


def sentence_locks(s: dict, rec: dict, ctx) -> dict:
    """What, on record, kept this sentence in place while it stood (see the How it works page)."""
    t = _talk(ctx).get(rec["article"]) or {}
    if t.get("revision") != rec["revision"]:
        t = {}
    end = rec["revision_timestamp"][:10]
    since = (s.get("history") or {}).get("in_place_since") or end
    quoting = [d for d in t.get("discussions", []) if s["id"] in d.get("quotes_sentences", [])]
    first = (s.get("history") or {}).get("first_added") or since
    bans = [b for b in ban_windows(t) if s["id"] in b["sentences"]     # any time since first added
            and (b["to"] or end) >= first and b["from"] <= end]
    act, _ = _activity(ctx)
    e = act.get(rec["article"]) or {}
    prot = {}
    for p_ in ((e.get("protection") or {}).get("periods") or []) if e.get("revision") == rec["revision"] else []:
        a, b = max(p_["from"], since), min(p_["to"], end)
        if b > a:
            prot[p_["level"]] = prot.get(p_["level"], 0) + _days(a, b)
    return {"notes": s.get("hidden_notes") or [],
            "tags": [x for x in (s.get("tags") or []) if x["template"] in DISPUTE_TAGS],
            "rfcs": [d for d in quoting if d.get("rfc")],
            "edit_requests": [d for d in quoting if d.get("edit_request")],
            "declined_under_ban": [d for d in quoting if d.get("edit_request") and d.get("moratorium_in_closing")],
            "bans": bans, "protection_days": prot, "days_in_place": _days(since, end)}


def lock_badges(lk: dict) -> str:
    bits = []
    if lk["bans"]:
        b = lk["bans"][-1]
        bits.append(f"<span class='tag'>discussion ban</span> {escape(b['from'])} to {escape(b['to'] or 'no end on record')}")
    if lk["declined_under_ban"]:
        bits.append(f"{len(lk['declined_under_ban'])} edit request{'s' if len(lk['declined_under_ban']) != 1 else ''} "
                    "closed with the ban mentioned")
    if lk["notes"]:
        bits.append("<span class='tag'>hidden note</span> asks editors to discuss first")
    if lk["rfcs"]:
        bits.append(f"{len(lk['rfcs'])} request{'s' if len(lk['rfcs']) != 1 else ''} for comment quote it")
    if lk["tags"]:
        bits.append("<span class='tag'>marked disputed</span>")
    tight = {k: v for k, v in lk["protection_days"].items() if k in ("extendedconfirmed", "sysop")}
    if tight and lk["days_in_place"]:
        d = sum(tight.values())
        bits.append(f"page protected for {p0(min(1, d / lk['days_in_place']))} of the time since then")
    return "<br>".join(bits) or "–"


def persistence_html(rec, ctx) -> str:
    rows = [x for x in rec["authorship"].get("persistence") or [] if x.get("baseline")]
    if not rows:
        return ""
    h = ["<h3>How much older text is still there</h3>",
         "<p>Take the article as it stood 1, 2, 3 and 5 years before this version, and count how "
         "many of its words are still in it today. The same distances are used for every article, "
         "so no date is picked for any one subject. This count includes the words inside footnotes, "
         "so it is a little different from the word counts elsewhere on this page.</p><div class='fig'>"]
    for x in rows:
        h.append(fig(p0(x["share_still_present"]),
                     f"of the text from {x['years']} year{'s' if x['years'] != 1 else ''} ago is still there"))
    h.append("</div><div class='scroll'><table><tr><th>Version</th><th class='n'>Words then</th>"
             "<th class='n'>Still there</th><th class='n'>Share still there</th>"
             "<th class='n'>Share of today's text</th></tr>")
    for x in rows:
        h.append(f"<tr><td>{x['years']} year{'s' if x['years'] != 1 else ''} earlier: "
                 f"{link(f'{WIKI}/w/index.php?oldid={x['baseline']}', x['baseline_timestamp'][:10])}</td>"
                 f"<td class='n'>{num(x['words_then'])}</td><td class='n'>{num(x['still_present'])}</td>"
                 f"<td class='n'>{p1(x['share_still_present'])}</td><td class='n'>{p1(x['share_of_current'])}</td></tr>")
    h.append("</table></div><p class='small'>“Share of today's text” is how much of today's article "
             "was already there at that time. A word taken out and later put back counts as still there.</p>")
    return "".join(h)


def contested_section(rec, ctx) -> str:
    sh = (rec.get("changes") or {}).get("sentence_history")
    if not sh:
        return ""
    sents = [s for s in rec["sentences"] if s.get("history")]
    top = sorted((s for s in sents if s["history"]["removed"] >= 2),
                 key=lambda s: (-s["history"]["removed"], s["id"]))
    h = ["<h2>Sentences taken out and put back</h2>",
         "<p>Some sentences have been removed and restored again and again. Here a sentence counts as "
         "<b>taken out</b> when one edit removed at least half of its words at once, and <b>put back</b> "
         "when a later edit restored them. Edits that wiped most of the page at once, which is almost "
         "always vandalism, are not counted. This does not say who was right, or why the sentence was "
         "removed.</p><div class='fig'>",
         fig(num(sh["sentences_removed_and_restored_twice_or_more"]),
             f"of {num(sh['sentences'])} sentences were taken out and put back at least twice"),
         fig(p1(sh["share_of_words"]), "of the article's words are in those sentences"),
         fig(num(sh["in_opening_section"]), "of them are in the opening section"),
         fig(num(sh["sentences_removed_by_two_or_more_accounts"]),
             "sentences were taken out by two or more different accounts"),
         "</div>"]
    if sh.get("median_days_in_place_since_last_restored") is not None and top:
        h.append(f"<p class='small'>In a typical one of those sentences (the median), "
                 f"{num(sh['median_days_in_place_since_last_restored'])} days have passed since it was last put back.</p>")
    if top:
        h.append("<h3>The sentences taken out most often</h3>"
                 "<p class='small'><b>Taken out</b>: how many times, and how many of those it was back "
                 "within a day. <b>Accounts</b>: how many different accounts took it out, and how many put "
                 "it back (names are not shown). <b>In place since</b>: when it was last put back, or first "
                 "added if it was never taken out. <b>Kept in place by</b>: rules on record that stopped it "
                 "being changed while it stood (see below).</p>"
                 "<div class='scroll'><table><tr><th>Sentence</th><th class='n'>Taken out</th>"
                 "<th class='n'>Accounts</th><th>In place since</th><th>Kept in place by</th><th>Latest removal</th></tr>")
        for s in top[:15]:
            x = s["history"]
            last = x["removals"][-1] if x["removals"] else None
            lk = sentence_locks(s, rec, ctx)
            h.append(f"<tr><td>{escape(s['text'])}{' <span class=\'tag\'>opening</span>' if s['id'].startswith('lead') else ''}</td>"
                     f"<td class='n'>{x['removed']}<div class='small'>{x['back_within_24h']} within a day</div></td>"
                     f"<td class='n'>{x['removing_accounts']} / {x['restoring_accounts']}</td>"
                     f"<td class='small'>{escape(x['in_place_since'] or '–')}</td>"
                     f"<td class='small'>{lock_badges(lk)}</td>"
                     f"<td class='small'>{link(f'{WIKI}/w/index.php?diff=prev&oldid={last[0]}', x['latest_removal'] or 'view') if last else '–'}</td></tr>")
        h.append("</table></div>")
        if len(top) > 15:
            h.append(f"<p class='small'>{num(len(top) - 15)} more are in the "
                     f"{link(f'../data/{slug(rec['article'])}.json', 'full data')} (each sentence's “history”).</p>")
    return "".join(h)


def kept_section(rec, ctx) -> str:
    """Rules on record that kept text from being changed: discussion bans, requests for comment,
    edit requests, hidden notes, dispute tags, page protection."""
    t = _talk(ctx).get(rec["article"]) or {}
    if t.get("revision") != rec["revision"]:
        t = {}
    act, _ = _activity(ctx)
    e = act.get(rec["article"]) or {}
    periods = ((e.get("protection") or {}).get("periods") or []) if e.get("revision") == rec["revision"] else []
    sid = {s["id"]: s for s in rec["sentences"]}
    notes = [s for s in rec["sentences"] if s.get("hidden_notes")]
    tags = [s for s in rec["sentences"] if any(x["template"] in DISPUTE_TAGS for x in s.get("tags") or [])]
    bans = ban_windows(t)
    disc = t.get("discussions", [])
    if not (t or notes or tags or periods):
        return ""
    h = ["<h2>Rules that kept text in place</h2>",
         "<p>Wikipedia has several ways to stop text being changed for a while. Some come from "
         "agreement among editors, some from administrators. This lists those on record for this "
         "article. It does not say whether a decision was right.</p>"]
    c = t.get("counts") or {}
    if t:
        h.append("<div class='fig'>"
                 + fig(num(len(bans)), "discussion bans on record")
                 + fig(num(c.get("rfcs", 0)), "requests for comment on the talk page")
                 + fig(num(c.get("edit_requests_quoting_text", 0)), "edit requests that quote today's text")
                 + fig(num(len(notes)), "sentences with a hidden “discuss first” note")
                 + "</div>")
    if bans:
        h.append("<h3>Discussion bans</h3><p class='small'>A discussion ban (Wikipedia calls it a "
                 "moratorium) means editors agreed not to propose changing a passage again for a set "
                 "time. Dates are from the closing of the discussion that set it; only bans whose closing "
                 "states an end date or a length are listed.</p>"
                 "<div class='scroll'><table><tr><th>Discussion</th><th>From</th><th>Until</th>"
                 "<th>Sentences of today's text it quotes</th></tr>")
        for b in bans:
            qs = [sid[x] for x in b["sentences"] if x in sid]
            qtxt = "<br>".join(escape(q["text"][:160]) + ("…" if len(q["text"]) > 160 else "") for q in qs[:3]) or "–"
            h.append(f"<tr><td>{link(b['url'], b['heading'])}</td><td>{escape(b['from'])}</td>"
                     f"<td>{escape(b['to'])}</td><td class='small'>{qtxt}</td></tr>")
        h.append("</table></div>")
        under = [d for d in disc if d.get("edit_request") and d.get("moratorium_in_closing")]
        if under:
            h.append(f"<p class='small'>{num(len(under))} edit request{'s were' if len(under) != 1 else ' was'} "
                     "closed with a discussion ban mentioned in the closing note.</p>")
    rf = [d for d in disc if d.get("rfc")]
    if rf:
        h.append("<h3>Requests for comment</h3><p class='small'>A request for comment invites editors "
                 "from across Wikipedia to settle a question. Once closed, its outcome is usually changed "
                 "only by a new discussion. <b>Quotes</b>: sentences of today's text it quotes eight or more "
                 "words of.</p><details><summary>"
                 f"{num(len(rf))} on record</summary><div class='scroll'><table><tr><th>Discussion</th>"
                 "<th>Started</th><th>Closed</th><th class='n'>Quotes</th></tr>")
        for d in rf:
            h.append(f"<tr><td>{link(d['url'], d['heading'])}</td><td>{escape(d['started'] or '–')}</td>"
                     f"<td>{escape(d['closed_on'] or ('closed' if d['closed'] else 'not closed'))}</td>"
                     f"<td class='n'>{len(d['quotes_sentences'])}</td></tr>")
        h.append("</table></div></details>")
    if notes:
        h.append("<h3>Hidden notes asking editors to discuss first</h3><p class='small'>Notes in the "
                 "page's source that readers do not see, placed just before the sentence.</p>"
                 "<div class='scroll'><table><tr><th>Sentence</th><th>Hidden note</th></tr>")
        for s in notes:
            h.append(f"<tr><td>{escape(s['text'])}</td><td class='small'>{escape(' / '.join(s['hidden_notes']))}</td></tr>")
        h.append("</table></div>")
    if tags:
        h.append("<h3>Sentences marked as disputed</h3><p class='small'>Tags such as “disputed” or "
                 "“dubious” that editors put after a sentence, with the discussion they point to.</p>"
                 "<div class='scroll'><table><tr><th>Sentence</th><th>Tag</th><th>Discussion</th></tr>")
        for s in tags:
            for x in s["tags"]:
                if x["template"] not in DISPUTE_TAGS:
                    continue
                talk_l = (link(WIKI + "/wiki/" + x["talk"].replace(" ", "_"), "talk page") if x.get("talk") else "–")
                h.append(f"<tr><td>{escape(s['text'])}</td><td class='small'>{escape(x['template'])}"
                         f"{' (' + escape(x['date']) + ')' if x.get('date') else ''}</td><td class='small'>{talk_l}</td></tr>")
        h.append("</table></div>")
    if periods:
        h.append("<h3>When editing was limited</h3><p class='small'>Administrators can protect a page "
                 "so that only some accounts can edit it. Periods from Wikipedia's protection log, up to "
                 "this version.</p><div class='scroll'><table><tr><th>From</th><th>To</th>"
                 "<th>Who could edit</th><th class='n'>Days</th></tr>")
        for p_ in periods:
            h.append(f"<tr><td>{escape(p_['from'])}</td><td>{escape(p_['to'])}</td>"
                     f"<td class='small'>{escape(PROTECTION_NAMES.get(p_['level'], p_['level']))}</td>"
                     f"<td class='n'>{num(_days(p_['from'], p_['to']))}</td></tr>")
        h.append("</table></div>")
    if t:
        h.append(f"<p class='small'>Read from {num(c.get('talk_pages', 0))} talk page"
                 f"{'s' if c.get('talk_pages', 0) != 1 else ''} (the talk page and its archives) as they "
                 "stood on the date of this version. Who took part in each discussion is not recorded "
                 f"here. {link('../data/talk.json', 'All articles, as JSON')}.</p>")
    return "".join(h)


def citations_detail(rec, ctx) -> str:
    s = rec.get("sources") or {}
    h = []
    b = s.get("bundles")
    if b and b.get("sentences_with_footnotes"):
        bw = b["sentences_by_works_cited"]
        h.append("<h3>How many works back each sentence</h3><p class='small'>A footnote can hold "
                 "several works. For each sentence with footnotes after it: how many works they hold "
                 "together.</p><div class='scroll'><table><tr><th>Works cited after the sentence</th>"
                 "<th class='n'>Sentences</th></tr>"
                 + "".join(f"<tr><td>{escape(k)}</td><td class='n'>{num(v)}</td></tr>" for k, v in bw.items())
                 + "</table></div>")
        if b.get("largest"):
            sid = {x["id"]: x for x in rec["sentences"]}
            h.append("<p class='small'>The sentences with the most works cited (five or more):</p>"
                     "<div class='scroll'><table><tr><th>Sentence</th><th class='n'>Footnotes</th>"
                     "<th class='n'>Works</th></tr>")
            for x in b["largest"]:
                st = sid.get(x["sentence"])
                if not st:
                    continue
                op = " <span class='tag'>opening</span>" if st["id"].startswith("lead") else ""
                h.append(f"<tr><td>{escape(st['text'])}{op}</td><td class='n'>{x['footnotes']}</td>"
                         f"<td class='n'>{x['works']}</td></tr>")
            h.append("</table></div>")
    au = s.get("authors") or []
    if au:
        db = _authors_db(ctx)
        h.append("<h3>Most-cited authors</h3><p class='small'>Authors named in the citations, by how "
                 "many citations name them. A short footnote such as “Morris 2004” counts for the author "
                 f"of the book it points to. {num(s.get('citations_naming_an_author', 0))} of "
                 f"{num(s['citations'])} citations name an author. <b>Recorded on Wikidata</b>: only for "
                 "authors the citation itself links to a Wikipedia article, so no name is matched to a "
                 "person by guesswork. † means the Wikidata statement gives no source.</p>"
                 "<div class='scroll'><table><tr><th>Author</th><th class='n'>Citations</th>"
                 "<th class='n'>Works</th><th>Recorded labels <span class='small'>(point at one for "
                 "Wikipedia's definition)</span></th><th>Recorded on Wikidata</th></tr>")
        for a in au[:15]:
            nm = escape(a["name"])
            if a.get("wikipedia"):
                nm = link(WIKI + "/wiki/" + a["wikipedia"].replace(" ", "_"), a["name"])
            h.append(f"<tr><td>{nm}</td><td class='n'>{a['citations']}</td><td class='n'>{a['works']}</td>"
                     f"<td>{' '.join(label_chip(x['label'], ctx, x['from'], x.get('display')) for x in (_labels_db(ctx).get('authors') or {}).get(a.get('wikipedia') or '', [])) or '<span class=small>–</span>'}</td>"
                     f"<td class='small'>{author_facts(db.get(a.get('wikipedia') or ''))}</td></tr>")
        h.append("</table></div>")
    return "".join(h)


AUTHOR_FACT_ROWS = [("occupation", "Occupation"), ("field_of_work", "Field"),
                    ("employer", "Employer (no end date given)"), ("former_employer", "Former employer"),
                    ("affiliation", "Affiliation"), ("political_party", "Party membership"),
                    ("former_political_party", "Former party membership"),
                    ("position_held", "Position held"), ("former_position_held", "Former position"),
                    ("member_of", "Member of"), ("political_ideology", "Political ideology")]


def author_facts(e) -> str:
    if not e:
        return "–"
    if not e.get("wikidata"):
        return "no Wikidata item"
    bits = []
    for k, lbl in AUTHOR_FACT_ROWS:
        vals = e.get(k) or []
        if vals:
            bits.append(f"{lbl}: " + ", ".join(escape(v["label"]) + ("" if v["sourced"] else "†") for v in vals[:6])
                        + (f" and {len(vals) - 6} more" if len(vals) > 6 else ""))
    q = e["wikidata"]
    return ("<br>".join(bits) or "nothing recorded") + f" <a href='https://www.wikidata.org/wiki/{escape(q)}'>Wikidata</a>"


def changes_section(rec, ctx):
    c = rec.get("changes")
    if not c or not c.get("editors"):
        return ""
    h = ["<h2>Text removed</h2>",
         f"<p>Over the article's history up to this version, <b>{num(c['words_removed'])}</b> "
         f"words were removed by {num(c['editors_removing'])} editors; "
         f"{num(c['words_removed_later_restored'])} of them "
         f"({p0(c['words_removed_later_restored'] / c['words_removed']) if c['words_removed'] else '0%'}) "
         f"were later put back. {num(c['source_links_removed'])} web links to sources were removed "
         "with that text. Each removal is credited to the editor of the revision that made it.</p>",
         "<div class='scroll'><table><tr><th>Editor</th><th class='n'>Words removed</th>"
         "<th class='n'>Of them, others' words</th><th class='n'>Later put back</th>"
         "<th class='n'>Edits that removed text</th><th>Sources whose links they removed</th>"
         "<th>Largest removals</th></tr>"]
    for e in c["editors"][:25]:
        if not e["words_removed"]:
            continue
        srcs = ", ".join(f"{escape(src_name(k, ctx))} ({n})" for k, n in list(e["sources_removed"].items())[:4])
        more = len(e["sources_removed"]) - 4
        ev = " ".join(f"<a href='{escape(u)}'>diff</a>" for u in e["evidence"][:3])
        h.append(f"<tr><td>{escape(e['label'])}</td><td class='n'>{num(e['words_removed'])}</td>"
                 f"<td class='n'>{num(e['others_words_removed'])}</td>"
                 f"<td class='n'>{num(e['words_removed_later_restored'])}</td>"
                 f"<td class='n'>{num(e['removing_revisions'])}</td>"
                 f"<td class='small'>{srcs or '–'}{f' and {more} more' if more > 0 else ''}</td>"
                 f"<td class='small'>{ev}</td></tr>")
    h.append("</table></div><p class='small'>The 25 editors who removed the most words. Text "
             "that WikiWho cannot follow when it is moved counts as removed and re-added; it "
             "follows most moves within an article.</p>")

    # wording
    lt = c.get("listed_terms") or {}
    groups = sorted(set(lt.get("inserted", {})) | set(lt.get("removed", {})))
    if groups:
        L = c.get("lists") or {}
        wtw = (L.get("words_to_watch") or {}).get("url", "")
        h.append("<h2>Words to watch and contested terms</h2>"
                 f"<p>Terms from two lists, counted when an editor added them (in today's text or "
                 f"in text later removed) and when an editor removed them. "
                 f"<b>WTW</b> is Wikipedia's own guideline {link(wtw, 'Words to watch')} (labels, "
                 "expressions of doubt, puffery, editorializing and so on). <b>Contested</b> terms "
                 f"are groups of alternative words for the same thing, published in "
                 f"{link('../data/contested_terms.json', 'this list')}; every member of a group is "
                 "counted the same way. A count says a word was added or removed, not whether it "
                 "was right.</p><div class='scroll'><table><tr><th>List and group</th>"
                 "<th class='n'>Added</th><th class='n'>Removed</th></tr>")
        for g in groups:
            h.append(f"<tr><td>{escape(g)}</td><td class='n'>{num(lt.get('inserted', {}).get(g, 0))}</td>"
                     f"<td class='n'>{num(lt.get('removed', {}).get(g, 0))}</td></tr>")
        h.append("</table></div>")
        eds = [e for e in c["editors"] if e["terms_inserted"] or e["terms_removed"]]
        eds.sort(key=lambda e: (-(sum(sum(v.values()) for v in e["terms_inserted"].values())
                                  + sum(sum(v.values()) for v in e["terms_removed"].values())),
                                int(e["label"].split()[1])))

        def terms(d):
            flat = sorted(((t, n, g) for g, v in d.items() for t, n in v.items()), key=lambda x: (-x[1], x[0]))
            return ", ".join(f"{escape(t)} {n}" for t, n, _ in flat[:8]) + (
                f" and {len(flat) - 8} more" if len(flat) > 8 else "") if flat else "–"
        h.append("<h3>By editor</h3><div class='scroll'><table><tr><th>Editor</th>"
                 "<th>Listed terms they added</th><th>Listed terms they removed</th></tr>")
        for e in eds[:20]:
            h.append(f"<tr><td>{escape(e['label'])}</td><td class='small'>{terms(e['terms_inserted'])}</td>"
                     f"<td class='small'>{terms(e['terms_removed'])}</td></tr>")
        h.append("</table></div><p class='small'>The 20 editors with the most listed terms added "
                 "or removed; all of them are in the article's data file.</p>")
    return "".join(h)


def interests_section(rec):
    d = rec.get("declared_interests")
    if not d or not (d.get("article_tags") or d.get("notices")):
        return ""
    h = ["<h2>Declared conflicts of interest</h2><ul>"]
    for t in d.get("article_tags", []):
        h.append(f"<li>The article carries a maintenance notice: <b>{escape(t)}</b>.</li>")
    for n in d.get("notices", []):
        who = ", ".join(n["editors"]) or "no editor listed on this page"
        other = n["accounts_not_among_listed_editors"]
        h.append(f"<li>The talk page has a <b>{escape(n['notice'])}</b> notice naming {escape(who)}"
                 + (f" and {other} other account{'s' if other != 1 else ''}" if other else "") + ".</li>")
    h.append("</ul>")
    if d.get("evidence"):
        h.append(f"<p class='small'>{link(d['evidence'], 'The talk page as it stood')} when this "
                 "version was saved. These notices are Wikipedia's own records.</p>")
    return "".join(h)


def sources_section(rec, ctx):
    s = rec.get("sources")
    if not s:
        return ""
    h = ["<h2>Sources cited</h2>",
         f"<p>The article has <b>{num(s['citations'])}</b> citations to {num(s['distinct_sources'])} "
         f"different sources, {num(s['lead_citations'])} of them in the opening section. Each "
         "citation is credited to the editor who added it: the editor of the words of its web "
         "address or, without one, of its publication name. A short footnote such as “Morris "
         "2004, p. 12” counts as a citation of the book it points to.</p>"]
    if ctx.outlets:
        pf = profile([(x["source"], x["citations"]) for x in s["list"]], ctx)
        h.append("<h3>How the cited sources are rated</h3><p class='small'>Several raters side "
                 "by side; none of them is this project's. Shares are of the article's "
                 f"{num(s['citations'])} citations. {link('../sources.html', 'About the raters')}.</p>")
        h.append("<div class='scroll'><table><tr><th>Rater</th><th>Result</th></tr>")
        for name, sub, val in profile_rows(pf):
            h.append(f"<tr><td>{escape(name)}<div class='small'>{escape(sub)}</div></td>"
                     f"<td class='small'>{val}</td></tr>")
        h.append("</table></div>")
    h.append("<h3>Most-cited sources</h3><div class='scroll'><table><tr><th>Source</th>"
             "<th class='n'>Citations</th><th class='n'>In opening</th>"
             + (ASSESSOR_HEAD if ctx.outlets else "") + "<th>Added by</th></tr>")
    from .sources import NOT_A_SOURCE
    listed = [x for x in s["list"] if x["source"] not in NOT_A_SOURCE]
    for x in listed[:25]:
        by = ", ".join(f"{escape(k)} ({v})" for k, v in list(x["added_by"].items())[:3])
        more = len(x["added_by"]) - 3
        h.append(f"<tr><td>{source_label(x['source'], ctx)}</td><td class='n'>{x['citations']}</td>"
                 f"<td class='n'>{x['lead_citations']}</td>"
                 + (_assessor_cells(x["source"], ctx) if ctx.outlets else "")
                 + f"<td class='small'>{by}{f' and {more} more' if more > 0 else ''}</td></tr>")
    allc = {x["source"]: x["citations"] for x in s["list"]}
    if ctx.outlets:
        h.append(summary_rows(allc, ctx, 3, 4))
    h.append("</table></div>")
    h.append(_non_source_line(allc, s["citations"]))
    if len(listed) > 25:
        data = link(f"../data/{slug(rec['article'])}.json", "full data")
        h.append(f"<p class='small'>{len(listed) - 25} further sources are in the {data}.</p>")
    if ctx.outlets:
        h.append(MEANS_NOTE)
    h.append(citations_detail(rec, ctx))
    h.append(writers_section(rec, ctx))
    h.append(flags_html(s))
    h.append(links_section(rec, ctx))
    # who added the citations
    if ctx.outlets:
        from collections import defaultdict
        per = defaultdict(list)
        for x in s["list"]:
            for lbl, n in x["added_by"].items():
                per[lbl].append((x["source"], n))
        top = sorted(per, key=lambda l: (-sum(n for _, n in per[l]), _lbl_no(l)))[:10]
        h.append("<h3>Who added the citations</h3><p class='small'>The ten editors who added the "
                 "most citations still in the article, with how the sources they cited are rated "
                 "(shares of that editor's citations).</p><div class='scroll'><table><tr>"
                 "<th>Editor</th><th class='n'>Citations</th><th>Wikipedia's rating</th>"
                 "<th>Independent quality (median)</th><th>Audience leaning (median)</th>"
                 "<th>Most cited by them</th></tr>")
        for lbl in top:
            pf = profile(per[lbl], ctx)
            t = pf["total"]
            top_src = ", ".join(f"{escape(src_name(k, ctx))} ({n})" for k, n in
                                sorted(per[lbl], key=lambda x: (-x[1], x[0]))[:3])
            q = (f"{median(pf['quality']):.2f} ({p0(len(pf['quality']) / t)} scored)"
                 if pf["quality"] else "–")
            au = (f"{median(pf['audience']):+.2f} ({p0(len(pf['audience']) / t)} scored)"
                  if pf["audience"] else "–")
            h.append(f"<tr><td>{escape(lbl)}</td><td class='n'>{t}</td>"
                     f"<td class='small'>{_shares(pf['rating'], t, RATING_ORDER, RATING_NAMES)}</td>"
                     f"<td class='small'>{q}</td><td class='small'>{au}</td>"
                     f"<td class='small'>{top_src}</td></tr>")
        h.append("</table></div>")
        h.append("".join(note(x, "About the ratings") for x in SOURCE_NOTES[:1])
                 + "<ul class='small'>" + "".join(f"<li>{escape(x)}</li>" for x in SOURCE_NOTES[1:])
                 + "</ul>")
    return "".join(h)


def _lbl_no(label):
    try:
        return int(label.split()[-1])
    except ValueError:
        return 10 ** 9


def sources_page(ctx):
    from collections import Counter
    snap = ctx.outlets_snap or {}
    asr = snap.get("assessors", {})
    h = ["<h1>Sources and how they are rated</h1>",
         "<p class='lede'>Each article page lists the sources the article cites, who added each "
         "citation, and how several raters rate those sources. No rater is treated as the "
         "truth, and this project adds no rating of its own.</p>"]
    if not snap:
        h.append("<p>The ratings snapshot has not been built yet.</p>")
        return page(f"Sources · {NAME}", "".join(h), "sources.html")
    wr = asr.get("wikipedia_rating", {})
    h.append("<h2>The raters</h2><ul>")
    h.append(f"<li><b>Wikipedia's own rating.</b> The {link(wr.get('url', ''), 'Perennial sources list')}, "
             "where Wikipedia editors record their consensus on sources they discuss often: "
             "generally reliable, no consensus, generally unreliable, deprecated or blacklisted. "
             "About 530 entries. Some people argue that these ratings lean in one political "
             "direction, which is one reason the independent assessments are shown beside them. "
             f"Snapshot of {len(wr.get('revisions', {}))} list pages taken {escape(snap['built'])}.</li>")
    h.append("<li><b>Independent quality score.</b> " + escape(asr.get("independent_quality", {}).get("reference", ""))
             + " It combines six independent rating sets from fact-checkers, journalists and "
             "researchers into one score per news website, from 0 (lowest quality) to 1 (highest). "
             "Wikipedia is not one of the six. 11,520 websites.</li>")
    h.append("<li><b>Audience leaning.</b> " + escape(asr.get("audience_leaning", {}).get("reference", ""))
             + " For each website, whether its links were shared more by registered Democrats "
             "(towards −1) or Republicans (towards +1) among about 500,000 US voters on Twitter in "
             "2017. It describes who shared a site, not what the site publishes. 19,022 websites.</li>")
    h.append("<li><b>AllSides (2018).</b> " + escape(asr.get("allsides_2018", {}).get("reference", ""))
             + " Left, lean left, centre, lean right or right, for a few hundred outlets.</li>")
    L0 = {x["entry"]: x["status"] for x in snap.get("wikipedia_list_compared", [])}

    def rsp_note(*entries):
        got = [(e, L0[e]) for e in entries if e in L0]
        return (" Wikipedia's own list rates " + "; ".join(
            f"{escape(e)} as {escape(RATING_NAMES.get(st, st))}" for e, st in got) + ".") if got else ""
    h.append("<li><b>Media Bias/Fact Check (MBFC).</b> " + escape(asr.get("mbfc", {}).get("reference", ""))
             + " A political bias label (left to right, or least biased) and a factual-reporting "
             "label for about 4,400 news outlets, many outside the United States. MBFC is also "
             "one of the six rating sets in the independent quality score." + rsp_note("Media Bias/Fact Check")
             + "</li>")
    h.append("<li><b>Academic level.</b> " + escape(asr.get("academic_level", {}).get("reference", ""))
             + " Level 1 means the panels judge a publisher or journal to meet the basic criteria "
             "of academic publishing; 2 and 3 are the higher levels; 0 means it was assessed and "
             "does not meet them. The Danish register's level is shown where the record gives it. "
             "Only publishers and journals the register lists can have a level."
             + ("" if any(o.get("academic_level") for o in ctx.outlets.values())
                else " <i>Not yet retrieved in this snapshot.</i>") + "</li>")
    h.append("<li><b>Kind of source and recorded associations.</b> From Wikidata: what kind of "
             "body a source is (newspaper, academic publisher, think tank, advocacy group, "
             "court and so on, from the classes Wikidata assigns), and links recorded there: "
             "founded by, parent organisation, member of, affiliation, funded by, sponsor, chair, "
             "publisher, indexed in, and designation as a terrorist organisation by a government "
             "or international body. Each is a statement on Wikidata, linked so it can be checked. "
             "A link records a connection; it is not a rating.</li>")
    h.append("<li><b>Wikidata.</b> Facts entered by volunteers on Wikidata, Wikipedia's sister "
             "database: country, current owner, political alignment and ideology where recorded, "
             "and whether it is classed as state media, a public broadcaster or a state-owned "
             f"enterprise. Retrieved {escape(snap['built'])}.</li></ul>")
    h.append(note(" ".join(SOURCE_NOTES), "Read with care"))

    # Wikipedia's list compared with the independent assessments
    L = snap.get("wikipedia_list_compared", [])
    h.append("<h2>Wikipedia's ratings next to independent ratings</h2>"
             f"<p>All {len(L)} entries on Wikipedia's list, cited in the analysed articles or not, "
             "with the independent scores for their websites where those exist. Each entry counts "
             "once. Entries without a website (for example, books) have no independent score.</p>")
    h.append("<h3>By Wikipedia's rating</h3><div class='scroll'><table><tr><th>Wikipedia's rating</th>"
             "<th class='n'>Entries</th><th class='n'>With an independent quality score</th>"
             "<th class='n'>Median independent quality</th><th class='n'>With an audience score</th>"
             "<th class='n'>Median audience leaning</th></tr>")
    for st in [x for x in RATING_ORDER if x]:
        rows = [x for x in L if x["status"] == st]
        if not rows:
            continue
        q = [x["independent_quality"] for x in rows if x["independent_quality"] is not None]
        a = [x["audience_leaning"] for x in rows if x["audience_leaning"] is not None]
        h.append(f"<tr><td>{escape(RATING_NAMES[st])}</td><td class='n'>{len(rows)}</td>"
                 f"<td class='n'>{len(q)}</td><td class='n'>{f'{median(q):.2f}' if q else '–'}</td>"
                 f"<td class='n'>{len(a)}</td><td class='n'>{f'{median(a):+.2f}' if a else '–'}</td></tr>")
    h.append("</table></div>")
    h.append("<h3>By audience leaning</h3><p class='small'>Entries on Wikipedia's list that have an "
             "audience score, grouped into five equal ranges of that score, with how Wikipedia "
             "rates them and their median independent quality score.</p>"
             "<div class='scroll'><table><tr><th>Audience leaning</th><th class='n'>Entries</th>"
             + "".join(f"<th class='n'>{escape(RATING_NAMES[x])}</th>" for x in RATING_ORDER if x)
             + "<th class='n'>Median independent quality</th></tr>")
    for lo, hi, lbl in AUD_BINS:
        rows = [x for x in L if x["audience_leaning"] is not None and lo <= x["audience_leaning"] < hi]
        c = Counter(x["status"] for x in rows)
        q = [x["independent_quality"] for x in rows if x["independent_quality"] is not None]
        h.append(f"<tr><td>{escape(lbl)}</td><td class='n'>{len(rows)}</td>"
                 + "".join(f"<td class='n'>{p0(c[x] / len(rows)) if rows else '–'}</td>"
                           for x in RATING_ORDER if x)
                 + f"<td class='n'>{f'{median(q):.2f}' if q else '–'} "
                   f"<span class='small'>({len(q)})</span></td></tr>")
    h.append("</table></div><p class='small'>−1 means shared only by Democrats and +1 only by "
             "Republicans. Percentages are shares of the entries in that row.</p>")
    h.append("<details><summary>All entries on Wikipedia's list</summary><div class='scroll'><table>"
             "<tr><th>Entry</th><th>Wikipedia's rating</th><th class='n'>Independent quality</th>"
             "<th class='n'>Audience leaning</th><th>AllSides (2018)</th></tr>")
    for x in L:
        qv = f"{x['independent_quality']:.2f}" if x["independent_quality"] is not None else "–"
        av = f"{x['audience_leaning']:+.2f}" if x["audience_leaning"] is not None else "–"
        h.append(f"<tr><td>{escape(x['entry'])}</td><td class='small'>{escape(RATING_NAMES.get(x['status'], x['status']))}</td>"
                 f"<td class='n'>{qv}</td><td class='n'>{av}</td>"
                 f"<td class='small'>{escape(x['allsides_2018'] or '–')}</td></tr>")
    h.append("</table></div></details>")

    # most-cited, by topic area, then across all areas
    from .sources import NOT_A_SOURCE

    def cited_table(recs, top):
        cites, arts = Counter(), Counter()
        for r in recs:
            for x in (r.get("sources") or {}).get("list", []):
                cites[x["source"]] += x["citations"]
                arts[x["source"]] += 1
        tot = sum(cites.values())
        out = ["<div class='scroll'><table><tr><th>Source</th><th class='n'>Citations</th>"
               f"<th class='n'>Articles</th>{ASSESSOR_HEAD}</tr>"]
        ranked = sorted(((k, n) for k, n in cites.items() if k not in NOT_A_SOURCE),
                        key=lambda x: (-x[1], x[0]))
        for k, n in ranked[:top]:
            out.append(f"<tr><td>{source_label(k, ctx)}</td><td class='n'>{n:,}</td>"
                       f"<td class='n'>{arts[k]}</td>{_assessor_cells(k, ctx)}</tr>")
        out.append(summary_rows(cites, ctx, 3, 3))
        out.append("</table></div>")
        out.append(_non_source_line(cites, tot))
        return "".join(out), tot, len(ranked)

    if any(r.get("sources") for r in ctx.recs):
        h.append("<h2>Most-cited sources, by topic area</h2><p>Each table lists the 50 sources "
                 "cited most often in that area's analysed articles. An article in several areas "
                 "is counted under the area it is shown under.</p>" + MEANS_NOTE)
        for a in _area_order(ctx):
            recs = [r for r in ctx.recs if ctx.areas.get(r["article"], "") == a]
            if not any(r.get("sources") for r in recs):
                continue
            tbl, tot, nsrc = cited_table(recs, 50)
            h.append(f"<details><summary><b>{escape(area_name(a))}</b>: {len(recs):,} "
                     f"article{'s' if len(recs) != 1 else ''}, "
                     f"{tot:,} citations, {nsrc:,} sources</summary>{tbl}</details>")
        # organisations: kind and recorded associations
        from .outlets import ORG_KINDS
        oc, oarts, oareas = Counter(), Counter(), {}
        for r in ctx.recs:
            for x in (r.get("sources") or {}).get("list", []):
                o = ctx.outlets.get(x["source"]) or {}
                designated = "designated as terrorist by" in (o.get("associations") or {})
                if o.get("kind") in ORG_KINDS or designated:
                    oc[x["source"]] += x["citations"]
                    oarts[x["source"]] += 1
                    oareas.setdefault(x["source"], set()).add(ctx.areas.get(r["article"], ""))
        if oc:
            h.append("<h2>Organisations cited: checklist and recorded associations</h2>"
                     "<p>The same checklist is applied to every organisation listed: registration in "
                     "a public registry (with a link to the official record), recorded funders, "
                     "founders, leadership, affiliations, political alignment, any terrorist "
                     "designation, ratings by Wikipedia and by independent raters, a Wikipedia "
                     "article, and for US non-profits the latest public tax filing. Each item is "
                     "either found, with its evidence, or not found in these records, which is not "
                     "the same as absent. There is no total and no score.</p>"
                     "<p>Think tanks, advocacy and activist groups, human rights organisations, "
                     "charities and foundations, NGOs, religious organisations, trade unions, "
                     "political parties and armed organisations cited in the analysed articles, "
                     "and any organisation a government or international body has designated as "
                     "terrorist. Each association is a statement on Wikidata, linked so it can be "
                     "checked; organisations with none recorded show a dash. † marks a statement "
                     "for which Wikidata cites no source (anyone can edit Wikidata). A recorded "
                     "connection is not a rating, and an organisation without one may simply not "
                     "have it entered on Wikidata.</p>"
                     f"<details><summary>Show {len(oc):,} organisations</summary>"
                     "<div class='scroll'><table><tr><th>Organisation</th><th>Kind</th>"
                     "<th class='n'>Citations</th><th class='n'>Articles</th><th>Areas</th>"
                     "<th>Checklist</th><th>All recorded associations (Wikidata)</th></tr>")
            for k, n in sorted(oc.items(), key=lambda x: (-x[1], x[0]))[:300]:
                o = ctx.outlets.get(k) or {}
                wr = o.get("wikipedia_rating")
                wdl = (f" <a class='small' href='https://www.wikidata.org/wiki/{escape(o['wikidata'])}'>"
                       "Wikidata</a>" if o.get("wikidata") else "")
                h.append(f"<tr><td>{source_label(k, ctx)}{wdl}</td><td class='small'>{escape(o.get('kind') or '–')}</td>"
                         f"<td class='n'>{n:,}</td><td class='n'>{oarts[k]}</td>"
                         f"<td class='small'>{escape('; '.join(sorted(area_name(a) for a in oareas[k])))}</td>"
                         f"<td class='small'>{checklist_cell(o)}</td>"
                         f"<td class='small'>{assoc_text(o, links=True) or '–'}</td></tr>")
            h.append("</table></div></details>")
        # journals
        jc, jarts = Counter(), Counter()
        for r in ctx.recs:
            for x in (r.get("sources") or {}).get("list", []):
                o = ctx.outlets.get(x["source"]) or {}
                if (o.get("checklist") or {}).get("type") == "journal":
                    jc[x["source"]] += x["citations"]
                    jarts[x["source"]] += 1
        if jc:
            h.append("<h2>Journals cited: checklist</h2><p>Every journal cited in the analysed "
                     "articles that Wikidata classes as an academic journal, or that the Finnish "
                     "Publication Forum lists, with the same checklist for each: ISSN, publisher, "
                     "indexing in Scopus and other indexes, the Directory of Open Access Journals, "
                     "an academic level from the Finnish and Danish registers, DOI registration "
                     "with Crossref, and whether Wikidata classes it as a predatory journal.</p>"
                     f"<details><summary>Show {len(jc):,} journals</summary>"
                     "<div class='scroll'><table><tr><th>Journal</th><th class='n'>Citations</th>"
                     "<th class='n'>Articles</th><th>Checklist</th></tr>")
            for k, n in sorted(jc.items(), key=lambda x: (-x[1], x[0]))[:300]:
                o = ctx.outlets.get(k) or {}
                h.append(f"<tr><td>{source_label(k, ctx)}</td><td class='n'>{n:,}</td>"
                         f"<td class='n'>{jarts[k]}</td><td class='small'>{checklist_cell(o)}</td></tr>")
            h.append("</table></div></details>")
        h.append(flagged_sources_section(ctx))
        h.append(books_section(ctx))
        h.append(reused_works_section(ctx))
        h.append(websites_section(ctx))
        h.append(trace_section(ctx))
        tbl, tot, nsrc = cited_table(ctx.recs, 100)
        h.append(f"<h3>All areas together</h3><details><summary>{len(ctx.recs):,} articles, "
                 f"{tot:,} citations, {nsrc:,} sources (top 100)</summary>{tbl}</details>")
    h.append(f"<p class='small'>{link('data/outlets.json', 'All ratings as JSON')}.</p>")
    return page(f"Sources · {NAME}", "".join(h), "sources.html", json_alt="data/outlets.json",
                description="Sources cited in the analysed articles, and how several raters rate them.")


RATED_KEYS = ("wikipedia_rating", "independent_quality", "audience_leaning", "allsides_2018", "mbfc",
              "academic_level")


def _coverage(o):
    """(rated by any rater, kind known, anything recorded) for one snapshot entry."""
    o = o or {}
    rated = any(o.get(x) for x in RATED_KEYS)
    kind = bool(o.get("kind"))
    rec = bool(o.get("associations") or o.get("owned_by") or o.get("registries")
               or o.get("wikidata"))
    return rated, kind, rated or kind or rec


def flagged_sources_section(ctx):
    """For each kind of opinion or harder-to-check citation: how many have an identified source,
    and how many of those sources any rater rates or Wikidata describes."""
    from collections import Counter
    from .sources import CHECK_FLAGS, NOT_A_SOURCE
    by_flag = {f: Counter() for f in CHECK_FLAGS}
    arts = {f: Counter() for f in CHECK_FLAGS}
    for r in ctx.recs:
        for x in (r.get("sources") or {}).get("list", []):
            for f, n in (x.get("flags") or {}).items():
                by_flag[f][x["source"]] += n
                arts[f][x["source"]] += 1
    if not any(by_flag.values()):
        return ""
    h = ["<h2>Opinion and harder-to-check citations: the sources behind them</h2>"
         "<p>Citations to opinion, comment or blog sections, and citations a reader would find "
         "harder to check, with how far their sources are profiled. <i>Identified</i>: the "
         "citation names or links a source. <i>Rated</i>: at least one rater on this page rates "
         "the source. <i>Kind known</i>: Wikidata records what kind of body it is. <i>Anything "
         "recorded</i>: rated, kind known, or found on Wikidata at all. Shares of the citations "
         "with an identified source.</p><div class='scroll'><table><tr><th>Citations that are</th>"
         "<th class='n'>Citations</th><th class='n'>Identified</th><th class='n'>Rated</th>"
         "<th class='n'>Kind known</th><th class='n'>Anything recorded</th></tr>"]
    for f in CHECK_FLAGS:
        c = by_flag[f]
        tot = sum(c.values())
        if not tot:
            continue
        ided = {k: n for k, n in c.items() if k not in NOT_A_SOURCE}
        ni = sum(ided.values())
        cov = [sum(n for k, n in ided.items() if _coverage(ctx.outlets.get(k))[i]) for i in range(3)]
        h.append(f"<tr><td>{escape(cap(FLAG_NAMES[f]))}</td><td class='n'>{tot:,}</td>"
                 f"<td class='n'>{p0(ni / tot)}</td>"
                 + "".join(f"<td class='n'>{p0(v / ni) if ni else '–'}</td>" for v in cov) + "</tr>")
    h.append("</table></div>")
    for f in CHECK_FLAGS:
        c = by_flag[f]
        ranked = sorted(((k, n) for k, n in c.items() if k not in NOT_A_SOURCE),
                        key=lambda x: (-x[1], x[0]))
        if not ranked:
            continue
        h.append(f"<details><summary>{escape(cap(FLAG_NAMES[f]))}: the {min(50, len(ranked))} "
                 f"sources with the most such citations</summary><div class='scroll'><table>"
                 f"<tr><th>Source</th><th class='n'>Such citations</th><th class='n'>Articles</th>"
                 f"{ASSESSOR_HEAD}</tr>")
        for k, n in ranked[:50]:
            h.append(f"<tr><td>{source_label(k, ctx)}</td><td class='n'>{n:,}</td>"
                     f"<td class='n'>{arts[f][k]}</td>{_assessor_cells(k, ctx)}</tr>")
        h.append("</table></div></details>")
    return "".join(h)


ENGLISH_AGENCIES = ("English language", "United States")   # 978-0, 978-1 and 979-8


def books_section(ctx):
    """Books cited by ISBN: where the ISBNs were issued, what Open Library records, and the
    publishers of books not in English, each with the publisher checklist."""
    from collections import Counter
    from . import books as bk
    data, _ = bk.load()
    B = (data or {}).get("books", {})
    if not B:
        return ""
    per_book = {}            # isbn -> {sources, articles, citations, flags}
    by_source_isbn = Counter()
    from_isbn = Counter()
    nopub = 0
    for r in ctx.recs:
        s = r.get("sources") or {}
        for x in s.get("list", []):
            for how, n in (x.get("publisher_from_isbn") or {}).items():
                from_isbn[how] += n
            if x["source"] == "book (no publisher given)":
                nopub += x["citations"]
        for it in s.get("items", []):
            if not it["id"].startswith("isbn:"):
                continue
            b = per_book.setdefault(it["id"][5:], {"source": Counter(), "articles": set(),
                                                   "citations": 0, "flags": set()})
            b["source"][it["source"]] += it["citations"]
            b["articles"].add(r["article"])
            b["citations"] += it["citations"]
            b["flags"] |= set(it.get("flags", []))
    if not per_book:
        return ""
    invalid = sum(1 for r in ctx.recs for it in (r.get("sources") or {}).get("items", [])
                  if it["id"].startswith("isbn-invalid:"))
    on_ol = sum(1 for i in per_book if B.get(i))
    h = ["<h2>Books: publishers, where their ISBNs were issued, and languages</h2>",
         f"<p>{len(per_book):,} different books are cited by ISBN in the analysed articles "
         f"({sum(b['citations'] for b in per_book.values()):,} citations). Open Library has a "
         f"record of {on_ol:,} ({p0(on_ol / len(per_book))}). Where a citation names no publisher, "
         f"the publisher was taken from Open Library's record of the ISBN for "
         f"{from_isbn.get('Open Library', 0):,} citations, and from the Wikidata item that holds the "
         f"ISBN's publisher prefix for {from_isbn.get('ISBN prefix (Wikidata)', 0):,}; "
         f"{nopub:,} book citations still name no publisher. {invalid:,} cited ISBNs fail their "
         "check digit.</p>",
         "<p>An ISBN is issued by a national or language-area agency, and its first digits say "
         "which (the <a href='https://www.isbn-international.org/range_file_generation'>International "
         "ISBN Agency's range file</a>). That is where the publisher registered, not necessarily "
         "the language of the book. Languages are as Open Library records them.</p>"]
    # by issuing agency
    ag = {}
    for i, b in per_book.items():
        sp = bk.split(i)
        a = sp["agency"] if sp else "not in the range file"
        g = ag.setdefault(a, {"books": 0, "citations": 0, "articles": set(), "ol": 0,
                              "langs": Counter(), "rated": 0, "kind": 0})
        g["books"] += 1
        g["citations"] += b["citations"]
        g["articles"] |= b["articles"]
        rec = B.get(i)
        if rec:
            g["ol"] += 1
            for l in rec.get("languages") or []:
                g["langs"][bk.lang_name(l)] += 1
        src = b["source"].most_common(1)[0][0]
        cv = _coverage(ctx.outlets.get(src))
        g["rated"] += cv[0]
        g["kind"] += cv[1]
    h.append("<details open><summary>By the agency that issued the ISBN</summary>"
             "<div class='scroll'><table><tr><th>ISBN issued by</th><th class='n'>Books</th>"
             "<th class='n'>Citations</th><th class='n'>Articles</th><th class='n'>On Open Library</th>"
             "<th>Languages (Open Library)</th><th class='n'>Publisher rated</th>"
             "<th class='n'>Publisher's kind known</th></tr>")
    for a, g in sorted(ag.items(), key=lambda x: (-x[1]["books"], x[0])):
        langs = ", ".join(f"{escape(k)} {v}" for k, v in g["langs"].most_common(4)) or "–"
        h.append(f"<tr><td>{escape(a)}</td><td class='n'>{g['books']:,}</td>"
                 f"<td class='n'>{g['citations']:,}</td><td class='n'>{len(g['articles']):,}</td>"
                 f"<td class='n'>{p0(g['ol'] / g['books'])}</td><td class='small'>{langs}</td>"
                 f"<td class='n'>{p0(g['rated'] / g['books'])}</td>"
                 f"<td class='n'>{p0(g['kind'] / g['books'])}</td></tr>")
    h.append("</table></div><p class='small'>Publisher rated / kind known: share of the books "
             "whose publisher (as matched for the citation) has a rating from any rater on this "
             "page, or a kind recorded on Wikidata.</p></details>")
    # publishers of books not in English, or with ISBNs issued outside the English-language groups
    pubs = {}
    for i, b in per_book.items():
        rec = B.get(i) or {}
        langs = rec.get("languages") or []
        sp = bk.split(i)
        non_en = ("not_english" in b["flags"]) or (langs and "eng" not in langs) or \
                 (sp and sp["agency"] not in ENGLISH_AGENCIES)
        if not non_en:
            continue
        for src, n in b["source"].items():
            p = pubs.setdefault(src, {"books": 0, "citations": 0, "articles": set(),
                                      "agencies": Counter(), "langs": Counter()})
            p["books"] += 1
            p["citations"] += n
            p["articles"] |= b["articles"]
            p["agencies"][sp["agency"] if sp else "?"] += 1
            for l in langs:
                p["langs"][bk.lang_name(l)] += 1
    if pubs:
        from .sources import NOT_A_SOURCE
        shown = sorted(((k, v) for k, v in pubs.items() if k not in NOT_A_SOURCE),
                       key=lambda x: (-x[1]["citations"], x[0]))
        h.append("<h3>Publishers of books not in English or registered outside the English-language "
                 "ISBN groups</h3><p>A book is listed when its citation gives a language other than "
                 "English, Open Library records it only in other languages, or its ISBN was issued "
                 "by an agency other than the English-language groups (978-0, 978-1, and 979-8 for the United States). For each "
                 "publisher, the same checklist: found on Wikidata, classed there as a self-publishing "
                 "company, owner or parent organisation, founders, affiliations, political alignment, "
                 "an academic level from the Finnish register, Wikipedia articles in any language, "
                 "and ratings. Each item is found, with its evidence, or not found in these records, "
                 "which is not the same as absent. There is no score. † marks a Wikidata statement "
                 "with no source given there.</p>"
                 f"<details><summary>Show {len(shown):,} publishers</summary><div class='scroll'><table>"
                 "<tr><th>Publisher</th><th class='n'>Books</th><th class='n'>Citations</th>"
                 "<th class='n'>Articles</th><th>ISBN issued by</th><th>Languages (Open Library)</th>"
                 "<th>Kind</th><th>Checklist</th><th>Recorded associations (Wikidata)</th></tr>")
        for k, v in shown[:400]:
            o = ctx.outlets.get(k) or {}
            wdl = (f" <a class='small' href='https://www.wikidata.org/wiki/{escape(o['wikidata'])}'>"
                   "Wikidata</a>" if o.get("wikidata") else "")
            h.append(f"<tr><td>{source_label(k, ctx)}{wdl}</td><td class='n'>{v['books']}</td>"
                     f"<td class='n'>{v['citations']}</td><td class='n'>{len(v['articles'])}</td>"
                     f"<td class='small'>{escape(', '.join(f'{a} {n}' for a, n in v['agencies'].most_common(3)))}</td>"
                     f"<td class='small'>{escape(', '.join(f'{a} {n}' for a, n in v['langs'].most_common(3))) or '–'}</td>"
                     f"<td class='small'>{escape(o.get('kind') or '–')}</td>"
                     f"<td class='small'>{checklist_cell(o)}</td>"
                     f"<td class='small'>{assoc_text(o, links=True) or '–'}</td></tr>")
        h.append("</table></div></details>")
        unnamed = [(k, v) for k, v in pubs.items() if k in NOT_A_SOURCE]
        if unnamed:
            nb = sum(v["books"] for _, v in unnamed)
            h.append(f"<p class='small'>A further {nb:,} such books have no publisher in the "
                     "citation, on Open Library, or on Wikidata by ISBN prefix.</p>")
    return "".join(h)


def websites_section(ctx, top=600):
    """What cited websites say about themselves, read by fixed rules (wtl/siteprobe.py), and
    groups of cited sites that share a tracking or advertising account."""
    from collections import Counter
    _, probe, shared = _extra(ctx)
    if not probe:
        return ""
    cites, arts = Counter(), Counter()
    for r in ctx.recs:
        for x in (r.get("sources") or {}).get("list", []):
            cites[x["source"]] += x["citations"]
            arts[x["source"]] += 1
    st = Counter("read" if x["status"].startswith("read") else
                 "blocked by this computer's filter" if "blocked" in x["status"] else "not reachable"
                 for x in probe.values())
    found = Counter()
    for x in probe.values():
        found["a statement of who runs, owns or funds it"] += bool(x.get("statements"))
        found["a registration number"] += bool(x.get("registry_ids"))
        found["a copyright holder"] += bool(x.get("copyright"))
        found["a declared organisation (structured data)"] += bool(x.get("declared_organisation"))
        found["a tracking or advertising account ID"] += bool(x.get("trackers"))
        found["a domain registration date"] += bool((x.get("rdap") or {}).get("registered"))
        found["a named registrant"] += bool((x.get("rdap") or {}).get("registrant"))
    h = ["<h2>What cited websites say about themselves</h2>",
         f"<p>{len(probe):,} cited websites that no rater rates, or that Wikidata classes as an "
         "organisation, were read by fixed rules: the home page and up to three of the site's own "
         "pages that usually name the body behind it (about, legal notice, privacy policy). Where "
         "the site refused or could not be reached, the Internet Archive's latest saved copy was "
         "read instead, and is marked. From those pages: sentences of the form “a project of…”, "
         "“published by…”, “funded by…” (quoted as printed); charity, company and tax registration "
         "numbers, linked to the official register where it can be searched by number; the "
         "copyright line; what the site declares about itself in its structured data; tracking "
         "and advertising account IDs; and, from the domain registry (RDAP), when the domain was "
         "registered and by whom, where that is published. Nothing is inferred: a site that names "
         "no owner is recorded as naming none.</p>",
         "<p>" + ", ".join(f"{escape(k)}: {v:,}" for k, v in st.most_common()) + ". Of these, the "
         "pages read gave " + "; ".join(f"{escape(k)} for {v:,}" for k, v in found.most_common())
         + ".</p>"]
    rows = sorted(probe.items(), key=lambda x: (-cites[x[0]], x[0]))
    h.append(f"<details><summary>Show the {min(top, len(rows))} most-cited sites read</summary>"
             "<div class='scroll'><table><tr><th>Site</th><th class='n'>Citations</th>"
             "<th class='n'>Articles</th><th>What the site says</th><th>Registration numbers</th>"
             "<th>Copyright / declared organisation</th><th>Domain registered</th>"
             "<th>Shares a tracking account with</th></tr>")
    for k, x in rows[:top]:
        stt = "".join(f"<div>“{escape(t['text'])}” <a class='small' href='{escape(t['page'])}'>page</a></div>"
                      for t in x.get("statements", [])[:3])
        regs = "".join(f"<div>{escape(r['registry'])}: " + (f"<a href='{escape(r['register_url'])}'>{escape(r['id'])}</a>"
                                                           if r.get("register_url") else escape(r["id"])) + "</div>"
                       for r in x.get("registry_ids", [])[:4])
        org = "; ".join(escape(o.get("legalName") or o.get("name") or "") + (
            f" (parent: {escape(o['parentOrganization'])})" if o.get("parentOrganization") else "") + (
            f" (funder: {escape(o['funder'])})" if o.get("funder") else "")
            for o in x.get("declared_organisation", [])[:2] if o.get("legalName") or o.get("name"))
        cp = escape("; ".join(x.get("copyright", [])[:2]))
        rd = x.get("rdap") or {}
        reg = escape(rd.get("registered", "–")) + (f"<div class='small'>{escape(rd['registrant'])}</div>"
                                                   if rd.get("registrant") else "")
        net = sorted({d for n in shared.get(k, []) for d in n["sites"] if d != k})
        status = "" if x["status"] == "read" else f"<div class='small'>{escape(x['status'])}</div>"
        h.append(f"<tr><td>{source_label(k, ctx)}{status}</td><td class='n'>{cites[k]:,}</td>"
                 f"<td class='n'>{arts[k]}</td><td class='small'>{stt or '–'}</td>"
                 f"<td class='small'>{regs or '–'}</td>"
                 f"<td class='small'>{cp or '–'}{'<div>' + org + '</div>' if org else ''}</td>"
                 f"<td class='small'>{reg}</td><td class='small'>{escape(', '.join(net[:8])) or '–'}"
                 f"{'…' if len(net) > 8 else ''}</td></tr>")
    h.append("</table></div></details>")
    nets = {}
    for k, ns in shared.items():
        for n in ns:
            nets[(n["service"], n["id"])] = n["sites"]
    if nets:
        h.append("<h3>Cited sites that share a tracking or advertising account</h3><p>Groups of two "
                 "or more cited websites whose pages carry the same Google Analytics, Google Tag "
                 "Manager, AdSense, Facebook pixel or Yandex Metrica account ID. The same account "
                 "means the sites are measured or monetised from one account, which usually means "
                 "one operator; a shared web agency or a copied template can also cause it. "
                 "Accounts that belong to a platform rather than a site (such as the host account "
                 "Google's Site Kit plugin puts on every site that uses it), and any ID found on "
                 "more than 25 cited sites, are left out as shared services. The account IDs are "
                 "shown so the match can be checked in each site's page source.</p>"
                 f"<details><summary>Show {len(nets):,} groups</summary><div class='scroll'><table>"
                 "<tr><th>Account</th><th class='n'>Sites</th><th>Sites (citations)</th></tr>")
        for (svc, i), sites in sorted(nets.items(), key=lambda x: (-len(x[1]), -sum(cites[d] for d in x[1]), x[0])):
            h.append(f"<tr><td class='small'>{escape(svc)} {escape(i)}</td><td class='n'>{len(sites)}</td>"
                     f"<td class='small'>{escape(', '.join(f'{d} ({cites[d]})' for d in sorted(sites, key=lambda d: -cites[d])))}</td></tr>")
        h.append("</table></div></details>")
    h.append(f"<p class='small'>{link('data/siteprobe.json', 'Everything read, as JSON')}, with the "
             "address and fingerprint of each page read and the date.</p>")
    return "".join(h)


def trace_section(ctx, top=300):
    """Fingerprints of cited websites that do not need the live site (wtl/sitetrace.py)."""
    from collections import Counter
    tr = _trace(ctx)
    sites, groups = tr["sites"], tr["groups"]
    if not sites:
        return ""
    cites = Counter()
    for r in ctx.recs:
        for x in (r.get("sources") or {}).get("list", []):
            cites[x["source"]] += x["citations"]
    _, probe, _ = _extra(ctx)
    h = ["<h2>Cited websites: records kept elsewhere</h2>",
         "<p>Facts about cited websites that do not depend on reading the site as it is today. "
         "<b>Saved copies</b>: for sites that could not be read live, the same facts as above were "
         "read from the Internet Archive's most recent good copy of the home page (found through "
         "its capture index), the archived copies of the cited pages that the citations themselves "
         "link to, and the site's about and legal pages as archived; where the Internet Archive had "
         "none, from the most recent copy in Common Crawl's public web crawl. <b>DNS</b>: the "
         "site's name servers, mail servers, the domains its SPF record allows to send its mail, "
         "and site-verification codes (from Google, Facebook, Microsoft and others) published in "
         "its DNS. <b>Certificate logs</b> (for sites that could not be read live): the certificates issued for the site, from the public "
         "Certificate Transparency logs, with the earliest seen and the other domains named on the "
         "same certificate; certificates naming more than 10 domains are left out of that list, "
         "because hosting companies issue such certificates for unrelated customers. "
         "<b>Citations</b>: the names editors gave the site in the citations, the earliest access "
         "date stated, and the earliest saved copy of a cited page.</p>"]
    unread = [d for d, x in probe.items() if x.get("status", "").startswith("not reachable")]
    got = Counter(((sites.get(d) or {}).get("copies") or {}).get("status", "not yet checked") for d in unread)
    h.append(f"<p>Of the {len(unread):,} sites that could not be read live: "
             + ", ".join(f"{escape(k)}: {v:,}" for k, v in got.most_common()) + ".</p>")
    ra = sorted(((d, e["registered_after_citation"]) for d, e in sites.items()
                 if e.get("registered_after_citation")), key=lambda x: (-cites[x[0]], x[0]))
    if ra:
        h.append("<h3>Domains whose current registration began after they were cited</h3><p>The "
                 "domain registry (RDAP) gives a registration date later than the Internet Archive's "
                 "copy of a page on that same domain that a citation links to. Both dates are shown, "
                 "with the copy and the article citing it. Access dates written in citations are not "
                 "used, because editors who update a link to a site's new domain often keep the old "
                 "access date. A registration date after the copy means the domain was registered "
                 "anew after that date; the record does not show whether the holder changed. Some "
                 "registries report the latest transfer as the registration date.</p>"
                 f"<details><summary>Show {len(ra):,} domains</summary><div class='scroll'><table>"
                 "<tr><th>Domain</th><th class='n'>Citations</th><th>Registered (RDAP)</th>"
                 "<th>Archived copy of a cited page</th><th>Home page title then and today</th>"
                 "<th>Wikipedia's mark on these citations</th><th>Links added, and marks set, "
                 "after registration began</th></tr>")
        for d, x in ra:
            ev = "".join(f"<div><a href='{escape(e['url'])}'>{escape(e['date'])}</a>, cited in "
                         f"<a href='{WIKI}/w/index.php?oldid={e['revision']}'>{escape(e['article'])}</a></div>"
                         for e in x["earlier"])
            reg = (f"<a href='{escape(x['rdap'])}'>{escape(x['registered'])}</a>" if x.get("rdap")
                   else escape(x["registered"]))
            tn = (sites[d].get("titles") or {})
            tt = (f"<a href='{escape(tn['then_url'])}'>then</a>: {escape(tn.get('then_title') or '–')}"
                  f"<br>today: {escape(tn.get('now_title') or ('not reachable' if not isinstance(tn.get('now_status'), int) or tn['now_status'] >= 400 else '–'))}"
                  if tn else "not yet checked")
            h.append(f"<tr><td>{source_label(d, ctx)}</td><td class='n'>{cites[d]:,}</td>"
                     f"<td>{reg}</td><td class='small'>{ev}</td><td class='small'>{tt}</td>"
                     f"<td class='small'>{escape(marks_text(d, ctx) or '–')}</td>"
                     f"<td class='small'>{_after_counts(sites[d])}</td></tr>")
        h.append("</table></div></details>")
        h.append(_rereg_extra(ctx, tr, cites))
    gl = [(label, g) for label, g in groups.items() if g.get("groups")]
    pairs = (groups.get("named on the same certificate") or {}).get("pairs", [])
    if gl or pairs:
        h.append("<h3>Cited sites that share a DNS or certificate value</h3><p>Groups of two or "
                 "more cited websites with the same site-verification code in their DNS records; "
                 "groups whose name servers, mail servers or authorised mail senders are on the "
                 "domain of another cited site; and pairs of cited websites named together on one "
                 "certificate. The same verification code means the same account verified the sites "
                 "with that service, which can be an agency or host acting for several clients. "
                 "Some cited sites also provide mail or name servers to the public (a webmail or "
                 "cloud company, for example); their groups are shown like any other. Servers on "
                 "domains that are not cited sites are recorded per site but not grouped. Values "
                 "found on more than 25 cited sites are left out as common services.</p>")
        for label, g in gl:
            h.append(f"<details><summary>Same {escape(label)}: {len(g['groups']):,} groups</summary>"
                     "<div class='scroll'><table><tr><th>Value</th><th class='n'>Sites</th>"
                     "<th>Sites (citations)</th></tr>")
            for grp in sorted(g["groups"], key=lambda x: (-len(x["sites"]), -sum(cites[d] for d in x["sites"]), x["value"]))[:top]:
                h.append(f"<tr><td class='small'>{escape(grp['value'][:80])}</td><td class='n'>{len(grp['sites'])}</td>"
                         f"<td class='small'>{escape(', '.join(f'{d} ({cites[d]})' for d in sorted(grp['sites'], key=lambda d: -cites[d])))}</td></tr>")
            h.append("</table></div></details>")
        if pairs:
            h.append(f"<details><summary>Named on the same certificate: {len(pairs):,} pairs</summary>"
                     "<div class='scroll'><table><tr><th>Site</th><th>Site</th><th>Certificate</th></tr>")
            for a, b in sorted(pairs, key=lambda p: (-(cites[p[0]] + cites[p[1]]), p))[:top]:
                ex = next((t["example"] for t in ((sites.get(a) or {}).get("ct") or {}).get("named_with", [])
                           if t["domain"] == b), "")
                h.append(f"<tr><td>{escape(a)} ({cites[a]})</td><td>{escape(b)} ({cites[b]})</td>"
                         f"<td class='small'>{'<a href=' + chr(39) + escape(ex) + chr(39) + '>certificate</a>' if ex else '–'}</td></tr>")
            h.append("</table></div></details>")
    h.append(f"<p class='small'>{link('data/sitetrace.json', 'Everything recorded, as JSON')}, with "
             "the address of each saved copy read and the date of each lookup.</p>")
    return "".join(h)


def _after_counts(e):
    links = e.get("links", [])
    if not links:
        return "–"
    a = sum(x["added_after_registration"] for x in links)
    m = sum(x["mark_set_after_registration"] for x in links)
    return f"{a} of {len(links)} links added after; {m} marks set after"


def _rereg_extra(ctx, tr, cites):
    """Accounts adding links to several re-registered domains, and domains sharing a holder's
    identifiers (wtl/sitetrace.py)."""
    from . import sitetrace
    d = sitetrace.load()
    h = []
    acc = d.get("accounts_adding_after_registration") or []
    h.append("<h4>Accounts that added links to two or more such domains after registration began</h4>"
             "<p class='small'>Counted from the analysed articles' word histories: the revision that "
             "added each link's domain to the text. Only domains whose home page title today shares "
             "no word with the title then are counted, so registry dates that only reflect a "
             "transfer are left out (a revived site that kept its old name is left out as well). "
             "Accounts are shown as one-way IDs that differ from the IDs on the editors page; the "
             "diffs are on each article's page under “Links to check”. An editor can add a link to "
             "a site that looks like the original in good faith; the table records when, not why.</p>")
    if acc:
        h.append("<div class='scroll'><table><tr><th>ID</th><th class='n'>Domains</th>"
                 "<th class='n'>Links</th><th>Domains</th><th>Articles</th></tr>")
        for a in acc:
            h.append(f"<tr><td>{escape(a['id'])}</td><td class='n'>{len(a['domains'])}</td>"
                     f"<td class='n'>{a['links']}</td><td class='small'>{escape(', '.join(a['domains']))}</td>"
                     f"<td class='small'>{', '.join(link('articles/' + slug(x) + '.html', x) for x in a['articles'])}</td></tr>")
        h.append("</table></div>")
    else:
        h.append("<p class='small'>None found.</p>")
    rg = {k: v for k, v in (d.get("reregistered_groups") or {}).items() if v}
    h.append("<h4>Such domains that share an identifier</h4><p class='small'>Domains registered "
             "after they were cited that share a tracking or advertising account read from the "
             "live site, a site-verification code in their DNS, or the domain their home page now "
             "redirects to. A shared value records only that the same value appears.</p>")
    if rg:
        for label, groups in rg.items():
            h.append(f"<details><summary>Same {escape(label)}: {len(groups)} groups</summary>"
                     "<div class='scroll'><table><tr><th>Value</th><th>Domains (citations)</th></tr>")
            for g in sorted(groups, key=lambda g: (-len(g["sites"]), g["value"])):
                h.append(f"<tr><td class='small'>{escape(g['value'][:80])}</td><td class='small'>"
                         f"{escape(', '.join(f'{x} ({cites[x]})' for x in g['sites']))}</td></tr>")
            h.append("</table></div></details>")
    else:
        h.append("<p class='small'>None found.</p>")
    return "".join(h)


def _work_link(iid):
    kind, _, v = iid.partition(":")
    if kind == "isbn":
        from . import books as bk
        return (f"<a href='https://openlibrary.org/isbn/{escape(v)}'>ISBN {escape(bk.hyphenated(v))}</a>")
    if kind == "doi":
        return f"<a href='https://doi.org/{escape(v)}'>doi:{escape(v)}</a>"
    if kind == "url":
        return f"<a href='https://{escape(v)}' rel='nofollow'>{escape(v[:70])}{'…' if len(v) > 70 else ''}</a>"
    return escape(iid)


def reused_works_section(ctx, min_articles=3, top=200):
    """The same work (ISBN, DOI or web address) cited in several analysed articles, and in how
    many of those one account added it."""
    from collections import Counter
    from .fetch import cache
    from .sources import NOT_A_SOURCE
    works = {}
    for r in ctx.recs:
        lk = cache.load(cache.path("patterns", "labels", str(r["revision"])))
        for it in (r.get("sources") or {}).get("items", []):
            if it["id"].startswith("isbn-invalid:"):
                continue
            w = works.setdefault(it["id"], {"source": it["source"], "articles": set(),
                                            "citations": 0, "flags": set(), "by": Counter(),
                                            "known": 0})
            w["articles"].add(r["article"])
            w["citations"] += it["citations"]
            w["flags"] |= set(it.get("flags", []))
            if lk:
                w["known"] += 1
                for acct in {lk.get(l) for l in it.get("added_by", {}) if lk.get(l)}:
                    w["by"][acct] += 1
    from . import reuse as ru
    RU = ru.load()
    many = [(k, w) for k, w in works.items() if len(w["articles"]) >= min_articles]
    if not many and not RU:
        return ""
    many.sort(key=lambda x: (-len(x[1]["articles"]), -x[1]["citations"], x[0]))
    h = ["<h2>Works cited in several analysed articles</h2>",
         f"<p>The same book (by ISBN), paper (by DOI) or web page (by address) cited in at least "
         f"{min_articles} of the analysed articles: {len(many):,} works. <i>Most by one editor</i>: "
         "the largest number of these articles in which the same account added the citation (the "
         "account is not named or numbered). Read it next to the number of articles: a work added "
         "by many different editors and one added by the same editor in each article are "
         "different patterns of use.</p>"
         f"<details><summary>Show the {min(top, len(many))} works cited in the most articles</summary>"
         "<div class='scroll'><table><tr><th>Work</th><th>Source</th><th class='n'>Articles</th>"
         "<th class='n'>Citations</th><th class='n'>Most by one editor</th>"
         "<th class='n'>English Wikipedia articles citing it</th><th>Flags</th>"
         "<th>Wikipedia's rating</th></tr>"]
    for k, w in many[:top]:
        o = ctx.outlets.get(w["source"]) or {}
        wr = (o.get("wikipedia_rating") or {}).get("status")
        mx = max(w["by"].values()) if w["by"] else None
        h.append(f"<tr><td class='small'>{_work_link(k)}</td>"
                 f"<td>{source_label(w['source'], ctx) if w['source'] not in NOT_A_SOURCE else escape(w['source'])}</td>"
                 f"<td class='n'>{len(w['articles'])}</td><td class='n'>{w['citations']}</td>"
                 f"<td class='n'>{mx if mx else '–'}</td><td class='n'>{_wiki_count(RU.get(k))}</td>"
                 f"<td class='small'>{escape(', '.join(FLAG_NAMES[f] for f in sorted(w['flags']) if f in FLAG_NAMES)) or '–'}</td>"
                 f"<td class='small'>{escape(RATING_NAMES.get(wr, wr) if wr else '–')}</td></tr>")
    h.append("</table></div></details>")
    if RU:
        wide = sorted(((k, v) for k, v in RU.items() if k in works and v["articles"] >= 2),
                      key=lambda x: (-x[1]["articles"], x[0]))
        h.append("<h3>Unrated, opinion and non-English works: other uses across English Wikipedia</h3>"
                 f"<p>For {len(RU):,} cited works (web pages and books whose source no rater rates, "
                 "or that are flagged as opinion or not in English, and every book whose ISBN was "
                 "issued outside the English-language groups): how many English Wikipedia articles "
                 "cite the same work, counting the analysed article itself. Web pages are found "
                 "through Wikipedia's record of external links; books by searching for the ISBN "
                 "written four standard ways, so a book whose ISBN is written another way is "
                 f"missed and its count is a lower bound. {len(wide):,} of these works are cited in "
                 "two or more articles.</p>"
                 f"<details><summary>Show the {min(top, len(wide))} cited in the most articles"
                 "</summary><div class='scroll'><table><tr><th>Work</th><th>Source</th>"
                 "<th class='n'>English Wikipedia articles</th><th class='n'>Analysed articles</th>"
                 "<th class='n'>Most by one editor</th><th>Flags</th><th>Some of the articles</th></tr>")
        for k, v in wide[:top]:
            w = works[k]
            mx = max(w["by"].values()) if w["by"] else None
            some = ", ".join(v["titles"][:6]) + ("…" if v["articles"] > 6 else "")
            h.append(f"<tr><td class='small'>{_work_link(k)}</td>"
                     f"<td>{source_label(w['source'], ctx) if w['source'] not in NOT_A_SOURCE else escape(w['source'])}</td>"
                     f"<td class='n'>{_wiki_count(v)}</td><td class='n'>{len(w['articles'])}</td>"
                     f"<td class='n'>{mx if mx else '–'}</td>"
                     f"<td class='small'>{escape(', '.join(FLAG_NAMES[f] for f in sorted(w['flags']) if f in FLAG_NAMES)) or '–'}</td>"
                     f"<td class='small'>{escape(some)}</td></tr>")
        h.append(f"</table></div></details><p class='small'>{link('data/reuse.json', 'All counts as JSON')}, "
                 f"with the date each was checked.</p>")
    return "".join(h)


def _wiki_count(v):
    if not v:
        return "–"
    return f"{v['articles']:,}{'+' if v.get('capped') else ''}"


# ---------------------------------------------------------------- editors across articles
EDITORS_NOTE = (
    "Editors are shown under pattern IDs (for example K7Q2MX), a keyed code of the account that "
    "cannot be reversed by trying account numbers. Pattern IDs are different from the “Editor 1, "
    "Editor 2” labels on article pages, and shares are shown as ranges, but an editor listed for "
    "an article can often be matched to that article's history, so this is not anonymity. "
    "Everything here comes from Wikipedia's public edit histories, which anyone can analyse with "
    "their own tools. Being listed says only that the editor's words are in the article; it is not "
    "a finding about the editor. Please do not contact, harass or target any editor; concerns "
    "about conduct belong in Wikipedia's own processes.")

FT_CSS = ("<style>.ft td{min-width:120px}"
          ".ft td:first-child{min-width:0;white-space:nowrap}"
          ".pick{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}.pick label{flex:1 1 260px;"
          "font-family:system-ui,-apple-system,sans-serif;font-size:.9rem}.pick input{width:100%;"
          "font-size:1rem;padding:8px 10px;border:1px solid var(--line);border-radius:6px;"
          "background:var(--bg);color:var(--fg)}</style>")


def _ed_src(x):
    """Plain-language summary of an editor's cited sources (escaped HTML)."""
    if not x:
        return "–"
    wr = "; ".join(f"{escape(RATING_NAMES.get(k, k) if k != 'not listed' else 'not on the list')} {escape(v)}"
                   for k, v in x["wikipedia_rating"].items())
    bits = [f"{escape(x['citations'])} citations.", f"Wikipedia's rating: {wr}."]
    if x["independent_quality_median"] is not None:
        bits.append(f"Independent quality: median {x['independent_quality_median']:.1f} "
                    f"({escape(x['independent_quality_coverage'])} scored).")
    kd = {k: v for k, v in (x.get("kinds") or {}).items() if k != "not classified"}
    if kd:
        bits.append("Kinds of source: " + "; ".join(f"{escape(k)} {escape(v)}" for k, v in kd.items()) + ".")
    if x["most_cited"]:
        bits.append("Most cited: " + "; ".join(f"{escape(k)} ({escape(v)})" for k, v in x["most_cited"].items()) + ".")
    return " ".join(bits)


def _ed_fp(e, area_name):
    """One editor's fingerprint as compact JSON for the look-up page."""
    el = e.get("elsewhere")
    return {"s": e["sanctioned"], "t": e["types"], "n": e["articles_with_text"],
            "a": [[a, v] for a, v in e["shares"].items()],
            "g": "; ".join(f"{n} of the {m} analysed articles in {g}" for g, (n, m) in e["topics"].items()),
            "src": _ed_src(e.get("sources")),
            "el": ("" if not el else f"{escape(el['edits'])} article edits. " + "; ".join(
                f"{escape(area_name.get(a, a))}: {escape(v)}" for a, v in el["areas"].items()))}


def write_editor_data(site_dir, ctx):
    """data/editors/a/<slug>.js per article and data/editors/id/<first letter>.js, loaded by the
    look-up page only when asked for (script tags, so it also works opened from disk)."""
    from .candidates import AREAS
    area_name = {k: v[0] for k, v in AREAS.items()} | {"outside": "outside these areas"}
    pt = ctx.patterns
    fps = {e["id"]: _ed_fp(e, area_name) for e in pt["editors"]}
    base = site_dir / "data" / "editors"
    (base / "a").mkdir(parents=True, exist_ok=True)
    (base / "id").mkdir(parents=True, exist_ok=True)
    for art, d in pt["by_article"].items():
        body = {"art": art, "rest": [d["rest_editors"], d["rest_share"]],
                "ed": [[i, here, fps[i]] for i, here in d["editors"]]}
        (base / "a" / f"{slug(art)}.js").write_text(
            "WTLED(" + json.dumps(body, ensure_ascii=False, separators=(",", ":")) + ");\n", encoding="utf-8")
    shards = {}
    for i, fp in fps.items():
        shards.setdefault(i[0], {})[i] = fp
    for c, d in shards.items():
        (base / "id" / f"{c}.js").write_text(
            f"WTLID({json.dumps(c)}," + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + ");\n",
            encoding="utf-8")


LOOKUP_JS = r"""
<script>
(function(){
var ARTS=__ARTS__, SHOW_EL=__EL__;
var bySlug={}, byTitle={};
ARTS.forEach(function(x){bySlug[x[1]]=x[0];byTitle[x[0]]=x[1];});
var out=document.getElementById('out'), idc={}, want=null;
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function load(src){var e=document.createElement('script');e.src=src;e.onerror=function(){out.innerHTML='<p>Could not load the data.</p>';};document.head.appendChild(e);}
function artLinks(a){
  var shown=a.slice(0,6).map(function(x){var s=byTitle[x[0]];return (s?'<a href="#a='+esc(s)+'">'+esc(x[0])+'</a>':esc(x[0]))+' '+esc(x[1]);});
  var h=shown.join('; ');
  if(a.length>6){h+='<details><summary>all '+a.length+'</summary>'+a.slice(6).map(function(x){var s=byTitle[x[0]];return (s?'<a href="#a='+esc(s)+'">'+esc(x[0])+'</a>':esc(x[0]))+' '+esc(x[1]);}).join('; ')+'</details>';}
  return h;
}
function head(first){return '<div class="ft"><table><tr><th>Pattern ID</th>'+(first?'<th class="n">'+first+'</th>':'')+'<th>Sanctioned by Wikipedia</th><th class="n">Analysed articles with their text</th><th>Analysed articles where they wrote at least 1% (share of each)</th><th>Topic groups of those articles</th><th>Sources they cited, across all analysed articles</th>'+(SHOW_EL?'<th>Where they edit across Wikipedia</th>':'')+'</tr>';}
function row(id,fp,here){
  return '<tr><td><code><a href="#id='+id+'">'+id+'</a></code></td>'+(here!==undefined?'<td class="n">'+esc(here)+'</td>':'')+
   '<td class="small">'+(fp.s?'yes'+(fp.t.length?' ('+esc(fp.t.join(', '))+')':''):'no')+'</td><td class="n">'+fp.n+'</td>'+
   '<td class="small">'+artLinks(fp.a)+'</td><td class="small">'+(esc(fp.g)||'–')+'</td><td class="small">'+fp.src+'</td>'+
   (SHOW_EL?'<td class="small">'+(fp.el||'–')+'</td>':'')+'</tr>';
}
window.WTLED=function(d){
  var s=byTitle[d.art];
  var h='<h2>'+esc(d.art)+'</h2><p class="small"><a href="articles/'+esc(s)+'.html">Article page</a> · '+d.ed.length+
    ' editors with at least 1% of the text, or sanctioned by Wikipedia. '+(d.rest[0]?d.rest[0].toLocaleString()+' other editors wrote the remaining '+(d.rest[1]*100).toFixed(0)+'% between them, each under 1%.':'')+'</p>';
  h+=head('Share of this article')+d.ed.map(function(x){return row(x[0],x[2],x[1]);}).join('')+'</table></div>';
  out.innerHTML=h;
};
window.WTLID=function(c,d){idc[c]=d; if(want&&want[0]===c) showId(want);};
function showId(id){
  var d=idc[id[0]];
  if(!d){want=id;load('data/editors/id/'+id[0]+'.js');out.innerHTML='<p class="small">Loading…</p>';return;}
  want=null;
  var fp=d[id];
  out.innerHTML=fp?'<h2>Pattern ID '+id+'</h2>'+head('')+row(id,fp)+'</table></div>':'<p>No editor with pattern ID '+esc(id)+' in the analysed articles.</p>';
}
function route(){
  var m=location.hash.match(/^#(a|id)=(.+)$/);
  if(!m){return;}
  var v=decodeURIComponent(m[2]);
  if(m[1]==='a'){ if(!bySlug[v]){out.innerHTML='<p>Not an analysed article.</p>';return;}
    document.getElementById('art').value=bySlug[v]; out.innerHTML='<p class="small">Loading…</p>'; load('data/editors/a/'+v+'.js');}
  else{ document.getElementById('pid').value=v; showId(v.toUpperCase()); }
}
document.getElementById('art').addEventListener('change',function(){var s=byTitle[this.value];if(s)location.hash='a='+encodeURIComponent(s);});
document.getElementById('pid').addEventListener('change',function(){var v=this.value.trim().toUpperCase();if(v)location.hash='id='+v;});
window.addEventListener('hashchange',route); route();
})();
</script>
"""


def editor_lookup_page(ctx: Context):
    pt = ctx.patterns
    rule = pt["rule"]
    arts = sorted(r["article"] for r in ctx.recs)
    opts = "".join(f"<option value='{escape(a, quote=True)}'>" for a in arts)
    h = ["<h1>Look up an editor</h1>",
         "<p class='lede'>Pick an article to see every editor who wrote at least 1% of it, and "
         "what else each of them wrote among the articles we analysed. Or type a pattern ID "
         "(the code we use instead of an editor's name).</p>",
         note(EDITORS_NOTE, "About these IDs"), FT_CSS,
         "<div class='pick'><label>Article<br><input id='art' list='arts' placeholder='Start typing a title' "
         "autocomplete='off'></label><label>Pattern ID<br><input id='pid' placeholder='for example K7Q2MX' "
         f"autocomplete='off' maxlength='6'></label></div><datalist id='arts'>{opts}</datalist>",
         "<div id='out'><p class='small'>Nothing chosen yet. "
         f"{link('editors.html', 'The overview')} lists the editors who wrote in the most "
         "articles.</p></div>",
         f"<p class='small'>Based on the {num(rule['articles_analysed'])} articles analysed so far, so an "
         "editor's work on other articles is not counted. <b>Share</b>: the range their words make up "
         "of the article's current text. <b>Sources</b>: every citation the editor added that is "
         "still in an analysed article, described with the same ratings as the Sources page; "
         "counts and shares are ranges. The same rules apply to every editor.</p>"]
    if not rule.get("elsewhere"):
        h.append("<p class='small'>Where each editor edits across the rest of Wikipedia is not "
                 "included yet.</p>")
    else:
        who = (f"a sample: the {rule['elsewhere_sample']} registered editors with the most words in "
               f"each area's analysed articles ({num(rule.get('elsewhere_editors', 0))} editors); "
               "“–” for everyone else" if rule.get("elsewhere_sample") else "every editor listed")
        h.append("<p class='small'><b>Where they edit across Wikipedia</b> is shown for "
                 f"{who}. We take the editor's last {num(rule['edit_cap'])} edits to articles and "
                 "count how many went to articles in each contentious topic that Wikipedia marks. "
                 "An edit to an article marked with two topics counts in both. Subjects we chose "
                 "ourselves (see Which articles) are not counted here yet.</p>")
    js = (LOOKUP_JS.replace("__ARTS__", json.dumps([[a, slug(a)] for a in arts], ensure_ascii=False)
                            .replace("</", "<\\/"))
          .replace("__EL__", "true" if rule.get("elsewhere") else "false"))
    h.append(js)
    return page(f"Look up an editor · {NAME}", "".join(h), "editor.html",
                description="Each editor of an analysed article, and their pattern across the others.")


LEAN_NAMES = {"audience_leaning_dd": "Audience leaning (DomainDemo, Yang et al. 2025)",
              "audience_leaning": "Audience leaning (Robertson et al. 2018)",
              "academic_level": "Academic level (JUFO, 0 to 3)",
              "affiliation": "Recorded political affiliation (Wikidata, Wikipedia categories)",
              "mbfc": "Media Bias/Fact Check bias label", "allsides_2018": "AllSides (2018) label",
              "independent_quality": "Independent quality (Lin et al.)",
              "wikipedia_rating": "Wikipedia's rating"}


LEAN_FIELDS = ("audience_leaning_dd", "audience_leaning", "mbfc", "allsides_2018", "affiliation")


def label_order(f, mix):
    """Labels of a mix in display order: the rater's own scale; otherwise largest first,
    leaving out labels under half a percent."""
    from .patterns import LEAN_LABELS
    if f in LEAN_LABELS:
        return [l for l in LEAN_LABELS[f] if mix.get(l)]
    return [l for l, v in sorted(mix.items(), key=lambda x: (-x[1], x[0])) if v >= 0.005]


def baseline_leaning(ctx) -> dict:
    """Mean audience leaning per rated citation across all analysed articles, per scale."""
    from .patterns import _rated
    out = {}
    for f in ("audience_leaning_dd", "audience_leaning"):
        acc = cov = 0
        for r in ctx.recs:
            for x in (r.get("sources") or {}).get("list", []):
                v = _rated(ctx.outlets.get(x["source"]) or {}).get(f)
                if v is not None:
                    acc += v * x["citations"]
                    cov += x["citations"]
        if cov:
            out[f] = round(acc / cov, 3)
    return out


def cited_figures(rec, ctx) -> dict:
    """Each rater's figure for the sources the article itself cites, in the same shape as the
    writers' figures: a citation-weighted mean or mix, and the share of citations rated."""
    from . import patterns as pm
    s = rec.get("sources") or {}
    tot = sum(x["citations"] for x in s.get("list", []))
    num_, lab = {}, {}
    for x in s.get("list", []):
        n = x["citations"]
        for f, v in pm._rated(ctx.outlets.get(x["source"]) or {}).items():
            if isinstance(v, (int, float)):
                t = num_.setdefault(f, [0.0, 0])
                t[0] += v * n
                t[1] += n
            else:   # a label, or several labels sharing the citation equally
                vs = v if isinstance(v, list) else [v]
                for x in vs:
                    lab.setdefault(f, {}).setdefault(x, 0)
                    lab[f][x] += n / len(vs)
    out = {f: {"mean": round(t[0] / t[1], 3), "citations_covered": round(t[1] / tot, 4)}
           for f, t in num_.items() if t[1]}
    for f, c in lab.items():
        k = sum(c.values())
        out[f] = {"mix": {a: round(b / k, 4) for a, b in c.items()}, "citations_covered": round(k / tot, 4)}
    return out


def writers_section(rec, ctx):
    """Article page: the sources this article cites beside the sources its writers cite."""
    w = ((ctx.patterns or {}).get("by_article", {}).get(rec["article"]) or {}).get("writers")
    if not w or not ctx.outlets:
        return ""
    c = cited_figures(rec, ctx)
    ms = ctx.patterns["rule"]["min_scored"]
    rows = []
    for f in LEAN_FIELDS:
        a, b = c.get(f), w.get(f)
        if not a and not b:
            continue
        def val(x):
            if not x:
                return "–"
            if "mean" in x:
                return f"{x['mean']:+.2f}"
            from .patterns import LEAN_LABELS
            return "; ".join(f"{escape(l)} {p0(x['mix'].get(l, 0))}" for l in label_order(f, x["mix"]))
        rows.append(f"<tr><td>{escape(LEAN_NAMES[f])}</td><td class='small'>{val(a)}"
                    + (f"<div class='small'>{p0(a['citations_covered'])} of citations rated</div>" if a else "")
                    + f"</td><td class='small'>{val(b)}"
                    + (f"<div class='small'>writers of {p0(b['text_covered'])} of the text, "
                       f"{num(b['writers'])} editors</div>" if b else "") + "</td></tr>")
    if not rows:
        return ""
    return ("<h3>The sources this article cites, and the sources its writers cite</h3>"
            "<p class='small'>Left: the article's own citations. Right: every citation the "
            "article's editors added across all the analysed articles, with each editor counted "
            "in proportion to their share of this article's text. An editor counts only with at "
            f"least {ms} citations rated by that rater, and no single editor's figure is "
            f"published ({link('../leaning-detail.html#method', 'method')}). Each rater's own scale; nothing is "
            "combined. Audience leaning runs from −1 to +1 and describes who shares a site, not "
            f"what it publishes. {link('../leaning.html', 'All articles ranked')}.</p>"
            "<div class='scroll'><table><tr><th>Rater</th><th>Cited in this article</th>"
            "<th>Cited by its writers</th></tr>" + "".join(rows) + "</table></div>")


LEAN_JS = r"""
<script>
(function(){
var D=__DATA__, AREAS=__AREAS__, LBL=__LBL__;
var sel=document.getElementById('ar'), as=document.getElementById('as'), out=document.getElementById('lt');
var sortCol=null, sortDir=-1;
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function pc(x){return x==null?'–':Math.round(x*100)+'%';}
function cols(f){
  if(f.indexOf('audience_leaning')===0){return [['c','Cited in the article',function(r){var x=r.c[f];return x?x.mean:null;},function(r){var x=r.c[f];return x?(x.mean>=0?'+':'')+x.mean.toFixed(2)+'<div class="small">'+pc(x.citations_covered)+' of citations</div>':'–';}],
    ['w','Cited by its writers',function(r){var x=r.w[f];return x?x.mean:null;},function(r){var x=r.w[f];return x?(x.mean>=0?'+':'')+x.mean.toFixed(2)+'<div class="small">'+pc(x.text_covered)+' of text</div>':'–';}]];}
  var c=[];
  ['c','w'].forEach(function(side){LBL[f].forEach(function(l){
    c.push([side+l,(side==='c'?'Cited: ':'Writers: ')+l,function(r){var x=r[side][f];return x?(x.mix[l]||0):null;},function(r){var x=r[side][f];return x?pc(x.mix[l]||0):'–';}]);});
    c.push([side+'cov',side==='c'?'Cited: citations rated':'Writers: text covered',function(r){var x=r[side][f];return x?(side==='c'?x.citations_covered:x.text_covered):null;},function(r){var x=r[side][f];return x?pc(side==='c'?x.citations_covered:x.text_covered):'–';}]);});
  return c;
}
function draw(){
  var f=as.value, a=sel.value, C=cols(f);
  var rows=D.filter(function(r){return a==='*'||r.ar===a;});
  if(sortCol!==null){var g=C[sortCol][2];rows.sort(function(x,y){var p=g(x),q=g(y);if(p==null)return 1;if(q==null)return -1;return (p-q)*sortDir;});}
  var h='<p class="small">'+rows.length+' articles. Choose a column heading to rank by it; choose again to reverse.</p><div class="ft"><table><tr><th>Article</th><th>Kind</th>'+
    C.map(function(c,i){return '<th class="n" data-i="'+i+'" style="cursor:pointer">'+esc(c[1])+(sortCol===i?(sortDir<0?' ▼':' ▲'):'')+'</th>';}).join('')+'</tr>';
  rows.forEach(function(r){h+='<tr><td><a href="articles/'+esc(r.s)+'.html">'+esc(r.t)+'</a>'+(a==='*'?'<div class="small">'+esc(AREAS[r.ar]||'')+'</div>':'')+'</td><td class="small">'+esc(r.k)+'</td>'+C.map(function(c){return '<td class="n">'+c[3](r)+'</td>';}).join('')+'</tr>';});
  out.innerHTML=h+'</table></div>';
  Array.prototype.forEach.call(out.querySelectorAll('th[data-i]'),function(th){th.onclick=function(){var i=+th.getAttribute('data-i');if(sortCol===i)sortDir=-sortDir;else{sortCol=i;sortDir=-1;}draw();};});
}
sel.onchange=draw; as.onchange=function(){sortCol=null;draw();}; draw();
})();
</script>
"""


def affiliation_note(ctx) -> str:
    """How recorded affiliation is drawn, and how many cited sources carry each label, by where
    it is recorded, so the balance of the records themselves can be seen."""
    from collections import Counter
    from .affiliation import NONE, NO_ENTRY, category_labels
    cited = Counter()
    for r in ctx.recs:
        for x in (r.get("sources") or {}).get("list", []):
            cited[x["source"]] += x["citations"]
    wd, cat, cit = Counter(), Counter(), Counter()
    for k, n in cited.items():
        a = (ctx.outlets.get(k) or {}).get("affiliation")
        if not a:
            continue
        for l in a["wikidata"]:
            wd[l] += 1
        for l in category_labels(a["wikipedia_categories"]):
            cat[l] += 1
        for l in a["labels"]:
            cit[l] += n
    if not cit:
        return ""
    labels = [l for l, _ in cit.most_common() if l not in (NONE, NO_ENTRY)][:16]
    from .affiliation import show
    rows = "".join(f"<tr><td>{escape(show(l))}</td><td class='n'>{num(wd[l])}</td><td class='n'>{num(cat[l])}</td>"
                   f"<td class='n'>{num(round(cit[l]))}</td></tr>" for l in labels)
    total = sum(cited.values())
    return ("<h2 id='affiliation'>Recorded political affiliation</h2>"
            "<p>This is a different measure from audience leaning. It is what Wikipedia and "
            "Wikidata already say about a publisher's own politics. Unlike audience leaning, it "
            "covers books as well as websites.</p><ul>"
            "<li><b>Where it comes from.</b> Wikidata's “political alignment” and “ideology” "
            "fields, and the category tags at the bottom of the publisher's own Wikipedia "
            "article, when the tag calls it a political publisher or state media (for example "
            "“Left-wing book publishing companies” or “Conservative media in Israel”). Tags "
            "about a subject, such as “Liberalism in Israel”, are not used.</li>"
            "<li><b>Labels are kept as written.</b> We only join word forms (conservatism and "
            "conservative). We never merge one label into another, because words like "
            "“liberal” mean different things in different countries.</li>"
            "<li><b>“None recorded”</b> means there is a record but it says nothing about "
            "politics, which is true of most university presses and big publishers. <b>“No "
            "entry”</b> means there is no record at all.</li>"
            "<li>A footnote whose publisher has two labels counts half for each.</li></ul>"
            "<p class='small'>These records are written by volunteer editors. They are fuller for "
            "English-language publishers than for others. The table shows how many cited sources "
            "carry each label, and where it was recorded, so you can see how balanced the "
            "records themselves are.</p>"
            "<div class='scroll'><table><tr><th>Label</th><th class='n'>Sources (Wikidata)</th>"
            "<th class='n'>Sources (Wikipedia categories)</th><th class='n'>Citations, all "
            f"analysed articles (of {num(total)})</th></tr>{rows}</table></div>")


def leaning_page(ctx: Context):
    from .patterns import LEAN_LABELS
    by = (ctx.patterns or {}).get("by_article", {})
    rows = []
    for r in ctx.recs:
        a = r["article"]
        rows.append({"t": a, "s": slug(a), "ar": ctx.areas.get(a, "") or "",
                     "k": kind_name(ctx.kinds.get(a) or "", plural=False),
                     "c": {f: v for f, v in cited_figures(r, ctx).items() if f in LEAN_FIELDS},
                     "w": {f: v for f, v in ((by.get(a) or {}).get("writers") or {}).items()
                           if f in LEAN_FIELDS}})
    from collections import Counter
    from .affiliation import NONE, NO_ENTRY
    tot_aff = Counter()
    for r in rows:
        for x in ((r["c"].get("affiliation") or {}).get("mix") or {}).items():
            tot_aff[x[0]] += x[1]
    aff_cols = [l for l, _ in tot_aff.most_common() if l not in (NONE, NO_ENTRY)][:8] + [NONE, NO_ENTRY]
    bl = baseline_leaning(ctx)
    base = ("<p class='small'>For reference: across all " + num(len(ctx.recs)) + " analysed "
            "articles, the mean audience leaning per rated citation is "
            + "; ".join(f"{bl[f]:+.2f} on {LEAN_NAMES[f].split('(')[1].rstrip(')')}" for f in bl)
            + ". Compare an article with these, not with zero.</p>") if bl else ""
    order = _area_order(ctx)
    opts = "<option value='*'>All areas</option>" + "".join(
        f"<option value='{escape(a, quote=True)}'{' selected' if i == 0 else ''}>{escape(area_name(a))}</option>"
        for i, a in enumerate(order))
    ms = (ctx.patterns or {}).get("rule", {}).get("min_scored", 5)
    h = ["<h1>Leaning of the sources, by article</h1>",
         "<p class='lede'>Two figures for each article, on each rater's own scale: the sources "
         "the article cites, and the sources its writers cite across all the analysed articles. "
         "Rank the articles by either. This page defines the figures and draws no conclusions "
         "from them.</p>",
         note("These are other organisations' ratings of the cited sources, applied as they are. "
              "Audience leaning (−1 to +1) describes who shares a site on social media, not what "
              "it publishes; there are two measures, from two panels of US Twitter users matched "
              "to voter records (DomainDemo, 2011–2022, about 129,000 sites; Robertson et al. "
              "2018, about 19,000 sites). They agree closely on the order of sites (correlation "
              "0.92 on the sites cited here), but on neither is zero a political centre: most "
              "sites, including those Media Bias/Fact Check calls least biased, fall below zero. "
              "These ratings are for websites: they are not applied to books, journals, "
              "publishers or sites that host scholarly papers, which no open dataset rates for "
              "leaning. Media Bias/Fact Check and AllSides labels are each organisation's own "
              "judgement. Many sources are rated by none of them, so each figure gives the share it "
              "covers. A writer's figure describes the sources that editor cited, not the editor's "
              "views.", "Read with care"),
         "<ul class='small'><li><b>Cited in the article</b>: each rated citation in the article, "
         "counted once; a mean for audience leaning, the share of each label for the others.</li>"
         "<li><b>Cited by its writers</b>: the sources the article's writers cite everywhere in the "
         "analysed articles, blended by how much of this article each of them wrote. "
         "<a href='#method'>How it is worked out</a>.</li></ul>",
         base, FT_CSS,
         "<div class='pick'><label>Area<br><select id='ar'>" + opts + "</select></label>"
         "<label>Rater<br><select id='as'><option value='audience_leaning_dd'>Audience leaning "
         "(DomainDemo 2025)</option><option value='audience_leaning'>Audience leaning "
         "(Robertson et al. 2018)</option><option value='mbfc'>Media Bias/Fact Check label</option>"
         "<option value='allsides_2018'>AllSides (2018) label</option>"
         "<option value='affiliation'>Recorded political affiliation</option></select></label></div>",
         "<style>.pick select{width:100%;font-size:1rem;padding:8px;border:1px solid var(--line);"
         "border-radius:6px;background:var(--bg);color:var(--fg)}</style>",
         "<div id='lt'></div>",
         affiliation_note(ctx),
         "<h2 id='method'>How the writers' figure is worked out</h2><ol>"
         "<li><b>Each editor's sources.</b> For every editor with text in an analysed article, all "
         "the citations that editor added that are still in the text of any analysed article are "
         "collected, not only those in the one article. Each citation is rated with the rater's "
         "ratings of its source, exactly as for the article's own citations.</li>"
         "<li><b>Each editor's figure.</b> From those citations: the mean for audience leaning, or "
         "the share of each label for Media Bias/Fact Check and AllSides. An editor gets a figure "
         f"only with at least {ms} citations rated by that rater. These figures are worked out "
         "but not published: no editor's own figure appears on this site, on the editor look-up "
         "page or in the downloadable data.</li>"
         "<li><b>The article's figure.</b> The editors' figures are averaged, each weighted by the "
         "number of words of this article's current text that editor wrote. An editor who wrote 40% "
         "of the text counts four times as much as one who wrote 10%. Editors without a figure "
         "are left out, and <i>text covered</i> gives the share of the article's words written "
         "by the editors who are counted.</li></ol>"
         "<p class='small'>Who wrote which words, and who added which footnote, comes from WikiWho "
         "(the word-tracking tool described on How it works). Each editor's own figure stays on "
         "the computer that builds this site, so the article figures can be checked, but it is "
         "never published.</p>",
         "<h3 id='limits'>Limits of this figure</h3><ul>"
         "<li><b>Only the analysed articles.</b> An editor's figure uses the citations they added "
         f"in the {num(len(ctx.recs))} analysed articles, not everything they have written on "
         "Wikipedia. An editor who writes mostly elsewhere is described by a small part of "
         "their work.</li>"
         "<li><b>Only citations still there.</b> Citations an editor added that were later removed "
         "are not counted, so the figure describes what survives, not what was added.</li>"
         "<li><b>Who placed a citation.</b> The editor credited with a citation is the one whose "
         "words make up its text. Citations moved, reformatted or restored after a revert can be "
         "credited to the editor who did that.</li>"
         "<li><b>Rated sources only.</b> Many sources have no rating from a given rater; their "
         f"citations are left out. Editors with fewer than {ms} rated citations are left out "
         "altogether, and <i>text covered</i> shows how much of the article the figure speaks for. "
         "A low share means the figure describes a small part of the writing.</li>"
         "<li><b>Websites only.</b> Leaning ratings exist for websites. Books, journals and "
         "scholarly papers are not rated, so for an article that rests mostly on books the "
         "figure describes only the part of its sourcing that is on the web; the share of "
         "citations rated shows how large that part is.</li>"
         "<li><b>One main writer.</b> Where one editor wrote most of an article, the article's "
         "figure is close to that editor's own.</li>"
         "<li><b>Unregistered editors.</b> Text from an IP address is counted as one editor per "
         "address. One person can use several addresses, and several people one address.</li>"
         "<li><b>The raters' own scales.</b> Each figure is only as good as the ratings it "
         "applies. Audience leaning describes who shares a site on social media, not what it "
         "publishes, and most large news outlets fall below zero on it; compare an article with "
         "the reference figure above, not with zero. Media Bias/Fact Check and AllSides labels "
         "are each organisation's own judgement, and the AllSides labels date from 2018.</li>"
         "<li><b>Not the editor's views.</b> The figure describes the sources editors cite, which "
         "follow from what sources exist on a subject and what Wikipedia's rules allow, as well "
         "as from editors' choices.</li></ul>"]
    js = (LEAN_JS.replace("__DATA__", json.dumps(rows, ensure_ascii=False).replace("</", "<\\/"))
          .replace("__AREAS__", json.dumps({a: area_name(a) for a in order}, ensure_ascii=False))
          .replace("__LBL__", json.dumps({**{k: list(v) for k, v in LEAN_LABELS.items()},
                                          "affiliation": aff_cols})))
    h.append(js)
    return page(f"Leaning of the sources · {NAME}", "".join(h), "leaning.html",
                description="Articles ranked by the leaning ratings of the sources they cite and their writers cite.")


def editors_page(ctx: Context):
    """The overview: a fixed set of summary tables across all analysed articles."""
    from collections import Counter
    from .candidates import AREAS
    pt = ctx.patterns
    rule = pt["rule"]
    eds = pt["editors"]
    def lk(i):
        return f"<code><a href='editor.html#id={i}'>{i}</a></code>"
    subst = [e for e in eds if e["articles_substantial"] >= 1]
    sanc = [e for e in eds if e["sanctioned"]]
    h = ["<h1>Editors across articles: overview</h1>",
         "<p class='lede'>How the writing of the analysed articles is spread across editors. Each "
         "figure counts individual editors. This page shows the data and draws no conclusions "
         f"from it. To see one article's editors, or one editor, use {link('editor.html', 'Look up an editor')}.</p>",
         note(EDITORS_NOTE, "About these IDs"), FT_CSS]
    many = Counter()
    bins = [(1, 1, "1"), (2, 2, "2"), (3, 4, "3–4"), (5, 9, "5–9"), (10, 19, "10–19"), (20, 10**9, "20 or more")]
    for e in subst:
        n = e["articles_substantial"]
        many[next(lbl for lo, hi, lbl in bins if lo <= n <= hi)] += 1
    h.append("<div class='fig'>"
             f"<div class='box'><div class='num'>{num(len(subst))}</div><div class='lbl'>editors wrote at least 1% of at least one analysed article</div></div>"
             f"<div class='box'><div class='num'>{num(sum(1 for e in subst if e['articles_substantial'] >= 2))}</div><div class='lbl'>did so in two or more</div></div>"
             f"<div class='box'><div class='num'>{num(len(sanc))}</div><div class='lbl'>editors Wikipedia has sanctioned have text in an analysed article</div></div>"
             "</div>")
    h.append("<h2>In how many articles each editor wrote at least 1%</h2>"
             "<div class='scroll'><table><tr><th>Analysed articles</th><th class='n'>Editors</th></tr>"
             + "".join(f"<tr><td>{lbl}</td><td class='n'>{num(many[lbl])}</td></tr>" for _, _, lbl in bins)
             + "</table></div>")
    # by area: editors with >=1% there, and how many of them also wrote >=1% in another area
    area_of = ctx.areas
    h.append("<h2>By topic area</h2><p>For each topic: how many editors wrote at least 1% of one of "
             "its articles, how many of them did so in two or more of its articles, and how many "
             "also did so in another topic.</p>"
             "<div class='scroll'><table><tr><th>Area</th><th class='n'>Articles</th>"
             "<th class='n'>Editors</th><th class='n'>In 2 or more of its articles</th>"
             "<th class='n'>Also in another area</th><th class='n'>Of them sanctioned</th></tr>")
    per_area = {}
    for e in subst:
        ar = Counter(area_of.get(a, "") for a, v in e["shares"].items() if v != "under 1%")
        for a, n in ar.items():
            x = per_area.setdefault(a, [0, 0, 0, 0])
            x[0] += 1
            x[1] += n >= 2
            x[2] += len(ar) >= 2
            x[3] += e["sanctioned"]
    art_n = Counter(area_of.get(r["article"], "") for r in ctx.recs)
    for a in _area_order(ctx):
        x = per_area.get(a)
        if x:
            h.append(f"<tr><td>{escape(area_name(a))}</td><td class='n'>{num(art_n[a])}</td>"
                     f"<td class='n'>{num(x[0])}</td><td class='n'>{num(x[1])}</td>"
                     f"<td class='n'>{num(x[2])}</td><td class='n'>{num(x[3])}</td></tr>")
    h.append("</table></div>")
    def table(rows):
        t = ["<div class='ft'><table><tr><th>Pattern ID</th><th class='n'>Articles with at least 1%</th>"
             "<th>Sanctioned</th><th>Topic groups of those articles</th><th>Sources they cited</th></tr>"]
        for e in rows:
            g = "; ".join(f"{n} of the {m} analysed articles in {escape(gr)}" for gr, (n, m) in e["topics"].items()) or "–"
            t.append(f"<tr><td>{lk(e['id'])}</td><td class='n'>{e['articles_substantial']}</td>"
                     f"<td class='small'>{'yes' + (' (' + escape(', '.join(e['types'])) + ')' if e['types'] else '') if e['sanctioned'] else 'no'}</td>"
                     f"<td class='small'>{g}</td><td class='small'>{_ed_src(e.get('sources'))}</td></tr>")
        t.append("</table></div>")
        return "".join(t)
    top = sorted(subst, key=lambda e: (-e["articles_substantial"], e["id"]))[:40]
    h.append("<h2>The 40 editors with the most articles</h2><p>Editors who wrote at least 1% of "
             "the most analysed articles. Choose a pattern ID to see the articles.</p>" + table(top))
    st = sorted(sanc, key=lambda e: (-e["articles_substantial"], -e["articles_with_text"], e["id"]))
    types = Counter(t for e in sanc for t in e["types"])
    h.append(f"<h2>Editors Wikipedia has sanctioned ({num(len(sanc))})</h2><p>Topic bans, site bans "
             "and sockpuppetry findings: " + "; ".join(f"{escape(k)} {num(v)}" for k, v in types.most_common())
             + ". An editor can have more than one. The 40 with the most articles:</p>" + table(st[:40]))
    h.append(f"<p class='small'>Based on the {num(rule['articles_analysed'])} articles analysed so "
             "far, so an editor's work on other articles is not counted. The same rules apply to "
             f"every editor. {link('editor.html', 'Look up any article or editor')}.</p>")
    return page(f"Editors across articles · {NAME}", "".join(h), "editors.html",
                description="How the writing of the analysed articles is spread across editors.")



# ---------------------------------------------------------------- home
SEARCH_FORM = ("<form class='sf' action='{up}search.html' method='get' role='search'>"
               "<input name='q' type='search' placeholder='Search a topic, article, source or pattern ID' "
               "aria-label='Search' autocomplete='off'{auto}><button type='submit'>Search</button></form>")
SEARCH_CSS = ("<style>.sf{display:flex;gap:8px;margin:14px 0}.sf input{flex:1;min-width:0;font-size:1.05rem;"
              "padding:10px 12px;border:1px solid var(--line);border-radius:6px;background:var(--bg);"
              "color:var(--fg)}.sf button{font-size:1rem;padding:8px 16px;border:1px solid var(--line);"
              "border-radius:6px;background:var(--soft);color:var(--fg);cursor:pointer}"
              ".hit{padding:8px 0;border-bottom:1px solid var(--line)}.hit .small a{margin-right:10px}</style>")


def search_index(ctx: Context) -> dict:
    """Everything the search page can find, as compact lists: analysed articles, queued
    articles, areas, cited sources (with the analysed articles that cite them most), pages."""
    from collections import Counter
    arts = sorted(ctx.recs, key=lambda r: r["article"])
    idx = {r["article"]: i for i, r in enumerate(arts)}
    A = [[r["article"], slug(r["article"]), ctx.areas.get(r["article"], "") or "",
          kind_name(ctx.kinds.get(r["article"]) or "", plural=False)] for r in arts]
    lists = {}
    for c in ctx.candidates:
        lists.setdefault(c["title"], []).append(c["area"])
    for a in A:   # every area list an analysed article is on, not only the one it is shown under
        a.append(sorted(set(lists.get(a[0], [])) - {a[2]}))
    Q = sorted([t, sorted(set(ars))] for t, ars in lists.items() if t not in idx)
    per_src, n_art = {}, Counter()
    for r in arts:
        for x in (r.get("sources") or {}).get("list", []):
            per_src.setdefault(x["source"], []).append((x["citations"], idx[r["article"]]))
            n_art[x["source"]] += 1
    S = []
    for k, lst in per_src.items():
        if len(lst) < 2:   # sources cited in a single analysed article are left out of the index
            continue
        nm = src_name(k, ctx)
        dom = "" if k.startswith("name:") or " " in k or nm == k else k
        top = [i for _, i in sorted(lst, key=lambda x: (-x[0], x[1]))[:6]]
        S.append([nm, dom, len(lst), sum(c for c, _ in lst), top])
    S.sort(key=lambda x: (-x[2], x[0]))
    R = {a: area_name(a) for a in _area_order(ctx)}
    P = [[h, n] for h, n in PAGES if h != "search.html"]
    return {"A": A, "Q": Q, "S": S, "R": R, "P": P}


SEARCH_JS = r"""
<script>
(function(){
var A=WTLS.A,Q=WTLS.Q,S=WTLS.S,R=WTLS.R,P=WTLS.P;
var box=document.getElementById('q'),out=document.getElementById('res');
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function norm(s){return String(s).normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/[‐-―\-_]/g,' ').replace(/[^\w\s.+]/g,' ').replace(/\s+/g,' ').trim();}
function prep(list,f){return list.map(function(x){return norm(f(x));});}
var nA=prep(A,function(a){return a[0];}),nQ=prep(Q,function(q){return q[0];}),nS=prep(S,function(s){return s[0]+' '+s[1];});
var nR={};Object.keys(R).forEach(function(k){nR[k]=norm(R[k]);});
function score(t,q,toks){
  if(t===q)return 0; if(t.indexOf(q)===0)return 1;
  for(var i=0;i<toks.length;i++){if(t.indexOf(toks[i])<0)return -1;}
  return (' '+t).indexOf(' '+toks[0])>=0?2:3;}
function find(n,q,toks,max){var r=[];for(var i=0;i<n.length;i++){var s=score(n[i],q,toks);if(s>=0)r.push([s,n[i].length,i]);}
  r.sort(function(a,b){return a[0]-b[0]||a[1]-b[1]||a[2]-b[2];});return [r.length,r.slice(0,max).map(function(x){return x[2];})];}
function wp(t){return 'https://en.wikipedia.org/wiki/'+encodeURIComponent(t.replace(/ /g,'_'));}
function arts(i){var a=A[i];return '<a href="articles/'+esc(a[1])+'.html">'+esc(a[0])+'</a>';}
function sec(title,n,shown,body){return body?'<h2>'+esc(title)+' <span class="small">('+n+(n>shown?', first '+shown+' shown':'')+')</span></h2>'+body:'';}
function run(){
  var raw=box.value.trim(),q=norm(raw),h='';
  try{history.replaceState(null,'',raw?'?q='+encodeURIComponent(raw):location.pathname);}catch(e){}
  if(!q){out.innerHTML='<p class="small">Type a topic (for example Gaza, Tiananmen, abortion), an article title, a source (for example Al Jazeera or nytimes.com) or a pattern ID.</p>';return;}
  var toks=q.split(' ');
  if(/^[A-Z0-9]{6}$/.test(raw)||(/^[a-z0-9]{6}$/i.test(raw)&&/[0-9]/.test(raw))){h+='<h2>Pattern ID</h2><div class="hit"><a href="editor.html#id='+esc(raw.toUpperCase())+'">Look up editor '+esc(raw.toUpperCase())+'</a> <span class="small">(shown if this ID belongs to an editor listed for an analysed article)</span></div>';}
  var ar=Object.keys(R).filter(function(k){return score(nR[k],q,toks)>=0;});
  h+=sec('Topic areas',ar.length,ar.length,ar.map(function(k){var n=A.filter(function(a){return a[2]===k;}).length;
    return '<div class="hit"><b>'+esc(R[k])+'</b><div class="small"><a href="compare.html#area-'+esc(k||'none')+'">'+n+' analysed articles and their figures</a><a href="articles-detail.html#list-'+esc(k)+'">the list and how it is chosen</a><a href="leaning.html">leaning of the sources</a></div></div>';}).join(''));
  var fa=find(nA,q,toks,60);
  h+=sec('Analysed articles',fa[0],fa[1].length,fa[1].map(function(i){var a=A[i];
    var also=a[4]&&a[4].length?'; also on the '+a[4].map(function(k){return esc(R[k]||k);}).join(', ')+' list':'';
    return '<div class="hit">'+arts(i)+' <span class="small">'+esc(a[3])+(a[2]?' · '+esc(R[a[2]]||a[2]):'')+also+'</span><div class="small"><a href="articles/'+esc(a[1])+'.html">report</a><a href="editor.html#a='+esc(a[1])+'">editors</a><a href="data/'+esc(a[1])+'.json">data (JSON)</a><a href="'+wp(a[0])+'">on Wikipedia</a></div></div>';}).join(''));
  var fq=find(nQ,q,toks,30);
  h+=sec('On a list, not analysed yet',fq[0],fq[1].length,fq[1].map(function(i){var x=Q[i];
    return '<div class="hit">'+esc(x[0])+' <span class="small">queued · '+x[1].map(function(k){return '<a href="articles-detail.html#list-'+esc(k)+'">'+esc(R[k]||k)+'</a>';}).join(', ')+' · <a href="'+wp(x[0])+'">on Wikipedia</a></span></div>';}).join(''));
  var fs=find(nS,q,toks,25);
  h+=sec('Cited sources',fs[0],fs[1].length,fs[1].map(function(i){var x=S[i];
    return '<div class="hit"><b>'+esc(x[0])+'</b>'+(x[1]?' <span class="small">'+esc(x[1])+'</span>':'')+'<div class="small">'+x[3].toLocaleString()+' citations in '+x[2].toLocaleString()+' analysed articles. Most cited in: '+x[4].map(arts).join(', ')+'</div></div>';}).join(''));
  var fp=P.filter(function(p){return score(norm(p[1]),q,toks)>=0;});
  h+=sec('Pages',fp.length,fp.length,fp.map(function(p){return '<div class="hit"><a href="'+esc(p[0])+'">'+esc(p[1])+'</a></div>';}).join(''));
  out.innerHTML=h||'<p>Nothing found for “'+esc(raw)+'”. Only analysed and listed articles, their cited sources and this site\'s pages are searched; the article may not be on a list yet.</p>';
}
var t=null;box.addEventListener('input',function(){clearTimeout(t);t=setTimeout(run,120);});
document.getElementById('sf').addEventListener('submit',function(e){e.preventDefault();run();});
var m=/[?&]q=([^&]*)/.exec(location.search);if(m){box.value=decodeURIComponent(m[1].replace(/\+/g,' '));}
run();box.focus();
})();
</script>
"""


def write_search_data(site_dir, ctx):
    (site_dir / "data" / "search.js").write_text(
        "var WTLS=" + json.dumps(search_index(ctx), ensure_ascii=False, separators=(",", ":"))
        .replace("</", "<\\/") + ";\n", encoding="utf-8")


# ---------------------------------------------------------------- word tracker (search page)
TRACK_CSS = """<style>
.trk{--t1:#2a78d6;--t2:#eb6834;--t3:#1baf7a;--t4:#eda100;--t5:#e87ba4;--t6:#8a63d2}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .trk{--t1:#3987e5;--t2:#d95926;--t3:#199e70;--t4:#c98500;--t5:#d55181;--t6:#9b7be0}}
:root[data-theme="dark"] .trk{--t1:#3987e5;--t2:#d95926;--t3:#199e70;--t4:#c98500;--t5:#d55181;--t6:#9b7be0}
.trk .chg button{font-size:.8rem;padding:2px 8px}
.trk .cmp2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
@media (max-width:700px){.trk .cmp2{grid-template-columns:1fr}}
.trk .cmp2>div{border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:.92rem}
.trk form{display:grid;gap:8px;grid-template-columns:1fr;max-width:640px}
.trk label{font-size:.88rem;color:var(--muted)}
.trk input,.trk select{font:inherit;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);width:100%;box-sizing:border-box}
.trk button{font:inherit;padding:6px 14px;border:1px solid var(--line);border-radius:6px;background:var(--soft);color:var(--fg);cursor:pointer;justify-self:start}
.trk .legend{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:.88rem;margin:8px 0}
.trk .legend span{display:inline-flex;align-items:center;gap:6px}
.trk .legend svg{flex:none}
.trk .chart{position:relative;margin:6px 0}
.trk svg.plot{width:100%;height:auto;display:block;overflow:visible}
.trk .grid line{stroke:var(--line);stroke-width:1}
.trk .axis text{fill:var(--muted);font-size:11px;font-family:system-ui,sans-serif}
.trk .end text{font-size:11px;font-family:system-ui,sans-serif;fill:var(--fg)}
.trk .tip{position:absolute;pointer-events:none;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:6px 8px;font-size:.82rem;box-shadow:0 2px 8px rgba(0,0,0,.12);display:none;white-space:nowrap;z-index:2}
.trk .status{font-size:.88rem;color:var(--muted);min-height:1.4em}
</style>"""

TRACK_HTML = """<h2 id='track'>Track words in an article over time</h2>
<p>Pick a Wikipedia article. We fetch it as it stood on 1 January and 1 July of each year and
count how often words appear, per 1,000 words of text. First we list the six words whose use
changed most between the first and the last version (three up, three down), picked by a fixed
statistical test. You can chart those, or up to six words or phrases of your own. A count only
says how often a word appears, not what the article says about it.</p>
<div class='trk'>
<form id='tf'>
<label for='ta'>Article title on English Wikipedia</label>
<input id='ta' name='ta' placeholder='for example: Zionism' autocomplete='off' required>
<label for='tw'>Words or phrases to chart, separated by commas (up to six; leave empty to chart the six that changed most)</label>
<input id='tw' name='tw' placeholder='for example: colonial, antisemitism, homeland' autocomplete='off'>
<label for='ty'>From the year</label>
<select id='ty'></select>
<button type='submit'>Track</button>
</form>
<p class='status' id='tstatus' aria-live='polite'></p>
<div id='tchg'></div>
<div id='tout'></div>
<div id='topen' hidden>
<h3>The opening on a date you choose</h3>
<p class='small'>The first paragraph as it read on the date you pick, next to the latest version.
<del class='d'>Struck through</del>: taken out since. <ins class='a'>Underlined</ins>: added since.</p>
<form id='of' class='sf'><label for='od' class='small'>Date</label> <input id='od' type='date' min='2002-01-01'>
<button type='submit'>Compare</button></form>
<div id='oout'></div>
</div>
</div>
<p class='small'>How it counts: footnotes, tables, templates and hidden notes are removed first, so
only the readable text is counted (roughly; a few template words may remain). Capitals do not
matter. A phrase matches whole words only, so “colonial” does not match “colonialism”: enter
both if you want both. <b>Words that changed most</b>: every word of three letters or more,
except common words such as “the” and “which”, that appears at least ten times in the first and
last versions together, ranked by a standard test of change in proportions (the log odds ratio
divided by its standard error), so a word going from 20 to 60 mentions counts for more than one
going from 1 to 3. The versions are fetched from Wikipedia by your browser when you press Track;
nothing is stored.</p>"""

TRACK_JS = r"""<script>
(function(){
const API='https://en.wikipedia.org/w/api.php';
const sel=document.getElementById('ty'), now=new Date().getFullYear();
for(let y=now-1;y>=2002;y--){const o=document.createElement('option');o.value=y;o.textContent=y;if(y===now-6)o.selected=true;sel.appendChild(o);}
const st=document.getElementById('tstatus'), out=document.getElementById('tout'), chg=document.getElementById('tchg');
const COLORS=['--t1','--t2','--t3','--t4','--t5','--t6'], DASH=['', '6 4', '2 3', '10 3 2 3', '1 5', '4 2 1 2'];
const STOP=new Set(('the and for that with was were are this from which who whom whose their they them his her its has have had not but also been being into than then there these those such other more most some any all each both after before between during while where when what about over under only one two three can could may might must should would will shall our out its it\'s per via upon onto within without among against through since until does did done many much very own same so too few new used use known called including include includes became become becomes made make makes said says say like well however although though because thus therefore whose whom whereas towards toward first second later early late part parts number').split(' '));
let STATE=null;
function strip(t){
  t=t.replace(/<!--[\s\S]*?-->/g,' ');
  t=t.replace(/<ref[^>]*\/>/gi,' ').replace(/<ref[^>]*>[\s\S]*?<\/ref\s*>/gi,' ');
  let prev;
  do{prev=t;t=t.replace(/\{\{[^{}]*\}\}/g,' ');}while(t!==prev);
  do{prev=t;t=t.replace(/\{\|[^]*?\|\}/g,' ');}while(t!==prev);
  t=t.replace(/\[\[(?:File|Image|Category):[^\[\]]*(?:\[\[[^\]]*\]\][^\[\]]*)*\]\]/gi,' ');
  t=t.replace(/\[\[(?:[^|\]]*\|)?([^\]]*)\]\]/g,'$1').replace(/\[https?:[^\s\]]+\s?([^\]]*)\]/g,'$1');
  t=t.replace(/<[^>]+>/g,' ').replace(/'{2,}/g,'').replace(/&[a-z]+;|&#x?[0-9a-f]+;/gi,' ');
  return t;
}
function prose(t){return strip(t).replace(/^=+.*?=+\s*$/gm,' ');}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function rx(p){return new RegExp('(?<![\\p{L}\\p{N}])'+p.trim().replace(/[.*+?^${}()|[\]\\]/g,'\\$&').replace(/\s+/g,'\\s+')+'(?![\\p{L}\\p{N}])','giu');}
async function at(title,date){
  const u=API+'?action=query&format=json&formatversion=2&origin=*&redirects=1&prop=revisions&rvlimit=1&rvdir=older&rvprop=ids|timestamp|content&rvslots=main&rvstart='+date+'T00:00:00Z&titles='+encodeURIComponent(title);
  const r=await fetch(u); const d=await r.json();
  const pg=(d.query&&d.query.pages&&d.query.pages[0])||{};
  if(pg.missing) throw new Error('missing');
  const rv=pg.revisions&&pg.revisions[0]; if(!rv) return null;
  return {title:pg.title, revid:rv.revid, ts:rv.timestamp, text:rv.slots.main.content||''};
}
function counts(txt){const c=new Map();let n=0;for(const w of (txt.toLowerCase().match(/[\p{L}][\p{L}'’-]*/gu)||[])){n++;if(w.length<3||STOP.has(w))continue;c.set(w,(c.get(w)||0)+1);}return {c,n};}
function topChanges(a,b){
  const A=counts(a), B=counts(b), out=[];
  const words=new Set([...A.c.keys(),...B.c.keys()]);
  for(const w of words){const x=A.c.get(w)||0, y=B.c.get(w)||0; if(x+y<10)continue;
    const lo=Math.log((y+.5)/(B.n-y+.5))-Math.log((x+.5)/(A.n-x+.5)), se=Math.sqrt(1/(x+.5)+1/(y+.5));
    out.push({w,x,y,z:lo/se,pa:x*1000/A.n,pb:y*1000/B.n});}
  const up=out.filter(o=>o.z>0).sort((p,q)=>q.z-p.z).slice(0,3), down=out.filter(o=>o.z<0).sort((p,q)=>p.z-q.z).slice(0,3);
  return up.concat(down);
}
function draw(title,phrases,rows){
  const W=720,H=300,L=44,R=110,T=12,B=28;
  const xs=rows.map(r=>new Date(r.date).getTime()), x0=Math.min(...xs), x1=Math.max(...xs);
  let ymax=0; rows.forEach(r=>r.per.forEach(v=>{if(v>ymax)ymax=v;}));
  const raw=(ymax>0?ymax:1)/4, mag=Math.pow(10,Math.floor(Math.log10(raw))), stepY=[1,2,2.5,5,10].map(f=>f*mag).find(f=>f>=raw);
  ymax=stepY*4;
  const X=t=>L+(x1>x0?(t-x0)/(x1-x0):0.5)*(W-L-R), Y=v=>T+(1-v/ymax)*(H-T-B);
  let g='<g class="grid">', ax='<g class="axis">';
  for(let i=0;i<=4;i++){const v=ymax*i/4, y=Y(v); g+=`<line x1="${L}" x2="${W-R}" y1="${y}" y2="${y}"/>`; ax+=`<text x="${L-6}" y="${y+4}" text-anchor="end">${+v.toFixed(2)}</text>`;}
  const y0=new Date(x0).getFullYear(), y1=new Date(x1).getFullYear(), step=Math.max(1,Math.ceil((y1-y0+1)/8));
  for(let y=y0;y<=y1;y+=step){const t=new Date(y+'-01-01').getTime(); if(t<x0||t>x1)continue; ax+=`<text x="${X(t)}" y="${H-8}" text-anchor="middle">${y}</text>`;}
  g+='</g>'; ax+='</g>';
  let lines='', ends='<g class="end">', lastY=[];
  phrases.forEach((p,i)=>{
    const pts=rows.map(r=>[X(new Date(r.date).getTime()),Y(r.per[i])]);
    lines+=`<polyline fill="none" stroke="var(${COLORS[i]})" stroke-width="2" stroke-linejoin="round" stroke-dasharray="${DASH[i]}" points="${pts.map(q=>q.join(',')).join(' ')}"/>`;
    pts.forEach(q=>{lines+=`<circle cx="${q[0]}" cy="${q[1]}" r="4" fill="var(${COLORS[i]})" stroke="var(--bg)" stroke-width="2"/>`;});
    let ly=pts[pts.length-1][1]; lastY.sort((m,n)=>m-n).forEach(o=>{if(Math.abs(o-ly)<13)ly=o+13;}); lastY.push(ly);
    ends+=`<text x="${W-R+8}" y="${ly+4}">${esc(p.length>16?p.slice(0,15)+'…':p)}</text>`;
  });
  ends+='</g>';
  const legend='<div class="legend">'+phrases.map((p,i)=>`<span><svg width="28" height="10" aria-hidden="true"><line x1="0" x2="28" y1="5" y2="5" stroke="var(${COLORS[i]})" stroke-width="2" stroke-dasharray="${DASH[i]}"/></svg>${esc(p)}</span>`).join('')+'</div>';
  let tbl='<details><summary>Table view, with a link to each version</summary><div class="scroll"><table><tr><th>Version</th><th class="n">Words</th>'+phrases.map(p=>`<th class="n">${esc(p)}<br><span class="small">per 1,000 (count)</span></th>`).join('')+'</tr>';
  rows.forEach(r=>{tbl+=`<tr><td><a href="https://en.wikipedia.org/w/index.php?oldid=${r.revid}">${r.date}</a></td><td class="n">${r.words.toLocaleString()}</td>`+r.per.map((v,i)=>`<td class="n">${v.toFixed(2)} (${r.n[i]})</td>`).join('')+'</tr>';});
  tbl+='</table></div></details>';
  out.innerHTML=`<h3>${esc(title)}: mentions per 1,000 words</h3>${legend}<div class="chart"><svg class="plot" viewBox="0 0 ${W} ${H}" role="img" aria-label="Mentions per 1,000 words over time; the table below has the same numbers">${g}${ax}${lines}${ends}<line class="xh" x1="0" x2="0" y1="${T}" y2="${H-B}" stroke="var(--muted)" stroke-width="1" visibility="hidden"/><rect x="${L}" y="${T}" width="${W-L-R}" height="${H-T-B}" fill="transparent" class="hit"/></svg><div class="tip"></div></div>${tbl}`;
  const svg=out.querySelector('svg'), tip=out.querySelector('.tip'), xh=out.querySelector('.xh'), hit=out.querySelector('.hit');
  function show(ev){
    const b=svg.getBoundingClientRect(), sx=(ev.clientX-b.left)*W/b.width;
    let k=0,best=1e9; rows.forEach((r,j)=>{const d=Math.abs(X(new Date(r.date).getTime())-sx); if(d<best){best=d;k=j;}});
    const r=rows[k], px=X(new Date(r.date).getTime());
    xh.setAttribute('x1',px);xh.setAttribute('x2',px);xh.setAttribute('visibility','visible');
    tip.innerHTML=`<b>${r.date}</b><br>`+phrases.map((p,i)=>`<span style="color:var(${COLORS[i]})">●</span> ${esc(p)}: ${r.per[i].toFixed(2)} (${r.n[i]})`).join('<br>');
    tip.style.display='block';
    const left=px*b.width/W; tip.style.left=Math.min(Math.max(0,left+12),b.width-tip.offsetWidth)+'px'; tip.style.top='8px';
  }
  hit.addEventListener('pointermove',show); hit.addEventListener('pointerleave',()=>{tip.style.display='none';xh.setAttribute('visibility','hidden');});
}
function chart(phrases){
  const res=phrases.map(rx);
  const rows=STATE.versions.map(v=>{const n=res.map(r=>(v.txt.match(r)||[]).length);return {date:v.date,revid:v.revid,words:v.words,n,per:n.map(c=>v.words?c*1000/v.words:0)};});
  draw(STATE.name,phrases,rows);
}
function showChanges(){
  const f=STATE.versions[0], l=STATE.versions[STATE.versions.length-1], tc=topChanges(f.txt,l.txt);
  STATE.top=tc.map(o=>o.w);
  if(!tc.length){chg.innerHTML='';return;}
  chg.innerHTML=`<h3>Words whose use changed most, ${f.date} to ${l.date}</h3><div class="scroll chg"><table><tr><th>Word</th><th class="n">Per 1,000 words then</th><th class="n">Now</th><th>Change</th><th></th></tr>`+
    tc.map(o=>`<tr><td>${esc(o.w)}</td><td class="n">${o.pa.toFixed(2)} (${o.x})</td><td class="n">${o.pb.toFixed(2)} (${o.y})</td><td>${o.z>0?'more often':'less often'}</td><td><button type="button" data-w="${esc(o.w)}">Chart</button></td></tr>`).join('')+'</table></div>';
  chg.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{
    const cur=document.getElementById('tw').value.split(',').map(s=>s.trim()).filter(Boolean);
    if(!cur.includes(b.dataset.w)){cur.push(b.dataset.w);} const list=cur.slice(-6);
    document.getElementById('tw').value=list.join(', '); chart(list);
  }));
}
document.getElementById('tf').addEventListener('submit',async e=>{
  e.preventDefault();
  const title=document.getElementById('ta').value.trim();
  let phrases=document.getElementById('tw').value.split(',').map(s=>s.trim()).filter(Boolean).slice(0,6);
  if(!title)return;
  history.replaceState(null,'','#track='+encodeURIComponent(title)+(phrases.length?'&w='+encodeURIComponent(phrases.join(',')):''));
  const y0=+sel.value, today=new Date().toISOString().slice(0,10), dates=[];
  for(let y=y0;y<=now;y++){for(const m of ['01-01','07-01']){const d=y+'-'+m; if(d<=today)dates.push(d);}}
  dates.push(today);
  const versions=[]; let name=title, lastRaw='';
  out.innerHTML=''; chg.innerHTML=''; document.getElementById('topen').hidden=true;
  try{
    for(let i=0;i<dates.length;i++){
      st.textContent=`Fetching version ${i+1} of ${dates.length}…`;
      const v=await at(title,dates[i]); if(!v)continue;
      name=v.title; lastRaw=v.text;
      const txt=prose(v.text);
      versions.push({date:dates[i],revid:v.revid,txt,words:(txt.match(/[\p{L}\p{N}]+/gu)||[]).length});
    }
  }catch(err){st.textContent=err.message==='missing'?'No English Wikipedia article has that title.':'Could not reach Wikipedia. Try again.';return;}
  if(!versions.length){st.textContent='The article did not exist yet in that period.';return;}
  STATE={name,versions,lastRaw};
  st.textContent=`${versions.length} versions of “${name}”, ${versions[0].date} to ${versions[versions.length-1].date}.`;
  showChanges();
  if(!phrases.length) phrases=STATE.top.slice(0,6);
  if(phrases.length) chart(phrases);
  document.getElementById('topen').hidden=false;
  document.getElementById('od').max=today;
});
function firstPara(raw){
  const lead=raw.split(/\n==[^=]/)[0];
  const paras=strip(lead).split(/\n\s*\n/).map(p=>p.replace(/\s+/g,' ').trim()).filter(p=>(p.match(/[\p{L}]+/gu)||[]).length>=8);
  return paras[0]||'';
}
function wdiff(a,b){
  const x=a.split(' '), y=b.split(' '), n=x.length, m=y.length;
  if(n*m>4e6) return {old:esc(a),neu:esc(b)};
  const L=Array.from({length:n+1},()=>new Uint16Array(m+1));
  for(let i=n-1;i>=0;i--)for(let j=m-1;j>=0;j--)L[i][j]=x[i].toLowerCase()===y[j].toLowerCase()?L[i+1][j+1]+1:Math.max(L[i+1][j],L[i][j+1]);
  let i=0,j=0; const o=[],nw=[];
  while(i<n&&j<m){if(x[i].toLowerCase()===y[j].toLowerCase()){o.push(esc(x[i]));nw.push(esc(y[j]));i++;j++;}else if(L[i+1][j]>=L[i][j+1]){o.push(`<del class="d">${esc(x[i])}</del>`);i++;}else{nw.push(`<ins class="a">${esc(y[j])}</ins>`);j++;}}
  while(i<n){o.push(`<del class="d">${esc(x[i])}</del>`);i++;} while(j<m){nw.push(`<ins class="a">${esc(y[j])}</ins>`);j++;}
  return {old:o.join(' ').replace(/<\/del> <del class="d">/g,' '),neu:nw.join(' ').replace(/<\/ins> <ins class="a">/g,' ')};
}
document.getElementById('of').addEventListener('submit',async e=>{
  e.preventDefault(); if(!STATE)return;
  const d=document.getElementById('od').value, oo=document.getElementById('oout'); if(!d)return;
  oo.textContent='Fetching…';
  try{const v=await at(STATE.name,d); if(!v){oo.textContent='The article did not exist yet on that date.';return;}
    const r=wdiff(firstPara(v.text),firstPara(STATE.lastRaw)), last=STATE.versions[STATE.versions.length-1];
    oo.innerHTML=`<div class="cmp2"><div><div class="small"><a href="https://en.wikipedia.org/w/index.php?oldid=${v.revid}">${esc(v.ts.slice(0,10))}</a></div>${r.old}</div><div><div class="small"><a href="https://en.wikipedia.org/w/index.php?oldid=${last.revid}">${esc(last.date)}</a></div>${r.neu}</div></div>`;
  }catch(err){oo.textContent='Could not reach Wikipedia. Try again.';}
});
const m=location.hash.match(/^#track=([^&]*)(?:&w=(.*))?/);
if(m){document.getElementById('ta').value=decodeURIComponent(m[1]); if(m[2])document.getElementById('tw').value=decodeURIComponent(m[2]); document.getElementById('track').scrollIntoView();}
})();
</script>"""


def search_page(ctx: Context):
    h = ["<h1>Search</h1>",
         "<p class='lede'>Find a topic, an article, a cited source or an editor's pattern ID, and "
         "go to its page and data.</p>", SEARCH_CSS,
         "<form class='sf' id='sf' role='search'><input id='q' name='q' type='search' "
         "placeholder='Search a topic, article, source or pattern ID' aria-label='Search' "
         "autocomplete='off'><button type='submit'>Search</button></form>",
         "<div id='res'><noscript><p>Search needs JavaScript. Without it, use "
         f"{link('articles.html', 'Which articles')} and {link('compare.html', 'All articles')}.</p></noscript></div>",
         "<p class='small'>Searches article titles (analysed, and waiting to be analysed), topic "
         "names, sources cited in at least two articles, and the pages of this site. Capitals, "
         "accents and dashes don't matter. Every word you type must appear.</p>",
         "<script src='data/search.js'></script>", SEARCH_JS, TN_CSS, TRACK_CSS, TRACK_HTML, TRACK_JS]
    return page(f"Search · {NAME}", "".join(h), "search.html",
                description="Search the analysed articles, topic areas and cited sources.")


HOME_CSS = """<style>
.hero{padding:36px 0 8px;display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:22px 48px;align-items:end}
.hero .kicker{font:600 .72rem/1 system-ui,-apple-system,"Segoe UI",sans-serif;letter-spacing:.16em;text-transform:uppercase;
 color:var(--accent);margin:0 0 14px}
.hero .ht{grid-column:1/-1}
.hero h1{font-size:clamp(2.1rem,4.2vw,3.4rem);line-height:1.08;letter-spacing:-.015em;margin:0;font-weight:600;max-width:22ch}
.hero .lede{font-size:1.16rem;color:var(--muted);max-width:none;margin:0}
.hero .sf{margin:22px 0 0}
.hero .sf input{padding:14px 18px;border-radius:999px;font-size:1.02rem;background:var(--bg)}
.hero .sf button{border-radius:999px;padding:10px 22px;background:var(--fg);color:var(--bg);border-color:var(--fg)}
.stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:var(--line);border:1px solid var(--line);
 border-radius:14px;overflow:hidden}
.stats div{background:var(--bg);padding:18px 20px}
.stats b{display:block;font:600 1.9rem/1.1 Georgia,"Iowan Old Style",serif;letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.stats span{font:.8rem/1.3 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted)}
.hsec{margin:56px 0 0}
.hsec>h2{border:0;font-size:1.5rem;margin:0 0 4px}
.hsec>.sub{color:var(--muted);margin:0 0 18px}
.feats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.feat{border:1px solid var(--line);border-radius:14px;padding:18px 18px 16px;background:var(--bg);display:flex;flex-direction:column}
.feat .no{font:600 .72rem/1 system-ui,-apple-system,"Segoe UI",sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.feat h3{font-size:1.08rem;margin:10px 0 8px;line-height:1.3}
.feat p{font-size:.92rem;color:var(--muted);margin:0 0 12px;flex:1}
.feat a{font:.86rem system-ui,-apple-system,"Segoe UI",sans-serif;text-decoration:none}
.feat a::after{content:" →"}
.principle{margin:44px 0 0;padding:22px 26px;border-radius:14px;background:var(--soft);display:grid;
 grid-template-columns:minmax(0,1fr) auto;gap:10px 30px;align-items:center}
.principle p{margin:0;font-size:1.05rem;max-width:none}
.principle nav{display:flex;flex-wrap:wrap;gap:6px 18px;font:.88rem system-ui,-apple-system,"Segoe UI",sans-serif}
.principle nav a{text-decoration:none}
.areas{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.area{display:block;border:1px solid var(--line);border-radius:14px;padding:18px 20px;color:var(--fg);text-decoration:none;
 transition:border-color .15s,transform .15s}
.area:hover{border-color:var(--muted);transform:translateY(-1px)}
.area h3{font-size:1.06rem;margin:0 0 12px;line-height:1.3}
.area .n{font:600 2rem/1 Georgia,"Iowan Old Style",serif;font-variant-numeric:tabular-nums}
.area .n small{font:.82rem system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted);margin-left:6px}
.area .kinds{display:flex;flex-wrap:wrap;gap:4px;margin:12px 0 0}
.area .kinds span{font:.74rem/1.2 system-ui,-apple-system,"Segoe UI",sans-serif;padding:3px 8px;border-radius:999px;
 background:var(--soft);color:var(--muted)}
.area .q{font:.78rem system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--muted);margin:10px 0 0}
.allbtn{display:inline-block;margin:18px 0 0;font:.92rem system-ui,-apple-system,"Segoe UI",sans-serif;text-decoration:none}
.allbtn::after{content:" →"}
@media (max-width:980px){.hero{grid-template-columns:1fr;gap:24px}.feats{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:560px){.feats{grid-template-columns:1fr}.principle{grid-template-columns:1fr}}
</style>"""


def home_page(ctx: Context):
    from .candidates import KINDS
    preview = os.environ.get("WTL_LAYOUT") == "2"
    revs = sum((r.get("inputs") or {}).get("history_revisions", 0) for r in ctx.recs)
    cited = len({x["source"] for r in ctx.recs for x in (r.get("sources") or {}).get("list", [])})
    areas = _area_order(ctx)
    if preview:
        kicker, title = "Wikipedia's own standards, and the record", "How did this article come to say what it says?"
        lede = ("Wikipedia sets itself written standards: contested views should be attributed to who holds them, "
                "every significant view should get due weight, anyone can check the sources, no one owns an article. "
                "We set each article beside those standards, quoted word for word, and check it against them "
                "using Wikipedia's own public records.")
    else:
        kicker, title = "From Wikipedia's public records", "Who wrote what you read on Wikipedia?"
        lede = ("Wikipedia shows you what an article says today, but not how it came to say it. We work that out "
                "from Wikipedia's own public records, with a link to the evidence for every number.")
    feats = [("1", "The opening",
              "Does it name who holds contested views, or state one view in Wikipedia's own voice?",
              "The first paragraph in 2015, 2019, 2023 and today, side by side: what changed, which sources "
              "were taken out, and which sentences state contested views without saying whose they are.",
              "how-it-works.html#voice"),
             ("2", "What it rests on", "How authoritative are its sources, what leanings are recorded for "
              "them, and can a reader check them?",
              "Each source with Wikipedia's own reliability rating, academic level, outside raters' scores, "
              "recorded political labels, and whether the footnote can be checked.", "sources.html"),
             ("3", "Who wrote it", "Who wrote the words you are reading, and what does Wikipedia record about them?",
              "How concentrated the writing is, how much is by editors Wikipedia later sanctioned, interests "
              "editors declared on Wikipedia, and where else they write. Editors are never named.",
              "editors.html"),
             ("4", "How it changes", "What was fought over, and what kept text in place?",
              "How often it is edited, what was taken out and put back, and the rules applied.",
              "how-it-works.html#numbers")]
    h = [HOME_CSS, SEARCH_CSS,
         "<section class='hero'><div class='ht'>"
         f"<p class='kicker'>{escape(kicker)}</p><h1>{escape(title)}</h1></div><div><p class='lede'>{escape(lede)}</p>"
         + SEARCH_FORM.format(up="", auto="") + "</div>"
         "<div class='stats' aria-label='The record so far'>"
         f"<div><b>{len(ctx.recs):,}</b><span>articles analysed</span></div>"
         f"<div><b>{len(areas):,}</b><span>topic areas</span></div>"
         f"<div><b>{revs:,}</b><span>revisions read</span></div>"
         f"<div><b>{cited:,}</b><span>different sources cited</span></div>"
         "</div></section>",
         "<section class='hsec'><h2>What each article page shows</h2>"
         "<p class='sub'>Four questions, each answered from the record, with a link to the evidence for every number.</p>"
         "<div class='feats'>"
         + "".join(f"<div class='feat'><span class='no'>{n} · {escape(t)}</span><h3>{escape(q)}</h3>"
                   f"<p>{escape(d)}</p><a href='{u}'>How it is measured</a></div>"
                   for n, t, q, d, u in feats)
         + "</div></section>",
         "<div class='principle'><p>We do not judge whether an article is right, or whether its editors are good "
         "or bad. We show where the record and Wikipedia's own standards can be set side by side.</p>"
         "<nav><a href='how-it-works.html'>How it works</a><a href='articles.html'>Which articles, and why</a>"
         "<a href='objective.html'>Why this matters for AI</a></nav></div>",
         "<section class='hsec'><h2>Topic areas</h2>"
         f"<p class='sub'>{len(ctx.recs):,} articles analysed so far, grouped like with like.</p><div class='areas'>"]
    queued = {}
    done = {r["article"] for r in ctx.recs}
    for c in ctx.candidates:
        if c["title"] not in done:
            queued.setdefault(c["area"], set()).add(c["title"])
    for a in areas:
        rows = [r for r in ctx.recs if ctx.areas.get(r["article"], "") == a]
        counts = [(kind_name(k), sum(1 for r in rows if (ctx.kinds.get(r["article"]) or "") == k))
                  for k in KINDS + [""]]
        q = len(queued.get(a, ()))
        h.append(f"<a class='area' href='compare.html#area-{escape(a or 'none')}'><h3>{escape(area_name(a))}</h3>"
                 f"<div class='n'>{len(rows):,}<small>analysed</small></div><div class='kinds'>"
                 + "".join(f"<span>{escape(name)} {n}</span>" for name, n in counts if n) + "</div>"
                 + (f"<p class='q'>{q:,} more queued</p>" if q else "") + "</a>")
    h.append("</div><a class='allbtn' href='compare.html'>See all articles and their figures</a></section>")
    return page(NAME, "".join(h), "index.html",
                description="How Wikipedia articles came to say what they say, from Wikipedia's public records.")


# ---------------------------------------------------------------- how it works
def _check_results():
    out = {}
    cj = OUT_DIR / "checks.json"
    if cj.exists():
        res = json.loads(cj.read_text(encoding="utf-8"))
        out["articles"] = len(res)
        for k in ("totals", "anonymity", "reproducible"):
            out[k] = sum(1 for v in res.values() if v.get(k, {}).get("pass"))
    sc = DOCS / "spotcheck.md"
    if sc.exists():
        m = re.search(r"\*\*(\d+) of (\d+) pass", sc.read_text(encoding="utf-8"))
        if m:
            out["spot"] = (int(m.group(1)), int(m.group(2)))
    sv = DOCS / "sanctions-verification.md"
    if sv.exists():
        m = re.search(r"(\d+) of (\d+) rows confirmed", sv.read_text(encoding="utf-8"))
        if m:
            out["sanctions"] = (int(m.group(1)), int(m.group(2)))
    return out


STEPS_CSS = """<style>
ol.steps{list-style:none;padding:0;margin:14px 0 0;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;
 counter-reset:s}
ol.steps>li{counter-increment:s;border:1px solid var(--line);border-radius:14px;padding:16px 18px;max-width:none;
 font-size:.93rem;color:var(--muted)}
ol.steps>li::before{content:"Step " counter(s);display:block;font:600 .7rem system-ui,-apple-system,"Segoe UI",sans-serif;
 letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin:0 0 8px}
ol.steps>li>b:first-child{display:block;color:var(--fg);font-size:1rem;margin:0 0 6px;line-height:1.3}
@media (max-width:900px){ol.steps{grid-template-columns:1fr}}
</style>"""


def how_page(ctx: Context):
    c = _check_results()
    n = c.get("articles", len(ctx.recs))
    from . import story as _st
    h = [_st.CSS, "<div class='st'>",
         _st.hero("Method", "How it works",
                  "Every number on this site is counted by a computer program from Wikipedia's public records. "
                  "The program does no guessing and uses no AI. Run it again on the same article and you get "
                  "exactly the same numbers."),
         _st.toc([("steps", "The steps"), ("numbers", "What each number means"), ("words", "Words used on this site"),
                  ("checks", "How the work is checked"), ("rules", "Rules"), ("limits", "Limits")]),
         "</div>", STEPS_CSS,
         "<h2 id='steps'>The steps</h2><ol class='steps'>",
         "<li><b>Take one exact version of the article.</b> Wikipedia keeps every version of every "
         "article. Each of our pages names the version it describes and its date, with a link, so "
         "you can open exactly the same text.</li>",
         "<li><b>Find out who wrote each word.</b> A free tool called "
         f"{link('https://wikiwho-api.wmcloud.org/', 'WikiWho')}, run on Wikipedia's own servers, "
         "follows every word through the article's whole history and finds the editor who first "
         "typed it. If a word was deleted and later put back, it still belongs to the person who "
         "first wrote it. Moving a paragraph does not make you its author.</li>",
         "<li><b>Count only the text people read.</b> Footnotes, tables, picture captions and "
         "lists of links are left out.</li>",
         "<li><b>Check each editor against Wikipedia's sanctions.</b> We keep a hand-checked list "
         "of editors whom Wikipedia's administrators banned from a topic, banned from the site, "
         "or caught running fake extra accounts. Each entry links to Wikipedia's own decision.</li>",
         "<li><b>Follow every footnote to its source.</b> Each footnote is matched to the "
         "newspaper, website, publisher, journal or organisation it points to. Books are matched "
         "by their ISBN (the number printed on the back of a book), using Open Library and "
         "Wikidata. Then we show what outside organisations say about each source. We add no "
         "rating of our own.</li>",
         "<li><b>Compare like with like.</b> Each number is shown next to the figure for a "
         "typical similar article (people next to people, newspapers next to newspapers), so you "
         "can tell whether it is unusual.</li></ol>",
         "<h2 id='numbers'>What each number means</h2>",
         "<p>The numbers on an article page, in the order they appear. Each one says what was "
         "counted. None of them says whether the article is right or wrong.</p>",
         "<h3>Who wrote the text</h3><ul>"
         "<li><b>Share of the words.</b> Out of every 100 words in today's article, how many "
         "each editor first typed. “Editor 1” wrote the most; the numbers are not their real "
         "names and change from article to article.</li>"
         "<li><b>Editors who wrote half the text.</b> Line the editors up from most words to "
         "fewest and count how many it takes to reach half the article. A small number means a "
         "few people wrote most of it.</li>"
         "<li><b>The opening section.</b> The same figures for the summary at the top of the "
         "article (Wikipedia calls it the lead). It is the part most readers, search engines and "
         "AI assistants see.</li>"
         "<li><b>When the text was added.</b> The year each editor's surviving words were first "
         "typed.</li>"
         "<li><b>How long new text lasts.</b> Of all the words ever added to the article, "
         "including ones later deleted, how many were still there 2 days, 30 days and a year "
         "later.</li>"
         "<li id='voice'><b>Wikipedia's voice in the opening.</b> Wikipedia's neutrality policy says "
         "contested assertions and opinions should not be stated as facts in Wikipedia's own voice but "
         "attributed to who holds them, and that uncontested facts should be stated plainly. For each sentence "
         "of the opening section we record two things. First, evidence it is contested: editors took it out "
         "for a day or more and put it back at least twice (by two or more accounts; removals undone within a "
         "day are mostly vandalism and are not counted), tagged it as disputed, or quoted it in three or more "
         "talk-page discussions or in a request for comment; or it uses a word from Wikipedia's own “Words to "
         "watch” guideline (labels, editorializing, unsupported attributions, expressions of doubt). Second, "
         "whether it names who holds the view: an author it cites, or a phrase such as “according to”, "
         "“historians argue”, “opponents characterize”, or “widely seen as” (the policy allows widespread views "
         "to be described as such), or “he”, “she” or “they” followed by a verb such as “argued”, “said” or "
         "“believed” (in an opening section these refer to a person or group already named). In that last case "
         "only the words after the phrase count as theirs: in “He notably argued …”, “notably” is still "
         "Wikipedia's own word. A sentence with the first and not the second is marked as one to check. "
         "That is not a finding that it breaks the policy: whether reliable sources really conflict is for "
         "readers and editors to judge. On control articles such as Photosynthesis no opening sentence is "
         "marked. “With attribution” puts the cited authors' surnames in front of the sentence by a fixed "
         "template (a leading word such as “However,” stays first); it is not a proposed edit, and nothing on this site is written by AI. The last column shows "
         "the most similar sentence of an earlier opening (1 January 2015, 2019 or 2023; content words in "
         "common, similarity at least 0.3) that cited works today's opening no longer cites, with those works "
         "and their authors named in front by the same template. The policy text quoted on every page is "
         "checked word for word against the policy page at the version linked.</li>"
         "<li id='shortdesc'><b>Short description changes.</b> The short description is the line Wikipedia "
         "shows under an article's title in its search box and apps. Each article's history from 1 January "
         "2017 is checked at 128 evenly spaced edits, plus every edit whose summary mentions the short "
         "description and every edit Wikipedia tagged as later reverted. Wherever two checks differ, the edits between them are checked until the exact edit "
         "is found. Only the opening section is read. A change undone between two checks can still be "
         "missed. Changes put back to the earlier wording within a day are shown separately, because that "
         "is how vandalism and its repair usually look. Before about 2018 most short descriptions came "
         "from Wikidata, not the article, and are not tracked. Edit summaries are used only to choose "
         "which edits to check and are not kept; no account names are kept.</li>"
         "<li id='framed'><b>The two template columns beside the opening.</b> Both are today's first "
         "paragraph rewritten by fixed rules; neither is written by a person or by AI, and neither is a "
         "proposed edit. “With sources named”: each sentence marked by the check above gets its cited "
         "authors' surnames in front (“According to A, B and C, …”; more than three become “and N others”); "
         "every other sentence is left as it is. When a marked sentence's footnotes name no author, the "
         "sources' names go in front instead (“According to The New York Times, …”); when no footnote "
         "follows it, “According to an unspecified source, …”. “With removed sources kept”: the same, plus every work cited in the "
         "opening on 1 January 2015, 2019 or 2023 and not cited there now. The sentence it backed then goes "
         "back in, after today's most similar sentence (content words in common, similarity at least 0.3), "
         "or at the end when nothing today is similar and that sentence was in that date's first paragraph. "
         "It gets its own authors in front (or its sources' names, or “an unspecified source”, as above), unless it "
         "already names one of them or says who holds the view. An earlier sentence that still reads nearly "
         "the same today (similarity at least 0.85) is not repeated; its authors join the names in front of "
         "today's sentence when that sentence has names in front. Earlier sentences nearly the same as each "
         "other are shown once; scraps of infobox or markup are left out.</li>"
         "<li><b>At a glance.</b> At the top of each article page, the main figures drawn as bars: "
         "who wrote the words, the share by sanctioned editors, the kinds of sources cited, how "
         "researchers grade the cited publishers and journals, how easy the footnotes are to check, "
         "and who shares the cited websites. They are the same numbers as in the sections below.</li>"
         "<li><b>How the opening has changed.</b> The whole first paragraph as it read on 1 January "
         "2015, 2019 and 2023 (those the article existed for) and today, side by side. Play on a "
         "version shows the one before it changing into it: words taken out fade in red, words "
         "added appear in green (compared word by word with Python's difflib). Below: how many of "
         "the earliest paragraph's words are still there in the same order, how many were taken "
         "out and added, and the share of meaningful words the two have in common (we leave out "
         "words like “the” and “of”). Above each version, the page's short description, the line "
         "Wikipedia shows under the title in its search box and apps (until about 2018 it came from "
         "Wikidata and is not in the article's text, so older versions often have none). Then the "
         "sources cited in footnotes inside the first paragraph at each date, with the same ratings "
         "as above. Folded below, the three opening sentences that changed most: each of today's "
         "opening sentences is paired with the old sentence that shares most of its meaningful "
         "words; pairs sharing between 30% and 90% are the same sentence, rewritten, and the three "
         "that share least are shown. The rules are the same for every article.</li>"
         "<li><b>The sources cited then and now</b> (under Sources cited). The whole article's footnotes on those same "
         "dates, with the same ratings as above. The ratings are today's, because past ratings are "
         "not on record: a change shows that different sources were cited, not that a source was "
         "rated differently. Below it, the sources are split into those dropped since the earliest "
         "date, those kept, and those added, each with the same ratings.</li>"
         "<li><b>Word tracker and the words that changed most.</b> On the search page, for any "
         "article: how often words appear per 1,000 words, twice a year. The six words that changed "
         "most (three up, three down) are picked by a standard statistical test that allows for how "
         "common a word is, so a jump from 20 to 60 mentions counts for more than one from 1 to 3. "
         "Words like “the” and “which” are left out.</li>"
         "<li><b>How much older text is still there.</b> Take the article as it was 1, 2, 3 and "
         "5 years before the version we analysed, and count how many of its words are still in "
         "it. If only 17 out of every 100 words from three years ago are left, most of the article "
         "has been rewritten since then. Every article uses the same distances, so we never pick "
         "a date for one subject.</li></ul>"
         "<h3>Editors Wikipedia sanctioned</h3><ul>"
         "<li><b>Text by sanctioned editors.</b> Out of every 100 words, how many were written by "
         "editors whom Wikipedia later sanctioned: banned from the topic (a topic ban), banned "
         "from Wikipedia (a site ban), or found running secret extra accounts (sockpuppets). A "
         "sanction is about how someone behaved on Wikipedia, not proof that what they wrote is "
         "wrong.</li>"
         "<li><b>Before, during or after the sanction.</b> Whether each of those words was added "
         "before the sanction, while it was in force, or after it ended.</li></ul>"
         "<h3>Sources</h3><ul>"
         "<li><b>Citations.</b> A citation is a footnote: the little number that points to a "
         "book, article or website. A source is who published it. One source can be cited many "
         "times.</li>"
         "<li><b>Works per sentence.</b> One footnote can hold a list of several books or "
         "articles. We count every work in the footnotes that follow a sentence. A sentence backed "
         "by 17 works has more support listed than most; it does not mean the works all say the "
         "same thing.</li>"
         "<li><b>Most-cited authors.</b> The people named as authors in the footnotes, counted "
         "once for every footnote that names them. Where a footnote links an author to their "
         "Wikipedia article, we show what Wikidata records about that person: job, field, "
         "employer, party membership, offices held and organisations they belong to. A † means "
         "Wikidata gives no source for that fact. We never give an author a political score, and "
         "we do not look up Wikipedia editors at all.</li>"
         "<li><b>Kind of source.</b> Book publisher, university press, academic journal, "
         "newspaper and so on, as recorded in Wikidata, the free database that sits behind "
         "Wikipedia.</li>"
         "<li><b>Wikipedia's own rating.</b> Wikipedia's editors keep a list of about 530 "
         "sources they argue about often, marked “generally reliable”, “no consensus”, "
         "“generally unreliable” and so on. Most sources are not on the list; that is not a bad "
         "mark.</li>"
         "<li><b>Quality score.</b> From researchers (Lin and colleagues, 2023) who combined six "
         "sets of expert ratings of news websites into one score from 0 (lowest) to 1 "
         "(highest). Books and journals have no score.</li>"
         "<li><b>Who shares a website (audience leaning).</b> Researchers matched Twitter users "
         "to US voter records and counted how many Democrats and how many Republicans shared "
         "links to each website, treating both parties as the same size. The score runs from −1 "
         "(shared only by Democrats) through 0 (shared equally) to +1 (shared only by "
         "Republicans). To turn it into people: out of every 100 people sharing the site, "
         "Republicans = (1 + score) ÷ 2 × 100. So −0.4 means about 70 Democrats and 30 "
         "Republicans. It describes who shares a website, not what the website says, and covers "
         "only websites. Two studies are used: DomainDemo (Yang and colleagues, 2025) and an "
         "older one from 2017 Twitter data (Robertson and colleagues, 2018).</li>"
         "<li><b>Media Bias/Fact Check and AllSides.</b> Two organisations that label news "
         "outlets (left, centre, right, and how factual). Their labels are shown as they give "
         "them.</li>"
         "<li><b>Academic level.</b> Finland's Publication Forum, where panels of university "
         "researchers grade publishers and journals: 3 top, 2 leading, 1 basic scholarly, 0 below "
         "the scholarly bar.</li>"
         "<li><b>Recorded left–right position.</b> Where a source's recorded labels put it, "
         "from far left to far right, out of every 100 citations that can be placed. Labels that are "
         "positions (far-left, left-wing, centre-left, centrist, centre-right, right-wing, far-right) "
         "are used as they are. For a source with none of those, other labels are placed only when "
         "English Wikipedia's own article on that ideology puts it on one side as a whole: "
         "“conservative” on the right, “socialist” on the left, “social democratic” centre-left, and "
         "so on. “Liberal” is placed by country, because it means different things in different "
         "places: centre-left in the United States, Japan and South Korea, centre-right in "
         "Australia, Sweden and France, and not placed where Wikipedia says both sides use it "
         "(Britain, Germany, Italy, the Netherlands, Russia, Israel and others). Labels such as "
         "“Zionist”, “Islamist” and “nationalist” are not placed, because Wikipedia's articles "
         "describe them on more than one side. "
         "<a href='#positions'>The full list, with Wikipedia's words for each</a>. Only a small share "
         "of citations can be placed, so the page always says how many citations and how many "
         "sources the figure rests on.</li>"
         "<li><b>Recorded as Zionist / anti-Zionist, Islamist, nationalist.</b> These labels are "
         "not left or right, so they are counted on their own: the share of an article's citations to "
         "sources recorded with the label, and how many sources that is. Zionist and anti-Zionist are "
         "shown side by side. Each row appears on any article that cites at least one source with "
         "that label, so we never choose which articles get it.</li>"
         "<li><b>Recorded political affiliation.</b> What Wikidata and Wikipedia's own category "
         "pages say about a publisher's politics (for example “left-wing” or “conservative”). "
         "“None recorded” means there is a record but it says nothing about politics; “no "
         "entry” means there is no record at all.</li>"
         "<li><b>Sources its writers cite.</b> The same ratings for every footnote this article's "
         "editors added across all the articles we analysed, with each editor counted in "
         "proportion to how much of this article they wrote. No single editor's figure is ever "
         "shown.</li>"
         "<li><b>Harder-to-check footnotes.</b> Footnotes with no web link, books with no page "
         "number, sources behind a paywall, opinion pieces, sources not in English with no quote "
         "or translation, and dead links with no saved copy. Each makes a footnote harder to "
         "check, not wrong.</li>"
         "<li><b>Links to check.</b> Cited websites whose home page our program could not open, "
         "and websites whose address (domain) was registered to someone after the article cited "
         "it, which can mean a new owner. We show the site's title then and now so you can "
         "compare.</li></ul>"
         "<h3>How the article was argued over</h3><ul>"
         "<li><b>Text removed.</b> How many words editors deleted over the article's history, "
         "and how many of those were later put back.</li>"
         "<li><b>Words to watch and contested terms.</b> Words from Wikipedia's own guide to "
         "loaded wording (such as “terrorist”, “claimed”, “legendary”), and groups of rival words "
         "for the same thing, counted when editors added or removed them. A count says a word was "
         "added or removed, not whether that was right.</li>"
         "<li><b>How often it changes.</b> Edits per year, edits and editors in the last year, "
         "and how many edits came from people without an account.</li>"
         "<li><b>Back-and-forth.</b> Words that were taken out and put back at least twice, each "
         "time staying out for a day or more. Words removed and restored within a day are counted "
         "separately, because that is how vandalism and its quick repair usually look.</li>"
         "<li><b>Sentences taken out and put back.</b> A sentence is “taken out” when one edit "
         "deletes at least half of its words, and “put back” when a later edit restores them. We "
         "count how many times that happened, how many different accounts did it (never who), "
         "and since when the sentence has stayed. Edits that wipe most of the page at once are "
         "left out, because that is almost always vandalism.</li>"
         "<li><b>Rules that kept text in place.</b> Records showing that Wikipedia's own "
         "processes stopped text being changed for a time: a <i>discussion ban</i> (editors agreed "
         "not to reopen a question until a set date), a <i>request for comment</i> (a formal vote-like "
         "discussion whose result is hard to undo), <i>edit requests</i> turned down (on locked "
         "pages, editors without enough experience must ask; we count requests that quote the "
         "sentence, and those closed with a ban mentioned), a <i>hidden note</i> in the page's "
         "source asking editors to discuss before changing a sentence, a <i>disputed</i> tag, and "
         "<i>page protection</i>. We read these from the talk page and its archives as they were "
         "on the date of the version, and match a discussion to a sentence when it quotes eight or "
         "more words of it in a row.</li>"
         "<li><b>Protection.</b> When Wikipedia locked the article so that only some editors could "
         "change it, and at what level.</li></ul>"
         "<h3>Comparisons</h3><ul>"
         "<li><b>Typical.</b> The middle value (the median) for the other analysed articles of the "
         "same kind: half of them are above it, half below. Shown first for the same topic area, "
         "then for all areas.</li></ul>",
         "<h2 id='words'>Words used on this site</h2><dl class='gloss'>"
         "<dt>Editor</dt><dd>Anyone who changes a Wikipedia article. We show editors as numbers "
         "(Editor 1, Editor 2), never by name.</dd>"
         "<dt>Version (revision)</dt><dd>One saved state of an article. Every edit makes a new "
         "version.</dd>"
         "<dt>Citation, footnote</dt><dd>The small number in an article that points to where a "
         "fact comes from.</dd>"
         "<dt>Source</dt><dd>The publisher, newspaper, website, journal or organisation a "
         "footnote points to.</dd>"
         "<dt>Opening section (lead)</dt><dd>The summary at the top of an article, before the "
         "first heading.</dd>"
         "<dt>Sanction</dt><dd>A restriction Wikipedia's administrators place on an editor "
         "because of how they behaved, such as a ban from a topic.</dd>"
         "<dt>Topic ban</dt><dd>An editor is forbidden to edit articles on one subject.</dd>"
         "<dt>Site ban</dt><dd>An editor is forbidden to edit Wikipedia at all.</dd>"
         "<dt>Sockpuppet</dt><dd>A secret extra account one person uses to look like several "
         "people.</dd>"
         "<dt>Median, typical</dt><dd>The middle value: half the articles are above it and half "
         "below.</dd>"
         "<dt>Average (mean)</dt><dd>Add the values up and divide by how many there are.</dd>"
         "<dt>Share</dt><dd>A part of the whole, as a percentage: 25% means 25 out of every "
         "100.</dd>"
         "<dt>Domain</dt><dd>A website's address, such as nytimes.com.</dd>"
         "<dt>ISBN</dt><dd>The number printed on the back of a book that identifies it.</dd>"
         "<dt>Wikidata</dt><dd>A free database run alongside Wikipedia that records facts about "
         "things, such as who owns a newspaper.</dd>"
         "<dt>Talk page</dt><dd>The discussion page behind every Wikipedia article, where editors "
         "argue about changes and place notices.</dd>"
         "<dt>Pattern ID</dt><dd>A code like 4F44YQ that stands for one editor across articles, "
         "so patterns can be seen without naming anyone.</dd>"
         "<dt>Request for comment (RfC)</dt><dd>A formal discussion that invites editors from "
         "all over Wikipedia to settle a question about an article. Someone not involved closes it "
         "and writes down the result.</dd>"
         "<dt>Discussion ban (moratorium)</dt><dd>An agreement that nobody will propose changing a "
         "passage again until a set date, to stop the same argument starting over.</dd>"
         "<dt>Edit request</dt><dd>On a locked page, editors who are not allowed to edit it ask "
         "on the talk page for a change. Another editor accepts or declines it.</dd>"
         "<dt>Page protection</dt><dd>A lock an administrator puts on a page. “Extended confirmed” "
         "means only accounts at least 30 days old with 500 edits can edit; “full” means only "
         "administrators.</dd>"
         "<dt>Hidden note</dt><dd>A message in an article's source text that readers do not see, "
         "left for other editors.</dd>"
         "<dt>Work</dt><dd>One book, article or web page listed in a footnote. A footnote can list "
         "several.</dd></dl>",
         position_rules_html(),
         "<h2>What is and isn't AI</h2>",
         "<p>The analysis has no AI in it: it only counts and matches, the same way every time. "
         "AI was used to build the project: the code and the first drafts of this site's text "
         "were written with Claude, an AI assistant, and then checked as described below. The "
         "checks are there so that you do not have to trust the code, or whoever wrote it.</p>",
         "<h2 id='checks'>How the work is checked</h2><ul>"]
    if "totals" in c:
        h.append(f"<li><b>Totals add up.</b> Every editor's share in an article sums to 100%: "
                 f"passed for {c['totals']} of {n} articles.</li>")
    if "reproducible" in c:
        h.append(f"<li><b>Reproducible.</b> Running the analysis again on the same version gives "
                 f"byte-for-byte identical data: passed for {c['reproducible']} of {n} articles.</li>")
    if "spot" in c:
        h.append(f"<li><b>Sentences checked against the actual edits.</b> For "
                 f"{c['spot'][1]} randomly chosen sentences, the edit credited with writing each "
                 f"one was opened. The check confirms that edit really added those words, and "
                 f"that the account that saved it is the editor credited: {c['spot'][0]} of "
                 f"{c['spot'][1]} confirmed.</li>")
    if "sanctions" in c:
        h.append(f"<li><b>Every sanction verified.</b> Each entry on the sanctions list was opened "
                 f"at its link and the quoted decision confirmed: {c['sanctions'][0]} of "
                 f"{c['sanctions'][1]} entries confirmed.</li>")
    if "anonymity" in c:
        h.append(f"<li><b>No usernames on the pages.</b> Every page is scanned for every account "
                 f"name in the article's history: passed for {c['anonymity']} of {n} articles.</li>")
    h.append("</ul>")
    h.append("<h2 id='rules'>Rules the project follows</h2><ul>"
             "<li><b>Editors are not named.</b> Article pages show neutral labels (Editor 1, "
             "Editor 2) that differ from page to page. The page on editors across articles uses "
             "separate pattern IDs, and shows editors Wikipedia has not sanctioned only by topic "
             "group, not by article. Usernames appear only behind links to Wikipedia's own public "
             "pages, such as an edit or a decision. The site is not designed to identify anyone; "
             "the underlying edit histories are public on Wikipedia for anyone to analyse.</li>"
             "<li><b>Nobody is identified.</b> No attempt is made to link accounts to real people, "
             "and no information from outside Wikipedia is used about any editor.</li>"
             "<li><b>Same rules for everyone.</b> Every figure is computed identically for every "
             "editor and article. The code has no notion of sides in any dispute.</li>"
             "<li><b>Evidence for every number.</b> Each figure traces to specific versions, edits "
             "or decisions, and the full data is downloadable.</li>"
             "<li><b>No single score.</b> There is no overall bias rating. Breakdowns with "
             "evidence only.</li>"
             "<li><b>Read-only.</b> The project never edits Wikipedia.</li></ul>")
    h.append("<h2 id='limits'>Limits</h2><ul>"
             "<li><b>The sanctions list is not complete.</b> It covers decisions from 2023 on, and "
             "is fullest for the Arab–Israeli conflict area. A figure of 0% means we found no "
             "sanction, not that there was none. Article pages flag where this matters.</li>"
             "<li><b>A sanction is about conduct, not content.</b> It is a finding about how an editor "
             "behaved, not about the accuracy of any text they wrote.</li>"
             "<li><b>Comparisons are between analysed articles.</b> A “typical” figure is the "
             "median of the other analysed articles of the same kind, which are the most-read "
             "ones, not a sample of everything Wikipedia has on the subject.</li>"
             "<li><b>A snapshot.</b> Each page describes one version. Wikipedia keeps changing, "
             "and the date is shown on every page.</li></ul>")
    h.append(f"<p>Full method, definitions and code: {link(REPO, 'the project repository')}.</p>")
    return page(f"How it works · {NAME}", "".join(h), "how-it-works.html",
                description="Method, checks and limits.")


# ---------------------------------------------------------------- objective, about
def objective_page():
    h = ["<h1>Objective</h1>",
         "<p class='lede'>AI assistants and search engines lean heavily on Wikipedia. They learn "
         "from it<sup><a href='#ref1'>1</a>,<a href='#ref2'>2</a>,<a href='#ref3'>3</a></sup>, and they "
         "quote and summarise it, increasingly without sending readers to it"
         "<sup><a href='#ref4'>4</a>,<a href='#ref5'>5</a></sup>. They take in the text, but not how it "
         "got there.</p>",
         "<p>For most articles that doesn't matter much. For contested subjects it can: a "
         "sentence might be the settled work of hundreds of editors, or the wording of a single "
         "editor that nobody has yet challenged. Readers, and the AI systems that read on their "
         "behalf, have no easy way to tell the difference.</p>",
         "<h2>What this project adds</h2>",
         "<p>For each article it analyses, it publishes how the text came to be, as plain pages "
         "and as structured data that software can read:</p><ul>"
         "<li>who wrote the current text, and how concentrated that writing is;</li>"
         "<li>how much comes from editors Wikipedia itself later sanctioned;</li>"
         "<li>how long new text lasts, and how often the article changes;</li>"
         "<li>which sources it rests on, and what outside raters say about them;</li>"
         "<li>what was removed and argued over.</li></ul>",
         "<p>Anyone who reads an article, whether a person, a journalist or an AI system, can "
         "then also read how it was made, and decide for themselves how much weight to give "
         "it.</p>",
         "<h2>What it is not</h2>",
         "<p>It does not decide what is true, rate articles as biased or neutral, or pass "
         "judgment on editors. It cannot make AI objective on its own. What it can do is make "
         "one of AI's main sources more transparent, so that people and machines can judge "
         "for themselves.</p>",
         "<h2>Where it is going</h2><ol>"
         "<li><b>Now:</b> authorship and sanctions for the most-read articles in Wikipedia's "
         "contentious topic areas (this site).</li>"
         "<li><b>Next:</b> a free browser add-on that shows this panel on the Wikipedia page "
         "itself, plus edit wars, removed content and source inventories.</li>"
         "<li><b>Later:</b> who set Wikipedia's source ratings, coordination signals, and checks "
         "of whether sentences match their sources.</li></ol>",
         "<h2 id='sources'>Sources</h2><ol class='refs small'>"
         "<li id='ref1'>Brown, T. et al. (2020). "
         f"{link('https://arxiv.org/abs/2005.14165', 'Language Models are Few-Shot Learners')}. NeurIPS 2020. "
         "The GPT-3 paper names English Wikipedia as one of the five sources of its training text "
         "(section 2.2).</li>"
         "<li id='ref2'>Touvron, H. et al. (2023). "
         f"{link('https://arxiv.org/abs/2302.13971', 'LLaMA: Open and Efficient Foundation Language Models')}. "
         "Wikipedia is 4.5% of the training text (Table 1), and is one of the two parts read about twice "
         "during training.</li>"
         "<li id='ref3'>Mueller, B., Danis, C. and Lavagetto, G. (1 April 2025). "
         f"{link('https://diff.wikimedia.org/2025/04/01/how-crawlers-impact-the-operations-of-the-wikimedia-projects/', 'How crawlers impact the operations of the Wikimedia projects')}. "
         "Wikimedia Foundation. Reports a sharp rise in automated scraping, largely to collect training "
         "data for AI models; at least 65% of the most resource-heavy traffic comes from bots.</li>"
         "<li id='ref4'>McMahon, C., Johnson, I. and Hecht, B. (2017). "
         f"{link('https://ojs.aaai.org/index.php/ICWSM/article/view/14883', 'The Substantial Interdependence of Wikipedia and Google: A Case Study on the Relationship Between Peer Production Communities and Information Technologies')}. "
         "ICWSM 2017. Finds that the quality of Google's search results depends heavily on Wikipedia, and "
         "that Google showing Wikipedia content on its own pages appears to reduce visits to Wikipedia.</li>"
         "<li id='ref5'>Miller, M. (17 October 2025). "
         f"{link('https://diff.wikimedia.org/2025/10/17/new-user-trends-on-wikipedia/', 'New user trends on Wikipedia')}. "
         "Wikimedia Foundation. Human page views fell by roughly 8% compared with the same months of 2024, "
         "which the Foundation links to search engines answering questions directly with generative AI "
         "instead of linking to Wikipedia, and to social video.</li></ol>"]
    return page(f"Objective · {NAME}", "".join(h), "objective.html",
                description="Why the provenance of Wikipedia text matters for AI.")


def about_page():
    h = ["<h1>About</h1>",
         f"<p class='lede'>{escape(NAME)} is an independent, non-commercial project that shows how "
         "Wikipedia articles came to say what they say.</p>",
         "<h2>Status</h2>",
         "<p>This is an early prototype. Articles are being added in batches. Figures and wording "
         "may change as the method is refined; every change to the code is public.</p>",
         "<h2>Independence</h2>",
         "<p>The project is not affiliated with Wikipedia or the Wikimedia Foundation and does not "
         "edit Wikipedia. It is published under a project name, so attention stays on the "
         "evidence rather than on any person.</p>",
         "<h2>Checking it yourself</h2>",
         f"<p>All code and data are public in {link(REPO, 'the project repository')}. Anyone can "
         "rerun the analysis and should get identical results. Corrections are welcome: open an "
         f"{link(REPO + '/issues', 'issue')} with a link to the figure and the evidence.</p>"]
    return page(f"About · {NAME}", "".join(h), "about.html", description="About this project.")


# ---------------------------------------------------------------- build
def build(recs, groups, areas=None, elsewhere=False, out_dir=None, kinds=None):
    # Compute first (this can take long with elsewhere=True), then write into a staging folder
    # and swap it in, so the existing site stays in place until the new one is complete.
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in recs]
    from . import patterns as patterns_mod
    cands = []
    from . import candidates as cd
    if cd.CANDIDATES_CSV.exists():
        import csv
        with open(cd.CANDIDATES_CSV, newline="", encoding="utf-8") as f:
            cands = list(csv.DictReader(f))
    areas, kinds = dict(areas or {}), dict(kinds or {})
    for c in cands:   # articles analysed before they were in the list get their kind from it
        if c["title"] in areas and not kinds.get(c["title"]) and c["area"] == areas[c["title"]]:
            kinds[c["title"]] = c["kind"]
    from .outlets import OUTLETS_JSON
    snap = json.loads(OUTLETS_JSON.read_text(encoding="utf-8")) if OUTLETS_JSON.exists() else None
    from .affiliation import load_display
    load_display((snap or {}).get("sources"))
    pt = patterns_mod.compute(clean, groups, areas, elsewhere=elsewhere, kinds=kinds,
                              outlets=(snap or {}).get("sources"))
    ctx = Context(clean, groups, pt, areas=areas, kinds=kinds, candidates=cands, outlets=snap)
    final = SITE_DIR if out_dir is None else Path(out_dir)
    stage = final.with_name(final.name + ".new")
    if stage.exists():
        shutil.rmtree(stage)
    (stage / "articles").mkdir(parents=True)
    (stage / "data").mkdir()
    _write(stage, clean, ctx)
    if final.exists():
        shutil.rmtree(final)
    stage.rename(final)
    return final


def _detail(html: str, overview: str, name: str, here: str) -> str:
    """A detailed page: the full tables and method notes, with a line back to its overview."""
    banner = (f"<p class='detail-banner'><b>Detailed page.</b> Every table and method note, kept whole. For the "
              f"overview with charts, see <a href='{overview}'>{escape(name)}</a>.</p>")
    return html.replace("<main>", "<main>" + banner, 1)


def _write(SITE_DIR, clean, ctx):
    for r in clean:
        (SITE_DIR / "articles" / f"{slug(r['article'])}.html").write_text(article_page(r, ctx), encoding="utf-8")
        (SITE_DIR / "data" / f"{slug(r['article'])}.json").write_text(json_writer.dumps(r), encoding="utf-8")
    shutil.copy(OUT_DIR / "summary.json", SITE_DIR / "data" / "summary.json")
    (SITE_DIR / "index.html").write_text(home_page(ctx), encoding="utf-8")
    from . import readers as _rd
    (SITE_DIR / "compare.html").write_text(_rd.compare_overview(ctx), encoding="utf-8")
    (SITE_DIR / "compare-detail.html").write_text(
        _detail(compare_page(ctx), "compare.html", "All articles", "compare-detail.html"), encoding="utf-8")
    (SITE_DIR / "articles.html").write_text(_rd.choose_overview(ctx), encoding="utf-8")
    (SITE_DIR / "articles-detail.html").write_text(
        _detail(choose_page(ctx), "articles.html", "Which articles, and why", "articles-detail.html"), encoding="utf-8")
    from . import readers
    (SITE_DIR / "sources.html").write_text(readers.sources_overview(ctx), encoding="utf-8")
    (SITE_DIR / "sources-detail.html").write_text(
        _detail(sources_page(ctx), "sources.html", "Sources", "sources-detail.html"), encoding="utf-8")
    (SITE_DIR / "categories.html").write_text(categories_page(ctx), encoding="utf-8")
    from .outlets import OUTLETS_JSON
    if OUTLETS_JSON.exists():
        shutil.copy(OUTLETS_JSON, SITE_DIR / "data" / "outlets.json")
    from .config import ROOT
    for name in ("contested_terms.json", "words_to_watch.json", "source_names.json", "books.json",
                 "isbn_ranges.xml", "reuse.json", "siteprobe.json", "sitetrace.json", "categories.json", "sorting_notes.json", "activity.json", "position_rules.json", "talk.json", "authors.json", "then_now.json", "stale.json", "wp_discussions.json",
                 "public_suffix_list.dat"):
        if (ROOT / "data" / name).exists():   # the lists every record's fingerprints refer to
            shutil.copy(ROOT / "data" / name, SITE_DIR / "data" / name)
    (SITE_DIR / "editors.html").write_text(_rd.editors_overview(ctx), encoding="utf-8")
    (SITE_DIR / "editors-detail.html").write_text(
        _detail(editors_page(ctx), "editors.html", "Editors", "editors-detail.html"), encoding="utf-8")
    (SITE_DIR / "editor.html").write_text(editor_lookup_page(ctx), encoding="utf-8")
    from . import fingerprints
    (SITE_DIR / "editors-across.html").write_text(fingerprints.editors_across(ctx), encoding="utf-8")
    (SITE_DIR / "sources-affiliations.html").write_text(fingerprints.sources_affiliations(ctx), encoding="utf-8")
    (SITE_DIR / "leaning.html").write_text(_rd.leaning_overview(ctx), encoding="utf-8")
    (SITE_DIR / "leaning-detail.html").write_text(
        _detail(leaning_page(ctx), "leaning.html", "Leaning", "leaning-detail.html"), encoding="utf-8")
    write_editor_data(SITE_DIR, ctx)
    (SITE_DIR / "search.html").write_text(search_page(ctx), encoding="utf-8")
    write_search_data(SITE_DIR, ctx)
    from . import extension
    extension.write(ctx, SITE_DIR)
    (SITE_DIR / "how-it-works.html").write_text(how_page(ctx), encoding="utf-8")
    (SITE_DIR / "objective.html").write_text(objective_page(), encoding="utf-8")
    (SITE_DIR / "about.html").write_text(about_page(), encoding="utf-8")
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")
