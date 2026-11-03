"""Family A: authorship and concentration of the current text, and survival of each editor's
words over the article's history.

Unit of measurement: a *word* is a WikiWho token that contains a letter or digit and sits in
readable prose (see wtl.text.wikitext). Each word has exactly one author: the editor of the
revision that first added it (WikiWho's origin revision), so shares always sum to 100%.
"""

import bisect
import datetime as dt
import ipaddress
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

WORD = re.compile(r"\w", re.UNICODE)
TOP_N = (1, 3, 5, 10)
HORIZONS = {"48h": dt.timedelta(hours=48), "30d": dt.timedelta(days=30),
            "365d": dt.timedelta(days=365)}


def parse_ts(ts: str) -> dt.datetime:
    return dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


@dataclass
class Word:
    editor: str        # internal editor key, never written to output
    o_rev_id: int
    lead: bool
    sentence: int      # index into the sentence list, or -1


class History:
    """Revision metadata for one page up to the analysed revision."""

    def __init__(self, revs: list[dict]):
        self.revs = revs
        self.by_id = {r["revid"]: r for r in revs}
        self.ids = [r["revid"] for r in revs]
        self.times = [parse_ts(r["timestamp"]) for r in revs]

    def time_of(self, revid: int):
        r = self.by_id.get(revid)
        return parse_ts(r["timestamp"]) if r else None

    def last_rev_at(self, t: dt.datetime) -> int:
        """Largest revision id saved at or before time t (0 if none)."""
        i = bisect.bisect_right(self.times, t)
        return self.ids[i - 1] if i else 0


def editor_key(o_rev_id: int, ww_editor: str, hist: History) -> tuple[str, str, str]:
    """Return (key, username, account_type). Username stays internal."""
    r = hist.by_id.get(o_rev_id)
    if r is not None:
        if r.get("hidden") or r.get("user") is None:
            return f"hidden:{o_rev_id}", "", "hidden"
        if r.get("userid"):
            return f"u{r['userid']}", r["user"], "registered"
        name = r["user"]
    else:  # origin revision missing from the public history (e.g. deleted): use WikiWho's field
        if ww_editor.isdigit() and ww_editor != "0":
            return f"u{ww_editor}", "", "registered"
        name = ww_editor.split("|", 1)[-1]
    if name.startswith("~"):
        return f"n:{name}", name, "temporary"
    try:
        ipaddress.ip_address(name)
        return f"n:{name}", name, "ip"
    except ValueError:
        return f"n:{name}", name, "unknown"


def collect_words(tokens, spans, lay, sent_of, hist: History):
    """Words in readable prose, with their author. Also returns {key: (username, type)}."""
    words, who = [], {}
    for (s, o_rev, ed), span in zip(tokens, spans):
        if span is None or not WORD.search(s):
            continue
        a, b = span
        k = next((i for i in range(a, b) if lay.prose[i]), None)
        if k is None:
            continue
        key, name, acct = editor_key(o_rev, ed, hist)
        who.setdefault(key, (name, acct))
        words.append(Word(key, o_rev, lay.section_of[k] == 0, sent_of[k]))
    return words, who


def label_editors(words: list[Word]) -> dict[str, str]:
    """Editor 1 = most words. Ties broken by earliest surviving contribution, then key."""
    count = Counter(w.editor for w in words)
    first = {}
    for w in words:
        first[w.editor] = min(first.get(w.editor, w.o_rev_id), w.o_rev_id)
    order = sorted(count, key=lambda k: (-count[k], first[k], k))
    return {k: f"Editor {i}" for i, k in enumerate(order, start=1)}


def concentration(counts: Counter) -> dict:
    total = sum(counts.values())
    vals = sorted(counts.values(), reverse=True)
    if not total:
        return {"top_shares": {str(n): 0.0 for n in TOP_N}, "hhi": 0.0,
                "editors_for_50pct": 0, "editors_for_80pct": 0}
    cum, need50, need80 = 0, None, None
    for i, v in enumerate(vals, start=1):
        cum += v
        if need50 is None and cum * 2 >= total:
            need50 = i
        if need80 is None and cum * 5 >= total * 4:
            need80 = i
    return {
        "top_shares": {str(n): r6(sum(vals[:n]) / total) for n in TOP_N},
        "hhi": r6(sum((v / total) ** 2 for v in vals)),
        "editors_for_50pct": need50,
        "editors_for_80pct": need80,
    }


def r6(x: float) -> float:
    return round(x, 6)


def survival(all_tokens, hist: History, analysed_revid: int, key_of_rev) -> dict:
    """Share of words still present 48 hours / 30 days / 365 days after they were added.

    Computed over every word ever added to the article up to the analysed revision (removed words
    included), using WikiWho's removal (out) and re-insertion (in) revisions. A word added less
    than the horizon before the analysed revision is left out of that horizon. Events after the
    analysed revision are ignored.
    """
    t_end = hist.time_of(analysed_revid)
    per_editor = defaultdict(lambda: {h: [0, 0] for h in HORIZONS})
    article = {h: [0, 0] for h in HORIZONS}
    skipped = 0
    for o_rev, ins, outs in all_tokens:
        if o_rev > analysed_revid:
            continue
        t0 = hist.time_of(o_rev)
        if t0 is None:
            skipped += 1
            continue
        key = key_of_rev(o_rev)
        for h, delta in HORIZONS.items():
            t = t0 + delta
            if t > t_end:
                continue
            cut = hist.last_rev_at(t)
            n_out = sum(1 for r in outs if r <= cut)
            n_in = sum(1 for r in ins if r <= cut)
            alive = n_out == n_in
            cell = per_editor[key][h]
            cell[0] += 1
            cell[1] += alive
            article[h][0] += 1
            article[h][1] += alive
    return {"per_editor": per_editor, "article": article, "skipped_unknown_revision": skipped}


def survival_block(cells: dict, article: dict) -> dict:
    out = {}
    for h in HORIZONS:
        n, k = cells[h]
        an, ak = article[h]
        rate = k / n if n else None
        avg = ak / an if an else None
        out[h] = {"words_added": n, "words_surviving": k,
                  "rate": r6(rate) if rate is not None else None,
                  "vs_article": r6(rate / avg) if rate is not None and avg else None}
    return out
