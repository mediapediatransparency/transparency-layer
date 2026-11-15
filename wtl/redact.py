"""Redaction of quoted Wikipedia text that would disclose people: editors' identities, or personal
details of private people that vandals wrote into an article.

Wikipedia's own history keeps such text; this site does not repeat it. The words are replaced by a
tag, [redacted:<reason>], which the site shows as a marked "redacted" chip with the reason. Only the
disclosing words are replaced; the rest of the quoted text stays as it was.

Two kinds of rule:
- automatic: links to an editor's page ([[User:…]], [[User talk:…]], [[Special:Contributions/…]])
  and IP addresses;
- by hand: passages listed in data/redactions.json per article, each with its reason, kept there
  only as a SHA-256 hash and length so that file does not repeat them.
"""
from __future__ import annotations

import hashlib
import json
import re
from html import escape

from .config import ROOT

REDACTIONS_JSON = ROOT / "data" / "redactions.json"

REASONS = {
    "editor-link": "a link to a Wikipedia editor's page",
    "ip-address": "an IP address (it can identify an editor)",
    "personal-details": "personal details of a private person",
}

TAG = re.compile(r"\[redacted:([a-z-]+)\]")

_EDITOR_LINK = re.compile(
    r"\[\[\s*(?:Special:Contributions/|User(?:[ _]talk)?:)[^\]\|\n]*(?:\|[^\]\n]*)?(?:\]\])?", re.I)
_IPV4 = re.compile(r"(?<![\w.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\w.])")
_IPV6 = re.compile(r"(?<![\w:])(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}(?![\w:])")

_BY_HAND: dict | None = None


def _by_hand() -> dict:
    global _BY_HAND
    if _BY_HAND is None:
        _BY_HAND = (json.loads(REDACTIONS_JSON.read_text(encoding="utf-8")).get("articles", {})
                    if REDACTIONS_JSON.exists() else {})
    return _BY_HAND


def _replace_hashed(s: str, digest: str, n: int, tag: str) -> str:
    """Every passage of s that is n characters long and has this SHA-256, replaced by tag."""
    out, i = [], 0
    while i + n <= len(s):
        if hashlib.sha256(s[i:i + n].encode("utf-8")).hexdigest() == digest:
            out.append(tag)
            i += n
        else:
            out.append(s[i])
            i += 1
    out.append(s[i:])
    return "".join(out)


def text(s: str | None, article: str | None = None) -> str | None:
    """s with every disclosing passage replaced by its tag."""
    if not s:
        return s
    for r in sorted(_by_hand().get(article or "", []), key=lambda r: -r["length"]):
        s = _replace_hashed(s, r["sha256"], r["length"], f"[redacted:{r['reason']}]")
    s = _EDITOR_LINK.sub("[redacted:editor-link]", s)
    s = _IPV4.sub("[redacted:ip-address]", s)
    return _IPV6.sub("[redacted:ip-address]", s)


def shortdesc_entry(e: dict, article: str) -> dict:
    """A data/shortdesc.json entry with its quoted descriptions redacted."""
    for c in e.get("changes") or []:
        for k in ("from", "to"):
            c[k] = text(c.get(k), article)
    return e


def then_now_entry(e: dict, article: str) -> dict:
    """A data/then_now.json entry with each dated version's short description redacted."""
    for v in e.get("versions") or []:
        if v.get("short_description"):
            v["short_description"] = text(v["short_description"], article)
    return e


CSS = (".redacted{display:inline-block;padding:0 6px;border-radius:4px;font-size:.85em;"
       "background:var(--fg,#222);color:var(--bg,#fff);letter-spacing:.02em;cursor:help}")


def chip(reason: str) -> str:
    why = REASONS.get(reason, reason.replace("-", " "))
    return (f"<span class='redacted' title='Redacted by this site: {escape(why)}. Wikipedia’s page "
            f"history still has the original.'>redacted · {escape(why.split(' (')[0])}</span>")


_SCRIPT = re.compile(r"(<script\b.*?</script>)", re.S | re.I)


def render(html: str) -> str:
    """Tags in page HTML (outside scripts) shown as chips; inside scripts they stay plain text."""
    parts = _SCRIPT.split(html)
    return "".join(p if i % 2 else TAG.sub(lambda m: chip(m.group(1)), p) for i, p in enumerate(parts))
