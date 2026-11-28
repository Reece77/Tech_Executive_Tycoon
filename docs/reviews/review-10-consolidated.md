# Review 10, consolidated (product manager, 2026-11-28)

Two independent read-only reviews of `main` at `f38146d7` (`m45-done..m59-done`: M46–M55, M58, M59):

- **Codex** (`codex-review-10.md`): 18 findings, ids `C01`–`C18` below (its R10-01 to R10-18).
- **Fable** (`review-10.md`): 40 findings, ids `F1`–`F40` below (its 1–40).

Neither reviewer read the other's file. Merged here into **38 items** (17 found by both, 21 by one). The severity is the product manager's: **P1** breaks a save, determinism, exact money, a hidden-value guarantee or the player's safety (CLAUDE.md §2 and §8); **P2** wrong behaviour a player would see, or a guard that can't fail; **P3** code health. Where the reviewers disagreed, the reproduced reading wins (noted).

Fixes go to **M57r-A** (engine) and **M57r-B** (platform, conversations and tests), two lanes in parallel; M57r-B also releases **v6.0.1**. Every item has exactly one owner.

## Findings

| # | Sev | Found by | Finding | Owner |
| --- | --- | --- | --- | --- |
| 1 | P1 | C01 | The uninstaller deletes the whole install folder (`[UninstallDelete] {app}`, filesandordirs); an install into the game's Documents folder loses its saves on uninstall | B |
| 2 | P1 | F37 | The local API has no Host or Origin check: a web page that finds the port can force a download and install (`/api/desktop/update`) or, by DNS rebinding, set the API key | B |
| 3 | P1 | C02, F4 | Finishing a negotiation, meeting or talk runs three transactions; a crash or a second request between them signs a deal twice (reproduced: `commodity_deals` 1 → 2) or loses an agreed outcome | B |
| 4 | P1 | C05, F2, F3, F22, F23 | Hidden values leak through derived numbers: a one-to-one's exact loyalty change scales with hidden loyalty (C05, reproduced); a negotiation's shown range and counters let three rounds recover the reservation to about 1–4% (F2, reproduced); a creative lead's exact fee inverts to the true `creative + vision` (F3, reproduced); a rival's approach offer is hidden in §61 and shown in the rivals API (F22); the planted-literal tests miss all of these (F23) | B |
| 5 | P1 | C06, F14, F15 | RNG keys depend on storage ids, list positions or file order: auction ids (C06 reproduced: one id change moved a clearing price by 5%), bank ids, region file order for FX and world streams, the editor's category index, the robotaxi incident's list index (F14), and a set-ordered float sum (F15, latent). Fable read the auction keys as stable; Codex's reproduction stands | A |
| 6 | P1 | C03, F1 | A bank's ordinary deposit outflows drive reserves negative with no securities sale, restriction or failure (both reproduced) | A |
| 7 | P1 | C09, F13 | Float arithmetic in money: spectrum's clock price (`price * (1.0 + increment)`), network capex, a custom rival's `cash * cash_mult`; the money guard sees only "cents" and review 9's aliases, so it reports none | A |
| 8 | P1 | C07, C08, F20 | Money rounding drifts: yearly interest rounded before dividing by 12, charge-offs, float income, a 1¢ claims reserve that never clears, a streaming licence billed per month (7¢ a year collects 12¢) | A |
| 9 | P2 | F18 | Charter capital can be withdrawn while the charter is pending: a bank chartered with 1¢ of capital lends at an infinite ratio | A |
| 10 | P2 | C04, F19, F17 | FX against engine-set prices: marks taken before media's ad pricing rewrites the price; an engine price in dollars translated again; royalties and claims as a share of untranslated revenue (85% instead of 68%) | A |
| 11 | P2 | F6 | Hedgeable foreign revenue counts the installed base for unit-sale lines (devices, cars, chips): a line booking $0 showed $12.7M a month and $152M of hedge room | A |
| 12 | P2 | C14, F21 | Several forwards settling together: the report keeps only the last (3 forwards posted 11.5M¢, screen 3.8M¢), and gains and losses net into one account | A |
| 13 | P2 | C12 | Finance sets the month's demand and its dated caps after sales, so a new real-time rail's first month sells against the old market | A |
| 14 | P2 | F7 | With no ad sellers at calibration (Sandbox with no rivals, a custom start without social incumbents) the ad price collapses to the 1¢ floor for the game | A |
| 15 | P2 | C11, F29 | Apple's tracking cut subtracts any owned platform's share from iOS's, reads a fixed iOS share instead of M31's, and applies Europe's cut to own-platform users | A |
| 16 | P2 | F28 | Game store fees are a flat 30% to cash, even on the player's own store; M31's fees and M34's remedies are ignored | A |
| 17 | P2 | F31 | Integrating an acquired bank's or insurer's line, or M34's ordered sale of one, moves the product but not its charter | A |
| 18 | P2 | F30 | The editor accepts starting customers in gated families (mobile without a network, banking without a charter) | A |
| 19 | P2 | F5 | A deal's hidden draws omit an attempt count: after one agreed supplier deal, a second one that month replays the same zone and the winning moves | B |
| 20 | P2 | F8 | A failed classifier call scores `neutral` and plays the round; two or three LLM calls run inside the save's write lock for up to minutes | B |
| 21 | P2 | C15, F25 | The reply validator lets the wording contradict the outcome ("we agreed" on a walk-away) and reads digits without units | B |
| 22 | P2 | C10, F27 | The conversation budget can be overspent: a call costing more than the remaining balance, two saves spending the same balance, spend lost if the commit fails; `source` a free string | B |
| 23 | P2 | C18, F36, F38 | The updater: asset URLs and redirects unchecked, the checksum parsed loosely, no size cap, the file re-run by path after the backup, old installers kept, and the in-game update path never run end to end | B |
| 24 | P2 | F39 | A release can be published from any ref with only the Windows smoke test; M9's rival-spread guard has been red on `main`'s nightly since M53 with no known-miss row | B |
| 25 | P2 | C17, F12 | V3's AI margin row is skipped, not failed, when the strategies go bankrupt (10/10 seeds), so its bound never runs | B |
| 26 | P2 | F9 | M48's and M49's hidden-word tests can't fail (the adversarial text contains the words; the system prompt is unchecked) | B |
| 27 | P2 | F10, F11 | M52's sandbox-to-2100 target runs nowhere that can fail; M53's and M50's targets have no test | B |
| 28 | P3 | C13 | History coverage accepts a missing interior month or year | A |
| 29 | P3 | F16 | `Generator.poisson` with a mean of 10 or more uses the C library's `log` (Windows parity unproven) | A |
| 30 | P3 | F33 | `x or turn` treats turn 0 as missing in a 2008 game; `began_in` says January 2010 for a 2008 Sandbox or custom game | A |
| 31 | P3 | F24 | The company name is formatted into a one-to-one's system prompt (ADR-0023 point 6) | B |
| 32 | P3 | F26 | Tests could call Anthropic if `TST_CONVERSATION_ADAPTER` is set in the shell or `.env` | B |
| 33 | P3 | F32, F34 | Custom scenarios: the stored hash is never checked at load (a missing row silently runs the base world); best results keyed by slug only | B |
| 34 | P3 | F35 | Migration 0066 backfills `start_turn = 0` for every old save; a save from a newer build fails with Alembic's raw error | B |
| 35 | P3 | C16 | The e2e fixture cache's key omits the profile's starting state | B |
| 36 | P3 | F40 | Guard housekeeping: M51's carried rules outside `known_misses.py`; the call-site guard ignores the family integer; stale known-miss readings and a non-milestone owner; the purity scanner's ban list | B |
| 37 | P3 | F40 (docs) | Docs drift: CLAUDE.md §5's `new-game` needs `--company-name`; the unused `finserv` fraud stream and the catastrophe key in ADR-0013; three `2010 + turn // 12` outside the calendar | B |
| 38 | — | both | Found sound: review 9's 14 resolutions hold; v6.0.0 saves upgrade; one migration head; every collected test runs in exactly one shard; ledger entries balance by construction | — |

