"""Who says so: the opening section, sentence by sentence, with what is known about every work it
rests on, and the works taken out of the opening since 2015 (pilot; not on the site).

Left: each sentence of today's opening section and, for every work cited in the footnotes after
it (placed as in wtl/narrative.py), its authors, title and year, and the tags the site shows for
its source (kind, Wikipedia's rating, academic level, quality score, who shares it, bias labels,
country, owner, recorded political labels) and for this citation (no link, paywall, opinion ...);
whether the sentence names the author or states the content in Wikipedia's voice; each author's
recorded labels with Wikipedia's definitions; later editions or later works by the same author on
the same subject (Wikipedia's guideline "Age matters" asks editors to check that older sources
have not been superseded; a later work does not mean the cited one is); and links to the sections
of the author's own Wikipedia article on their views and reception.

Right: works cited in the opening on 1 January 2015, 2019 or 2023, or at the start of a later
quarter, that today's opening no longer cites: the last date seen, the sentence each followed then,
whether today's article still cites it elsewhere, and the same tags. Facts with their sources; no
verdict.
"""

import re
from html import escape

AGE_MATTERS = "https://en.wikipedia.org/w/index.php?oldid=1383420477#Age_matters"
WIKI = "https://en.wikipedia.org"
SHOWN = 4

CSS = """<style>
.wsgrid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:22px;
 width:100%}
@media (max-width:980px){.wsgrid{grid-template-columns:1fr}}
.wsgrid h2{margin-top:6px}
.ws{border:1px solid var(--line);border-radius:10px;margin:12px 0;background:var(--bg)}
.ws>.s{margin:0;padding:12px 14px;font-size:1.02rem;border-bottom:1px solid var(--line)}
.ws>.s .sid{color:var(--muted);font-size:.78rem;margin-right:6px}
.ws ul{list-style:none;margin:0;padding:4px 14px 8px}
.ws li{padding:8px 0;border-bottom:1px dashed var(--line)}
.ws li:last-child{border-bottom:0}
.ws .who{font-weight:600}
.ws .work{color:var(--muted)}
.ws .src{font-size:.85rem;color:var(--muted);margin-top:2px}
.ws .tags{margin-top:4px;display:flex;flex-wrap:wrap;gap:3px 2px;align-items:center}
.ws .pill.voice{background:var(--soft);border-color:var(--fg)}
.ws .pill.flag{border-color:#c98500;background:color-mix(in srgb,#eda100 14%,transparent);color:inherit;text-decoration:none}
.ws .more{font-size:.8rem;color:var(--muted);margin-top:4px}
.ws details>summary{cursor:pointer;color:var(--link);font-size:.86rem;padding:4px 0}
.ws>.s.then{font-size:.92rem;color:var(--fg)}
.rm .ws{background:var(--soft)}
</style>"""


from .voice import ATTRIB, PRONOUN_ATTRIB   # noqa: E402


def _surname(n: str) -> str:
    p = re.sub(r"\(.*?\)", "", n).replace(",", " ").split()
    return p[-1] if p else n


