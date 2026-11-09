"""Article page layout: six sections, each opening with the questions it answers, its main
graphic, and its details folded into accordions.

The section contents are the ones site.article_page writes; this module only regroups them by
their headings, so every figure and its wording stay exactly as computed. Nothing is added or
interpreted here.
"""

import re
from html import escape

# (anchor, title, questions it answers, h2 headings it gathers, glance cards shown first)
# one line under each section title; the standard and the questions open from it
ONE_LINE = {
    "opening": "How the first paragraph read in 2015, 2019, 2023 and now, and the same paragraph with its "
               "sources named.",
    "writers": "Who wrote today's words, and how much is by editors Wikipedia later sanctioned.",
    "sources": "What kinds of sources it cites, and how outside raters grade them.",
    "held": "What has kept text from changing.",
    "changes": "How often it is edited, how long new text lasts, and what was taken out.",
    "lookup": "Where a given sentence came from and what has happened to it since.",
}

SECTIONS = [
    ("opening", "The opening",
     "Does the summary readers, search engines and AI assistants see first state contested views as "
     "facts, or name who holds them? How has it changed since 2015, and which sources were taken out?",
     ["How the opening has changed", "Wikipedia's voice in the opening"], []),
    ("writers", "Who wrote it",
     "Who wrote the words in today's version? How concentrated is that? How much is by editors "
     "Wikipedia later sanctioned, and when was it added?",
     ["Who wrote the text", "The opening section", "Text by editors Wikipedia sanctioned",
      "Editors in detail", "This article's editors elsewhere"], ["peers_w", "writers", "sanctioned"]),
    ("sources", "What it rests on",
     "What kinds of sources does it cite? How do outside raters grade them? Who wrote them? "
     "Can a reader check the footnotes?", ["Sources cited"], ["peers_s", "kinds", "academic", "checkable", "sharers"]),
    ("held", "How text is held in place",
     "What has kept text from changing: protection, discussion bans, requests for comment, "
     "hidden notes, and sentences taken out and put back?",
     ["Rules that kept text in place", "Sentences taken out and put back"], []),
    ("changes", "How it changes",
     "How often is the article edited? How long does new text last? What was taken out, and "
     "which watched words does it use?",
     ["How often the article changes", "How long new text lasts", "Text removed",
      "Words to watch and contested terms"], []),
    ("lookup", "Look up a sentence",
     "Where did a given sentence come from, who wrote it, and what has happened to it since?",
     ["Sentence by sentence"], []),
]
LAST = ["About these numbers"]
# sub-headings of one old section folded together, in this order; others fold on their own
GROUPS = {"sources": [
    ("How the sources are rated", ["How the cited sources are rated", "How many works back each sentence"]),
    ("Most-cited sources and authors", ["Most-cited sources", "Most-cited authors",
                                        "The sources this article cites, and the sources its writers cite"]),
    ("Checking the footnotes", ["Opinion and harder-to-check citations", "Links to check",
                                "Who added the citations"]),
    ("Sources then and now", ["The sources cited then and now", "Sources dropped and added since 2015"]),
]}

