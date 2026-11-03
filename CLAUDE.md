# Wikipedia Transparency Layer — project brief for Claude Code

## What this project is

A tool that shows readers how a Wikipedia article came to say what it says: who wrote the current
text, which sources it rests on, and how it was disputed. Its output is published as structured
data so AI systems that retrieve an article also get its provenance.

The full design spec is in `docs/spec.md` (exported from the planning doc). Read it before
starting any phase. This file covers **Phase 1 only**.

**Guiding aim:** maximum transparency about the article being read, not judgments about the people
who wrote it. The tool asks "how reliable is this text, and how did it get this way?", never
"who is guilty?"

## Non-negotiable rules

1. **Anonymous by default.** Reports refer to editors as neutral labels (Editor 1, Editor 2)
   grouped by facts ("later sanctioned", "wrote 30% of the lead"). Usernames appear only inside
   evidence links (diffs, log entries) that Wikipedia already shows publicly.
2. **Never unmask anyone.** No linking accounts to real names, employers, social media or
   locations. No matching writing style or active hours to identify a person. No off-wiki data
   about editors.
3. **Symmetric.** Every metric runs identically for every editor and source, whichever side they
   are on. The code has no notion of "sides".
4. **Reproducible.** Every number traces to revision IDs, diffs or log entries. Store those IDs
   with every result.
5. **No single bias score.** Output breakdowns with evidence, never one number.
6. **Read-only.** The tool never edits Wikipedia. No automated or AI-written edits.
7. **Code first, AI last.** Phase 1 uses no AI calls at all.

## Phase 1 goal

A command-line tool: give it an article title, get back

- `out/<article>/<revid>.json`: the claim-level record (schema below)
- `out/<article>/<revid>.html`: a plain, readable one-page report

covering two metric families from the spec:

**A. Authorship**
- Share of the current text written by each editor
- Concentration (top 1, 3, 5 and 10 editors' share)
- Same figures for the lead section only
- How long each editor's text survives, compared with the article average

**B. Accountability**
- Share of the current text written by editors later topic-banned or site-banned in the
  Palestine-Israel topic area, or confirmed as sockpuppets
- Same for the lead
- Whether that text was added before or after the sanction

## Test set

Resolve redirects automatically; titles below may have changed.

Topic articles:
- Gaza war
- October 7 attacks
- Zionism
- Nakba
- Hamas
- Israel

Control articles (to compare against, so topic figures aren't read in isolation):
- Russian invasion of Ukraine
- Kashmir conflict
- Photosynthesis

## Data sources

- **MediaWiki Action API** (`https://en.wikipedia.org/w/api.php`): revisions and content
  (`prop=revisions`), logs (`list=logevents`, including `letype=block`), user contributions
  (`list=usercontribs`).
  - Follow Wikimedia's API etiquette: a descriptive User-Agent with contact details, `maxlag=5`,
    requests one at a time, and back off on errors.
- **WikiWho** (word-level authorship, hosted on Wikimedia Cloud): look up the current endpoint
  and documentation before use. If it is unavailable, compute authorship from the revision
  history directly (slower but self-contained).
- **Sanctions.** Topic bans don't appear in the block log, so build `data/sanctions.csv` as a
  hand-verified seed list first. One row per sanction with: username, sanction type, scope,
  date, and a link to the decision. Sources:
  - The Arbitration Committee's Palestine-Israel case pages and noticeboard announcements
  - The arbitration enforcement log
  - The editing restrictions list
  - Sockpuppet investigation archives
  - The list must include sanctioned editors on **both** sides. For example, the January 2025
    ruling topic-banned editors from both camps. Every row needs its link; no link, no row.
  - Automated parsing of these pages comes later. Accuracy matters more than coverage here.

## Output schema (Phase 1 subset)

```json
{
  "article": "Gaza war",
  "revision": 0,
  "computed": "YYYY-MM-DD",
  "authorship": {
    "editors": [{"label": "Editor 1", "share": 0.0, "lead_share": 0.0,
                 "sanctioned": false, "evidence": ["<diff or log URL>"]}],
    "top_shares": {"1": 0.0, "3": 0.0, "5": 0.0, "10": 0.0},
    "sanctioned_share": 0.0,
    "sanctioned_lead_share": 0.0
  },
  "sentences": [
    {"id": "lead-1", "authors": ["Editor 1"], "author_sanctioned": false,
     "added_revision": 0, "added_before_sanction": null}
  ]
}
```

Editor labels are assigned by share (Editor 1 = largest) and are stable for a given revision.

## Suggested structure

- Python 3, standard project layout, `requirements.txt`
- `fetch/`: API clients with caching
- `cache/`: raw API responses, keyed by revision ID. Never refetch a revision already cached.
- `metrics/`: one module per family (A, B)
- `report/`: JSON writer and HTML template
- `data/sanctions.csv`: the seed list
- `tests/`: unit tests on small, fixed revision histories

## How to check the work

Before calling Phase 1 done:

1. **Hand-check authorship.** For 20 random sentences across the test set, open the history and
   confirm the attributed editor really added that text.
2. **Check the totals.** Authorship shares for each revision add up to 100%.
3. **Check the sanctions list.** Every row in `sanctions.csv` opens to a page confirming it.
   Both sides are represented.
4. **Run the controls.** Run every metric on the control articles and report topic figures next
   to control figures.
5. **Check reproducibility.** Rerunning on the same revision gives byte-identical JSON.
6. **Check anonymity.** No username appears in the HTML report outside evidence links.

## Not in Phase 1

Coordination signals, source ratings, claim status, AI verification and the browser extension
all come in later phases (see `docs/spec.md`). Don't start them until Phase 1 passes the checks
above.

## Implementation notes (added during Phase 1 build)

- Package code lives in `wtl/` (`wtl/fetch`, `wtl/text`, `wtl/metrics`, `wtl/report`).
- Run with `.venv/bin/python -m wtl --help`. Tests: `.venv/bin/python -m pytest`.
- Set `WTL_CONTACT` (an email or URL) before fetching, so the User-Agent carries contact details.
- See `README.md` for method definitions and `docs/phase1-results.md` for the check results.
