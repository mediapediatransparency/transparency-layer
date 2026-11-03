import datetime as dt

from wtl import sanctions as sanc
from wtl.metrics import accountability, authorship as au

HIST = au.History([
    {"revid": 10, "timestamp": "2020-01-01T00:00:00Z", "user": "Alpha", "userid": 1},
    {"revid": 20, "timestamp": "2020-01-01T12:00:00Z", "user": "1.2.3.4", "userid": 0},
    {"revid": 30, "timestamp": "2020-03-01T00:00:00Z", "user": "Beta", "userid": 2},
    {"revid": 40, "timestamp": "2021-06-01T00:00:00Z", "user": "Alpha", "userid": 1},
])


def W(editor, rev, lead=False, sent=0):
    return au.Word(editor, rev, lead, sent)


def test_editor_keys_and_account_types():
    assert au.editor_key(10, "1", HIST) == ("u1", "Alpha", "registered")
    assert au.editor_key(20, "0|1.2.3.4", HIST) == ("n:1.2.3.4", "1.2.3.4", "ip")
    assert au.editor_key(99, "0|~2025-1234", HIST)[2] == "temporary"


def test_labels_by_share_with_deterministic_ties():
    words = [W("u1", 10), W("u2", 30), W("u2", 30), W("n:x", 20)]
    # u1 and n:x tie on one word each; u1 contributed earlier (rev 10 < rev 20)
    assert au.label_editors(words) == {"u2": "Editor 1", "u1": "Editor 2", "n:x": "Editor 3"}


def test_concentration():
    from collections import Counter
    c = au.concentration(Counter({"a": 6, "b": 3, "c": 1}))
    assert c["top_shares"] == {"1": 0.6, "3": 1.0, "5": 1.0, "10": 1.0}
    assert c["editors_for_50pct"] == 1 and c["editors_for_80pct"] == 2
    assert c["hhi"] == round(0.36 + 0.09 + 0.01, 6)


def test_survival_uses_presence_at_horizon_and_ignores_later_events():
    toks = [
        [10, [], [20]],        # removed 12h later -> dead at 48h, 30d, 365d
        [10, [30], [20]],      # removed, restored at 2 months -> dead at 48h/30d, alive at 365d
        [30, [], []],          # never removed
        [30, [], [40]],        # removed after 1 year+3 months -> alive at 365d
        [40, [], []],          # added at the analysed revision: too young for any horizon
    ]
    s = au.survival(toks, HIST, 40, lambda r: "u1" if r in (10, 40) else "u2")
    assert s["article"]["48h"] == [4, 2]
    assert s["article"]["30d"] == [4, 2]
    assert s["article"]["365d"] == [4, 3]
    assert s["per_editor"]["u1"]["365d"] == [2, 1]
    blk = au.survival_block(s["per_editor"]["u1"], s["article"])
    assert blk["365d"]["rate"] == 0.5 and blk["365d"]["vs_article"] == round(0.5 / 0.75, 6)


def S(t, area="A-I", date="2020-02-01"):
    return sanc.Sanction("x", t, area, "indefinite", date, "AE", "https://x", "seed_list")


def test_topic_bans_only_apply_in_their_area_site_bans_everywhere():
    assert S("topic_ban").applies_to("A-I") and not S("topic_ban").applies_to("EE")
    assert S("site_ban").applies_to("") and S("sockpuppet").applies_to("EE")


def test_before_after_sanction_split():
    words = [W("u1", 10, lead=True), W("u1", 40), W("u2", 30)]
    out = accountability.compute(words, {"u1": [S("topic_ban")]}, HIST)
    assert out["sanctioned_words"] == 2 and out["sanctioned_share"] == round(2 / 3, 6)
    assert out["sanctioned_lead_share"] == 1.0
    assert out["timing"]["added_before_sanction_words"] == 1
    assert out["timing"]["added_after_sanction_words"] == 1


def test_block_classification():
    base = {"expiry": "infinity", "partial": False, "timestamp": "2024-01-01T00:00:00Z", "id": 5}
    assert sanc.classify_block({**base, "reason": "{{checkuserblock-account}}"}) == "sockpuppet"
    assert sanc.classify_block({**base, "reason": "Abusing [[WP:SOCK|multiple accounts]]"}) == "sockpuppet"
    assert sanc.classify_block({**base, "reason": "[[WP:CBAN|Community ban]]"}) == "site_ban"
    assert sanc.classify_block({**base, "reason": "Disruptive editing"}) is None
    assert sanc.classify_block({**base, "reason": "sock", "expiry": "2025-01-01T00:00:00Z"}) is None
    assert sanc.classify_block({**base, "reason": "sock", "partial": True}) is None


def test_sanction_end_dates():
    assert sanc.end_from_duration("2024-01-31", "1 month") == "2024-02-29"
    assert sanc.end_from_duration("2024-03-01", "90 days") == "2024-05-30"
    assert sanc.end_from_duration("2024-03-01", "6 months and 500 edits") == "2024-09-01"
    assert sanc.end_from_duration("2023-01-01", "until 2023-08-31") == "2023-08-31"
    assert sanc.end_from_duration("2023-01-01", "indefinite") == ""
    assert sanc.end_from_duration("2023-01-01", "not stated") == ""


def test_timing_during_versus_after_ban_ended():
    # HIST has revisions dated so that W(...,10) is before 2020-02-01 and W(...,40) after it.
    fixed = sanc.Sanction("x", "topic_ban", "A-I", "1 day", "2020-02-01", "AE", "https://x",
                          "seed_list", "2020-02-02", "duration")
    w_after = W("u1", 40)
    t = HIST.time_of(40).date().isoformat()
    long = sanc.Sanction("x", "topic_ban", "A-I", "until", "2020-02-01", "AE", "https://x",
                         "seed_list", "2999-01-01", "duration")
    openended = sanc.Sanction("x", "topic_ban", "A-I", "indefinite", "2020-02-01", "AE",
                              "https://x", "seed_list")
    assert accountability.word_timing(W("u1", 10), [fixed], HIST) == "before"
    assert accountability.word_timing(w_after, [long], HIST) == "during"
    assert accountability.word_timing(w_after, [openended], HIST) == "during_open"
    if t >= "2020-02-02":
        assert accountability.word_timing(w_after, [fixed], HIST) == "after_ended"
