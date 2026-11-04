"""Declared conflicts of interest, as Wikipedia records them publicly.

Two places, both read as they stood when the analysed revision was saved:
- the article's talk page: "Connected contributor" notices (and the paid version), which name
  accounts with a declared or noted connection to the subject;
- the article itself: maintenance tags for a conflict of interest, autobiography, paid
  contributions or undisclosed paid editing.

Accounts named in a notice are matched to the article's editor labels by user ID. Usernames stay
internal, as everywhere in the record; the notice is linked as evidence.
"""

import re

from .fetch import cache
from .fetch.mediawiki import api, resolve_users

# Template names and their redirects (checked on Wikipedia, November 2026).
CONNECTED = ["connected contributor", "connected contributor multi", "connected contributors",
             "connected editor", "connected", "wikipedianarticle", "wikipedian-bio",
             "notablewikipedian", "notable wikipedian", "nwp", "coi2"]
CONNECTED_PAID = ["connected contributor (paid)", "paid article", "paid-talk", "paid contributor",
                  "connpaid", "ccp", "coi (paid)"]
ARTICLE_TAGS = {
    "conflict of interest": ["coi", "selfpromotion", "coi-section", "coi-check", "coi-issues",
                             "coi section", "potential vanity", "close connection",
                             "close connexion", "conflicts of interest", "conflict of interest"],
    "autobiography": ["autobiography", "auto", "autobio"],
    "paid contributions": ["paid contributions", "paid content"],
    "undisclosed paid editing": ["undisclosed paid", "udp", "upe", "paid piece", "paid push",
                                 "push piece", "paid edit", "paidedit", "paid writeup", "undisclosed"],
}


def _tpl_re(names):
    alt = "|".join(re.escape(n).replace(r"\ ", r"[ _]") for n in sorted(names, key=len, reverse=True))
    return re.compile(r"\{\{\s*(?:template:)?(" + alt + r")\s*(\|[^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*)?\}\}",
                      re.I)


CONNECTED_RE, PAID_RE = _tpl_re(CONNECTED), _tpl_re(CONNECTED_PAID)
TAG_RES = {k: _tpl_re(v) for k, v in ARTICLE_TAGS.items()}
USER_PARAM = re.compile(r"\|\s*(?:user|u)(\d*)\s*=\s*([^|}\n]+)", re.I)


def talk_at(title: str, timestamp: str) -> dict | None:
    """The talk page's text as of the given time: {revid, content} or None."""
    p = cache.path("coi", "talk", re.sub(r"\W+", "_", title)[:80] + "_" + timestamp.replace(":", ""))
    hit = cache.load(p)
    if hit is not None:
        return hit or None
    d = api({"action": "query", "prop": "revisions", "titles": f"Talk:{title}", "rvlimit": "1",
             "rvstart": timestamp, "rvdir": "older", "rvprop": "ids|content", "rvslots": "main"})
    pg = d["query"]["pages"][0]
    revs = pg.get("revisions")
    out = ({"revid": revs[0]["revid"], "content": revs[0]["slots"]["main"].get("content", "")}
           if revs else {})
    cache.save(p, out)
    return out or None


def compute(title: str, timestamp: str, article_text: str, label_of_key) -> dict:
    """The record's "declared_interests" block. label_of_key maps an editor key (u<userid>) to its
    label in this record, or None if the account is not among the listed editors."""
    tags = sorted(k for k, rx in TAG_RES.items() if rx.search(article_text))
    talk = talk_at(title, timestamp)
    notices = []
    if talk:
        for kind, rx in (("connected contributor", CONNECTED_RE), ("connected contributor (paid)", PAID_RE)):
            for m in rx.finditer(talk["content"]):
                users = [u.strip() for _, u in USER_PARAM.findall(m.group(2) or "") if u.strip()]
                ids = resolve_users(users) if users else {}
                labels, other = [], 0
                for u in users:
                    uid = (ids.get(u) or {}).get("userid")
                    lab = label_of_key(f"u{uid}") if uid else None
                    if lab:
                        labels.append(lab)
                    else:
                        other += 1
                notices.append({"notice": kind, "editors": sorted(set(labels), key=lambda l: int(l.split()[1])),
                                "accounts_not_among_listed_editors": other})
    return {
        "article_tags": tags,
        "talk_page_revision": talk["revid"] if talk else None,
        "evidence": (f"https://en.wikipedia.org/w/index.php?oldid={talk['revid']}" if talk else None),
        "notices": notices,
    }
