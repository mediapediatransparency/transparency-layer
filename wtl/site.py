"""Public website (GitHub Pages) built from the stored records: home, article pages, comparison,
how it works, objective, about. Written for journalists and general readers: every figure is a
full sentence that names what it is a share *of*, with the comparison figures beside it.

Anonymity: editors appear only as per-article labels. Usernames may appear only inside link
targets (diffs, decisions) that Wikipedia already publishes; `wtl check` scans these pages too.
"""

import json
import re
import shutil
from html import escape
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


def cap(s):
    return s[:1].upper() + s[1:]

CSS = """
:root{--bg:#fbfbf9;--fg:#1d1d1b;--muted:#5d5d58;--line:#dcdbd5;--soft:#f1f0eb;--link:#1f4e8c;
--bar:#4a6fa5;--bar2:#b9c7dc;--note:#fff8e6;--noteline:#e2c46f}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#171715;--fg:#e9e8e3;
--muted:#a8a79f;--line:#3a3935;--soft:#22221f;--link:#93b8ec;--bar:#7f9fd0;--bar2:#3b4a62;
--note:#2a2516;--noteline:#7a6524}}
:root[data-theme="dark"]{--bg:#171715;--fg:#e9e8e3;--muted:#a8a79f;--line:#3a3935;--soft:#22221f;
--link:#93b8ec;--bar:#7f9fd0;--bar2:#3b4a62;--note:#2a2516;--noteline:#7a6524}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 Georgia,"Iowan Old Style",serif}
header.site{border-bottom:1px solid var(--line);background:var(--soft)}
header.site .in{max-width:860px;margin:0 auto;padding:12px 16px;display:flex;flex-wrap:wrap;
gap:6px 18px;align-items:baseline;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
header.site .brand{font-weight:700;color:var(--fg);text-decoration:none;margin-right:auto}
header.site nav a{color:var(--link);text-decoration:none;font-size:.95rem;margin-right:14px}
header.site nav a[aria-current]{color:var(--fg);font-weight:600}
main{max-width:860px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:2rem;line-height:1.2;margin:8px 0 6px}
h2{font-size:1.35rem;margin:40px 0 10px;padding-top:14px;border-top:1px solid var(--line)}
h3{font-size:1.08rem;margin:24px 0 6px}
p,li{max-width:70ch}
a{color:var(--link)}
.sans,table,.meta,.small,.note,.fig,details summary,footer{font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
.meta{color:var(--muted);font-size:.9rem}
.small{font-size:.88rem;color:var(--muted)}
.lede{font-size:1.12rem}
.brief{background:var(--soft);border:1px solid var(--line);border-radius:8px;padding:6px 20px;margin:18px 0}
.brief li{margin:8px 0}
.fig{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}
.fig .box{flex:1 1 180px;border:1px solid var(--line);border-radius:8px;padding:10px 14px}
.fig .num{font-size:1.7rem;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.2}
.fig .lbl{font-size:.88rem}
.fig .cmp{font-size:.82rem;color:var(--muted);margin-top:4px}
.note{background:var(--note);border-left:4px solid var(--noteline);padding:8px 14px;margin:12px 0;
font-size:.92rem;border-radius:0 6px 6px 0;max-width:70ch}
.note b{font-weight:600}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:10px 0}
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
footer .in{max-width:860px;margin:0 auto;padding:16px}
@media (max-width:520px){h1{font-size:1.6rem}.bars .row{grid-template-columns:70px 1fr 48px}}
"""

PAGES = [("index.html", "Home"), ("compare.html", "All articles"), ("editors.html", "Editors across articles"),
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
    nav = "".join(f'<a href="{up}{href}"' + (' aria-current="page"' if href == current else "")
                  + f">{escape(name)}</a>" for href, name in PAGES)
    alt = (f'<link rel="alternate" type="application/json" href="{escape(json_alt, quote=True)}">'
           if json_alt else "")
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{escape(title)}</title>"
            f"<meta name='description' content='{escape(description, quote=True)}'>{alt}"
            f"<style>{CSS}</style></head><body>"
            f"<header class='site'><div class='in'><a class='brand' href='{up}index.html'>"
            f"{escape(NAME)}</a><nav>{nav}</nav></div></header><main>{body}</main>"
            f"<footer><div class='in'>An independent project. Not affiliated with Wikipedia or "
            f"the Wikimedia Foundation. Figures are computed by open code from Wikipedia's public "
            f"records; {link(REPO, 'source code and data')}.</div></footer></body></html>\n")


