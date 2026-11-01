# Data dictionary

Column-level reference for a save file (`saves/<slug>.tst.sqlite`). Kept current with the Alembic migrations in `backend/migrations/versions/`; ORM models are in `backend/tst/db/models.py`.

- **Schema version:** 19 (migrations `0001_initial`, `0002_people`, `0003_hiring`, `0004_inbox`, `0005_org`, `0006_search_plan`, `0007_plan_focus`, `0008_products`, `0009_finance`, `0010_stage_board_history`, `0011_board_nominee`, `0012_inbox_archive`, `0013_rivals`, `0014_free_agents`, `0015_relationships`, `0016_events`, `0017_save_display_name`, `0018_person_rating_log`, `0019_coo_answer`). Alembic also records its revision in its own `alembic_version` table.
- **Conventions:** integer ids; money is integer US cents in `*_cents` columns (ADR-0003); every time-varying row carries a `turn` (0 = January 2010, ADR-0006). History tables are append-only and never updated or deleted (ADR-0004 §6).
- **Connection pragmas:** `journal_mode=WAL`, `foreign_keys=ON`, `synchronous=NORMAL`.

## save_meta

One row describing the save. Current-state table (updated in place each turn).

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Always 1. |
| `name` | VARCHAR(64) | no | Save slug, also the file name stem. |
| `master_seed` | BIGINT | no | 63-bit master seed; every RNG stream derives from it (ADR-0002). Never changes. |
| `scenario_id` | VARCHAR(64) | no | Scenario the game started with (`scenarios.yaml` id). |
| `difficulty` | VARCHAR(16) | no | `easy`, `standard`, `hard`, or `ironman` (ADR-0011). |
| `created_turn` | INTEGER | no | Turn the save was created at (0). |
| `current_turn` | INTEGER | no | Next turn to be played. Incremented once per committed turn. |
| `data_hashes` | JSON | no | `{file name: SHA-256}` of the data files used to create the save (line endings normalized), so later data changes can be detected (ADR-0008). |
| `schema_version` | INTEGER | no | Current schema version; each schema migration sets it (8 after `0008_products`). |
| `next_person_id` | INTEGER | no | Next person id to assign. Ids are never reused, because people leave the live state (M1b sweep rule 2). |
| `next_search_id` | INTEGER | no | Next search id. |
| `next_offer_id` | INTEGER | no | Next offer id. |
| `next_employment_id` | INTEGER | no | Next employment id. |
| `next_unit_id` | INTEGER | no | Next org unit id (M2a). |
| `next_plan_id` | INTEGER | no | Next hiring plan id (M2a). |
| `next_product_id` | INTEGER | no | Next product id (M3a). The 12 incumbent products take 1..12 in a new game. |
| `game_state` | VARCHAR(16) | no | `active`, `bankrupt` or `founder_removed` (ADR-0018 §4). Once ended, turns and actions are refused (HTTP 409); reads still work (M4a). |
| `ended_turn` | INTEGER | yes | Turn the game ended; null while active (M4a). |
| `display_name` | VARCHAR(80) | yes | The save's name on the Saves screen; null shows `name` (M7b, `0017_save_display_name`). Renaming a save changes only this; the company name and the file stay. Mapped as a deferred column, because migration 0013 reads `save_meta` through the current models. |
| `next_cap_entry_id` / `next_grant_id` / `next_safe_id` / `next_round_id` / `next_term_sheet_id` / `next_seat_id` | INTEGER | no | Next ids for the finance tables (M4a). |

## company

The player company, the 2010 incumbents (M3a, ADR-0017: `is_player` false, no people, no ledger, no decisions until M5) and, from M5, all rivals, handled by the same code (ADR-0010). Current-state table.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Company id. The player company is 1. |
| `name` | VARCHAR(80) | no | Display name. |
| `is_player` | BOOLEAN | no | True for the player's company. |
| `stage` | INTEGER | no | Company stage, 0 (solo founder) to 5 (conglomerate), spec §3. |
| `founded_turn` | INTEGER | no | Turn the company was founded; negative for incumbents (January of `founded_year` in `incumbents.yaml`). |
| `mission` | JSON | no | List of two `interests.yaml` keys (formulas.md §7); empty for saves made before M1b. |
| `work_policy` | VARCHAR(16) | no | The company root's work-location policy, `office` (default) or `remote` (formulas.md §13.9, M2a). Units without their own policy inherit it. |
| `root_product_id` | INTEGER | yes | Product the company root's members (the founder included) work on (formulas.md §11.3, M3a); null = none. No FK (added by `0008_products`). |
| `arr_milestone_cents` | BIGINT | no | Highest ARR milestone (`products.arr_milestones_cents`) already announced in the inbox; 0 = none (M3a). |
| `mrr_history` | JSON | no | MRR in cents at the last 13 month ends, oldest first: the sim's input to `g_6` (formulas.md 14.3) and board confidence (M4a). |
| `insolvent_months` | INTEGER | no | Consecutive month ends with cash below zero after phase 7; 3 is bankruptcy (14.7, M4a). |
| `stage_history` | JSON | no | `[stage, turn]` each time a stage was reached, oldest first; a new game starts with `[0, 0]`. Empty for saves from before M4b (migration `0010_stage_board_history`), whose "since" date is unknown. |

Cash is not stored here; it is the `1000_cash` ledger balance (ADR-0003).

## account

Chart of accounts, copied from `backend/data/accounts.yaml` when the save is created.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `code` | VARCHAR(64) PK | no | Stable account code, e.g. `1000_cash`, `6900_general_admin`. |
| `name` | VARCHAR(120) | no | Display name. |
| `type` | VARCHAR(16) | no | `asset`, `liability`, `equity`, `revenue`, or `expense`. |

## ledger_entry

One balanced double-entry posting. Append-only history.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Entry id; insertion order. |
| `turn` | INTEGER | no | Turn the entry belongs to. Starting cash is posted at turn 0. |
| `company_id` | INTEGER FK → company.id | no | Company whose books the entry is in. |
| `memo` | VARCHAR(200) | no | Short description, e.g. "Base overhead". |

Index `ix_ledger_entry_company_turn (company_id, turn)`.

## ledger_line

One line of a ledger entry. The lines of an entry sum to zero. Append-only history.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Line id. |
| `entry_id` | INTEGER FK → ledger_entry.id | no | Owning entry. |
| `account_code` | VARCHAR(64) FK → account.code | no | Account posted to. |
| `amount_cents` | BIGINT | no | Signed cents: debit positive, credit negative. |
| `division_id` | INTEGER | yes | M8 (migration `0020_divisions`; formulas.md 18.1): the division the line reports to (an `org_unit` id, no FK); null = corporate. A product's revenue, hosting and marketing go to its division; an employee's salary, benefits, office, tools, recruiting fee and severance to the division containing their unit. Lines before M8 stay null. Server default NULL, deferred in the ORM. |

