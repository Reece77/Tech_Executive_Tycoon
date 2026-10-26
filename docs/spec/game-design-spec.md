# Tech Startup Tycoon: Game Design and Technical Specification v1.0

Oct 26, 2026 · Reece DeHaan

> Exported from the Claude Doc of the same name. The Doc is the editable source; re-export after changes. Where this spec and the ADRs differ on technical detail, the ADRs win (see `CLAUDE.md` §1).

## 1. Vision and Pillars

Tech Startup Tycoon is a single-player, turn-based management game in which one founder grows a garage idea into a vertically integrated technology conglomerate, from quartz mines to cloud software. It combines Football Manager's people depth and screen-driven interface with Capitalism Lab's supply chains, product quality math, and corporate structure.

This specification supersedes the v0.2 overview ("Startup & Minerals Management Sim"). All decisions resolved there carry forward: real-world company and commodity names, a monthly turn with severity-triggered weekly crisis windows, agent-based rivals simulated as full entities, the Python/FastAPI/SQLite/React stack, and four scenario starts with four difficulty levels.

**Design pillars**

1. **People are the engine.** Every employee is an individual with stats, personality, interests, and hidden traits. Talent and chemistry decide outcomes as much as capital does.
2. **Structure is a strategy.** The player designs the company: subsidiaries, divisions, departments, teams, and reporting lines, each with real costs and coordination penalties.
3. **Everything is a supply chain.** Software runs on cloud, cloud runs on GPUs, GPUs run on fabs, fabs run on refined minerals. Integration upstream trades capital for control.
4. **The engine owns the truth.** Deterministic, seeded simulation owns all numbers. The LLM writes narrative and proposes bounded effects; it never edits state.
5. **Nothing is lost.** Every turn, decision, and event is persisted, so the company's history becomes the story.
6. **Information over graphics.** Dense tables, panels, and charts. No 3D, no animation.

## 2. Scope and Release Phases

The build ships in three playable phases; each phase must be fun on its own before the next begins.

| Phase | Player fantasy | Systems in scope | Explicitly deferred |
| --- | --- | --- | --- |
| v1 Startup | Solo founder to Series B software company | Founder, hiring, people sim, departments, 4 software product categories, customers, seed to Series B funding, template and LLM events, 8 rival companies | Hardware, chips, mining, IPO, subsidiaries |
| v2 Scale-up | Multi-division tech company, public markets | Divisions, cloud and GPU infrastructure, hardware and devices, R&D tech tree, IPO and stock market, M&A of rivals, debt, macro cycles | Fabs, mining |
| v3 Conglomerate | Vertically integrated empire | Holding company and subsidiaries, fabless then fab, wafers and refining, prospecting and mining, offtake contracts, geopolitics and export controls | None planned |

**In scope throughout:** single player, local only, one save per database file, keyboard and mouse UI, LLM optional with template fallback.

**Out of scope:** multiplayer, monetization, mobile, real-time play, real market data feeds, 3D or animated graphics, modding tools (v1).

## 3. Player Journey and Company Stages

The company advances through six stages; each stage is gated by measurable thresholds and unlocks new screens, actions, and risks. Thresholds below are starting values for tuning.

| Stage | Typical size | Gate to enter | Unlocks | New pressures |
| --- | --- | --- | --- | --- |
| 0. Solo founder | 1 person | Game start | Founder skills, first product concept, side income, friends-and-family money | Personal savings runway, founder burnout |
| 1. Garage startup | 2 to 10 | First hire or co-founder | Hiring, equity grants, pre-seed and seed, first customers | Co-founder conflict, product-market fit |
| 2. Venture-backed | 10 to 75 | Seed closed or $1M ARR | Departments, managers, Series A and B, board seats, office leases | Board pressure, burn rate, poaching |
| 3. Scale-up | 75 to 500 | Series B or $20M ARR | Divisions, executive team, second product line, infrastructure ownership, debt | Coordination cost, culture drift, rival response |
| 4. Public company | 500 to 10,000 | IPO completed | Stock market, buybacks, acquisitions, R&D labs, hardware, fabless chips | Quarterly earnings, activist investors, analyst sentiment |
| 5. Conglomerate | 10,000+ | Two or more subsidiaries | Holding company, fabs, refining, mining, sovereign deals | Regulation, antitrust, geopolitics, capital intensity |

The founder is always the player character. The player can later appoint a CEO and step up to Chair, which changes which decisions are hands-on versus delegated.

## 4. Core Loop and Time Model

The base turn is one month; a critical event opens a weekly crisis window of up to four sub-turns, then play returns to monthly.

**Turn sequence (engine order is fixed and tested):**

1. **Inbox and review.** Player reads events, reports from department heads, scouting reports, and market news.
2. **Decisions.** Hire, fire, promote, restructure, set budgets and prices, assign people to projects, start R&D, raise or borrow, bid on deals.
3. **Advance.** The engine resolves, in order: rival decisions, R&D progress, production and capacity, sales and churn, payroll and costs, financing, people updates (morale, growth, aging, relationships), market and commodity prices, stage checks.
4. **Events.** The event director selects one to three events from state triggers; the LLM writes them, the engine validates them.
5. **Month-end report.** P&L, KPI deltas, and a short narrative recap are written to the history log.

