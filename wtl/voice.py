"""Wikipedia's voice check: sentences of the opening section that may state contested assertions
or opinions as facts, measured against Wikipedia's own neutrality policy (pilot; not on the site).

The policy (Wikipedia:Neutral point of view, version NPOV_REV):
- "Avoid stating opinions as facts ... these opinions should not be stated in Wikipedia's voice.
  Rather, they should be attributed in the text to particular sources".
- "Avoid stating seriously contested assertions as facts. If different reliable sources make
  conflicting assertions about a matter, treat these assertions as opinions rather than facts,
  and do not present them as direct statements in wikivoice."
- "Avoid stating facts as opinions": uncontested facts belong in Wikipedia's voice.

A sentence is listed as a possible case when both hold:
1. Evidence that it is contested or evaluative, each kind shown on its own:
   - editors disputed it: taken out for a day or more at least twice (removals undone within a day
     are mostly vandalism and are not counted) by at least two accounts,
     tagged as disputed, or quoted in at least three talk-page discussions or in a request for
     comment (wtl/talk.py);
   - it uses a word from Wikipedia's own "Words to watch" guideline in the groups on labels,
     editorializing, unsupported attributions and expressions of doubt.
   (Words from this project's own lists of alternative terms are shown too, but do not count.)
2. It is stated in Wikipedia's voice: it names no author it cites and has no phrase of attribution
   ("according to", "historians argue", "opponents characterize", "described as ... by", "in the view
   of", or "widely seen as", which the policy allows for widespread views), or a pronoun followed by a
   reporting verb ("he argued", "she said", "they consider"), which in an opening section refers to a
   named person or group. Such a pronoun phrase covers only the words after it: in "He notably
   claimed ...", "notably" is still Wikipedia's own word.
This finds sentences to check against the rule. It does not decide that a sentence breaks the
rule: whether reliable sources really conflict is for readers and editors to judge.

"With attribution" shows the same sentence with the cited authors named in front ("According to
A, B and C, ..."). It is a fixed template, not a proposed edit: it shows what naming the sources
would look like, nothing more. This project never edits Wikipedia.
"""

import json
import re

from .config import ROOT

NPOV_REV = 1384386153
NPOV_URL = f"https://en.wikipedia.org/w/index.php?oldid={NPOV_REV}#Explanation"
VERB = (r"(?:argue|write|wrote|say|said|contend|maintain|claim|assert|believe|consider|regard|view|"
        r"describe|characteri[sz]e|call|suggest|conclude|hold|held|note|reject|dispute|declare|"
        r"see|saw|seen|regard|deem|label|accuse|praise|condemn|criticize|criticise)(?:s|d|ed)?")
WHO = (r"(?:historians|scholars|critics|supporters|commentators|observers|researchers|analysts|advocates|"
       r"opponents|proponents|detractors|defenders|some|many|others|[A-Z][a-z]+ (?:government|officials|leaders)|"
       r"Britain|Israel|the United Nations|the UN)")
ATTRIB = re.compile(r"(?i)\b(?:according to|in the (?:view|words|opinion) of|widely (?:seen|regarded|considered|viewed|described)|as (?:argued|described|noted|put) by|"
                    r"(?:has|have|is|are|was|were) (?:been )?(?:described|characteri[sz]ed|called|viewed|seen|regarded) as\b.{0,80}?\bby|"
                    + WHO + r"(?:\s+\w+){0,3}?\s+" + VERB + r")\b")
LOWER_OK = {"the", "a", "an", "in", "during", "after", "before", "by", "since", "from", "its", "this", "these",
            "it", "they", "many", "some", "most", "both", "when", "while", "although", "following"}
PRONOUN_ATTRIB = re.compile(
    r"\b(?:[Hh]e|[Ss]he|[Tt]hey)\s+(?:\w+ly\s+)?(?:argue|contend|maintain|claim|assert|believe|consider|"
    r"say|said|state|suggest|conclude|insist|denie|deny|reject|dispute|accuse|describe|characteri[sz]e|"
    r"view|regard|warn|predict|propose|advocate|hold|held|wrote|write)(?:s|d|ed)?\b")
CONNECTIVES = {"however", "nevertheless", "nonetheless", "moreover", "furthermore", "additionally",
               "instead", "meanwhile", "conversely", "consequently", "thus", "therefore", "still", "yet",
               "later", "subsequently", "similarly", "likewise", "also", "in addition", "in contrast",
               "by contrast", "on the other hand", "for instance", "for example", "as a result", "as such",
               "in fact", "in particular", "in turn", "rather", "today", "instead"}


def with_prefix(prefix: str, sent: str) -> tuple[str, str]:
    """(text before the prefix, text after it): a leading connective ("However,") stays in front,
    and the first word after the prefix is lower-cased unless it may be a name."""
    lead = ""
    m = re.match(r"([A-Z][\w ]{1,20}?),\s+", sent)
    if m and (m.group(1).lower() in CONNECTIVES or re.fullmatch(r"[a-z]{3,}(?:ally|ately|ently|antly|ously|ively|arly|ually|ably|ibly|ectly|ainly|edly)", m.group(1).lower())):
        lead, sent = m.group(0), sent[m.end():]
        prefix = prefix[0].lower() + prefix[1:]
    first, rest = (sent.split(" ", 1) + [""])[:2]
    low = first.lower() if first.lower() in LOWER_OK | CONNECTIVES else first   # keep names capitalised
    return lead, prefix, f"{low} {rest}".strip()
WTW_GROUPS = ("contentious labels", "unsupported attributions", "expressions of doubt", "editorializing",
              "said, stated, claimed")


