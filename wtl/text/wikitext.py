"""Decide which characters of the wikitext a reader actually sees as prose, and where sections
begin.

Counted as prose: running text, the visible part of internal links, external-link titles,
bold/italic and similar inline markup, block quotes, and the text argument of a few inline-text
templates (nowrap, lang, quote).
Not counted: templates (infoboxes, citation templates, navboxes), references, tables, files and
images (including captions), categories, comments, headings, and appendix sections such as
"References", "See also" and "External links".
"""

from dataclasses import dataclass, field

import mwparserfromhell as mwp
from mwparserfromhell.nodes import (Comment, ExternalLink, Heading, HTMLEntity, Tag, Template,
                                    Text, Wikilink)

PROSE_TAGS = {
    "b", "i", "u", "s", "strike", "del", "ins", "small", "big", "span", "sup", "sub",
    "blockquote", "poem", "div", "center", "abbr", "q", "cite", "em", "strong", "font", "p",
    "nowiki", "tt", "code", "var", "kbd", "mark", "bdi", "bdo", "dfn", "time", "data",
}
HIDDEN_LINK_NS = {"file", "image", "category", "media"}
APPENDIX_SECTIONS = {
    "references", "notes", "citations", "sources", "bibliography", "further reading",
    "external links", "see also", "footnotes", "works cited", "notes and references",
    "references and notes", "general and cited sources", "cited sources", "general sources",
    "explanatory notes", "endnotes", "cited works", "literature",
}
# template name -> parameters whose value is shown inline as prose
TEXT_TEMPLATES = {
    "nowrap": ("1",), "lang": ("2", "text"), "blockquote": ("1", "text", "quote"),
    "quote": ("1", "text", "quote"), "cquote": ("1", "text", "quote"),
}


@dataclass
class Section:
    index: int        # 0 = lead
    title: str
    level: int
    start: int        # character offset where the section's heading begins
    appendix: bool


@dataclass
class Layout:
    prose: bytearray                 # 1 if the character is prose
    section_of: list                 # section index per character
    sections: list = field(default_factory=list)


def _tag_contents_offset(s: str, node: Tag) -> int | None:
    if node.contents is None:
        return None
    c = str(node.contents)
    if not c:
        return None
    if s.endswith(c):
        return len(s) - len(c)
    wm = node.wiki_markup
    if wm and s.endswith(wm) and s[: -len(wm)].endswith(c):
        return len(s) - len(wm) - len(c)
    k = s.rfind("</")
    if k > 0 and s[:k].endswith(c):
        return k - len(c)
    i = s.find(c)
    return i if i >= 0 else None


def _walk(code, base: int, spans: list) -> None:
    pos = base
    for node in code.nodes:
        s = str(node)
        n = len(s)
        if isinstance(node, (Text, HTMLEntity)):
            spans.append((pos, pos + n))
        elif isinstance(node, Wikilink):
            title = str(node.title)
            ns = title.strip().split(":", 1)[0].strip().lower() if ":" in title else ""
            if not title.strip().startswith(":") and ns in HIDDEN_LINK_NS:
                pass
            elif s.startswith("[[" + title):
                if node.text is not None:
                    off = 2 + len(title) + 1
                    if s[off:off + len(str(node.text))] == str(node.text):
                        _walk(node.text, pos + off, spans)
                else:
                    spans.append((pos + 2, pos + 2 + len(title)))
        elif isinstance(node, ExternalLink):
            if node.brackets and node.title is not None:
                t = str(node.title)
                i = s.rfind(t)
                if t and i > 0:
                    _walk(node.title, pos + i, spans)
        elif isinstance(node, Tag):
            name = str(node.tag).strip().lower()
            if name in PROSE_TAGS or node.wiki_markup in ("''", "'''"):
                off = _tag_contents_offset(s, node)
                if off is not None:
                    _walk(node.contents, pos + off, spans)
        elif isinstance(node, Template):
            name = str(node.name).strip().lower().replace("_", " ")
            wanted = TEXT_TEMPLATES.get(name)
            if wanted:
                cur = 2 + len(str(node.name))
                for param in node.params:
                    ps = str(param)
                    i = s.find("|" + ps, cur)
                    if i < 0:
                        break
                    start = i + 1
                    if str(param.name).strip() in wanted:
                        voff = start + len(ps) - len(str(param.value))
                        _walk(param.value, pos + voff, spans)
                    cur = start + len(ps)
        # Heading, Comment, Argument and anything else: not prose
        pos += n


def layout(text: str) -> Layout:
    code = mwp.parse(text, skip_style_tags=False)
    spans: list = []
    headings = []  # (start, end, level, title)
    pos = 0
    for node in code.nodes:
        s = str(node)
        if isinstance(node, Heading):
            headings.append((pos, pos + len(s), node.level, node.title.strip_code().strip()))
        else:
            _walk(mwp.wikicode.Wikicode([node]), pos, spans)
        pos += len(s)
    assert pos == len(text), "parser did not round-trip the wikitext"

    prose = bytearray(len(text))
    for a, b in spans:
        prose[a:b] = b"\x01" * (b - a)

    sections = [Section(0, "(lead)", 1, 0, False)]
    section_of = [0] * len(text)
    appendix_level = None
    for k, (a, b, level, title) in enumerate(headings, start=1):
        if appendix_level is not None and level <= appendix_level:
            appendix_level = None
        is_appendix = appendix_level is not None or title.lower() in APPENDIX_SECTIONS
        if is_appendix and appendix_level is None:
            appendix_level = level
        sections.append(Section(k, title, level, a, is_appendix))
    bounds = [s.start for s in sections] + [len(text)]
    for sec in sections:
        lo, hi = bounds[sec.index], bounds[sec.index + 1]
        if sec.index:
            section_of[lo:hi] = [sec.index] * (hi - lo)
        if sec.appendix:
            prose[lo:hi] = bytes(hi - lo)
    for a, b, _, _ in headings:
        prose[a:b] = bytes(b - a)
    return Layout(prose, section_of, sections)
