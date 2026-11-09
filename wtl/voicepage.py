"""Wikipedia's standard, and the record: the opening section against Wikipedia's neutrality policy
(pilot page; not on the site).

One row per sentence of today's opening section, five columns:
1. the sentence as it reads today;
2. evidence that it is contested (editors' disputes; Wikipedia's "Words to watch"), from wtl/voice.py;
3. the works it rests on, with their authors' and sources' tags;
4. with attribution: for a possible case, the same sentence with its cited authors named in front
   ("According to A, B and C, ..."), a fixed template, not a proposed edit;
5. when the removed sources were in: the earlier wording of the same sentence, with the authors of
   the works since taken out named in front by the same template (the most similar
   sentence of an earlier opening, by shared content words, similarity at least 0.3, as in
   wtl/then_now.py) on the last date checked when it still cited works that today's opening no
   longer cites, with those works. Real past Wikipedia text with a link to that version; nothing
   is written by this project.
Works taken out with sentences that match nothing in today's opening are listed below the table.
"""

from html import escape

from .then_now import similarity
from .voice import _surname, with_prefix

WIKI = "https://en.wikipedia.org"

CSS = """<style>
.vp{width:100%;overflow-x:auto}
.vp table{border-collapse:collapse;min-width:1100px;width:100%}
.vp th{position:sticky;top:0;background:var(--bg);text-align:left;font-size:.8rem;text-transform:uppercase;
 letter-spacing:.03em;color:var(--muted);border-bottom:2px solid var(--fg);padding:8px}
.vp td{vertical-align:top;border-bottom:1px solid var(--line);padding:10px 8px;font-size:.9rem;width:20%}
.vp td.s{font-size:.98rem}
.vp tr.pc td.s{box-shadow:inset 4px 0 0 #c98500}
.vp .ev{margin:0 0 6px}.vp .ev b{font-weight:600}
.vp .w{margin:0 0 8px}.vp .w .who{font-weight:600}
.vp .tpl{background:var(--soft);border-radius:6px;padding:8px}
.vp .tpl .add{background:color-mix(in srgb,#1baf7a 22%,transparent);border-radius:3px;padding:0 2px}
.vp .old{border-left:3px solid var(--line);padding-left:8px}
.vp .muted{color:var(--muted);font-size:.84rem}
.vp .sum{display:flex;gap:18px;flex-wrap:wrap;margin:10px 0 16px}
.vp .sum div{border:1px solid var(--line);border-radius:8px;padding:8px 14px}
.vp .sum b{font-size:1.4rem;display:block}
</style>"""


