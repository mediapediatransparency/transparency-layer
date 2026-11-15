from wtl import redact


def test_editor_link_and_ip():
    s = "Armed conflict that took place in the late 709s to [[Special:Contributions/192.0.2.44"
    assert redact.text(s) == "Armed conflict that took place in the late 709s to [redacted:editor-link]"
    assert redact.text("see [[User:Example|me]] now") == "see [redacted:editor-link] now"
    assert redact.text("from 10.0.0.1 today") == "from [redacted:ip-address] today"


def test_ordinary_text_untouched():
    for s in ["Theater of World War II fought in the Pacific and Asia", "Version 1.2.3 released",
              "Ruling party of China", None, ""]:
        assert redact.text(s) == s


def test_by_hand_list(monkeypatch):
    import hashlib
    h = lambda t: {"sha256": hashlib.sha256(t.encode()).hexdigest(), "length": len(t), "reason": "personal-details"}
    monkeypatch.setattr(redact, "_BY_HAND", {"Test article": [h("Jane Q. Sample"), h("Age: 33")]})
    s = "Jane Q. Sample is a singer\nAge: 33\nHeight: tall"
    out = redact.text(s, "Test article")
    assert out == "[redacted:personal-details] is a singer\n[redacted:personal-details]\nHeight: tall"
    assert redact.text(s, "Some other article") == s


def test_render_skips_scripts():
    h = "<p>a [redacted:ip-address] b</p><script>var x='[redacted:ip-address]'</script>"
    out = redact.render(h)
    assert "class='redacted'" in out and "var x='[redacted:ip-address]'" in out
