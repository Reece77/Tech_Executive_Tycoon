# Reece's playtest 5 (2026-11-10, on `main` at `m22-done`; the v3 playtest)

Sessions A–F on practice saves (pt5-*), with pt5-mine2 and pt5-explore2 rebuilt from `fix-fixture-reveals`. No blocking bug in the game itself; the practice saves had several faults (below).

| Card | Verdict | Reece's note (abridged) |
| --- | --- | --- |
| Forming a holding company | works well | "Makes sense." |
| Mandates and subsidiary CEOs | could be better | A capital request had no link to it (extra clicks). Subsidiaries should give better quarterly updates and ask for advice. |
| Selling stakes, carve-outs, spin-offs | could be better | "I sold and did a carve-out but can't see where this is tracked to see what it accomplished." |
| Commodities and offtake | could be better | Shows the hedge paying, "but I lost production". Only last month's use is shown; wants a planning view (need next year, which products drive it, offtake cover). |
| Exploration | **needs a fix** | Clicking a block licenses it at once (bought several by accident). Greyed-out stages say what's missing, not how to get it (drill N more holes, then re-estimate); a progress line or auto-upgrade. A glossary entry and Explain for NPV. Desk studies recolour every block; needs a better view of the blocks you're working than clicking through regions. "Otherwise feels fair and is fun." |
| Building and running a mine | **needs a fix** | Founding a subsidiary belongs on the Group screen, not Mines. "Some stress in awaiting to see what happens." |
| A price crash | could be better | The critical event can't be dismissed to look at the mine first: "If I haven't looked in a while I don't have the information to make an informed decision." |
| Refining and wafers | **needs a fix** | Confused: the product page shows TSMC 52 wafers a month while selling 10,588 phones; the chip shows no revenue though the phones use it; "used 25.21" unexplained. Wants a Terminate button on contracts (fee = remaining take-or-pay, discounted, plus a penalty; the supplier remembers). "Wafer contract" should read "foundry contract"; the wafer plant makes "blank wafers"; the chip cost should split wafer material and foundry processing. |
| A fab of your own | could be better | "Feels like a business but getting customers seems too up to chance. There are no contracts to lock in foundry customers." |
| Waiting for EUV | works well | "Frustrating in a good way." |
| Export controls | (no verdict) | "Rivals should also be affected for this to be fair." |
| A supply ban | could be better | Dowa works as a non-China source, "not sure I would have known they were Japanese and not Chinese without asking". |
| The World screen | works well | — |
| Stress and burnout | works well | — |
| Persona and lobbying | works well | — |
| Investing your own money | could be better | Angel position value never rose though the company grew ("until they take more funding?"). |
| Explain this | works well | — |
| Achievements and mods | works well | — |
| Into the 2030s | didn't get to it | "The pieces seem good but I can't sit and play hard through 20 years right now." |

Log: the top bar should stay visible; the side bar should stay visible when scrolling ("the top and side should be independent of the working pane").

Practice-save faults found during the session: geologists without knowledge records broke People and Org (`fix-fixture-reveals`); stage-3 saves with only a founder and two geologists; `pt5-fab` ("mature") has no chips though it says it does; no save combines a chip company with its own fab.

## Where each goes

- **M23a (integration and accounting):** rivals under export controls; group supply (fabs, mines, refineries to any group company); a country choice for facilities and suppliers' countries shown; contract termination and foundry contracts; Codex review 5's twelve findings; offtakes protecting production.
- **M23c (playtest fixes and the interface):** critical events you can look around before answering; sticky top and side bars; exploration's licence confirmation, how-to messages, progress and a "your blocks" view; founding subsidiaries on the Group screen; capital requests linked; capital actions' history; clearer chip, wafer and foundry wording; a commodity planning view; NPV glossary and Explain; angel stakes shown with an estimated value; better subsidiary quarterly updates; realistic practice saves.
- **M23b (v3 balance):** 30-year runs across the chain; known misses; the gallium-ban impact; foundry demand; Reece's 30-year campaign after M23.