## Product manager rulings (2026-11-28)

1. **#1, #2 and #23 ship as v6.0.1** from M57r-B as soon as it merges: the installed game is the only copy most players have.
2. **#4, hidden values:** every derived leak is closed, not documented. Exact amounts that depend on a hidden value become qualitative feedback or are computed from the public projection. **#4's F22:** keep §61's guarantee; show the rival's approach offer as a band in both the talk's facts and the rivals API. The test standard becomes **paired-state**: vary one hidden field, assert the API JSON, prompts and public view are byte-identical.
3. **#5, RNG keys:** keys come from stable identities (an auction's market key and year, a bank's owner, region and local ordinal; region and category **keys**, not positions; an incident's zone and turn). ADR-0013's table is corrected to match. Outcomes change: re-record every fixture with the reason.
4. **#10's F17:** fix, don't record: shares of revenue are taken from booked (translated) revenue.
5. **#16:** route game store fees through `platforms.data.fee_for`, posting to the store's owner (internal on the player's own store).
6. **#24, M9's Africa miss:** M57r-B adds a bounded known-miss row (`M9.spread.africa`, owner M57, bound 10/10 seeds), with M57 to add a fixed-broadband rival in Africa or retire the cell. Releases require a commit on `main` with green `check` and `e2e`.
7. **#29:** add a poisson-heavy seed to the `determinism` job's Windows and Linux digests; if they differ, draw through a `dmath`-based sampler.