**Actions between turns (ADR-0014):** decisions are immediate actions applied the moment the player confirms them (interview, scout, offer, fire, reorganize, raise). Each costs founder energy (100 a month, reset at month end). An offer needs an interview first (ADR-0016), and offers are answered when the player presses Continue. From M2, staff delegates take the same actions on the player's behalf in the advance step, with their own energy (ADR-0015).

**Time-scale controls:** "Continue" advances one turn; "Holiday" auto-advances until an event above a chosen severity occurs, with delegated staff making routine decisions using their own attributes.

**Severity tiers:** Minor (resolved in inbox), Major (requires a decision this turn), Critical (opens a crisis window: production outage, funding crunch, key executive exit, security breach, export ban).

**Win and loss:** Loss on insolvency without financing, or board removal; Ironman disables reloads. Scenario goals (for example reach IPO in 10 years) and an open Sandbox with a company score.

## 5. People System

Every person, including the founder and every rival employee, uses one model: visible skills on a 1 to 20 scale, a personality profile, interests, hidden traits revealed over time, and dynamic state that changes each turn.

### 5.1 Attribute model

| Group | Attributes | Visibility |
| --- | --- | --- |
| Technical skills (1 to 20) | Software engineering, ML research, data, infrastructure, hardware design, chip design, manufacturing, geology, mining engineering, security | Visible, fuzzed by scout quality |
| Business skills (1 to 20) | Product, design, sales, marketing, finance, legal, operations, procurement, recruiting | Visible, fuzzed |
| Leadership skills (1 to 20) | Leadership, mentoring, strategy, negotiation, communication, judgment of talent | Visible, fuzzed |
| Personality (1 to 20) | Ambition, loyalty, professionalism, temperament, adaptability, risk appetite, ego, integrity, sociability | Revealed as ranges |
| Interests | 2 to 4 tags from a fixed list (AI, hardware, crypto, climate, security, gaming, mining, policy, design) plus a preferred work style (builder, operator, researcher, seller) | Visible after interview |
| Hidden traits | Potential (current and ceiling), consistency, injury-proneness equivalent (burnout risk), important-moments performance, poachability | Never shown exactly |
| Behavior tags | Mentor, Quiet Genius, Credit-Taker, Politician, Maverick, Perfectionist, Job-Hopper, Culture Carrier, Toxic High Performer | Revealed by events |
| Dynamic state | Morale, stress, energy, performance form (last 6 turns), satisfaction with pay, role, manager, and mission | Visible |

### 5.2 How people change

- **Growth:** skills grow toward potential based on age, mentoring quality, project difficulty, and professionalism; growth slows after 45 and some skills decay.
- **Interest fit:** assignments that match interests add morale and growth; mismatches drain both over time.
- **Relationships:** pairwise affinity from -100 to +100 drives team chemistry, cliques, and conflict events.
- **Retention:** a monthly flight-risk score combines pay vs market, morale, manager rating, equity vesting cliff, and rival offers.
- **Life events:** promotions, burnout, family leave, sabbaticals, poaching approaches, and resignations, generated by the event engine.

**As built (M1–M2):** monthly growth noise is multiplicative, so skills drift with their growth rate rather than random-walking; the person's manager multiplies growth through mentoring and span of control (`docs/formulas.md` §13.5). Displayed ranges are derived from a stored half-width and center offset per observer company. Relationships arrive with events in M6.

### 5.3 Founder

The founder is built at game start with a point budget and a background (engineer, salesperson, academic, ex-big-tech, geologist). Founder energy is a scarce monthly resource spent on hands-on actions; delegation frees energy but depends on lieutenants' quality. The founder is outside payroll, morale, resignation, retirement and firing until the board arrives in M4; their tags are known to their own company, and the company mission defaults to the founder's interests.

### 5.4 Hiring

Candidate pools are generated per role and region with salary expectations tied to market rates. Recruiters and scouts with higher "judgment of talent" narrow attribute ranges faster. Channels: network, job post, recruiter, acqui-hire, poaching from rivals, university pipeline (v1 builds network, job post and recruiter). A search produces a batch of candidates who stay available for a few months; the company must interview a candidate before making an offer; a candidate with a pending offer does not expire until it is answered, and withdrawing an offer keeps the candidate in the pool. Offers may include equity from an option pool (`docs/formulas.md` §7); a hire's interests are revealed on joining. From M2, a hiring plan lets a staff delegate search, interview and make offers each month.

## 6. Corporate Structure

The player builds the org as a tree of five unit levels, and every unit has a leader, a budget, a headcount, a P&L or cost-center role, and policies.

