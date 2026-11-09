"""Wikipedia's own standards, quoted: the policy and guideline sentences each section of an article
page is measured against.

Each quote is checked to appear word for word in the plain text of the named Wikipedia page at
the version read (formatting removed), and stored with that version's ID, so the site links to
exactly the text it quotes. A quote not found is left out and reported, never paraphrased.
`wtl policies` writes data/policies.json.
"""

import datetime as dt
import json
import re

from .config import ROOT

POLICIES_JSON = ROOT / "data" / "policies.json"

# section of the article page -> [(page, anchor, quote)]
WANTED = {
    "opening": [
        ("Wikipedia:Neutral point of view", "Explanation",
         "Avoid stating seriously contested assertions as facts. If different reliable sources make conflicting "
         "assertions about a matter, treat these assertions as opinions rather than facts, and do not present them "
         "as direct statements in wikivoice."),
        ("Wikipedia:Neutral point of view", "Explanation",
         "Avoid stating facts as opinions. Uncontested and uncontroversial factual assertions made by reliable "
         "sources should normally be directly stated in Wikipedia's voice"),
        ("Wikipedia:Manual of Style/Lead section", None,
         "The lead section should briefly summarize the most important points covered in an article"),
    ],
    "writers": [
        ("Wikipedia:Ownership of content", None, "No one, no matter what, has the right to act as if they are the owner of a particular article (or any part of it)."),
        ("Wikipedia:Contentious topics", None, "These are specially designated topics that have attracted more persistent disruptive editing than the rest of the project and have been designated as contentious topics by the Arbitration Committee."),
    ],
    "sources": [
        ("Wikipedia:Verifiability", None, "verifiability means that people can check that facts or claims correspond to reliable sources."),
        ("Wikipedia:Neutral point of view", "Due_and_undue_weight",
         "Neutrality requires that mainspace articles and pages fairly represent all significant viewpoints that have "
         "been published by reliable sources, in proportion to the prominence of each viewpoint in those sources."),
        ("Wikipedia:Reliable sources", "Age_matters", "Be sure to check that older sources have not been superseded"),
    ],
    "held": [
        ("Wikipedia:Consensus", None, "Consensus is Wikipedia's fundamental method of decision-making."),
        ("Wikipedia:Edit warring", None, "An edit war occurs when editors who disagree about the content of a page repeatedly override each other's contributions."),
    ],
    "changes": [
        ("Wikipedia:Manual of Style/Words to watch", None,
         "There are no forbidden words or expressions on Wikipedia, but certain expressions should be used with "
         "caution because they may introduce bias or imprecise meaning."),
    ],
}


def _plain(wikitext: str) -> str:
    t = re.sub(r"\{\{(?:xt|!xt|tq|em|strong|var)\|([^{}]*?)\}\}", r"\1", wikitext)
    t = re.sub(r"<ref[^>]*?/>|<ref[^>]*>.*?</ref>", "", t, flags=re.S)
    t = re.sub(r"\{\{[^{}]*\}\}", "", t)
    t = re.sub(r"\{\{[^{}]*\}\}", "", t)
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", t)
    t = re.sub(r"\[https?://\S+\s([^\]]+)\]", r"\1", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = t.replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", t)


def build(log=print) -> dict:
    from .fetch.mediawiki import api
    pages, out, missing = {}, {}, []
    for section, items in WANTED.items():
        for page, anchor, quote in items:
            if page not in pages:
                d = api({"action": "query", "titles": page, "prop": "revisions", "rvprop": "ids|content",
                         "rvslots": "main", "redirects": "1"})
                r = d["query"]["pages"][0]["revisions"][0]
                pages[page] = (r["revid"], _plain(r["slots"]["main"]["content"]))
            rev, text = pages[page]
            if quote not in text:
                missing.append(f"{page}: {quote[:60]}")
                continue
            short = page.split(":", 1)[1].split("/")[-1]
            out.setdefault(section, []).append({
                "page": page, "name": short, "revision": rev, "quote": quote,
                "url": f"https://en.wikipedia.org/w/index.php?oldid={rev}" + (f"#{anchor}" if anchor else "")})
    d = {"built": dt.date.today().isoformat(), "rule": __doc__.strip(), "sections": out, "not_found": missing}
    POLICIES_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    log(f"wrote {POLICIES_JSON}: {sum(len(v) for v in out.values())} quotes; {len(missing)} not found" +
        ("".join(f"\n  not found: {m}" for m in missing)))
    return d
