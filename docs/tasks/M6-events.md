# M6: Events, storylines and relationships

**Goal:** the company has a story. Each month the engine picks one to three events from what is actually happening (an unhappy star, a price war, a short runway, two people who can't stand each other), writes them with the LLM inside strict limits or from templates offline, and lets the player choose; some grow into multi-month storylines; people have relationships that move morale; and the month reads like a company, with headlines and board minutes. One milestone: rules, LLM pipeline, API, CLI and screens.

**Spec sections:** §5, §12, §20 · **ADRs:** 0002, 0005 (budget §6), 0006 (amended: no weekly sub-turns), 0011 (tone), 0012, 0014 · **Formulas:** `docs/formulas.md` §16 (all) and its §9 and §12 rows · **Wireframes:** `docs/wireframes.md` (M6 screens) and `docs/wireframes/source/Event.dc.html`, `Settings.dc.html` · **Depends on:** M5 (`m5-done`)

## Context

ADR-0005 is the contract: the director decides when, about whom, how severe and which effects are allowed; the LLM only writes the words and attaches allowed effects; the validator clamps everything; templates are the offline mode and the fallback. LLM calls happen outside the sim after the turn commits, and every event is stored, so replay never calls the LLM. Reece set the budget at $10 a calendar month.

## Out of scope

Weekly crisis sub-turns (v2, ADR-0006 amended), "Ask my COO" (M7), the History screen (M7), events about v2 or v3 systems, voice or images.

## Sub-tasks (commit after each)

1. **Data and formula tests:** every §12 M6 key; the trigger table (§16.2) and effect caps (§16.3) as data; every §16.11 worked example as a unit test.
2. **Relationships** (§16.7): pairs, starting values, drift, tag pushes, `W_rel` in morale, the §13.6 change; property tests (relationships stay in [−100, 100]; pairs exist only for unit-mates and manager links). Migration; data dictionary.
3. **Director** (§16.1, §16.2): triggers from state, candidate weights, cooldowns, severity, critical spacing, stream `events` (id 6), `EventRequest`s from phase 12.
4. **Templates** (§16.4): about 60 in `backend/data/events/*.yaml`, validated at load (every trigger covered, every critical trigger has a critical template, placeholders resolvable, effects within caps); the 5 storylines (§16.6).
5. **Event service and validator** (§16.3, §16.5): the post-commit service, `TemplateAdapter`, `MockLLMAdapter` (deterministic, used by every test), `AnthropicAdapter` (structured output, models and prices from settings, budget meter and fallback, `llm_call_log`), the context builder with its allowlist, the validator with clamps and one retry; the hidden-value prompt test.
6. **Choices and critical events:** the `choose_event` action (energy 0) applying effects, auto-resolution of minor and major events at Continue, Continue blocked by an open critical event (the API returns the blocking event), follow-ups.
7. **Other LLM text** (§16.8): headlines in Market news, board minutes, exit-interview lines, each with templates.
8. **API, CLI and screens:** events with choices and effect words (§16.9), storylines, relationship labels on profiles and in the org unit panel, the LLM meter and settings; `tst events`, `tst choose --event --choice`, `tst storylines`; the event card in the inbox, the critical event modal, the profile's relationships panel, the Settings screen per the wireframes, and an **Event** inbox kind badge.
9. **Golden, balance and e2e:** golden snapshots with `MockLLMAdapter` (CHANGELOG note); the §16.10 balance table, tuning only `events.*` and `relationships.*` keys; Playwright: (a) answer an event and see its effect; (b) a scripted critical event blocks Continue until answered; (c) switch to offline mode in Settings and receive a template event.

## Acceptance criteria

- [ ] Every §16.11 worked example passes as a test.
- [ ] The director's events follow the state (a scripted low-morale star, price war and short runway each produce their events) and respect every cooldown.
- [ ] No LLM draft can apply an effect outside the catalog, a target outside the eligible list, or a value beyond its cap (property test over random drafts).
- [ ] No prompt contains a hidden value (planted-value test).
- [ ] With the budget at $0 or no API key, the game plays fully on templates; the meter and fallback work at the limit.
- [ ] Critical events block Continue until answered; follow-ups arrive the next month.
- [ ] Relationships move morale through `W_rel`; a credit-taker's unit-mates settle near the §16.11 value.
- [ ] Replay reproduces a save with events, choices and a storyline without calling any adapter.
- [ ] §16.10 balance targets met (printed, values recorded).
- [ ] `make check` green; `make e2e` passes all flows; merged and tagged `m6-done` per CLAUDE.md §6.

## Manual check (Reece, after merge)

Put your `ANTHROPIC_API_KEY` in `backend/.env`, play 24 months, and note: do events feel like they come from your company's situation, are choices interesting, does any event feel unfair, and how much of the $10 did it use (the meter shows it).

## Decisions made

_(Agent fills in.)_

## Follow-ups

_(Agent fills in.)_
