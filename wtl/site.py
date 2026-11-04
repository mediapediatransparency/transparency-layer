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
tr.sum td{background:var(--soft);border-top:1px solid var(--line)}
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

PAGES = [("index.html", "Home"), ("compare.html", "All articles"), ("articles.html", "Which articles"),
         ("editors.html", "Editors across articles"), ("sources.html", "Sources"),
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
        out = "Typical (median): " + " and ".join(bits) + "." if bits else ""
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
        return ("Typical (median): " + "; ".join(bits) + ".") if bits else ""


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
    kind = ctx.kinds.get(title)
    label = (f"{kind_name(kind, plural=False)} · {area_name(ctx.areas.get(title))}" if kind
             else GROUP_ONE.get(group, area_name(ctx.areas.get(title))))
    h.append(f"<p class='meta'>{escape(label)} · "
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

    # ---- sources
    h.append(sources_section(rec, ctx))

    # ---- removals, wording changes, declared interests
    h.append(changes_section(rec, ctx))
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
               "<th>Sanctioned editor's words</th><th>Edit</th></tr>"]
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
                h.append("<tr><td><b>Typical (median)</b></td>")
                for path, _, k in TABLE_COLS:
                    if path in SANCTION_PATHS and any(_is_thin(r) for r in rows):
                        h.append("<td class='n small'>not compared</td>")
                    else:
                        h.append(f"<td class='n'><b>{fmt(median([get(r, path) for r in rows]), k)}</b></td>")
                h.append("</tr>")
            h.append("</table></div>")
    h.append("<p class='small'>† Sanctions list for this article's area not yet as thorough as "
             "for the Arab–Israeli conflict (or the article is in no sanctioned area), so the "
             "figure is likely an undercount.</p>")
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
         "politics, gender and sexuality, Eastern Europe). It does this with notices on the "
         "articles' talk pages. Every article carrying such a notice is a candidate.</li>",
         "<li><b>Kind of subject.</b> Each candidate is classed as a journalist or commentator, "
         "another public figure, a news outlet, an organisation, an idea or movement, or an event, "
         "using Wikidata (Wikipedia's sister database). Articles that fit none of these, and "
         "“List of…” articles, are left out.</li>",
         "<li><b>Most read.</b> In each area, for each kind, the 25 articles with the most page "
         "views over the previous 60 days are chosen.</li>",
         "<li><b>On request.</b> A few articles are added on request. They are marked as such.</li>",
         "</ol>",
         "<h2>A second rule, for subjects Wikipedia does not tag</h2>"
         "<p>Some subjects have no contentious-topic designation on Wikipedia: China beyond the "
         "Uyghur and Xinjiang area, socialism, communism and Marxism, and Islam. For these, the "
         "candidates are the articles whose talk pages carry the banner of the WikiProject for "
         "the subject (a WikiProject is a group of Wikipedia editors who look after a subject; "
         "the editors who add a banner decide which articles belong). Steps 2 and 3 above are "
         "then the same. These areas are marked “chosen by subject”, because here the project "
         "chose the subjects, not Wikipedia.</p><ul>"
         + "".join(f"<li><b>{escape(n.split(' (')[0])}</b>: "
                   + ", ".join(escape(c.split(':', 1)[1].replace(' articles', '')) for c in cats)
                   + "</li>" for n, cats in SUBJECTS.values())
         + "</ul>",
         note("Wikidata's classification is used as it stands, and is sometimes surprising (for "
              "example, an ideology recorded as an organisation). An article can appear in more "
              "than one area; it is analysed once and listed in each.", "About the classes"),
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
    "Wikipedia's Perennial sources list rates about 530 sources that Wikipedia editors discuss "
    "often. A source not on the list has not been rated there; it is not rated unreliable.",
    "The independent quality score (Lin et al. 2023) covers news websites. Books and academic "
    "journals usually have no score.",
    "The audience score (Robertson et al. 2018) measures which US voters shared a site's links on "
    "Twitter in 2017, not what the site publishes. It is centred on the United States and "
    "covers only sites shared widely enough.",
    "Wikidata records a political alignment or ideology for few outlets, and those entries are "
    "made by volunteers.",
    "All ratings are as of the date of the ratings snapshot, not as of when a citation was added.",
    "Associations come from Wikidata, which anyone can edit; † marks a statement for which "
    "Wikidata cites no source.",
]


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
                if x.get("name_as_cited"):
                    c.setdefault(x["source"], Counter())[x["name_as_cited"]] += x["citations"]
        ctx._cited_names = {k: min(v, key=lambda s: (-v[s], s)) for k, v in c.items()}
    if key in ctx._cited_names and key.startswith("name:"):
        return ctx._cited_names[key]
    if o and o.get("name"):
        return o["name"]
    return key[5:] if key.startswith("name:") else key