| Level | Example | Unlocked at | Has its own |
| --- | --- | --- | --- |
| Holding company | DeHaan Holdings | Stage 5 | Board, treasury, cap table, capital allocation |
| Subsidiary | Quarry Minerals Inc. | Stage 5 | Legal entity, separate books, minority investors, can be spun off or sold |
| Division | Cloud Division, Devices Division | Stage 3 | P&L, president, shared-service charges |
| Department | Engineering, Sales, Finance, Exploration | Stage 2 | Cost center, head, hiring plan |
| Team | Inference Platform Team | Stage 1 | Lead, members, assigned project |

**Structure mechanics**

- **Span of control:** managers above 8 direct reports (tuned by leadership skill) lose effectiveness; layers add latency to decisions.
- **Coordination cost:** each layer and cross-division dependency adds overhead and a small productivity tax, so reorganizing is a real trade-off.
- **Shared services:** HR, legal, finance, and IT can be centralized (cheaper, slower) or embedded (faster, costlier).
- **Policies per unit:** remote vs office, pay band position (percentile vs market), equity generosity, performance review cadence, crunch tolerance, R&D share of budget.
- **Executive roles:** CEO, COO, CFO, CTO, CPO, CMO, CRO, General Counsel, Chief Scientist, Head of Exploration. Vacant seats impose specific penalties; strong executives grant bonuses to their function.
- **Culture:** each unit has culture values (speed, quality, frugality, collaboration) that drift toward the dominant personalities in it and affect fit for new hires.
- **Reorgs, spin-offs, and mergers** are player actions with morale and attrition costs, generated as events.

**Built in M2 (`docs/formulas.md` §13):** a company root led by the founder, departments (from 10 staff or stage 2) and teams. A person's manager is their unit's leader; span of control is `5 + floor(leadership / 4)`, and manager quality moves morale (±8) and growth. Reorganizing, raises (+3 for 5% or more, once a year), pay cuts (−10) and promotions (+5) change morale once. Units choose office or remote work. Coordination cost, decision latency, shared services, executive seats and unit culture wait for products (M3) or v2.

## 7. Products, R&D, and Technology Tree

Products are rated the Capitalism Lab way: each has quality, price, brand, and features scores that combine into a customer appeal score per segment, and appeal versus rivals sets market share.

### 7.1 Product categories

| Category | Examples | Revenue model | Key inputs | Phase |
| --- | --- | --- | --- | --- |
| B2B SaaS | CRM, HR, analytics | Subscription | Engineers, sales | v1 |
| Developer tools and APIs | CI, observability, databases | Usage-based | Engineers, compute | v1 |
| Consumer apps | Social, productivity, games | Ads, subscription | Product, marketing | v1 |
| Cybersecurity | Endpoint, identity, cloud security | Subscription, contracts | Security researchers | v1 |
| Fintech | Payments, lending, banking-as-a-service | Fees, interest | Compliance, engineering | v2 |
| AI models and inference | Foundation models, inference APIs | Usage, licensing | GPUs, ML researchers | v2 |
| Cloud and GPU hosting | IaaS, GPU cloud | Compute rental | Data centers, power, GPUs | v2 |
| Hardware and devices | Phones, laptops, servers, networking | Unit sales | Components, contract manufacturing | v2 |
| Fabless chips | GPUs, AI accelerators, CPUs | Unit sales, licensing | Chip designers, foundry slots | v2 |
| Semiconductor manufacturing | Foundry services | Wafer sales | Fabs, wafers, process engineers | v3 |
| Materials and mining | Quartz, silicon metal, gallium, copper, rare earths | Commodity sales, offtake | Deposits, geologists | v3 |

### 7.2 Product lifecycle

Concept, prototype, beta, launch, growth, maturity, sunset. Each stage needs assigned teams; quality comes from team skill, tech level, and time; bugs and tech debt accumulate when teams crunch.

### 7.3 Technology tree

- Each technology has a level (1 to 100) per domain: software platform, AI, infrastructure, chip design, process node, materials science, extraction.
- R&D projects spend researcher-months and money to raise a level; higher levels raise the quality ceiling of dependent products.
- Technologies can be licensed in or out, acquired through M&A, or leaked through poaching.
- Rivals research too, so tech leadership decays without continued spend.
- Breakthroughs and dead ends are rolled events, weighted by research team quality.

**Built in M3 (`docs/formulas.md` §11):** four categories (B2B SaaS, developer tools, consumer apps, cybersecurity) with consumer, SMB, mid-market and enterprise segments. Org units are assigned to products; their builders raise quality toward a cap set by their skill and add features against a rising market expectation; sellers give mid-market and enterprise sales capacity; marketers and budget build brand. Lifecycle in v1: in development, live, sunset (launch at quality 25 and feature score 30). The technology tree, beta stage and tech debt wait for v2.

## 8. Value Chain and Production

The economy is one connected chain of seven tiers, and every tier can be bought from the market, contracted, or owned by the player.

Tiers, from raw materials to the customer: **Mining** (quartz, gallium, copper, rare earths; v3) → **Refining** (silicon metal, polysilicon; v3) → **Wafers** (ingots and wafers; v3) → **Chips** (design, fab, packaging; v2 to v3) → **Hardware** (servers, devices; v2) → **Cloud** (data centers, GPU cloud; v2) → **Software** (SaaS, apps, AI models; v1 start).

