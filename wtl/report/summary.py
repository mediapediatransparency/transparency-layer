"""Topic articles next to control articles, so no figure is read in isolation."""

import statistics
from html import escape

from .html import CSS, get, pct

METRICS = [
    ("authorship.total_words", "Prose words", "int"),
    ("authorship.editor_count", "Editors with text", "int"),
    ("authorship.top_shares.1", "Top 1 share", "pct"),
    ("authorship.top_shares.5", "Top 5 share", "pct"),
    ("authorship.top_shares.10", "Top 10 share", "pct"),
    ("authorship.editors_for_50pct", "Editors for 50%", "int"),
    ("authorship.hhi", "HHI", "f3"),
    ("authorship.lead.top_shares.3", "Lead: top 3 share", "pct"),
    ("authorship.survival_article.48h.rate", "48-hour survival", "pct"),
    ("authorship.survival_article.30d.rate", "30-day survival", "pct"),
    ("authorship.survival_article.365d.rate", "1-year survival", "pct"),
    ("authorship.sanctioned_share", "Text by sanctioned editors", "pct"),
    ("authorship.sanctioned_lead_share", "Lead by sanctioned editors", "pct"),
    ("accountability.by_type.topic_ban.share", "… topic ban", "pct"),
    ("accountability.by_type.site_ban.share", "… site ban", "pct"),
    ("accountability.by_type.sockpuppet.share", "… sockpuppetry", "pct"),
    ("accountability.by_source.block_log.share", "… found via block log", "pct"),
    ("accountability.sanctioned_editors", "Sanctioned editors with text", "int"),
    ("accountability.sanctions_list.seed_rows_in_topic_area", "Seed-list rows for this area", "int"),
]


def fmt(v, kind):
    if v is None:
        return "–"
    if kind == "pct":
        return pct(v)
    if kind == "f3":
        return f"{v:.3f}"
    return f"{v:,.0f}" if isinstance(v, (int, float)) else str(v)


def median(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def baseline(records: list[dict], groups: dict[str, str], group="control") -> dict:
    rs = [r for r in records if groups.get(r["article"]) == group]
    values = {path: median([get(r, path) for r in rs]) for path, _, _ in METRICS}
    for n in ("1", "3", "5", "10"):
        values[f"authorship.top_shares.{n}"] = median([get(r, f"authorship.top_shares.{n}") for r in rs])
        values[f"authorship.lead.top_shares.{n}"] = median(
            [get(r, f"authorship.lead.top_shares.{n}") for r in rs])
    return {"label": f"control median, n={len(rs)}", "articles": [r["article"] for r in rs],
            "values": values}


def summary_json(records, groups):
    rows = []
    for r in records:
        rows.append({"article": r["article"], "group": groups.get(r["article"]),
                     "revision": r["revision"], "computed": r["computed"],
                     "topic_area": r["topic_area"],
                     **{path: get(r, path) for path, _, _ in METRICS}})
    meds = {g: {path: median([get(r, path) for r in records if groups.get(r["article"]) == g])
                for path, _, _ in METRICS} for g in ("topic", "control")}
    return {"articles": rows, "medians": meds}


def render(records: list[dict], groups: dict[str, str]) -> str:
    topic = [r for r in records if groups.get(r["article"]) == "topic"]
    control = [r for r in records if groups.get(r["article"]) == "control"]
    cols = topic + control
    h = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
         f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>Test set comparison</title><style>{CSS}</style></head><body><main>",
         "<h1>Topic articles next to controls</h1>",
         "<p class='small'>Every metric computed the same way for every article. Topic: "
         "Arab–Israeli conflict articles. Controls: two other contested topics and one quiet "
         "one. Sanction figures depend on the seed list's coverage of each area, shown in the "
         "last row; compare them only where coverage is similar.</p>",
         "<div class='scroll'><table><tr><th>Metric</th>"]
    for r in cols:
        h.append(f"<th class='n'><a href='{escape(r['_href'], quote=True)}'>{escape(r['article'])}</a></th>")
    h.append("<th class='n'>Topic median</th><th class='n'>Control median</th></tr>")
    for path, name, kind in METRICS:
        h.append(f"<tr><td>{escape(name)}</td>")
        for r in cols:
            h.append(f"<td class='n'>{fmt(get(r, path), kind)}</td>")
        h.append(f"<td class='n'><b>{fmt(median([get(r, path) for r in topic]), kind)}</b></td>"
                 f"<td class='n'><b>{fmt(median([get(r, path) for r in control]), kind)}</b></td></tr>")
    h.append("<tr><td>Revision</td>" + "".join(
        f"<td class='n small'>{r['revision']}<br>{escape(r['revision_timestamp'][:10])}</td>"
        for r in cols) + "<td></td><td></td></tr>")
    h.append("</table></div></main></body></html>\n")
    return "".join(h)
