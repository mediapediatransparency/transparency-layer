"""How often each analysed article changes, by fixed rules, from data already cached.

All figures stop at the analysed revision, so they do not depend on when they were computed.

- Edits: revisions per calendar year since the article began, and in the 365 days before the
  analysed revision: edits, distinct accounts (registered accounts by user ID, others by name),
  and the share of edits made without a registered account (IP addresses and temporary accounts).
  From the page's public revision history.
- Back-and-forth: words in the analysed text that were taken out and put back at least twice
  (WikiWho's out and in lists), as a share of the words in the text, and the longest passages
  of such words: runs of words that WikiWho first saw together, all present in the analysed
  text and all removed at least twice. WikiWho numbers words in the order it first saw them, so
  a run is usually, but not always, one stretch of text. Each passage gives how many times its
  words were removed, and the latest revision that removed or restored them.

- Protection: the page-protection log up to the analysed revision (how often administrators
  limited who may edit, and at what level), the periods it was in force, and the protection
  today; account names are not kept. Levels: "autoconfirmed" (accounts at least 4 days old with
  10 edits), "extendedconfirmed" (at least 30 days and 500 edits), "sysop" (administrators only).
- Subject date: the subject's own date from Wikidata (point in time, start time, inception, date
  of birth or publication date, the first one recorded), so activity can be set against age.

Nothing here says why a page changes: an article can be busy because its subject is in the news,
because editors disagree, or because of vandalism and its repair.

`wtl activity` writes data/activity.json. `wtl stale` asks Wikipedia how many edits each article
has had since the analysed revision (data/stale.json), to decide which to analyse again.
"""

import datetime as dt
import json
import re
from collections import Counter

from .config import ROOT
from .fetch import cache

ACTIVITY_JSON = ROOT / "data" / "activity.json"
STALE_JSON = ROOT / "data" / "stale.json"
WORD = re.compile(r"\w", re.U)
MIN_FLIPS = 2       # removed at least this many times to count as back-and-forth
LASTING_HOURS = 24  # a removal undone sooner counts as a quick repair, not as back-and-forth
MIN_RUN = 6         # words in a passage
TOP_PASSAGES = 5


