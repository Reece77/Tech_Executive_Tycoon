# M36: Family and succession (v5, lane D)

**Goal:** the founder has a family, and the game can outlive the founder. A partner and children grow with their own stats, personalities and interests. Family time eases stress but costs energy, and neglect strains the relationship. Children are educated and mentored, and can join the company. Succession passes the company to an heir, whom **the player then plays**, or to a professional CEO, with the old founder on the board as an adviser. Estate tax and planning decide whether the family keeps control.

**Formulas:** `docs/formulas.md` §45 (all), with §2, §7, §14, §18.8, §25, §32, §37 · **ADRs:** 0002, 0003, 0005, 0013 (stream `family` 59), 0018 · **Outline:** `docs/v5-outline.md` · **Research:** a short estate-tax dossier, written by this milestone (sub-task 1) · **Depends on:** M24, M26 (built) · **Lane:** D, a fourth lane beside M30, M31 and M32

## Reece's decisions (2026-11-14)

- **Play the heir.** The old founder becomes a board adviser with opinions.
- **Dynasty mode past 2039 comes later** (M37). In M36, succession can happen in the normal campaign: by choice, through the board, or on health grounds for founders who start older.

## Lane

- Its own session and branch (`m36-family`) from `main`.
- **M36 owns:** new `backend/tst/sim/family/`; `backend/tst/sim/founder/` where the founder's energy, stress, persona, legacy and personal account join it; succession's hand-off in the board code (`§14`'s removal path: succession instead of game over when an heir or CEO is named); the Family screen and the founder profile's family tab; `family.*` and `estate_tax.*` in `balance.yaml`; `tst/balance/m36.py` (new).
- **M36 must not edit:** M31's `platforms/`; M30's performance changes (merge `main` often); M32's power code; automation (`automation/`), except reading it for the family head's mode.
- **Shared files:** `balance.yaml`, `docs/formulas.md` (notes in §45 only), CHANGELOG, data dictionary, ADR-0013. Keep both sides.
- **Golden snapshots:** with Family set to none they must stay unchanged. New-game golden saves keep Family none.
- **CLAUDE.md §9's decision rules apply.**

## Out of scope

Dynasty mode past 2039 and the founder's death within it (M37: §45.6's death trigger is built and tested, but cannot happen before 2040 until M37). Family members founding rival companies beyond an occasional event and a rival entrant record. Family-office changes beyond its use in estate planning.

## Sub-tasks (commit after each)

1. **Research and data:**
   - Estate and gift tax by region (rates, exemptions and their history, 2010–2025) in a short dossier, `docs/v5-research/estate-tax.md`, with sources.
   - Education tiers and costs.
   - `family.*` and `estate_tax.*` keys with comments; stream `family` in ADR-0013; the family-member and relationship records; the migration and data dictionary.
   - **Test:** loader validation.
2. **The family** (§45.1): the setting, generating members, life events. **Seeded test:** the same seed gives the same family.
3. **Family time, the relationship and its strain** (§45.2), including divorce and the partner as a shareholder. **Property test:** the personal book and the cap table balance through a divorce.
4. **Children growing up** (§45.3): development, education choices and revealed ranges. **Hidden-value test:** no child's potential or hidden trait reaches the API or a prompt.
5. **Heirs in the company** (§45.4): joining, mentoring, readiness bands and staff reactions.
6. **Succession** (§45.5):
   - by choice, on health grounds, and through the board;
   - the critical choice;
   - playing the heir (the player's founder person changes; every founder-keyed record moves cleanly);
   - the family-head mode with a professional CEO;
   - the adviser's opinions.
   - **Test:** after succession, the save reloads cold, the new founder's energy, stress and persona are as §45.5 says, and the old founder is on the board.
7. **Estate planning and tax** (§45.6): gifts, trusts, the foundation route, the estate paying tax and selling shares.
8. **The dynasty legacy** (§45.7) and the Hall of Fame's family tree.
9. **Screens:**
   - a **Family** screen: members, ages, relationships, education, ratings as ranges, readiness, family time;
   - the founder profile's family tab;
   - succession and estate planning on the Group or Founder screen;
   - M29 unlocks: Family when a family exists;
   - glossary entries (estate tax, trust, readiness) and Explain on readiness and estate quotes.
10. **API, CLI, e2e, balance and close-out:**
    - **CLI:** `tst family`, and `tst succession --heir <id>`.
    - **Playwright:** (a) start a game with a partner and two children and set family time; (b) educate a child at 18 and see their ranges narrow; (c) a succession to an heir makes them the player, and the adviser comments on the next proposal.
    - **A practice save** `pt-family`: a founder aged 62 in 2034 with a partner, three adult children (one in the company) and $8B in shares, no estate planning.
    - **§45.8 targets** printed and recorded. Tune only `family.*` and `estate_tax.*` (rule 1).
    - CHANGELOG, data dictionary, README index row.

## Acceptance criteria

- [ ] With Family set to none, every earlier guard, the golden snapshots and the state-cache check are unchanged.
- [ ] A succession to an heir moves the player to the heir cleanly, survives a cold reload, and puts the old founder on the board (tests and e2e).
- [ ] The personal book, the cap table and the estate balance through divorce, gifts, trusts and estate tax (property tests).
- [ ] No family member's potential or hidden trait reaches the API or a prompt (hidden-value test).
- [ ] §45.8 targets printed and met, or carried with a recorded decision.
- [ ] `make check` and CI `e2e` green; merged through a pull request per CLAUDE.md §6 with the trailer `Milestone-Tag: m36-done`.

## Manual check (Reece, after merge)

Load `pt-family`. Look at your children, set up a trust, and mentor the child in the company. Then step back and play on as the heir, and read what your old founder thinks of your first big decision.

## Decisions made

(filled in by the agent)

## Follow-ups

(filled in by the agent)
