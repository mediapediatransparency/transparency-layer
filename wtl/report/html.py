"""Plain one-page HTML report. Editors appear only as neutral labels; usernames can appear only
inside evidence links (href attributes), never in visible text."""

from html import escape

CSS = """
:root{--bg:#fbfbf9;--fg:#1d1d1b;--muted:#5d5d58;--line:#d9d8d2;--soft:#f0efea;--link:#1f4e8c;--mark:#3a3a36}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#181816;--fg:#e9e8e3;--muted:#a6a59e;--line:#3a3935;--soft:#22221f;--link:#8fb6ec;--mark:#d6d5cf}}
:root[data-theme="dark"]{--bg:#181816;--fg:#e9e8e3;--muted:#a6a59e;--line:#3a3935;--soft:#22221f;--link:#8fb6ec;--mark:#d6d5cf}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1060px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.7rem;margin:0 0 4px}
h2{font-size:1.15rem;margin:36px 0 8px;padding-top:8px;border-top:1px solid var(--line)}
p{margin:6px 0}
a{color:var(--link)}
.meta{color:var(--muted);font-size:.9rem}
.facts{background:var(--soft);border:1px solid var(--line);border-radius:6px;padding:12px 16px;margin:16px 0}
.facts li{margin:4px 0}
.base{color:var(--muted);font-size:.85em;white-space:nowrap}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;font-size:.9rem;margin:8px 0}
th,td{text-align:left;vertical-align:top;padding:5px 8px;border-bottom:1px solid var(--line)}
th{font-weight:600;color:var(--muted);font-size:.8rem;text-transform:uppercase;letter-spacing:.02em}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.tag{display:inline-block;border:1px solid var(--mark);border-radius:3px;padding:0 5px;font-size:.78rem;white-space:nowrap}
.small{font-size:.85rem;color:var(--muted)}
details{margin:8px 0}
summary{cursor:pointer;color:var(--link)}
"""


def pct(x, digits=1):
    return "–" if x is None else f"{x * 100:.{digits}f}%"


def get(rec, path):
    cur = rec
    for part in path.split("."):
        if cur is None:
            return None
        cur = cur.get(part) if isinstance(cur, dict) else None
    return cur


def base(baseline, path, fmt=pct):
    if not baseline:
        return ""
    v = baseline["values"].get(path)
    if v is None:
        return ""
    return f' <span class="base">({escape(baseline["label"])}: {fmt(v)})</span>'


def link(url, text):
    return f'<a href="{escape(url, quote=True)}">{escape(text)}</a>'


def diff_link(revid):
    return link(f"https://en.wikipedia.org/w/index.php?diff=prev&oldid={revid}", f"diff {revid}")


TYPE_NAMES = {"topic_ban": "topic ban", "site_ban": "site ban", "sockpuppet": "sockpuppetry finding"}


def sanction_cell(e):
    if not e["sanctioned"]:
        return ""
    parts = []
    for s in e["sanctions"]:
        what = TYPE_NAMES.get(s["type"], s["type"])
        area = f' ({s["area"]})' if s["area"] else ""
        src = " · block log" if s["source"] == "block_log" else ""
        parts.append(f'<span class="tag">{escape(what)}{escape(area)}</span> {escape(s["date"])}'
                     f'{escape(src)} {link(s["evidence"], "decision")}')
    return "<br>".join(parts)


