# Wireframes (M1 to M6)

Six desktop screens, built in M1c: New-game setup, Inbox, Overview, People, Person profile, and Recruitment with the offer panel. The editable canvas is the Claude Design artifact "Tech Startup Tycoon M1b Wireframes" (ask Reece for the link). The artboard sources are copied in `docs/wireframes/source/` for reference; they use the design canvas's runtime and are not meant to run in the app.

Build the screens in React with Mantine to match these layouts. Example data (Kestrel Systems, June 2010) is consistent with `docs/formulas.md`, so the numbers can double as test fixtures.

## Shared shell

| Part | Content |
| --- | --- |
| Top bar | Company name and stage label; date; cash; runway (orange when below 6 months); founder energy as `62 / 100` with a bar; Continue button (Space or Enter) |
| Left nav | Keys 1–9: Inbox, Overview, People, Recruitment, then Org, Products, Finance, Competitors, History shown dimmed with the milestone they arrive in (M2, M3, M4, M5, M7). Inbox shows an unread count |
| Layout | Nav 200–240 px, content fills the rest; both wrap to a single column on narrow windows; wide tables scroll horizontally inside their panel |

## Design tokens (dark theme)

| Token | Value | Use |
| --- | --- | --- |
| `bg` | `#0E1217` | Page |
| `nav-bg` | `#11161D` | Left nav |
| `panel` | `#151B23` | Panels, top bar |
| `panel-active` | `#1F2A38` | Selected nav item, pressed toggle |
| `border` | `#2A3442` | Panel borders |
| `rule` | `#222B37` | Table row lines |
| `text` | `#E8ECF1` | Primary text |
| `text-2` | `#C9D1DB` | Secondary text |
| `muted` | `#9BA7B6` | Labels, captions |
| `accent` | `#5AA2FF` | Continue, primary buttons, selection, morale ≥ 60 |
| `warn` | `#F5A25D` | Low runway, morale < 40, notice status, Fire button |
| `good` | `#6FCF8E` | Active status, hire messages, "likely" hint |
| Fonts | IBM Plex Sans; IBM Plex Mono with tabular numerals for every number |

**Attribute colors** (`AttributeRange`, by range midpoint): 1–5 `#9BA7B6`, 6–10 `#D5DBE3`, 11–15 `#6FCF8E`, 16–20 `#F5C451` bold. A range shows as `14–17`; a known value as `14`.

**Morale bar:** below 40 `warn`, 40–59 `#D5DBE3`, 60+ `accent`; the number is always shown beside the bar.

**Message kinds** (inbox badges): Hire (green), Search (blue), Scout (gold), Notice (orange), Declined (grey). Text labels, no icons or emoji. There are no month-closed messages; the Overview covers each month (M1c review).

## Screens

