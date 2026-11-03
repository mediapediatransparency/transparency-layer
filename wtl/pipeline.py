"""Analyse one article revision: fetch (cached), attribute, measure, and assemble the record."""

import sys
from collections import Counter, defaultdict

from . import __version__, caveats, sanctions as sanc
from .config import WIKIWHO_URL
from .fetch import cache, mediawiki as mw, wikiwho as ww
from .metrics import accountability, authorship as au
from .text import align, sentences, wikitext

WIKI = "https://en.wikipedia.org"


def diff_url(revid: int) -> str:
    return f"{WIKI}/w/index.php?diff=prev&oldid={revid}"


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def analyse(title: str | None = None, revid: int | None = None, area: str = "",
            sanctions_path=None, internals: bool = False):
    """Return the record for one revision (latest if revid is None). With internals=True also
    return {"labels": key->label, "who": key->(username, account type)} for local checks; that
    mapping is never written to the output."""
    latest = None
    if revid is None:
        info = mw.resolve_title(title)
        revid = latest = info["lastrevid"]
        if info["redirected_from"]:
            log(f"  {title!r} resolves to {info['title']!r}")
    rev = mw.get_revision(revid)
    title, pageid, text = rev["title"], rev["pageid"], rev["content"]
    log(f"  {title} @ {revid} ({rev['timestamp']})")

    rc = ww.rev_content(revid)
    hist = au.History(mw.get_history(pageid, revid))
    al = align.align(text, [t[0] for t in rc["tokens"]])
    lay = wikitext.layout(text)
    sents = sentences.split(text, lay)
    sent_of = [-1] * len(text)
    for i, s in enumerate(sents):
        for o in s.offsets:
            sent_of[o] = i

    words, who = au.collect_words(rc["tokens"], al.spans, lay, sent_of, hist)
    labels = au.label_editors(words)
    count = Counter(w.editor for w in words)
    lead_count = Counter(w.editor for w in words if w.lead)
    total, lead_total = len(words), sum(lead_count.values())

    # --- survival (all words ever added, from WikiWho all_content) ---
    p = cache.path("wikiwho", "all_content", str(pageid))
    hit = cache.load(p)
    if hit is None or hit["covers_revid"] < revid:
        if latest is None:
            latest = mw.resolve_title(title)["lastrevid"]
        log("  fetching full token history (WikiWho all_content)…")
        allc = ww.all_content(pageid, revid, latest)
    else:
        allc = hit
    key_cache: dict[int, str] = {}

    def key_of_rev(o):
        if o not in key_cache:
            key_cache[o] = au.editor_key(o, "", hist)[0]
        return key_cache[o]

    surv = au.survival(allc["tokens"], hist, revid, key_of_rev)

    # --- sanctions: seed list + block log, one rule for everyone ---
    rows = sanc.load(sanctions_path) if sanctions_path else sanc.load()
    ids = mw.resolve_users(sorted({r.username for r in rows}))
    seed_by_key = defaultdict(list)
    unresolved = 0
    for r in rows:
        u = ids[r.username]
        if u.get("userid"):
            seed_by_key[f"u{u['userid']}"].append(r)
        else:
            unresolved += 1
    names = sorted({who[k][0] for k in labels if who[k][1] in ("registered", "temporary")
                    and who[k][0]})
    snap = mw.block_snapshot(revid, names)
    applicable = {}
    for k in labels:
        ss = [r for r in seed_by_key.get(k, []) if r.applies_to(area)]
        name = who[k][0]
        for b in snap["blocks"].get(name, []):
            kind = sanc.classify_block(b)
            if kind:
                ss.append(sanc.block_sanction(name, b, kind))
        if ss:
            applicable[k] = sorted(set(ss), key=lambda s: (s.date, s.type, s.url))
    acc = accountability.compute(words, applicable, hist)

    # --- editors ---
    top_revs = defaultdict(Counter)
    by_year = defaultdict(Counter)
    for w in words:
        top_revs[w.editor][w.o_rev_id] += 1
        t = hist.time_of(w.o_rev_id)
        by_year[w.editor][str(t.year) if t else "unknown"] += 1
    editors = []
    for k, label in sorted(labels.items(), key=lambda kv: int(kv[1].split()[1])):
        ss = applicable.get(k, [])
        revs = [r for r, _ in sorted(top_revs[k].items(), key=lambda x: (-x[1], x[0]))[:3]]
        editors.append({
            "label": label,
            "account_type": who[k][1],
            "words": count[k],
            "share": au.r6(count[k] / total),
            "lead_words": lead_count.get(k, 0),
            "lead_share": au.r6(lead_count.get(k, 0) / lead_total) if lead_total else 0.0,
            "sanctioned": bool(ss),
            "sanctions": [s.public() for s in ss],
            "survival": au.survival_block(surv["per_editor"][k], surv["article"]),
            "top_revisions": revs,
            # when this editor's surviving words were first added, by calendar year (UTC)
            "added_by_year": dict(sorted(by_year[k].items())),
            "evidence": [diff_url(r) for r in revs] + [s.url for s in ss],
        })

    # --- sentences ---
    per_sent = defaultdict(list)
    for w in words:
        if w.sentence >= 0:
            per_sent[w.sentence].append(w)
    sent_out = []
    for i, s in enumerate(sents):
        ws = per_sent.get(i)
        if not ws:
            continue
        by_ed = Counter(w.editor for w in ws)
        order = sorted(by_ed, key=lambda k: (-by_ed[k], int(labels[k].split()[1])))
        by_rev = Counter(w.o_rev_id for w in ws)
        rev_order = sorted(by_rev, key=lambda r: (-by_rev[r], r))
        sw = [w for w in ws if w.editor in applicable]
        timing = Counter(accountability.word_timing(w, applicable[w.editor], hist) for w in sw)
        before = timing["before"]
        after = len(sw) - before
        sent_out.append({
            "id": s.id,
            "section": s.section_title,
            "text": s.text,
            "words": len(ws),
            "authors": [labels[k] for k in order],
            "author_words": [by_ed[k] for k in order],
            "author_sanctioned": bool(sw),
            "sanctioned_words": len(sw),
            "added_revision": rev_order[0],
            "revisions": rev_order,
            "revision_words": [by_rev[r] for r in rev_order],
            "added_before_sanction": (None if not sw or (before and after) else after == 0),
            "sanctioned_words_before": before,
            "sanctioned_words_after": after,
            "sanctioned_words_during": timing["during"] + timing["during_open"],
        })

    conc = au.concentration(count)
    lead_conc = au.concentration(lead_count)
    acct = Counter()
    for w in words:
        acct[who[w.editor][1]] += 1

    area_rows = [r for r in rows if r.area == area] if area else []
    record = {
        "article": title,
        "revision": revid,
        "revision_timestamp": rev["timestamp"],
        "computed": snap["date"],
        "topic_area": area or None,
        "permalink": f"{WIKI}/w/index.php?oldid={revid}",
        "authorship": {
            "basis": "words of readable prose; each word credited to the editor whose revision "
                     "first added it (WikiWho)",
            "total_words": total,
            "lead_words": lead_total,
            "editor_count": len(labels),
            "lead_editor_count": len(lead_count),
            "editors": editors,
            "top_shares": conc["top_shares"],
            "hhi": conc["hhi"],
            "editors_for_50pct": conc["editors_for_50pct"],
            "editors_for_80pct": conc["editors_for_80pct"],
            "lead": lead_conc,
            "account_types": {t: au.r6(n / total) for t, n in sorted(acct.items())},
            "survival_article": {h: {"words_added": n, "words_surviving": k,
                                     "rate": au.r6(k / n) if n else None}
                                 for h, (n, k) in surv["article"].items()},
            "sanctioned_share": acc["sanctioned_share"],
            "sanctioned_lead_share": acc["sanctioned_lead_share"],
        },
        "accountability": {
            **acc,
            "rule": "topic bans count on articles in the same topic area; site bans and "
                    "sockpuppetry findings count everywhere",
            "sanctions_list": {
                "seed_rows_total": len(rows),
                "seed_rows_in_topic_area": len(area_rows),
                "seed_rows_unresolved_accounts": unresolved,
                "block_log_snapshot": snap["date"],
            },
        },
        "sentences": sent_out,
        "inputs": {
            "tool_version": __version__,
            "wikitext": f"{WIKI}/w/index.php?oldid={revid}&action=raw",
            "wikiwho_rev_content": f"{WIKIWHO_URL}/rev_content/rev_id/{revid}/",
            "wikiwho_all_content": f"{WIKIWHO_URL}/all_content/page_id/{pageid}/",
            "history_revisions": len(hist.revs),
            "sanctions_csv_sha256": sanc.file_sha256(sanctions_path) if sanctions_path
            else sanc.file_sha256(),
        },
        "quality": {
            "wikiwho_tokens": len(rc["tokens"]),
            "unaligned_tokens": al.unaligned,
            "skipped_chars": al.skipped_chars,
            "words_outside_sentences": sum(1 for w in words if w.sentence < 0),
            "survival_tokens_without_history": surv["skipped_unknown_revision"],
        },
    }
    record["accountability"]["concentration"] = caveats.sanctioned_concentration(record)
    record["caveats"] = caveats.compute(record)
    if internals:
        return record, {"labels": labels, "who": who}
    return record