The player starts at the software end in v1 and integrates leftward toward raw materials in later phases.

Each tier is modeled as a set of **facilities** (mine, refinery, wafer plant, fab, assembly plant, data center, software team) built from Capitalism Lab-style **units**: purchasing, production, R&D, sales, and logistics. A facility has capacity, utilization, input requirements, output quality, operating cost, and staff.

**Sourcing choices at each tier**

- **Spot market:** flexible, exposed to price shocks and allocation shortfalls.
- **Contract:** fixed volume and price for a term; counterparty risk and take-or-pay penalties.
- **Own it:** capital-intensive and slow to build, but gives cost control, quality control, and supply security.

**Integration payoffs:** owning an upstream tier removes its margin from your costs, guarantees allocation during shortages, and lets you deny supply to rivals. Downsides are capital lock-up, utilization risk, and management attention (a coordination cost on the holding company).

**Starting simplifications:** v1 treats cloud compute as a priced input only. v2 adds owned data centers and GPU procurement. v3 adds the upstream tiers.

## 9. Markets, Customers, and Rivals

Demand is segmented, and market share is split each turn by relative appeal among the player and simulated rivals.

**Customer segments:** consumers, SMB, mid-market, enterprise, government, and hyperscalers (for infrastructure and chips). Each has price sensitivity, quality sensitivity, brand loyalty, sales-cycle length, and churn.

**Regions:** North America, Europe, East Asia, South and Southeast Asia, Latin America, Africa, Oceania. Regions differ in demand, wages, regulation, tax, and political risk.

**Share formula (per segment, per product category):** appeal = weighted sum of quality, price, brand, features, and distribution reach; share = appeal raised to a competitiveness exponent, normalized across all competitors, then smoothed by switching costs.

**Rivals (agent-based, full entities)**

- 8 to 12 active rivals, seeded with real-world names (for example Microsoft, Salesforce, NVIDIA, AMD, TSMC, Intel, Apple, Freeport-McMoRan) plus generated startups that appear and die over time.
- Each rival runs on the same engine rules as the player: cash, staff, products, tech levels, facilities.
- Rival AI uses a personality (aggressive, fast-follower, premium, cost leader, acquirer) and utility scoring over a fixed action set: price change, launch, R&D, hire, poach, raise, acquire, expand capacity.
- Rivals do not call the LLM; their decisions are logged so events can reference them.
- Real-company starting stats are approximate and fictionalized after turn one; personal use only.

**Macro layer:** interest rates, venture funding climate, AI compute demand cycle, consumer confidence, and a geopolitics index that affects export controls and regional risk.

**Built in M3:** one global market per category and segment (regions later). Each month churned and newly adopting customers are in play; products win them by appeal cubed against a no-purchase option, limited by awareness in self-serve segments and by sales capacity in sales-led ones. Until rival AI arrives in M5, the competitors are 2010 incumbents (Salesforce, Oracle, Zoho, Atlassian, Microsoft, GitHub, Facebook, Zynga, Evernote, Symantec, McAfee, Check Point) with fixed scores (ADR-0017).

## 10. Finance and Capital Markets

The finance model keeps real double-entry books, so the P&L, balance sheet, cash flow statement, and cap table always reconcile.

**Until M4:** cash may go negative without ending the game, and runway is reported at this month's projected costs. M4 adds financing, statements and the bankruptcy rule.

| Instrument | Available from | Mechanics |
| --- | --- | --- |
| Founder savings, friends and family | Stage 0 | Small, cheap, personal relationship risk |
| SAFEs and convertible notes | Stage 1 | Valuation cap, discount, converts at next priced round |
| Priced rounds (seed to Series D+) | Stage 1 to 3 | Investor firms with personalities; terms include valuation, liquidation preference, board seats, pro rata, protective provisions |
| Venture debt and bank loans | Stage 2 | Covenants tied to cash and revenue; breach triggers events |
| Employee option pool | Stage 1 | Vesting, cliffs, refresh grants; drives retention |
| IPO and follow-on offerings | Stage 4 | Bankers, roadshow event chain, pricing based on growth, margins, and market sentiment |
| Public stock | Stage 4 | Share price from fundamentals plus sentiment; analysts, guidance, earnings beats and misses, buybacks, dividends |
| M&A | Stage 3 | Acquire rivals or startups for cash or stock; integration risk, culture clash, key-talent flight |
| Project finance and offtake-backed loans | Stage 5 | Funds mines, refineries, and fabs against contracted output |

**Board dynamics:** board members are people with attributes and agendas. Losing board confidence leads to warnings, forced hires, and in the extreme, founder removal.

**Valuation:** private rounds use comparables from rival multiples and the funding climate; public valuation is market-driven each turn.

## 11. Minerals, Prospecting, and Mining (v3)