def median(vals):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    m = len(vals) // 2
    return vals[m] if len(vals) % 2 else (vals[m - 1] + vals[m]) / 2


class Context:
    """All records plus the typical (median) values per group, for comparisons."""

    def __init__(self, recs, groups, patterns=None):
        self.recs, self.groups, self.patterns = recs, groups, patterns
        self.by_group = {g: [r for r in recs if groups[r["article"]] == g] for g in GROUP_NAMES}

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
        nt, nc = len(self.by_group["topic"]), len(self.by_group["control"])
        bits = []
        t = self.med("topic", path)
        if t is not None and not (sanction and self.thin("topic")):
            bits.append(f"{fmt(t)} across the {nt} Arab–Israeli conflict articles")
        c = self.med("control", path)
        if c is not None and not (sanction and self.thin("control")):
            bits.append(f"{fmt(c)} across the {nc} comparison articles")
        out = "Typical (median): " + " and ".join(bits) + "." if bits else ""
        if sanction and self.thin("control") and c is not None:
            out += (" Not compared with the comparison articles: their sanctions lists are not "
                    "yet as thorough.")
        return out.strip()


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
        s += (f" The largest contributor among them, {c['editor']}, wrote "
              f"{p1(c['share_of_article'])} of the whole article, which is "
              f"{p0(c['share_of_sanctioned_text'])} of the sanctioned editors' text; the other "
              f"{p0(rest)} comes from the remaining {n - 1}.")
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
    h.append(f"<p class='meta'>{escape(GROUP_ONE[group])} · "
             f"{link(wp, 'Read it on Wikipedia')}</p>")
    h.append(f"<h1>{escape(title)}</h1>")
    h.append(f"<p class='meta'>Figures describe the article as it stood on {escape(date)} "
             f"({link(rec['permalink'], 'that exact version')}). Computed {escape(rec['computed'])}. "
             f"{link(f'../data/{slug(title)}.json', 'Full data (JSON)')}.</p>")

    # ---- in brief
    h.append("<h2 style='border:0;margin-top:20px'>In brief</h2><ul class='brief'>")
    h.append(f"<li>The article has {num(a['total_words'])} words of readable text. "
             f"{num(a['editor_count'])} different editors wrote the words that are still there.</li>")
    h.append(f"<li><b>Half of the text was written by {a['editors_for_50pct']} "
             f"editor{'s' if a['editors_for_50pct'] != 1 else ''}.</b> The single largest "
             f"contributor wrote {p1(a['top_shares']['1'])} of it.</li>")
    h.append(f"<li>{escape(sanctioned_sentence(rec))}</li>")
    if lead_sents:
        h.append(f"<li>In the opening section, which most readers see first, "
                 f"{len(lead_sanct)} of {len(lead_sents)} sentences contain words by a sanctioned "
                 f"editor ({p1(acc['sanctioned_lead_share'])} of the opening's words).</li>")
    h.append(f"<li>Of all the words ever added to this article, {p1(sv30)} were still there 30 "
             f"days later.</li>")
    h.append("</ul>")
    h.append("<p class='small'>Editors are shown as neutral labels: Editor 1 has the most "
             "surviving text in this article, Editor 2 the next most, and so on. The labels are "
             "per article, so Editor 1 here is not the same person as Editor 1 on another page. "
             "A sanction is a finding about an editor's conduct on Wikipedia, not proof that any "
             "sentence they wrote is wrong.</p>")

    # ---- who wrote it
    h.append("<h2>Who wrote the text</h2>")
    h.append("<p>Each word in today's article is credited to the editor who first added it. The "
             "shares below are shares of the article's current words.</p>")
    h.append("<div class='fig'>")
    h.append(fig(str(a["editors_for_50pct"]), "editors wrote half of the text",
                 ctx.cmp("authorship.editors_for_50pct", fmt=lambda v: f"{v:g} editors")))
    h.append(fig(p1(a["top_shares"]["1"]), "of the text is by the single largest contributor",
                 ctx.cmp("authorship.top_shares.1")))
    h.append(fig(p1(a["top_shares"]["10"]), "of the text is by the top 10 editors together",
                 ctx.cmp("authorship.top_shares.10")))
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

    # ---- lead
    h.append("<h2>The opening section</h2>")
    h.append(f"<p>The opening section (Wikipedia calls it the lead) is the summary at the top. "
             f"Search engines and AI assistants quote it most. Here it has "
             f"{num(a['lead_words'])} words by {a['lead_editor_count']} editors.</p>")
    h.append("<div class='fig'>")
    h.append(fig(p1(lead["top_shares"]["3"]), "of the opening was written by its top 3 editors",
                 ctx.cmp("authorship.lead.top_shares.3")))
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
        h.append("<h3>Before or after the sanction</h3>")
        h.append(f"<p>Of the words by sanctioned editors, {p1(t['added_before_sanction_words'] / tot_t)} "
                 f"were added before that editor's first sanction and "
                 f"{p1(t['added_after_sanction_words'] / tot_t)} after it.</p>")
        h.append(caveats_for(rec, "timing"))

    # ---- survival
    h.append("<h2>How long new text lasts</h2>")
    surv = a["survival_article"]
    h.append("<p>This counts every word ever added to the article, including words later removed, "
             "and asks how many were still there after a given time.</p>")
    h.append("<div class='fig'>")
    for key, lbl in (("48h", "still there after 2 days"), ("30d", "still there after 30 days"),
                     ("365d", "still there after a year")):
        h.append(fig(p1(surv[key]["rate"]), lbl, ctx.cmp(f"authorship.survival_article.{key}.rate")))
    h.append("</div>")

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
        sanc = "<br>".join(
            f"<span class='tag'>{escape(TYPE_NAMES.get(s['type'], s['type']))}</span> "
            f"{escape(s['date'])} {link(s['evidence'], 'decision')}" for s in e["sanctions"])
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
               "<th>Sanctioned editor's words</th><th>Edit</th></tr>"]
        for s in rows:
            authors = ", ".join(f"{escape(l)} ({n})" for l, n in zip(s["authors"][:4], s["author_words"][:4]))
            if len(s["authors"]) > 4:
                authors += f", and {len(s['authors']) - 4} more"
            sanc = ""
            if s["author_sanctioned"]:
                when = {True: "added before the sanction", False: "added after the sanction",
                        None: "some before, some after"}[s["added_before_sanction"]]
                sanc = f"{s['sanctioned_words']} of {s['words']} <span class='small'>({when})</span>"
            out.append(f"<tr><td>{escape(s['text'])}</td><td class='small'>{authors}</td>"
                       f"<td class='small'>{sanc}</td><td class='small'>"
                       f"{link(WIKI + '/w/index.php?diff=prev&oldid=' + str(s['added_revision']), 'view')}</td></tr>")
        out.append("</table></div>")
        return "".join(out)

    h.append("<h2>Sentence by sentence</h2>")
    h.append("<p class='small'>For each sentence: who wrote its words, how many of them are by a "
             "sanctioned editor, and a link to the edit that added most of it, so you can check it "
             "yourself. Text inside templates (for example unit conversions) is not counted, so a "
             "few sentences show small gaps such as empty brackets.</p>")
    h.append(f"<details open><summary>Opening section ({len(lead_sents)} sentences)</summary>"
             f"{sent_table(lead_sents)}</details>")
    body_s = [s for s in rec["sentences"] if not s["id"].startswith("lead-") and s["author_sanctioned"]]
    if body_s:
        h.append(f"<details><summary>Rest of the article: the {num(len(body_s))} sentences with "
                 f"words by sanctioned editors</summary>{sent_table(body_s)}</details>")

    ov = ctx.patterns["overlap"].get(title) if ctx.patterns else None
    if ov:
        h.append("<h2>Where else this article's editors write</h2>")
        h.append("<p>Each row shows how much of <i>this</i> article's text was written by editors "
                 "who also have text in the other article.</p>")
        h.append("<div class='bars'>")
        for other, v in sorted(ov.items(), key=lambda x: -x[1]):
            h.append(f"<div class='row' style='grid-template-columns:minmax(120px,190px) 1fr 54px'>"
                     f"<span>{link(slug(other) + '.html', other)}</span><span class='track'>"
                     f"<span class='fill' style='display:block;width:{v * 100:.1f}%'></span></span>"
                     f"<span class='v'>{p0(v)}</span></div>")
        h.append(f"</div><p class='small'>Individual editors' patterns across articles are on "
                 f"{link('../editors.html', 'Editors across articles')}.</p>")

    h.append("<h2>About these numbers</h2>")
    h.append(f"<p class='small'>Computed from {num(rec['inputs']['history_revisions'])} revisions of "
             f"the article's history, the word-level authorship service WikiWho, and a "
             f"hand-checked list of sanctions. No AI is used to produce any figure. See "
             f"{link('../how-it-works.html', 'How it works')} for the method and its limits, and "
             f"the {link(f'../data/{slug(title)}.json', 'full data')} for every number with its "
             f"source.</p>")
    desc = f"Who wrote the Wikipedia article {title}: authorship, concentration and sanctioned editors."
    return page(f"{title} · {NAME}", "".join(h), "", depth=1,
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


def compare_page(ctx: Context):
    cols = ctx.by_group["topic"] + ctx.by_group["control"]
    h = ["<h1>All articles side by side</h1>",
         "<p>Every figure is computed the same way for every article. The six Arab–Israeli "
         "conflict articles are shown next to three comparison articles: two on other contested "
         "subjects and one quiet science article. That way no figure is read in isolation.</p>",
         note("Sanction figures are only comparable between articles whose sanctions lists were "
              "built equally thoroughly (last row). Where they were not, the figure is marked † "
              "and no group median is given.", "Sanction figures"),
         "<div class='scroll'><table><tr><th>Figure</th>"]
    for r in cols:
        h.append(f"<th class='n'><a href='articles/{slug(r['article'])}.html'>{escape(r['article'])}</a></th>")
    h.append("<th class='n'>Typical, Arab–Israeli</th><th class='n'>Typical, comparison</th>"
             "<th>What it means</th></tr>")
    for path, name, kind, expl in COMPARE_ROWS:
        sanction = path in SANCTION_PATHS
        h.append(f"<tr><td>{escape(name)}</td>")
        for r in cols:
            mark = " †" if sanction and any(c["code"] in THIN for c in r.get("caveats", [])) else ""
            h.append(f"<td class='n'>{fmt(get(r, path), kind)}{mark}</td>")
        med = {g: ("not compared" if sanction and ctx.thin(g) else fmt(ctx.med(g, path), kind))
               for g in ("topic", "control")}
        h.append(f"<td class='n'><b>{med['topic']}</b></td><td class='n'><b>{med['control']}</b></td>"
                 f"<td class='expl'>{escape(expl)}</td></tr>")
    h.append("<tr><td>Version analysed</td>" + "".join(
        f"<td class='n small'>{link(r['permalink'], r['revision_timestamp'][:10])}</td>" for r in cols)
        + "<td></td><td></td><td></td></tr></table></div>")
    h.append("<p class='small'>† Sanctions list for this article's area not yet as thorough as "
             "for the Arab–Israeli conflict (or the article is in no sanctioned area), so the "
             "figure is likely an undercount. Medians for sanction figures are not shown for a "
             "group containing such articles.</p>")
    h.append("<p class='small'>“Typical” is the median: the middle value of the group. With "
             "only six and three articles, treat the comparison as a first indication, not a "
             "measurement of whole topic areas.</p>")
    h.append(f"<p class='small'>{link('data/summary.json', 'All figures as JSON')}.</p>")
    return page(f"All articles · {NAME}", "".join(h), "compare.html",
                json_alt="data/summary.json", description="Wikipedia articles compared side by side.")


# ---------------------------------------------------------------- editors across articles
def editors_page(ctx: Context):
    pt = ctx.patterns
    rule = pt["rule"]
    arts = [r["article"] for r in ctx.recs]
    h = ["<h1>Editors across articles</h1>",
         "<p class='lede'>How editors' text is spread across the analysed articles. This page "
         "shows the data only and draws no conclusions from it.</p>",
         note("Editors here are shown under pattern IDs (for example K7Q2MX). Pattern IDs are "
              "different from the “Editor 1, Editor 2” labels on article pages, the page has no "
              "links, shares are shown as ranges, and editors Wikipedia has not sanctioned are "
              "shown by topic group rather than by article. This page is not designed to identify anyone, and "
              "does not make it easy. Everything here comes from Wikipedia's public edit "
              "histories, which anyone can analyse with their own tools. Please do not contact, "
              "harass or target any editor; concerns about conduct belong in Wikipedia's own "
              "processes.", "About these IDs"),
         f"<p class='small'>Based on the {rule['articles_analysed']} articles analysed so far, so "
         f"an editor's work on other articles is not counted. The same rules apply to every "
         f"editor.</p>"]

    # level 1
    h.append("<h2>Overlap between articles</h2>")
    h.append("<p>Read across a row: the share of that article's text written by editors who also "
             "have text in the column's article.</p>")
    h.append("<div class='scroll'><table><tr><th>Article</th>" + "".join(
        f"<th class='n'>{escape(a)}</th>" for a in arts) + "</tr>")
    for a in arts:
        h.append(f"<tr><td>{link('articles/' + slug(a) + '.html', a)}</td>" + "".join(
            "<td class='n'>—</td>" if a == b else f"<td class='n'>{p0(pt['overlap'][a][b])}</td>"
            for b in arts) + "</tr>")
    h.append("</table></div>")

    from .candidates import AREAS
    area_name = {k: v[0] for k, v in AREAS.items()} | {"outside": "outside these areas"}
    show_else = rule.get("elsewhere")

    def table(rows, by_topic=False):
        out = ["<div class='scroll'><table><tr><th>Pattern ID</th><th class='n'>Articles</th>"
               + ("<th>Topic groups where they wrote at least 1% of an article</th>" if by_topic
                  else "<th>Share of each article's text</th>")
               + ("<th>Where they edit across Wikipedia (share of their article edits)</th>"
                  if show_else else "") + "</tr>"]
        for e in rows:
            if by_topic:
                sh = "; ".join(f"{n} of the {m} analysed articles in {escape(g)}"
                               for g, (n, m) in e["topics"].items()) or "–"
            else:
                sh = "; ".join(f"{escape(a)}: {escape(v)}" for a, v in e["shares"].items())
            el = ""
            if show_else:
                x = e.get("elsewhere")
                el = "<td class='small'>" + ("–" if not x else
                     f"{escape(x['edits'])} article edits. " + "; ".join(
                         f"{escape(area_name.get(a, a))}: {escape(v)}" for a, v in x["areas"].items())) + "</td>"
            out.append(f"<tr><td><code>{e['id']}</code></td><td class='n'>{e['articles_with_text']}"
                       f"</td><td class='small'>{sh}</td>{el}</tr>")
        out.append("</table></div>")
        return "".join(out)

    sanc = [e for e in pt["editors"] if e["sanctioned"]]
    other = [e for e in pt["editors"] if not e["sanctioned"]]
    # level 2
    h.append(f"<h2>Sanctioned editors across articles ({len(sanc)})</h2>")
    h.append("<p>Editors Wikipedia has sanctioned (topic ban, site ban or sockpuppetry finding) "
             "who wrote in more than one analysed article, or a substantial share of one.</p>")
    h.append(f"<details><summary>Show {len(sanc)} editors</summary>{table(sanc)}</details>")
    # level 3
    h.append("<p class='small'><b>Articles</b>: how many analysed articles have any text by this "
             "editor. <b>Share</b>: the range their words make up of each article's current "
             "text.</p>")
    if show_else:
        h.append(f"<p class='small'><b>Where they edit across Wikipedia</b>: of the editor's most "
                 f"recent article edits (up to {rule['edit_cap']:,}), the share made to articles "
                 f"in each contentious area, as tagged by Wikipedia itself on each article's talk "
                 f"page. This counts edits, not words, and covers all of Wikipedia, not only the "
                 f"analysed articles. An article tagged with two areas counts in both, so shares "
                 f"can add up to more than 100%. Areas under 1% are not listed.</p>")
    h.append(f"<h2>Substantial contributors across articles ({len(other)})</h2>")
    h.append(f"<p>Editors <b>not</b> sanctioned by Wikipedia who wrote at least "
             f"{rule['min_share'] * 100:.0f}% of the text of at least {rule['min_articles']} "
             f"analysed articles. Being listed here says only that; it is not a finding about "
             f"the editor.</p>")
    h.append(f"<p class='small'>These editors are shown by topic group, not by article, so a row "
             f"cannot be matched to an article page. A group is shown only if it holds at least "
             f"{rule['min_group']} analysed articles; smaller groups are merged or left out.</p>")
    h.append(table(other, by_topic=True) if other else "<p>None so far.</p>")
    return page(f"Editors across articles · {NAME}", "".join(h), "editors.html",
                description="How editors' work spans the analysed articles.")


# ---------------------------------------------------------------- home
def home_page(ctx: Context):
    h = [f"<h1>Who wrote what you read on Wikipedia?</h1>",
         "<p class='lede'>Wikipedia shows the current text of an article but not, at a glance, "
         "how it came to say it. This project works that out from Wikipedia's own public "
         "records: who wrote the words that are there today, how concentrated that writing is, "
         "and how much of it comes from editors Wikipedia later sanctioned for their conduct.</p>",
         "<p>It does not judge whether articles are right or wrong, or whether editors are good "
         "or bad. It shows where the text came from, with a link to the evidence for every "
         f"number. {link('how-it-works.html', 'How it works')} · "
         f"{link('objective.html', 'Why this matters for AI')}</p>"]
    for g in ("topic", "control"):
        h.append(f"<h2>{escape(cap(GROUP_NAMES[g]))}</h2>")
        if g == "control":
            h.append("<p class='small'>Included so the figures above can be compared with articles "
                     "outside the Arab–Israeli topic area.</p>")
        h.append("<div class='cards'>")
        for r in ctx.by_group[g]:
            a, acc = r["authorship"], r["accountability"]
            c = acc.get("concentration")
            extra = ""
            if c and acc["sanctioned_editors"] > 1 and c["share_of_sanctioned_text"] >= 0.5:
                extra = f" Most of it ({p0(c['share_of_sanctioned_text'])}) is from one editor."
            h.append(f"<div class='card'><h3><a href='articles/{slug(r['article'])}.html'>"
                     f"{escape(r['article'])}</a></h3>"
                     f"<p>Half the text by <b>{a['editors_for_50pct']}</b> of {num(a['editor_count'])} editors.</p>"
                     f"<p><b>{p1(acc['sanctioned_share'])}</b> of the words by "
                     f"{acc['sanctioned_editors']} sanctioned editors.{escape(extra)}</p>"
                     f"<p class='small'>As of {escape(r['revision_timestamp'][:10])}</p></div>")
        h.append("</div>")
    h.append(f"<p>{link('compare.html', 'See all figures side by side')}, with the comparison "
             "articles and an explanation of each figure.</p>")
    return page(NAME, "".join(h), "index.html",
                description="Who wrote the text of Wikipedia articles, from Wikipedia's public records.")


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


def how_page(ctx: Context):
    c = _check_results()
    n = c.get("articles", len(ctx.recs))
    h = ["<h1>How it works</h1>",
         "<p class='lede'>Every figure on this site is produced by ordinary, open software from "
         "Wikipedia's public records. No AI is used to produce, select or word any figure, and "
         "the same input always gives exactly the same result.</p>",
         "<h2>The steps</h2><ol>",
         "<li><b>Take one exact version of the article.</b> Each page names the version and date it "
         "describes, with a link, so anyone can open the same text.</li>",
         "<li><b>Credit every word to the editor who first added it.</b> This uses "
         f"{link('https://wikiwho-api.wmcloud.org/', 'WikiWho')}, a word-matching service run on "
         "Wikimedia's servers that follows each word through the article's whole edit history. "
         "A word that was removed and later restored is still credited to whoever first wrote it. "
         "Moving a paragraph does not make the mover its author.</li>",
         "<li><b>Count readable text only.</b> References, tables, image captions, templates and "
         "lists of links are left out, so the figures describe the prose people actually read.</li>",
         "<li><b>Check each editor against a list of sanctions.</b> Topic bans are not in any single "
         "Wikipedia log, so they come from a hand-checked list built from Wikipedia's arbitration "
         "and enforcement records. Every entry links to the decision and quotes it. Site bans and "
         "sockpuppetry findings also come from Wikipedia's block log.</li>",
         "<li><b>Compare.</b> The same figures are computed for comparison articles outside the "
         "topic, so a number is never read without context.</li></ol>",
         "<h2>What is and isn't AI</h2>",
         "<p>The analysis itself contains no AI model: it is counting and matching, the same each "
         "time it runs. AI was used in building the project: the code and the first drafts of "
         "this site's text were written with Claude, an AI assistant, and then checked as "
         "described below. The checks exist so that you do not have to trust the code, or "
         "whoever wrote it.</p>",
         "<h2>How the work is checked</h2><ul>"]
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
    h.append("<h2>Rules the project follows</h2><ul>"
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
    h.append("<h2>Limits</h2><ul>"
             "<li><b>The sanctions list is not complete.</b> It covers decisions from 2023 on, and "
             "is fullest for the Arab–Israeli conflict area. A figure of 0% means no sanction was "
             "found, not that none exists. Article pages flag where this matters.</li>"
             "<li><b>A sanction is about conduct, not content.</b> It is a finding about how an editor "
             "behaved, not about the accuracy of any text they wrote.</li>"
             "<li><b>Few comparison articles.</b> Three comparison articles give context, not a "
             "full baseline for a topic area.</li>"
             "<li><b>A snapshot.</b> Each page describes one version. Wikipedia keeps changing, "
             "and the date is shown on every page.</li></ul>")
    h.append(f"<p>Full method, definitions and code: {link(REPO, 'the project repository')}.</p>")
    return page(f"How it works · {NAME}", "".join(h), "how-it-works.html",
                description="Method, checks and limits.")


# ---------------------------------------------------------------- objective, about
def objective_page():
    h = ["<h1>Objective</h1>",
         "<p class='lede'>AI assistants and search engines lean heavily on Wikipedia. They learn "
         "from it, quote it and summarise it, often without telling you. They take in the text, "
         "but not how it got there.</p>",
         "<p>For most articles that doesn't matter much. For contested subjects it can: a "
         "sentence might be the settled work of hundreds of editors, or the wording of a single "
         "editor that nobody has yet challenged. Readers, and the AI systems that read on their "
         "behalf, have no easy way to tell the difference.</p>",
         "<h2>What this project adds</h2>",
         "<p>For each article it analyses, it publishes how the text came to be, as plain pages "
         "and as structured data that software can read:</p><ul>"
         "<li>who wrote the current text, and how concentrated that writing is;</li>"
         "<li>how much comes from editors Wikipedia itself later sanctioned;</li>"
         "<li>how stable the text has been;</li>"
         "<li>and later, which sources it rests on and how it was disputed.</li></ul>",
         "<p>An AI system or a journalist that retrieves an article can then retrieve its history "
         "alongside it, and weigh the text accordingly.</p>",
         "<h2>What it is not</h2>",
         "<p>It does not decide what is true, rate articles as biased or neutral, or pass "
         "judgment on editors. It cannot make AI objective on its own. What it can do is make "
         "one of AI's main sources more transparent, so that people and machines can judge "
         "for themselves.</p>",
         "<h2>Where it is going</h2><ol>"
         "<li><b>Now:</b> authorship and sanctions for a test set of articles (this site).</li>"
         "<li><b>Next:</b> a free browser add-on that shows this panel on the Wikipedia page "
         "itself, plus edit wars, removed content and source inventories.</li>"
         "<li><b>Later:</b> who set Wikipedia's source ratings, coordination signals, and checks "
         "of whether sentences match their sources.</li></ol>"]
    return page(f"Objective · {NAME}", "".join(h), "objective.html",
                description="Why the provenance of Wikipedia text matters for AI.")


def about_page():
    h = ["<h1>About</h1>",
         f"<p class='lede'>{escape(NAME)} is an independent, non-commercial project that shows how "
         "Wikipedia articles came to say what they say.</p>",
         "<h2>Status</h2>",
         "<p>This is an early prototype covering a small test set of articles. Figures and wording "
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
    pt = patterns_mod.compute(clean, groups, areas or {}, elsewhere=elsewhere, kinds=kinds)
    ctx = Context(clean, groups, pt)
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


def _write(SITE_DIR, clean, ctx):
    for r in clean:
        (SITE_DIR / "articles" / f"{slug(r['article'])}.html").write_text(article_page(r, ctx), encoding="utf-8")
        (SITE_DIR / "data" / f"{slug(r['article'])}.json").write_text(json_writer.dumps(r), encoding="utf-8")
    shutil.copy(OUT_DIR / "summary.json", SITE_DIR / "data" / "summary.json")
    (SITE_DIR / "index.html").write_text(home_page(ctx), encoding="utf-8")
    (SITE_DIR / "compare.html").write_text(compare_page(ctx), encoding="utf-8")
    (SITE_DIR / "editors.html").write_text(editors_page(ctx), encoding="utf-8")
    (SITE_DIR / "how-it-works.html").write_text(how_page(ctx), encoding="utf-8")
    (SITE_DIR / "objective.html").write_text(objective_page(), encoding="utf-8")
    (SITE_DIR / "about.html").write_text(about_page(), encoding="utf-8")
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")
