"""Caveats that change how a figure should be read, computed from the record itself.

Each caveat is stored in the JSON record (so readers and AI systems get it with the numbers) and
shown next to the figure it qualifies. Only conditions that materially change the reading belong
here; generic disclaimers live on the method page.
"""

# A topic area's sanctions list counts as thin below this many hand-checked rows. The
# Israel-Palestine (A-I) list, the most thoroughly checked, has about a hundred.
COVERAGE_MIN_ROWS = 50
# One editor "dominates" the sanctioned figure above this share of it.
DOMINANT_SHARE = 0.5
# Data-quality note when more than this share of WikiWho words could not be placed in the text.
UNALIGNED_MAX = 0.005

AREA_NAMES = {"A-I": "Arab–Israeli conflict", "EE": "Eastern Europe", "SA": "South Asia"}


def sanctioned_concentration(rec: dict) -> dict | None:
    """How much of the sanctioned figure comes from the single largest sanctioned editor."""
    a = rec["authorship"]
    sanc = [e for e in a["editors"] if e["sanctioned"]]
    total = sum(e["words"] for e in sanc)
    if not total:
        return None
    top = max(sanc, key=lambda e: (e["words"], -int(e["label"].split()[-1])))
    return {"editor": top["label"], "words": top["words"],
            "share_of_article": top["share"],
            "share_of_sanctioned_text": round(top["words"] / total, 6),
            "sanctioned_editors": len(sanc)}


def compute(rec: dict) -> list[dict]:
    """List of {code, applies_to, text}. `applies_to` names the figure the caveat qualifies."""
    out = []
    acc = rec["accountability"]
    area = rec.get("topic_area") or ""
    rows = acc["sanctions_list"]["seed_rows_in_topic_area"]

    conc = sanctioned_concentration(rec)
    if conc and conc["sanctioned_editors"] > 1 and conc["share_of_sanctioned_text"] >= DOMINANT_SHARE:
        out.append({
            "code": "one_editor_dominates",
            "applies_to": "sanctioned_share",
            "text": (f"Most of this figure comes from one editor. {conc['editor']} alone wrote "
                     f"{conc['share_of_article'] * 100:.1f}% of the article, which is "
                     f"{conc['share_of_sanctioned_text'] * 100:.0f}% of all the text by sanctioned "
                     f"editors. Read it as one editor's contribution, not a pattern across "
                     f"many editors."),
        })
    elif conc and conc["sanctioned_editors"] == 1:
        out.append({
            "code": "single_sanctioned_editor",
            "applies_to": "sanctioned_share",
            "text": f"This figure comes from a single editor ({conc['editor']}).",
        })

    if not area:
        out.append({
            "code": "no_topic_area",
            "applies_to": "sanctioned_share",
            "text": ("This article is not in a topic area under special sanctions, so only "
                     "Wikipedia-wide bans and sockpuppetry findings can count here. Topic bans "
                     "do not apply."),
        })
    elif rows < COVERAGE_MIN_ROWS:
        name = AREA_NAMES.get(area, area)
        out.append({
            "code": "thin_sanctions_list",
            "applies_to": "sanctioned_share",
            "text": (f"The sanctions list for this topic area ({name}) has only {rows} "
                     f"hand-checked entries, against about a hundred for the Arab–Israeli "
                     f"conflict. This figure is likely an undercount, and comparing it with "
                     f"better-covered areas would overstate the difference."),
        })

    if area:
        out.append({
            "code": "minimum_figure",
            "applies_to": "sanctioned_share",
            "text": ("Treat this as a minimum. The hand-checked list starts in 2023, so topic "
                     "bans from earlier years are not counted. Long-established articles are "
                     "affected most."),
        })

    t = acc["timing"]
    if t.get("added_during_open_ended_sanction_words"):
        out.append({
            "code": "open_ended_sanctions",
            "applies_to": "timing",
            "text": ("Indefinite sanctions are counted as in force from their start date unless "
                     "the list records that they were lifted or overturned on appeal. Some may "
                     "have ended without that being recorded yet, so part of the “while an "
                     "open-ended sanction was in force” figure may belong under “after the "
                     "sanctions had ended”."),
        })

    q = rec["quality"]
    if q["wikiwho_tokens"] and q["unaligned_tokens"] / q["wikiwho_tokens"] > UNALIGNED_MAX:
        out.append({
            "code": "alignment_gaps",
            "applies_to": "authorship",
            "text": (f"{q['unaligned_tokens']:,} of {q['wikiwho_tokens']:,} words could not be "
                     f"matched to the article text, so figures may be slightly off."),
        })
    return out