Minerals are the slowest, riskiest, and most strategic layer: a deposit takes years to develop, but owning one insulates the chip and hardware businesses from shocks.

**Commodities (initial set):** high-purity quartz, silicon metal, polysilicon, gallium, germanium, copper, tin, tantalum, cobalt, lithium, rare earth elements, neon (as a refining by-product proxy).

**Prospecting pipeline:** desk study, field survey, sampling, drilling, resource estimate, feasibility study, permitting, construction, production, closure. Each stage costs money and time, and narrows the uncertainty on true grade and tonnage.

**Hidden geology:** every deposit has a hidden true grade, tonnage, and metallurgy. The player sees an estimate range whose width depends on spend and the geologists' skill, the same reveal mechanic used for hidden person traits.

**Operations:** capex, opex per tonne, recovery rate, strip ratio, power and water needs, environmental footprint, and community relations.

**Regions and risk:** each region has geology profiles, permitting time, royalty and tax, infrastructure, political stability, and export-control exposure.

**Selling output:** spot sale, long-term offtake contracts with rivals or third parties, or internal transfer to the player's own refinery and fab at a transfer price that shows up in divisional P&Ls.

## 12. Event Engine and LLM Contract

The engine decides when an event happens and what it may change; the LLM decides only how it reads.

**Pipeline**

1. **Director:** picks event slots each turn from weighted triggers on state (low morale, rival launch, commodity spike, covenant breach), with cooldowns and category rotation.
2. **Context builder:** assembles a compact snapshot: company KPIs, up to 6 relevant people with visible traits and tags, active storylines, last 10 event summaries, the allowed effect catalog for this slot, and severity caps.
3. **LLM call:** Anthropic API with a strict JSON schema (tool-use or structured output).
4. **Validator:** schema check, known effect types only, valid target ids, values clamped by severity, cash effects capped as a share of cash or revenue.
5. **Fallback:** one retry, then a template event of the same category.
6. **Persistence:** event, choices, chosen option, applied effects, and storyline links are stored.

**Output schema (summary)**

```json
{
  "title": "string",
  "body": "string (<= 180 words)",
  "category": "personnel|market|operational|financial|exploration|regulatory",
  "severity": "minor|major|critical",
  "choices": [
    {"key": "A", "label": "string", "effects": [{"type": "morale_delta", "target": "person:142", "value": -8}]}
  ],
  "storyline": {"id": "optional", "new_summary": "optional"}
}
```

**Other LLM uses (all read-only):** month-end newspaper headlines, scouting report prose, board meeting minutes, employee exit-interview flavor, and an "Ask my COO" advisor that answers from a state snapshot.

**Cost control:** batch event generation at turn end, cache by prompt hash, use a small model for flavor text and a larger model for multi-turn storylines, and a monthly token budget setting. The game is fully playable with the LLM switched off.

## 13. UI and UX Specification

The interface copies Football Manager's grammar: a persistent left navigation, a top bar with date, cash, and a large Continue button, an inbox as home, and every entity (person, product, rival, deposit) clickable into a profile page.

| Screen | Purpose | Key components | Phase |
| --- | --- | --- | --- |
| Inbox | Home; events, reports, decisions due | Message list, decision cards, severity badges | v1 |
| Company overview | KPIs at a glance | Runway, ARR, burn, headcount, morale, valuation tiles; 12-month trends | v1 |
| People and squad | Roster | Sortable, filterable table with custom column views; attribute heat colors | v1 |
| Person profile | Everything about one person | Attribute grid (1 to 20), personality ranges, interests, history, relationships, contract | v1 |
| Recruitment | Find and sign talent | Search filters, shortlist, scouting assignments, offer negotiation | v1 |
| Org chart | Structure | Interactive tree, drag to reassign, span-of-control warnings | v1 |
| Products | Portfolio and pipeline | Stage board, quality and appeal bars vs rivals, team allocation | v1 |
| Finance | Statements and funding | P&L, balance sheet, cash flow, cap table, term sheet comparison | v1 |
| Competitors | Rival intelligence | Rival profiles, market share charts, news | v1 |
| R&D | Tech tree | Domain levels, active projects, licensing | v2 |
| Markets | Prices and macro | Commodity and component charts, macro indicators | v2 |
| Facilities and supply chain | Production network | Facility list, chain map, utilization, contracts | v2 |
| Stock and M&A | Public markets | Share price, analyst ratings, acquisition targets | v2 |
| Exploration | Mining | Region map, prospect pipeline, estimate ranges | v3 |
| History | The story so far | Searchable event log, storyline timelines, hall of fame | v1 |

**UX rules:** every number has a tooltip explaining its drivers; every table supports saved column views; keyboard shortcuts for Continue and navigation; dark mode by default; no screen needs more than two clicks from the left nav.

## 14. Technical Architecture

A local web app: a Python simulation core with no I/O, wrapped by a FastAPI service, persisted to SQLite, and rendered by a React front end in the browser.

