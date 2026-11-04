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
