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

- **Regional price bug (1).** The engine stored and charged the regional price; it did not show on the product. The product response gains `regional_prices` (shown under the product's Segments as "Prices in other regions"), and the Regions price dialog now reads the region's current row (it kept the copy it opened with, so a set price looked lost) and says "now $39".
- **Blocking (2).** `advance_turn(block_major=True)` refuses open major and critical events with a 409 `events_open` listing them; only the player's Continue (the API's `/advance`) passes it. Holiday refuses to start with one open and, during its months, answers a major event below its stop level with the first choice, as before; scripts, the CLI's `advance` and tests that call `run_turn` keep that behaviour. `EventsOut.blocking_event_ids` drives the top bar's "Answer N events first" (a link to the inbox); a critical event still opens the modal.
- **Inbox (2).** Answered events archive (and are marked read) whether answered by the player or at Continue; at month end read, unbookmarked items `inbox.auto_archive_months` (3) old archive; a star keeps an item (`inbox_item.bookmarked`, migration 0024); starring an archived item brings it back.
- **Modifiers (3).** One effect type `modifier` {target, stat, value_pct, months}; stats and the targets each accepts in `MODIFIER_STATS` (a company target reaches every product, unit and person). Product stats fold into the product team's existing multipliers (brand target into `brand_mult`, quality cap into `qcap_mult`, builder output into `output_mult` and per-unit builder output, seller capacity into a new `seller_mult`, awareness, churn); the morale target adds an `events` term (target x pct); founder energy scales the monthly cap at reset. Several on one stat multiply. A modifier starts in the month chosen (applies that month) and expires at the month end of its last month; expired rows stay in `event_modifier` (migration 0025) for history. The LLM may attach a modifier only for a stat its template's own modifiers use; value and months are clamped (5/10/20%, 6/12/12 months).
- **Numbers (3).** Effects read as numbers ("costs $8,000", "+3 brand for Pipeline", "Priya's morale +5", "−10 founder energy next month", "+5% brand target for Pipeline for 12 months"); caps and trigger strengths stay hidden. An explicit "Do nothing" choice carries `do_nothing: true` and reads "Do nothing: no effect"; a template choice without effects must be one. The energy tooltip lists last month's energy effects and running energy modifiers; the max shown includes the modifier.
- **Template pass (3).** 17 empty choices marked `do_nothing`. Benefit templates with a matching modifier (28): early_domain_name, early_mentor_offer, early_customer_interviews, early_meetup_talk, early_coworking_desk, early_accelerator_invite, early_open_source, early_advisor, launch_press, launch_hacker_news, milestone_case_study, milestone_customers, milestone_user_group, quiet_analyst_call, quiet_award, quiet_meetup, rival_move_trade_show, quiet_tooling, star_conference_talk (its one-off brand lift became a 12-month brand-target modifier: the choice already had three effects), support_backlog, slipping_tech_debt, unhappy_unit_retro, launch_night_outage, rival_price_war, price_war_customers_ask, key_customer_2, poaching_war_2, funding_party (plus early_long_hours' energy cost and slipping_outage's lasting churn on the cost side). `tests/unit/test_m10b_modifiers.py` holds the list.
- **Crises (4).** `key_exit`, `security_breach` and `outage` are checked in phase 12 apart from the drawn triggers, in a fixed order (key exits by person id, then per live product by id a breach draw and an outage draw) on the director's own `events` generator right after its count draw (ADR-0013 allows one call site per stream); the first that holds brings its critical template when no critical event came in the last 6 months, and that month's drawn candidates exclude critical ones. Key people: seat holders, division presidents and the top 10% of staff by current ability; a key exit holds the month they resign or accept a rival. Security coverage is the product team's (builders, sellers, marketers) mean security / 15. `pr_crisis` is a critical storyline step: scheduled steps whose template allows critical become critical when spacing allows (the new `press_scrutiny` storyline). A new valueless effect `retain` (critical only) withdraws a notice and lapses an accepted approach: the counter-offer.
- **Event balance (4).** With the counter-offer first, the key exit's raise kept people and lifted morale on two seeds above 3 points; its first choice is now the handover, and the award's morale modifier is 1% for 3 months. These are template values authored here, not `events.*` keys.
- **Explanations (5), numbers as the player can judge them.** ADR-0007 keeps the team's true output and seller capacity inside (the hidden-field check forbids `output` and `capacity`). The team-strength line and the slipping and capacity notes use the team re-scaled from the displayed ranges' midpoints and noticed tags (`sim/products/estimates.py`), labelled "about ... (est.)"; the field is `estimated_output`. The founder knows themself. The rotting decision itself stays on true output.
- **Roles and structure (5).** Every role has `summary` and `why_hire` (Recruitment, the plan dialog, the profile). The Org structure guide (`GET /org/guide`) composes the existing org and scale-up views (seat effects as estimates).
- **Regions (6).** `markets.foreign_awareness` is 1.0 (self-serve needs no presence; presence still matters for nothing self-serve). A product's marketing split (by revenue unless set; `product_marketing_split`, migration 0026) sets each selling region's self-serve awareness to x (0.7 + 0.3 x min(1, share / revenue share)): full at the default, 70% with none. A home-only product is unchanged, so v1's market replays. A newly live region with no revenue gets 70% until it earns some or the player gives it a share.
- **Former profiles (6).** Job history is rebuilt from the decision log: the candidate's level and the accepted offer's unit at hire, then promotions, moves and appointments; "what they led" lists units led, seats held, products their unit was assigned while they were in it, and storylines they appeared in. Research projects come with M11.
- **Tests that play turns** call the helpers that answer blocking events first, as a player would; the e2e helper answers them through the API before Continue.

- **A moved guard, recorded for M10d.** T5 "blitzscale (standard) bankrupt by the end" reads 0% (band 10-40%; 10% before M10b). The brief says a guard that moves is reported for M10d, not tuned here, so it is an `xfail(strict=False)` with that reason, outside the aggregate check, like T3 and T7 before it. **It needs the product manager's approval**; M10d re-checks every target.
- **Verification at close.** Backend lint, types and the non-nightly suite pass, golden snapshots regenerated (above); front-end lint, types and tests pass; the API is in sync; `make e2e` 49 passed. Nightly guards, alone: as tabled in `docs/balance-targets.md` (M10b): 15 passed, the recorded xfails unchanged, §20.5 target 2 now passes, T5 blitzscale moved. S2 17.8 worker-minutes with the balance runner alone (70 inside the parallel nightly). §23.7 target 1: 1.08 critical events per 18 months with 20+ staff, shortest gap 6.

## Follow-ups

- **T5 blitzscale bankruptcy** moved to 0% (see above): for M10d.
- **Crises in practice are mostly key exits** (45 of 49 critical events in the target-1 run, the other 4 press crises; no breach or outage on the steady script, whose products keep quality up). If Reece wants more breaches and outages, the `events.crisis` chances are the keys.
- **Estimated output:** the team-strength line uses displayed ranges. A team whose skills are barely known reads near the middle of the scale until interviews and time narrow them.
- **The CLI's `advance`** still answers major events with their first choice (headless); a `--strict` flag could block like the API.
- **Regional history** (product_month by region) would let the home-only series cover the whole product (carried from M10r).
- **Research projects** in "what they led" come with M11.