Runtime flow: React front end → (HTTP JSON) → FastAPI service → runs the turn in the pure, seeded Simulation core; FastAPI reads and writes the SQLite save file; the Simulation core passes a state snapshot to the Event engine (director and validator), which sends prompts to the LLM adapter (Anthropic, mock, or templates) and writes only validated effects back to the save.

Only validated effects reach the save file; the LLM never writes state directly.

| Layer | Choice | Notes |
| --- | --- | --- |
| Simulation core | Python 3.12, pure functions, Pydantic models | No database, network, or LLM imports; fully unit-testable |
| Persistence | SQLite via SQLAlchemy 2.x, Alembic migrations | One file per save; WAL mode; automatic backup every 12 turns |
| API | FastAPI | Thin; loads state, calls core, writes results in one transaction |
| LLM adapter | Anthropic Python SDK behind an interface | Mock adapter for tests; template adapter for offline play |
| Front end | React, TypeScript, Vite, TanStack Table and Query, Mantine components, Recharts | Table-heavy UI |
| Tooling | uv, Ruff, mypy, pytest, Hypothesis; pnpm, ESLint, Vitest, Playwright | Pre-commit hooks enforce lint and types |
| Packaging (later) | Tauri or a single launcher script | Optional desktop feel |

**Repository layout**

```text
tech-startup-tycoon/
  CLAUDE.md                # rules for Claude Code
  .cursor/rules/           # rules for Cursor
  docs/                    # this spec, ADRs, data dictionary, balance notes
  backend/
    sim/                   # pure engine: people, org, products, market, finance, minerals, rivals
    events/                # director, context builder, validator, templates
    llm/                   # adapter interface, anthropic, mock, template
    db/                    # models, repositories, migrations
    api/                   # FastAPI routers and schemas
    data/                  # seed YAML: companies, commodities, regions, roles, tags, tech tree
    tests/                 # unit, property, golden-seed simulation tests
  frontend/
    src/screens/  src/components/  src/api/
  tools/                   # balance runner, save inspector, seed generator
```

**Architecture rules:** the core never reads the clock or the global random generator (one seeded generator is passed in); every turn is a single transaction; all tunable numbers live in `data/balance.yaml`; the API contract is generated as OpenAPI and the TypeScript client is generated from it.

## 15. Data Model v1

The schema separates static seed data, current state, and an append-only history so any past turn can be inspected or replayed.

| Domain | Tables | Phase |
| --- | --- | --- |
| Save and time | save_meta (master seed, current turn, data file hashes, next-id counters), settings; no stored RNG state, since streams are derived from the seed (ADR-0002) | v1 |
| Entities | company (player and rivals), legal_entity, org_unit (kind, parent, leader, work-location policy; M2), unit_policy (later policies) | v1 |
| People | person, person_skill, person_personality, person_interest, person_hidden, person_reveal (half-width and center offset per attribute per observer company; ranges derived on read), person_tag, person_tag_reveal, person_profile_reveal, person_state (including energy), employment (company, unit, role, level, salary, equity, start, end, last raise), relationship (M6) | v1 |
| Hiring | search, candidate (with status: open, hired, declined, expired, withdrawn), offer, hiring_plan (M2) | v1 |
| Products | product_category, product, product_rating (quality, price, brand, features per turn), team_assignment, customer_segment, market_share | v1 |
| Finance | account, ledger_entry (double entry), funding_round, security (SAFE, preferred, common, option), cap_table_entry, loan, covenant | v1 |
| Events | event, event_choice, event_resolution, storyline, event_template, llm_call_log | v1 |
| R&D | technology, tech_level, research_project, license | v2 |
| Supply chain | facility, facility_unit, input_requirement, inventory, contract, commodity, price_history, macro_indicator | v2 |
| Public markets | listing, share_price_history, analyst, acquisition | v2 |
| Minerals | region, deposit (hidden truths), deposit_estimate, mining_project, permit | v3 |
| History | turn_snapshot (KPIs as JSON), decision_log (source: player or delegate), inbox_item, news_item | v1 |

**Conventions:** integer ids; money stored as integer cents; turn number on every time-varying row; soft deletes for people and products; hidden "truth" columns never returned by the API to the front end. The full column-level data dictionary is a pre-build artifact (section 21).

## 16. Balancing and Tuning

Balance is tested by machine before it is tested by play: a headless runner plays thousands of seeded games with scripted strategies and reports outcome distributions.

- **Single source of numbers:** every constant (salary curves, churn rates, share exponent, R&D costs, mine capex) lives in `balance.yaml` with a comment on its unit and intended effect.
- **Scripted strategies:** bootstrap-frugal, blitzscale, research-heavy, acquirer, vertical-integrator, and do-nothing. The do-nothing strategy must fail; no single strategy should win more than 60% of seeds.
- **Target curves:** median time to seed, to Series A, to IPO; bankruptcy rate by difficulty; employee tenure distribution; rival survival rate. These live in `docs/balance-targets.md`.
- **Golden seeds:** 10 fixed seeds whose 120-turn KPI snapshots are stored; any code change that shifts them must be intentional and noted in the changelog.
- **Exploit checks:** property tests for infinite-money loops (for example selling to yourself across subsidiaries) and negative-cost edge cases.
- **Difficulty levers:** starting cash, rival aggression, event severity weights, funding climate, and attribute fog width.

