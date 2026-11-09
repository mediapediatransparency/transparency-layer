"""Article page: the figures at a glance, as bar charts, and the opening paragraph at each date
with an animated change from one date to the next.

Everything shown here is also on the page further down, in more detail; these are the same
numbers, drawn. Colours: one blue ramp for ordered groups (Editor 1, 2-5, ...; grades 3 to 0),
fixed categorical hues for kinds of source, grey for "the rest" or "not known".
"""

import json
from collections import Counter
from html import escape

GLANCE_CSS = """<style>
:root{--g-o1:#104281;--g-o2:#256abf;--g-o3:#5598e7;--g-o4:#86b6ef;--g-o1i:#fff;--g-o2i:#fff;--g-o3i:#fff;--g-o4i:#0b0b0b;
--g-c1:#2a78d6;--g-c2:#eb6834;--g-c3:#1baf7a;--g-c4:#eda100;--g-c5:#e87ba4;--g-rest:#dcdbd5;--g-resti:#0b0b0b;
--g-dem:#2a78d6;--g-rep:#e34948;--g-sanc:#e34948;--g-card:#fcfcfb;--g-soft:#f1f0eb}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--g-o1:#9ec5f4;--g-o2:#5598e7;--g-o3:#256abf;--g-o4:#184f95;
--g-o1i:#0b0b0b;--g-o2i:#0b0b0b;--g-o3i:#fff;--g-o4i:#fff;--g-c1:#3987e5;--g-c2:#d95926;--g-c3:#199e70;--g-c4:#c98500;
--g-c5:#d55181;--g-rest:#383835;--g-resti:#f0efec;--g-dem:#3987e5;--g-rep:#e66767;--g-sanc:#e66767;--g-card:#1a1a19;--g-soft:#22221f}}
:root[data-theme="dark"]{--g-o1:#9ec5f4;--g-o2:#5598e7;--g-o3:#256abf;--g-o4:#184f95;
--g-o1i:#0b0b0b;--g-o2i:#0b0b0b;--g-o3i:#fff;--g-o4i:#fff;--g-c1:#3987e5;--g-c2:#d95926;--g-c3:#199e70;--g-c4:#c98500;
--g-c5:#d55181;--g-rest:#383835;--g-resti:#f0efec;--g-dem:#3987e5;--g-rep:#e66767;--g-sanc:#e66767;--g-card:#1a1a19;--g-soft:#22221f}
.gl{display:grid;grid-template-columns:1fr;gap:14px;margin:14px 0 8px}
.gl .card{background:var(--g-card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.gl .card h3{font-size:1.05rem;margin:0 0 4px;line-height:1.3;border:0}
.gl .big{margin:0 0 10px;max-width:none}
.gl .bar{display:flex;gap:2px;height:28px;margin:6px 0 4px;min-width:0}
.gl .seg{border-radius:4px;display:flex;align-items:center;padding:0 6px;font-size:.8rem;font-weight:600;color:#fff;
white-space:nowrap;min-width:0;overflow:hidden;cursor:default}
.gl .seg.nolabel{color:transparent!important}
.gl .seg:focus-visible{outline:2px solid var(--fg);outline-offset:2px}
.gl .seg.rest{background:var(--g-rest);color:var(--g-resti)}
.gl .rowlabel{font-size:.84rem;color:var(--muted);margin:10px 0 0}
.gl .legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:.82rem;color:var(--muted);margin:6px 0 2px;padding:0;list-style:none}
.gl .legend li{display:flex;align-items:center;gap:6px;max-width:none}
.gl .sw{width:10px;height:10px;border-radius:3px;display:inline-block;flex:none}
.gl .what{font-size:.86rem;color:var(--muted);margin:10px 0 0;max-width:none}
.gl .facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin:10px 0 0}
.gl .fact{background:var(--g-soft);border-radius:8px;padding:8px 10px}
.gl .fact .v{font-size:1.3rem;font-weight:650;line-height:1.2}
.gl .fact .l{font-size:.8rem;color:var(--muted)}
.gl .mid{position:relative}
.gl .mid::after{content:"";position:absolute;left:50%;top:-4px;bottom:-4px;border-left:2px dashed var(--fg);opacity:.55}
.gl .scale{display:flex;justify-content:space-between;font-size:.76rem;color:var(--muted)}
#gtip{position:fixed;pointer-events:none;background:var(--fg);color:var(--bg);font-size:.8rem;padding:5px 8px;
border-radius:6px;max-width:260px;display:none;z-index:9;line-height:1.35}
</style>"""

