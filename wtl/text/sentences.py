"""Split the visible prose into sentences, keeping each character's offset in the wikitext.

Rule-based (no models): a sentence ends at . ! or ? (plus closing quotes or brackets) followed by
whitespace and a character that is not a lower-case letter, unless the word before the full stop
is a known abbreviation or a single letter (an initial). Line breaks and section changes always
end a sentence.
"""

import re
from dataclasses import dataclass

from .wikitext import Layout

ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "st", "jr", "sr", "gen", "lt", "col", "capt", "sgt", "maj",
    "adm", "gov", "sen", "rep", "rev", "hon", "pres", "no", "nos", "vol", "vols", "pp", "p", "ed",
    "eds", "inc", "ltd", "co", "corp", "vs", "etc", "al", "ca", "approx", "fig", "jan", "feb",
    "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "e.g", "i.e", "u.s",
    "u.k", "u.n", "a.d", "b.c", "b.c.e", "c.e", "op", "cf", "mt", "ft", "est",
}
END = re.compile(r"[.!?]+[\"'”’»)\]]*(?=\s+\S)")


@dataclass
class Sentence:
    id: str
    section: int
    section_title: str
    text: str
    offsets: list   # wikitext character offsets of the sentence's visible characters


def _is_abbrev(par: str, dot: int) -> bool:
    if par[dot] != ".":
        return False
    m = re.search(r"([\w.]+)$", par[:dot])
    if not m:
        return False
    word = m.group(1).lower().strip(".")
    return len(word) == 1 or word in ABBREVIATIONS


def split(text: str, lay: Layout) -> list[Sentence]:
    # Visible stream, broken into paragraphs at newlines and section changes.
    paragraphs = []  # (section, chars, offsets)
    chars, offs, cur_sec = [], [], None
    for i, ch in enumerate(text):
        if not lay.prose[i]:
            continue
        sec = lay.section_of[i]
        if ch == "\n" or (cur_sec is not None and sec != cur_sec):
            if chars:
                paragraphs.append((cur_sec, chars, offs))
            chars, offs = [], []
            if ch == "\n":
                cur_sec = sec
                continue
        cur_sec = sec
        chars.append(ch)
        offs.append(i)
    if chars:
        paragraphs.append((cur_sec, chars, offs))

    out, counters = [], {}
    titles = {s.index: s.title for s in lay.sections}
    for sec, chars, offs in paragraphs:
        par = "".join(chars)
        cuts, start = [], 0
        for m in END.finditer(par):
            nxt = par[m.end():].lstrip()[:1]
            if nxt.islower() or _is_abbrev(par, m.start()):
                continue
            cuts.append((start, m.end()))
            start = m.end()
        cuts.append((start, len(par)))
        for a, b in cuts:
            seg = par[a:b]
            if not re.search(r"\w", seg):
                continue
            lead = len(seg) - len(seg.lstrip())
            trail = len(seg.rstrip())
            seg_offs = offs[a + lead:a + trail]
            counters[sec] = counters.get(sec, 0) + 1
            sid = f"lead-{counters[sec]}" if sec == 0 else f"sec{sec}-{counters[sec]}"
            out.append(Sentence(sid, sec, titles.get(sec, ""), " ".join(seg.split()), seg_offs))
    return out
