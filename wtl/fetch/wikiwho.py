"""WikiWho client (word-level authorship, GESIS / Wikimedia Cloud).

Docs: https://wikiwho-api.wmcloud.org/en/api/v1.0.0-beta/ (swagger) and https://api.wikiwho.net.
Tokens come back lower-cased and without whitespace; `wtl.text.align` maps them back onto the
revision's wikitext.
"""

import re

from ..config import WIKIWHO_URL
from . import cache
from .http import FetchError, get_json

ALNUM = re.compile(r"\w", re.UNICODE)


def rev_content(revid: int) -> dict:
    """Tokens of one revision with their origin revision and editor. Cached by revision ID.

    Returns {"revid", "tokens": [[str, o_rev_id, editor], ...]}.
    """
    p = cache.path("wikiwho", "rev_content", str(revid))
    hit = cache.load(p)
    if hit is not None:
        return hit
    url = f"{WIKIWHO_URL}/rev_content/rev_id/{revid}/"
    data = get_json(url, {"o_rev_id": "true", "editor": "true", "token_id": "false",
                          "out": "false", "in": "false"})
    if not data.get("success"):
        raise FetchError(f"WikiWho rev_content failed for {revid}: {data.get('message')}")
    revs = data["revisions"]
    body = revs[0][str(revid)] if isinstance(revs, list) else revs[str(revid)]
    out = {"revid": revid, "article_title": data.get("article_title"),
           "page_id": data.get("page_id"),
           "tokens": [[t["str"], t["o_rev_id"], t["editor"]] for t in body["tokens"]]}
    cache.save(p, out)
    return out


def all_content(pageid: int, needed_revid: int, latest_revid: int | None) -> dict:
    """Every token ever present in the article, in WikiWho's token order, with the revisions
    that removed (out) and re-inserted (in) it, and its text (lower-cased, as WikiWho gives it).
    Returns {"page_id", "covers_revid", "tokens": [[o_rev_id, in, out, str], ...]}. Used for
    survival (word tokens only, see word_view) and for removals and wording changes.

    The cached copy is reused for any analysed revision at or before the revision the article
    was at when it was fetched (`covers_revid`); events after the analysed revision are ignored
    downstream, so the result does not depend on when the data was fetched.
    """
    p = cache.path("wikiwho", "all_content_v2", str(pageid))
    hit = cache.load(p)
    if hit is not None and hit["covers_revid"] >= needed_revid:
        return hit
    if latest_revid is None or latest_revid < needed_revid:
        raise FetchError("all_content needs the page's latest revision id at fetch time")
    url = f"{WIKIWHO_URL}/all_content/page_id/{pageid}/"
    data = get_json(url, {"o_rev_id": "true", "editor": "false", "token_id": "true",
                          "out": "true", "in": "true"}, timeout=900)
    if not data.get("success"):
        raise FetchError(f"WikiWho all_content failed for page {pageid}: {data.get('message')}")
    toks = sorted(data["all_tokens"], key=lambda t: t["token_id"])
    out = {"page_id": pageid, "covers_revid": latest_revid,
           "tokens": [[t["o_rev_id"], t.get("in", []), t.get("out", []), t["str"]] for t in toks]}
    cache.save(p, out)
    return out


def word_view(allc: dict) -> list:
    """[o_rev_id, in, out] for word tokens only (what survival counts)."""
    # older caches (and test fixtures) hold word tokens only, without their text
    return [t[:3] for t in allc["tokens"] if len(t) < 4 or ALNUM.search(t[3])]
