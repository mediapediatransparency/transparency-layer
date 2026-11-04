from wtl import books, sources


def test_isbn_check_digits_and_conversion():
    assert books.to13("0-19-953556-6") == "9780199535569"
    assert books.to13("978-0-19-953556-9") == "9780199535569"
    assert books.to13("978-0-19-953556-8") is None          # wrong check digit
    assert books.to13("12345") is None


def test_isbn_found_in_citation_text():
    assert books.isbn_in("{{cite book|title=T|isbn=978-0-19-953556-9}}") == ("9780199535569",
                                                                           "978-0-19-953556-9")
    assert books.isbn_in("Smith (2001). ''T''. ISBN 0-19-953556-6.")[0] == "9780199535569"
    assert books.isbn_in("{{ISBN|9780199535569}}")[0] == "9780199535569"
    assert books.isbn_in("{{cite book|isbn=978-0-19-953556-8}}") == (None, "978-0-19-953556-8")


def test_registration_group_and_publisher_prefix():
    if not books.RANGES_XML.exists():
        return
    s = books.split("9789652295934")
    assert s["agency"] == "Israel" and s["registrant"] == "978-965-229"
    assert books.hyphenated("9780199535569") == "978-0-19-953556-9"


def test_item_ids():
    assert sources.item_id("{{cite book|isbn=0-19-953556-6|url=https://x.org/a}}") == "isbn:9780199535569"
    assert sources.item_id("{{cite journal|doi=10.1000/XYZ.1|url=https://x.org}}") == "doi:10.1000/xyz.1"
    assert sources.item_id("{{cite web|url=https://www.example.com/a/b/?utm_source=x}}") == \
        "url:example.com/a/b"
    assert sources.item_id("{{cite web|url=https://web.archive.org/web/2020/https://example.com/a}}") == \
        "url:example.com/a"
    assert sources.item_id("{{cite book|isbn=978-0-19-953556-8}}") == "isbn-invalid:9780199535568"
    assert sources.item_id("Some plain text") is None


def test_book_without_publisher_takes_open_library_publisher():
    text = "Text.<ref>{{cite book|last=Roe|title=T|isbn=0-19-953556-6}}</ref>"
    data = {"books": {"9780199535569": {"publishers": ["Oxford University Press"], "languages": ["eng"]}}}
    c = sources.find(text, None, data)[0]
    assert c["source"] == "name:oxford university press" and c["publisher_from"] == "Open Library"
    assert sources.find(text, None, {})[0]["source"] == "book (no publisher given)"


def test_book_without_publisher_takes_prefix_publisher():
    if not books.RANGES_XML.exists():
        return
    text = "Text.<ref>{{cite book|last=Roe|title=T|isbn=978-965-229-593-4}}</ref>"
    data = {"books": {}, "prefixes": {"978-965-229": {"wikidata": "Q1", "label": "Gefen"}}}
    c = sources.find(text, None, data)[0]
    assert c["source"] == "name:gefen" and c["publisher_from"] == "ISBN prefix (Wikidata)"
