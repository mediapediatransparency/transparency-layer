# Wikipedia Transparency Layer — Metrics & Display Spec

3 Nov 2026 · exported from the planning doc

A transparency layer for Wikipedia: for any article, it shows who wrote the text, which sources and
authors it rests on and what documented leanings they carry, and how the article was fought over.
The same findings are published as structured data, so an AI that retrieves the article also gets
its provenance.

Three rules drive every design choice: show evidence, never one score; run every metric identically
for every side; code first, AI only where code can't do the job.

## Purpose and ground rules

The tool shows a reader who shaped a Wikipedia article, from which sources, and under what dispute,
then leaves the verdict to them. It reads only public data and never reduces its findings to one
bias score.

The guiding aim: maximum transparency about the article being read, not judgments about the people
who wrote it. The tool asks "how reliable is this text, and how did it get this way?", never "who
is guilty?"

1. **Show, don't score.** Every finding is a breakdown with its evidence. There is no single
   "leaning" number.
2. **Public on-wiki data only.** Usernames and their on-wiki records. No attempt to identify real
   people, no off-wiki tracking.
3. **Reproducible.** Every claim links to the exact revision, diff, log entry or discussion behind
   it, so anyone can check it.
4. **Facts before inferences.** Hard facts (who wrote what, who was sanctioned) are shown plainly.
   Inferences (possible coordination, loaded wording) are labelled as signals, with their
   confidence and known false-positive patterns.
5. **Symmetric by construction.** Every metric runs identically whichever side an editor or source
   is on. The tool has no built-in notion of "sides" unless a user applies a lens.
6. **Disagreement is information.** Where rating systems, language editions or sources disagree,
   the tool shows the disagreement instead of resolving it.
7. **Anonymous by default.** The reader view refers to editors as neutral labels (Editor 1,
   Editor 2) grouped by facts, such as "later sanctioned" or "wrote 30% of the lead". Usernames
   appear only one click deeper, in the evidence links, where Wikipedia already shows them.

## Claim status: what kind of statement is this?

Every sentence gets exactly one status label. It is the single most useful thing a reader or an AI
can know about a sentence. The status is decided by fixed rules over the sentence's form, its
citations and its sources' ratings across all lenses, so it is mostly code.

"Mainstream" means a source that at least one lens rates reliable; "fringe" means sources that
every lens rates unreliable. That way no single rating system, including Wikipedia's own, decides
what counts as a real dispute.

| Status | What it means | How it is decided | How to present it |
|---|---|---|---|
| Established fact | Two or more independent reliable sources agree; none contradict | Count of independent publishers (wire reprints counted once), contradiction check | State plainly |
| Single-source fact | One source, not contradicted | Citation count | State with attribution ("according to X") |
| Disputed by fringe only | Contradicted only by sources every lens rates unreliable | Lens check on the contradicting sources | State as fact; note the dispute only where it is notable |
| Disputed in mainstream | Contradicted by a source at least one lens rates reliable | Lens check on the contradicting sources | Give each version with attribution and its evidence |
| Changed over time | Reliable reporting shifted after the first reports, e.g. early casualty or responsibility claims | Publication dates of supporting vs contradicting sources | Give the latest assessment and note the earlier one |
| Party claim | The only source is a party to the conflict: a government, army, armed group or one of its ministries | Publisher matched against a published list of parties, using ownership data | Always attributed, whichever party |
| Unsourced | No citation | Parser | Flagged; not to be relied on |
| Expert opinion, in field | Author has a record in the relevant field | Author record matched to the claim's topic | Attributed, with credentials |
| Expert opinion, other field | A credentialed author speaking outside their field | Same match, failing | Attributed, with the mismatch shown |
| Advocacy or lay opinion | Columnists, activists, officials, NGOs, commentators | Opinion-section metadata, attributive verbs, author profile | Attributed, never as fact |

Detecting that one source contradicts another is the only step that needs a model. It runs through
the same cheapest-first funnel as family F.

### Credentials, shown for every opinion

All from database lookups, no AI:

- **Field match:** the author's publications and post in the claim's specific field (e.g.
  international law, epidemiology, military history), not just "Professor".
- **Track record:** peer-reviewed works in that field, citations, years active (OpenAlex, ORCID).
- **Position:** current institution and role, from the author's own bio.
- **Affiliations and funding:** advocacy roles, employer, funders (family J).
- **Consensus context:** whether the view matches review articles or published surveys of experts
  in the field, where these exist.

### Possible AI-generated material

Checked in two places: the article's own text and the sources it cites. Detection of AI writing is
unreliable, so the flag says "check this", never "AI-written".

