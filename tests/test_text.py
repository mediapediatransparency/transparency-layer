from wtl.text.align import align
from wtl.text.sentences import split
from wtl.text.wikitext import layout


def prose_of(text):
    lay = layout(text)
    return "".join(c for c, p in zip(text, lay.prose) if p)


def test_align_recovers_case_and_offsets():
    text = "The '''Quick''' Fox."
    al = align(text, ["the", "'''", "quick", "'''", "fox", "."])
    assert al.unaligned == 0 and al.skipped_chars == 0
    assert [text[a:b] for a, b in al.spans] == ["The", "'''", "Quick", "'''", "Fox", "."]


def test_align_handles_length_changing_lowercase():
    text = "İstanbul is big"
    al = align(text, ["i̇stanbul", "is", "big"])
    assert al.unaligned == 0
    assert text[al.spans[1][0]:al.spans[1][1]] == "is"


def test_prose_excludes_markup_but_keeps_visible_link_text():
    text = ("{{Infobox|name=X}}'''Gaza''' is a [[Gaza Strip|strip]] city.<ref>{{cite web|title=T}}"
            "</ref> See [[Egypt]].[[File:a.jpg|thumb|Caption words]]<!-- hidden -->\n"
            "[[Category:Cities]]")
    assert prose_of(text) == "Gaza is a strip city. See Egypt.\n"


def test_tables_and_appendix_sections_are_not_prose():
    text = "Lead text.\n{|\n|cell\n|}\n== History ==\nBody.\n== See also ==\n* [[Other]]\n"
    lay = layout(text)
    prose = "".join(c for c, p in zip(text, lay.prose) if p)
    assert "cell" not in prose and "Other" not in prose
    assert "Body." in prose and "History" not in prose
    assert [s.title for s in lay.sections] == ["(lead)", "History", "See also"]
    assert [s.appendix for s in lay.sections] == [False, False, True]
    assert lay.section_of[text.index("Body")] == 1 and lay.section_of[0] == 0


def test_quote_template_text_counts_as_prose():
    assert "Said this." in prose_of("{{blockquote|text=Said this.|author=A}}")


def test_sentence_split_respects_abbreviations_and_initials():
    text = ("Dr. Smith met J. R. Tolkien in the U.S. in c. 1950. They spoke. "
            "Then e.g. tea was served!\nNew line here\n== S ==\nBody one. Body two.")
    lay = layout(text)
    ss = split(text, lay)
    assert [s.text for s in ss] == [
        "Dr. Smith met J. R. Tolkien in the U.S. in c. 1950.", "They spoke.",
        "Then e.g. tea was served!", "New line here", "Body one.", "Body two."]
    assert [s.id for s in ss] == ["lead-1", "lead-2", "lead-3", "lead-4", "sec1-1", "sec1-2"]
    first = ss[0]
    assert "".join(text[o] for o in first.offsets) == first.text