Index `ix_ledger_line_entry (entry_id)`.

## turn_snapshot

Month-end KPIs per company per turn, written by phase 11. Append-only history.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Row id. |
| `turn` | INTEGER | no | Turn the snapshot closes. |
| `company_id` | INTEGER FK → company.id | no | Company. |
| `kpis` | JSON | no | `{cash_cents, monthly_burn_cents, headcount, payroll_cents, avg_morale, mrr_cents, arr_cents, founder_bp, board_confidence}`. `founder_bp` is the founder's shares in bp of fully diluted shares, rounded down, and `board_confidence` the average investor and independent director confidence, null without a board (M4a). Only companies with a ledger (the player until M5) get a row. `mrr_cents` is this month's subscription revenue and `arr_cents` 12 × MRR (formulas.md §11.8, M3a). `cash_cents` equals the `1000_cash` balance through this turn; `monthly_burn_cents` is the net cash decrease this month (0 if cash did not fall); `headcount` counts the company's `active` and `notice` employments (1 for the founder from turn 0). |

Unique index `ux_turn_snapshot_turn_company (turn, company_id)`.

## decision_log

Decisions applied each turn, for replay and narrative. Append-only history.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Row id. |
| `turn` | INTEGER | no | Turn the decisions were applied in. |
| `company_id` | INTEGER FK → company.id | no | Deciding company. |
| `kind` | VARCHAR(64) | no | `turn_decisions` for the per-turn `Decisions` object. |
| `payload` | JSON | no | Serialized `Decisions` (includes its `version`), or an action's fields. |
| `seq` | INTEGER | yes | Order of an action within its turn (1, 2, 3…; ADR-0014): player actions first, then delegate actions in the order phase 2 took them; null for the per-turn `turn_decisions` row. |
| `source` | VARCHAR(16) | no | `player` (re-applied by replay) or `delegate` (taken in phase 2, recomputed by replay and checked against this row; ADR-0015). Default `player` (M2a). |
| `actor_id` | INTEGER | yes | Person who took the action (the founder or a delegate); null for `turn_decisions` and `new_game`. No FK constraint (added by `ALTER TABLE` in `0005_org`). |

Index `ix_decision_log_turn (turn)`.

## turn_log

Engine log items produced during a turn (month-end report lines, later events). Append-only history.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Row id. |
| `turn` | INTEGER | no | Turn that produced the item. |
| `company_id` | INTEGER FK → company.id | yes | Company the item concerns; null for world-level items. |
| `kind` | VARCHAR(64) | no | Item type, e.g. `month_end`. |
| `message` | TEXT | no | Human-readable text. |

Index `ix_turn_log_turn (turn)`.

## People (migration `0002_people`, M1a)

Current-state tables, updated in place each turn (ADR-0004 §7). They hold **true values** used by the sim; the API never returns them (ADR-0007). Every attribute table keeps a `position` so the data-file order, which fixes the order of random draws (ADR-0013), round-trips exactly.

### person

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Person id. The founder is 1. |
| `first_name` | VARCHAR(40) | no | Given name (from `names.yaml` unless the player chose one). |
| `last_name` | VARCHAR(40) | no | Family name. |
| `region` | VARCHAR(32) | no | `regions.yaml` key. |
| `birth_turn` | INTEGER | no | Turn of birth (negative before 2010); age = `(turn − birth_turn) // 12`. |
| `role` | VARCHAR(64) | yes | `roles.yaml` role the person was generated for; null for the founder, who uses the best-fit role. |
| `level` | VARCHAR(16) | yes | Level the person was generated at (`junior` … `exec`); null for the founder. |
| `work_style` | VARCHAR(16) | no | `builder`, `operator`, `researcher` or `seller`. |
| `salary_expectation_cents` | BIGINT | yes | Expected annual salary in 2010 cents (formulas.md §2.8); null for the founder. |
| `is_founder` | BOOLEAN | no | True for the player character. |

### person_skill / person_personality / person_hidden

One row per attribute. Primary key `(person_id, skill)` or `(person_id, trait)`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER FK → person.id | no | Person. |
| `skill` / `trait` | VARCHAR(64) | no | `skills.yaml` key; `personality.yaml` trait; for `person_hidden`, a hidden trait or `potential_ability`. |
| `position` | INTEGER | no | Order within the data file (`potential_ability` comes last). |
| `value` | FLOAT | no | True value: 1–20 for skills and traits; 10–200 for `potential_ability`. |

### person_interest / person_tag

Primary key `(person_id, interest)` or `(person_id, tag)`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER FK → person.id | no | Person. |
| `interest` / `tag` | VARCHAR(64) | no | `interests.yaml` key, or the person's **true** behavior tag from `tags.yaml`. |
| `position` | INTEGER | no | Order the interest or tag was drawn in. |

### person_reveal

What one observer company knows about one attribute of a person (ADR-0007 as amended in M1a). Primary key `(person_id, observer_company_id, attribute)`. Displayed min/max are derived on read from the current true value, `hw` and `center_offset` (formulas.md §4); they are never stored.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER FK → person.id | no | Person observed. |
| `observer_company_id` | INTEGER FK → company.id | no | Company whose knowledge this is. |
| `attribute` | VARCHAR(64) | no | A skill, a personality trait, or `potential_ability`. |
| `position` | INTEGER | no | Skills, then personality, then PA (the order offsets were drawn in). |
| `hw` | FLOAT | no | Half-width of the range; only ever shrinks. 0 for the founding company's view of its founder's skills and personality. |
| `center_offset` | FLOAT | no | Fixed offset in [−0.5, 0.5] drawn when the record was created (stream `reveal`). |
| `last_updated_turn` | INTEGER | no | Turn of the last narrowing. |

### person_profile_reveal

When an observer learned a person's interests and work style (shown exactly from then on). Primary key `(person_id, observer_company_id)`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER FK → person.id | no | Person. |
| `observer_company_id` | INTEGER FK → company.id | no | Observer. |
| `revealed_turn` | INTEGER | no | First interview or network intro; 0 for the founding company and its founder. |

### person_tag_reveal

Behavior tags an observer has learned (ADR-0007). Primary key `(person_id, observer_company_id, tag)`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER FK → person.id | no | Person. |
| `observer_company_id` | INTEGER FK → company.id | no | Observer. |
| `tag` | VARCHAR(64) | no | Revealed tag. |
| `revealed_turn` | INTEGER | no | Turn it was revealed; 0 for the founder's own company. |

### person_state