## Resolution, lane A (M57r-A, 2026-11-28)

| # | Status | Commit (branch `claude/m57r-a-engine-fixes-597pvg`) |
| --- | --- | --- |
| 5 | Fixed: stable keys; insertion tests (`test_m57r_a_rng_keys.py`); older index-keyed streams left, follow-up | fddc366 |
| 6 | Fixed: one liquidity routine; property test (`test_m57r_a_bank_liquidity.py`) | 1261e3b |
| 7 | Fixed: integer clock, rational capex, half-even cash; money guard extended and triaged | 40efc2e, 680fa80 |
| 8 | Fixed: one rational expression a month; reserves clear; licences by cumulative entitlement (`test_m57r_a_money.py`) | 40efc2e, 1261e3b |
| 9 | Fixed: no withdrawal before the charter or below its capital | 1261e3b |
| 10 | Fixed: marks after ad pricing; engine-priced lines re-marked; shares from booked revenue | 169c5df |
| 11 | Fixed: `FxMonth` from phase 5's booked revenue (`test_m57r_a_currencies.py`) | 169c5df |
| 12 | Fixed: settlements summed, settlement-only rows, gains and losses apart | 169c5df |
| 13 | Fixed: finance demand and pin before sales (`test_m57r_a_timing.py`) | b438a65 |
| 14 | Fixed: calibration at a region's first seller | b438a65 |
| 15 | Fixed: privacy cuts by delivery; iOS share from M31 | b438a65 |
| 16 | Fixed: game fees through `fee_for` to the owner | b438a65 |
| 17 | Fixed: charters move with integrated or sold lines | b438a65 |
| 18 | Fixed: the editor refuses customers behind a gate | b438a65 |
| 28 | Fixed: interior gaps refused to 2010 | fdad52b |
| 29 | Checked: poisson probe identical on Linux and Windows; no sampler change needed | 81b27c1 |
| 30 | Fixed: 19 sites, AST guard; `began_in` by start month | fdad52b |

## Resolution, lane B (M57r-B, 2026-11-28)

A section of its own rather than a column in the table above, so lane A's resolution never conflicts with it. Details in `docs/tasks/M57r-B-review-10-platform-fixes.md`, "Decisions made".