GLANCE_JS = """<div id="gtip" role="tooltip"></div><script>
(function(){var t=document.getElementById('gtip');
function show(e){var s=e.target.closest('.seg');if(!s)return;t.textContent=s.dataset.tip;t.style.display='block';
var r=s.getBoundingClientRect(),x=(e.clientX||r.left+r.width/2)+12,y=(e.clientY||r.top)+16;
t.style.left=Math.max(8,Math.min(x,innerWidth-t.offsetWidth-8))+'px';t.style.top=y+'px';}
function hide(){t.style.display='none';}
function fit(){document.querySelectorAll('.gl .seg').forEach(function(s){s.classList.remove('nolabel');
if(s.scrollWidth>s.clientWidth+1)s.classList.add('nolabel');});}
fit();addEventListener('resize',fit);
document.querySelectorAll('.gl .seg').forEach(function(s){s.setAttribute('aria-label',s.dataset.tip);
s.addEventListener('mousemove',show);s.addEventListener('mouseleave',hide);
s.addEventListener('focus',show);s.addEventListener('blur',hide);});})();
</script>"""


def _pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def _bar(segs, label, mid=False):
    """segs: [(share 0-1, background css, ink css or None, tooltip, shown text or None)]."""
    out = [f"<div class='bar{' mid' if mid else ''}' role='img' aria-label='{escape(label, quote=True)}'>"]
    for share, bg, ink, tip, text in segs:
        if share <= 0:
            continue
        cls = "seg rest" if bg is None else "seg"
        style = f"flex:{100 * share:.2f}" + (f";background:{bg}" if bg else "") + (f";color:{ink}" if ink else "")
        out.append(f"<div class='{cls}' tabindex='0' style='{style}' data-tip='{escape(tip, quote=True)}'>"
                   f"{escape(text if text is not None else _pct(share))}</div>")
    out.append("</div>")
    return "".join(out)


def _legend(items):
    return "<ul class='legend'>" + "".join(
        f"<li><span class='sw' style='background:{bg or 'var(--g-rest)'}'></span>{escape(t)}</li>"
        for bg, t in items) + "</ul>"


def _n(x):
    return f"{x:,}"


def card_writers(rec):
    a = rec["authorship"]
    eds, tot = a["editors"], a["total_words"]
    if not tot or not eds:
        return ""
    groups = [("Editor 1", eds[:1]), ("Editors 2–5", eds[1:5]), ("Editors 6–10", eds[5:10]),
              (f"the other {max(0, len(eds) - 10):,}", eds[10:])]
    cols = [("var(--g-o1)", "var(--g-o1i)"), ("var(--g-o2)", "var(--g-o2i)"),
            ("var(--g-o3)", "var(--g-o3i)"), ("var(--g-o4)", "var(--g-o4i)")]
    segs, leg = [], []
    for (name, g), (bg, ink) in zip(groups, cols):
        w = sum(e["words"] for e in g)
        if not g or not w:
            continue
        segs.append((w / tot, bg, ink, f"{name}: {_pct(w / tot)} of the words ({_n(w)})", None))
        leg.append((bg, name))
    top = round(100 * eds[0]["words"] / tot)
    return ("<section class='card'><h3>Who wrote the words you are reading?</h3>"
            f"<p class='big'>The article has <b>{_n(tot)} words</b>, written by <b>{_n(a['editor_count'])} "
            f"editor{'s' if a['editor_count'] != 1 else ''}</b>. One editor wrote <b>{top} of every 100</b> of them.</p>"
            + _bar(segs, "; ".join(s[3] for s in segs)) + _legend(leg) +
            "<p class='what'><b>How to read this:</b> each word in today's article is credited to the "
            "editor who first added it. Editors are numbered by how much of the text they wrote: "
            "Editor 1 wrote the most. The numbers are per article, and account names are never shown.</p></section>")


