"""What Wikidata records about the authors that analysed articles cite.

Only authors that a citation itself links to a Wikipedia article (author-link=, or the name
written as a link) are looked up, so no name is matched to a person by guesswork. For each,
from the Wikidata item of that Wikipedia article, the current statements (deprecated ones
left out):
- occupation (P106), field of work (P101);
- employer (P108), affiliation (P1416), member of political party (P102), position held (P39),
  member of (P463): those with an end date recorded are kept apart as "former"; those without
  one may still be past (Wikidata often leaves the end date out);
- political ideology (P1142).
Each value says whether its Wikidata statement cites a reference (beyond "imported from
Wikipedia"). Wikipedia categories are not used: they are labels added by Wikipedia editors.
No score or side is given to any person.

Nothing else is gathered about cited authors, and nothing at all about Wikipedia editors.
`wtl authors` writes data/authors.json.
"""

import datetime as dt
import json

from .config import ROOT
from .fetch.http import get_json
from .outlets import WD_API, _sourced, qids_for_titles

AUTHORS_JSON = ROOT / "data" / "authors.json"
PROPS = {"P106": "occupation", "P101": "field_of_work", "P108": "employer", "P1416": "affiliation",
         "P102": "political_party", "P39": "position_held", "P463": "member_of",
         "P1142": "political_ideology"}
DATED = {"employer", "affiliation", "political_party", "position_held", "member_of"}


def _entities(ids, props):
    out = {}
    for i in range(0, len(ids), 50):
        d = get_json(WD_API, {"action": "wbgetentities", "ids": "|".join(ids[i:i + 50]),
                              "props": props, "languages": "en", "format": "json"})
        out.update(d.get("entities", {}))
    return out


def facts(qids: list[str]) -> dict:
    ents = _entities(qids, "labels|claims")
    raw, vids = {}, set()
    for q in qids:
        c = ents.get(q, {}).get("claims", {})
        human = any((st.get("mainsnak", {}).get("datavalue", {}).get("value") or {}).get("id") == "Q5"
                    for st in c.get("P31", []))
        f = {"human": human}
        for pid, key in PROPS.items():
            for st in c.get(pid, []):
                if st.get("rank") == "deprecated":
                    continue
                v = (st.get("mainsnak", {}).get("datavalue", {}).get("value") or {})
                if not isinstance(v, dict) or "id" not in v:
                    continue
                vids.add(v["id"])
                slot = ("former_" + key) if key in DATED and "P582" in st.get("qualifiers", {}) else key
                f.setdefault(slot, {})
                f[slot][v["id"]] = f[slot].get(v["id"], False) or _sourced(st)
        raw[q] = f
    labels = {k: v.get("labels", {}).get("en", {}).get("value", k)
              for k, v in _entities(sorted(vids), "labels").items()}
    return {q: {k: (sorted(({"label": labels.get(x, x), "sourced": src} for x, src in v.items()),
                           key=lambda d: d["label"]) if isinstance(v, dict) else v)
                for k, v in f.items()} for q, f in raw.items()}


def build(records: list[dict], log=print) -> dict:
    titles = sorted({a["wikipedia"] for r in records for a in (r.get("sources") or {}).get("authors", [])
                     if a.get("wikipedia")})
    log(f"  authors: {len(titles):,} linked to Wikipedia articles")
    qids = qids_for_titles(titles)
    f = facts(sorted(set(qids.values())))
    out = {}
    for t in titles:
        q = qids.get(t)
        if not q:
            out[t] = {"wikidata": None}
            continue
        out[t] = {"wikidata": q, **f.get(q, {})}
    d = {"built": dt.date.today().isoformat(), "rule": __doc__.strip(), "authors": out}
    AUTHORS_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    log(f"wrote {AUTHORS_JSON}: {sum(1 for v in out.values() if v.get('wikidata')):,} with a Wikidata item")
    return d
