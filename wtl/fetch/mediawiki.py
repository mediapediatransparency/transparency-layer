"""MediaWiki Action API client. Read-only; every call is a GET.

Caching rules:
- A revision (content + metadata) is cached under its revision ID and never refetched.
- Page history is cached per page and only extended with revisions newer than the cached ones.
- Block status is time-dependent, so it is snapshotted once per analysed revision and reused.
"""

import datetime as dt
import hashlib

from ..config import API_URL
from . import cache
from .http import FetchError, get_json


def api(params: dict) -> dict:
    p = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
    data = get_json(API_URL, p)
    if "error" in data:
        raise FetchError(f"API error {data['error'].get('code')}: {data['error'].get('info')}")
    return data


def resolve_title(title: str) -> dict:
    """Follow redirects and normalisation. Returns {title, pageid, lastrevid, redirected_from}."""
    data = api({"action": "query", "titles": title, "redirects": "1", "prop": "info"})
    q = data["query"]
    page = q["pages"][0]
    if page.get("missing") or page.get("invalid"):
        raise FetchError(f"no such article: {title!r}")
    redirected = [r["from"] for r in q.get("redirects", [])]
    return {"title": page["title"], "pageid": page["pageid"], "lastrevid": page["lastrevid"],
            "redirected_from": redirected}


def get_revision(revid: int) -> dict:
    """Wikitext and metadata of one revision. Cached forever by revision ID."""
    p = cache.path("mediawiki", "rev", str(revid))
    hit = cache.load(p)
    if hit is not None:
        return hit
    data = api({"action": "query", "prop": "revisions", "revids": str(revid),
                "rvprop": "ids|timestamp|user|userid|sha1|content", "rvslots": "main"})
    page = data["query"]["pages"][0]
    rev = page["revisions"][0]
    if rev.get("texthidden") or "content" not in rev["slots"]["main"]:
        raise FetchError(f"revision {revid} text is hidden or unavailable")
    out = {
        "revid": rev["revid"], "parentid": rev.get("parentid"), "pageid": page["pageid"],
        "title": page["title"], "timestamp": rev["timestamp"], "user": rev.get("user"),
        "userid": rev.get("userid"), "sha1": rev.get("sha1"),
        "content": rev["slots"]["main"]["content"],
    }
    cache.save(p, out)
    return out


def get_history(pageid: int, upto_revid: int) -> list[dict]:
    """All revisions of a page up to and including upto_revid, oldest first.

    Each item: {revid, parentid, timestamp, user, userid, hidden}. `user` is the current account
    name (MediaWiki shows renamed accounts under their new name); `userid` is 0 for IP edits.
    """
    p = cache.path("mediawiki", "history", str(pageid))
    hist = cache.load(p) or []
    if not hist or hist[-1]["revid"] < upto_revid:
        params = {"action": "query", "prop": "revisions", "pageids": str(pageid),
                  "rvprop": "ids|timestamp|user|userid", "rvlimit": "max", "rvdir": "newer"}
        if hist:
            params["rvstartid"] = str(hist[-1]["revid"] + 1)
        seen = {h["revid"] for h in hist}
        while True:
            data = api(params)
            for r in data["query"]["pages"][0].get("revisions", []):
                if r["revid"] in seen:
                    continue
                seen.add(r["revid"])
                hist.append({"revid": r["revid"], "parentid": r.get("parentid"),
                             "timestamp": r["timestamp"], "user": r.get("user"),
                             "userid": r.get("userid"), "hidden": bool(r.get("userhidden"))})
            cont = data.get("continue")
            if not cont:
                break
            params.update(cont)
            if hist and hist[-1]["revid"] >= upto_revid:
                break
        hist.sort(key=lambda h: h["revid"])
        cache.save(p, hist)
    return [h for h in hist if h["revid"] <= upto_revid]