- Citations that don't resolve: a DOI or URL that never existed, with no archive record or a title
  mismatch. This is the strongest signal and pure code.
- Edit pattern: large, polished insertions by new accounts since late 2022, especially in contested
  sections.
- Wikipedia's own tags for suspected AI text.
- Cited sites with content-farm signs: no named authors, mass output, no corrections policy.
- Statistical detectors: shown only as a weak signal, because they misfire, especially on
  non-native writers.

### Citation quality, per citation

- Primary, secondary or tertiary source.
- News report, opinion piece or advocacy publication. An opinion piece cited for a fact is flagged.
- Independent report or reprint. Wire copies count once.
- Circular: the source itself relies on Wikipedia.
- Accessible: link works, archived, language.
- Timing: published before or after the facts settled.

## Data sources

Nearly everything needed is already public and free; the only paid inputs are outside bias-rating
datasets. Access details for each should be confirmed at build time.

| Source | What it gives | Access | Cost |
|---|---|---|---|
| MediaWiki Action API | Full revision history, diffs, editor contributions, page protection, block and abuse-filter logs | Public API | Free |
| WikiWho / "Who Wrote That?" | Which editor wrote each word of the current text | Public API and Wikimedia browser extension | Free |
| XTools | Top editors, edit counts, article statistics | Public tool | Free |
| Wikimedia revert-risk models (Lift Wing) | Likelihood that an edit will be reverted | Public API | Free |
| Arbitration and enforcement records | Case decisions, topic bans, site bans, enforcement log, editing restrictions | Public wiki pages, parsed | Free |
| Sockpuppet investigation archives | Confirmed and suspected sockpuppet accounts | Public wiki pages, parsed | Free |
| Perennial sources list and Reliable Sources Noticeboard archives | Source ratings plus the discussions and votes that set them | Public wiki pages, parsed | Free |
| RfC, deletion and move discussion archives | Who voted how on content decisions | Public wiki pages, parsed | Free |
| Talk pages and archives | Disputes, rejected edit requests, consensus records | Public API | Free |
| Wikidata sitelinks | The same article in other language editions | Public API | Free |
| Pageviews API | How many people read the article, and when | Public API | Free |
| Internet Archive | Archived copies of cited pages, dead-link checks | Public API | Free |
| OpenAlex / Crossref | Metadata for academic citations | Public API | Free |
| Outside bias and reliability ratings (e.g. AllSides, Media Bias/Fact Check, Ad Fontes) | Independent source ratings for comparison lenses | Licensed datasets | Paid; licences vary |

## A. Authorship and control

These answer the first question a reader should ask: who actually wrote what I am reading? All are
hard facts computed from the revision history.

| Metric | What it shows | How computed |
|---|---|---|
| Current-text authorship share | % of today's words written by each editor | Word-level attribution (WikiWho) |
| Concentration | How few editors wrote most of the text, e.g. "4 editors wrote 62%" | Top-N share and a concentration index over the attribution |
| Lead-section authorship | Who wrote the opening paragraphs, which most readers and AI summaries use | Attribution limited to the lead |
| Survival rate | How long each editor's text lasts before removal, compared with the article average | Word-level lifespan from the history |
| Removal pattern | Whose additions get removed, and by whom | Attribution of deleted words, paired with the editor who removed them |
| Ownership signal | Editors who revert most changes by others to "their" sections | Share of others' edits reverted, per editor, per section |
| Editor topic focus | Whether top authors edit broadly or almost only in this topic area | Share of each editor's edits that fall in the same topic category |
| Newcomer access | Whether new or outside editors' changes survive | Survival of edits by accounts below the extended-confirmed threshold, plus answered edit requests |

## B. Editor accountability

This is the most direct answer to the problem Rindsberg and the ADL describe: banned editors' text
often stays live after the ban. Each metric rests on Wikipedia's own published sanctions, so it
states a fact, not an opinion.

| Metric | What it shows | How computed |
|---|---|---|
| Surviving text from sanctioned editors | % of current text written by editors later topic-banned or site-banned in this area | Authorship (A) joined with the arbitration and enforcement logs |
| Surviving text from sockpuppets | % written by accounts later confirmed as sockpuppets | Authorship joined with sockpuppet investigation archives |
| Pre-sanction vs post-sanction edits | Whether the problematic text was added before or after the editor was warned | Edit dates compared with warning and sanction dates |
| Lead-section exposure | Same as above, for the lead only | Attribution limited to the lead |
| Partial-block and warning history | Lesser sanctions: formal warnings, partial blocks, editing restrictions | Block log plus the enforcement log |
| Removals reversed after a ban | Content a sanctioned editor deleted that was later restored, or still isn't | Deleted text by sanctioned editors, checked against later revisions |