CSS = """<style>
.secnav{position:sticky;top:0;z-index:20;background:var(--bg);border-bottom:1px solid var(--line);
 margin:14px -16px 0;padding:6px 16px;display:flex;gap:4px;overflow-x:auto;scrollbar-width:none}
.secnav::-webkit-scrollbar{display:none}
.secnav a{white-space:nowrap;padding:5px 10px;border-radius:999px;font-size:.86rem;color:var(--muted);text-decoration:none}
.secnav a:hover,.secnav a.on{background:var(--soft);color:var(--fg)}
section.sec{scroll-margin-top:52px;margin:34px 0 0;padding-top:4px;border-top:2px solid var(--fg)}
section.sec>h2{border:0;margin:10px 0 4px;font-size:1.45rem}
section.sec>h2 .no{color:var(--muted);font-weight:500;margin-right:8px}
.std{border-left:4px solid var(--fg);background:var(--soft);padding:10px 14px;margin:6px 0 12px;border-radius:0 8px 8px 0}
.std .lbl2{font-size:.74rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:2px}
.std p{margin:4px 0;font-size:.95rem}.std a{font-size:.8rem;white-space:nowrap}
.asks{margin:0 0 14px;color:var(--muted);font-size:.98rem}
p.one{margin:4px 0 12px;max-width:none}
details.one{margin:4px 0 12px}
details.one>summary{cursor:pointer;list-style:none;color:var(--fg);font-size:.98rem}
details.one>summary::-webkit-details-marker{display:none}
details.one>summary .more{color:var(--link);font-size:.84rem;white-space:nowrap}
details.one>summary .more::after{content:" ▸"}
details.one[open]>summary .more::after{content:" ▾"}
details.one[open]>summary{margin-bottom:6px}
details.one>summary:not(:has(.more)){color:var(--link);font-size:.9rem}
details.one>summary:not(:has(.more))::after{content:" ▸"}
details.one[open]>summary:not(:has(.more))::after{content:" ▾"}
.asks b{color:var(--fg);font-weight:600}
details.acc{border:1px solid var(--line);border-radius:8px;margin:8px 0;background:var(--bg)}
details.acc>summary{cursor:pointer;padding:10px 14px;font-weight:600;list-style:none;display:flex;gap:10px;align-items:baseline}
details.acc>summary::-webkit-details-marker{display:none}
details.acc>summary::before{content:"▸";color:var(--muted);transition:transform .15s}
details.acc[open]>summary::before{transform:rotate(90deg)}
details.acc>summary .hint{font-weight:400;color:var(--muted);font-size:.85rem}
details.acc>.in{padding:0 14px 12px}
details.acc>.in h3{font-size:1.02rem;margin-top:16px}
.find{width:100%;max-width:420px;padding:8px 10px;border:1px solid var(--line);border-radius:6px;
 background:var(--bg);color:var(--fg);font:inherit;margin:4px 0 10px}
.gl.two{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
main,header.site .in,footer .in{max-width:1240px}
.tn.four{width:100%!important;margin-left:0!important;display:grid!important;grid-auto-flow:column;
 grid-auto-columns:max(280px,calc((100% - 24px) / 3));
 grid-template-columns:none!important;grid-template-rows:repeat(8,auto);overflow-x:auto;gap:0 12px;
 scroll-snap-type:x proximity;padding-bottom:10px}
.vp{width:100%!important;margin-left:0!important}
@media (max-width:700px){.tn.four{grid-auto-columns:84vw}}
.tn.four .pair{scroll-snap-align:start;background:var(--bg)}
.tn.four .pair.framed{background:var(--soft)}
.tn.four .pair:first-child{position:sticky;left:0;z-index:2;box-shadow:8px 0 10px -8px rgba(0,0,0,.35)}
.tn.four .pair:first-child .when::after{content:" · stays in view";text-transform:none;letter-spacing:0}
@media (max-width:760px){.tn.four .pair:first-child{position:static;box-shadow:none}
 .tn.four .pair:first-child .when::after{content:""}}
</style>"""

JS = """<script>
(function(){
 function openTo(id){var t=id&&document.getElementById(id);if(!t)return;
  for(var e=t;e;e=e.parentElement){if(e.tagName==='DETAILS')e.open=true}t.scrollIntoView();}
 window.addEventListener('hashchange',function(){openTo(location.hash.slice(1))});
 document.addEventListener('DOMContentLoaded',function(){openTo(location.hash.slice(1))});
 var links=[].slice.call(document.querySelectorAll('.secnav a'));
 var secs=links.map(function(a){return document.getElementById(a.getAttribute('href').slice(1))});
 if('IntersectionObserver' in window){var io=new IntersectionObserver(function(es){es.forEach(function(e){
  if(e.isIntersecting){links.forEach(function(a){a.classList.toggle('on',a.getAttribute('href')==='#'+e.target.id)})}})},
  {rootMargin:'-45% 0px -50% 0px'});secs.forEach(function(s){s&&io.observe(s)})}
 [].forEach.call(document.querySelectorAll('input.find'),function(inp){inp.addEventListener('input',function(){
  var q=inp.value.toLowerCase(),box=document.getElementById(inp.dataset.box);
  [].forEach.call(box.querySelectorAll('details'),function(d){if(q)d.open=true});
  [].forEach.call(box.querySelectorAll('tr'),function(tr){if(!tr.querySelector('td'))return;
   tr.style.display=!q||tr.textContent.toLowerCase().indexOf(q)>-1?'':'none'})})});
})();
</script>"""

H2 = re.compile(r"<h2\b[^>]*>(.*?)</h2>", re.S)
H3 = re.compile(r"<h3\b[^>]*>(.*?)</h3>", re.S)


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


def _blocks(html: str, rx) -> tuple[str, list[tuple[str, str, str]]]:
    """(text before the first heading, [(heading text, heading html, content)])."""
    ms = list(rx.finditer(html))
    if not ms:
        return html, []
    head, out = html[:ms[0].start()], []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(html)
        out.append((_text(m.group(1)), m.group(0), html[m.end():end]))
    return head, out


_POL: dict = {}


def _standard(anchor: str) -> str:
    """Wikipedia's own standard for this section, quoted word for word with the version read
    (data/policies.json, wtl/policies.py)."""
    if "d" not in _POL:
        import json
        from .config import ROOT
        p = ROOT / "data" / "policies.json"
        _POL["d"] = json.loads(p.read_text(encoding="utf-8")).get("sections", {}) if p.exists() else {}
    qs = _POL["d"].get(anchor) or []
    if not qs:
        return ""
    return ("<div class='std'><div class='lbl2'>Wikipedia's own standard</div>" + "".join(
        f"<p>“{escape(q['quote'])}” <a href='{escape(q['url'])}'>{escape(q['name'])}</a></p>" for q in qs) + "</div>")


