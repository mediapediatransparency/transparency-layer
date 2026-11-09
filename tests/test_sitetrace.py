from wtl import sitetrace


def test_parse_date_needs_a_full_date():
    assert sitetrace.parse_date("4 March 2012") == "2012-03-04"
    assert sitetrace.parse_date("March 4, 2012") == "2012-03-04"
    assert sitetrace.parse_date("2012-03-04") == "2012-03-04"
    assert sitetrace.parse_date("Sept. 9, 2015") == "2015-09-09"
    assert sitetrace.parse_date("March 2012") is None
    assert sitetrace.parse_date("2012") is None


def test_verification_codes_and_spf():
    assert sitetrace.VERIFY.match("google-site-verification=abc123XYZ").group(2) == "abc123XYZ"
    assert sitetrace.VERIFY.match("facebook-domain-verification=q1w2e3").group(1) == "facebook-domain-verification"
    assert sitetrace.VERIFY.match("v=spf1 include:_spf.google.com ~all") is None
    assert sitetrace.SPF_INCLUDE.findall("v=spf1 include:_spf.google.com include:mail.example.org ~all") == [
        "_spf.google.com", "mail.example.org"]


def test_archive_addresses():
    m = sitetrace.WB_TS.match("https://web.archive.org/web/20120304101010/http://ex.org/a")
    assert m.group(1) == "20120304101010" and m.group(2) == "http://ex.org/a"
    assert sitetrace._raw_copy("https://web.archive.org/web/20120304101010/http://ex.org/a") == \
        "https://web.archive.org/web/20120304101010id_/http://ex.org/a"
    assert sitetrace._ts_date("20120304101010") == "2012-03-04"


def test_groups_leave_out_common_values():
    vals = {f"s{i}.org": ["big-host.net"] for i in range(30)}
    vals.update({"a.org": ["small.net"], "b.org": ["small.net"], "c.org": ["only.net"]})
    keep, common = sitetrace._groups(vals)
    assert keep == [{"value": "small.net", "sites": ["a.org", "b.org"]}]
    assert common == [{"value": "big-host.net", "sites": 30}]


def test_link_mark():
    from wtl.sitetrace import link_mark
    assert link_mark("|url=http://x.com |url-status=usurped |title=a") == "usurped"
    assert link_mark("|url=http://x.com | url-status = live}}") == "live"
    assert link_mark("|url=http://x.com |dead-url=yes") == "dead"
    assert link_mark("|deadurl=no|") == "live"
    assert link_mark("|url=http://x.com |title=a") == "none"
def test_link_mark_comment():
    from wtl.sitetrace import link_mark
    assert link_mark("|url-status=dead<!--server errors-->|") == "dead"


def test_title_changed():
    from wtl.sitetrace import title_changed
    assert title_changed("The Bosnian Institute", "Slot Gacor Hari Ini") is True
    assert title_changed("VG - Norges største nyhetsside", "VG – Nyheter, sport og underholdning") is False
    assert title_changed("", "Anything") is None


def test_mark_and_param():
    from wtl.sitetrace import _mark_in, _param_before
    toks = [[t, n, "e"] for n, t in enumerate(["{{", "cite", "|", "url", "=", "https", ":", "/", "/", "a", ".", "com",
                                                "|", "url", "-", "status", "=", "live", "}}"])]
    assert _param_before(toks, 9) == "url"
    assert _mark_in(toks, 0, len(toks) - 1) == ("live", 17)
