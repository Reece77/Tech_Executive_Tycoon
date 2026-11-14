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

Engineering and design gaps the spec and ADRs left open (CLAUDE.md §9), decided and recorded here.

- **Family none is a true no-op.** No `Family` record, no rows, no draws: `founder_month` and `next_budget` call into `tst/sim/family/` only when `state.family` exists. Golden snapshots unchanged (11/11 passed on the branch, Family none); the state-cache check runs over family games in `tests/integration/test_api_family.py`.
- **Family members are people** (`person` rows, role `family` outside a company) with the player's `reveal_state` view, started as a stranger's ranges. The live set (`load_state`, `live_view`) now includes the family's people. **Person rows now persist `role`, `level` and `is_founder` changes**; before M36 no flow changed them, so existing saves and goldens are unaffected.
- **Setup:** children's ages 0–40 (`family.start_child_ages`), at least 18 years younger than the founder; a setup child has already grown as development would have made them (no noise); choices already past at setup default to standard school and university.
- **Children's development** uses §3's growth formula on every skill with the child's general ability (10 × the mean skill) as CA, × `family.child_growth` × e × closeness. University multipliers apply from 18 to 22; an MBA's for 24 months (`family.mba_months`); a degree's skills × `family.education.degree_mult` (1.5). Education is a one-off cost (`family.education.cents`, from the dossier's 2025 figures).
- **Seeing a child:** ranges narrow each month by `family.reveal_rate × time / 20` and by `family.education.reveal` at each education choice; potential is shown as the usual phrase and its half-width never falls below `family.pa_hw_floor` (10).
- **Joining:** an offer pays the role's band midpoint at the level; "the role matches their interests" means a role whose interest weight for one of the child's interests is above the role's mean weight. A refusal sends the child their own way with `family.own_way_rate` (a minor event; founding a rival company is a follow-up).
- **Readiness points** = displayed CEO-seat fit + 0.5 a year in the group (up to 8) + 1 per executive seat held + (board confidence − 50) / 10; bands at 10, 14 and 17 (`family.ready.*`).
- **Staff reactions:** on a family member's promotion, the unit's others at the old level or above are "passed over"; ratings are their displayed role ratings.
- **Succession hand-over:** the heir's employment becomes the founder's (role `founder`, level exec) at the player company; the old founder's ends (`retired`); the heir takes the founder's board seat and the old founder a new common seat as adviser (exempt from the vacated-nominee rule). The heir's energy is the founder's (or Chair's) less family time. The heir's own life starts fresh; the old founder's life, shares, investments and foundation stay theirs except at a **health** succession, when the estate settles and everything left passes to the heir.
- **Estate tax applies only at a health succession to an heir** (and, in M37, death). A professional CEO on health grounds leaves the founder's estate in place (the founder is alive and still plays). Private shares are valued at 28.1's value per share (the last round's price without balances).
- **Gift tax** is the region's rate on the part of a gift above what lifetime gifts leave of the exemption (unified, as the US); the trust costs `family.trust_setup_cents` once and no gift tax; shares given to the foundation count toward the giving term of the generation's legacy (not M24's `legacy_of`, so earlier guards are unchanged).
- **Family control** = the family's people (not ex-partners) and the trust holding at least `family.control_bp` (25%) of fully diluted shares; a loss is counted when it falls below after having it (checked at December, a divorce, an estate and foundation gifts).
- **The adviser's stance** comes from their persona (Visionary + Reckless against Ruthless + Beloved): a bold adviser backs rounds, loans and high-risk pitches and doubts the rest; a cautious one the reverse; the wording is a template in their strongest trait's voice (LLM wording is a follow-up). "That director's board confidence falls (−5)" is applied to every voting director when the player approves something the adviser opposed.
- **Board removal with a successor** resets each voting seat to `board.start` (a new leader's patience) and opens the succession choice next month; the readiest heir at least developing takes over, else a professional CEO.
- **A professional CEO** is 25.6's CEO record at any stage, the best senior-or-above insider by displayed fit, else an executive found by a search (stream `family`, key `(head, 3, 0)`).
- **Life events** use stream `family` keys `(head_id, 0, k)` (k 0 a partner, 2 a child), `(head_id, 2)` health each January, `(person_id, 1)` development, `(person_id, 4)` an offer turned down.
- **Unlock:** Family is M29 system 24 (23 is M31's platforms), opening when a family exists.
- **Estate-tax data** (`estate_tax.*`, `docs/v5-research/estate-tax.md`): one jurisdiction per region (US federal, UK, Japan with a spouse and two children, India, Brazil's 8% cap, South Africa, Australia), rate and exemption by year from 2010; the US uses the OBBBA's $15M from 2026.

### §45.8 targets (10 seeds, `tools/m36_targets.py`, 2026-11-14)

| # | Target | Reading | Result |
|---|---|---|---|
| 1 | Nothing moves without a family | goldens 11/11 unchanged; full suite and guards as on `main` | PASS |
| 2 | Family time matters | time 10 above 50 on 10/10; neglect with burnout divorces 10/10 | PASS |
| 3 | Upbringing matters (≥ 3 points) | median CEO-seat score at 22: 8.28 vs 7.21, gap 1.07 | **carried** |
| 4 | Succession is a real choice (±20%) | median value 10 years on: heir $1.42B vs CEO $2.86B (0.49); heir within 20% or ahead on 3/10 seeds | **carried** |
| 5 | Estate planning pays | control lost 7/10 without planning, 0/10 with a trust | PASS |
| 6 | Turn time | a family adds one month of family rules per head; the timing suite passes | PASS |

- **Target 3, tuned and carried (rule 1).** `family.child_growth` 0.55 → 0.30 (a 22-year-old lands at junior-to-mid level). With §45.3's multipliers (school e ≤ 1.2, university ≤ 1.3, closeness × 0.8–1.2) and §3's headroom (growth slows as ability nears potential), the gap cannot reach 3 points: the sweep found 1.07 at the spec's values and 2.4 even with e doubled (elite 2.0, top 2.5). Reaching 3 would need multipliers far from the spec's, which is a design change: Reece to decide whether to raise them or move the target.
- **Target 4, carried.** No `family.*` or `estate_tax.*` key moves company value. The gap is structural: in the CEO arm two decision-makers act (the CEO with every authority, and the old founder as Chair running the script), and the CEO arm listed earlier on several seeds; the heir arm has one. Neither is always right (seeds 4, 9 and 10 within 20% or the heir ahead), but the median favours the CEO. A follow-up for Reece: whether the family head should act less once a CEO runs the company (e.g. Chair energy for the family head), or the target compare like with like.
- **Target 5's scenario:** a seeded founder stake of 26–50% of a listed company (the stakes at which a family holds control), $10B of shares, 2030's US rules; the trust holds 80% of the shares.
- **pt-family** opens at $8B of the founder's shares at the save's share price; the market reprices toward the company's fundamentals from the next month (its value is near $1B), so the estate quote falls after Continue.

## Follow-ups

- Reece: targets 3 and 4 above (multipliers or target for upbringing; the family head's role beside a professional CEO).
- The adviser's opinions in the LLM's voice within §16's budget (templates now), and opinions on one-off actions from the screens (the engine hook `adviser.opinion_on_one_off` exists, unused).
- Trust distributions to heirs, and dividends on trust and foundation shares (they hold shares; nothing pays out yet).
- A child who goes their own way founding a rival company record (the event and the flag exist).
- The heir's own partner and children start empty; life events give them a family from then on.
- A secondary offering when an estate's sale exceeds the free float (§25.5) is not modelled; the estate sells into the float at the share price.
- Dynasty mode and death (M37); the Hall of Fame family tree reads `dynasty` but the Game over screen does not show it yet.