def profile(pairs, ctx):
    """Citation-weighted summary of (source key, citations) pairs, one entry per assessor."""
    from collections import Counter
    tot = sum(n for _, n in pairs)
    rating, align, cls, bins = Counter(), Counter(), Counter(), Counter()
    kinds, fact, acad = Counter(), Counter(), Counter()
    q, a = [], []
    for k, n in pairs:
        o = ctx.outlets.get(k) or {}
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
            "alignment": align, "classed": cls, "kinds": kinds, "factual": fact, "academic": acad}


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
    rows.append(("Political alignment recorded on Wikidata", "as entered on Wikidata",
                 _shares(pf["alignment"], tot)))
    if pf["classed"]:
        rows.append(("Classed on Wikidata as", "state media, public broadcaster, state-owned",
                     _shares(pf["classed"], tot)))
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


def _assessor_cells(key, ctx):
    o = ctx.outlets.get(key) or {}
    wr = o.get("wikipedia_rating")
    iq = o.get("independent_quality")
    al = o.get("audience_leaning")
    wd = []
    if o.get("kind"):
        wd.append(f"<b>{escape(o['kind'])}</b>")
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
    rating = RATING_NAMES[wr["status"]] if wr else "–"
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
    return (f"<td class='small'>{escape(rating)}</td><td class='n'>{quality}</td>"
            f"<td class='n'>{audience}</td>"
            f"<td class='small'>{escape(' · '.join(labels) or '–')}</td>"
            f"<td class='n'>{acad}</td>"
            f"<td class='small'>{' · '.join(wd) or '–'}</td>")


ASSESSOR_HEAD = ("<th>Wikipedia's rating</th><th class='n'>Independent quality</th>"
                 "<th class='n'>Audience leaning</th><th>Bias labels</th>"
                 "<th class='n'>Academic level</th><th>Kind and Wikidata facts</th>")


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
              "dead_link_no_archive": "dead link with no archived copy",
              "paywall_or_registration": "behind a paywall or registration"}