| # | Resolution | Test |
| --- | --- | --- |
| 1 | The uninstaller removes only its tracked files and `_internal`; setup refuses a folder overlapping the saves or app data (wizard and silent) | smoke: sentinel survives uninstall; overlap refused; `test_release_workflow.py` |
| 2 | Loopback `Host` (the game's own port when installed), own `Origin` on writes, instance token on desktop writes | `test_api_desktop.py` (14 Host/Origin cases, token refusals) |
| 3 | Last round, outcome action and closure in one transaction (`repository.apply_in_session`) | M47/M48/M49: injected failures at the action and the closure, after the commit, two simultaneous Accepts and Skips |
| 4 | Negotiation ranges from the nominal zone, centred once and nested; asymmetric zones; concession jitter; talk effects by direction; fees from shown centres; the rival's offer as a band (ruling 2) | paired-state tests (talks, meetings, media, a negotiation's range); 400-seed estimator test |
| 19 | Attempt ordinal in the negotiation key; refused closes cool off | `test_a_second_deal_this_month_draws_afresh_and_a_failed_close_cools_off` |
| 20 | Failed scoring call: retryable, nothing played; calls outside the write lock; moved conversations refused | M47/M48 failure, lock and moved-round tests |
| 21 | Engine-template outcome after the LLM's tone; unit-aware number, amount-word and outcome-claim checks | `test_m57r_b_llm.py`, `test_wording_that_contradicts_the_decision_is_replaced` |
| 22 | Atomic per-folder, per-month reservation of each call's bound; spend in a `finally`; `source` a `Literal` | `test_m57r_b_llm.py` (race of 20), M47 spend and nearly-spent tests |
| 23 | Updater pins hosts, scheme and paths, one checksum record, size cap, re-hash, old installers deleted; setup waits for the game (`/WAITPID`), `/SUPPRESSMSGBOXES`, `/LOG` | `test_desktop.py`; smoke: in-game update to a fake next version reaches its health check |
| 24 | Releases gated on `main` with green `check` and `e2e`; `M9.spread.africa` a known miss (ruling 6) | `test_release_workflow.py`, `test_m9_balance.py` |
| 25 | An unmeasurable V3 row fails; `V3.ai.survival` its own owned target | `test_known_misses.py` |
| 26 | M48's and M49's word tests in M47's form, planted before the opening, system prompt checked, percent and 2-decimal forms | `test_no_hidden_value_reaches_a_prompt_or_the_api` (M48, M49) |
| 27 | `weekly-m52-2100`; the tool exits 1 on a failure; every weekly file in a scheduled target; nightly M53 and M50 tests | `test_weekly_targets.py`, `test_m53_balance.py`, `test_m50_balance.py` |
| 31 | Constant conversation system prompts; names as JSON context | `test_conversation_system_prompts_hold_no_name` |
| 32 | conftest pins `TST_CONVERSATION_ADAPTER=mock` and an empty key | `test_tests_use_the_mock_for_conversations_and_no_key` |
| 33 | Stored copy checked against its hash at load; results keyed by slug and hash | `test_m57r_b_saves.py` |
| 34 | `0071_m57rb` (`start_turn = created_turn`); `SaveTooNewError` for a newer build's save | `test_m57r_b_saves.py` |
| 35 | The e2e cache key covers the folder's starting JSON files | `test_the_key_covers_the_profiles_starting_state` (both orders) |
| 36 | M51's carried rules as bounded known misses; family check in the call-site guard; owners named M57; purity bans every `tst.*` outside `tst.sim`. The V4 rows' readings: M57 (decision 18) | `test_rng_call_sites.py`, `test_sim_purity.py`, `test_known_misses.py` |
| 37 | CLAUDE.md §5's `--company-name`; `turn_to_ym` at five sites. ADR-0013's two corrections wait for lane A's merge (its file) | — |
