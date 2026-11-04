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
