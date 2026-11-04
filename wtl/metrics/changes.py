"""Removals and wording changes, per editor, from WikiWho's full token history.

Everything is counted up to the analysed revision; later events are ignored.

Removals. Each time a revision takes a word out of the article (WikiWho's "out" list), the
editor of that revision is counted as removing it. For each editor: words removed; how many
were written by someone else; how many were later put back (a later "in" for that word, up to
the analysed revision); and the web sources whose links were in the removed text. Text that
WikiWho cannot follow when it is moved counts as removed and re-added; WikiWho follows most
moves within an article.

Wording changes. Terms on the word lists (wtl/words.py) are counted when an editor inserts them
(in today's text, or in text that was later removed) and when an editor removes them. A word is
credited to the revision that first added it, as in the rest of the record.
"""

import re
from collections import Counter, defaultdict

from .. import sources as src
from ..words import is_word

URL = re.compile(r"https?://[^\s|\]\[}{<>\"']+", re.I)


def _runs(idxs: list[int]) -> list[list[int]]:
    """Split sorted token positions into runs of consecutive positions."""
    runs, cur = [], []
    for i in idxs:
        if cur and i != cur[-1] + 1:
            runs.append(cur)
            cur = []
        cur.append(i)
    if cur:
        runs.append(cur)
    return runs


def _sources_in(strs: list[str]) -> set[str]:
    """Source keys (registrable domains) of the web links in a run of removed tokens."""
    keys = set()
    for m in URL.finditer("".join(strs)):
        h = src.host_of(m.group(0))
        if h and "." in h:
            keys.add(src.registrable(h))
    return keys


def compute(toks, current, analysed_revid, key_of_rev, matcher=None):
    """toks: WikiWho all_content tokens [o_rev, in, out, str] in token order; current: the
    analysed revision's tokens [str, o_rev, editor]. Returns (per_editor, article, evidence)."""
    A = analysed_revid
    if toks and len(toks[0]) < 4:   # history without token text: removals cannot be read
        toks = [[*t, "w"] for t in toks]
    removed_by = defaultdict(list)                 # revision -> token positions it removed
    per = defaultdict(lambda: {"words_removed": 0, "others_words_removed": 0,
                               "words_removed_later_restored": 0, "removing_revisions": set(),
                               "sources_removed": Counter(),
                               "terms_inserted": Counter(), "terms_removed": Counter()})
    article = Counter()
    for i, (o, ins, outs, s) in enumerate(toks):
        if o > A:
            continue
        for r in outs:
            if r > A:
                continue
            removed_by[r].append(i)
            if not is_word(s):
                continue
            k = key_of_rev(r)
            e = per[k]
            e["words_removed"] += 1
            e["removing_revisions"].add(r)
            article["words_removed"] += 1
            if key_of_rev(o) != k:
                e["others_words_removed"] += 1
            if any(r < x <= A for x in ins):
                e["words_removed_later_restored"] += 1
                article["words_removed_later_restored"] += 1
    rev_words = Counter()
    for r, idxs in removed_by.items():
        k = key_of_rev(r)
        for run in _runs(sorted(idxs)):
            strs = [toks[i][3] for i in run]
            for key in _sources_in(strs):
                per[k]["sources_removed"][key] += 1
                article["source_links_removed"] += 1
            if matcher:
                w = [x for x in strs if is_word(x)]
                for _, _, g, term in matcher.find(w):
                    per[k]["terms_removed"][(g, term)] += 1
            rev_words[r] += sum(1 for x in strs if is_word(x))
    if matcher:
        # inserted and still present: today's text, credited to the revision that added it
        cw = [(t[0], t[1]) for t in current if is_word(t[0])]
        for s0, L, g, term in matcher.find([x for x, _ in cw]):
            per[key_of_rev(cw[s0][1])]["terms_inserted"][(g, term)] += 1
        # inserted and later removed: runs of removed tokens added by one revision
        gone = [i for i, t in enumerate(toks) if t[0] <= A
                and sum(r <= A for r in t[2]) > sum(x <= A for x in t[1])]   # absent at A
        for run in _runs(gone):
            by_o = []
            for i in run:   # split further where the adding revision changes
                if by_o and toks[by_o[-1][0]][0] != toks[i][0]:
                    _match_inserted(toks, by_o, matcher, per, key_of_rev)
                    by_o = []
                by_o.append((i,))
            _match_inserted(toks, by_o, matcher, per, key_of_rev)
    evidence = {}
    for k, e in per.items():
        top = sorted(e["removing_revisions"], key=lambda r: (-rev_words[r], r))[:5]
        evidence[k] = top
        e["removing_revisions"] = len(e["removing_revisions"])
    return per, article, evidence


def _match_inserted(toks, group, matcher, per, key_of_rev):
    if not group:
        return
    idx = [g[0] for g in group]
    w = [toks[i][3] for i in idx if is_word(toks[i][3])]
    for _, _, g, term in matcher.find(w):
        per[key_of_rev(toks[idx[0]][0])]["terms_inserted"][(g, term)] += 1
