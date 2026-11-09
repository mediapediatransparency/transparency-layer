"""Pilot: who links to each cited website, and the audience figure of the sites that link to it.

Source: Common Crawl's domain-level web graph (one dated release, open data): every pair of
registered domains where a page on one links to a page on the other, from three months of
crawling. For each cited website we count the other domains linking to it and, among those that
have a DomainDemo audience score (Yang et al. 2025: -1 shared mostly by Democratic-leaning users,
+1 by Republican-leaning), the plain mean of their scores, each linking domain counted once.
Links from a domain to itself are left out.

This is our own derived figure, so it is tested before any use: for websites that DomainDemo
scores itself, the figure from the sites linking to them is compared with their own score
(`validate`). A link is not an endorsement: sites link to what they criticise as well as what
they agree with. The figure describes who links to a site, not what the site says.

Nothing is fetched about Wikipedia editors. Output: cache/linkgraph/<release>.json.gz (not
published while this is a pilot).
"""

import gzip
import json
import math
import time
import zlib

from .config import ROOT

RELEASE = "cc-main-2026-aug-sep-oct"
BASE = f"https://data.commoncrawl.org/projects/hyperlinkgraph/{RELEASE}/domain/{RELEASE}-domain"
OUT = ROOT / "cache" / "linkgraph" / f"{RELEASE}.json.gz"
CHUNK = 1 << 22


def stream(url, log=print):
    """Lines (bytes, no newline) of a gzip file over HTTP, resuming after a dropped connection."""
    from .fetch.http import session
    s, pos, d, rest, tries = session(), 0, zlib.decompressobj(16 + zlib.MAX_WBITS), b"", 0
    while True:
        try:
            with s.get(url, headers={"Range": f"bytes={pos}-"} if pos else {}, stream=True, timeout=120) as r:
                r.raise_for_status()
                for c in r.iter_content(CHUNK):
                    pos += len(c)
                    data = rest + d.decompress(c)
                    lines = data.split(b"\n")
                    rest = lines.pop()
                    yield from lines
            break
        except Exception as ex:   # noqa: BLE001 - network: resume from the last byte read
            tries += 1
            if tries > 20:
                raise
            log(f"  resuming at byte {pos:,} after {str(ex)[:80]}")
            time.sleep(min(60, 5 * tries))
    tail = rest + d.flush()
    if tail:
        yield tail


def _rev(d: str) -> str:
    return ".".join(reversed(d.split(".")))


def _candidates(domain: str) -> list[str]:
    """Reversed domain and each parent, most specific first (the graph holds registered domains)."""
    parts = domain.split(".")
    out = []
    for i in range(len(parts) - 1):
        rest = parts[i:]
        if len(rest) == 2 and len(rest[1]) == 2 and rest[0] in SUFFIX_2ND:
            break   # "co.uk", "com.au" and similar are suffixes, not sites
        out.append(_rev(".".join(rest)))
    return out


SUFFIX_2ND = {"co", "com", "org", "net", "ac", "gov", "edu", "or", "ne", "go", "gob", "nic", "mil", "sch", "nhs"}


