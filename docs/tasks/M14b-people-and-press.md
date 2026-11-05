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

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