def card_sanctioned(rec):
    a, acc = rec["authorship"], rec["accountability"]
    if not a["total_words"]:
        return ""
    s, sl = acc["sanctioned_share"], acc["sanctioned_lead_share"]
    bt = acc.get("by_type") or {}
    names = {"topic_ban": "banned them from this topic", "site_ban": "banned them from Wikipedia altogether",
             "sockpuppet": "found they were secretly running extra accounts (sockpuppets)"}
    kinds = [f"{names[k]} ({_pct(bt[k]['share'])} of the words)" for k in names if (bt.get(k) or {}).get("share")]

    def two(share, words, of):
        return _bar([(share, "var(--g-sanc)", None, f"By sanctioned editors: {_pct(share)} ({_n(words)} of {_n(of)} words)", None),
                     (1 - share, None, None, f"By editors with no sanction on record: {_pct(1 - share)}", None)],
                    f"{_pct(share)} of the words by sanctioned editors, {_pct(1 - share)} by others.")
    h = ["<section class='card'><h3>How much was written by editors Wikipedia later sanctioned?</h3>",
         f"<p class='big'><b>{round(100 * s)} of every 100 words</b> in the article"
         + (f", and <b>{round(100 * sl)} of every 100</b> in the opening section," if a["lead_words"] else "")
         + f" were written by <b>{_n(acc['sanctioned_editors'])} editor{'s' if acc['sanctioned_editors'] != 1 else ''}</b> "
         "Wikipedia sanctioned.</p>",
         "<p class='rowlabel'>Whole article</p>", two(s, acc["sanctioned_words"], a["total_words"])]
    if a["lead_words"]:
        h += ["<p class='rowlabel'>Opening section</p>", two(sl, acc["sanctioned_lead_words"], a["lead_words"])]
    h.append(_legend([("var(--g-sanc)", "editors sanctioned"), (None, "no sanction on record")]))
    if kinds:
        h.append("<p class='what'><b>What “sanctioned” means:</b> Wikipedia's own administrators "
                 + "; ".join(kinds) + ". One editor can have more than one. A sanction is about how "
                 "someone behaved on Wikipedia, not proof that what they wrote is wrong.</p>")
    h.append("</section>")
    return "".join(h)


KIND_GROUPS = [("books, other publishers", "var(--g-c1)", {"book publisher", "self-publishing company or platform"}),
               ("books, university presses", "var(--g-c2)", {"university press"}),
               ("academic journals", "var(--g-c3)", {"academic journal"}),
               ("news and magazines", "var(--g-c4)", {"newspaper or news website", "magazine", "broadcaster",
                                                     "news agency", "news media"}),
               ("other kinds", "var(--g-c5)", None)]


