# M1b wireframes

Four desktop screens for M1b: Inbox, People, Person profile, and Recruitment with the offer panel. The editable canvas is the Claude Design artifact "Tech Startup Tycoon M1b Wireframes" (ask Reece for the link). The artboard sources are copied in `docs/wireframes/source/` for reference; they use the design canvas's runtime and are not meant to run in the app.

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

**Message kinds** (inbox badges): Hire (green), Search (blue), Scout (gold), Notice (orange), Declined and Month (grey). Text labels, no icons or emoji.

## Screens

**Inbox (home).** Filters (All, Unread, People, Hiring). Message list with a kind badge, bold title when unread, one-line preview, and date. The selected message opens in a detail panel with its body, key facts (for a resignation: role, morale, last day, salary), and actions that follow the message's link (View profile, Find a replacement, Mark unread).

**People.** Overview/Skills view toggle, Columns button, name or role filter. Summary tiles: headcount (and how many on notice), monthly people cost, average employee morale, company mission. Roster table: name (links to profile), role, level, age, salary, morale (number and bar), form ("From M3"), top 3 skills as ranges, status chip (Founder, Active, Notice). The founder shows salary "—" and morale "n/a" because the founder is excluded from both in M1.

**Person profile.** Back link; summary band with name, role, level, age, region, salary, tenure, potential phrase (never a number), morale bar. Three attribute panels (Technical 10, Business 9, Leadership 6), then Personality (9), Interests (mission matches marked) with work style, noticed traits, a "how well you know them" line, and Contract: salary, market rate, equity, joined, monthly cost, 5-month morale sparkline, Fire button with confirm text stating severance and the morale penalty.

**Recruitment.** Open-a-search panel: role select and three channel cards showing energy, cost, batch size, and whether the search stays open; the submit button names its energy cost. "Your searches" list with Close on open job posts. Candidates table for the selected search: name, level, age, asking salary (exact), the role's key skills as ranges, interests ("Interview to learn" until revealed), what you know (Screened, Interviewed, references), and actions with energy costs, or "Offer pending · answer in <month>". Offer panel: salary with its ratio to the ask and the 85% decline floor, equity in basis points with its percent, the hint ("Likely to accept", "Uncertain", "Unlikely") with a one-sentence reason drawn only from what the player knows, Send offer and Cancel, and a note that the answer comes at Continue.

## Rules carried from the docs

- Never show CA, PA as a number, hidden traits, or tags the player's company has not noticed (ADR-0007).
- The offer hint uses only known values (`docs/formulas.md` §7).
- Actions apply at once and spend energy; offers resolve at Continue (ADR-0014).
- Touch targets at least 44 px for primary buttons; real buttons, links, and labelled inputs.