def build(log=print) -> dict:
    from .outlets import OUTLETS_JSON, domaindemo
    sources = json.loads(OUTLETS_JSON.read_text(encoding="utf-8"))["sources"]
    cited = [k for k in sources if "." in k and ":" not in k and " " not in k]
    dd = domaindemo()
    want = {}
    for k in set(cited) | set(dd):
        for c in _candidates(k):
            want.setdefault(c, []).append(k)
    log(f"  linkgraph: {len(cited):,} cited websites, {len(dd):,} DomainDemo domains; reading the node list")
    node_of, score_of, n = {}, {}, 0
    for ln in stream(BASE + "-vertices.txt.gz", log):
        n += 1
        p = ln.split(b"\t")
        if len(p) < 2:
            continue
        rd = p[1].decode("utf-8", "replace")
        if rd in want:
            node_of[rd] = p[0]
            d = _rev(rd)
            if d in dd:   # only a score given to the registered domain itself
                score_of[p[0]] = dd[d]
        if n % 20_000_000 == 0:
            log(f"    {n:,} nodes")
    # each source -> its most specific domain in the graph
    target, via_parent = {}, {}
    for k in set(cited) | set(dd):
        for i, c in enumerate(_candidates(k)):
            if c in node_of:
                target.setdefault(node_of[c], []).append(k)
                via_parent[k] = i > 0
                break
    log(f"  linkgraph: {n:,} nodes; {len(target):,} target domains, {len(score_of):,} scored linkers; "
        "reading the links")
    links, scored, total, sq, e = {}, {}, {}, {}, 0
    for ln in stream(BASE + "-edges.txt.gz", log):
        e += 1
        i = ln.find(b"\t")
        t = ln[i + 1:]
        if t in target:
            f = ln[:i]
            if f != t:
                links[t] = links.get(t, 0) + 1
                v = score_of.get(f)
                if v is not None:
                    scored[t] = scored.get(t, 0) + 1
                    total[t] = total.get(t, 0.0) + v
                    sq[t] = sq.get(t, 0.0) + v * v
        if e % 100_000_000 == 0:
            log(f"    {e:,} links")
    out = {}
    for t, keys in target.items():
        m = scored.get(t, 0)
        rec = {"linking_domains": links.get(t, 0), "scored_linking_domains": m,
               "mean_score": round(total[t] / m, 4) if m else None,
               "sd": round(math.sqrt(max(0.0, sq[t] / m - (total[t] / m) ** 2)), 4) if m else None}
        for k in keys:
            out[k] = {**rec, "via_parent_domain": via_parent.get(k, False)}
    res = {"release": RELEASE, "nodes": n, "edges": e, "built": time.strftime("%Y-%m-%d"),
           "rule": __doc__.strip(), "sites": out}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump(res, f, sort_keys=True)
    log(f"wrote {OUT}: {e:,} links read, {sum(1 for v in out.values() if v['scored_linking_domains']):,} "
        "sites with at least one scored linking domain")
    return res


def _rank(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and xs[o[j + 1]] == xs[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2
        i = j + 1
    return r


def _pearson(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else None


def validate(res=None, mins=(1, 5, 10, 25, 50, 100)) -> dict:
    """For sites DomainDemo scores itself: the figure from the sites linking to them against their
    own score. Reported for all scored sites and for the cited websites alone."""
    from .outlets import OUTLETS_JSON, domaindemo
    if res is None:
        with gzip.open(OUT, "rt", encoding="utf-8") as f:
            res = json.load(f)
    dd = domaindemo()
    cited = set(json.loads(OUTLETS_JSON.read_text(encoding="utf-8"))["sources"])
    report = {}
    for group, keys in (("all DomainDemo sites", set(dd)), ("cited websites", set(dd) & cited)):
        rows = []
        for m in mins:
            pairs = [(v["mean_score"], dd[k]) for k, v in res["sites"].items()
                     if k in keys and not v["via_parent_domain"] and v["scored_linking_domains"] >= m]
            if len(pairs) < 30:
                continue
            est, own = [p[0] for p in pairs], [p[1] for p in pairs]
            mean_own = sum(own) / len(own)
            rows.append({"min_scored_linkers": m, "sites": len(pairs),
                         "pearson": round(_pearson(est, own), 3),
                         "spearman": round(_pearson(_rank(est), _rank(own)), 3),
                         "mean_abs_error": round(sum(abs(a - b) for a, b in pairs) / len(pairs), 3),
                         "mean_abs_error_guessing_the_average": round(sum(abs(mean_own - b) for b in own) / len(own), 3),
                         "same_side_of_zero": round(sum(1 for a, b in pairs if (a > 0) == (b > 0)) / len(pairs), 3)})
        report[group] = rows
    unscored = [k for k in cited if k not in dd and k in res["sites"]]
    report["cited websites with no DomainDemo score"] = {
        "in the link graph": len(unscored),
        **{f"with at least {m} scored linking domains": sum(1 for k in unscored
                                                            if res["sites"][k]["scored_linking_domains"] >= m)
           for m in mins}}
    return report