Sanctions are shown with their date, scope and a link to the decision. The tool treats a sanction
as a fact about conduct. It doesn't by itself make any sentence wrong; it flags which text deserves
a second look.

## C. Coordination signals

These are statistical patterns, not proof, and are labelled as such. Editors who care about the
same topic naturally edit the same pages, so every signal is compared against a baseline of other
active editors in the same topic area.

| Signal | What it shows | How computed |
|---|---|---|
| Co-editing overlap | Pairs or groups of editors who edit the same articles far more than the topic baseline | Shared-article counts, normalised against random active editors in the area |
| Timing proximity | Editors who repeatedly arrive at the same page within minutes or hours of each other | Gaps between their edits on shared pages |
| Revert tag-teaming | One editor's reverts consistently supported by another, keeping each under the revert limit | Sequences of reverts on the same content by different editors |
| Vote alignment | Editors who vote the same way in RfCs, deletion debates and enforcement cases far above baseline | Agreement rate across shared discussions |
| Summoning pattern | Clusters of editors appearing in a discussion soon after a mention elsewhere | Arrival times after a link or ping |
| Network clusters | Groups that form tight blocks across all the signals above | Graph built from the pairwise signals |

False positives to expect: subject experts, members of an open WikiProject, and editors who watch
the same pages will all show overlap honestly. A signal is only shown with its baseline comparison
and is never presented as an accusation. Confirmed coordination comes from Wikipedia's own findings
(family B).

## K. Actor patterns

Every account's full edit history is public, so its activity can be mapped across time, articles
and themes. The ADL's 2025 report did a version of this, comparing 30 suspected editors with
baseline groups of other active editors. All detectors here are plain code over the edit history;
no AI is needed. Their output is evidence for Wikipedia's own enforcement, not a verdict.

### The activity map

Each edit is placed on four axes: time (week), article, theme (from Wikipedia's category tree and
section headings) and type (addition, removal, revert, talk comment, vote).

| View | What it reveals |
|---|---|
| Account timeline | Edits per week by theme; when an account pivoted into the topic, and how fast |
| Theme × time heatmap (whole topic) | Which themes surged when, and which accounts drove each surge |
| Article × account matrix | Who edits which articles; blocks of accounts covering the same set of pages |
| Directional ledger | Per account and theme: what it consistently adds or removes, e.g. one outlet's citations removed, one term added |

### Detectors

| Pattern | What it looks like | How detected |
|---|---|---|
| Threshold gaming | Many tiny edits made quickly to unlock restricted articles (500 edits, 30 days), then a switch to contested pages. Wikipedia's committee cited encouragement to game this threshold in its 2025 ruling | Edit size and type before vs after crossing the threshold |
| Single-purpose account | Nearly all edits in one topic, consistently in one direction | Topic share plus the directional ledger |
| Sleeper account | Long dormancy, then sudden activity in the topic, often around news events | Gaps in the activity history |
| Cross-article campaign | The same wording change, source removal or term swap across many articles in a short window | Matching diff fragments across articles |
| Event-driven surge | Edit bursts after news events or after publicly posted calls to edit | Spike detection against the topic baseline; matched against public calls to action |
| Coordinated arrival | Accounts arriving together at articles, discussions and votes | Timing and co-occurrence against the baseline (family C) |
| Behavioural twin | Two accounts with matching on-wiki habits that are never active at the same time | Account-to-account comparison of edit habits; never linked to a real person |
| Undisclosed paid editing | Promotional edits across unrelated commercial or political subjects | Topic spread, promotional wording, no paid-editing disclosure |
| Sourced-content removal | Repeated removal of reliably sourced material on one theme | Removal ledger joined with source ratings across lenses |

### How findings are handled

1. **Public:** Wikipedia's own confirmed findings (sanctions, confirmed sockpuppets) and topic-wide
   aggregates, such as theme heatmaps and detected campaigns with their diffs. No unconfirmed
   account is publicly labelled.
2. **Research view:** account-level patterns with their baselines, for researchers preparing
   evidence.
3. **Escalation:** strong patterns go to Wikipedia's enforcement and sockpuppet processes with diffs
   attached. If Wikipedia confirms them, they become public facts under family B.

The reason for the tiers: accounts are pseudonymous people, and a pattern can have an innocent
explanation. A public "suspect" label that turns out wrong invites harassment and would discredit
the whole tool. The same thresholds apply to every account, whichever side it edits for.