def resolve_users(names: list[str]) -> dict[str, dict]:
    """Map account names to {userid, name}. User IDs never change, so results are cached."""
    p = cache.path("mediawiki", "users")
    known = cache.load(p) or {}
    todo = sorted({n for n in names if n not in known})
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        data = api({"action": "query", "list": "users", "ususers": "|".join(batch)})
        for u in data["query"]["users"]:
            known[u["name"]] = {"userid": u.get("userid"), "name": u["name"],
                                "missing": bool(u.get("missing") or u.get("invalid"))}
        # MediaWiki normalises names (first letter upper-cased, underscores to spaces).
        for n in batch:
            norm = n.replace("_", " ")
            norm = norm[:1].upper() + norm[1:]
            if n not in known and norm in known:
                known[n] = known[norm]
            elif n not in known:
                known[n] = {"userid": None, "name": n, "missing": True}
    # Renamed accounts: follow Wikipedia's rename log to the current account.
    for n in todo:
        if not known[n]["missing"]:
            continue
        cur, logids = n, []
        for _ in range(5):
            data = api({"action": "query", "list": "logevents", "letype": "renameuser",
                        "letitle": f"User:{cur}", "lelimit": "5"})
            ev = [e for e in data["query"]["logevents"]
                  if e.get("params", {}).get("olduser") == cur]
            if not ev:
                break
            cur = ev[0]["params"]["newuser"]
            logids.append(ev[0]["logid"])
        if logids:
            u = api({"action": "query", "list": "users", "ususers": cur})["query"]["users"][0]
            if u.get("userid"):
                known[n] = {"userid": u["userid"], "name": u["name"], "missing": False,
                            "rename_logids": logids}
    if todo:
        cache.save(p, known)
    return {n: known[n] for n in names}


def block_snapshot(revid: int, usernames: list[str]) -> dict:
    """Active blocks for the given accounts, taken once per analysed revision.

    Returns {"date": "YYYY-MM-DD", "blocks": {username: block}}. Rerunning the same revision
    reuses the snapshot, so results stay reproducible; the date says how current it is.
    """
    p = cache.path("mediawiki", "blocks", f"rev-{revid}")
    snap = cache.load(p)
    names = sorted(set(usernames))
    digest = hashlib.sha256("\n".join(names).encode()).hexdigest()
    if snap is not None and snap.get("names_sha256") == digest:
        return snap
    blocks = {}
    for i in range(0, len(names), 50):
        batch = names[i:i + 50]
        params = {"action": "query", "list": "blocks", "bkusers": "|".join(batch),
                  "bkprop": "id|user|userid|by|timestamp|expiry|reason|flags|restrictions",
                  "bklimit": "max"}
        while True:
            data = api(params)
            for b in data["query"]["blocks"]:
                blocks.setdefault(b["user"], []).append({
                    "id": b["id"], "timestamp": b["timestamp"], "expiry": b["expiry"],
                    "reason": b.get("reason", ""), "partial": bool(b.get("partial")),
                })
            if "continue" not in data:
                break
            params.update(data["continue"])
    snap = {"date": dt.datetime.now(dt.timezone.utc).date().isoformat(),
            "names_sha256": digest, "blocks": blocks}
    cache.save(p, snap)
    return snap


def compare(torev: int) -> dict:
    """Diff of a revision against its parent (used by the hand-check helper). Cached by revid."""
    p = cache.path("mediawiki", "compare", str(torev))
    hit = cache.load(p)
    if hit is not None:
        return hit
    data = api({"action": "compare", "torev": str(torev), "torelative": "prev",
                "prop": "diff|ids|user|timestamp"})
    out = data["compare"]
    cache.save(p, out)
    return out


def page_wikitext(revid: int) -> dict:
    """Wikitext of any page revision (used to verify sanctions links). Cached by revid."""
    p = cache.path("mediawiki", "parse", str(revid))
    hit = cache.load(p)
    if hit is not None:
        return hit
    data = api({"action": "parse", "oldid": str(revid), "prop": "wikitext|revid"})
    out = {"title": data["parse"]["title"], "revid": data["parse"]["revid"],
           "wikitext": data["parse"]["wikitext"]}
    cache.save(p, out)
    return out