def page(check: dict, works: dict, removed: list, row_html, policy_quotes: list[tuple[str, str]],
         std_html: str = "") -> str:
    """row_html(work, sentence_text, removed) renders one work with its tags (wtl/whosays.py)."""
    rows = check["sentences"]
    # each removal group (by the sentence it followed) goes to the most similar sentence of today
    groups = {}
    for w in removed:
        groups.setdefault((w["last_seen"], w["sentence_then"], w["revision_then"]), []).append(w)
    placed, unplaced = {}, []
    for key, ws in groups.items():
        best = max(((similarity(key[1], r["text"]), r["id"]) for r in rows), default=(0, None))
        if best[0] >= 0.3:
            placed.setdefault(best[1], []).append((key, ws))
        else:
            unplaced.append((key, ws))
    n_pc = check["possible_cases"]
    h = [CSS, "<div class='vp'>",
         "<div class='sum'>"
         f"<div><b>{n_pc} of {check['sentences_checked']}</b>opening sentences may state a contested "
         f"assertion in Wikipedia's voice {std_html}</div>"
         f"<div><b>{sum(1 for r in rows if r['disputed_by_editors'])}</b>show editors disputing them</div>"
         f"<div><b>{len(removed)}</b>works taken out of the opening since 2015</div></div>",
         ("<blockquote class='muted'>" + "<br>".join(
             f"“{escape(q)}” — {src}" for q, src in policy_quotes) + "</blockquote>" if policy_quotes else ""),
         "<table><tr><th>Today's sentence</th><th>Evidence it is contested</th><th>Works it rests on</th>"
         "<th>With attribution (template)</th><th>When the removed sources were in</th></tr>"]
    works_html = {}
    for r in rows:
        ev = []
        for d in r["disputed_by_editors"]:
            ev.append(f"<p class='ev'><b>Editors:</b> {escape(d)}</p>")
        if r["talk"]:
            ev.append("<p class='ev muted'>" + " · ".join(
                f"<a href='{escape(t['url'])}'>{escape(t['heading'][:50])}</a>" for t in r["talk"][:3]) + "</p>")
        for g, ts in r["words_to_watch"].items():
            ev.append(f"<p class='ev'><b>Words to watch</b> ({escape(g)}): {escape(', '.join(ts))}</p>")
        for g, ts in r["project_terms"].items():
            ev.append(f"<p class='ev muted'>Contested-terms list ({escape(g)}): {escape(', '.join(ts))}</p>")
        if r["named_authors"] or r["attribution_phrase"]:
            ev.append(f"<p class='ev'><b>Attributed:</b> “{escape(r['attribution_phrase'] or ', '.join(r['named_authors']))}”</p>")
        ws = works.get(r["id"], [])
        wl = "".join(f"<div class='w'>{row_html(w, r['text'], False)}</div>" for w in ws[:3])
        if len(ws) > 3:
            wl += (f"<details><summary class='muted'>all {len(ws)} works</summary>"
                   + "".join(f"<div class='w'>{row_html(w, r['text'], False)}</div>" for w in ws[3:]) + "</details>")
        tpl = ""
        if r["with_attribution"]:
            pre, lead = r["attribution_prefix"], r.get("attribution_lead", "")
            tpl = (f"<div class='tpl'>{escape(lead)}<span class='add'>{escape(pre)}</span> "
                   f"{escape(r['with_attribution'][len(lead) + len(pre) + 1:])}</div>")
        elif r["possible_case"]:
            tpl = "<span class='muted'>No author named in its footnotes, so the template has no name to add.</span>"
        old = []
        for (last, sent, rev), gws in sorted(placed.get(r["id"], []), key=lambda x: x[0][0], reverse=True)[:2]:
            items = "".join(f"<div class='w'>{row_html(w, sent, True)}</div>" for w in gws[:3])
            more = (f"<details><summary class='muted'>all {len(gws)} works</summary>"
                    + "".join(f"<div class='w'>{row_html(w, sent, True)}</div>" for w in gws[3:]) + "</details>"
                    if len(gws) > 3 else "")
            names = list(dict.fromkeys(_surname(a) for w in gws for a in w["authors"]))
            if names:
                who = names[:3] + ([f"{len(names) - 3} others"] if len(names) > 3 else [])
                lead, pre, rest = with_prefix("According to " + (who[0] if len(who) == 1 else ", ".join(who[:-1]) + " and " + who[-1]) + ",", sent)
                shown = f"{escape(lead)}<span class='add'>{escape(pre)}</span> {escape(rest)}"
            else:
                shown = escape(sent)
            old.append(f"<div class='old'><p class='tpl'>{shown}</p><p class='muted'>Last seen {escape(last)} · "
                       f"<a href='{WIKI}/w/index.php?oldid={rev}'>that version</a> · works since taken out:</p>"
                       f"{items}{more}</div>")
        h.append(f"<tr class='{'pc' if r['possible_case'] else ''}'><td class='s'><span class='muted'>{escape(r['id'])}"
                 f"</span><br>{escape(r['text'])}</td><td>{''.join(ev) or '<span class=muted>none found</span>'}</td>"
                 f"<td>{wl or '<span class=muted>no footnote after it</span>'}</td><td>{tpl}</td>"
                 f"<td>{''.join(old) or '<span class=muted>no removed work matched to this sentence</span>'}</td></tr>")
    h.append("</table>")
    if unplaced:
        h.append(f"<h3>Taken out with sentences that are no longer in the opening ({sum(len(w) for _, w in unplaced)} works)</h3>")
        for (last, sent, rev), gws in sorted(unplaced, key=lambda x: x[0][0], reverse=True):
            h.append(f"<div class='old' style='margin:10px 0'><p>“{escape(sent)}”</p><p class='muted'>Last seen "
                     f"{escape(last)} · <a href='{WIKI}/w/index.php?oldid={rev}'>that version</a></p>"
                     + "".join(f"<div class='w'>{row_html(w, sent, True)}</div>" for w in gws) + "</div>")
    h.append("</div>")
    return "".join(h)