## D. Conflict and stability

These show how contested an article or a section is, and when it changed. A sudden shift is not
wrong by itself, but readers should know when the version they see is recent and disputed.

| Metric | What it shows | How computed |
|---|---|---|
| Revert rate | Share of edits reverted, overall and per section | Identity reverts (text restored to an earlier version) in the history |
| Edit-war episodes | Periods of back-and-forth reverting, and who took part | Clusters of mutual reverts within short windows |
| Protection history | When and why the page was locked, and at what level | Protection log |
| Content shifts by date | How much of the article changed around key dates, e.g. after 7 October 2023 | Text difference between dated revisions |
| Removed content log | Well-sourced passages that were deleted, with the edit summary given | Deleted text that carried citations, with its remover and reason |
| Lead volatility | How often the opening paragraphs change | Revisions that touched the lead |
| Talk-page heat | Volume of dispute, open RfCs, unanswered edit requests | Talk page and archive counts |
| Readership at stake | Daily readers, especially during news spikes | Pageviews |

## E. Sources

The tool rates sources through several lenses side by side, never one. Wikipedia's own ratings are
one lens among several, shown together with where they came from (family I).

| Metric | What it shows | How computed |
|---|---|---|
| Citation inventory | Every source cited, how often, and in which sections | Parsed references, grouped by publisher |
| Source concentration | How much of the article rests on a few outlets or authors | Share of citations per publisher and per author |
| Source type mix | News, academic, NGO or advocacy, government, primary documents | Classified by publisher type |
| Wikipedia rating | Each source's rating on Wikipedia's perennial sources list, with date and link | Parsed from the list |
| Outside ratings | The same sources under outside reliability and lean ratings | Licensed datasets, each a separate lens |
| Rating disagreement | Sources Wikipedia rates very differently from outside raters | Gap between lenses, per source |
| Use in wikivoice vs attributed | Whether a source's claims appear as fact or as "according to X" | Sentence form around each citation (see G) |
| Advocacy-source use | NGO and advocacy sources cited for facts rather than opinions | Type mix crossed with wikivoice use |
| Excluded sources | Sources removed from the article, and the reason given | Deleted citations, with their edit summaries |
| Dead and altered links | Citations that no longer load or whose page has changed | Archive comparison |
| Citation age | Breaking-news citations never replaced by later reporting | Publication dates of cited news on event articles |

One important caution: a source's lean says little about how it is used. Citing a partisan outlet
for its own stated position is normal practice. The useful signal is the combination: which sources
carry factual claims in Wikipedia's own voice.

## J. Author and publication profiling

Outlet ratings miss what often matters most: who wrote the cited work and for which school of
thought. This family profiles journals, publishers and authors from documented facts only, such as
their own declarations, ownership, funding and affiliations. It never infers anyone's ideology from
their opinions.

| Metric | What it shows | How computed |
|---|---|---|
| Self-declared orientation | A publication's own stated stance, e.g. a subtitle or mission statement calling it socialist, Marxist, Zionist, conservative or libertarian | Publication's about page and Wikidata "political ideology" field; confirmed once per publication, then cached |
| Ownership and state control | State-owned or party-owned outlets, and their owners | Wikidata ownership fields, plus country press-freedom context |
| Funding | Main funders of NGOs and think tanks cited as sources | Public financial filings (e.g. US nonprofit tax returns) and official funding registries |
| Advocacy vs independent | Whether the author or organisation describes itself as campaigning for a cause | Self-description and mission statement |
| Author affiliations | An author's institution, roles in advocacy groups, and editorial posts | OpenAlex author records, the author's own published bio |
| Citation community | Which scholarly community a cited work belongs to: the cluster of works that cite each other | Citation graph from OpenAlex, clustered by algorithm; no ideology label needed |
| Viewpoint balance | Share of the article's citations from each community vs that community's share of all scholarship on the topic | Article citations per cluster vs cluster sizes in the topic's literature, which matches Wikipedia's own "due weight" rule |
| Self-citation loops | Articles resting on a small circle of authors who mainly cite each other | Co-citation density within the cited set |
| Retracted or predatory sources | Citations to retracted papers or low-quality journals | Retraction databases and journal index checks |

What keeps this fair: labels appear only with a link to the document they come from, such as the
journal's own mission page or the funder's own filing. Where nothing is declared, the tool says "no
declared orientation" rather than guessing. Outside raters' labels stay a separate, clearly marked
lens. Citation communities are found by structure first and only then described by what their
leading journals say about themselves, so the grouping isn't shaped by anyone's prior view of who
belongs where.