**New-game setup** (no shell; replaces M0's create form). One page in four numbered panels. *Company:* name, difficulty (segmented), scenario cards with starting cash (the v3 scenario shown locked). *Founder:* optional first and last name (blank draws one), age, background cards with their bonuses (geologist locked until v3), and the skill allocation in three columns: each skill shows its background bonus, −/+ buttons, and the final value colored like `AttributeRange`; a large "points left" counter and a reset-to-default button. *Personality:* four preset cards plus "Surprise me". *Mission:* the 13 interests as toggle chips, exactly 2 chosen. A summary line and the Start button, disabled until the founder preview reports no errors. Final values and points left come from `POST /api/meta/founder-preview`; ability and potential are never shown.

**Overview.** Six KPI tiles (cash, monthly burn, runway at this month's projected costs, headcount, monthly payroll, average employee morale), each with a one-line note; a line chart of cash at each month end; this month's projected costs (salaries, benefits, office, job posts, overhead, total) with a note that revenue arrives in M3; and the five latest inbox items linking to the inbox.

**Inbox (home).** Filters (All, Unread, People, Hiring). Message list with a kind badge, bold title when unread, one-line preview, and date. The selected message opens in a detail panel with its body, key facts (for a resignation: role, morale, last day, salary), and actions that follow the message's link (View profile, Find a replacement, Mark unread).

**People.** Overview/Skills view toggle, Columns button, name or role filter. Summary tiles: headcount (and how many on notice), monthly people cost, average employee morale, company mission. Roster table: name (links to profile), role, level, age, salary, morale (number and bar), form ("From M3"), top 3 skills as ranges, status chip (Founder, Active, Notice). The founder shows salary "—" and morale "n/a" because the founder is excluded from both in M1.

**Person profile.** Back link; summary band with name, role, level, age, region, salary, tenure, potential phrase (never a number), morale bar. Three attribute panels (Technical 10, Business 9, Leadership 6), then Personality (9), Interests (mission matches marked) with work style, noticed traits, a "how well you know them" line, and Contract: salary, market rate, equity, joined, monthly cost, 5-month morale sparkline, Fire button with confirm text stating severance and the morale penalty.

**Recruitment.** Open-a-search panel: role select and three channel cards showing energy, cost, batch size, and whether the search stays open; the submit button names its energy cost. "Your searches" list with Close on open job posts. Candidates table for the selected search: name, level, age, asking salary (exact), the role's key skills as ranges, interests ("Interview to learn" until revealed), what you know (Screened, Interviewed, references), and actions with energy costs, or "Offer pending · answer in <month>". Offer panel: salary with its ratio to the ask and the 85% decline floor, equity in basis points with its percent, the hint ("Likely to accept", "Uncertain", "Unlikely") with a one-sentence reason drawn only from what the player knows, Send offer and Cancel, and a note that the answer comes at Continue.

## M2b screens

Three more artboards on the same canvas, in its second row: **Org**, **Profile additions**, and **Hiring plans**. Example data is Kestrel Systems in March 2011 with 19 people. Unlike the M1 examples, the morale numbers in the M2b boards are illustrative, not test fixtures; span counts and headcounts are consistent with `docs/formulas.md` §13.

**Shell change.** Nav key 5, Org, is live. The other dimmed items are unchanged.

**Org.** Header with headcount, unit count and how many managers are over span; New team and New department buttons with energy costs (New department shown only once departments unlock, otherwise the reason). The chart is an indented tree: company → departments → teams, with people who report to the founder directly shown as chips in a dashed row. Each node shows a kind label (Company, Department, Team), name, leader (linked), work location (with "(inherited)" when it comes from the parent), headcount, and a span badge `reports / comfortable span` (green, or orange "over span"). Selecting a node opens the side panel: leader, reports against span, the manager label (strong, fine, stretched), an explanation when over span, the work-location select (inherit, office, remote), Set leader, Rename, Move team, Dissolve (with energy costs), and the members table with a "Leads" chip and a "Move to…" button per person. People can be dragged onto a unit, and teams onto a department. Every change opens a preview first: who it moves, the one-off morale change for each person affected (from the API preview), the energy cost, and Confirm or Cancel.

**Profile additions.** The summary band gains Unit and Manager links and three buttons: Give a raise, Promote, Move to…. A "Why his morale is moving" panel lists the API's morale breakdown: starting point 50, pay, fit, runway, manager (naming the manager and why), teammates (noticed traits only), work location, and other, with where morale is heading. "Other" is labelled as things the player does not know yet (§13.11). Raise dialog: new salary, percent change, ratio to the market rate, one-off morale, monthly cost change, energy, and the yearly-bonus and pay-cut rules. Promote dialog: level change, market rate before and after, salary against the new rate, one-off morale, energy, a warning when pay falls well below the new market rate, and a "Promote and raise…" path. All values come from the preview endpoints.

**Hiring plans** (Recruitment, below the M1 panels). Table: owner (and role), unit, role, focus ("Spot potential" in gold), progress with a bar, channel, highest offer as times the ask, equity, last month's activity in words, status (Active, Paused), and Edit or Choose owner, and Close. A plan whose owner left shows "No owner" and the reason. The New plan dialog: owner (with their judgment of talent and recruiting as the company's displayed ranges, and their own energy), unit hires join, role, how many, Focus ("Best now" or "Spot potential", with one line on what it does), channel (Any, Job post, Recruiter, Network), highest offer (up to 1.20×), equity per offer with what is left in the option pool, and Start plan with its energy cost. Candidates the company has not interviewed show "Interview first" instead of Offer.

**Not drawn (text only):**
- *People:* Unit and Manager columns, a unit filter, and a "Leads" chip next to leaders' names.
- *Inbox:* a **Delegate** kind badge (purple, `#B9A6FF` on `#262040`) for plan summaries; 50 messages per page with Newer and Older buttons and the page range shown (for example "51–100 of 342").
- *Overview:* an Org tile showing units, managers over span, and the average manager label (strong, fine, stretched).
- *Recruitment:* the Network channel card adds "+1 candidate: your founder is sociable" when it applies.

## M3b screens

Three artboards in the canvas's third row: **Products**, **Product profile**, and **Market view**. Example data is Kestrel Systems in June 2012 at stage 2, with a live B2B SaaS product (Pipeline), a cybersecurity product in development (Sentinel) and a consumer app being sunset (Flock). Appeal, price scores and share-of-choice numbers follow `docs/formulas.md` §11 exactly (checked); customer counts and money are illustrative.

**Shell change.** Nav key 6, Products, is live. The top bar is unchanged (MRR and ARR live on Overview and Products).

**Products.** Header with a Markets link and New product (energy 4). KPI tiles: MRR with change on last month, ARR (with the month stage 2 was reached), paying customers (consumer users counted separately), hosting and marketing this month. Portfolio table: product (links to its profile), category, status chip (Live with the growth or mature label, In development, Sunset), quality with a bar, features, brand, customers, MRR, trend (a month-on-month rate, or what launch still needs), development pace (fast, steady, slow, no team). New product dialog: name, category, and the category's segments as checkboxes, each with how it is reached (self-serve or needs salespeople), its addressable customers now and its typical price; a note that it starts in development at quality 10 and the launch thresholds; Create with energy cost.

**Product profile.** Name, category, launch month, status chip, and a link to its market. KPI tiles: MRR, customers (new and lost last month), hosting, development pace with builder count. *Against the competition:* a segment toggle and, for each of quality, features, brand, price (shown as price and score) and appeal, one bar per product in that segment (the player's product in accent blue, competitors in greys), with a line explaining the segment's weights. *Who works on it:* assigned units with Unassign, builders, sellers and marketers by name, Assign a unit. *Marketing:* monthly budget with Save and a one-line brand trend (never the target brand). *Segments:* price (editable), customers, share of buyers, new, lost, churn, MRR, and the sales-capacity note when it applied; Add segment with energy cost. *Price preview* (opens when a price is edited): price score, appeal and chance a buyer in play picks the product, before and after, plus the change in revenue per customer, with a note that customer numbers depend on next month. *Last 12 months:* MRR line chart; Sunset with its confirm text. Products in development show a launch-readiness panel in place of the segment numbers: quality and feature score against 25 and 30, prices set or missing, and Launch (energy 3) enabled only when ready, plus Cancel development (energy 3, with a confirm).

**Market view.** Category toggle and the market's growth. One table per segment, sorted by appeal: product, company ("(you)" on the player's rows, highlighted), quality, features, brand, price, appeal, customers, and share of buyers with a bar. Each segment's summary line gives addressable businesses or users, how many use a product, the typical price, whether it is sales-led, and "you do not sell here" where it applies.

**Not drawn (text only):**
- *Org:* each unit shows the product it works on; the unit panel gains "Works on" with Assign or Unassign.
- *Overview:* MRR and ARR tiles; revenue above costs in the month's breakdown; revenue added to the cash chart.
- *Recruitment:* a Scout button on each search row for the founder ("Scout · 20"), which narrows every open candidate in that search.
- *Inbox:* a **Product** kind badge (teal, `#5FD4C4` on `#123331`) for launches, first customers, ARR milestones and capacity notes; filters and the unread count apply across all pages.

## M4b screens

Five artboards in the canvas's fourth and fifth rows: the four **Finance** tabs (**Statements**, **Cap table**, **Fundraising**, **Board**) and the **Game over** screen. The Kestrel example follows `docs/formulas.md` §14.10: a $500,000 SAFE at a $5M cap (April 2010), a $2M seed at $6M pre from First Round Capital (November 2010), and a $5M Series A at $18.3M pre from Andreessen Horowitz (August 2012). Cap-table shares, percentages, the pool top-up, vesting and fees are exact; statement amounts are illustrative but add up.

**Shell change.** Nav key 7, Finance, is live. The top bar's runway shows "Profitable" when the projection is positive, and an orange **Insolvent** badge while cash is negative (it links to an open bridge offer).

**Statements.** Period toggle (month, quarter, year) and "in thousands of dollars". The P&L shows six periods side by side: revenue, hosting as cost of revenue, gross margin, each operating expense, operating expenses, and net result (negatives in orange with a minus sign). Below: the balance sheet at the period end (cash, total assets, SAFEs outstanding, total liabilities, common and preferred paid in, accumulated result, and liabilities plus equity equal to assets), the cash flow (operating, financing, change in cash, burn) with a note on how runway is computed, and a 12-month chart of cash and burn on separate scales.

**Cap table.** Tiles: fully diluted shares, share price (last priced round), post-money valuation, and the founder's ownership. Holders table: holder, class, shares, percentage with a bar (founder in accent, investors in light grey, granted options in green, the unallocated pool in dark grey) and a total row. "Your ownership over time": each event with the founder's percentage. Employee options: granted, vested and unallocated totals and the vesting rule; per person the grant month, options, vested, unvested and the next vesting date (the cliff highlighted in gold).

**Fundraising.** The open round: series, start month and when it lapses, ARR against the series gate, the typical raise, and how many firms answered. Term sheets table: firm, pre-money, amount, post-money, "you own after", board seat, expiry, and Preview. Selecting one opens the **dilution preview**: amount, price and new shares, then each holder's percentage now, after and the change, the pool top-up, the board after closing (with who controls a tie), legal fees, and Accept (energy 5) with the note that it closes at Continue. Beside it, **Raise on a SAFE**: amount, post-money cap, the hint band ("Likely", "Uncertain", "Unlikely") with one line on how SAFEs answer, and Raise (disabled with the reason while a priced round is open). "Past rounds and SAFEs" lists each with its terms and outcome. When no round can be started yet, the series gate says what is missing (for example "Series B needs ARR of $5M; you are at $3.2M").

**Board.** Tiles: confidence as a label and number with its direction, seats by kind and who controls a tie, the growth the board expects against actual, and the next quarterly meeting. Directors table: founder and common nominee (no confidence), then each investor or independent director with seat, firm, start month, confidence (bar coloured by band: below 25 orange, 25–39 gold, 40+ accent) and label, a six-month sparkline, and months below 25. A paragraph explains how removal works and when it becomes possible. "Last board meeting" shows the quarterly summary and the confidence change, with any formal warning.

**Game over.** No nav; the top bar shows the company, date, final cash, a Game over badge and New game. A headline with the reason and month (bankruptcy, or removal by the board), a sentence on what happened (including a lapsed bridge), tiles for how long the company lasted, final ARR, peak and final headcount and the founder's ownership, the last six months as a timeline, and links to read the save (Statements, Cap table, Inbox, People). For a removal the screen names the directors who voted and shows their confidence.

**Not drawn (text only):**
- *Offer dialog:* equity shows options and percentage of fully diluted shares, and what is left in the pool.
- *Profile:* the contract panel gains granted, vested and unvested options and the next vesting date.
- *Overview:* a Funding tile (last round, post-money, founder ownership, board confidence label).
- *Inbox:* a **Finance** kind badge (gold, `#F5C451` on `#3A2F16`) for SAFE answers, term sheets, closings, board meetings, warnings, insolvency and bridges.

## M5 screens

Two artboards in the canvas's sixth row: **Competitors** (with the month's market news and an approach) and a **Rival profile** (Salesforce). The example is Kestrel in June 2012; the approach on Priya Raman is `docs/formulas.md` §15.8's worked example ("might go" is the band for 23.7%). Rival revenue and staff follow §15.1's sizing from the M3b market numbers.