def card_kinds(rec, outlets):
    s = rec.get("sources") or {}
    tot = s.get("citations") or 0
    if not tot or not outlets:
        return ""
    c = Counter()
    for x in s.get("list", []):
        k = (outlets.get(x["source"]) or {}).get("kind")
        g = None if k is None else next((n for n, _, ks in KIND_GROUPS if ks is None or k in ks), None)
        c[g] += x["citations"]
    counted = sum(c.values())
    c[None] += max(0, tot - counted)
    segs, leg = [], []
    for name, bg, _ in KIND_GROUPS:
        if c.get(name):
            segs.append((c[name] / tot, bg, "#0b0b0b" if name == "news and magazines" else None,
                         f"{name[0].upper() + name[1:]}: {_n(c[name])} citations ({_pct(c[name] / tot)})", None))
            leg.append((bg, name))
    if c.get(None):
        segs.append((c[None] / tot, None, None, f"Kind not known: {_n(c[None])} citations ({_pct(c[None] / tot)})", None))
        leg.append((None, "kind not known"))
    known = [(n, k) for k, n in c.items() if k]
    lead = max(known)[1] if known else None
    return ("<section class='card'><h3>What kinds of sources does it cite?</h3>"
            f"<p class='big'>The article has <b>{_n(tot)} citations</b> (footnotes) to <b>{_n(s.get('distinct_sources', 0))} "
            "different sources</b>." + (f" The largest known group: <b>{escape(lead)}</b>." if lead else "") + "</p>"
            + _bar(segs, "; ".join(x[3] for x in segs)) + _legend(leg) +
            "<p class='what'><b>Where this comes from:</b> Wikidata, the free database behind Wikipedia, "
            "which records what kind of thing each publisher or website is. “Kind not known” means "
            "Wikidata does not say, or the footnote does not name its publisher.</p></section>")


def card_academic(rec, outlets):
    s = rec.get("sources") or {}
    tot = s.get("citations") or 0
    lv = Counter()
    for x in s.get("list", []):
        L = ((outlets.get(x["source"]) or {}).get("academic_level") or {}).get("level")
        if L is not None:
            lv[L] += x["citations"]
    g = sum(lv.values())
    if not g:
        return ""
    names = {3: "3, top", 2: "2, leading", 1: "1, basic scholarly", 0: "0, below the scholarly bar"}
    cols = {3: ("var(--g-o1)", "var(--g-o1i)"), 2: ("var(--g-o2)", "var(--g-o2i)"),
            1: ("var(--g-o3)", "var(--g-o3i)"), 0: ("var(--g-o4)", "var(--g-o4i)")}
    segs = [(lv[k] / g, cols[k][0], cols[k][1], f"Grade {names[k]}: {_n(lv[k])} citations ({_pct(lv[k] / g)})", None)
            for k in (3, 2, 1, 0) if lv.get(k)]
    return ("<section class='card'><h3>How do researchers grade the publishers and journals it cites?</h3>"
            f"<p class='big'>Of the citations to publishers and journals that researchers grade "
            f"(<b>{_n(g)} of {_n(tot)}</b>), <b>{round(100 * lv.get(3, 0) / g)} of every 100</b> are to the top grade.</p>"
            + _bar(segs, "; ".join(x[3] for x in segs))
            + _legend([(cols[k][0], names[k]) for k in (3, 2, 1, 0) if lv.get(k)]) +
            "<p class='what'><b>Who grades them:</b> Finland's Publication Forum (JUFO), where panels of "
            "university researchers grade publishers and journals from 0 to 3. The other "
            f"{_n(tot - g)} citations are to sources it does not grade, such as newspapers and websites.</p></section>")


def card_checkable(rec, links_count):
    s = rec.get("sources") or {}
    tot = s.get("citations") or 0
    if not tot:
        return ""
    wl = s.get("with_link", 0)
    f = s.get("flags") or {}
    facts = [(f.get("paywall_or_registration", 0), "behind a paywall or sign-up"),
             (f.get("book_without_page", 0), "books cited with no page number"),
             (f.get("opinion", 0), "opinion pieces or blogs"),
             (f.get("not_english_no_quote", 0), "not in English, with no quote or translation"),
             (f.get("dead_link_no_archive", 0), "dead links with no saved copy")]
    if links_count:
        facts.append((links_count, "cited websites listed under “Links to check”"))
    return ("<section class='card'><h3>Can a reader check the footnotes?</h3>"
            f"<p class='big'><b>{round(100 * wl / tot)} of every 100</b> footnotes link to something a reader can open online.</p>"
            + _bar([(wl / tot, "var(--g-c1)", None, f"With a web link: {_n(wl)} citations ({_pct(wl / tot)})", None),
                    (1 - wl / tot, None, None, f"No web link: {_n(tot - wl)} citations ({_pct(1 - wl / tot)})", None)],
                   f"Of {tot} citations: {_pct(wl / tot)} have a web link.")
            + _legend([("var(--g-c1)", "has a web link"), (None, "no web link")])
            + "<div class='facts'>" + "".join(f"<div class='fact'><div class='v'>{_n(v)}</div><div class='l'>{escape(l)}</div></div>"
                                              for v, l in facts)
            + "</div><p class='what'>Each of these makes a footnote harder to check, not wrong. "
            "<a href='#links-to-check'>Details</a>.</p></section>")


