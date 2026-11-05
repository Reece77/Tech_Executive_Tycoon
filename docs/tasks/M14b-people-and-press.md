# M14b: People and press (lane B)

**Goal:** what the company says in public starts to matter. Launches, earnings, crises and eras bring press moments with a choice of tone and the option of a **public promise** (ship by a date, beat a rival, reach an era, no layoffs, no price rise), which the engine tracks and rewards or punishes in brand, credibility, morale and share price. Rival CEOs become named characters who answer back, and feuds turn into rivalries. Three recruitment fixes from playtest 2 ride along.

**Spec sections:** §5 (people), §16 (events) · **ADRs:** 0002, 0005, 0007, 0013 (stream `press` 40; 41–42 reserved), 0015 · **Formulas:** `docs/formulas.md` §29 (all), with §16, §25.4, §27 · **Playtest:** `docs/playtests/reece-playtest-2.md` · **Backlog:** `docs/ideas-backlog.md` · **Depends on:** M13b (`m13b-done`) · **Lane:** B, alongside M14

## Lane

- **Lane B.** Its own session and branch (`m14b-press`). **Merge order: M14b merges first** (it is the smaller milestone); M14 then merges `main`, re-parents its migrations and regenerates golden snapshots.
- **M14b owns:** new `backend/tst/sim/press/` (moments, promises, credibility); rival CEOs and feuds (new `backend/tst/sim/rivals/characters.py`); the recruitment changes in `backend/tst/sim/hiring/`; `data/events/press.yaml`; screens: press items in the inbox, a Promises panel and credibility on the Overview, leadership fit on Org and People, Replace and interest search on Recruitment, and a new `RivalLeaderPanel` component (CEO, statements, feud) inserted into the Rival screen with a one-line change.
- **M14b must not edit:** `backend/tst/sim/mna/`, consolidation, `incumbents.yaml`, `entrants.yaml`, `data/events/deals.yaml`, the Rival screen beyond the one-line insertion, Finance → Deals (M14's). Rival CEOs come from existing key people, so no data-file change is needed.
- **Hook for M14:** expose `press.queue_moment(state, company_id, trigger, facts)` so M14 can add the acquisition-announced trigger when it merges second.
- **Shared files:** `balance.yaml` (add only `press.*`, `promise.*`, `feud.*`, `recruit.*`; append to `events.trigger`), `docs/formulas.md` (notes in §29 only), `CHANGELOG.md`, `docs/data-dictionary.md`: keep both sides.
- **Golden snapshots:** press events change the event flow, so this lane may regenerate golden snapshots once, with the reason in CHANGELOG; M14 regenerates again on the combined code.

## Out of scope

One-on-ones and private promises (Reece: not needed). Social media and advertising campaigns. Press for subsidiaries (M16). Analyst questions beyond §29.3's credibility weight.

## Sub-tasks (commit after each)

1. **Data and formula tests:** `press.*`, `promise.*`, `feud.*`, `recruit.*` keys with comments; press templates (every trigger and tone, with the LLM allowed to write titles and bodies from engine facts only, choices always the template's, ADR-0005); stream `press` in ADR-0013's main table; both §29.8 examples as unit tests.
2. **Press moments** (§29.1): triggers, the quarterly cap with stakes order, tones, audience, bold backfire.
3. **Promises** (§29.2): making, tracking from displayed values, deadlines, kept and broken effects, reminders. **Tests:** each kind kept and broken; a promise is judged on displayed values (differential test: two saves with the same displayed quality but different true quality judge a Beat promise the same way).
4. **Credibility** (§29.3): drift, effects on press, analysts' consensus (listed) and hiring appeal; Overview panel.
5. **Rival CEOs and feuds** (§29.4): CEO choice and succession, statements, feud sources and decay, rivalry effects on rival decisions and poaching, storyline events; the `RivalLeaderPanel`.
6. **Recruitment fixes** (§29.5): Replace with a recruiter, search by interest with its fee, leadership-fit ranges from revealed values only (hidden-value test).
7. **API, CLI and screens:** press moments in the inbox; the Promises panel (open, kept, broken, progress, deadline); credibility; rival CEOs; Replace and interest filter; leadership fit. **CLI:** `tst press`, `tst promises`, `tst feuds`. Glossary entries.
8. **Balance and e2e:**
   - §29.7 targets printed and recorded; tune only `press.*`, `promise.*`, `feud.*` and `recruit.*`.
   - **Playwright:** (a) a launch press moment: answer boldly with a Ship promise, see it on the Promises panel, keep it and see the brand note; (b) break a no-layoffs promise and see the reminder event and morale; (c) a rival CEO's jab, a bold answer naming them, and the feud on the Rival screen; (d) Replace a poached engineer with a recruiter on staff.
   - **No new xfails;** report and stop on any guard that fails against `main` and that M14b's keys can't fix.
   - Close-out: CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] Both §29.8 worked examples pass as tests.
- [ ] Promises are judged on displayed values only; no hidden value reaches the API or a prompt (differential and hidden-value tests).
- [ ] §29.7 targets 2–5 met (printed, values recorded); target 1 holds.
- [ ] `make check` green; `make e2e` passes; merged first in the pair through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m14b-done`.

## Manual check (Reece, after merge)

On `pt-ipo`, launch a product and promise to ship the next one in six months, boldly naming a rival. Watch the rival CEO answer, the feud build and the promise come due. Then lose an engineer to poaching and use Replace.

## Decisions made

1. **Press moments are `press` events with engine tones.** Ten templates in `data/events/press.yaml`, one per trigger plus the reminder, queued by id under a new scheduled trigger `press`; each choice carries a valueless `press_step` effect (measured, bold, deflect). Measured is the first choice (what Holiday and scripts take). The LLM may write a press event's title and body; its choices are always the template's (as M13's `public` events). No `events.trigger` entry was needed: press moments are engine-queued, never drawn.
2. **The promise is a separate action in the moment's month** (`make_promise`, energy `promise.energy` 2): templates allow three choices (16.3), so the tone is the event's choice and the promise is made on the press item after a bold or measured answer, one promise a moment.
3. **The cap:** at most `press.max_per_quarter` (2) a quarter and one a month (so each event finds its moment), highest stakes first in 29.1's order (breach, outage, layoffs, earnings, era, launch, acquisition, jab, rivalry); the rest are skipped. Reminders sit outside the cap and wait for a free month.
4. **Effects as modifiers:** brand effects are company-wide `brand_target` modifiers in percent (bold +3 % × a × credibility factor for 6 months, measured +1 %, kept +4 % × a × (1 + ambition) × factor for 12 months, broken −8 % × a for 12 months), created directly rather than through the event caps.
5. **Backfire:** a bold claim about a product backfires once in 6 months if that product's displayed market share falls below its share at the claim, or (listed) the next report is a miss.
6. **Judging on displayed values:** quality is judged as the screens show it (rounded), prices and research leads likewise (`press/shares.py`). A Beat promise compares the two products' displayed quality at the deadline; Ship is kept when the product goes live in time; Research when the displayed lead reaches the level or the company causes an era; No layoffs breaks on any firing; No price rise when a displayed price goes above its level at the promise.
7. **Ambition:** Ship by months (3 months 1.0 to 18 months 0); Beat and Research half the target's distance (over `promise.beat_span` / `research_span`, 20 points) and half the deadline; no-layoffs and no-price-rise 0.2.
8. **Reminders** come 1–3 months after a break, drawn on stream `press` (key (company_id,), one generator a month, in promise order); a break by an action between turns waits the shortest time.
9. **Credibility** lives per company with its last five causes; drift is not listed as a cause. Its hiring appeal is added to the offer score's pitch term at both call sites. **The market's weight on guidance:** once listed, the expectation a report is judged against is credibility/100 × the player's guidance + the rest × the trend consensus (only for guidance the player set).
10. **Layoffs:** firings in a month are counted on the company's credibility record (ended employments leave the live state between actions); 10% of the staff at the month's first firing raises the moment.
11. **Rival CEOs:** chosen on demand (the startup's first exec-level key person, else the highest true leadership among key people), so succession is automatic. Statements: a rival speaks at its own launch, price cut or segment entry with chance `press.statement_chance`; when the player sells in that segment it is a jab with chance `jab_base + jab_feud × feud/100`, which raises a `jab` moment naming it. Aggressive rivals answer a bold claim that names them. Voices are four short lines per personality in code, not data.
12. **Feud sources:** bold mention +20 (29.4 says 10; tuned for 29.7 target 4); a player launch into a segment a rival sells in +8 per rival; a poach either way +15 (detected from the month's ended and started employments); M14 adds hostile bids through `rivals.characters.add_feud`. Decay 1 a month (29.4 says 2; tuned for target 4). Rivalry (≥ 50) multiplies a rival's weights for actions on its products in segments where the player sells, and for poaching, by 1.5; crossing 50 raises a `rivalry` press moment (the storyline event).
13. **Replace:** offered for a resignation serving notice or a resignation or poach of the last 3 months (`recruit.replace_window`), with a recruiter (the role) on staff. It opens a recruiter-owned plan for one hire at the leaver's role and level, in their unit, at `recruit.replace_ratio_bp` of the ask, and its search at once. Its time saving: the recruiter screens the batch and offers in phase 12 of the month it arrives, so the hire lands a month sooner (one month of the normal two, `normal_months` × `replace_speed` rounded). Departures are kept in a small `departure` table for this.
14. **Search by interest:** the fee is charged when the search opens; candidates are drawn from a pool `recruit.interest_pool` (4) times larger and only those with the interest are kept; their profile (interests and work style) shows at once.
15. **Leadership fit:** a weighted mean (leadership 0.35, mentoring 0.25, communication 0.25, temperament 0.15) of the observer's revealed ranges' ends, mapped to 1–5 stars and rounded; never the true values.
16. **Persistence:** migration `0033_press`; the new search and plan fields live in side tables (`search_interest`, `hiring_plan_detail`), because migration 0013 loads state through the current models and new columns on `search` or `hiring_plan` would break older saves (as M8 and M9 did).
17. **The `press.queue_moment(state, company_id, trigger, facts)` hook** takes the trigger `acquisition` (already in the stakes order); `facts` may carry `product_id`, `rival_id`, `segment` and displayed words.
18. **M10's covenant guard (20.5 target 3, band 20–60%) is a known miss** (product manager's ruling, 2026-11-04): blitz_debt seeds that breach a covenant read `main` 60% (6/10) on seeds 1–10 and 70% (21/30) on seeds 11–40; M14b 70% (7/10) on seeds 1–10 and 70% (21/30) on seeds 11–40. The miss is pre-existing (60% on seeds 1–10 was luck). It is entry `M10.T3` in `backend/tst/balance/known_misses.py`, owner M15, failing at 90% or more (M10's original measured value); the guard xfails while known. Recorded in docs/balance-targets.md (M14b and Known misses).

## Follow-ups

- M15: bring the covenant guard (known miss `M10.T3`) back into 20–60%.
- Promises of a broken kind beyond the five (a price cut, a region launch) and private promises stay out (Reece).
- Interest edits on an existing plan (`HiringPlanPatchIn` has no interest); the plan table could mark Replace plans.
- Rival statements are recorded for every rival, but reach the inbox only for markets the player sells in, plus jabs and answers; a per-rival mute could follow.
- Leadership fit uses the observer's revealed ranges; a fit history (how it narrowed) could show on the profile.

