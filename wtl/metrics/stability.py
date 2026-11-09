"""Per-sentence history and footnote bundles, from the analysed revision and WikiWho's full
token history. Everything stops at the analysed revision.

Sentence history. A sentence is "taken out" by a revision that removed at least half of its
words at once (WikiWho's out lists), and "put back" by the revision that re-inserted most of
those words afterwards. Every word in the analysed text is present, so every taking-out was
later undone. A revision that took out half or more of the whole of today's text at once
(page blanking, almost always vandalism) is counted apart, as a page-wide removal. For each
sentence: how many times it was taken out, how many of those were put back within 24 hours and
how many stayed out longer, how many different accounts took it out and put it back (counts
only), when it was first added, the latest removal, and since when it has been in place.

A sentence counts as "taken out and put back at least twice" on two or more such occasions.
That is a fixed count; it does not say the sentence is wrong or right, or why it was removed.

Hidden notes and tags. A hidden note in the page source (<!-- … -->) that records agreement on
the talk page or asks editors not to change text without discussion is attached to the
sentence after it; a tag questioning text ({{Disputed inline}}, {{Dubious}}, {{Citation
needed}} and similar) to the sentence before it, with its talk-page link and date.

Footnote bundles. Each footnote (<ref>, including a re-use of a named footnote) is placed after
the sentence that comes before it. A footnote holds one or more works: each citation template
or short footnote ({{sfn}} and similar) inside it is a work; a footnote written as plain text
is one work. Footnotes in a named group (explanatory notes) are left out.
"""

import re
from collections import Counter

from .. import sources as src
from .authorship import parse_ts, r6

WORD = re.compile(r"\w", re.U)
MIN_TIMES = 2
PAGE_WIDE = 0.5   # a revision removing half of today's words at once is page-wide
EVENTS_KEPT = 10

REF_TAG = re.compile(r"<ref(\s[^>]*?)?\s*(/>|>(.*?)</ref\s*>)", re.I | re.S)
NAME_ATTR = re.compile(r"""\bname\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s/>]+))""", re.I)
GROUP_ATTR = re.compile(r"\bgroup\s*=", re.I)


def _works_in(body: str) -> int:
    n = len(src._templates(body, 0, len(body), src.CITE_START)) + \
        len(src._templates(body, 0, len(body), src.SHORT))
    return n or 1


def _sentence_before(text, sent_of, pos, skip_end, lookback=600):
    """Sentence of the nearest sentence character before `pos`, jumping over footnotes and
    templates (skip_end: end offset -> start offset), within the same paragraph."""
    j, seen = pos - 1, 0
    while j >= 0 and seen < lookback:
        if j + 1 in skip_end:
            j = skip_end[j + 1] - 1
            continue
        if j < len(sent_of) and sent_of[j] >= 0:
            return sent_of[j]
        if text[j] == "\n" and j > 0 and text[j - 1] == "\n":
            return -1
        j -= 1
        seen += 1
    return -1


def _sentence_after(text, sent_of, pos, lookback=300):
    j, n = pos, min(len(text), pos + lookback)
    while j < n:
        if j < len(sent_of) and sent_of[j] >= 0:
            return sent_of[j]
        if text[j] == "\n" and j + 1 < len(text) and text[j + 1] == "\n":
            return -1
        j += 1
    return -1


TAG = re.compile(r"\{\{\s*(disputed[ -]inline|disputed-section|dubious|pov[ -]statement|pov-inline|"
                 r"neutrality[ -]inline|contradict-inline|according to whom|by whom|who\?|weasel-inline|"
                 r"failed verification|verification needed|better source needed|unreliable source\?|"
                 r"citation needed|cn|fact)\s*(\|[^{}]*)?\}\}", re.I)
