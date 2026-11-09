from wtl.candidates import resolve_batch


def test_article_and_redirect_in_one_batch():
    q = {"redirects": [{"from": "Wahhabi", "to": "Wahhabism"}, {"from": "Wahabism", "to": "Wahhabism"}],
         "pages": [{"title": "Wahhabism", "pageviews": {"a": 10, "b": None}, "pageprops": {"wikibase_item": "Q1"}}]}
    out = resolve_batch(["Wahhabism", "Wahhabi", "Wahabism"], q)
    for t in ("Wahhabism", "Wahhabi", "Wahabism"):
        assert out[t] == {"title": "Wahhabism", "missing": False, "views": 10, "qid": "Q1"}


def test_normalised_redirect_and_missing():
    q = {"normalized": [{"from": "wahhabi", "to": "Wahhabi"}],
         "redirects": [{"from": "Wahhabi", "to": "Wahhabism"}],
         "pages": [{"title": "Wahhabism"}, {"title": "No such page", "missing": True}]}
    out = resolve_batch(["wahhabi", "No such page", "Not returned"], q)
    assert out["wahhabi"]["title"] == "Wahhabism" and not out["wahhabi"]["missing"]
    assert out["No such page"]["missing"] and out["Not returned"]["missing"]


def test_double_redirect():
    q = {"redirects": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}], "pages": [{"title": "C"}]}
    assert resolve_batch(["A"], q)["A"]["title"] == "C"