def card_sharers(here, writers, everyone):
    """Each: (score on DomainDemo's -1..+1 scale, share of citations covered or None) or None."""
    if not here:
        return ""

    def row(label, v, extra=""):
        if not v:
            return ""
        r = (1 + v[0]) / 2
        return (f"<p class='rowlabel'>{escape(label)}</p>"
                + _bar([(1 - r, "var(--g-dem)", None, f"Democrats: {100 * (1 - r):.1f} of every 100 sharers{extra}",
                         f"Democrats {round(100 * (1 - r))}"),
                        (r, "var(--g-rep)", None, f"Republicans: {100 * r:.1f} of every 100 sharers",
                         f"Republicans {round(100 * r)}")],
                       f"{label}: {100 * (1 - r):.1f} Democrats, {100 * r:.1f} Republicans among people who shared them.",
                       mid=True))
    r = (1 + here[0]) / 2
    cov = here[1]
    return ("<section class='card'><h3>Who shares the websites this article cites?</h3>"
            f"<p class='big'>Out of every 100 people who shared these websites on Twitter, about "
            f"<b>{round(100 * (1 - r))} were Democrats and {round(100 * r)} were Republicans</b>.</p>"
            "<div class='scale'><span>all Democrats</span><span>half and half</span><span>all Republicans</span></div>"
            + row("Websites this article cites", here)
            + row("Websites the same editors cite in all the articles we analysed", writers)
            + row("Websites cited in all the articles we analysed, for comparison", everyone) +
            "<p class='what'><b>How this is measured:</b> researchers matched Twitter users to US voter "
            "records and counted, for each website, how many Democrats and how many Republicans shared "
            "links to it, treating both parties as the same size, so a website shared equally comes out "
            "50–50 (the dashed line). It describes <b>who shares a website, not what the website says</b>.</p>"
            + (f"<p class='what'><b>What it covers:</b> only websites have this measure, so these bars "
               f"describe <b>{round(100 * cov)} of every 100</b> footnotes in this article.</p>" if cov is not None else "")
            + "</section>")


# ---------------------------------------------------------------- the opening, animated
OPEN_CSS = """<style>
.tn .para{margin:2px 0 6px}
.tn .playb{font:inherit;font-size:.82rem;border:1px solid var(--line);background:transparent;color:var(--link);
border-radius:6px;padding:3px 9px;cursor:pointer;margin:4px 0 2px}
.tn .playb:hover{background:var(--g-soft)}
.tn .w-del{background:var(--del-bg);color:var(--del-fg);text-decoration:line-through;
transition:opacity .7s ease,font-size .7s ease}
.tn .w-del.out{opacity:0;font-size:0}
.tn .w-ins{transition:opacity .45s ease,font-size .45s ease,background-color 1.2s ease,color 1.2s ease}
.tn .w-ins.pre{opacity:0;font-size:0}
.tn .w-ins.on{background:var(--ins-bg);color:var(--ins-fg)}
.tn .playall{margin:0 0 6px}
</style>"""