def flags_html(s):
    f = s.get("flags")
    if not f:
        return ""
    tot = s["citations"]
    bits = " · ".join(f"{escape(FLAG_NAMES[k])} {num(v)} ({p0(v / tot)})" for k, v in f.items() if v)
    out = [f"<h3>Opinion and harder-to-check citations</h3><p class='small'>Of the article's "
           f"{num(tot)} citations: {bits or 'none'}. Opinion is recognised from the web address "
           "(sections such as /opinion/, /commentisfree/ or blogs) or the citation template; the "
           "others from the citation's own details. These are facts about how a citation can be "
           "checked, not about whether it is right.</p>"]
    rows = [(l, e) for l, e in s.get("flags_by_editor", {}).items() if l != "unknown"][:10]
    if rows:
        out.append("<div class='scroll'><table><tr><th>Editor</th><th class='n'>Citations added</th>"
                   + "".join(f"<th class='n'>{escape(FLAG_NAMES[k])}</th>" for k in FLAG_NAMES) + "</tr>")
        for l, e in rows:
            out.append(f"<tr><td>{escape(l)}</td><td class='n'>{e['citations']}</td>"
                       + "".join(f"<td class='n'>{e[k] or '–'}</td>" for k in FLAG_NAMES) + "</tr>")
        out.append("</table></div><p class='small'>The ten editors who added the most citations "
                   "still in the article.</p>")
    return "".join(out)


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
        h.append("<h3>How the cited sources are rated</h3><p class='small'>Several assessors side "
                 "by side; none of them is this project's. Shares are of the article's "
                 f"{num(s['citations'])} citations. {link('../sources.html', 'About the assessors')}.</p>")
        h.append("<div class='scroll'><table><tr><th>Assessor</th><th>Result</th></tr>")
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
    h.append(flags_html(s))
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
         "citation, and how several assessors rate those sources. No assessor is treated as the "
         "truth, and this project adds no rating of its own.</p>"]
    if not snap:
        h.append("<p>The ratings snapshot has not been built yet.</p>")
        return page(f"Sources · {NAME}", "".join(h), "sources.html")
    wr = asr.get("wikipedia_rating", {})
    h.append("<h2>The assessors</h2><ul>")
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
                     "designation, ratings by Wikipedia and by independent assessors, a Wikipedia "
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
        tbl, tot, nsrc = cited_table(ctx.recs, 100)
        h.append(f"<h3>All areas together</h3><details><summary>{len(ctx.recs):,} articles, "
                 f"{tot:,} citations, {nsrc:,} sources (top 100)</summary>{tbl}</details>")
    h.append(f"<p class='small'>{link('data/outlets.json', 'All ratings as JSON')}.</p>")
    return page(f"Sources · {NAME}", "".join(h), "sources.html", json_alt="data/outlets.json",
                description="Sources cited in the analysed articles, and how several assessors rate them.")


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
    show_src = bool(ctx.outlets)

    def src_cell(x):
        if not x:
            return "–"
        wr = "; ".join(f"{escape(RATING_NAMES.get(k, k) if k != 'not listed' else 'not on the list')} {escape(v)}"
                       for k, v in x["wikipedia_rating"].items())
        bits = [f"{escape(x['citations'])} citations.", f"Wikipedia's rating: {wr}."]
        if x["independent_quality_median"] is not None:
            bits.append(f"Independent quality: median {x['independent_quality_median']:.1f} "
                        f"({escape(x['independent_quality_coverage'])} scored).")
        if x["audience_leaning_median"] is not None:
            bits.append(f"Audience leaning: median {x['audience_leaning_median']:+.1f} "
                        f"({escape(x['audience_leaning_coverage'])} scored).")
        kd = {k: v for k, v in (x.get("kinds") or {}).items() if k != "not classified"}
        if kd:
            bits.append("Kinds of source: " + "; ".join(f"{escape(k)} {escape(v)}" for k, v in kd.items()) + ".")
        al = {k: v for k, v in x["alignment"].items() if k != "none recorded"}
        if al:
            bits.append("Wikidata alignment: " + "; ".join(f"{escape(k)} {escape(v)}" for k, v in al.items()) + ".")
        if x["most_cited"]:
            bits.append("Most cited: " + "; ".join(f"{escape(k)} {escape(v)}" for k, v in x["most_cited"].items()) + ".")
        return " ".join(bits)

    def table(rows, by_topic=False):
        out = ["<div class='scroll'><table><tr><th>Pattern ID</th><th class='n'>Articles</th>"
               + ("<th>Topic groups where they wrote at least 1% of an article</th>" if by_topic
                  else "<th>Share of each article's text</th>")
               + ("<th>Where they edit across Wikipedia (share of their article edits)</th>"
                  if show_else else "")
               + ("<th>Sources they cited in the analysed articles</th>" if show_src else "")
               + "</tr>"]
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
            sc = f"<td class='small'>{src_cell(e.get('sources'))}</td>" if show_src else ""
            out.append(f"<tr><td><code>{e['id']}</code></td><td class='n'>{e['articles_with_text']}"
                       f"</td><td class='small'>{sh}</td>{el}{sc}</tr>")
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
    from .candidates import KINDS
    h = [f"<h1>Who wrote what you read on Wikipedia?</h1>",
         "<p class='lede'>Wikipedia shows the current text of an article but not, at a glance, "
         "how it came to say it. This project works that out from Wikipedia's own public "
         "records: who wrote the words that are there today, how concentrated that writing is, "
         "and how much of it comes from editors Wikipedia later sanctioned for their conduct.</p>",
         "<p>It does not judge whether articles are right or wrong, or whether editors are good "
         "or bad. It shows where the text came from, with a link to the evidence for every "
         f"number. {link('how-it-works.html', 'How it works')} · "
         f"{link('articles.html', 'Which articles, and why')} · "
         f"{link('objective.html', 'Why this matters for AI')}</p>",
         f"<h2>Topic areas</h2><p>{len(ctx.recs):,} articles analysed so far.</p><div class='cards'>"]
    queued = {}
    done = {r["article"] for r in ctx.recs}
    for c in ctx.candidates:
        if c["title"] not in done:
            queued.setdefault(c["area"], set()).add(c["title"])
    for a in _area_order(ctx):
        rows = [r for r in ctx.recs if ctx.areas.get(r["article"], "") == a]
        counts = [(kind_name(k), sum(1 for r in rows if (ctx.kinds.get(r["article"]) or "") == k))
                  for k in KINDS + [""]]
        parts = " · ".join(f"{name} {n}" for name, n in counts if n)
        q = len(queued.get(a, ()))
        h.append(f"<div class='card'><h3><a href='compare.html#area-{escape(a or 'none')}'>"
                 f"{escape(area_name(a))}</a></h3><p><b>{len(rows)}</b> analysed</p><p class='small'>{escape(parts)}</p>"
                 + (f"<p class='small'>{q} more queued.</p>" if q else "") + "</div>")
    h.append("</div>")
    h.append(f"<p>{link('compare.html', 'See all articles and their figures')}, grouped like with "
             "like, with an explanation of each figure.</p>")
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
         "<li><b>Compare like with like.</b> Each figure is shown next to the typical value for "
         "other articles of the same kind (people with people, news outlets with news outlets), "
         "first in the same topic area and then across all areas, so a number is never read "
         "without context.</li></ol>",
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
         "<li><b>Now:</b> authorship and sanctions for the most-read articles in Wikipedia's "
         "contentious topic areas (this site).</li>"
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