**Shell change.** Nav key 8, Competitors, is live. The top bar shows M4c's 60-point energy.

**Competitors.** A filter (in your markets, all, startups) and a count of established companies, startups alive and failed. Table: company (links to its profile; a purple "Startup" chip on startups), style chip (aggressive orange, fast follower blue, premium gold, cost leader green), where it competes with the player, estimated staff, money label (deep pockets, comfortable, tight), and its last move in words. **Market news** for the month: one line per rival action or startup event with a coloured tag (Price, Push, Launch, Funding, Approach, Failed) and a link to earlier months in the inbox. An open **approach** appears as an orange panel: who, the offer against their salary and unvested options, the band ("likely to stay", "might go", "likely to go"), **Counter with a raise** (opens the M2b raise dialog, whose preview now also shows the new band) and **Let them decide**. The same approach is an inbox item with the News kind badge.

**Rival profile.** Name, style chip and one line on how that style competes. Tiles: staff in the player's markets, revenue in those markets (from public prices and customers), money label, and stance toward the player ("responding", "watching", "not competing") with the reason. Products table: each segment's quality, features, brand, price, customers, and what is running now (a push and its end month). **Key people:** name, role, level, top skills as the player's ranges, potential phrase, and **Poach from <company>** (the Recruitment channel, energy 10), with a note on the quality cost to the rival and the harder ask. **Recent moves:** dated list of the rival's actions, approaches to the player's people in orange.

