# Ideas backlog

**Status: living list (started 2026-11-03).** Features beyond the v2 roadmap and the v3 outline. Reece's verdicts are recorded per idea. An idea moves into a brief only when it is scheduled. Until then it is not built, not even as a stub (CLAUDE.md §3).

Placement key: **v2** = a v2 milestone before the v2 retrospective; **v3** = alongside a v3 milestone; **v4** = after v3.

## Football Manager: people and drama

| Idea | What it adds | Reece | Placement |
| --- | --- | --- | --- |
| **Press, media and public promises** | Short interviews at launches, earnings calls and crises. Your tone moves brand, share price and morale. You can make **public promises** ("we ship a frontier model by Q3", "our chip beats NVIDIA's next year", "no layoffs this year"). The engine tracks each one: keeping it builds brand and analyst credibility; breaking it costs brand, the share price and staff trust, and rivals and the press remind everyone. Promises are the press system's stakes, not a separate system. | **Yes** (2026-11-03) | **M14b** (scheduled 2026-11-05) |
| One-on-ones and private promises | Raises, promotions and projects promised to individuals | **Not needed** (2026-11-03) | dropped |
| Mentoring | Senior and junior pairs; skills and personality rub off, bad habits included | Yes | v2 people-and-press milestone, or v4 |
| Recruiter replaces a poached person | A recruiter on staff can be asked to find a replacement (playtest 2) | Yes | **M14b** (scheduled) |
| Candidate search by interest | Filter recruitment by interests, at extra cost (playtest 2) | Yes | **M14b** (scheduled) |
| Leadership fit in the org chart | Show who would make a good team lead or manager, from revealed traits (playtest 2) | Yes | **M14b** (scheduled) |
| Rival founders as characters | Named rival CEOs with personalities, grudges and public feuds; LLM-written storylines through the event director (ADR-0005) | Yes | **M14b** (scheduled) |
| Industry rankings | Yearly Fortune 500, Best Places to Work and Most Innovative lists; goals to chase; rankings affect hiring and brand | Yes | **M15b** (scheduled) |

## Capitalism Lab: economic depth

| Idea | What it adds | Reece | Placement |
| --- | --- | --- | --- |
| **Antitrust and regulation** | A dominant share in a market triggers investigations: fines, conduct remedies, forced divestitures, blocked acquisitions. The late-game brake on a conglomerate | Yes | M14 (blocked deals) and M22 (regulators by bloc) |
| **Patents and IP litigation** | Research produces patents; license them, sue infringers, defend against trolls; settlements and injunctions | Yes | M15 or early v3 (extends M11's licensing) |
| Platforms and network effects | App stores, developer ecosystems, lock-in: your devices sell better with your software, and the reverse (out of scope in M12b) | Yes | v3 or v4 |
| Owning real estate | Buy headquarters and campuses instead of leasing; a property asset with market risk | Yes | v4 |
| Government contracts and lobbying | Defence and sovereign cloud deals; influence spending with scandal risk | Yes | M22 (geopolitics) |

## Replay value

| Idea | What it adds | Reece | Placement |
| --- | --- | --- | --- |
| **Historical scenarios** | Short challenges with goals: "found an AI lab in 2015", "survive the 2022 rate shock", "turn around a failing chipmaker". Built on the history-then-seeded systems (macro, supply, eras) | Yes | **M15b** (scheduled) |
| Career mode | The founder ages, retires or is pushed out; continue as a successor, or start again at a new company | Yes | v4 |
| Achievements and a legacy score | Built on M15's company score | Yes | **M25** (scheduled) |

## Quality of life

| Idea | What it adds | Reece | Placement |
| --- | --- | --- | --- |
| Chief-of-staff advisor | Ask "why did churn rise?" and get an answer from the engine's driver breakdowns, worded by the LLM (it explains, never decides; ADR-0005) | Yes | **M25** (scheduled) |
| Skip to the next decision | Time runs until something needs you; for the long late game | Yes | **M15b** (scheduled) |
| In-game data editor | Edit rivals, prices and balance without touching YAML, validated by the loader | Yes | **M25** (scheduled) |

## Carried from milestone follow-ups

Engineering follow-ups stay in their briefs and the roadmap (`docs/v2-roadmap.md`, M15 follow-ups). Only player-facing ideas live here.

## v4 and v5 directions (Reece, 2026-11-07)

Proposed after v3's chain (quartz mines to cloud software) is complete. Not scheduled; the playtests through v3 decide the order (economy or personal story, whichever feels thinner).

| Version | Direction | What it adds | Builds on |
| --- | --- | --- | --- |
| **v4** | **Power, platforms and regulation** | **Power and compute:** regional power markets, power-purchase agreements, owning solar, gas or small nuclear plants for data centres and fabs, grid queues and outages, carbon pricing; energy as the next upstream tier. **Platforms and ecosystems:** app stores, developer ecosystems, network effects and lock-in, open-source strategy, standards wars, platform fees. **Regulation grown up:** antitrust with forced unbundling and gatekeeper rules. | the facility and market-good models (ADR-0020), M12a data centres, M21 fabs, M14 antitrust |
| **v5** | **The founder's dynasty and new industries** | **The founder's life:** personal wealth, a family office, personal stock trading, philanthropy and a foundation, political influence, health and burnout, public reputation, succession to an heir or a professional CEO, then play on as the next generation. **New industries on the chain:** electric vehicles (v3's lithium and chips), robotics (the humanoid-robotics era), satellites and space launch, medical devices, each a category family with its own rivals. | M15b's serial founder, M16's group, v3's minerals and chips |
| across both | **A living world** | Rivals as full player-like groups (holding companies, spin-offs, hostile bids against the player and each other); currencies and hedging across regions; more countries with their own rules; regional recessions and booms. | M14, M16, M22 |

## From playtest 4 (2026-11-07)

- **Data-centre costs by region:** through regional power prices in M17 (power as a market good), then v4's power expansion.
- **The founder as an angel or venture investor** with personal money (M24's account): **M26** (scheduled 2026-11-09); M16 covers corporate venture investing.
