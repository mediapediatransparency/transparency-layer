from wtl import sources

TEXT = (
    "Lead.<ref>{{cite web |url=https://www.haaretz.com/x |title=T |work=Haaretz}}</ref> "
    "More.<ref>{{cite book |url=https://books.google.com/b?id=1 |publisher=Zed Books |title=B}}</ref> "
    "Short.<ref>{{sfn|Morris|2004|p=12}}</ref> Bare.<ref>See https://edition.cnn.com/a</ref> "
    "Tweet.<ref>{{cite tweet|user=x|number=1|title=y}}</ref> Reuse.<ref name=\"a\" /> "
    "Plain.<ref>Some old pamphlet, 1921.</ref>\n"
    "==Sources==\n* {{cite book |last=Morris |first=Benny |year=2004 |publisher=Cambridge University Press |title=R}}\n"
    "* {{cite book |last=Other |year=1999 |publisher=Verso |title=Q}}\n"
)


def test_find_sources():
    got = [c["source"] for c in sources.find(TEXT)]
    assert got == ["haaretz.com", "name:zed books", "name:cambridge university press", "cnn.com",
                   "twitter.com", "unidentified", "name:verso"]


def test_short_footnote_resolves_and_counts_bibliography_once():
    cs = sources.find(TEXT)
    short = [c for c in cs if c["short"]]
    assert len(short) == 1 and short[0]["name"] == "Cambridge University Press"
    # the Morris entry is reached through its short footnote, so it is not counted again
    assert sum(1 for c in cs if c["source"] == "name:cambridge university press") == 1


def test_domains():
    assert sources.registrable(sources.host_of("https://www.bbc.co.uk/news/1")) == "bbc.co.uk"
    assert sources.host_of("https://web.archive.org/web/2020/https://www.jpost.com/a") == "jpost.com"
    assert sources.registrable("edition.cnn.com") == "cnn.com"


def test_google_books_link_without_publisher_is_a_book_not_google():
    t = ("A.<ref>Author, [https://books.google.com/books?id=abc&pg=PA1 ''Title''], p. 1.</ref> "
         "B.<ref>{{cite book |url=https://books.google.com/books?id=x |publisher=Zed Books |title=T}}</ref>")
    got = [c["source"] for c in sources.find(t)]
    assert got == ["book (no publisher given)", "name:zed books"]


def test_piped_link_in_publisher_is_kept_whole():
    t = "A.<ref>{{cite book |title=T |publisher=[[Brill Publishers|Brill]] |year=2001}}</ref>"
    assert [c["source"] for c in sources.find(t)] == ["name:brill"]


def test_free_text_matching_with_name_list():
    import re
    names = {"periodicals": {"new york times": "The New York Times"},
             "publishers": {"john wiley sons": "John Wiley & Sons"},
             "domains": {"new york times": "nytimes.com"}}
    names["_pub_re"] = re.compile(r"(?<![\w&])(John Wiley & Sons)(?![\w&])")
    t = ('A.<ref>"Death Ray" for Planes, \'\'New York Times\'\', 22 September 1940</ref> '
         "B.<ref>Rockman, ''Intellectual Property Law'', John Wiley & Sons, 2004, p. 198.</ref> "
         "C.<ref>Morris, 2001, pp. 259–260.</ref> D.<ref>[[#laurens|Henry Laurens (2005)]], p. 85</ref> "
         "E.<ref>Some book, 1999, {{ISBN|978-0-316-92919-6}}</ref> F.<ref>Something else.</ref>\n"
         "==Bibliography==\n* {{cite book |last=Morris |first=Benny |year=2001 |title=Righteous Victims "
         "|publisher=Vintage}}\n* {{cite book |last=Laurens |year=2005 |title=La question |publisher=Fayard "
         "|ref=laurens}}\n")
    got = [c["source"] for c in sources.find(t, names)]
    assert got == ["nytimes.com", "name:john wiley & sons", "name:vintage", "name:fayard",
                   "book (no publisher given)", "unidentified"]


def test_short_refs_to_plain_bibliography_and_to_other_footnotes():
    import re
    names = {"periodicals": {}, "publishers": {"vintage books": "Vintage Books"}, "domains": {}}
    names["_pub_re"] = re.compile(r"(?<![\w&])(Vintage Books)(?![\w&])")
    t = ("A.<ref>[[#morris birth|Benny Morris (2003)]], p. 67</ref> "
         "B.<ref>{{cite web |last=Poe |url=https://www.example.org/x |title=T}}</ref> "
         "C.<ref>Poe, pp. 171–172.</ref>\n==Bibliography==\n"
         "* {{anchor|morris birth}}Morris, Benny (2003). ''The Birth''. Vintage Books.\n")
    got = [c["source"] for c in sources.find(t, names)]
    assert got == ["name:vintage books", "example.org", "example.org"]


def test_opinion_and_hard_to_check_flags():
    t = ("A.<ref>{{cite web |url=https://www.nytimes.com/2024/01/02/opinion/x.html |title=T}}</ref> "
         "B.<ref>{{cite news |url=https://www.theguardian.com/commentisfree/2020/x |title=T}}</ref> "
         "C.<ref>{{cite book |title=T |publisher=Zed Books |year=2001}}</ref> "
         "D.<ref>{{cite book |title=T |publisher=Zed Books |year=2001 |page=12}}</ref> "
         "E.<ref>{{cite web |url=https://www.haaretz.co.il/x |language=he |url-status=dead |title=T}}</ref> "
         "F.<ref>{{cite news |url=https://www.wsj.com/articles/x |url-access=subscription |title=T}}</ref>")
    cs = sources.find(t)
    got = [sorted(sources.flags_of(t, c)) for c in cs]
    assert got == [["opinion"], ["opinion"], ["book_without_page", "no_link"], ["no_link"],
                   ["dead_link_no_archive", "not_english"], ["paywall_or_registration"]]


def test_rated_subdomain_kept_as_its_own_source():
    sources._SUBS = {"abcnews.go.com", "news.sky.com"}
    try:
        assert sources.source_domain("abcnews.go.com", "go.com") == "abcnews.go.com"
        assert sources.source_domain("x.abcnews.go.com", "go.com") == "abcnews.go.com"
        assert sources.source_domain("espn.go.com", "go.com") == "go.com"
        assert sources.source_domain("sky.com", "sky.com") == "sky.com"
    finally:
        sources._SUBS = None