**Not drawn (text only):**
- *Recruitment:* a fourth channel card, **Poach from a rival** (energy 10), with a company picker; candidates show "currently at <company>" and asks of about 1.3× their salary.
- *Inbox:* a **News** kind badge (blue-grey, `#AFC3D9` on `#1C2733`) for Market news and approaches; approaches are pinned to the top until answered.
- *People and profile:* an "Approached by <company>" chip while an approach is open.

## M6 screens

Two artboards in the canvas's seventh row: **Events** (the inbox with an event open and a critical event's modal on top) and **Settings** (AI writing and the budget). Kestrel in September 2012; the raise in Priya's event is 10% of her $118,000 salary.

**Events.** The inbox lists events with an **Event** badge (gold) or a **Critical** badge (orange, filled), and an "Ongoing stories" section below the messages with each storyline's step. An open event shows its category and severity, its storyline if any, the title, the body (up to 180 words), and two or three choices as full-width buttons; under each choice its effects in words with a size ("large morale lift for Priya · costs about $11,800 a year"), never exact numbers or caps. A line says effects apply at once, and that the text is written by AI within the game's rules. A header line counts the events still to answer and states that minor and major ones resolve to their first choice at Continue, and links the month's AI spend to Settings.

**Critical events** open as a modal that cannot be dismissed; the top bar's Continue is disabled with "Answer the critical event first". The modal names its storyline and says when a follow-up will come.