## 17. Milestones and Acceptance Criteria

Each milestone ends in something playable and a green test suite; nothing from a later milestone starts until the current one passes its criteria.

| Milestone | Scope | Acceptance criteria | Phase |
| --- | --- | --- | --- |
| M0 Foundation (done) | Repo, tooling, schema v1 for save and company, seeded RNG, turn runner, CI | New save advances 24 turns headless; same seed gives identical results; backup file written | v1 |
| M1 People (done: M1a, M1b, M1c) | Person generator, attributes, personality, interests, hidden traits with reveal, hiring, payroll, morale | Hire 10 people via UI; profiles render; payroll hits ledger; morale moves with pay and fit | v1 |
| M2 Org (done: M2a, M2b) | Departments, teams, reporting lines, span of control, remote policy, raises and promotions, delegated hiring | Build a 3-level org chart; span penalty visible; reorg costs morale; a recruiter's plan hires without founder energy | v1 |
| M3 Products and market (M3a rules and API, M3b screens) | 4 software categories, lifecycle, ratings, segments, share formula, revenue and churn | A company can earn and burn (bankruptcy arrives with M4); share responds to price and quality | v1 |
| M4 Finance | Double-entry ledger, statements, SAFEs, priced rounds, cap table, board | Statements reconcile every turn; dilution correct across 3 rounds | v1 |
| M5 Rivals | 8 agent rivals with personalities and utility AI, poaching | Rivals launch, price, hire, and die across 120 turns; balance runner passes targets | v1 |
| M6 Events | Director, templates, LLM adapter, validator, storylines, crisis windows | 200 LLM events with zero invalid state writes; offline mode works | v1 |
| M7 v1 polish | History screen, saves manager, tooltips, balance pass | Reece plays a full 10-year run without a blocking bug | v1 |
| M8 to M12 | Divisions, R&D tree, cloud and hardware, IPO and stock, M&A, macro | Defined at v1 retrospective | v2 |
| M13 to M16 | Holding company, fabs, refining, minerals, geopolitics | Defined at v2 retrospective | v3 |

## 18. AI-Assisted Development Workflow

Use one tool as the builder of record per task, keep the spec and rules files as the shared memory, and use a second model as an independent reviewer.

| Tool | Primary role | Best used for |
| --- | --- | --- |
| Claude Code | Builder of record | Multi-file features from a task brief, migrations, test suites, refactors, running the balance runner and fixing failures |
| Cursor | Interactive editor | UI iteration, small fixes, reading code alongside the running app, inline edits while playtesting |
| ChatGPT | Second opinion | Reviewing a diff or design against the spec, brainstorming event templates and names, sanity-checking economic formulas |
| Claude (this Project) | Product manager and designer | Spec changes, ADRs, task briefs, balance targets, playtest triage |

**Working agreement**

1. Every task starts from a written brief in `docs/tasks/` that cites spec sections and lists acceptance criteria.
2. Claude Code works on a branch, writes tests first for engine code, and must leave `pytest`, `mypy`, and `ruff` green.
3. One milestone at a time; no tool adds a system not in the current brief.
4. Any design change discovered while coding is written back to the spec or an ADR before merge.
5. A second model reviews each merged milestone against its acceptance criteria.
6. Commit small and often; tag a release at the end of each milestone so a bad session can be rolled back.

## 19. Risks and Mitigations

The largest risk is scope: this design describes three games' worth of systems, so phase gating is the primary mitigation.

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Scope creep stalls the project before v1 is fun | High | Hard phase gates; v2 and v3 systems stay in the spec, not the code |
| AI-generated code drifts from the architecture | High | CLAUDE.md and Cursor rules, task briefs, tests required, review by a second model |
| Economy is exploitable or dull | Medium | Balance runner, golden seeds, strategy win-rate caps |
| Simulation slows with many rivals and people | Medium | Rival employees simulated at reduced fidelity; profile at M5; vectorize hot loops if needed |
| LLM events feel generic or contradict state | Medium | Tight context snapshots, storylines, validator, template fallback |
| LLM cost creeps up | Low | Token budget setting, caching, small model for flavor |
| Save corruption | Low | Transactional turns, WAL, automatic backups, migration tests |
| Real-company names cause discomfort if shared | Low | Personal use only; a toggle to swap in fictional names |

## 20. Settled Decisions

All design questions but one are settled, and each answer is recorded in an ADR in the repository so coding agents do not re-ask. The LLM budget remains open, with a configurable cap as the default.

