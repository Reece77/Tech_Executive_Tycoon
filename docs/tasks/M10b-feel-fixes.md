# M10b: Feel fixes from Reece's playtest

**Goal:** act on Reece's v1 playtest (2026-11-01).
- **Inbox:** stops drowning him.
- **Events:** visibly change things, and crises happen.
- **Explanations:** every warning says what to do.
- **Regions:** a software company sells self-serve abroad without an office.
- **Former staff profiles:** tell the person's story.
- **Bug:** fix regional prices not showing.

**Spec sections:** §12, §13 · **ADRs:** 0005, 0014 · **Formulas:** `docs/formulas.md` §23 (all), with §11.4, §16, §19.5 · **Source:** Reece's Playtest Log (summarized in Context) and `docs/playtests/agent-m7c.md` · **Depends on:** M10r (`m10r-done`)

## Context

Reece played a full v1 run (ex-big-tech founders, standard) and the M8–M10 features on `quick-stage3`. He reported no blocking bug: "It is fun, works well. Needs some fine tuning."

**What he said:**
- **Events:** they feel like they don't change anything ("a perfect domain for sale", but no effect described); critical events never happen; energy effects go unnoticed.
- **Inbox:** answered events should disappear; auto-archive after a quarter unless bookmarked; important items shouldn't let him advance.
- **Product quality:** a product with one engineer kept "slipping" with "nobody is working on it". That's the §11.4 maintenance line (one builder is below `0.25 σ`) with a misleading message.
- **Sales capacity:** "sales capacity limited" warnings don't say what to do.
- **Hiring:** there's no description of what each role does or why to hire it.
- **Regions:** they shouldn't need a local presence for software. Bug: a regional price he set doesn't show anywhere.
- **Org:** explain divisions, teams and structure, and how they help efficiency.
- **Former profiles:** add job history and what they led.

**His decisions:** visible, lasting event effects; major and critical events block Continue (no preference given; the product manager chose this); self-serve needs no presence abroad.

Executive authority is M10c. All tuning is M10d.

## Out of scope

Executive delegation (M10c). Balance tuning beyond `events.*` (M10d). New game systems.

## Sub-tasks (commit after each)

1. **Regional price bug** (first, with a regression test): a price set for a region appears in the product's prices panel and the Regions panel, and is the price charged.
2. **Inbox** (§23.1): answered events auto-archive; bookmark (star); auto-archive after `inbox.auto_archive_months` (3); major and critical events block Continue (409 with the blocking events; the top bar says how many); Holiday unchanged. Tests for each, including Holiday answering a below-threshold major event by default.
3. **Event modifiers and numbers** (§23.2):
   - the `modifier` effect with severity caps, the validator, application each month and expiry;
   - choices shown as numbers (§16.9 replaced); the active-effects panel on Overview, Product and Person; the month-end "Your choices this month" line; energy effects in the energy tooltip;
   - template pass: every choice has an effect or is an explicit "Do nothing", and benefit-story templates carry a matching modifier (list them in Decisions made);
   - **property test:** modifiers never exceed caps and always expire;
   - update `formulas.md` §16.9 with a pointer to §23.2.
4. **Critical events** (§23.3): triggers `key_exit`, `security_breach`, `outage` and `pr_crisis`, with critical templates (offline templates first, LLM allowed). Tests for each trigger; spacing kept.
5. **Explanations** (§23.4):
   - product team strength with the maintains and full-speed lines;
   - the two slipping messages; the sales capacity message with numbers;
   - `roles.yaml` `summary` and `why_hire` for every role, shown in Recruitment, the plan dialog and the profile;
   - the Org structure guide with live numbers;
   - glossary entries for anything new.
6. **Regions** (§23.5): self-serve at full awareness abroad; marketing split by region; the Regions panel's one-line rules.
7. **Former staff profiles** (§23.6): job history and what they led.
8. **Targets, golden snapshots and e2e:**
   - the §23.7 targets printed and recorded;
   - golden snapshots regenerated (modifiers and new triggers change events), with the reason in CHANGELOG;
   - **Playwright:**
     - (a) answer an event, see it archive and its modifier on the active-effects panel;
     - (b) a major event blocks Continue until answered;
     - (c) a one-engineer product shows "team too small" with the maintenance line;
     - (d) set a regional price and see it shown;
   - close-out: CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] The regional price bug is fixed with a regression test.
- [ ] Answered events archive; old items auto-archive unless bookmarked; major and critical events block Continue; Holiday unchanged.
- [ ] Every event choice shows numeric effects; modifiers apply, show on the active-effects panel and expire (property test).
- [ ] The four critical triggers fire as specified; §23.7 target 1 met.
- [ ] Every warning in §23.4 says what to do with numbers; every role has a summary and a reason to hire.
- [ ] Self-serve sells abroad at full awareness; marketing can be split by region.
- [ ] Former profiles show job history and what the person led.
- [ ] `make check` green (recorded xfails unchanged; any newly moved guard reported for M10d); `make e2e` passes; merged per CLAUDE.md §6 with the trailer `Milestone-Tag: m10b-done`.

## Manual check (Reece, after merge)

Play 3 years from a new game. Do events feel like they matter, does the inbox stay manageable, and does every warning tell you what to do?

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