def _ts(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def edits(hist: list[dict], revid: int) -> dict:
    revs = [r for r in hist if r["revid"] <= revid]
    if not revs:
        return {}
    end = _ts(next(r["timestamp"] for r in revs if r["revid"] == revid) if any(r["revid"] == revid for r in revs)
              else revs[-1]["timestamp"])
    start = end - dt.timedelta(days=365)
    year = [r for r in revs if _ts(r["timestamp"]) > start]
    who = {(f"u{r['userid']}" if r.get("userid") else f"n:{r.get('user')}") for r in year if not r.get("hidden")}
    # IP addresses (user ID 0) and temporary accounts (names starting "~", which have user IDs)
    anon = sum(1 for r in year if not r.get("userid") or str(r.get("user", "")).startswith("~"))
    return {
        "first_edit": revs[0]["timestamp"][:10],
        "edits_total": len(revs),
        "edits_by_year": dict(sorted(Counter(r["timestamp"][:4] for r in revs).items())),
        "last_365_days": {"from": start.date().isoformat(), "to": end.date().isoformat(),
                          "edits": len(year), "accounts": len(who),
                          "share_without_registered_account": round(anon / len(year), 3) if year else None},
    }


def back_and_forth(allc: dict, idx: list[int], revid: int, rev_time: dict) -> dict:
    """allc: WikiWho all_content (token-ID order); idx: positions in allc["tokens"] of the
    analysed revision's tokens in text order (wikiwho.history_positions); rev_time: revision
    id -> timestamp."""
    epoch = {r: _ts(t).timestamp() for r, t in rev_time.items()}
    toks = allc["tokens"]
    def removals(i):
        """(lasting, quick): removals later undone, split at LASTING_HOURS; and the latest event."""
        _, ins, outs, *_ = toks[i]
        ins = sorted(x for x in ins if x <= revid)
        outs = sorted(x for x in outs if x <= revid)
        lasting = quick = 0
        for o in outs:
            back = next((x for x in ins if x > o), None)
            if back is None:
                continue
            gap = (epoch.get(back, 0) - epoch.get(o, 0)) / 3600
            if gap >= LASTING_HOURS:
                lasting += 1
            else:
                quick += 1
        return lasting, quick, max(ins + outs) if (ins or outs) else 0
    text = [toks[i][3] if len(toks[i]) > 3 else "" for i in idx]
    is_word = [bool(WORD.search(x)) for x in text]
    info = [removals(i) for i in idx]
    words = [k for k in range(len(idx)) if is_word[k]]
    slow = [k for k in words if info[k][0] >= MIN_FLIPS]
    quick_any = [k for k in words if info[k][1] >= 1]
    runs, cur = [], []
    for k in range(len(idx)):
        if info[k][0] >= MIN_FLIPS or (cur and not is_word[k]):
            cur.append(k)
        else:
            if cur:
                runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    runs = [r for r in runs if sum(is_word[k] for k in r) >= MIN_RUN]
    runs.sort(key=lambda r: (-sum(is_word[k] for k in r), r[0]))
    passages = []
    for r in runs[:TOP_PASSAGES]:
        ws = [text[k] for k in r if is_word[k]]
        lr = max(info[k][2] for k in r)
        passages.append({"words": len(ws), "start": " ".join(ws[:16]) + (" …" if len(ws) > 16 else ""),
                         "times_removed_min": min(info[k][0] for k in r if is_word[k]),
                         "times_removed_max": max(info[k][0] for k in r if is_word[k]),
                         "latest_revision": lr, "latest": (rev_time.get(lr) or "")[:10]})
    n = len(words)
    return {"words": n,
            "words_removed_twice_or_more": len(slow),
            "share": round(len(slow) / n, 4) if n else None,
            "words_removed_five_times_or_more": sum(1 for k in words if info[k][0] >= 5),
            "words_with_quick_repair": len(quick_any),
            "quick_repair_share": round(len(quick_any) / n, 4) if n else None,
            "passages": passages}


DATE_PROPS = [("P585", "point in time"), ("P580", "start time"), ("P571", "inception"),
              ("P569", "date of birth"), ("P577", "publication date")]


def protection(title: str, upto: str) -> dict:
    """Page-protection log entries for the title up to the analysed revision's time (no account
    names are kept), and the page's protection today. Cached per title for a day's run; the log
    is read under the current title only, so entries made under an earlier title are missed."""
    from .fetch.mediawiki import api
    p = cache.path("activity", "protection", re.sub(r"\W+", "_", title)[:120])
    hit = cache.load(p)
    if hit is None:
        ev, cont = [], {}
        while True:
            d = api({"action": "query", "list": "logevents", "letype": "protect", "letitle": title,
                     "lelimit": "500", "leprop": "timestamp|details|type", **cont})
            for x in d.get("query", {}).get("logevents", []):
                det = (x.get("params") or {}).get("details") or []
                edit = next((y for y in det if y.get("type") == "edit"), {})
                ev.append({"date": x["timestamp"][:10], "action": x.get("action"),
                           "edit_level": edit.get("level", ""), "expiry": str(edit.get("expiry", ""))[:10]})
            if "continue" not in d:
                break
            cont = d["continue"]
        info = api({"action": "query", "titles": title, "prop": "info", "inprop": "protection"})
        pg = (info.get("query", {}).get("pages") or [{}])[0]
        now = next((y for y in pg.get("protection", []) if y.get("type") == "edit"), {})
        hit = {"events": sorted(ev, key=lambda x: x["date"]), "today": now.get("level", "none"),
               "today_expiry": str(now.get("expiry", ""))[:10], "checked": dt.date.today().isoformat()}
        cache.save(p, hit)
    ev = [x for x in hit["events"] if x["date"] <= upto[:10]]
    return {"events_up_to_revision": len(ev),
            "periods": protection_periods(ev, upto[:10]),
            "by_action": dict(Counter(x["action"] for x in ev)),
            "first": ev[0]["date"] if ev else None, "latest": ev[-1]["date"] if ev else None,
            "latest_edit_level": ev[-1]["edit_level"] if ev else None,
            "today": hit["today"], "checked": hit["checked"]}


def protection_periods(ev: list[dict], upto: str) -> list[dict]:
    """[{from, to, level}] when the page was protected against editing, up to `upto` (a date).
    A protection lasts until the next log entry, its expiry, or `upto`, whichever is first.
    Log entries from before about 2008 do not record the level ("unknown")."""
    out = []
    ev = [x for x in ev if x["action"] in ("protect", "modify", "unprotect")]   # not page moves
    for i, x in enumerate(ev):
        if x["action"] == "unprotect":
            continue
        nxt = ev[i + 1]["date"] if i + 1 < len(ev) else upto
        exp = x.get("expiry") or ""
        end = min(nxt, exp) if re.match(r"\d{4}-\d{2}-\d{2}$", exp) else nxt
        if end > x["date"] or (end == x["date"] and i + 1 == len(ev)):
            lvl = x.get("edit_level") or "unknown"
            if out and out[-1]["to"] == x["date"] and out[-1]["level"] == lvl:
                out[-1]["to"] = end
            else:
                out.append({"from": x["date"], "to": end, "level": lvl})
    return out


def subject_dates(qids: list[str]) -> dict:
    """Wikidata ID -> {property, label, date} for the subject's own date: when an event happened,
    began or was founded, or a person was born (the first of DATE_PROPS that Wikidata has)."""
    from .fetch.http import get_json
    p = cache.path("activity", "subject_dates")
    known = cache.load(p) or {}
    todo = sorted({q for q in qids if q and q not in known})
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        w = get_json("https://www.wikidata.org/w/api.php", {"action": "wbgetentities", "ids": "|".join(batch),
                                                            "props": "claims", "format": "json"})
        for q in batch:
            cl = ((w.get("entities") or {}).get(q) or {}).get("claims") or {}
            got = None
            for prop, label in DATE_PROPS:
                for c in cl.get(prop, []):
                    v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
                    t = v.get("time") if isinstance(v, dict) else None
                    if t:
                        got = {"property": prop, "label": label, "date": t.lstrip("+")[:10]}
                        break
                if got:
                    break
            known[q] = got or {}
        cache.save(p, known)
    return known


def _qids() -> dict:
    import csv
    from .candidates import CANDIDATES_CSV
    out = {}
    if CANDIDATES_CSV.exists():
        with open(CANDIDATES_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("wikidata"):
                    out[r["title"]] = r["wikidata"]
    info = cache.load(cache.path("candidates", "info_v2")) or {}
    for t, i in info.items():
        if i.get("qid"):
            out.setdefault(i["title"], i["qid"])
    return out


def compute(records: list[dict]) -> dict:
    from .fetch import mediawiki as mw
    from .fetch import wikiwho as ww
    out = {}
    for r in records:
        try:
            rc = ww.rev_content(r["revision"])
            pageid = rc["page_id"]
            hist = mw.get_history(pageid, r["revision"])
        except Exception:  # noqa: BLE001
            continue
        e = {"revision": r["revision"], **edits(hist, r["revision"])}
        allc = cache.load(cache.path("wikiwho", "all_content_v2", str(pageid)))
        if allc and allc.get("covers_revid", 0) >= r["revision"] and allc["tokens"] and len(allc["tokens"][0]) > 3:
            try:
                order = ww.rev_token_ids(r["revision"])
            except Exception:  # noqa: BLE001  no network: left out this run
                order = None
            idx = ww.history_positions(allc, order, rc["tokens"]) if order else None
            if idx:
                e["back_and_forth"] = back_and_forth(allc, idx, r["revision"],
                                                     {h["revid"]: h["timestamp"] for h in hist})
        try:
            e["protection"] = protection(r["article"], r.get("revision_timestamp") or "9999")
        except Exception:  # noqa: BLE001
            pass
        out[r["article"]] = e
    qids = _qids()
    dates = subject_dates([qids.get(a) for a in out])
    for a, e in out.items():
        sd = dates.get(qids.get(a) or "")
        if sd:
            e["subject_date"] = {**sd, "wikidata": qids[a]}
    return out


def write(records: list[dict]) -> dict:
    d = {"built": dt.date.today().isoformat(), "rule": __doc__.strip(), "articles": compute(records)}
    ACTIVITY_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    return d


def stale(records: list[dict]) -> dict:
    """Edits to each article since its analysed revision, asked of Wikipedia now."""
    from .fetch.mediawiki import api
    out = {}
    for r in records:
        params = {"action": "query", "titles": r["article"], "prop": "revisions", "rvprop": "ids|timestamp|size",
                  "rvlimit": "max", "rvdir": "newer", "rvstartid": str(r["revision"])}
        n, first_size, last, cont = 0, None, None, {}
        while True:
            d = api({**params, **cont})
            pgs = d.get("query", {}).get("pages", [])
            revs = (pgs[0].get("revisions") if pgs else None) or []
            for x in revs:
                if first_size is None:
                    first_size = x.get("size")
                last = x
                n += 1
            if "continue" not in d:
                break
            cont = d["continue"]
        out[r["article"]] = {"analysed_revision": r["revision"], "edits_since": max(0, n - 1),
                             "latest_revision": last["revid"] if last else None,
                             "latest": (last or {}).get("timestamp", "")[:10],
                             "bytes_change": (last.get("size", 0) - (first_size or 0)) if last else None}
    for x in out.values():
        x["checked"] = dt.date.today().isoformat()
    d = {"checked": dt.date.today().isoformat(), "articles": out}
    STALE_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    return d


def load() -> dict:
    return json.loads(ACTIVITY_JSON.read_text(encoding="utf-8")) if ACTIVITY_JSON.exists() else {}