def _write(SITE_DIR, clean, ctx):
    for r in clean:
        (SITE_DIR / "articles" / f"{slug(r['article'])}.html").write_text(article_page(r, ctx), encoding="utf-8")
        (SITE_DIR / "data" / f"{slug(r['article'])}.json").write_text(json_writer.dumps(r), encoding="utf-8")
    shutil.copy(OUT_DIR / "summary.json", SITE_DIR / "data" / "summary.json")
    (SITE_DIR / "index.html").write_text(home_page(ctx), encoding="utf-8")
    (SITE_DIR / "compare.html").write_text(compare_page(ctx), encoding="utf-8")
    (SITE_DIR / "articles.html").write_text(choose_page(ctx), encoding="utf-8")
    (SITE_DIR / "sources.html").write_text(sources_page(ctx), encoding="utf-8")
    from .outlets import OUTLETS_JSON
    if OUTLETS_JSON.exists():
        shutil.copy(OUTLETS_JSON, SITE_DIR / "data" / "outlets.json")
    from .config import ROOT
    for name in ("contested_terms.json", "words_to_watch.json", "source_names.json"):
        if (ROOT / "data" / name).exists():   # the lists every record's fingerprints refer to
            shutil.copy(ROOT / "data" / name, SITE_DIR / "data" / name)
    (SITE_DIR / "editors.html").write_text(editors_page(ctx), encoding="utf-8")
    (SITE_DIR / "how-it-works.html").write_text(how_page(ctx), encoding="utf-8")
    (SITE_DIR / "objective.html").write_text(objective_page(), encoding="utf-8")
    (SITE_DIR / "about.html").write_text(about_page(), encoding="utf-8")
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")