TAG_TALK = re.compile(r"\|\s*(?:talk\s*=\s*)?((?:Talk|Wikipedia talk):[^|}]+)", re.I)
TAG_DATE = re.compile(r"\|\s*date\s*=\s*([^|}]+)", re.I)
COMMENT = re.compile(r"<!--(.*?)-->", re.S)
# a hidden note that asks editors not to change text without discussion, or records that the
# text was agreed (words as editors write them; matched in English only)
KEEP_NOTE = re.compile(r"\bconsensus\b|\bRfC\b|request for comment|moratorium|"
                       r"\b(?:do not|don't|please do not|please don't)\s+(?:change|alter|modify|remove|edit|delete)|"
                       r"(?:discuss|discussed)\s+(?:on|at|in)\s+(?:the\s+)?talk|before (?:changing|editing|removing)",
                       re.I)
USER_LINK = re.compile(r"\[\[\s*(?:User|User talk|Special:Contributions)\s*:[^\]]*\]\]|"
                       r"\b(?:User|User talk)\s*:\s*[^\s\]|,;]+", re.I)


def _skip_spans(text):
    spans = {}
    for m in REF_TAG.finditer(text):
        spans[m.end()] = m.start()
    for m in COMMENT.finditer(text):
        spans[m.end()] = m.start()
    for m in TAG.finditer(text):
        spans[m.end()] = m.start()
    return spans


def footnotes(text: str, sent_of: list[int]) -> dict[int, list[int]]:
    """{sentence index: [works in each footnote that follows it]}."""
    named, tags = {}, []
    for m in REF_TAG.finditer(text):
        attrs = m.group(1) or ""
        if GROUP_ATTR.search(attrs):
            continue
        nm = NAME_ATTR.search(attrs)
        name = next((g for g in nm.groups() if g is not None), "").strip() if nm else ""
        if m.group(3) is not None:
            w = _works_in(m.group(3))
            if name:
                named.setdefault(name, w)
            tags.append((m.start(), w, None))
        else:
            tags.append((m.start(), None, name))
    skip = _skip_spans(text)
    out: dict[int, list[int]] = {}
    for pos, w, name in tags:
        if w is None:
            w = named.get(name)
            if w is None:
                continue
        s = _sentence_before(text, sent_of, pos, skip)
        if s >= 0:
            out.setdefault(s, []).append(w)
    return out


def notes_and_tags(text: str, sent_of: list[int]) -> tuple[dict, dict]:
    """Hidden notes asking editors to keep text (attached to the sentence that follows the note)
    and maintenance tags questioning text (attached to the sentence before the tag).
    Returns ({sentence: [note text]}, {sentence: [{"template", "talk", "date"}]}). Account names
    in a note are replaced with "[account]"."""
    skip = _skip_spans(text)
    notes, tags = {}, {}
    for m in COMMENT.finditer(text):
        body = re.sub(r"\s+", " ", m.group(1)).strip()
        if not body or not KEEP_NOTE.search(body):
            continue
        s = _sentence_after(text, sent_of, m.end())
        if s >= 0:
            notes.setdefault(s, []).append(USER_LINK.sub("[account]", body)[:400])
    for m in TAG.finditer(text):
        s = _sentence_before(text, sent_of, m.start(), skip)
        if s < 0:
            continue
        args = m.group(2) or ""
        t, d = TAG_TALK.search(args), TAG_DATE.search(args)
        tags.setdefault(s, []).append({"template": m.group(1).strip().lower().replace("_", " "),
                                       "talk": t.group(1).strip() if t else None,
                                       "date": d.group(1).strip() if d else None})
    return notes, tags


def bundles_summary(per_sentence: dict[int, list[int]], sent_ids: dict[int, str]) -> dict:
    works = {s: sum(v) for s, v in per_sentence.items() if s in sent_ids}
    bands = Counter()
    for w in works.values():
        bands["1" if w == 1 else "2-4" if w <= 4 else "5-9" if w <= 9 else "10 or more"] += 1
    largest = sorted(works, key=lambda s: (-works[s], s))[:10]
    return {"sentences_with_footnotes": len(works),
            "sentences_by_works_cited": {k: bands[k] for k in ("1", "2-4", "5-9", "10 or more")},
            "largest": [{"sentence": sent_ids[s], "footnotes": len(per_sentence[s]), "works": works[s]}
                        for s in largest if works[s] >= 5]}