## F. Claim-to-source verification

This is the most powerful check and the costliest one. It asks of each sentence: does the cited
source actually say this? A mismatch is the least arguable kind of finding, so it is the best basis
for a correction on Wikipedia.

| Check | What it finds | How computed |
|---|---|---|
| Support | Whether the cited source states the claim, partly states it, or doesn't | AI reads the sentence and the source text, then a human confirms each flag |
| Overstatement | "Some reports suggest" in the source becoming plain fact in the article | Comparison of certainty wording in source vs article |
| Missing context | Source qualifications or counter-facts dropped from the summary | AI comparison, human-confirmed |
| Selective quotation | Quotes trimmed in a way that changes their meaning | Comparison with the full quote in the source |
| Uncited claims | Contentious sentences with no citation | Sentences without a reference, ranked by how contested the section is |
| Citation laundering | A chain where article → news story → the original claim is weaker or traces back to Wikipedia itself | Following the source's own references |
| Source accessibility | Paywalled, offline or foreign-language sources that few editors can check | Link and language checks |

AI is only the first pass here. It is fast at finding candidate mismatches but can misread sources,
so no mismatch is published without a human reviewer and a quoted excerpt from the source as
evidence.

## G. Language and framing

These are the most subjective metrics, so they measure asymmetry, not "bad words". The question is
whether comparable facts about each party are described the same way.

| Metric | What it shows | How computed |
|---|---|---|
| Attribution asymmetry | One party's claims stated as fact, the other's as "X claimed" | Classify sentences as wikivoice or attributed, by which party they concern |
| Verb asymmetry | "Said" for one side vs "claimed" or "alleged" for the other | Reporting verbs counted by party |
| Agency and voice | Active voice for one party's actions, passive for the other's ("were killed" vs "killed") | Grammatical parsing by party |
| Loaded terms | Contested terms used in wikivoice without attribution | A term list, shown with each term's usage counts so users can judge |
| Weasel and hedge words | "Critics say", "widely regarded", with no named source | Pattern match against Wikipedia's own style guidance |
| Lead vs body weight | Claims prominent in the lead but thin in the body, or the reverse | Compare the lead's emphasis with the share of body text and sources on that topic |
| Section weight | Space given to each viewpoint relative to its share in reliable sources | Word counts per viewpoint vs citation counts per viewpoint |
| Cross-article consistency | The same event described differently in different articles | Matching passages across linked articles |

Term lists are themselves contested, so the tool publishes its list, lets users add their own, and
shows counts rather than a verdict.

## H. External cross-verification

These check the article against independent references. Comparing language editions is especially
useful for this topic, because the English, Hebrew and Arabic editions have different editor
communities.

| Check | What it shows | How computed |
|---|---|---|
| Language-edition comparison | Facts, framing and sources in the English article vs the Hebrew, Arabic, French, German and other editions | Linked editions via Wikidata, machine-translated, then aligned claim by claim |
| Claims unique to one edition | Facts or framings found in one edition only | Claims with no match in other editions |
| Other reference works | How established encyclopedias and reference books treat the same topic | Comparison against licensed or open reference texts where available |
| Scholarly coverage | Whether the article reflects the range of academic work on the topic | Academic citations vs leading works by citation count (OpenAlex) |
| News coverage spread | Whether the cited news sources match the spread of coverage in major outlets | Article's news citations vs a broad news sample on the same event |
| Wikidata consistency | Whether structured data (dates, casualty figures, places) matches the article text | Field-by-field comparison |
| Talk-page vs article | Points with consensus on the talk page that never reached the article, or the reverse | Matching closed discussions against later revisions |

## I. Governance provenance

This family looks at the rules behind the articles: who set the source ratings and decided the key
content disputes. No existing tool shows this, and it addresses the point that Wikipedia's
reliability ratings are themselves community judgments in the same contested topic area.

| Metric | What it shows | How computed |
|---|---|---|
| Rating provenance | For each source rating: the discussion, date, closer, and every participant's vote | Parsed Reliable Sources Noticeboard and RfC archives |
| Participant overlap with sanctioned editors | Share of votes in a rating or RfC cast by editors later sanctioned in the topic | Votes joined with enforcement logs |
| Participant overlap with top authors | Whether the people rating sources are the same people writing the articles that cite them | Voters joined with authorship (A) |
| Consistency across similar sources | Whether comparable sources from different sides got comparable ratings and evidence standards | Side-by-side of rating discussions, with the evidence cited in each |
| Closer history | Who closed contested discussions, and their involvement in the topic | Closer's own edit history in the area |
| Decisions taken after sanctions | Ratings or RfCs decided with heavy participation by later-sanctioned editors and never revisited | The overlap metric, filtered to decisions with no later review |