**Settings** (a top-bar button). *AI writing:* a choice between Claude and offline templates (with whether an API key was found, never the key), this calendar month's spend against the budget as a bar with the call count and reset date, the monthly budget, the two model ids, three counts (events written by Claude, rejected drafts replaced by templates, average cost per event), and a plain statement of what Claude can and cannot see. *Game:* difficulty and the saves folder.

**Not drawn (text only):**
- *Profile:* a **Relationships** panel listing unit-mates and manager with a label ("close", "good", "neutral", "strained", "hostile").
- *Org unit panel:* a "Team mood" line naming any strained or hostile pairs.
- *Market news:* two or three AI-written headlines at the top (templates offline).
- *Board tab:* quarterly minutes as a short paragraph in "Last board meeting".

## Rules carried from the docs

- Never show CA, PA as a number, hidden traits, or tags the player's company has not noticed (ADR-0007).
- The offer hint uses only known values (`docs/formulas.md` §7).
- Actions apply at once and spend energy; offers resolve at Continue (ADR-0014). An offer needs an interview first (ADR-0016).
- Never show a product's quality cap, anyone's output or capacity numbers (`docs/formulas.md` §11.13).
- Never show investors' base value, a firm's bias or noise, or a SAFE's acceptance probability (`docs/formulas.md` §14.9).
- Never show a rival's utilities, needs or noise, its key people's true attributes, or an approach's probability (`docs/formulas.md` §15.5–§15.6).
- Event effects are shown as words and sizes; relationships as labels; never caps, trigger strengths or relationship numbers (`docs/formulas.md` §16.9).
- The front end never computes a game value: spans, manager labels, morale terms and previews all come from the API (`CLAUDE.md` §7).
- Touch targets at least 44 px for primary buttons; real buttons, links, and labelled inputs.