def render(rec: dict, baseline: dict | None = None, summary_href: str | None = None) -> str:
    a, acc = rec["authorship"], rec["accountability"]
    title = rec["article"]
    eds = a["editors"]
    sanctioned_eds = [e for e in eds if e["sanctioned"]]
    lead_sents = [s for s in rec["sentences"] if s["id"].startswith("lead-")]
    lead_sanct = [s for s in lead_sents if s["author_sanctioned"]]
    h = []
    h.append(f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
             f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>{escape(title)} provenance</title><style>{CSS}</style></head><body><main>")
    h.append(f"<h1>{escape(title)}</h1>")
    h.append(f"<p class='meta'>Revision {link(rec['permalink'], str(rec['revision']))} of "
             f"{escape(rec['revision_timestamp'][:10])} · computed {escape(rec['computed'])} · "
             f"topic area: {escape(rec['topic_area'] or 'none')} · "
             f"{link(f'{rec['revision']}.json', 'JSON record')}"
             + (f" · {link(summary_href, 'all articles compared')}" if summary_href else "")
             + "</p>")
    h.append("<p class='small'>Who wrote the text you read, and whether Wikipedia later "
             "sanctioned any of those editors. Editors are shown as neutral labels; every figure "
             "links to the revisions or decisions behind it. A sanction is a fact about conduct, "
             "not proof that any sentence is wrong.</p>")

    # --- at a glance ---
    top5 = a["top_shares"]["5"]
    h.append("<ul class='facts'>")
    h.append(f"<li>{a['total_words']:,} words of readable prose, written by "
             f"{a['editor_count']:,} editors.</li>")
    h.append(f"<li>The top 5 editors wrote {pct(top5)} of the text"
             f"{base(baseline, 'authorship.top_shares.5')}; "
             f"{a['editors_for_50pct']} editors wrote half of it.</li>")
    h.append(f"<li>The lead ({a['lead_words']:,} words) was written by "
             f"{a['lead_editor_count']} editors; the top 3 wrote "
             f"{pct(a['lead']['top_shares']['3'])}{base(baseline, 'authorship.lead.top_shares.3')}."
             f"</li>")
    h.append(f"<li>{pct(a['sanctioned_share'])} of the current text"
             f"{base(baseline, 'authorship.sanctioned_share')} and "
             f"{pct(a['sanctioned_lead_share'])} of the lead"
             f"{base(baseline, 'authorship.sanctioned_lead_share')} was written by "
             f"{len(sanctioned_eds)} editors whom Wikipedia sanctioned (topic ban in this area, "
             f"site ban, or sockpuppetry finding). {len(lead_sanct)} of {len(lead_sents)} lead "
             f"sentences contain words by them.</li>")
    t = acc["timing"]
    tot_s = t["added_before_sanction_words"] + t["added_after_sanction_words"]
    if tot_s:
        h.append(f"<li>Of those words, {pct(t['added_before_sanction_words'] / tot_s)} were "
                 f"added before the editor's first sanction and "
                 f"{pct(t['added_after_sanction_words'] / tot_s)} after it.</li>")
    sv = a["survival_article"]["30d"]["rate"]
    h.append(f"<li>On this article, {pct(sv)} of words added stay at least 30 days"
             f"{base(baseline, 'authorship.survival_article.30d.rate')}.</li>")
    h.append("</ul>")
    if baseline:
        h.append(f"<p class='small'>Figures in brackets: {escape(baseline['label'])} "
                 f"({escape(', '.join(baseline['articles']))}), so no number is read alone.</p>")

    # --- concentration ---
    h.append("<h2>A. Authorship concentration</h2><div class='scroll'><table><tr><th></th>"
             "<th class='n'>Top 1</th><th class='n'>Top 3</th><th class='n'>Top 5</th>"
             "<th class='n'>Top 10</th><th class='n'>HHI</th><th class='n'>Editors for 50%</th>"
             "<th class='n'>Editors for 80%</th></tr>")
    for name, block, prefix in (("Whole article", a, "authorship"),
                                ("Lead only", a["lead"], "authorship.lead")):
        row = [f"<td>{name}</td>"]
        for n in ("1", "3", "5", "10"):
            row.append(f"<td class='n'>{pct(block['top_shares'][n])}"
                       f"{base(baseline, f'{prefix}.top_shares.{n}')}</td>")
        row.append(f"<td class='n'>{block['hhi']:.3f}</td>")
        row.append(f"<td class='n'>{block['editors_for_50pct']}</td>"
                   f"<td class='n'>{block['editors_for_80pct']}</td>")
        h.append("<tr>" + "".join(row) + "</tr>")
    h.append("</table></div>")
    types = ", ".join(f"{k} {pct(v)}" for k, v in a["account_types"].items())
    h.append(f"<p class='small'>Text by account type: {escape(types)}. HHI is the "
             "Herfindahl index of shares (1 = one editor wrote everything).</p>")

    # --- editors ---
    h.append("<h2>Editors with the most surviving text</h2>")
    h.append("<p class='small'>Survival: share of all words the editor ever added here that were "
             "still present 30 days later, against the article average "
             f"({pct(sv)}). Diffs are the editor's revisions that contributed most "
             "of their surviving text.</p>")
    h.append("<div class='scroll'><table><tr><th>Editor</th><th>Account</th>"
             "<th class='n'>Words</th><th class='n'>Share</th><th class='n'>Lead share</th>"
             "<th class='n'>30-day survival</th><th>Sanctions</th><th>Evidence</th></tr>")
    shown = eds[:25] + [e for e in eds[25:] if e["sanctioned"]]
    for e in shown:
        s30 = e["survival"]["30d"]
        ratio = "" if s30["vs_article"] is None else f"×{s30['vs_article']:.2f}, "
        surv = "–" if s30["rate"] is None else (
            f"{pct(s30['rate'], 0)} <span class='base'>({ratio}n={s30['words_added']:,})</span>")
        h.append(f"<tr><td>{escape(e['label'])}</td><td>{escape(e['account_type'])}</td>"
                 f"<td class='n'>{e['words']:,}</td><td class='n'>{pct(e['share'])}</td>"
                 f"<td class='n'>{pct(e['lead_share'])}</td><td class='n'>{surv}</td>"
                 f"<td>{sanction_cell(e)}</td>"
                 f"<td>{' '.join(diff_link(r) for r in e['top_revisions'])}</td></tr>")
    h.append("</table></div>")
    if len(eds) > len(shown):
        h.append(f"<p class='small'>{len(eds) - len(shown):,} more editors are listed in the "
                 "JSON record.</p>")

    # --- accountability ---
    h.append("<h2>B. Accountability</h2>")
    h.append("<div class='scroll'><table><tr><th>Sanction type</th><th class='n'>Words</th>"
             "<th class='n'>Share of text</th><th class='n'>Share of lead</th></tr>")
    for k in ("topic_ban", "site_ban", "sockpuppet"):
        b = acc["by_type"][k]
        h.append(f"<tr><td>{TYPE_NAMES[k]}</td><td class='n'>{b['words']:,}</td>"
                 f"<td class='n'>{pct(b['share'])}</td><td class='n'>{pct(b['lead_share'])}</td></tr>")
    h.append(f"<tr><td><b>any of these</b></td><td class='n'>{acc['sanctioned_words']:,}</td>"
             f"<td class='n'>{pct(acc['sanctioned_share'])}</td>"
             f"<td class='n'>{pct(acc['sanctioned_lead_share'])}</td></tr></table></div>")
    sl = acc["sanctions_list"]
    h.append(f"<p class='small'>Rule: {escape(acc['rule'])}. An editor can hold several "
             f"sanctions, so the rows overlap. Sources: hand-verified seed list "
             f"({sl['seed_rows_total']} rows, {sl['seed_rows_in_topic_area']} in this topic area) "
             f"and Wikipedia's block log (indefinite sitewide blocks whose logged reason cites "
             f"sockpuppetry or a ban; snapshot {escape(sl['block_log_snapshot'])}). Text by "
             f"sanctioned editors from the block log: "
             f"{pct(acc['by_source']['block_log']['share'])}; from the seed list: "
             f"{pct(acc['by_source']['seed_list']['share'])}.</p>")

    # --- sentences ---
    def sent_rows(rows):
        out = ["<div class='scroll'><table><tr><th>ID</th><th>Sentence</th><th>Authors (words)</th>"
               "<th>Sanctioned</th><th>Added in</th></tr>"]
        for s in rows:
            authors = ", ".join(f"{escape(l)} ({n})" for l, n in
                                zip(s["authors"][:4], s["author_words"][:4]))
            if len(s["authors"]) > 4:
                authors += f", +{len(s['authors']) - 4}"
            sanc = ""
            if s["author_sanctioned"]:
                when = {True: "added before sanction", False: "added after sanction",
                        None: "mixed"}[s["added_before_sanction"]]
                sanc = (f"<span class='tag'>{s['sanctioned_words']} of {s['words']} words</span> "
                        f"<span class='small'>{when}</span>")
            out.append(f"<tr><td class='small'>{escape(s['id'])}</td><td>{escape(s['text'])}</td>"
                       f"<td class='small'>{authors}</td><td>{sanc}</td>"
                       f"<td class='small'>{diff_link(s['added_revision'])}</td></tr>")
        out.append("</table></div>")
        return "".join(out)

    h.append("<h2>Lead sentences</h2><p class='small'>“Added in” is the revision that "
             "contributed the most words to the sentence.</p>")
    h.append(sent_rows(lead_sents))
    body_s = [s for s in rec["sentences"] if not s["id"].startswith("lead-") and s["author_sanctioned"]]
    h.append(f"<h2>Body sentences with words by sanctioned editors ({len(body_s):,})</h2>")
    if body_s:
        h.append(f"<details><summary>Show {min(len(body_s), 400):,} sentences</summary>"
                 f"{sent_rows(body_s[:400])}</details>")

    # --- method ---
    q = rec["quality"]
    h.append("<h2>Method and limits</h2><ul class='small'>")
    h.append(f"<li>{escape(a['basis'])}. Templates, references, tables, image captions and "
             "appendix sections (References, See also, External links…) are not counted.</li>")
    h.append("<li>Authorship comes from WikiWho, which credits a word to the revision that first "
             "added it, even if it was later removed and restored.</li>")
    h.append(f"<li>Data quality: {q['wikiwho_tokens']:,} WikiWho tokens, "
             f"{q['unaligned_tokens']} could not be placed in the wikitext.</li>")
    h.append("<li>The sanctions seed list covers decisions from 2023 onward and is not complete; "
             "a share of 0% means no matching sanction was found, not that none exists.</li>")
    h.append(f"<li>Inputs: {link(rec['inputs']['wikitext'], 'wikitext')}, "
             f"{link(rec['inputs']['wikiwho_rev_content'], 'WikiWho tokens')}, "
             f"{rec['inputs']['history_revisions']:,} revisions of history, sanctions file "
             f"sha256 {escape(rec['inputs']['sanctions_csv_sha256'][:12])}…</li>")
    h.append("</ul></main></body></html>\n")
    return "".join(h)
