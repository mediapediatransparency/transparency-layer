from wtl import outlets, siteprobe, sources

HOME = """<html><head><script>gtag('config', 'G-ABCDEF1234');</script>
<script type="application/ld+json">{"@type": "NewsMediaOrganization", "name": "Example News",
"parentOrganization": {"name": "Example Holdings"}, "ownershipFundingInfo": "https://ex.org/funding"}</script>
</head><body><a href="/about-us">About us</a><a href="https://other.org/about">x</a>
<footer>© 2024 Example Foundation. Registered charity no. 1234567. EIN: 12-3456789.
Example News is a project of the Example Foundation, a 501(c)(3) nonprofit.</footer></body></html>"""


def test_extract_reads_statements_numbers_and_ids():
    x = siteprobe.extract([{"kind": "home", "url": "https://ex.org/", "text": HOME}])
    regs = {(r["registry"], r["id"]) for r in x["registry_ids"]}
    assert ("UK registered charity", "1234567") in regs
    assert ("US employer identification number (EIN)", "12-3456789") in regs
    assert any(r.get("register_url", "").endswith("/123456789") for r in x["registry_ids"])
    assert {(t["service"], t["id"]) for t in x["trackers"]} == {("Google Analytics 4", "G-ABCDEF1234")}
    assert any("a project of the Example Foundation" in s["text"] for s in x["statements"])
    assert x["copyright"][0].startswith("Example Foundation")
    assert x["declared_organisation"][0]["parentOrganization"] == "Example Holdings"


def test_copyright_ignores_501c3():
    x = siteprobe.extract([{"kind": "home", "url": "https://a.org/",
                            "text": "<p>We are a 501(c)(3) nonprofit.</p>"}])
    assert x["copyright"] == []


def test_about_links_stay_on_the_site():
    links = siteprobe._about_links("https://ex.org/", HOME)
    assert links == [("about", "https://ex.org/about-us")]


def test_israeli_amuta_number():
    x = siteprobe.extract([{"kind": "home", "url": "https://n.org/",
                            "text": "<p>Institute for NGO Research - R.A. 58-0465508.</p>"}])
    assert [(r["registry"][:7], r["id"]) for r in x["registry_ids"]] == [("Israeli", "58-0465508")]


def test_domain_classes_and_public_suffixes():
    assert outlets.domain_class("pib.nic.in") == "government"
    assert outlets.domain_class("ox.ac.uk") == "academic"
    assert outlets.domain_class("who.int") == "international organisation"
    assert outlets.domain_class("bbc.co.uk") is None
    if sources.psl_sha256():
        assert sources.registrable("pib.nic.in") == "pib.nic.in"
        assert sources.registrable("news.bbc.co.uk") == "bbc.co.uk"


def test_not_english_without_quote_flag():
    text = ("A.<ref>{{cite web|url=https://x.ru/a|title=T|language=ru}}</ref> "
            "B.<ref>{{cite web|url=https://x.ru/b|title=T|language=ru|quote=Текст|trans-quote=Text}}</ref>")

    class Lay:
        section_of = [1] * len(text)
    block, _, _ = sources.compute(text, Lay(), [], [], None, {}, {})
    assert block["flags"]["not_english"] == 2
    assert block["flags"]["not_english_no_quote"] == 1
