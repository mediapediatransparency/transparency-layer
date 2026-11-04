from wtl import outlets


def test_row_attributes_in_either_order():
    t = ('|- class="s-nc" id="Cato Institute"\n| x {{WP:RSPUSES|cato.org}}\n'
         '|- id="CBS News" class="s-gr"\n| y {{WP:RSPUSES|cbsnews.com}}\n')
    ms = list(outlets.ROW.finditer(t))
    assert [m.group(1) for m in ms] == ["nc", "gr"]
    assert [outlets.ROW_ID.search(m.group(0)).group(1) for m in ms] == ["Cato Institute", "CBS News"]


def test_combined_status():
    r = lambda i, s: {"id": i, "status": s}  # noqa: E731
    assert outlets.combined_status([r("The Guardian", "gr"), r("The Guardian blogs", "nc")]) == "gr"
    assert outlets.combined_status([r("Fox News", "nc"), r("Fox News (talk shows)", "gu")]) == "m"
    assert outlets.combined_status([r("BBC", "gr")]) == "gr"
    assert outlets.combined_status([r("A 2012-2018", "nc"), r("A 2019-present", "gu")]) == "m"


def test_sourced_ignores_import_only_references():
    imported = {"references": [{"snaks": {"P143": [{}]}}]}
    cited = {"references": [{"snaks": {"P854": [{}], "P813": [{}]}}]}
    assert not outlets._sourced(imported)
    assert not outlets._sourced({})
    assert outlets._sourced(cited)


def test_checklist_for_an_organisation():
    e = {"kind": "think tank", "wikipedia_rating": None, "mbfc": {"bias": "right"},
         "registries": [{"registry": "Charity Commission for England and Wales", "id": "123",
                         "property": "P3057", "url": "https://example.org/123"}],
         "associations": {"founded by": [{"label": "A", "wikidata": "Q1"}]},
         "political_alignment": [], "political_ideology": [], "enwiki": None}
    cl = outlets.checklist(e)
    got = {i["check"]: i["found"] for i in cl["items"]}
    assert cl["type"] == "organisation"
    assert got["registered in a public registry"] and got["founders recorded"]
    assert not got["funders recorded"] and not got["rated on Wikipedia's list"]
    assert got["rated by an independent assessor"]
    assert "US public tax filing (Form 990) found" not in got   # only asked when a US tax ID exists


def test_checklist_for_a_journal_and_none_for_a_newspaper():
    j = {"kind": "academic journal", "journal_ids": {"issn": ["0377-919X"]},
         "academic_level": {"level": 1, "type": "journal or series", "url": "u"}}
    got = {i["check"]: i["found"] for i in outlets.checklist(j)["items"]}
    assert got["ISSN recorded"] and got["academic level assigned (JUFO, Finland)"]
    assert not got["classed as a predatory journal on Wikidata"]
    assert outlets.checklist({"kind": "newspaper or news website"}) is None