def _row(w, sentence, authors_db, labels_db, newer, sections, chip, tags, src_name, removed=False) -> str:
    names, author_tags, links = [], [], []
    for a in w["authors"]:
        e = authors_db.get(a) or {}
        names.append(f"<a href='{WIKI}/wiki/{escape(a.replace(' ', '_'))}'>{escape(a)}</a>" if e.get("wikidata")
                     else escape(a))
        named = re.search(r"\b" + re.escape(_surname(a)) + r"\b", sentence) is not None
        phrase = None if named else (ATTRIB.search(sentence) or PRONOUN_ATTRIB.search(sentence))
        how = ("named in the sentence" if named else
               f"attributed in the sentence (“{escape(phrase.group(0))}”)" if phrase else "stated in Wikipedia’s voice")
        author_tags.append(f"<span class='pill voice' title='Whether the sentence names this author (for example "
                           f"“According to {escape(_surname(a))} …”), attributes the content with a phrase such as "
                           f"“he argued” or “historians say”, or states the content without either.'>"
                           f"{escape(_surname(a))}: {how}{' then' if removed else ''}</span>")
        for x in (labels_db.get("authors") or {}).get(a, []):
            author_tags.append(chip(x["label"], x["from"], x.get("display")))
        for row in (newer.get(a) or {}).get("cited", []):
            if w["title"] and row["title"] == w["title"]:
                if row["later_editions"]:
                    y = ", ".join(str(x[1]) for x in row["later_editions"][:3])
                    author_tags.append(f"<a class='pill flag' href='{AGE_MATTERS}' title='The scholarly catalogue "
                                       f"lists the same title in a later year: a later edition or a reprint.'>"
                                       f"same title also {y}</a>")
                if row["later_same_subject"]:
                    t, y, _ = row["later_same_subject"][0]
                    author_tags.append(f"<a class='pill flag' href='{AGE_MATTERS}' title='A later work by the same "
                                       f"author whose title shares subject words with this one.'>later work by "
                                       f"{escape(_surname(a))} on the same subject: {escape(t[:50])} ({y})</a>")
        sec = sections.get(a) or []
        top = [x for x in sec if x["under"] is None]
        if top:
            base = f"{WIKI}/wiki/{a.replace(' ', '_')}#"
            links.append(f"{escape(_surname(a))} on Wikipedia: " + " · ".join(
                f"<a href='{base}{escape(x['anchor'])}'>{escape(x['heading'])}</a>" for x in top))
    who = " and ".join(names) or "<span class='work'>no author named</span>"
    work = (f" — <i>{escape(w['title'])}</i>" if w["title"] else "") + (f" ({w['year']})" if w["year"] else "")
    extra = ""
    if removed:
        extra = ("<div class='more'>Still cited elsewhere in today's article.</div>" if w["still_cited_elsewhere"]
                 else "<div class='more'>Not cited anywhere in today's article.</div>")
    return (f"<li><span class='who'>{who}</span><span class='work'>{work}</span>"
            f"<div class='src'>Source: {escape(src_name(w['source']) if w['source'] else '–')}</div>"
            f"<div class='tags'>{tags(w['source'], w['flags'])}{''.join(author_tags)}</div>"
            + "".join(f"<div class='more'>{x}</div>" for x in links) + extra + "</li>")


def view(rec, sents, works_by_sentence, removed, authors_db, labels_db, newer, sections, chip, tags,
         src_name) -> str:
    args = (authors_db, labels_db, newer, sections, chip, tags, src_name)
    left = ["<div><h2>The opening today</h2>"]
    for s in sents:
        if not s.id.startswith("lead"):
            continue
        ws = works_by_sentence.get(s.id, [])
        left.append(f"<div class='ws'><p class='s'><span class='sid'>{escape(s.id)}</span>{escape(s.text)}</p>")
        if not ws:
            left.append("<ul><li class='more'>No footnote directly after this sentence.</li></ul></div>")
            continue
        rows = [_row(w, s.text, *args) for w in ws]
        left.append("<ul>" + "".join(rows[:SHOWN]) + "</ul>")
        if len(rows) > SHOWN:
            left.append(f"<details><summary>&nbsp;&nbsp;Show all {len(rows)} works</summary><ul>"
                        + "".join(rows[SHOWN:]) + "</ul></details>")
        left.append("</div>")
    left.append("</div>")
    right = [f"<div class='rm'><h2>Taken out of the opening since 2015 ({len(removed)})</h2>"
             "<p class='small'>Works cited in the opening section on 1 January 2015, 2019 or 2023 or at the "
             "start of a later quarter, and not cited in today's opening. Newest removals first. A work taken "
             "out may have been replaced by a better source, moved lower in the article, or dropped; the "
             "dates show when, not why.</p>"]
    groups = {}
    for w in removed:   # one box per sentence they followed, newest first
        groups.setdefault((w["last_seen"], w["sentence_then"], w["revision_then"]), []).append(w)
    for (last, sent, rev), ws in groups.items():
        rows = [_row(w, sent, *args, removed=True) for w in ws]
        right.append(f"<div class='ws'><p class='s then'>In the opening until {escape(last)} (last date checked), "
                     f"after: “{escape(sent)}” <a href='{WIKI}/w/index.php?oldid={rev}'>that version</a></p>"
                     "<ul>" + "".join(rows[:SHOWN]) + "</ul>"
                     + (f"<details><summary>&nbsp;&nbsp;Show all {len(rows)} works</summary><ul>"
                        + "".join(rows[SHOWN:]) + "</ul></details>" if len(rows) > SHOWN else "")
                     + "</div>")
    right.append("</div>")
    return CSS + "<div class='wsgrid'>" + "".join(left) + "".join(right) + "</div>"