Example of the kind of question this answers: the June 2024 discussion that rated the ADL generally
unreliable on Israel-Palestine. Who voted, and how many were later sanctioned in this topic? The
tool reports the count with links; readers draw the conclusion.

## L. Removed and rejected content

Most of what editors strike down stays public. Wikipedia keeps every version of every article, so
anything removed from a live article can be recovered and shown. The exceptions are deleted
articles and hidden revisions, and those should stay hidden.

| What was struck down | Visible? | How it's tracked (all code) |
|---|---|---|
| Text removed from an article | Fully | Compare consecutive versions; record who removed it, when, the reason given, and whether it was sourced |
| Reverted additions | Fully | Detect edits undone by the next edits; record whether the revert was discussed on the talk page |
| Sources removed | Fully | Citations present in one version and gone in the next, with that source's ratings across lenses |
| Rejected edit requests | Fully | Requests from newer accounts to change protected pages, parsed from talk pages and their archives, with the reason for refusal |
| Failed proposals | Fully | Talk-page proposals and RfCs closed as rejected or "no consensus", or never answered |
| Article renames | Fully | The move log plus the rename discussion, e.g. "Israel–Hamas war" renamed to "Gaza war" |
| Articles merged or turned into redirects | Fully | The old article's history stays public under the redirect |
| Deleted articles | Discussion only | The deletion debate, votes and reasoning are public; the deleted text is visible only to administrators |
| Hidden revisions | Count and log reason only | Wikipedia hides revisions for privacy, copyright or defamation; the log shows that something was hidden, not what |

| Metric | What it shows |
|---|---|
| Removal ledger | Every passage ever removed, with its sources, who removed it, the stated reason, and whether it was later restored |
| Removal reasons | Edit summaries grouped by keyword rules: "unreliable source", "undue weight", "point of view", "biography rules", "copyright", "vandalism", or no reason given |
| Sourced material removed without discussion | Passages with citations that a lens rates reliable, removed with no talk-page discussion. This is often the most telling signal |
| Removal speed | How quickly additions on each theme get removed, compared with the article's average |
| Churn | Passages repeatedly removed and restored. These are usually live disputes and are fed into claim status |
| Removal asymmetry | Whether sourced material on one theme or viewpoint is removed far more often than comparable material on another. This uses the same mirror test as the framing metrics, and is shown as counts, never as a verdict |
| Rejected-request record | What newer editors tried to add to protected articles, and why it was refused. This is the main view into what restricted articles keep out |

**On display:** a "show removed text" lens on the article itself. Removed passages appear as
struck-through text where they used to be, with the removal date, the reason given, their sources,
and a link to the exact edit. A reader can see what the article used to say and why it changed,
without leaving the page.

**Limits:**

- Material removed for privacy, defamation or copyright is shown only as "removed for
  privacy/legal reasons", never reproduced. Some removals happen precisely to protect a real person.
- No attempt to recover hidden revisions or deleted articles from mirrors. Their deletion debates
  and reasoning are still shown.

**For AI output:** each article's JSON gets a `removed` list: passage, sources, removal reason
category, date and evidence link. An AI can then see when a well-sourced point was cut from an
article, not just what the article says now.

**Cost:** everything here is plain code over the edit history, with no AI calls. It fits Phase 2,
alongside conflict and stability, since it uses the same version comparisons.

### Implementation notes for Phase 2 (added 3 Nov 2026, from the Phase 1 build)

- **Reuse what Phase 1 already fetches.** WikiWho's `all_content` (cached for survival) already
  lists every token ever added with the revisions that removed (`out`) and restored (`in`) it.
  Grouping consecutive tokens with the same removal revision gives removed passages, their
  remover, and whether and when they came back, without diffing every revision pair.
  Phase 1 keeps only word tokens and drops their text to save space, so Phase 2 needs to keep
  the token text, or refetch it.
- **Hidden revisions must stay hidden at the token level.** WikiWho is built from revision text.
  Before a removed passage is shown, check that neither the revision that added it nor the one
  that removed it is text-hidden (`texthidden`/`suppressed` in the history), and that the passage
  wasn't removed under a privacy, BLP or copyright reason. Otherwise show only the placeholder.
  This check belongs in code, not in review.
