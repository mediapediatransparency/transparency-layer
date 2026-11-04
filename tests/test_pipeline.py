"""End to end on a fixed three-revision history, with every network call replaced."""

import re

import pytest

from wtl import checks, pipeline
from wtl.fetch import mediawiki as mw, wikiwho as ww
from wtl.report import html, json_writer

TEXT = ("'''Testland''' is a place.<ref>{{cite web|title=Src}}</ref> It has hills.\n"
        "== History ==\nAlice founded it. Bob named it.\n")
TOKENS = [  # (str, origin revision, WikiWho editor)
    ("'''", 1, "11"), ("testland", 1, "11"), ("'''", 1, "11"), ("is", 1, "11"), ("a", 1, "11"),
    ("place", 1, "11"), (".", 1, "11"), ("<", 2, "22"), ("ref", 2, "22"), (">", 2, "22"),
    ("{{", 2, "22"), ("cite", 2, "22"), ("web", 2, "22"), ("|", 2, "22"), ("title", 2, "22"),
    ("=", 2, "22"), ("src", 2, "22"), ("}}", 2, "22"), ("<", 2, "22"), ("/", 2, "22"),
    ("ref", 2, "22"), (">", 2, "22"), ("it", 2, "22"), ("has", 2, "22"), ("hills", 2, "22"),
    (".", 2, "22"), ("==", 1, "11"), ("history", 1, "11"), ("==", 1, "11"), ("alice", 3, "33"),
    ("founded", 3, "33"), ("it", 3, "33"), (".", 3, "33"), ("bob", 1, "11"), ("named", 1, "11"),
    ("it", 1, "11"), (".", 1, "11"),
]
HIST = [
    {"revid": 1, "parentid": 0, "timestamp": "2020-01-01T00:00:00Z", "user": "Founder", "userid": 11, "hidden": False},
    {"revid": 2, "parentid": 1, "timestamp": "2021-01-01T00:00:00Z", "user": "Sourcer", "userid": 22, "hidden": False},
    {"revid": 3, "parentid": 2, "timestamp": "2023-01-01T00:00:00Z", "user": "Writer", "userid": 33, "hidden": False},
]


@pytest.fixture
def offline(monkeypatch, tmp_path):
    csvp = tmp_path / "sanctions.csv"
    csvp.write_text("username,sanction_type,area,duration,date,authority,decision_url,source_quote,notes\n"
                    "Sourcer,topic_ban,A-I,indefinite,2022-06-01,AE,https://example.org/d?oldid=9,q,\n"
                    "Writer,topic_ban,EE,indefinite,2022-06-01,AE,https://example.org/d?oldid=9,q,\n",
                    encoding="utf-8")
    monkeypatch.setattr(mw, "get_revision", lambda r: {
        "revid": 3, "parentid": 2, "pageid": 7, "title": "Testland", "timestamp": HIST[-1]["timestamp"],
        "user": "Writer", "userid": 33, "sha1": "x", "content": TEXT})
    monkeypatch.setattr(ww, "rev_content", lambda r: {"revid": 3, "tokens": [list(t) for t in TOKENS]})
    monkeypatch.setattr(mw, "get_history", lambda p, r: [h for h in HIST if h["revid"] <= r])
    monkeypatch.setattr(pipeline.cache, "load", lambda p: {
        "covers_revid": 3, "tokens": [[o, [], []] for s, o, e in TOKENS if re.search(r"\w", s)]})
    monkeypatch.setattr(mw, "resolve_users", lambda names: {
        n: {"userid": {"Sourcer": 22, "Writer": 33}[n], "name": n, "missing": False} for n in names})
    monkeypatch.setattr(mw, "block_snapshot", lambda r, names: {"date": "2026-11-03", "blocks": {
        "Founder": [{"id": 1, "timestamp": "2024-01-01T00:00:00Z", "expiry": "infinity",
                     "reason": "{{checkuserblock-account}}", "partial": False}]}})
    monkeypatch.setattr(pipeline.coi, "talk_at", lambda title, ts: {
        "revid": 99, "content": "{{Connected contributor|User1=Writer|U1-declared=yes}}"})
    monkeypatch.setattr(pipeline.coi, "resolve_users", lambda names: {
        n: {"userid": {"Sourcer": 22, "Writer": 33}[n], "name": n, "missing": False} for n in names})
    return csvp


def test_record_shares_labels_and_sanctions(offline):
    rec = pipeline.analyse(revid=3, area="A-I", sanctions_path=offline)
    a = rec["authorship"]
    # prose words: Testland is a place (4, rev1) It has hills (3, rev2) Alice founded it (3, rev3)
    # Bob named it (3, rev1) -> Founder 7, Sourcer 3, Writer 3
    assert a["total_words"] == 13 and a["lead_words"] == 7
    assert [(e["label"], e["words"]) for e in a["editors"]] == [
        ("Editor 1", 7), ("Editor 2", 3), ("Editor 3", 3)]
    assert sum(e["words"] for e in a["editors"]) == a["total_words"]
    assert abs(sum(e["share"] for e in a["editors"]) - 1) < 1e-9
    # Sourcer: A-I topic ban applies; Writer: EE ban does not apply here; Founder: sock block
    flags = {e["label"]: [s["type"] for s in e["sanctions"]] for e in a["editors"]}
    assert flags == {"Editor 1": ["sockpuppet"], "Editor 2": ["topic_ban"], "Editor 3": []}
    assert a["sanctioned_share"] == round(10 / 13, 6)
    lead = [s for s in rec["sentences"] if s["id"].startswith("lead")]
    assert [s["text"] for s in lead] == ["Testland is a place.", "It has hills."]
    assert lead[1]["authors"] == ["Editor 2"] and lead[1]["added_before_sanction"] is True
    assert rec["sentences"][2]["authors"] == ["Editor 3"]
    assert rec["sentences"][2]["author_sanctioned"] is False


def test_json_is_byte_identical_and_html_is_anonymous(offline):
    r1 = json_writer.dumps(pipeline.analyse(revid=3, area="A-I", sanctions_path=offline))
    r2 = json_writer.dumps(pipeline.analyse(revid=3, area="A-I", sanctions_path=offline))
    assert r1 == r2
    rec = pipeline.analyse(revid=3, area="A-I", sanctions_path=offline)
    page = html.render(rec)
    visible = checks.visible_text(page)
    for name in ("Founder", "Sourcer", "Writer"):
        assert name not in visible
        assert name not in r1


def test_declared_connection_is_matched_to_the_editor_label(offline):
    rec = pipeline.analyse(revid=3, area="A-I", sanctions_path=offline)
    d = rec["declared_interests"]
    assert d["talk_page_revision"] == 99
    assert d["notices"][0]["notice"] == "connected contributor"
    assert d["notices"][0]["editors"] and "Writer" not in str(d)
