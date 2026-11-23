# v6 outline: Conversations, scenarios and more of the world

**Status: OUTLINE (2026-11-21).** Scope, decisions and rough milestones. Full briefs, formulas and research come milestone by milestone, starting the day v5 closes (`m43-done`).

## What v6 is for

By the end of v5 the game has more industries than any one campaign can use: software, cloud, AI, devices, chips, fabs and equipment, mining and refining, power, platforms, cars, robots, space, medical devices, medicines and defence. What it lacks is **the feeling of being in the room**, **reasons to start again**, and a few remaining industries that tie the world together. v6 adds all three.

## Reece's decision (2026-11-21)

**All three directions:**
- **A, conversations:** you talk to the world, and the engine still decides what is possible.
- **B, scenarios:** other start years, set scenarios, challenges, an editor.
- **C, more of the world:** telecom, financial services, media.

## Principles

- **The LLM proposes, the engine disposes** (CLAUDE.md §2.5) applies more than ever. In every conversation the engine sets the range of possible outcomes (a negotiation's zone of agreement, a board's tolerance, an analyst's facts). The conversation can only move the player's odds **within** that range, with every effect clamped and visible afterwards. The LLM never sees hidden values.
- **Every conversation works without the LLM:** a template mode with structured choices gives the same mechanics, for offline play and for tests (MockLLMAdapter).
- **A player can skip any conversation** and take the engine's default outcome, so conversations add depth without forcing it.

## Rough milestones

| # | Milestone | Direction | Notes |
| --- | --- | --- | --- |
| **M46** | **v6 balance pass one:** the known misses handed to "v6's first balance pass" by M43 (V2, V4, V4.T2, robotics_first's dynasty bankruptcies if still present, and any others M43 records) and M37's 2069 turn time | — | first, alongside M47 |
| **M47** | **Negotiations by conversation:** acquisitions, key hires and retention, supplier and offtake contracts, foundry and government deals, regulator settlements. The engine sets each side's reservation value and priorities (hidden); you negotiate in free text or by suggested replies; the counterpart's personality and your persona shape it; outcomes clamp to the zone of agreement | A | a shared negotiation engine for every deal kind |
| **M48** | **Board meetings, earnings calls and investor days:** a quarterly board meeting you attend (agenda, directors with personalities and confidence, votes); earnings calls with analysts asking pointed questions from your real numbers, with guidance and its credibility; investor days for big strategy changes | A | builds on §14's board, §25's markets and §29's promises |
| **M49** | **Press conferences, interviews and one-to-ones:** launches and crises answered live (feeding §29's promises and the persona); staff one-to-ones for key people (ambitions, morale, retention, promotions), Football Manager style | A | builds on §29 and the people model |
| **M50** | **Start years:** 2008 (the financial crisis and the App Store), then 2000 (after the dot-com peak), then 1995 (the boom and bust). Each needs history for every system from its start year: markets, rivals at their real values, eras, commodity and power prices, regulation | B | the largest data milestone of v6; may split by year |
| **M51** | **Scenarios and challenges:** set starts (turn around a failing chipmaker in 2012, build an EV maker in 2016, a Chinese foundry under export controls in 2019, and more), each with goals, a time limit and a score; challenge rules (no outside funding, hardware only) | B | uses M50's start years where they exist |
| **M52** | **The editor and sandbox:** edit a starting company, rivals, markets and rules into a custom scenario; sandbox play past 2069 with no score | B | |
| **M53** | **Telecom:** mobile and fixed networks, spectrum auctions, 5G then 6G, towers and fibre as facilities, subsea cables, satellite links (M40), network equipment (Ericsson, Nokia, Huawei under §39's rules) | C | ties devices, space, chips and geopolitics |
| **M54** | **Financial services at scale:** a bank (deposits, loans, capital rules, interest-rate cycles), payments networks, and insurance; the player's fintech products can grow into them; regulators with capital requirements and stress tests; **currencies and hedging** (the backlog's last item) | C | |
| **M55** | **Media and entertainment:** streaming, a games studio and social networks, with content as an asset (hits drawn like trials), talent with egos, and platforms and advertising tying back to M31 | C | |
| **M56** | **The shared core (deferred):** extracting the engine into a library for another game. Not in v6 unless the law firm game starts and outgrows a fork (Reece, 2026-11-22) | engineering | deferred |
| **M58** | **A real executable:** one Windows installer and `.exe` that runs in its own window with nothing else installed (PyInstaller and pywebview approved as build tools), with automatic updates from GitHub releases and a "What's new" note | engineering | early, beside M46 and M47 |
| **M57** | **v6 balance and polish:** strategies for the new industries and start years, conversation outcomes within bands, review and playtest fixes | — | closes v6 |

Expect review-fix milestones (Codex reviews 10 and later) and a playtest milestone, as in earlier versions. **Rough size:** 12 milestones in four or five rounds of three lanes.

## Reece's answers (2026-11-22)

The defaults below, except question 5: the shared core is **deferred**. Also: M58, a real executable with automatic updates, early in v6.

## Questions (with the product manager's defaults)

1. **How you talk:** type freely, or choose from suggested replies? *Default: both. Free text, with three suggested replies you can pick or edit.*
2. **LLM cost:** conversations use the Anthropic API. *Default: a monthly spend cap in Settings (for example $10), after which conversations fall back to template mode for the rest of the month.*
3. **Start years:** which first? *Default: 2008 first (only two years of history to add), then 2000, then 1995.*
4. **New industries' order:** *Default: telecom first (it ties space, devices and chips together), then financial services, then media.*
5. **The shared core:** inside v6 (M56), or only if another game is actually started? *Default: inside v6, after the conversation milestones, because it also tidies this game's architecture.*
6. **Conversation difficulty:** can a bad negotiation lose a deal the engine would otherwise have made? *Default: yes, within the zone. A good conversation gets you up to the counterpart's best terms; a poor one can push them to walk away. Skipping gives the median outcome.*