- **"Theme or viewpoint" needs a lens.** Removal asymmetry needs passages grouped by theme or
  viewpoint, but the core code has no notion of sides (ground rule 5). Themes from section
  headings and categories are safe defaults. Any viewpoint grouping should be an explicit,
  published, user-selected lens, run through the mirror test.
- **"Reliably sourced" depends on family E.** "Sourced material removed without discussion" needs
  citation parsing and lens ratings, so it lands with the free parts of E in Phase 2, not before.

## Display design

The display has four layers, so a casual reader sees a few plain facts while a researcher can reach
every piece of evidence. Each layer opens from the one above, and nothing appears without a link to
where it came from.

Rules across all layers:

- **Facts and signals look different.** Hard facts (authorship, sanctions) use solid marks; inferred
  signals (coordination, framing) use dashed marks with a confidence label.
- **No verdict colours.** No red/green "biased/neutral" scheme. Colours identify author groups or
  lenses, explained in a key.
- **One lens at a time.** Inline highlights show one metric family at a time, chosen by the reader,
  so the article stays readable. The default lens is claim status, so a reader first sees which
  sentences are established, disputed, a party's claim or an opinion.
- **A baseline beside every number.** Each figure appears next to the average for comparable
  articles, so it is never read in isolation.
- **As-of stamp.** Every panel shows the revision and date it was computed on.
- **Shareable evidence.** Any finding can be copied as a permalink, or as a ready-to-paste talk-page
  note with the diffs attached.

## Output for AI systems

An AI reading Wikipedia sees only the final text. The tool publishes the provenance alongside it,
at the sentence level, so a model can weigh each claim and not just the page as a whole.

1. A claim-level record per article revision (illustrative values):

```json
{
  "article": "Example article",
  "revision": 123456789,
  "computed": "2026-11-03",
  "authorship": {"top_editors": 4, "top_share": 0.62, "sanctioned_share": 0.18},
  "sentences": [
    {
      "id": "lead-3",
      "author_sanctioned": true,
      "status": "disputed_mainstream",
      "flags": ["opinion_piece_cited_as_fact"],
      "voice": "wikivoice",
      "contested": true,
      "verification": "partial",
      "citations": [
        {"publisher": "Outlet X", "wp_rating": "generally reliable",
         "self_declared": "socialist", "owner": "independent",
         "community": "C3", "lenses_disagree": true}
      ],
      "evidence": ["diff/987654", "source-excerpt/lead-3"]
    }
  ]
}
```

2. A context card: a short plain-text summary an AI can place next to the article when it
   retrieves it, for example:

   > Provenance for "Example article" (revision 123456789, 3 Nov 2026): 62% of text by 4 editors;
   > 18% by editors later sanctioned in this topic, including 2 of 5 lead sentences. 3 cited claims
   > not fully supported by their sources. 40% of citations come from one citation community, which
   > holds 15% of the topic's literature. Dispute level: high.

3. Delivery: static JSON files at predictable addresses (article + revision), a public API, a
   connector that AI assistants can query directly, and a bulk download for researchers and model
   builders. Open licence.

How an AI should use it:

- Follow each sentence's claim status: state established facts plainly; attribute single-source
  claims, party claims and all opinions; give both versions of mainstream disputes; and attribute
  unverified or sanctioned-author claims rather than state them as fact.
- Prefer claims marked as verified against their source, and quote the source excerpt where it
  matters.
- When citation communities are lopsided, look for the under-cited community's work before
  answering.
- Treat every flag as a reason to check, never as proof that a claim is false.

## Risks, caveats and abuse prevention

The tool's credibility depends on it being harder to accuse of bias than the problem it exposes.
The main risks and the guard against each:

| Risk | Guard |
|---|---|
| Seen as a partisan attack tool | Symmetric metrics, published methodology, open code; run the same reports on several conflict topics, not only Israel-Palestine |
| Harassment of named editors | Usernames and on-wiki records only; no public profiles of unconfirmed accounts (account-level patterns stay in the research view, family K); coordination signals shown at article level, not as lists of suspects |
| Deanonymization | Never combine on-wiki data with outside data; no matching of writing style or activity times to real people |
| False accusations of coordination | Signals always shown with their baseline and known false-positive cases; "confirmed" reserved for Wikipedia's own findings |
| AI verification errors | Human review before any mismatch is shown; the source excerpt always displayed beside the flag |
| Imported bias from outside rating sets | Several lenses side by side; disagreement shown, never averaged; users can switch lenses off |
| Gaming by editors once the tool exists | Metrics based on durable history (authorship, sanctions) are hard to game; publish changes to the method openly |
| Wikipedia policy conflicts | Use the tool to inform talk-page proposals and arbitration reports; never to make automated or AI-written edits |
| Data staleness | Every panel shows the revision and the date it was computed |

