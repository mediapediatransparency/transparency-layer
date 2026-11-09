"""Two template versions of today's first paragraph, shown beside the dated versions
(site.then_now_top, columns 5 and 6). Fixed rules applied to data already computed; nothing here
is written by this project, and neither is a proposed edit to Wikipedia.

5. Sources named: each sentence the voice check marks (wtl/voice.py: evidence it is contested,
   stated in Wikipedia's voice) gets its cited authors named in front by the fixed template
   "According to A, B and C, ...". When its footnotes name no author, the sources' names are used
   instead; when no footnote follows it, "According to an unspecified source, ...". Other sentences
   are unchanged.
6. Removed sources kept: as 5, plus every work cited in the opening on an earlier date checked and
   not cited there now (narrative.removed_from_opening). The sentence it backed then goes back in,
   after today's most similar sentence (content-word similarity at least 0.3, as in
   voicepage.page), or at the end of the paragraph when nothing today is similar and the sentence
   was in that date's first paragraph. It is framed "According to <its authors>," (or its sources'
   names, or "an unspecified source", as in column 5) unless it already
   names one of them or has a phrase of attribution. A sentence that still reads nearly the same
   (similarity at least 0.85) is not repeated; its removed authors join the names in front of it,
   when it has names in front. Earlier sentences nearly the same as each other are shown once, with
   all their works; scraps of infobox or markup are left out.
"""

import re

from .then_now import similarity
from .voice import ATTRIB, PRONOUN_ATTRIB, _join, _surname, with_prefix

UNSPECIFIED = "an unspecified source"
SAME = 0.85      # an earlier sentence this similar to today's is the same sentence
NEAR = 0.3       # voicepage.page's threshold for "the same sentence, reworded"


def _who(authors: list[str]) -> list[str]:
    names = list(dict.fromkeys(_surname(a) for a in authors))
    return names[:3] + ([f"{len(names) - 3} others"] if len(names) > 3 else [])


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _attributed(sent: str, authors: list[str]) -> bool:
    return bool(any(re.search(r"\b" + re.escape(_surname(a)) + r"\b", sent) for a in authors)
                or ATTRIB.search(sent) or PRONOUN_ATTRIB.search(sent))


def _sentence(s: str) -> bool:
    """A whole sentence of prose: not an infobox scrap ("| pop2 = ...") or a fragment left where
    markup was taken out (") is a ...")."""
    return (len(s.split()) >= 4 and re.match(r"[A-Z0-9“\"'‘]", s) is not None
            and not re.search(r"(?:^|\s)\|\s*\w+\s*=", s))


def _frame(sent: str, names: list[str]) -> dict:
    if not names:
        return {"lead": "", "prefix": "", "rest": sent}
    lead, prefix, rest = with_prefix(f"According to {_join(names)},", sent)
    return {"lead": lead, "prefix": prefix, "rest": rest}


def columns(par: str, voice: dict, old_pars: list[str], name_of) -> tuple[list[dict], list[dict]] | None:
    """(column 5, column 6) as lists of segments {kind, lead, prefix, rest, note}. kind: "plain"
    (text between matched sentences), "today", "back" (an earlier sentence put back). name_of(key)
    names a source that has no author. None when no sentence of the paragraph is matched."""
    rows = voice.get("sentences") or []
    # today's first-paragraph sentences, in order, with any text between them kept as it is
    hits, pos = [], 0
    for r in rows:
        i = par.find(r["text"], pos)
        if i >= 0:
            hits.append((i, r))
            pos = i + len(r["text"])
    if not hits:
        return None
    in_par = {r["id"] for _, r in hits}

    # removed works, one group per earlier sentence, placed as voicepage.page places them
    groups: dict[str, list[dict]] = {}
    for w in voice.get("removed") or []:
        sent = (w.get("sentence_then") or "").strip()
        if not _sentence(sent):
            continue
        same = next((g for g in groups if similarity(g, sent) >= SAME), None)
        groups.setdefault(same or sent, []).append(w)
    after: dict[str, list] = {}       # today's sentence id -> [(earlier sentence, works)]
    merged: dict[str, list] = {}      # today's sentence id -> removed authors of the same sentence
    tail = []
    old_norm = [_norm(p) for p in old_pars]
    for sent, ws in groups.items():
        best = max(((similarity(sent, r["text"]), r["id"]) for r in rows), default=(0, None))
        if best[0] >= SAME and best[1] in in_par:
            merged.setdefault(best[1], []).extend(a for w in ws for a in w["authors"])
        elif best[0] >= NEAR:
            if best[1] in in_par:
                after.setdefault(best[1], []).append((sent, ws))
        elif any(_norm(sent)[:80] in p for p in old_norm):
            tail.append((sent, ws))

    works = voice.get("works") or {}

    def sources_of(ws):
        return list(dict.fromkeys(n for w in ws if (n := name_of(w.get("source")))))[:3]

    def today(r, extra=()):
        names, note = [], None
        if r["possible_case"]:
            names = _who(list(r["cited_authors"]) + [a for a in extra if a not in r["cited_authors"]])
            if not names:
                names = sources_of(works.get(r["id"], []))
                note = "Its footnotes name no author, so the source is named."
            if not names:
                names = [UNSPECIFIED]
                note = "No footnote after this sentence names an author or a source."
        seg = {"kind": "today", **_frame(r["text"], names)}
        if note:
            seg["note"] = note
        return seg

    def back(sent, ws):
        authors = list(dict.fromkeys(a for w in ws for a in w["authors"]))
        if _attributed(sent, authors):
            names = []
        else:
            names = _who(authors) or sources_of(ws) or [UNSPECIFIED]
        titles = "; ".join(dict.fromkeys(w.get("title") or "" for w in ws if w.get("title")))
        return {"kind": "back", **_frame(sent, names), "works": ws,
                "note": "Put back: cited in the opening earlier, not now" + (f" ({titles[:200]})" if titles else "")}

    c5, c6, pos = [], [], 0
    for i, r in hits:
        if i > pos:
            c5.append({"kind": "plain", "lead": "", "prefix": "", "rest": par[pos:i]})
            c6.append(c5[-1])
        c5.append(today(r))
        c6.append(today(r, merged.get(r["id"], ())))
        for sent, ws in after.get(r["id"], []):
            c6.append(back(sent, ws))
        pos = i + len(r["text"])
    if pos < len(par):
        c5.append({"kind": "plain", "lead": "", "prefix": "", "rest": par[pos:]})
        c6.append(c5[-1])
    c6.extend(back(sent, ws) for sent, ws in tail)
    return c5, c6