Energy, stress and morale; one row per person who has any (the founder's and delegates' energy, employees' morale).

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER PK, FK → person.id | no | Person. |
| `energy` | FLOAT | yes | Energy left this month for the founder (formulas.md §6) and for delegates who own a hiring plan (§13.10); reset after phase 12. Null for everyone else. |
| `stress` | FLOAT | yes | 0–100 (M1b+). |
| `morale` | FLOAT | yes | 0–100 for employees; null for the founder (formulas.md §9). |

### employment

A person's job at a company. Rows are closed (`status = ended`, `end_turn`, `end_reason`), never deleted (ADR-0004 §6). Index `ix_employment_company_status (company_id, status)`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Employment id. The founder's is 1. |
| `person_id` | INTEGER FK → person.id | no | Employee. |
| `company_id` | INTEGER FK → company.id | no | Employer. |
| `role` | VARCHAR(64) | no | `roles.yaml` key, or `founder`. |
| `level` | VARCHAR(16) | no | `junior` … `exec` (the founder is `exec`). |
| `salary_cents` | BIGINT | no | Annual salary in cents (0 for the founder). |
| `equity_bp` | INTEGER | no | Equity grant in basis points (0 for the founder in M1). |
| `start_turn` | INTEGER | no | First turn employed. |
| `end_turn` | INTEGER | yes | Last turn employed, once known. |
| `status` | VARCHAR(16) | no | `active`, `notice` or `ended`; headcount counts `active` and `notice`. |
| `end_reason` | VARCHAR(16) | yes | `resigned`, `fired`, `retired`, or null while employed. |
| `unit_id` | INTEGER | yes | Org unit (`org_unit.id`) the person belongs to; null = the company root, where the founder always is (formulas.md §13.1, M2a). No FK constraint (added by `ALTER TABLE`). |
| `last_raise_turn` | INTEGER | yes | Turn of the last raise that earned the raise morale bonus (§13.8); null if none. |

### relationship

Created in M1a and **empty**; affinity defaults to 0 (neutral). Primary key `(person_id, other_person_id)`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER FK → person.id | no | One person. |
| `other_person_id` | INTEGER FK → person.id | no | The other person. |
| `affinity` | FLOAT | no | Relationship strength; 0 is neutral. |
| `updated_turn` | INTEGER | no | Turn of the last change. |

## Hiring (migration `0003_hiring`, M1b)

Live records are loaded into the game state; finished ones keep their rows with a status (M1b sweep rule 1).

### search

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Search id. |
| `company_id` | INTEGER FK → company.id | no | Searching company. |
| `role` | VARCHAR(64) | no | `roles.yaml` role searched for. |
| `channel` | VARCHAR(16) | no | `network`, `job_post`, `recruiter`, or `poach` (M5: a rival's key people, one batch). |
| `actor_id` | INTEGER FK → person.id | no | Who opened it; their judgment of talent scouts its candidates. |
| `opened_turn` | INTEGER | no | Turn opened. |
| `status` | VARCHAR(16) | no | `open` or `closed`. Network and recruiter searches close after their one batch. |
| `closed_turn` | INTEGER | yes | Turn closed. |
| `plan_id` | INTEGER | yes | Hiring plan whose delegate opened it, or that inherited it (`hiring_plan.id`); null for the player's searches. A filled or closed plan's job posts close (formulas.md §13.10). No FK constraint (added by `ALTER TABLE` in `0006_search_plan`). |
| `rival_id` | INTEGER | yes | A poach search's rival (`company.id`, migration `0013_rivals`, M5); null otherwise. |

Index `ix_search_company_status (company_id, status)`.

### candidate

A generated person available to one company. Primary key `person_id`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER PK, FK → person.id | no | The candidate. |
| `company_id` | INTEGER FK → company.id | no | Company that found them. |
| `search_id` | INTEGER FK → search.id | no | Search that found them. |
| `channel` | VARCHAR(16) | no | That search's channel, kept because one-batch searches close (decides the recruiter fee on hire). |
| `created_turn` | INTEGER | no | Turn whose phase 12 generated the batch. |
| `expires_turn` | INTEGER | no | They leave in phase 12 of this turn unless hired. |
| `status` | VARCHAR(16) | no | `open`, `hired`, `declined`, `expired`, or `withdrawn` (reserved for M2). |
| `resolved_turn` | INTEGER | yes | Turn the status left `open`. |
| `interviewed_turn` | INTEGER | yes | Turn the company first interviewed them (founder or delegate); an offer needs one (ADR-0016, M2a). Backfilled from `decision_log` by `0005_org`. |

Index `ix_candidate_company_status (company_id, status)`.

### offer

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Offer id; offers resolve in id order. |
| `company_id` | INTEGER FK → company.id | no | Offering company. |
| `candidate_id` | INTEGER FK → person.id | no | Candidate. |
| `actor_id` | INTEGER FK → person.id | no | Who made the offer. |
| `salary_cents` | BIGINT | no | Annual salary offered. |
| `equity_bp` | INTEGER | no | Equity offered, in basis points (option pool rules, formulas.md §7). |
| `made_turn` | INTEGER | no | Turn made; resolved in phase 1 of that turn's Continue. |
| `status` | VARCHAR(16) | no | `pending`, `accepted`, `declined`, or `withdrawn` (by the player). |
| `resolved_turn` | INTEGER | yes | Turn resolved or withdrawn. |
| `plan_id` | INTEGER | yes | Hiring plan a delegate made it under (`hiring_plan.id`); null for the player's offers (M2a). |
| `unit_id` | INTEGER | yes | Org unit the hire joins; null = the company root (M2a). |

Index `ix_offer_company_status (company_id, status)`.

### person_morale_log

Month-end morale per employee, append-only. Primary key `(person_id, turn)`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER FK → person.id | no | Employee. |
| `turn` | INTEGER | no | Turn closed. |
| `morale` | FLOAT | no | Morale after phase 8. |

### person_rating_log

Month-end shown rating per player employee, append-only (M7b, migration `0018_person_rating_log`). Primary key `(person_id, turn)`. Written with each turn for the player's staff, the founder excepted; History's best hires and notable departures read it (formulas.md 17.2). It holds only what the player could see (ADR-0007). Saves from before 0018 start logging at their next turn.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER FK → person.id | no | Employee. |
| `turn` | INTEGER | no | Turn closed. |
| `rating` | FLOAT | no | The mean midpoint of the displayed ranges of the role's primary skills, 1–20. |

## Organization (migration `0005_org`, M2a)

Active units and hiring plans that are not closed are loaded into the game state; dissolved units and closed plans keep their rows with a status.

### org_unit

A department or team (formulas.md §13.1). The company root is implicit and has no row. Index `ix_org_unit_company_status (company_id, status)`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Unit id. |
| `company_id` | INTEGER FK → company.id | no | Owning company. |
| `kind` | VARCHAR(16) | no | `department` (parent is the root) or `team` (parent is the root or a department). |
| `name` | VARCHAR(64) | no | Display name, unique among the company's active units. |
| `parent_id` | INTEGER FK → org_unit.id | yes | Parent unit; null = the company root. |
| `leader_id` | INTEGER FK → person.id | yes | Leader, a member of this unit who leads no other; null if none. |
| `policy` | VARCHAR(16) | yes | `office` or `remote`; null = inherit the parent's (§13.9). |
| `created_turn` | INTEGER | no | Turn created. |
| `status` | VARCHAR(16) | no | `active` or `dissolved`. |
| `dissolved_turn` | INTEGER | yes | Turn dissolved. |
| `product_id` | INTEGER | yes | Product the unit's members work on (formulas.md §11.3, M3a); a unit works on at most one. No FK (added by `0008_products`). |

### hiring_plan

Delegated hiring (formulas.md §13.10, ADR-0015). Index `ix_hiring_plan_company_status (company_id, status)`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Plan id; plans act in id order in phase 2. |
| `company_id` | INTEGER FK → company.id | no | Hiring company. |
| `owner_id` | INTEGER FK → person.id | no | The delegate (any staff member except the founder). |
| `unit_id` | INTEGER FK → org_unit.id | yes | Unit the hires join; null = the company root. |
| `role` | VARCHAR(64) | no | `roles.yaml` role hired for. |
| `target` | INTEGER | no | Hires wanted in total. |
| `channel` | VARCHAR(16) | no | `job_post`, `recruiter`, `network`, or `any` (searches as a job post). |
| `ratio_bp` | INTEGER | no | Salary offered as basis points of the candidate's ask, at most `delegates.max_ratio_bp`. |
| `equity_bp` | INTEGER | no | Equity per offer, in basis points. |
| `created_turn` | INTEGER | no | Turn created. |
| `status` | VARCHAR(16) | no | `active`, `paused` (its owner left), `filled` (target reached), or `closed`. |
| `hired` | INTEGER | no | Offers made under the plan that were accepted. |
| `closed_turn` | INTEGER | yes | Turn closed. |
| `last_activity` | JSON | yes | `{turn, searches, interviews, scouted, offers}` for the last turn the delegate worked the plan. |
| `focus` | VARCHAR(16) | no | `current` ("Best now", default) or `potential` ("Spot potential": juniors and mids ranked by the displayed PA midpoint, formulas.md §13.10). Added by `0007_plan_focus` (M2b). |

## Products and markets (migration `0008_products`, M3a)

Products that are not retired, their segments, and every market segment are loaded into the game state; retired products keep their rows with a status. An existing save upgraded by `0008_products` gets the 2010 market from the current `categories.yaml` and `incumbents.yaml`, with demand grown to the save's turn (ADR-0017).

### product

A product of the player or an incumbent (formulas.md §11.2, §11.9). Index `ix_product_company_status (company_id, status)`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Product id. |
| `company_id` | INTEGER FK → company.id | no | Owner. |
| `category` | VARCHAR(32) | no | `categories.yaml` category key, e.g. `b2b_saas`. |
| `name` | VARCHAR(80) | no | Display name. |
| `status` | VARCHAR(16) | no | `in_development`, `live`, `sunset`, or `retired` (a sunset product with no customers left, or one cancelled in development, M3b). |
| `quality` | FLOAT | no | Quality, 0–100 (§11.4). |
| `feature_points` | FLOAT | no | Accumulated feature points F; the feature score is 100 × F / F_exp(t), clamped to 0–100. |
| `brand` | FLOAT | no | Brand, 0–100 (§11.5). |
| `marketing_budget_cents` | BIGINT | no | Monthly marketing budget, posted to `6400_marketing` in phase 6. |
| `created_turn` | INTEGER | no | Turn created. |
| `launched_turn` | INTEGER | yes | Turn launched. |
| `sunset_turn` | INTEGER | yes | Turn sunset. |
| `retired_turn` | INTEGER | yes | Turn its last customers left, or the turn it was cancelled. |
| `held_feature` | FLOAT | yes | Incumbents only: the fixed feature score; F follows F_exp so the score stays here (§11.9). Null for products that develop. |
| `first_customer_turn` | INTEGER | yes | First month with at least one paying customer (inbox note). |
| `rotting` | BOOLEAN | no | The last phase 3 found no team working on it (output below a quarter of scope); the inbox notes the change. |

### product_segment

A segment a product sells to. Primary key `(product_id, segment)`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `product_id` | INTEGER FK → product.id | no | Product. |
| `segment` | VARCHAR(32) | no | `categories.yaml` segment key: `consumer`, `smb`, `mid_market`, or `enterprise`. |
| `price_cents` | BIGINT | yes | Monthly price per customer (revenue per user for consumer apps); null until set. |
| `customers` | FLOAT | no | Customers, stored as a float and shown rounded (§11.7). |
| `capacity_limited` | BOOLEAN | no | Sales capacity bound new customers in the last phase 5 (sales segments only, §11.13). |
| `added_turn` | INTEGER | no | Turn the segment was added. |

### market_segment

Addressable customers for one category and segment (§11.1). Primary key `(category, segment)`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `category` | VARCHAR(32) | no | Category key. |
| `segment` | VARCHAR(32) | no | Segment key. |
| `addressable` | FLOAT | no | Addressable customers D; grows by (1 + g)^(1/12) in phase 9. |

### product_month

Month-end history per product and segment, append-only. Primary key `(product_id, segment, turn)`; index `ix_product_month_turn (turn)`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `product_id` | INTEGER FK → product.id | no | Product. |
| `segment` | VARCHAR(32) | no | Segment. |
| `turn` | INTEGER | no | Turn closed. |
| `quality` | FLOAT | no | Quality at month end. |
| `feature_score` | FLOAT | no | Feature score against F_exp(turn). |
| `brand` | FLOAT | no | Brand after phase 9. |
| `appeal` | FLOAT | yes | Appeal at month end (§11.6); null while the segment has no price. |
| `customers` | FLOAT | no | Customers after phase 5. |
| `new` | FLOAT | no | Customers won this month. |
| `churned` | FLOAT | no | Customers lost this month. |
| `revenue_cents` | BIGINT | no | Revenue booked this month (0 for incumbents, who have no ledger until M5). |

## Finance (migration `0009_finance`, M4a)

Shares are integer counts (ADR-0018). Fully diluted shares (FD) = every `cap_table_entry` (the unallocated pool included) + every grant's `granted - forfeited`. On upgrade an existing save gets its scenario's cap table; each employment's `equity_bp` becomes a grant of `equity_bp x 1000` options from the pool at its `start_turn`, vested to the save's turn; a funded spinout also gets its closed seed round and the lead's board seat with a generated director.

### cap_table_entry

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Entry id (`save_meta.next_cap_entry_id`). |
| `company_id` | INTEGER FK → company.id | no | Company. |
| `holder_kind` | VARCHAR(16) | no | `person` (the founder), `firm` (an investor in `investors.yaml`), `group` (e.g. "Former colleagues", "SAFE holders") or `pool` (the unallocated option pool, one per company). |
| `share_class` | VARCHAR(24) | no | `common`, `preferred_seed`, `preferred_a`, `preferred_b`, `safe_conversion` or `option_pool`. |
| `shares` | BIGINT | no | Shares held. |
| `acquired_turn` | INTEGER | no | Turn the shares were issued. |
| `person_id` | INTEGER | yes | Holder when `holder_kind` is `person`. |
| `firm` | VARCHAR(32) | yes | `investors.yaml` key when `holder_kind` is `firm`. |
| `name` | VARCHAR(80) | yes | Holder name when `holder_kind` is `group` or `pool`. |
| `round_id` | INTEGER | yes | The priced round that issued the shares. |

### option_grant

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Grant id (`save_meta.next_grant_id`). |
| `company_id` | INTEGER FK → company.id | no | Company. |
| `person_id` | INTEGER FK → person.id | no | Holder. |
| `employment_id` | INTEGER FK → employment.id | no | The hire the grant came with (one grant per employment). |
| `granted` | BIGINT | no | Options granted: `round(offer bp x FD / 10000)` at hire (14.2). |
| `start_turn` | INTEGER | no | Hire turn; vesting counts from here. |
| `vested` | BIGINT | no | Vested options: 0 before the 12-month cliff, then `floor(granted x min(48, months) / 48)`. |
| `forfeited` | BIGINT | no | Unvested options returned to the pool when the person left. |
| `status` | VARCHAR(16) | no | `active` or `ended` (the person left; vested options stay theirs). |

### safe

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | SAFE id (`save_meta.next_safe_id`). |
| `company_id` | INTEGER FK → company.id | no | Company. |
| `kind` | VARCHAR(16) | no | `safe` (raised by the founder) or `bridge` (offered by existing investors while insolvent, 14.7). |
| `amount_cents` | BIGINT | no | Money raised. A bridge's amount is set again when it is accepted: 3 × that month's projected net burn plus any deficit (14.7, M4b); while offered it holds the amount at the offer. |
| `cap_cents` | BIGINT | no | Post-money valuation cap (ADR-0018 §2). |
| `status` | VARCHAR(16) | no | SAFE: `pending` → `outstanding` or `declined`. Bridge: `offered` → `accepted` → `outstanding`, or `lapsed`. An outstanding SAFE becomes `converted` at the next priced round. |
| `raised_turn` | INTEGER | no | Turn raised (or offered). |
| `resolved_turn` | INTEGER | yes | Turn answered, funded or lapsed. |
| `expires_turn` | INTEGER | yes | Bridge: last turn it can be accepted. |
| `converted_round_id` | INTEGER | yes | The round it converted in. |

### funding_round

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Round id (`save_meta.next_round_id`). |
| `company_id` | INTEGER FK → company.id | no | Company. |
| `series` | VARCHAR(8) | no | `seed`, `a` or `b`. |
| `status` | VARCHAR(16) | no | `open` → `accepted` (a term sheet accepted) → `closed`; or `failed` (no term sheets) or `lapsed` (none accepted in time). |
| `target_cents` | BIGINT | no | The amount the founder asked for. |
| `opened_turn` | INTEGER | no | Turn started. |
| `expires_turn` | INTEGER | no | Last turn a term sheet can be accepted. |
| `accepted_sheet_id` | INTEGER | yes | The accepted term sheet. |
| `closed_turn` | INTEGER | yes | Turn it closed (phase 1). |
| `lead_firm` | VARCHAR(32) | yes | The lead investor. |
| `pre_money_cents` / `amount_cents` | BIGINT | yes | Agreed pre-money valuation and new money. |
| `fd_before` | BIGINT | yes | `E`: FD before the round. |
| `pool_shares` / `safe_shares` / `new_shares` | BIGINT | yes | `X` (pool top-up), `C` (SAFE conversion), `N` (new preferred), 14.5. |
| `fd_pre` | BIGINT | yes | `E + X + C`; the price is `pre_money_cents / fd_pre` cents a share. |
| `down_round` | BOOLEAN | no | The price was below the previous round's. |

### term_sheet

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Term sheet id (`save_meta.next_term_sheet_id`). |
| `round_id` | INTEGER FK → funding_round.id | no | Round. |
| `firm` | VARCHAR(32) | no | `investors.yaml` key. |
| `pre_money_cents` | BIGINT | no | The firm's quoted pre-money valuation. |
| `amount_cents` | BIGINT | no | What the firm offers to invest. |
| `status` | VARCHAR(16) | no | `offered`, `accepted` or `lapsed`. |
| `offered_turn` / `expires_turn` | INTEGER | no | Turn it arrived and the last turn it can be accepted. |

### board_seat

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Seat id (`save_meta.next_seat_id`; the `board` stream key for generating its director). |
| `company_id` | INTEGER FK → company.id | no | Company. |
| `kind` | VARCHAR(16) | no | `common` (the founder or their nominee), `investor` or `independent` (14.6). |
| `person_id` | INTEGER FK → person.id | yes (from `0011_board_nominee`, M4c) | Director: the founder; on the second common seat, the founder's nominee (an employee); on investor and independent seats, a generated person with role `board_member` and no employment. Null for an empty common seat (the nominee left, or none was named); it still votes with the founder. |
| `seated_turn` | INTEGER | no | Turn the seat was created. |
| `firm` | VARCHAR(32) | yes | Investor seats: the firm. |
| `round_id` | INTEGER | yes | The round that created the seat. |
| `confidence` | FLOAT | yes | Investor and independent seats: confidence 0–100 (starts at 70). Null for common seats, which always back the founder. |
| `months_below` | INTEGER | no | Consecutive month ends below the removal threshold (25). |

### round_nominee (migration `0011_board_nominee`, M4c)

The founder's board nominee named when accepting a term sheet for a round that adds a common seat (14.6). A table of its own rather than a column on `funding_round`, because migration `0009_finance` builds `funding_round` rows from the current models. `0011` also empties any common seat held by a generated person, adding a `board_seat_empty` inbox item, and gives the founder back their own seat where `0009` had seated a generated person in it (funded spinout saves upgraded from before M4).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `round_id` | INTEGER PK, FK → funding_round.id | no | The round. |
| `person_id` | INTEGER | yes | The nominee (an employee when named); null when the round adds no common seat or there was no one to name. |

### board_seat_history (migration `0010_stage_board_history`, M4b)

One row per seat. A table of its own rather than a column on `board_seat`, because migration `0009_finance` builds `board_seat` rows from the current models.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `seat_id` | INTEGER PK, FK → board_seat.id | no | The seat. |
| `history` | JSON | no | The director's confidence at the last `board.history_months` (6) month ends, oldest first; empty for common seats. Upgraded saves start with the current confidence. |

## Inbox (migration `0004_inbox`, M1b)

### inbox_item

Messages for the player company, rendered from `inbox_templates.yaml` when the turn or action that produced them is saved. Rows are only appended, except `read` and `archived`. Index `ix_inbox_item_company_read (company_id, read)`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Message id; newest has the highest id. |
| `turn` | INTEGER | no | Turn that produced it. |
| `company_id` | INTEGER FK → company.id | no | The player company. |
| `template` | VARCHAR(64) | no | `inbox_templates.yaml` key, e.g. `offer_accepted`. |
| `title` | VARCHAR(200) | no | Rendered title. |
| `body` | TEXT | no | Rendered body; amounts are formatted as money. |
| `link_kind` | VARCHAR(16) | yes | `person`, `candidate`, `search`, or null. |
| `link_id` | INTEGER | yes | Id of the linked person or search. |
| `read` | BOOLEAN | no | Marked read by the player. |
| `archived` | BOOLEAN | no | Archived by the player (migration `0012_inbox_archive`, M4c): hidden from the inbox unless the Archived filter is on; archiving also marks it read. UI state only: no game effect, not in `decision_log`. |

## Rivals (migration `0013_rivals`, M5)

Rivals are ordinary `company` rows with `is_player = 0` (ADR-0010). From M5 they have key people (persons with an `employment` at the rival), workforce pools, a ledger, and decisions (formulas.md §15). Rivals' own people and employments take ids from 1,000,001 (`save_meta.next_rival_person_id`, `next_rival_employment_id`), so the player's ids are as before M5. An upgraded save's incumbents become rivals at its turn, as at a new game (§15.1).

### company (M5 columns)

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `personality` | VARCHAR(16) | yes | `aggressive`, `fast_follower`, `premium` or `cost_leader`; null for the player. |
| `builder_skill` | FLOAT | yes | An incumbent's builder pool skill `d` (§15.1). |
| `target_margin_bp` | INTEGER | yes | The margin an incumbent's staff was sized for. |
| `is_startup` | BOOLEAN | no | A rival startup founded in play (§15.4). |
| `failed_turn` | INTEGER | yes | The turn a rival went bankrupt (§15.1, §14.7). |
| `last_raise_turn` | INTEGER | yes | A startup's last funding attempt (§15.4). |

### save_meta (M5 columns)

`next_rival_effect_id`, `next_rival_move_id`, `next_approach_id` (from 1) and `next_rival_person_id`, `next_rival_employment_id` (from 1,000,001): id counters.

### workforce_pool

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `company_id` | INTEGER PK, FK → company.id | no | The rival. |
| `function` | VARCHAR(16) PK | no | `builder`, `seller` or `marketer`. |
| `headcount` | FLOAT | no | People in the pool (key people are counted separately). |
| `skill` | FLOAT | no | Mean skill, 1–20 (builders: the table's `d`; others 12). |
| `morale` | FLOAT | no | Mean morale (60). |

### rival_effect

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Effect id. |
| `company_id` | INTEGER FK → company.id | no | The rival. |
| `kind` | VARCHAR(16) | no | `feature_push`, `quality_push`, `brand_push`, `cut_costs` or `builder_left` (§15.2). |
| `start_turn` / `end_turn` | INTEGER | no | First and last turn it applies. |
| `product_id` | INTEGER | yes | The product; null for a cost cut, which drags every product. |

### rival_move

Append-only; the last 24 months are loaded into the state (news, cooldowns, stance). Index `ix_rival_move_turn (turn)`.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Move id. |
| `company_id` | INTEGER FK → company.id | no | The rival. |
| `turn` | INTEGER | no | Turn it happened. |
| `action` | VARCHAR(16) | no | A §15.3 action, or `founded`, `launched`, `funded`, `failed`. |
| `product_id` / `segment` | INTEGER / VARCHAR(32) | yes | Where it applies. |
| `detail` | VARCHAR(200) | no | The news line's words. |

### poach_approach

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Approach id (the `poach` stream key). |
| `rival_id` | INTEGER FK → company.id | no | The rival making the offer. |
| `person_id` | INTEGER FK → person.id | no | The player's employee. |
| `offer_cents` | BIGINT | no | Annual salary offered (1.25 × market rate). |
| `made_turn` / `resolved_turn` | INTEGER | no / yes | When it was made and answered. |
| `status` | VARCHAR(16) | no | `pending`, `accepted`, `declined` or `lapsed`. |

### segment_share

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `product_id` / `segment` | INTEGER / VARCHAR(32) PK | no | The product in one segment. |
| `history` | JSON | no | Its share of the segment's served customers at the last 7 month ends, oldest first (§15.3 needs). |

## Events (migration `0016_events`, M6)

Phase 12 queues next month's events as `pending` rows; after the turn commits the event service writes their words and validated choices (`open`); the player answers (`answered`) or Continue answers minor and major ones with their first choice (`auto`). Replay copies these rows from the original save and never calls an adapter. Effect values are in each effect's own units (formulas.md §16.3): points for morale, relationships, brand, quality, energy and confidence; cents for cash; percent for customers and salary; skill points for growth.

### event

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Event id (next id = max + 1; not in `save_meta`). |
| `company_id` | INTEGER FK → company.id | no | The player's company. |
| `turn` | INTEGER | no | The month it is shown in (queued in phase 12 of the month before). |
| `template_id` | VARCHAR(64) | no | `events/*.yaml` template. |
| `category` / `severity` / `trigger` | VARCHAR | no | From the template and the director: `minor`, `major` or `critical`; the §16.2 trigger, `storyline` or `follow_up`. |
| `strength` | FLOAT | no | The trigger's strength (0–1). Never shown (§16.9). |
| `person_ids` | JSON | no | The trigger's people (a pair: two). |
| `unit_id` / `product_id` / `segment` / `rival_id` / `months` | various | yes | What else the event is about; `months` is the runway for `runway_short`. |
| `cash_base_cents` | BIGINT | no | max(cash, 3 × monthly revenue) when queued: the base of the cash caps. |
| `tone` | VARCHAR(16) | no | `grounded` or `light` (ADR-0011). |
| `storyline_id` | INTEGER FK → storyline.id | yes | The storyline this event is a step of. |
| `status` | VARCHAR(16) | no | `pending`, `open`, `answered` or `auto`. |
| `title` / `body` | VARCHAR(160) / TEXT | no | Written by the LLM or the template (empty while pending). |
| `choices` | JSON | no | `[{key, label, effects: [{type, target, value}]}]`, validated and clamped. |
| `chosen` / `resolved_turn` | VARCHAR(1) / INTEGER | yes | The choice taken and when. |
| `source` | VARCHAR(16) | no | Who wrote the words: `claude`, `template`, `mock` or `replay`. |

### storyline

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Storyline id. |
| `company_id` | INTEGER FK → company.id | no | The player's company. |
| `key` / `title` | VARCHAR | no | The template storyline key and its rendered title. |
| `step` | INTEGER | no | The last step queued. |
| `started_turn` / `ended_turn` | INTEGER | no / yes | When it began and ended. |
| `summary` | TEXT | no | At most 60 words, from the template or the LLM; passed to later requests. |
| `person_ids` / `product_id` / `rival_id` / `unit_id` / `segment` | various | — | What every step is about; it ends when its people leave. |
| `next_turn` / `next_template` | INTEGER / VARCHAR(64) | yes | The next step and the month it is shown in; null at the last step. |
| `status` | VARCHAR(16) | no | `active` or `ended`. |

### event_queue

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Queue id. |
| `company_id` | INTEGER FK → company.id | no | The player's company. |
| `template_id` | VARCHAR(64) | no | The critical event's follow-up template. |
| `due_turn` | INTEGER | no | The month it is shown in (the month after the answer). |
| `source_event_id` | INTEGER FK → event.id | no | The critical event answered. |
| `person_ids` / `product_id` / `unit_id` / `rival_id` / `segment` | various | — | Inherited from that event. |
| `done` | BOOLEAN | no | Queued as an event. |

### llm_text

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Row id. |
| `company_id` | INTEGER FK → company.id | no | The player's company. |
| `turn` | INTEGER | no | The month it is about. |
| `kind` | VARCHAR(16) | no | `headlines` (Market news), `minutes` (quarterly board meeting) or `exit_line`. |
| `ref_id` | INTEGER | yes | The person, for an exit line. |
| `status` | VARCHAR(16) | no | `pending` until the service writes it, then `written`. |
| `text` / `source` | TEXT / VARCHAR(16) | no | The words and who wrote them. |

### llm_call_log

ADR-0005 §5: one row per adapter call. Prompts and responses are stored only with `TST_LLM_DEBUG=1`.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Row id. |
| `turn` | INTEGER | no | The save's month when written. |
| `purpose` | VARCHAR(16) | no | `event`, `story`, `headlines`, `minutes` or `exit_line`. |
| `model` | VARCHAR(64) | no | Model id from the response (or `template`). |
| `prompt_hash` | VARCHAR(16) | no | First 16 hex digits of the prompt's SHA-256. |
| `input_tokens` / `output_tokens` | INTEGER | no | From the API response. |
| `cost_cents` | FLOAT | no | Real US cents (tokens × `llm.price_per_mtok_cents`); not game money. |
| `latency_ms` | INTEGER | no | Call time. |
| `outcome` | VARCHAR(16) | no | `ok`, `rejected`, `error` or `budget`. |
| `created_at` | VARCHAR(32) | no | Wall-clock UTC time (outside the sim). |
| `prompt` / `response` | TEXT | yes | Debug only. |

### account (M6 row)

`4900_other_income` (revenue): event cash gains. Costs post to `6900_general_admin`.

## Files next to the saves (M6)

- `saves/llm_settings.json`: the AI writing settings (adapter, monthly budget in cents, model ids, prices per million tokens in cents). Never holds the API key.
- `saves/llm_spend.json`: spend, calls, events written by Claude and rejected drafts per real calendar month (`YYYY-MM`); the meter reads the current month.

## Relationships (migration `0015_relationships`, M6 sub-task 2)

### relationship

Rebuilt by `0015_relationships` (the M1a table with `affinity` and `updated_turn` was never written). Only the player's company has pairs: every two members of a unit (the company root included) and each manager with each report. A pair that is no longer one of these is deleted in phase 8.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `person_id` / `other_person_id` | INTEGER PK FK → person.id | no | The pair, `person_id < other_person_id`. |
| `value` | FLOAT | no | True relationship, −100..100. The API shows only a label (§16.7, §16.9). |
| `start_value` | FLOAT | no | round(15 − 1.5 × \|temperament difference\|), clamped to −20..15; the value drifts 10% a month back toward it. |
| `since_turn` | INTEGER | no | The turn the pair began. |

## Free agents (migration `0014_free_agents`, M6 sub-task 0)

### free_agent

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `person_id` | INTEGER PK FK → person.id | no | A failed rival's former employee. |
| `role` | VARCHAR(32) | no | Their role at the rival (`roles.yaml` key): they join the player's next search for it. |
| `released_turn` | INTEGER | no | The turn the rival failed. |
| `until_turn` | INTEGER | no | They leave the pool in phase 12 of this turn (`released_turn + rivals.free_agent_months`). |
| `status` | VARCHAR(16) | no | `available`, `placed` (joined a search's batch) or `expired`. Only `available` rows are loaded. |

## Files next to the saves

- `saves/index.json`: list of `{slug, company_name, scenario_id, difficulty, current_turn}`; the save's own entry is updated after each create and turn (M6), and the whole list is rebuilt from the save files when it is missing or unreadable. The save files are the source of truth; a missing or corrupt index is rebuilt.
- `saves/backups/<slug>/<slug>.turn-<NNN>.sqlite`: periodic backup after every 12th committed turn; the newest 10 are kept.
- `saves/backups/<slug>/<slug>.turn-<NNN>.pre-migration-<rev>.sqlite`: backup taken before upgrading an older save; never pruned.

## coo_answer

"Ask my COO" questions and answers (M7b, migration `0019_coo_answer`; formulas.md 17.3). Read-only: never fed into events and never part of the game state; the newest `coo.keep_answers` (20) per save are kept and older rows deleted when a new one is written.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Autoincrement. |
| `turn` | INTEGER | no | The month the question was asked in. |
| `person_id` | INTEGER FK → person.id | yes | Who answered; null for the founder's notebook. |
| `speaker` | VARCHAR(120) | no | "Name, Role" or "Founder's notebook", as shown then. |
| `question` | TEXT | no | The player's question, at most `coo.max_question_chars` characters. |
| `answer` | TEXT | no | At most `coo.max_answer_words` words; offline, over budget or after an error, "I can't think that through right now" with the briefing. |
| `source` | VARCHAR(16) | no | `claude`, `mock` or `offline`. |
| `cost_cents` | FLOAT | no | Real cents the call cost (counts toward the monthly AI budget), not game money. |
| `created_at` | VARCHAR(32) | no | Wall-clock time (UTC, ISO 8601), as `llm_call_log`. |

## Divisions, executives and new markets (migration `0020_divisions`, M8)

Side tables rather than columns on `org_unit`, `product` and `search`: migration 0013 loads and syncs those tables through the current models when it upgrades an older save (as `round_nominee`). The migration also adds `market_segment` rows for categories a save lacks (Fintech, AI models and inference), grown to the save's turn; their incumbents and the scheduled entrants come only with new games.

### unit_services

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `unit_id` | INTEGER PK FK → org_unit.id | no | A division. |
| `services` | VARCHAR(16) | no | `central` or `embedded` (18.4). No row means central. |

### product_division

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `product_id` | INTEGER PK FK → product.id | no | The product. |
| `division_id` | INTEGER | yes | Its division (`org_unit` id, no FK); null or no row = corporate (18.1). |

### search_level

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `search_id` | INTEGER PK FK → search.id | no | An exec-level search (18.3, stage 3). |
| `level` | VARCHAR(16) | no | `exec`: every candidate is generated at this level. |

### exec_seat

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `company_id` | INTEGER PK FK → company.id | no | The company (the player's in M8). |
| `seat` | VARCHAR(8) PK | no | `coo`, `cfo`, `cto`, `cpo`, `cmo` or `cro`. |
| `person_id` | INTEGER | yes | The holder; null while vacant (a row exists once the seat was first filled). |
| `since_turn` | INTEGER | no | When the holder was appointed, or the seat became vacant. |

### division_month

Headcount per division at each month's payroll (phase 6), for the shared-services allocation of the division statements (18.1). Written only while the player has divisions. Append-only history.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Autoincrement. |
| `turn` | INTEGER | no | The month. |
| `company_id` | INTEGER FK → company.id | no | The player. |
| `division_id` | INTEGER | yes | The division; null for corporate. |
| `name` | VARCHAR(64) | no | Its name that month ("Corporate" for null). |
| `headcount` | INTEGER | no | Staff in it (corporate counts the founder). |
| `embedded` | BOOLEAN | no | Embedded shared services that month (takes no allocation). |

Index `ix_division_month_company_turn (company_id, turn)`. `save_meta.schema_version` is 20.

## former_staff (migration `0021_former_staff`, M7c)

What the player knew of an employee when they left, frozen at departure (the "Former employee" profile). Written by `sync_state` when one of the player's employments that was on staff ends (resigned, fired, retired, poached, company closed). Displayed ranges and noticed tags only, never a true value (ADR-0007). One row per person: a rehire who leaves again overwrites it. The migration backfills past departures from the stored data; for someone now at a rival, whose true skills may have moved since, those backfilled ranges are a best effort.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER PK FK → person.id | no | The person. |
| `company_id` | INTEGER FK → company.id | no | The player's company. |
| `employment_id` | INTEGER | no | The employment that ended. |
| `role` | VARCHAR(64) | no | Last role (roles.yaml key). |
| `level` | VARCHAR(16) | no | Last level. |
| `unit_name` | VARCHAR(64) | yes | The unit they were in; null for the company root. |
| `start_turn` | INTEGER | no | Hire month. |
| `end_turn` | INTEGER | no | Leaving month. |
| `reason` | VARCHAR(16) | no | `resigned`, `fired`, `retired`, `poached`, `company_failed` (or `left`). |
| `rival_id` | INTEGER | yes | The rival they joined when poached. |
| `knowledge` | JSON | no | `{"ranges": {attribute: [min, max]}, "tags": [[tag, noticed_turn]], "interests": [..] or null, "work_style": .. or null}`; potential is the `potential_ability` range, shown only as a phrase. |

`save_meta.schema_version` is 21 (22 from M10).

## inbox_event_link (migration `0021_former_staff`, M7c)

The events an inbox message links to: the "While you were away" summary lists the events decided for the player while on holiday, each opening that event's card (`/game/:save/events/:id`).

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `item_id` | INTEGER PK FK → inbox_item.id | no | The message. |
| `position` | INTEGER PK | no | Order in the message. |
| `event_id` | INTEGER | no | The event (no FK). |
| `label` | VARCHAR(200) | no | Its title as listed. |

## Capital and macro (migration `0022_capital_macro`, M10)

`save_meta.schema_version` is 22. Loans and the macro month are written by `sync_state`; a save from before M10 has no rows (the API fills months up to 2025 from history, and the covenant history fills as months are played).

### macro_month

One month's macro indicators (formulas.md 20.1), written when phase 1 sets them. Rows exist only for months already played: never a month ahead (20.4).

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `turn` | INTEGER PK | no | The month (0 = January 2010). |
| `base_rate` | FLOAT | no | Base rate, % a year (the US federal funds rate to 2025). |
| `climate` | FLOAT | no | Venture climate multiplier (M4's climate table to 2025). |
| `confidence` | FLOAT | no | Consumer confidence, 100 = the 2010-2019 average. |
| `ai_index` | FLOAT | no | AI compute price against 2010 (compute_index.yaml to 2025). |
| `ai_change` | FLOAT | no | The AI index's change over the year before (steps each January). |
| `downturn_turn` | INTEGER | yes | Start of the latest downturn after 2025, carried forward; null if none. |

### loan

Venture debt and bank loans (formulas.md 20.3).

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Loan id (ids continue from the largest stored). |
| `company_id` | INTEGER FK → company.id | no | The borrower (the player). |
| `instrument` | VARCHAR(16) | no | `venture_debt` or `bank_loan`. |
| `lender` | VARCHAR(32) | no | investors.yaml `lenders` key. |
| `principal_cents` | BIGINT | no | Amount borrowed. |
| `balance_cents` | BIGINT | no | Principal still owed. |
| `rate_bp` | INTEGER | no | Rate a year in basis points: base rate at signing + spread (+ 200 after a breach's higher-rate choice). |
| `signed_turn` | INTEGER | no | Month signed; its interest is charged in that month's phase 7. |
| `term_months` | INTEGER | no | 36 (venture) or 48 (bank). |
| `interest_only_months` | INTEGER | no | 12 (venture) or 0. |
| `round_id` | INTEGER | yes | Venture debt: the priced round it follows (no FK). |
| `warrant_shares` | BIGINT | no | Warrants issued at signing (a `warrant` cap-table entry); 0 for a bank loan. |
| `status` | VARCHAR(16) | no | `active`, `repaid` or `called`. |
| `closed_turn` | INTEGER | yes | Month repaid or called. |
| `interest_paid_cents` | BIGINT | no | Interest paid so far. |
| `principal_paid_cents` | BIGINT | no | Principal paid so far; never above `principal_cents`. |
| `breach_turn` | INTEGER | yes | The latest covenant breach. |
| `breaches` | INTEGER | no | Breaches so far (the one that called the loan included). |

### finance_history

The player's operating result and burn at the last month ends (oldest first), which covenants and the bank loan's gate read (20.3).

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `company_id` | INTEGER PK FK → company.id | no | The player's company. |
| `op_history` | JSON | no | Operating result (revenue − cost of revenue − operating expenses, before interest) per month, cents, last 6. |
| `burn_history` | JSON | no | Net cash used before financing per month (14.1), cents, last 6. |

### Columns added to existing tables

- `event.loan_id` INTEGER null: a lender event's loan (target `loan:<id>`).
- `event_queue.loan_id` INTEGER null: a lender event the debt phase queued; `event_queue.source_event_id` is now nullable (null for an event the engine queued, not an answer).
- `cap_table_entry.share_class` gains `preferred_c`, `preferred_d` and `warrant`; `funding_round.series` gains `c` and `d`.
