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

(filled in by the session)

## Follow-ups

(filled in by the session)