def sentence_history(allc_tokens, idx, word_sentence, revid, hist, key_of_rev) -> dict[int, dict]:
    """idx: position in allc_tokens of each token of the analysed revision (text order);
    word_sentence: sentence index of each of those tokens (-1 outside sentences)."""
    members: dict[int, list[int]] = {}
    for k, s in enumerate(word_sentence):
        if s >= 0 and len(allc_tokens[idx[k]]) > 3 and WORD.search(allc_tokens[idx[k]][3]):
            members.setdefault(s, []).append(idx[k])
    # revisions that took out most of today's text at once (page blanking and similar)
    all_words = [i for v in members.values() for i in v]
    wide = Counter()
    for i in all_words:
        wide.update({r for r in allc_tokens[i][2] if r <= revid})
    page_wide = {r for r, n in wide.items() if n >= PAGE_WIDE * len(all_words)}
    out = {}
    for s, toks in members.items():
        need = (len(toks) + 1) // 2
        outs = Counter()
        for i in toks:
            outs.update({r for r in allc_tokens[i][2] if r <= revid})
        events, blanked = [], 0
        for r in sorted(x for x, n in outs.items() if n >= need):
            if r in page_wide:
                blanked += 1
                continue
            back = Counter()
            for i in toks:
                ins, os_ = allc_tokens[i][1], allc_tokens[i][2]
                if r in os_:
                    nxt = min((x for x in ins if r < x <= revid), default=None)
                    if nxt:
                        back[nxt] += 1
            if not back:
                continue
            rr = min(back, key=lambda x: (-back[x], x))
            t0, t1 = hist.time_of(r), hist.time_of(rr)
            hours = (t1 - t0).total_seconds() / 3600 if t0 and t1 else None
            events.append((r, rr, hours))
        last_back = max((e[1] for e in events), default=None)
        first = min(allc_tokens[i][0] for i in toks)
        since = last_back or first
        date = lambda r: hist.by_id[r]["timestamp"][:10] if r in hist.by_id else None  # noqa: E731
        out[s] = {
            "removed": len(events),
            "back_within_24h": sum(1 for e in events if e[2] is not None and e[2] < 24),
            "out_24h_or_more": sum(1 for e in events if e[2] is not None and e[2] >= 24),
            "removing_accounts": len({key_of_rev(e[0]) for e in events}),
            "restoring_accounts": len({key_of_rev(e[1]) for e in events}),
            "page_wide_removals": blanked,
            "first_added": date(first),
            "latest_removal": date(events[-1][0]) if events else None,
            "in_place_since": date(since),
            "in_place_since_revision": since,
            # [removing revision, restoring revision, hours out] of the latest removals
            "removals": [[e[0], e[1], round(e[2], 1) if e[2] is not None else None]
                         for e in events[-EVENTS_KEPT:]],
        }
    return out


def history_summary(hist_by_sentence: dict[int, dict], words_of: dict[int, int],
                    lead: set[int], revid, hist) -> dict:
    t_end = hist.time_of(revid)
    contested = [s for s, h in hist_by_sentence.items() if h["removed"] >= MIN_TIMES]
    days = sorted((t_end - parse_ts(hist.by_id[hist_by_sentence[s]["in_place_since_revision"]]["timestamp"])).days
                  for s in contested if hist_by_sentence[s]["in_place_since_revision"] in hist.by_id)
    total_words = sum(words_of.values())
    cw = sum(words_of.get(s, 0) for s in contested)
    return {
        "rule": f"taken out and put back at least {MIN_TIMES} times, not counting page-wide removals",
        "sentences": len(hist_by_sentence),
        "sentences_removed_and_restored_twice_or_more": len(contested),
        "their_words": cw,
        "share_of_words": r6(cw / total_words) if total_words else None,
        "in_opening_section": sum(1 for s in contested if s in lead),
        "median_days_in_place_since_last_restored": (days[len(days) // 2] if days else None),
        "sentences_removed_five_times_or_more": sum(1 for h in hist_by_sentence.values()
                                                    if h["removed"] >= 5),
        "sentences_removed_by_two_or_more_accounts": sum(1 for h in hist_by_sentence.values()
                                                         if h["removing_accounts"] >= 2),
    }