def _words():
    w = json.loads((ROOT / "data" / "words_to_watch.json").read_text(encoding="utf-8"))
    c = json.loads((ROOT / "data" / "contested_terms.json").read_text(encoding="utf-8"))
    wtw = {g: ts for g, ts in w["categories"].items() if any(k in g.lower() for k in WTW_GROUPS)}
    return wtw, w, c["groups"]


def _find(terms, text):
    return sorted({t for t in terms if re.search(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", text, re.I)})


def _surname(n: str) -> str:
    p = re.sub(r"\(.*?\)", "", n).replace(",", " ").split()
    return p[-1] if p else n


def _join(xs):
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def check(rec: dict, sents, works: dict, talk: dict | None) -> dict:
    wtw, wsrc, groups = _words()
    quoted = {}
    for d in (talk or {}).get("discussions", []):
        for sid in d.get("quotes_sentences", []):
            quoted.setdefault(sid, []).append({"heading": d["heading"], "url": d["url"], "rfc": d.get("rfc")})
    info = {s["id"]: s for s in rec["sentences"]}
    rows = []
    for s in sents:
        if not s.id.startswith("lead"):
            continue
        r = info.get(s.id) or {}
        h = r.get("history") or {}
        tags = [t.get("template") for t in r.get("tags") or []]
        q = quoted.get(s.id, [])
        disputed = []
        if (h.get("out_24h_or_more") or 0) >= 2 and (h.get("removing_accounts") or 0) >= 2:
            disputed.append(f"taken out for a day or more {h['out_24h_or_more']} times and put back "
                            f"(taken out {h['removed']} times in all, by {h.get('removing_accounts', '?')} accounts)")
        if tags:
            disputed.append("tagged: " + ", ".join(tags))
        if len(q) >= 3 or any(x["rfc"] for x in q):
            disputed.append(f"quoted in {len(q)} talk-page discussions" +
                            (f" ({sum(1 for x in q if x['rfc'])} requests for comment)" if any(x["rfc"] for x in q) else ""))
        words = {g: f for g, ts in wtw.items() if (f := _find(ts, s.text))}
        project = {g["name"]: f for g in groups if (f := _find(g["terms"], s.text))}
        authors = list(dict.fromkeys(a for w in works.get(s.id, []) for a in w["authors"]))
        named = [a for a in authors if re.search(r"\b" + re.escape(_surname(a)) + r"\b", s.text)]
        phrase = ATTRIB.search(s.text)
        pron = None if named or phrase else PRONOUN_ATTRIB.search(s.text)
        attributed = bool(named or phrase or pron)
        # "he argued ..." covers only what follows it: words to watch before it are Wikipedia's own
        voiced = {} if named or phrase else words if not pron else {
            g: f for g, ts in words.items() if (f := _find(ts, s.text[:pron.end()]))}
        phrase = phrase or pron
        possible = bool((disputed and not attributed) or voiced)
        who = [_surname(a) for a in authors][:3]
        if len(authors) > 3:
            who.append(f"{len(authors) - 3} others")
        template = prefix = None
        lead = ""
        if possible and who:
            lead, prefix, rest = with_prefix(f"According to {_join(who)},", s.text)
            template = f"{lead}{prefix} {rest}"
        rows.append({"id": s.id, "text": s.text, "disputed_by_editors": disputed, "talk": q[:5],
                     "words_to_watch": words, "project_terms": project, "named_authors": named,
                     "attribution_phrase": phrase.group(0) if phrase else None, "cited_authors": authors,
                     "possible_case": possible, "with_attribution": template, "attribution_prefix": prefix,
                     "attribution_lead": lead if template else ""})
    return {"policy": NPOV_URL, "words_to_watch_source": wsrc["url"],
            "sentences": rows, "possible_cases": sum(r["possible_case"] for r in rows),
            "sentences_checked": len(rows)}


VOICE_JSON = ROOT / "data" / "voice.json"


def for_record(rec: dict, talk: dict | None) -> dict:
    from . import narrative
    from . import then_now as tn
    sents, works = narrative.sentence_works(rec)
    chk = check(rec, sents, works, talk)
    removed = narrative.removed_from_opening(rec, works, dates=tn.DATES)
    lead_works = {sid: ws for sid, ws in works.items() if sid.startswith("lead")}
    return {"revision": rec["revision"], **chk, "works": lead_works, "removed": removed,
            "removed_dates": tn.DATES}


def build(records: list[dict], log=print) -> dict:
    """data/voice.json: the check for every analysed article, redone only when the analysed
    revision changes. Earlier openings: the then-and-now dates (wtl/then_now.py)."""
    import datetime as dt
    talk = json.loads((ROOT / "data" / "talk.json").read_text(encoding="utf-8")).get("articles", {})
    old = json.loads(VOICE_JSON.read_text(encoding="utf-8")) if VOICE_JSON.exists() else {}
    arts = old.get("articles", {})
    for i, r in enumerate(records):
        if (arts.get(r["article"]) or {}).get("revision") == r["revision"]:
            continue
        t = talk.get(r["article"])
        try:
            arts[r["article"]] = for_record(r, t if (t or {}).get("revision") == r["revision"] else None)
        except Exception as ex:   # noqa: BLE001 - one article's failure is reported, not fatal
            log(f"  voice: {r['article']}: {str(ex)[:100]}")
        if i % 100 == 0:
            log(f"  voice: {i + 1:,} of {len(records):,}")
            _write(arts)
    return _write(arts)


def _write(arts):
    import datetime as dt
    d = {"built": dt.date.today().isoformat(), "policy": NPOV_URL, "rule": __doc__.strip(),
         "articles": dict(sorted(arts.items()))}
    VOICE_JSON.write_text(json.dumps(d, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return d