### Keeping the tool itself objective

The tool can carry bias too, through its term lists, its choice of outside lenses or its reviewers.
These checks are built in from Phase 1:

1. **Mirror test.** For every framing rule, run the mirror image. If "claimed" for party X is
   flagged, "claimed" for party Y is flagged by the same rule. Publish both counts.
2. **Control topics.** Run every metric on other contested topics (e.g. Russia-Ukraine,
   India-Pakistan, US politics) and on quiet topics. If the Israel-Palestine figures stand out, the
   comparison shows it; if they don't, that is reported too.
3. **Paired human review.** Every disputed flag is checked by two reviewers with opposing known
   views. Only flags both accept are published; their disagreement rate is published.
4. **Open method.** Code, term lists, profiling rules and lens data sources are public, with a
   changelog. Anyone can rerun a result.
5. **Correction channel.** Any editor, author or outlet can challenge a label, and the challenge and
   outcome stay public.

## Build order

Start with the facts that are cheapest to compute and hardest to dispute; add the judgment-heavy
metrics last.

1. **Phase 1: proof of concept (days, free).** A web page where you enter an article title and get
   families A and B: authorship, concentration, and surviving text from sanctioned editors. Test it
   on 5–10 Israel-Palestine articles plus a few control articles from unrelated topics.
2. **Phase 2: browser extension (weeks, free).** The same data shown as a panel on the Wikipedia
   page itself, plus family D (conflict and stability), family L (removed and rejected content)
   and the free parts of E (citation inventory, Wikipedia ratings with provenance). The JSON files
   and context cards for AI systems are published from this phase on.
3. **Phase 3: governance and coordination (weeks, free).** Family I (who set the ratings), family J
   (author and publication profiling) and family C (coordination signals with baselines). Needs
   parsing of noticeboard and RfC archives.
4. **Phase 4: verification and framing (months, low cost).** Families F and G. Needs AI calls per
   article and a small pool of human reviewers.
5. **Phase 5: comparison lenses (ongoing, paid).** Outside rating datasets, language-edition
   comparison (H), and an open methodology page with a public changelog.

## Cost plan: code first, AI last

Ten of the eleven metric families run on plain code and public data. Paid AI is needed only to check
whether hard-to-verify sentences match their sources, and only after cheaper checks have failed.
Everything not flagged goes straight from the code pipeline to the published files.

| Family | Method | AI needed | Main cost |
|---|---|---|---|
| A. Authorship | Word attribution from history | None | Compute only |
| B. Accountability | Parse sanction logs, join with authorship | None | Compute only |
| C. Coordination | Statistics and graph clustering against baselines | None | Compute only |
| D. Conflict | Revert detection, date diffs, logs | None | Compute only |
| E. Sources | Parse references, join with rating lists | None | Licence fees for outside lenses |
| F. Verification | Exact matching, then a small open model, then a large model for the rest, then humans | Yes, limited | AI calls on flagged sentences, reviewer time |
| G. Framing | Grammar parsing and term counts; viewpoint weight via a small local classifier | Minimal, local | Compute only |
| H. Cross-check | Free local translation models and text matching | Minimal, local | Compute only |
| I. Governance | Parse discussion archives, join with sanctions | None | Compute only |
| J. Profiling | Wikidata, OpenAlex, filings, citation clustering | None | One-off human check per publication |
| L. Removed content | Version comparison, edit-summary keyword rules, talk-page and log parsing | None | Compute only |

Ways to keep costs down:

- Compute once per revision and cache. When an article changes, recompute only the changed
  sentences.
- Scope first. Start with the Israel-Palestine topic area (about 10,000 articles by Rindsberg's
  count), then extend.
- Bulk from dumps, updates from the live stream. No heavy API polling.
- Serve static files. The extension reads pre-computed files, so reading costs almost nothing
  however many people use it.
- Spend AI only where it matters: lead sentences, contested sections and text by later-sanctioned
  editors.

Rough running cost, to be confirmed in Phase 1: a single small server plus free static hosting, in
the low tens of dollars a month, with AI spend scaling only with the number of flagged sentences.

## Sources

- Times of Israel: Edit wars over Israel spur rare ban of 8 Wikipedia editors
- Jewish Journal: two editors site-banned over Tech for Palestine dossier
- Times of Israel: ADL says biased edits remain despite bans
- The Signpost: coverage of the ADL reliability decision
- Wikipedia: Reliable sources guideline
