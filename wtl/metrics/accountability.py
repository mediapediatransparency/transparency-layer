"""Family B: how much of the current text was written by editors that Wikipedia itself later
sanctioned (topic ban, site ban, or sockpuppetry finding), and whether each word was added before
or after the sanction.

A sanction is a fact about conduct. It does not make any sentence wrong; it marks text that
deserves a second look.
"""

from collections import Counter

from ..sanctions import Sanction
from .authorship import History, Word, parse_ts, r6


def earliest(sanctions: list[Sanction]) -> Sanction | None:
    return min(sanctions, key=lambda s: (s.date, s.type)) if sanctions else None


def word_timing(w: Word, ss: list[Sanction] | Sanction, hist: History) -> str:
    """When the word's origin revision was saved, relative to the editor's sanctions:
    'before'      before the first sanction started;
    'during'      while a sanction with a known end date was in force;
    'during_open' while an open-ended sanction was in force with no end on record (it may have
                  been lifted without our list recording it);
    'after_ended' after a sanction started, but when none was in force;
    'unknown'     the origin revision's date is not known."""
    ss = [ss] if isinstance(ss, Sanction) else ss
    t = hist.time_of(w.o_rev_id)
    if t is None:
        return "unknown"
    d = t.date().isoformat()
    if d < min(s.date for s in ss):
        return "before"
    active = [s for s in ss if s.date <= d and (not s.end or d < s.end)]
    if any(s.end for s in active):
        return "during"
    if active:
        return "during_open"
    return "after_ended"


def compute(words: list[Word], applicable: dict[str, list[Sanction]], hist: History) -> dict:
    total = len(words)
    lead_total = sum(w.lead for w in words)
    by_type, by_source, timing = Counter(), Counter(), Counter()
    lead_by_type, lead_timing = Counter(), Counter()
    sanctioned = lead_sanctioned = 0
    for w in words:
        ss = applicable.get(w.editor)
        if not ss:
            continue
        sanctioned += 1
        lead_sanctioned += w.lead
        when = word_timing(w, ss, hist)
        timing[when] += 1
        if w.lead:
            lead_timing[when] += 1
        for t in sorted({s.type for s in ss}):
            by_type[t] += 1
            if w.lead:
                lead_by_type[t] += 1
        for src in sorted({s.source for s in ss}):
            by_source[src] += 1

    def share(n, d):
        return r6(n / d) if d else 0.0

    return {
        "sanctioned_words": sanctioned,
        "sanctioned_share": share(sanctioned, total),
        "sanctioned_lead_words": lead_sanctioned,
        "sanctioned_lead_share": share(lead_sanctioned, lead_total),
        "by_type": {t: {"words": by_type[t], "share": share(by_type[t], total),
                        "lead_words": lead_by_type[t],
                        "lead_share": share(lead_by_type[t], lead_total)}
                    for t in ("topic_ban", "site_ban", "sockpuppet")},
        "by_source": {s: {"words": by_source[s], "share": share(by_source[s], total)}
                      for s in ("seed_list", "block_log")},
        "timing": {
            "added_before_sanction_words": timing["before"],
            "added_after_sanction_words": timing["during"] + timing["during_open"] + timing["after_ended"],
            "added_during_sanction_words": timing["during"],
            "added_during_open_ended_sanction_words": timing["during_open"],
            "added_after_sanction_ended_words": timing["after_ended"],
            "unknown_words": timing["unknown"],
            "lead_added_before_sanction_words": lead_timing["before"],
            "lead_added_after_sanction_words": (lead_timing["during"] + lead_timing["during_open"]
                                                + lead_timing["after_ended"]),
            "lead_added_during_sanction_words": lead_timing["during"],
            "lead_added_during_open_ended_sanction_words": lead_timing["during_open"],
        },
        "sanctioned_editors": len([k for k in applicable if applicable[k]]),
    }
