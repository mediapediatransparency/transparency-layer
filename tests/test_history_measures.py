"""Sentence history, footnote bundles, hidden notes, persistence, talk-page reading, authors."""
from wtl import sources, talk
from wtl.metrics import authorship as au, stability as st


def _sent_of(text, spans):
    s = [-1] * len(text)
    for i, (a, b) in enumerate(spans):
        for o in range(a, b):
            s[o] = i
    return s


def test_footnotes_follow_long_named_refs_and_reuse():
    body = "{{cite book|last=A}}{{sfn|B|2001}}{{sfn|C|2002}}"
    text = ("Alpha one. <ref name=x>" + body + "x" * 900 + "</ref><ref name=y>{{cite web|url=u}}</ref>\n\n"
            "Beta two.<ref name=x/><ref name=y />")
    a, b = text.index("Alpha"), text.index("Beta")
    so = _sent_of(text, [(a, a + 10), (b, b + 9)])
    fn = st.footnotes(text, so)
    assert fn == {0: [3, 1], 1: [3, 1]}


def test_hidden_note_and_dispute_tag_attach_to_sentence():
    text = "<!-- Result of consensus on the talk page; do not change. -->Gamma three.{{Disputed inline|talk=Talk:X#Y|date=May 2026}}"
    g = text.index("Gamma")
    notes, tags = st.notes_and_tags(text, _sent_of(text, [(g, g + 12)]))
    assert 0 in notes and tags[0][0] == {"template": "disputed inline", "talk": "Talk:X#Y", "date": "May 2026"}


class _H:
    def __init__(self, times):
        import datetime as dt
        self.by_id = {r: {"timestamp": t} for r, t in times.items()}
        self._t = {r: dt.datetime.fromisoformat(t.replace("Z", "+00:00")) for r, t in times.items()}

    def time_of(self, r):
        return self._t.get(r)


def test_sentence_history_counts_removals_and_skips_page_wide():
    h = _H({1: "2020-01-01T00:00:00Z", 2: "2020-02-01T00:00:00Z", 3: "2020-02-01T05:00:00Z",
            4: "2020-03-01T00:00:00Z", 5: "2020-03-05T00:00:00Z", 6: "2020-04-01T00:00:00Z",
            7: "2020-04-01T00:10:00Z"})
    # sentence 0: two words, out at 2 back at 3 (5 h), out at 4 back at 5 (4 days); 6/7 page-wide
    toks = [[1, [3, 5, 7], [2, 4, 6], "one"], [1, [3, 5, 7], [2, 4, 6], "two"]] + \
        [[1, [7], [6], w] for w in "three four five six seven eight".split()]
    out = st.sentence_history(toks, list(range(8)), [0, 0] + [1] * 6, 7, h, lambda r: f"k{r}")
    s0 = out[0]
    assert s0["removed"] == 2 and s0["back_within_24h"] == 1 and s0["out_24h_or_more"] == 1
    assert s0["page_wide_removals"] == 1 and s0["removing_accounts"] == 2
    assert out[1]["removed"] == 0 and out[1]["in_place_since"] == "2020-01-01"   # blanking does not reset it


def test_persistence_counts_words_still_present():
    hist = au.History([{"revid": 1, "timestamp": "2020-01-01T00:00:00Z"},
                       {"revid": 2, "timestamp": "2021-06-01T00:00:00Z"},
                       {"revid": 3, "timestamp": "2022-06-01T00:00:00Z"}])
    toks = [[1, [], []], [1, [], [2]], [2, [], []], [3, [], []]]
    p = au.persistence(toks, hist, 3, years=(1, 5))
    assert p[0]["baseline"] == 2 and p[0]["words_then"] == 2 and p[0]["still_present"] == 2
    assert p[1]["baseline"] is None


def test_talk_section_ban_end_date_and_kinds():
    body = ("{{archive top|'''MORATORIUM ENFORCEMENT''' suspended until February 21, 2026. "
            "[[User:X|X]] 10:27, 21 February 2025 (UTC)}}\nText 09:00, 27 January 2025 (UTC)\n"
            "=== Moratorium proposal ===\n")
    r = talk.read_section("Language in the lead", body)
    assert r["moratorium_discussed"] and r["moratorium_in_closing"] and r["closed_on"] == "2025-02-21"
    assert r["ban_until"] == "2026-02-21" and r["started"] == "2025-01-27" and not r["rfc"]
    assert talk._clean_heading("Edit by [[User:Foo|Foo]] and Barbaz", {"Barbaz"}) == "Edit by [account] and [account]"


def test_authors_of_reads_links_and_skips_editors():
    a = sources.authors_of("{{cite book|last1=Morris|first1=Benny|author-link1=Benny Morris|"
                           "last2=Doe|first2=Jo|editor-last=Ed|title=T}}")
    assert a == [("Benny Morris", "Benny Morris"), ("Jo Doe", None)]


def test_position_split_positions_and_rules():
    from wtl.affiliation import position_split
    assert position_split(["left-wing", "centre-left", "liberal"]) == {"left": 1.0}   # positions win
    assert position_split(["liberal"], ["United States"]) == {"left": 1.0}
    assert position_split(["liberal"], ["Australia"]) == {"right": 1.0}
    assert position_split(["liberal"], ["Germany"]) == {}
    assert position_split(["liberal"], ["Japan", "United States"]) == {}
    assert position_split(["conservative"]) == {"right": 1.0}
    assert position_split(["zionist"]) == {} and position_split(["islamist"]) == {} and position_split(["nationalist"]) == {}
    assert position_split(["socialist", "conservative"]) == {"left": 0.5, "right": 0.5}
    assert position_split(["social liberalism"]) == {"centre": 0.5, "left": 0.5}
    assert position_split(["far-right", "centrist"]) == {"far right": 0.5, "centre": 0.5}