def _fold_intro(html: str, label: str = "") -> str:
    """A section's first long paragraph of explanation becomes its first sentence (or `label`),
    with the rest one click away."""
    m = re.search(r"<p(?: class='small')?>(.*?)</p>", html, re.S)
    if not m or len(_text(m.group(1))) < 220:
        return html
    inner = m.group(1)
    cut = re.search(r"(?<=[a-z)])\.\s", inner)
    if label:
        first, rest = escape(label), inner
    elif not cut:
        return html
    else:
        first, rest = inner[:cut.start() + 1], inner[cut.end():]
    more = "" if label else " <span class='more'>More</span>"
    return (html[:m.start()] + f"<details class='one'><summary>{first}{more}</summary>"
            f"<p class='small'>{rest}</p></details>" + html[m.end():])


POPUP_SECTIONS = {"opening"}


def std_popup(anchor: str, label: str = "Wikipedia's standard") -> str:
    """Wikipedia's own standard for a section as a small pop-up (quoted word for word, with the
    version read)."""
    if "d" not in _POL:
        _standard(anchor)
    qs = _POL.get("d", {}).get(anchor) or []
    if not qs:
        return ""
    return (f"<details class='pop'><summary>ⓘ {escape(label)}</summary><div class='popb'>" + "".join(
        f"<p>“{escape(q['quote'])}” <a href='{escape(q['url'])}'>{escape(q['name'])}</a></p>" for q in qs)
        + "</div></details>")


def _acc(title: str, body: str, open_=False) -> str:
    return (f"<details class='acc'{' open' if open_ else ''}><summary>{escape(title)}</summary>"
            f"<div class='in'>{body}</div></details>")


def regroup(body: str, cards: dict[str, str], glance_css: str = "", glance_js: str = "") -> str:
    """Rebuild an article page body (as site.article_page writes it) into the six sections."""
    head, blocks = _blocks(body, H2)
    by = {t: (hh, c) for t, hh, c in blocks}
    used = {"At a glance"}
    nav, out = [], [CSS, glance_css, head]
    for n, (anchor, title, asks, h2s, card_keys) in enumerate(SECTIONS, 1):
        present = [t for t in h2s if t in by]
        cs = [cards[k] for k in card_keys if cards.get(k)]
        if not present and not cs:
            continue
        nav.append(f"<a href='#sec-{anchor}'>{escape(title)}</a>")
        s = [f"<section class='sec' id='sec-{anchor}'><h2><span class='no'>{n}</span>{escape(title)}</h2>"]
        if anchor in POPUP_SECTIONS:   # the standard opens from the places it applies to
            s.append(f"<p class='one'>{escape(ONE_LINE.get(anchor, asks))}</p>")
        else:
            s.append(f"<details class='one'><summary>{escape(ONE_LINE.get(anchor, asks))} <span class='more'>"
                     f"Wikipedia's standard and what this records</span></summary>{_standard(anchor)}"
                     f"<p class='asks'><b>The record.</b> {escape(asks)}</p></details>")
        if cs:
            s.append(f"<div class='gl two'>" + "".join(cs) + "</div>")
        if anchor == "opening":
            for t in present:
                if t == "How the opening has changed":   # the version viewer stays open, first
                    s.append(_fold_intro(by[t][1], "How to read the columns").replace(
                        "<div class='tn four", "<p class='small' style='margin:4px 0'>Scroll sideways for the "
                        "later versions and the two template columns; the earliest stays in view.</p>"
                        "<div class='tn four", 1))
                else:                                     # the sentence-by-sentence table folds
                    s.append(_acc(t + ": every sentence of the opening, checked", _fold_intro(by[t][1])))
        elif anchor == "lookup":
            for t in present:
                s.append("<input class='find' type='search' placeholder='Find words in a sentence…' "
                         "data-box='lookup-box' aria-label='Find words in a sentence'>"
                         f"<div id='lookup-box'>{by[t][1]}</div>")
        elif len(present) == 1:   # one old section: its intro shows, each sub-heading folds
            intro, subs = _blocks(by[present[0]][1], H3)
            s.append(intro)
            done = set()
            for gt, members in GROUPS.get(anchor, []):
                part = [(t, hh, c) for t, hh, c in subs if t in members]
                if part:
                    s.append(_acc(gt, "".join(hh + c for _, hh, c in part)))
                    done.update(t for t, _, _ in part)
            for t, hh, c in subs:
                if t not in done:
                    s.append(_acc(t, c))
        else:                     # several old sections: each folds whole
            for t in present:
                s.append(_acc(t, by[t][1]))
        used.update(present)
        s.append("</section>")
        out.append("".join(s))
    rest = [(t, hh, c) for t, hh, c in blocks if t not in used and t not in LAST]
    for t, hh, c in rest:          # anything not mapped keeps its place at the end, unfolded
        out.append(hh + c)
    for t in LAST:
        if t in by:
            out.append(by[t][0] + by[t][1])
    # the section menu goes straight after the page header (title and version line)
    out.insert(3, f"<nav class='secnav' aria-label='Sections'>{''.join(nav)}</nav>")
    return "".join(out) + glance_js + JS