OPEN_JS = """<script>
(function(){
var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function playSD(col,done){
  var s=col.querySelector(':scope>.hd script.sdsteps'),el=col.querySelector(':scope>.hd .sdt'),
      badge=col.querySelector(':scope>.hd .sdwhen');
  if(!s||!el){done();return;}
  var steps=JSON.parse(s.textContent),plain=el.getAttribute('data-plain'),i=0,T=reduce?0:1;
  (function one(){
    if(i>=steps.length){el.textContent=plain;if(badge)badge.textContent='';done();return;}
    var st=steps[i++];if(badge)badge.textContent=st.d?'('+st.d+')':'';
    el.innerHTML=st.ops.map(function(o){var t=esc(o[1]);
      if(o[0]==='=')return '<span>'+t+'</span>';
      if(o[0]==='-')return '<span class="w-del">'+t+'</span>';
      return '<span class="w-ins pre">'+t+'</span>';}).join(' ');
    var dels=el.querySelectorAll('.w-del'),ins=el.querySelectorAll('.w-ins');
    setTimeout(function(){dels.forEach(function(d){d.classList.add('out');});},700*T);
    setTimeout(function(){ins.forEach(function(d){d.classList.remove('pre');d.classList.add('on');});},1500*T);
    setTimeout(function(){el.textContent=st.to;one();},reduce?1500:3000);
  })();
}
function play(col,done){
  if(col._busy)return;col._busy=1;
  var left=2;function fin(){if(--left===0){col._busy=0;if(done)done();}}
  playSD(col,fin);
  var src=col.querySelector(':scope>.hd>script.ops, :scope>script.ops'),p=col.querySelector(':scope>.para');
  if(!src||!p){fin();return;}
  var ops=JSON.parse(src.textContent),plain=p.getAttribute('data-plain');
  var html=ops.map(function(o){var t=esc(o[1]);
    if(o[0]==='=')return '<span>'+t+'</span>';
    if(o[0]==='-')return '<span class="w-del">'+t+'</span>';
    return '<span class="w-ins pre">'+t+'</span>';}).join(' ');
  p.innerHTML=html;
  var dels=p.querySelectorAll('.w-del'),ins=p.querySelectorAll('.w-ins');
  var T=reduce?0:1,start=1800*T,step=Math.min(260,4500/Math.max(1,dels.length))*T;
  dels.forEach(function(d,i){setTimeout(function(){d.classList.add('out');},start+i*step);});
  var t2=start+dels.length*step+900*T,step2=Math.min(260,4500/Math.max(1,ins.length))*T;
  ins.forEach(function(d,i){setTimeout(function(){d.classList.remove('pre');d.classList.add('on');},t2+i*step2);});
  var t3=t2+ins.length*step2+(reduce?5000:2200);
  setTimeout(function(){ins.forEach(function(d){d.classList.remove('on');});},t3);
  var fhtml=p.getAttribute('data-html');
  setTimeout(function(){if(fhtml)p.innerHTML=fhtml;else p.textContent=plain;fin();},t3+(reduce?0:1300));
}
document.querySelectorAll('.tn.four .pair[data-play], .tn.four .scell[data-play]').forEach(function(col){
  col.querySelector(':scope>.hd .playb, :scope>.playb').addEventListener('click',function(e){e.stopPropagation();play(col);});});
var all=document.getElementById('tn-playall');
function playAll(){
  var cols=[].slice.call(document.querySelectorAll('.tn.four .pair[data-play]')),i=0;
  (function next(){if(i<cols.length){var c=cols[i++];
    var box=c.parentElement;if(box&&box.scrollTo)box.scrollTo({left:c.offsetLeft-box.offsetLeft-(i>1?box.firstElementChild.offsetWidth:0),behavior:reduce?'auto':'smooth'});
    play(c,next);}})();}
if(all)all.addEventListener('click',playAll);
var tbl=document.querySelector('.tn.four');
if(tbl&&!reduce&&'IntersectionObserver' in window){var seen=false,io=new IntersectionObserver(function(es){
  if(!seen&&es[0].isIntersecting){seen=true;io.disconnect();setTimeout(playAll,600);}},{threshold:.35});io.observe(tbl);}
})();
</script>"""


def ops_json(ops) -> str:
    return json.dumps(ops, ensure_ascii=False).replace("</", "<\\/")
