from wtl import affiliation as af


def test_political_type_categories_only():
    cats = ["Left-wing book publishing companies", "Liberal mass media in the United Kingdom",
            "Conservative media in Israel", "Right-wing think tanks", "Liberalism in Israel",
            "Anti-communist organizations in the United States", "Political magazines published in the United States",
            "State media", "Conservative magazines published in the United States"]
    assert af.category_labels(cats) == ["conservative", "left-wing", "liberal", "right-wing", "state media"]


def test_nationality_prefix_and_propaganda_categories():
    assert af.category_labels(["American conservative websites", "Alt-right websites"]) == ["alt-right", "conservative"]
    assert af.category_labels(["United States government propaganda organizations"]) == ["propaganda organisation"]
    assert af.category_labels(["Russian propaganda organizations", "Chinese propaganda organisations"]) == ["propaganda organisation"]
    # topic categories are not affiliations
    assert af.category_labels(["Antisemitic propaganda", "Communist propaganda", "Propaganda in China",
                               "Anti-Zionism in the United States", "Far-right politics in Iran"]) == []


def test_labels_unify_word_forms_and_mark_missing():
    e = {"political_alignment": ["centre-left"], "political_ideology": ["Liberalism"], "wikidata": "Q1"}
    got = af.labels_for(e, ["Liberal mass media in the United Kingdom"])
    assert got["labels"] == ["centre-left", "liberal"]
    assert af.labels_for({"wikidata": "Q2"}, [])["labels"] == [af.NONE]
    assert af.labels_for({}, None)["labels"] == [af.NO_ENTRY]


def test_several_labels_share_a_citation():
    from wtl.patterns import editor_ratings
    outlets = {"a.com": {"affiliation": {"labels": ["conservative", "liberal"]}},
               "b.com": {"affiliation": {"labels": ["none recorded"]}}}
    r = editor_ratings({"a.com": 2, "b.com": 2}, outlets)["affiliation"]
    assert r["mix"] == {"conservative": 0.25, "liberal": 0.25, "none recorded": 0.5}