| Topic | Decision | Recorded in |
| --- | --- | --- |
| World and names | Real-world company and commodity names; personal use only; fictional-name toggle later | ADR-0011 |
| Start year | January 2010; a 2026 scenario later as a separate seed pack | ADR-0006, ADR-0011 |
| Campaign length | 360 turns (30 years) for a standard run; Sandbox unlimited | ADR-0006 |
| Turn granularity | Monthly turns, with weekly crisis sub-turns triggered by severity | ADR-0006 |
| Founder | Playable person with stats; can be fired by the board outside Sandbox | ADR-0011 |
| Delegation | Everything delegable; outcome quality depends on the delegate's attributes | ADR-0011 |
| Geography | Abstract regions in v1; named cities with offices in v2 | ADR-0011 |
| Personal stock trading | Allowed in v2 or v3 if scope permits; not in v1 | ADR-0011 |
| Event tone | Grounded realism with occasional light or satirical moments | ADR-0011 |
| Rivals | Agent-based full entities; utility AI, no LLM; reduced-fidelity staff beyond each rival's top 20 | ADR-0010 |
| Stack | Python, FastAPI, SQLite, React with Mantine | ADR-0001 |
| Scenarios and difficulty | Four starts and four difficulties; mineral-first start unlocks in v3 | ADR-0011 |
| LLM budget | Open: configurable monthly token cap with an on-screen meter until Reece sets a number | ADR-0005 |
| Randomness | One stream name per call site, keyed by entity id, so draws never collide or depend on iteration order | ADR-0013 |
| Action timing | Player actions apply immediately between turns; offers are answered at Continue | ADR-0014 |
| Delegates | Act in the advance step through the player's own actions, with their own energy and random stream | ADR-0015 |
| Offers and candidates | Withdrawing an offer keeps the candidate; a pending offer blocks expiry; equity comes from an option pool (200 bp per offer, 1,000 bp total before M4) | formulas.md §7 |
| Company mission | Defaults to the founder's interests | M1b brief |
| Cash before M4 | Cash may go negative; runway is shown at this month's projected costs | M1b, M1c briefs |
| Departments | Unlock at 10 staff or at stage 2, whichever comes first | formulas.md §13.1 |
| Interview before offer | An offer requires that the company (founder or delegate) has interviewed the candidate | ADR-0016 |
| Founder energy | Stays on (100 a month) after the M1 playtest; every hire now costs at least one interview. Delegates have their own energy | ADR-0016 |
| Judgment of talent | Its main job is spotting potential: potential narrows much faster for good scouts, and hiring plans can favour potential (juniors and mids) | formulas.md §4, §13.10 |
| Competitors before M5 | Real 2010 incumbents with fixed product scores and starting customers; the same companies get people, ledgers and AI in M5 | ADR-0017 |
| Founder scouting | The founder can scout a search for 20 energy, the same action delegates use | formulas.md §11.12 |

## 21. Pre-Build Artifacts to Generate

Twelve artifacts should exist before the first line of game code; the first five are required for M0 and M1, the rest can follow just in time.

| # | Artifact | Why it matters for AI-assisted coding | Needed by | Format |
| --- | --- | --- | --- | --- |
| 1 | CLAUDE.md and Cursor rules | Gives every coding session the same architecture rules, commands, and do-not-do list | M0 | Markdown in repo |
| 2 | Architecture decision records (ADRs) | Freezes stack, RNG, money-as-cents, transactional turns so tools stop re-deciding them | M0 | docs/adr/*.md |
| 3 | Data dictionary (column level) | Removes guesswork from models and migrations | M0 | Markdown or Sheet |
| 4 | Attribute and formula reference | Exact formulas for growth, morale, flight risk, appeal, share, churn | M1 | Markdown with formulas |
| 5 | Milestone task briefs (M0, M1) | Scoped prompts with acceptance criteria for Claude Code | M0 | docs/tasks/*.md |
| 6 | Seed data packs | Roles, skills, tags, interests, product categories, segments, regions, rivals, investors | M1 to M5 | YAML |
| 7 | balance.yaml and balance targets | Single source of tunable numbers plus the curves the runner checks | M3 | YAML and Markdown |
| 8 | UI wireframes for v1 screens | Lets Cursor build screens to a target instead of inventing them | M1 | Design mockups |
| 9 | Design system tokens | Consistent tables, badges, attribute colors, dark theme | M1 | Design System |
| 10 | Effect catalog and event JSON schema | The contract the LLM and validator share | M6 | JSON Schema |
| 11 | Event template library (50 to 100) | Offline play and LLM fallback; tone reference for prompts | M6 | YAML |
| 12 | Test and playtest plan | Golden seeds, scripted strategies, playtest checklist | M3 | Markdown |

**Recommended order:** 1, 2, 5 in one sitting (so Claude Code can start M0), then 3 and 4, then 8 and 9 in parallel with M0.

**Status:** items 1, 2, 4, and 5 are in the GitHub repository (`Reece77/Tech_Executive_Tycoon`): rules files, 17 ADRs, `docs/formulas.md` (final through M3: §11 products and markets, §13 organization), and briefs for M0 through M3b. Item 3 (data dictionary) is kept current with each migration. M0, M1 and M2 are complete; M3a is next, and M3b follows once its product wireframes are drawn.
