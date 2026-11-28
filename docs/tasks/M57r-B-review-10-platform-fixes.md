# M57r-B: Review 10's platform fixes, and v6.0.1 (lane B)

**Goal:** close every review 10 finding owned by lane B (the installer, updater and local API; crash-safe conversations; hidden values; LLM handling; saves; and guards that can't fail), then release **v6.0.1**. **No new features.**

**Findings:** `docs/reviews/review-10-consolidated.md`, items **1–4, 19–27 and 31–37** (with `codex-review-10.md` and `review-10.md` for detail) · **Rulings:** the consolidated file's "Product manager rulings" 1, 2 and 6 · **ADRs:** 0004, 0005, 0023, 0026 · **Depends on:** `m59-done` · **Lane:** B, alongside M57r-A

## Authority

CLAUDE.md §9 asks a session to stop on a P1 defect or anything touching a hidden-value guarantee. Items 1–4 are already reported and ruled: **fix them; don't stop for them.** These fixes strengthen the guarantee. Stop only for a new P1 the reviews didn't name.

## Lane

- Its own session, in its **own clone or worktree**, on branch `m57r-b` from `main`.
- **Owns:**
  - `packaging/`, `tst/desktop/`, `tst/api/`, `tst/conversations/`, `tst/db/`, `tst/profile/`;
  - `tst/sim/negotiation/`, `tst/sim/talks/`, `tst/sim/meetings/`, `tst/sim/media/talent.py`;
  - `tst/balance/known_misses.py`, `tst/balance/v2.py` and the balance tests and tools named in items 25–27;
  - `.github/workflows/release.yml`, `weekly.yml` and `nightly.yml`;
  - `tests/conftest.py`, `tools/e2e_cache.py`;
  - CLAUDE.md §5 and new migrations.
- **Must not edit** lane A's files (`tst/sim/**` otherwise, `backend/data/**`, `tests/money_guard.py`, `tst/modes/custom.py`, ADR-0013, `determinism.yml`).
- **No fixed merge order** with M57r-A.
- CLAUDE.md §9's decision rules apply.

## Sub-tasks (commit after each; each with the test named in the finding)

1. **Installer, updater and local API** (items 1, 2 and 23, ruling 1):
   - the uninstaller removes only its own tracked files, and setup refuses an install directory that overlaps the game's data;
   - local API middleware rejects a foreign `Host` and, on any non-GET, a foreign `Origin`; desktop writes also require the instance token;
   - the updater pins scheme, host and repository path for assets and redirects, parses one checksum record for the named installer, caps bytes at the asset size, re-hashes just before launch, and deletes older installers;
   - **smoke steps:** a custom install directory with a sentinel file survives uninstall; a full in-game update against a fake release reaches the new version's health check.
2. **Crash-safe conversations** (item 3): the terminal round, the outcome's action and the closure in one `write_session`, or a `closing` status with an idempotent action keyed by the conversation id, finished on open. **Tests:** an injected failure at each commit boundary, and two simultaneous Accepts, each sign exactly once.
3. **Hidden values** (item 4, ruling 2):
   - loyalty changes shown qualitatively;
   - negotiation ranges anchored to a centre drawn once, narrowed by nesting with a floor above the offset, from an asymmetric zone, with hidden jitter on concessions;
   - creative-lead fees priced from the shown range centres, rounded to a coarse step;
   - the rival's approach offer shown as a band in both places.

   **Paired-state tests** for negotiations, meetings, talks and media: vary one hidden field, and assert the API JSON, prompts and public view are byte-identical. Also fix M48's and M49's hidden-word tests (item 26) to M47's form, checking the system prompt, with percent and decimal forms.
4. **LLM handling:**
   - deal draws keyed with an attempt ordinal, and the cooldown applied to failed closes (item 19);
   - a failed call is retryable and never scored `neutral`, and calls run outside the write transaction with the round number re-checked (item 20);
   - outcome and commitments rendered from engine templates, with wording limited and checked for its outcome class and money and percent units (item 21);
   - a per-folder, per-month atomic reservation of each call's bounded cost before the call, spend recorded in a `finally`, and `source` as a `Literal` (item 22);
   - the company name passed in the JSON context, not the system prompt (item 31);
   - conftest pins `TST_CONVERSATION_ADAPTER=mock` and an empty key (item 32).
5. **Saves and scenarios:**
   - check a custom scenario's stored hash at load (a missing row or a mismatch raises a domain error), and key results by slug and hash (item 33);
   - a new migration sets `start_turn = created_turn` where `created_turn > 0` (never editing 0066), and a save from a newer build raises "made by a newer version" (item 34);
   - the e2e cache key covers the profile's starting state, tested warm to empty and empty to warm (item 35).
6. **Guards that can fail:**
   - releases only from a commit on `main` with green `check` and `e2e` (item 24);
   - `M9.spread.africa` as a known miss, owned by M57 and bounded at 10/10 seeds (ruling 6);
   - V3's row emitted as a failure when unmeasurable, and the AI-first bankruptcies as their own owned target (item 25);
   - M52's 2100 target in `weekly-m52`, exiting non-zero on error, and a guard that every `weekly` test file is in a weekly target (item 27);
   - nightly tests for M53's and M50's targets (item 27);
   - the housekeeping of item 36: M51's carried rules in `known_misses.py`, the call-site guard checking families, readings refreshed, the purity scanner banning every `tst.*` outside `tst.sim`;
   - the docs drift of item 37.
7. **Close-out and v6.0.1:**
   - re-record what moves, with reasons; fill in the consolidated file's Resolution column for lane B's items;
   - merge with `Milestone-Tag: m57r-b-done` and confirm the tag;
   - add a `## v6.0.1` section to the CHANGELOG (bullets, player-facing: the uninstall fix, the update and local-security fixes, conversations that survive a crash, fairer negotiations) through a docs pull request;
   - once that is on `main` with green checks, dispatch `release.yml` with version `6.0.1` from `main`. Confirm the release, its installer and its checksum, and report.

## Acceptance criteria

- [ ] Every lane B item is fixed with its test, or explained in "Decisions made".
- [ ] The paired-state tests pass for every conversation kind and media; M48's and M49's word tests fail on a planted leak.
- [ ] The installer smoke test proves the sentinel survives uninstall, and that an in-game update completes.
- [ ] `make check`, `make check-timing`, `determinism` and CI `e2e` green; merged with `Milestone-Tag: m57r-b-done`; v6.0.1 published from `main`.

## Decisions made

1. **Branch `m57r-b`**, as the instructions name it (the session's default branch name was another).
2. **The local API's guard (item 2).** `tst/api/local_guard.py`, outermost middleware: every request's `Host` must be a loopback name (`127.0.0.1`, `localhost`, `[::1]`, plus `TST_ALLOWED_HOSTS`, which conftest sets to the test client's `testserver`); in the installed game (a desktop context) the port must be the server's own. A write (not GET, HEAD or OPTIONS) with an `Origin` must come from such a host, in the installed game exactly `http://<its Host>`; `null` and foreign origins are refused (403 `foreign_request`). A write with no `Origin` passes (no browser page sends a cross-origin write without one). Desktop writes (key, import, Update now, Later) also need the instance token in `X-TST-Instance`, served to the game's own page as `write_token` on `GET /api/desktop` (only that page can read it: the Host check stops a rebound name, and no CORS header is ever sent).
3. **The updater (item 23).** Asset URLs must be exactly `https://github.com/Reece77/Tech_Executive_Tycoon/releases/download/<tag>/<name>`; redirects only to https on `github.com`, `objects.githubusercontent.com` and `release-assets.githubusercontent.com`; a release without a listed size is not offered; the checksum file must be one `sha256sum` record naming the installer; a download longer or shorter than the listed size is refused; older `TechStartupTycoon-Setup-*` files are deleted once the new one is verified; the installer is hashed again just before it runs. `TST_UPDATE_SOURCE` (only `http://127.0.0.1:<port>`; anything else is ignored and logged) points the check and the downloads at a fake release for the smoke test.
4. **The smoke test found two real faults in the in-game update** (review 10's F38: it had never run end to end). Setup started while the game was still closing (it closes a second after launching setup), and Restart Manager cannot close a game with no window: unattended, setup waited on a prompt nobody saw (first run), then, with `/SUPPRESSMSGBOXES`, aborted and rolled back (second run, from its `/LOG`). The game now passes `/WAITPID=<pid>`; setup's `InitializeSetup` waits up to two minutes for that process to exit; `/SUPPRESSMSGBOXES` and `/LOG=<app data>/logs/update-install.log` stay (the smoke test prints that log on a failure). The third run installed the update and the new version answered its health check with the save.
5. **The uninstaller (item 1)** removes Inno Setup's tracked files and `{app}\_internal` only. Setup refuses (wizard page and `PrepareToInstall`, so silent installs too) a folder that is, holds or sits inside `Documents\Tech Startup Tycoon` or the app-data folder, or is the Documents or profile folder itself, or a drive root.
6. **Releases (item 24)** run a `gate` job first: the commit must be an ancestor of `origin/main` and its latest `check` and `e2e` check runs must have succeeded; `publish` needs it. A pull request skips the gate and still builds and smoke-tests (nothing is published).
7. **Crash safety (item 3)** by one transaction rather than a `closing` status: `repository.apply_in_session` is `run_action`'s body inside the caller's `write_session`; the profile bookkeeping (`after_action`) runs after the commit. M47's "an agreement waits out a busy save" test is removed, not weakened: the second transaction it covered no longer exists (a busy save now refuses the whole finish before anything changes, retryably).
8. **Negotiations (item 4, F2).** The range's width is a share of the kind's nominal zone (`2 x spread[kind] x aspiration`), not the true zone, whose width also gave the reservation away; its centre is drawn once and later ranges nest around it, never narrower than the greatest offset. `reservation_skew` 0.5 (asymmetric zones, also applied to given zones, so a listed target's board bar no longer follows from its opening) and `concession_jitter` 0.2 (each round's concession x 1 ± 0.2, the cap at `move_step` x 1.2) are new keys. **Rule 1 tuning:** at 0.3 jitter, M47's 58.5 target 2 missed (the strong script +9.47% of the zone on seeds 1-3, band 10-25%; CI shard 4); swept (skew, jitter) over 0.3-0.5 x 0.15-0.3: lower skew lifts the strong script but drops estimator (c) below its floor, so skew stays 0.5 and jitter goes 0.3 -> 0.2: strong +10.1% (seeds 1-3) and +10.5% (1-10), weak -7.4% (1-10, band -15-0%), always-threaten loses 100%, nobody beats a reservation. **They live as defaults on `NegotiationBalance`, marked tunable-exempt,** because `backend/data/` is lane A's; once M57r-A merges (CLAUDE.md §9 rule 8) they move into `balance.yaml` (follow-up). Readings on 400 seeds (`tests/unit/test_m57r_b_negotiation_leaks.py`, three throwaway rounds), at the tuned keys: median miss of the reservation, as a share of the zone, (a) midpoint extrapolation 16.7% (5.2% on M47's engine), (b) counter inversion 78% (88%), (c) `2 x price − opening` 11.8% (7.5%, M47's rounding already hid most of it); the test's floor is 10%. M47's unit tests that encoded the symmetric zone and the uncapped step now assert the asymmetric bounds and `move_step x (1 + jitter)`.
9. **Talks (item 4, C05).** Every talk effect a hidden factor scales (loyalty, morale, a press talk's brand and credibility) is shown by direction only (`change` ±1, words); persona points and stress (published tables) stay exact. **Meetings' outcome effects stay exact**: a director's confidence, an analyst's target, sentiment and credibility are public numbers on their own screens, so the change is visible there anyway; the paired-state tests hold meetings byte-identical through every answer, talks through the outcome.
10. **A creative lead's fee (F3)** is priced from the shown ranges' centres and rounded to a 1-2-5 step at or below 5% of it (`talent.FEE_STEP`, display rounding, tunable-exempt like the negotiation's `NICE`). The sign action's up-front cash check in `tst/sim/media/actions.py` (lane A's file) still prices from the true values, so it can differ from the shown fee by a few percent: aligned once M57r-A merges (follow-up).
11. **A rival's approach offer (F22, ruling 2)** is the 1-2-5 band at or below 20% of it (8-20% wide) that holds it, in the retention talk's facts and in the rivals API (`offer_lo_cents`, `offer_hi_cents`; `offer_cents` is gone); the counter dialog starts at the band's top. The retention negotiation's own zone is unchanged.
12. **Item 19's key** is `(kind index, *deal key, attempt)` for every negotiation (outcomes change; conversations are outside the turn, so no golden snapshot, fixture or state cache moves). ADR-0013's table (lane A's file) names the new key part: follow-up.
13. **LLM calls (items 20, 22).** `ConversationCallError` (503) and `ConversationMovedError` (409) are retryable domain errors in `tst/conversations/common.py` (`tst/sim/errors.py` is lane A's). A call's bound is its prompt at one token a character plus 1,500 output tokens at the adapter's model price; reservations live in `<saves>/llm_reservations.json` under an OS file lock and lapse after 10 minutes (a crash costs at most that); template mode shows once what is left (open reservations aside) can't cover a typical call (4,000 prompt characters). A failed reply or suggestions call still falls back to the template (only scoring is required).
14. **Reply checks (item 21)** compare money with its unit (`$12` ≠ "12 months"; `$1,200K` ≠ `$1,200`) and percentages as percentages, refuse amounts in words (hundred, thousand, million, billion, dozen, and a number word before percent or dollars), and, for negotiations, any agreement or walk-away claim the engine did not decide.
15. **Saves (items 33, 34).** `CustomScenarioMismatchError` and `SaveTooNewError` live in `tst/db` (409 each). Custom results are keyed `<scenario>@<sha256>`; records written before are re-keyed on read by their own `sha256` field. `0071_m57rb` is data only (`start_turn = created_turn` where `created_turn > 0` and `start_turn = 0`; `schema_version` 71).
16. **The e2e cache key (item 35)** adds the folder's JSON files as the build found them; a warm and an empty folder never share an entry (CI's per-shard caches may miss more often: correctness first).
17. **V3 (item 25).** An unmeasurable margin row is now a failure with an infinite score, which no bound covers: **the weekly `test_v1_to_v4_ten_years` reports `V3.ai` as a failure until M57 makes the AI-first scripts survive.** The cause is its own row, `V3.ai.survival` (neither AI-first script bankrupt on more than 5 of 10 seeds, the band M57r-B chose so a median margin exists), a known miss owned by M57 bounded at 10 of 10 (the reading on M46 and `main`). For the product manager to confirm or re-band.
18. **Known misses (rulings 6, item 36).** `M9.spread.africa` (M57, 10/10 seeds; the test fails on any other empty cell). M51's three carried rules are rows `M51.T2.<rule>` bounded at M51's readings (shortfalls 0.09, 0.13, 0.10 against the 10% drop) and `m51.TARGET2_CARRIED` reads them; the test judges every rule. The two `v6 performance` rows are owned by M57 (a milestone id). **The four V4 rows' readings (M35b-M43a) were not refreshed:** their scripts never negotiate and M57r-B changes no balance key, so a weekly run would give `main`'s numbers; M57, the next balance pass, re-reads every row (follow-up).
19. **Weekly and nightly guards (item 27).** `weekly-m52-2100` (in `weekly.yml`'s default parts) runs target 4's pytest test; `tools/m52_save.py` exits 1 on an error, an integer past int64 or a miss past its bound; `tests/unit/test_weekly_targets.py` fails when a file with a `@pytest.mark.weekly` test is in no scheduled weekly target. New nightly `test_m53_balance.py` (62.5 targets 2-4) and `test_m50_balance.py` (60.3 targets 2-3; target 4 stays reported, M50 decision 15).
20. **The call-site guard (item 36 b)** checks each package's `draws.gen` families: a declared key-family constant, a module or sibling-module int constant, or a literal (pharma's `family` pass-through helper allowed), with no family value under two names. A static check cannot prove two sites' full keys differ; the families are the part that can be checked. The purity scanner bans every `tst.*` outside `tst.sim`.
21. **Docs drift (item 37).** CLAUDE.md §5's `new-game` gains `--company-name`; `loader.py`, `routers/editor.py` and `balance/m14.py`, `v4.py`, `v5.py` use `turn_to_ym`. The unused `finserv` fraud stream and the catastrophe key's month are in `rng.py` and ADR-0013, lane A's files: follow-up.

## Follow-ups

- Once M57r-A merges (CLAUDE.md §9 rule 8): move `negotiation.reservation_skew` and `concession_jitter` into `balance.yaml`; price `SignLead`'s up-front cash check in `tst/sim/media/actions.py` with `talent.offer_fee_cents`; ADR-0013's `negotiation` key gains `attempt`, its `finserv` fraud stream and catastrophe key are corrected (item 37).
- M57: `V3.ai.survival` (and so `V3.ai`), `M9.spread.africa`, M51's carried rules; refresh the four V4 rows' readings; confirm `V3.ai.survival`'s band of 5 of 10.
- The installer is still unsigned (F36): a code-signing certificate, or a signed manifest, would give authenticity beyond the checksum.
- The COO and Ask-why prompts still format the company name into their system prompts (F24 names them; outside conversations).
- Meetings' outcome effects could be shown qualitatively too, if the product manager wants every hidden-scaled change qualitative (decision 9).
