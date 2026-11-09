from wtl import activity


def _hist():
    return [{"revid": 1, "timestamp": "2020-01-01T00:00:00Z", "userid": 5, "user": "A"},
            {"revid": 2, "timestamp": "2026-01-01T00:00:00Z", "userid": 0, "user": "1.2.3.4"},
            {"revid": 3, "timestamp": "2026-01-01T01:00:00Z", "userid": 9, "user": "~2026-1"},
            {"revid": 4, "timestamp": "2026-01-03T00:00:00Z", "userid": 5, "user": "A"},
            {"revid": 5, "timestamp": "2026-01-05T00:00:00Z", "userid": 5, "user": "A"},
            {"revid": 6, "timestamp": "2026-02-05T00:00:00Z", "userid": 5, "user": "A"}]


def test_edits():
    e = activity.edits(_hist(), 6)
    assert e["edits_total"] == 6 and e["edits_by_year"] == {"2020": 1, "2026": 5}
    y = e["last_365_days"]
    assert y["edits"] == 5 and y["accounts"] == 3 and y["share_without_registered_account"] == 0.4


def test_back_and_forth_splits_quick_and_lasting():
    times = {h["revid"]: h["timestamp"] for h in _hist()}
    # token 1: removed at 2, back at 3 (1 hour: quick); token 2..7: removed at 2 back at 4 (2 days),
    # removed at 5 back at 6 (a month): lasting twice
    toks = [[1, [3], [2], "alpha"]] + [[1, [4, 6], [2, 5], w] for w in "one two three four five six".split()]
    b = activity.back_and_forth({"tokens": toks}, list(range(0, 7)), 6, times)
    assert b["words"] == 7 and b["words_removed_twice_or_more"] == 6 and b["words_with_quick_repair"] == 1
    assert b["passages"][0]["words"] == 6 and b["passages"][0]["latest_revision"] == 6


def test_history_positions_finds_offset_and_refuses_mismatch():
    from wtl.fetch import wikiwho as ww
    allc = {"tokens": [[1, [], [], "a"], [1, [], [], "b"], [2, [], [], "c"]]}
    rc = [["b", 1, "x"], ["c", 2, "x"]]
    assert ww.history_positions(allc, [1, 2], rc) == [1, 2]      # IDs start at 0
    assert ww.history_positions(allc, [2, 3], rc) == [1, 2]      # IDs start at 1
    assert ww.history_positions(allc, [0, 1], [["q", 9, "x"], ["r", 9, "x"]]) is None


def test_protection_periods_expiry_moves_and_unprotect():
    ev = [{"date": "2020-01-01", "action": "protect", "edit_level": "autoconfirmed", "expiry": "infinite"},
          {"date": "2020-03-01", "action": "move_prot", "edit_level": "", "expiry": ""},
          {"date": "2020-06-01", "action": "modify", "edit_level": "sysop", "expiry": "2020-06-08"},
          {"date": "2020-09-01", "action": "unprotect", "edit_level": "", "expiry": ""}]
    assert activity.protection_periods(ev, "2021-01-01") == [
        {"from": "2020-01-01", "to": "2020-06-01", "level": "autoconfirmed"},
        {"from": "2020-06-01", "to": "2020-06-08", "level": "sysop"}]
