from wtl.metrics import changes
from wtl.words import Matcher

# revision 1 (editor A) writes "hamas militants attacked https://www.example.org/x";
# revision 2 (editor B) removes "militants" and the link, adds "terrorists";
# revision 3 (editor A) restores "militants".
TOKS = [
    [1, [], [], "hamas"],
    [1, [3], [2], "militants"],
    [1, [], [], "attacked"],
    [1, [], [2], "https"], [1, [], [2], "://"], [1, [], [2], "www"], [1, [], [2], "."],
    [1, [], [2], "example"], [1, [], [2], "."], [1, [], [2], "org"],
    [2, [], [], "terrorists"],
]
CURRENT = [["hamas", 1, "A"], ["militants", 1, "A"], ["attacked", 1, "A"], ["terrorists", 2, "B"]]
KEY = {1: "A", 2: "B", 3: "A"}.get


def test_removals_and_terms():
    m = Matcher({"armed": ["militant", "terrorist"]})
    per, art, ev = changes.compute(TOKS, CURRENT, 3, KEY, m)
    b = per["B"]
    assert b["words_removed"] == 5              # militants + https, www, example, org
    assert b["others_words_removed"] == 5
    assert b["words_removed_later_restored"] == 1
    assert dict(b["sources_removed"]) == {"example.org": 1}
    assert dict(b["terms_removed"]) == {("armed", "militant"): 1}
    assert dict(b["terms_inserted"]) == {("armed", "terrorist"): 1}
    assert dict(per["A"]["terms_inserted"]) == {("armed", "militant"): 1}
    assert ev["B"] == [2]


def test_events_after_the_analysed_revision_are_ignored():
    per, art, _ = changes.compute(TOKS, CURRENT, 1, KEY, None)
    assert art["words_removed"] == 0
