# Agent playtest, M7c: ten years through the browser

A Playwright agent (`frontend/e2e/playtest/agent.spec.ts`, `make playtest`) played a new game, **Agent Co**, on `ex_big_tech_founders`, standard difficulty, seed 7, for 120 months (January 2010 to December 2019), clicking through the screens at 1440×900. Events and the COO used the mock adapter. The final run took **14.5 minutes**, with **no 5xx responses** and no failed steps. Screenshots of Overview, People, Products and Finance at each year end are in [`agent-m7c/`](agent-m7c/) (40 PNGs, 6.3 MB).

How it played (the brief's "reasonable player"):

- one B2B SaaS product (Pipeline, SMB $40, mid-market $700) built by the whole company;
- hiring through job posts, interviews and offers toward 4 + 2 people a half-year, only while runway was 12 months or more, plus a recruiter plan in June 2010;
- the seed at once, then each later round as soon as it was allowed, taking the best valuation; a bridge when offered; a $1.5M SAFE at the highest cap read as "likely" when runway fell under 9 months;
- marketing at $10,000 or 15% of revenue;
- a second product (Forge, Developer tools, SMB $30) once ARR passed $1M with 12 staff, built by a new Forge team with three engineers moved in;
- events read and answered in rotation (critical ones read for their cash wording, costly choices skipped when runway was short);
- a 4-month Holiday each May from 2012;
- every screen, four screenshots and a COO question at each year end;
- the saves manager once (Aug 2012: duplicate, then restore a backup as a new save).

## The game in numbers

At each December, before Continue:

| Year | Cash | ARR | Staff | Avg morale | Stage | Rounds so far | Products | Events |
|---|---:|---:|---:|---:|---:|---|---|---:|
| 2010 | $710,496 | $68,235 | 8 | 56 | 2 | Seed | Pipeline (live) | 27 |
| 2011 | $1,089,390 | $571,833 | 11 | 62 | 2 | Seed | Pipeline | 30 |
| 2012 | $5,081,843 | $1,061,788 | 13 | 47 | 2 | Seed, A | Pipeline, Forge (in development) | 27 |
| 2013 | $3,901,837 | $1,410,748 | 19 | 54 | 2 | Seed, A | Pipeline, Forge (in development) | 30 |
| 2014 | $2,583,766 | $1,917,931 | 22 | 55 | 2 | Seed, A | Pipeline, Forge (in development) | 30 |
| 2015 | $1,092,159 | $2,808,690 | 26 | 54 | 2 | Seed, A | Pipeline, Forge (in development) | 29 |
| 2016 | $1,839,599 | $4,507,415 | 31 | 52 | 2 | Seed, A | Pipeline, Forge (live) | 34 |
| 2017 | $18,217,443 | $5,897,214 | 34 | 48 | 3 | Seed, A, B | Pipeline, Forge | 32 |
| 2018 | $18,336,400 | $6,942,326 | 37 | 46 | 3 | Seed, A, B | Pipeline, Forge | 28 |
| 2019 | $18,752,679 | $8,647,804 | 39 | 53 | 3 | Seed, A, B | Pipeline, Forge | 34 |

Funding milestones: seed in Feb 2010 at $3.2M post-money (the founder kept 55.19%); angels turned down a $1.5M SAFE at a $5M cap in Nov 2010 and took the same terms in Dec 2010; Series A in Nov 2012 at $13.4M post (founder 20.83%); a $1.5M SAFE at a $20M cap in Sep 2016; Series B in Apr 2017 at $49.4M post (founder 11.96%). Stage 3 from Apr 2017. Profitable by late 2019 (MRR $720,650, runway "Profitable"). Unread inbox at the end: 676.

## Bugs fixed

Each has a regression test that fails on the old code.

| Bug | Fix and test | Commit |
|---|---|---|
| `GET /events/{id}` answered 404 for an answered event older than the live state's 24 months, so History links to old events broke. | Falls back to the stored event row. `tests/integration/test_event_links.py::test_an_old_answered_event_still_opens` | 414104f |
| A company-wide `unhappy_unit` event showed a raw "{unit}" in its title ("{unit} asks for fewer meetings"). | The root unit renders as the company name. `tests/unit/test_m7c_fixes.py` | 9de85a5 |
| The People table still had a placeholder "Form" column reading "From M3". | Column removed. `src/lib/placeholders.test.ts` fails on any ">From M…<" placeholder. | 9de85a5 |
| `GET /saves` returned 500 when SQLite removed a save's `-wal` file between the exists check and `stat`, while another request's turn closed its connection. | File size and last-played read only the files that still exist. `tests/unit/test_m7c_fixes.py::test_save_size_survives_a_vanishing_wal_file` | eb21129 |
| At 1440×900 the People table pushed Status off-screen behind a sideways scroll. | Top skills wrap. Playwright `e2e/m7c.spec.ts` (d) | bd4275c |
| The Overview's Monthly burn left out an event paid by answering it before Continue, so the tile disagreed with its own breakdown and the P&L (Nov 2011: $86,530 shown, cash fell $87,710). | The tile reads the month's whole fall in cash from the ledger. `tests/integration/test_m7c_burn.py` | bc9c31a |
| At 1440×900 the P&L cut off the latest month, the one the player most needs. | Long line labels wrap. Playwright `e2e/m7c.spec.ts` (e) | 2b61495 |
| The burn tile's note "Dec projected $214,140" showed gross costs under a net burn of $96,577 (Dec 2013). | New `month_net_burn_cents` (projected costs less this month's revenue). `tests/integration/test_m7c_burn.py` | 22613cf |
| (Found by `make e2e`, from this milestone's deep links) Opening a message remounted the inbox and lost its Archived filter. | The screen's error boundary ignores the `/inbox/:id` suffix; one inbox route. `e2e/m4c.spec.ts` (c) | 5c4f085 |
| A cap table with SAFEs converted in two rounds (A and B) gave two rows the same React key (console error from 2017 on). | Row ids include the line's position. `src/components/finance.test.tsx` | a914e89 |

The brief's own features also closed two M7b follow-ups: former staff now open a read-only profile (583f0f7), and event links open the event's message with its card (414104f).

## Bugs not fixed, and why

- **History's burn chart uses the snapshot burn**, which starts after the month's actions, so in a month with an event paid before Continue it can differ from the Overview tile. Fixing it means changing the sim snapshot, which regenerates every golden snapshot; the brief allows golden changes only when a fix needs them, and the Overview fix doesn't. Follow-up.
- **Runway and the burn note can disagree in a month with a large one-off cost.** In Dec 2019 the note said "Dec projected $73,248" while Runway said "Profitable". Runway uses only this month's recurring projected costs (formulas.md 14.1, the M1c decision), and the note includes the $227,765 event already paid. Both follow their written rules, so this goes under design notes.
- **SAFE panel: "Your read: Likely" sits above a disabled Raise button** ("the cap is too low: outstanding SAFEs would claim too much of the company", 2012). The read is the angels' appetite and the warning is the company's rule. This is a wording question, not a broken number.
- **In an earlier attempt, the top bar wrapped to two rows at 1440 wide while the insolvency badge showed.** Nothing was hidden, and it didn't come up in the final run.

## Design and balance notes

Ranked by how much they'd affect a player. These are observations only; nothing was built.

1. **The inbox drowns the player.** About 30 events a year (27–34), plus hiring, market and month-end messages. Unread mail went from 69 at the end of 2010 to 130 (2011), 257 (2013), 450 (2016) and 676 (2019). A player who reads everything spends most of a month in the inbox; one who doesn't loses the messages that matter. Information is hard to find.
2. **Holiday rarely survives the mid-game.** The first three holidays ran (3 months stopped by short runway in 2012; then 4 and 4 months). From 2015 every holiday stopped after 1–2 months because "an event needs your answer". With major events this frequent there are no quiet stretches, so years 6–10 feel slow (one Continue, one event, repeat).
3. **Early cash is tight for a modest hirer.** With 8 staff the runway was 7 months by December 2010. The company needed a second SAFE attempt, paused hiring from August to October 2012, and its holiday was stopped by short runway, until Series A, which opens at $1M ARR (reached in late 2012). Survivable, but it felt unforgiving for a sensible strategy.
4. **Event costs are large late on.** G&A spiked to −$208.6k in Mar 2019 and −$286.2k in Nov 2019 (an event of $227,765) against about $650k of revenue a month, turning two months of 2019 into losses. A single event costing a third of a month's revenue may feel unfair.
5. **The seed takes a lot.** The founder kept 55.19% after the seed ($3.2M post), 20.83% after A and 11.96% after B. Reece may want to judge whether 45% for a seed is intended.
6. **Product quality falls with nothing to explain it.** Pipeline reached 100 features by 2011 at "Fast" pace, but quality went from 51 (2011) to 44–45 (2013–2016). The player can't see why or what to do.
7. **A second product is slow to launch with a small team.** Forge, started in Oct 2012 with three engineers moved over, still showed "Not ready: feature score 15 of the 30 needed" in Dec 2013 and launched in 2016. If that's intended, the screen could say how long it will take.
8. **Late-game cash has nowhere to go.** From the Series B, cash sat at about $18M for three years with runway "Profitable". The M8 stage-3 levers (divisions, executives, support staff) exist, but nothing pointed the agent to them. Support coverage read "0 of 3, output −18.8%" in 2019, shown only on an Overview tile.
9. **A flat org has little cost.** All 39 staff reported to the founder ("1 over span · managers stretched" from 2011) and morale stayed between 46 and 62. If span limits are meant to matter, the effect isn't visible.
10. **Many small decisions repeat.** Of the 181 events the agent answered, 50 (28%) were small personal moments that recur for each person: work anniversaries, "asked to speak", "being asked to consult", "online at 2 a.m.", the doctor, "disagrees at the all-hands". Their effects are small (minor events are capped at ±3 morale), so answering them may feel like busywork.
11. **Small UI points.** The "Back from holiday" banner stays on every screen until dismissed, still showing in December after a May holiday. The SAFE block message doesn't say what share the outstanding SAFEs would claim.

## Checklist for Reece's playtest

The ten things most worth your judgment:

1. Inbox volume by year 3: is the 250+ unread pile acceptable, or does it need filtering, auto-archiving or digests?
2. Does Holiday ever feel useful after year 5, or do major events stop it every month?
3. Years 1–3 cash: with a sensible hiring pace, does the game force a SAFE or bridge to survive, and is that the intended feel?
4. Seed dilution (about 45%) and where founder ownership ends after A and B: right for the fantasy?
5. Event cash sizes at $500k+ MRR: should a single event cost $200k+?
6. Product quality drift: can you tell why quality falls and what to do about it?
7. A second product's launch time with a small team: fair, and is the "feature score 15 of 30" line enough guidance?
8. Stage 3: do you notice support coverage and the executive seats without being told? Try `make quickstart-saves`, then open `quick-stage3`.
9. Former employee profiles: from History, the hall of fame and the org, do they show what you'd want to remember?
10. Event deep links: from History, storylines, the COO briefing and "While you were away", does each one land on the right card?

## Running it

```bash
make playtest            # 120 months (about 15 minutes); PLAYTEST_MONTHS=36 for a shorter run
make quickstart-saves    # quick-stage2 and quick-stage3 in saves/
```

The agent writes `frontend/test-results/playtest/journal.json` (each decision, each year's numbers, server and console errors) and failure screenshots next to it. Don't run `make e2e` at the same time in the same checkout: each Playwright run clears `frontend/test-results`. Use `TST_E2E_API_PORT` and `TST_E2E_WEB_PORT` when the default ports are taken.
