from wtl import patterns as pm

OUT = {"a.com": {"audience_leaning": {"score": 0.5}, "mbfc": {"bias": "right"}},
       "b.com": {"audience_leaning": {"score": -0.5}, "mbfc": {"bias": "far left"}},
       "c.com": {}}


def test_editor_ratings_weights_by_citations():
    r = pm.editor_ratings({"a.com": 3, "b.com": 1, "c.com": 10}, OUT)
    assert r["audience_leaning"] == {"mean": 0.25, "rated": 4}
    assert r["mbfc"]["mix"] == {"right": 0.75, "left": 0.25}
    assert r["wikipedia_rating"]["mix"] == {"not listed": 1.0}


def test_writers_figures_weight_by_text_share_and_skip_thin_editors():
    ratings = {"x": pm.editor_ratings({"a.com": 5}, OUT),        # +0.5, 5 rated
               "y": pm.editor_ratings({"b.com": 5}, OUT),        # -0.5, 5 rated
               "z": pm.editor_ratings({"a.com": 2}, OUT)}        # too few rated: left out
    per = {"x": {"share": 0.6}, "y": {"share": 0.2}, "z": {"share": 0.2}}
    w = pm.writers_figures(per, ratings)
    assert w["audience_leaning"]["mean"] == 0.25          # (0.6*0.5 + 0.2*-0.5) / 0.8
    assert w["audience_leaning"]["text_covered"] == 0.8
    assert w["audience_leaning"]["writers"] == 2
    assert w["mbfc"]["mix"] == {"right": 0.75, "left": 0.25}


def test_sample_keys_top_n_per_area_registered_only():
    from wtl.patterns import sample_keys
    per = {"A1": {"u1": {"words": 50}, "u2": {"words": 30}, "n:1.2.3.4": {"words": 999}},
           "A2": {"u2": {"words": 40}, "u3": {"words": 10}},
           "B1": {"u4": {"words": 5}, "u3": {"words": 5}},
           "X": {"u9": {"words": 999}}}
    areas = {"A1": "AA", "A2": "AA", "B1": "BB", "X": ""}
    # area AA: u2 70, u1 50 -> top 1 is u2; area BB: tie u3/u4 broken by key -> u3
    assert sample_keys(per, areas, 1) == {"u2", "u3"}
    assert sample_keys(per, areas, 2) == {"u1", "u2", "u3", "u4"}
