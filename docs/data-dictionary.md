# Data dictionary

Column-level reference for a save file (`saves/<slug>.tst.sqlite`). Kept current with the Alembic migrations in `backend/migrations/versions/`; ORM models are in `backend/tst/db/models.py`.

- **Schema version:** 27 (migrations `0001_initial`, `0002_people`, `0003_hiring`, `0004_inbox`, `0005_org`, `0006_search_plan`, `0007_plan_focus`, `0008_products`, `0009_finance`, `0010_stage_board_history`, `0011_board_nominee`, `0012_inbox_archive`, `0013_rivals`, `0014_free_agents`, `0015_relationships`, `0016_events`, `0017_save_display_name`, `0018_person_rating_log`, `0019_coo_answer`, `0020_divisions`, `0021_former_staff`, `0022_capital_macro`, `0023_geo`, `0024_inbox_bookmark`, `0025_event_modifiers`, `0026_marketing_split`, `0027_exec_authority`). Alembic also records its revision in its own `alembic_version` table.
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
| `mod_name` | VARCHAR(64) | yes | The data-editor mod the game started with (M25, `0040_m25`): a `saves/mods/<name>.yaml` name; null for a game without a mod (and every save from before M25). A modded game earns no achievements and is flagged on the Saves list and in the Hall of Fame. |
| `mod_hash` | VARCHAR(64) | yes | SHA-256 of the merged data files (base files with the overlay merged, canonical JSON) the game started with (M25); a later difference (the base files changed) is logged, as `data_hashes` is. Null without a mod. |
| `mod_overlay` | JSON | yes | A copy of the mod's overlay (`{data file: changed values}`, tst/mods/overlay.py) taken at new game (M25). The save always loads with this copy, so editing or deleting the mod file never changes it. Null without a mod. |

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

M14b: a search's interest filter lives in `search_interest` (migration `0033_press`).

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

M14b: a plan's `interest`, `replace_of` and `level` live in `hiring_plan_detail` (migration `0033_press`).

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

Messages for the player company, rendered from `inbox_templates.yaml` when the turn or action that produced them is saved. Rows are only appended, except `read`, `archived` and `bookmarked`. Index `ix_inbox_item_company_read (company_id, read)`.

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
| `archived` | BOOLEAN | no | Archived by the player (migration `0012_inbox_archive`, M4c): hidden from the inbox unless the Archived filter is on; archiving also marks it read. Since M10b (formulas.md 23.1) an answered event's item archives itself, and a read, unbookmarked item `inbox.auto_archive_months` (3) old archives at month end. UI state only: no game effect, not in `decision_log`. |
| `bookmarked` | BOOLEAN | no | Starred by the player (migration `0024_inbox_bookmark`, M10b): never auto-archived; starring an archived item brings it back. UI state only. |

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
| `choices` | JSON | no | `[{key, label, effects: [{type, target, value}]}]`, validated and clamped. Since M10b (23.2) a `modifier` effect also carries `stat` and `months`, and an explicit "Do nothing" choice carries `do_nothing: true` (no effects). |
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

## Cities, offices and regions (migration `0023_geo`, M9)

Side tables, as M8's: migration 0013 loads `company`, `person`, `org_unit` and `search` through the current models on older saves, so M9's values for them live in tables of their own. An existing save gets San Francisco as its HQ, each person's home city (the first city of their region; Africa's people take London), every other region's market grown to its turn, and its v1 incumbents' Europe presence at their starting shares. The six regional incumbents (SAP, Kaspersky, Tencent, Alibaba, Baidu, Infosys) come only with new games.

### company_hq

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `company_id` | INTEGER PK FK → company.id | no | The player's company. |
| `city` | VARCHAR(32) | no | `cities.yaml` key of the HQ (19.1). No row: `geo.default_hq_city`. |

### person_city

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER PK FK → person.id | no | The person. |
| `city` | VARCHAR(32) | no | Their home city (19.1): where a candidate lives, where a remote employee works, and where an office worker last moved to. No row: the first city of their region. |

### office

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Counted as max(id) + 1 on load (like M6's counters). |
| `company_id` | INTEGER FK → company.id | no | The leasing company (the player's; rivals have no offices). |
| `city` | VARCHAR(32) | no | `cities.yaml` key. |
| `seats` | INTEGER | no | 25, 50, 100 or 250 (`office.seat_sizes`). |
| `opened_turn` | INTEGER | no | The month the lease started (its fit-out was paid then). |
| `status` | VARCHAR(16) | no | `open` or `closed`. Only open offices are loaded. |
| `closed_turn` | INTEGER | yes | The month the lease was ended early. |

### unit_office

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `unit_id` | INTEGER PK FK → org_unit.id | no | The unit. |
| `office_id` | INTEGER | yes | Its home office; null (or no row) = its parent's office, up to flexible space in the HQ city (19.2). |

### search_city

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `search_id` | INTEGER PK FK → search.id | no | The search. |
| `city` | VARCHAR(32) | no | Where its candidates live (85% local, the rest relocators), or `anywhere` for a remote unit's search (19.3). No row: a search opened before M9, generated as in v1. |

### candidate_relocation

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER PK FK → person.id | no | A candidate who lives outside their search's city. |
| `city` | VARCHAR(32) | no | The search's city they would move to; hiring them into an office there costs `hiring.relocation_cents`. |

### regional_market

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `category` | VARCHAR(32) PK | no | `categories.yaml` key. |
| `segment` | VARCHAR(32) PK | no | Segment key. |
| `region` | VARCHAR(32) PK | no | A region other than the home region (the home region stays in `market_segment`). |
| `addressable` | FLOAT | no | Addressable customers D: the home D0 x the region's size, grown monthly at the category's growth x the region's `region_growth` (19.5). |

### product_region

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `product_id` | INTEGER PK FK → product.id | no | The product. |
| `region` | VARCHAR(32) PK | no | A region other than the home region. |
| `launched_turn` | INTEGER | no | When it launched there (localization paid). |
| `live_turn` | INTEGER | no | From this month it sells there (`markets.localize_months` later for the player; at once for rivals). |

### regional_segment

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `product_id` | INTEGER PK FK → product.id | no | The product. |
| `region` | VARCHAR(32) PK | no | The region. |
| `segment` | VARCHAR(32) PK | no | The segment. |
| `price_cents` | BIGINT | yes | Monthly price there; defaults to p_ref x the region's price index (19.5). |
| `customers` | FLOAT | no | Customers there. |
| `capacity_limited` | BOOLEAN | no | Last phase 5's sales capacity there bound new customers. |
| `added_turn` | INTEGER | no | When the row was added. |

`save_meta.schema_version` is 23.

## Event modifiers (migration `0025_event_modifiers`, M10b)

### event_modifier

An event choice's lasting percent change to one stat (formulas.md 23.2). It applies every month from `start_turn` up to but not including `end_turn`, then expires at that month end. Rows stay after they expire, for history; the game state loads those still running (`end_turn` > the current turn). Index on `end_turn`.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key; the next id is max(id) + 1 (not in `save_meta`). |
| `company_id` | INTEGER FK company | no | The company (the player's in M10b). |
| `event_id` | INTEGER FK event | yes | The event whose choice started it. |
| `target` | VARCHAR(32) | no | `product:<id>`, `unit:<id>`, `person:<id>`, `company:<id>` or `founder:<id>`. A company target reaches every product, unit and person. |
| `stat` | VARCHAR(32) | no | `brand_target`, `quality_cap`, `builder_output`, `seller_capacity`, `awareness`, `churn`, `morale_target` or `founder_energy`. |
| `value_pct` | FLOAT | no | Percent; the stat is multiplied by 1 + value_pct / 100. Held to `events.caps.modifier` (5 / 10 / 20 by severity). |
| `start_turn` | INTEGER | no | The month it was chosen; it applies from this month. |
| `end_turn` | INTEGER | no | The first month it no longer applies; at most `events.modifier_months` (6 / 12 / 12) after `start_turn`. |

## Marketing by region (migration `0026_marketing_split`, M10b)

### product_marketing_split

A product's marketing budget split across the regions it sells in (formulas.md 23.5). No rows: the budget follows revenue by region. Rows for regions the product no longer sells in are ignored (the rest are renormalized). Primary key `(product_id, region)`.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `product_id` | INTEGER FK product | no | The product. |
| `region` | VARCHAR(32) | no | `regions.yaml` key: the home region or one it is live in. |
| `share_bp` | INTEGER | no | Its share of the budget, basis points; a product's rows sum to 10,000. |

## Executives with authority (migration `0027_exec_authority`, M10c)

### exec_authority

A seat's authority over its function (formulas.md 24.1). Primary key `(company_id, seat)`; a row exists once authority was first given.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `company_id` | INTEGER FK company | no | The company. |
| `seat` | VARCHAR(8) | no | `cto`, `cro`, `cmo`, `coo` or `cfo`. |
| `enabled` | BOOLEAN | no | The executive acts in phase 2 while true. |
| `guardrails` | JSON | no | `{key: value}`: `headcount_cap`, `max_salary_ratio_bp`, `protected_units` (CTO), `price_band_pct` (CRO), `marketing_pct_of_revenue` (CMO), `coverage_target`, `lease_approval_rent_cents` (COO), `runway_months`, `repay_above_months` (CFO). Defaults from `exec_authority.defaults`. |
| `since_turn` | INTEGER | no | When authority was last given. |
| `price_anchors` | JSON | no | CRO: `[[product_id, segment, cents], ...]`, the player's sales-led prices when authority was given; the CRO moves prices within its band of these. |

### exec_decision

What an executive with authority did, or got wrong (24.1-24.2). The state holds the last `exec_authority.memory_months` (12); rows are only appended.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key; max(id) + 1 is the next. |
| `company_id` | INTEGER FK company | no | The company. |
| `seat` | VARCHAR(8) | no | The seat. |
| `person_id` | INTEGER | no | The executive (no FK). |
| `turn` | INTEGER | no | The month. |
| `text` | TEXT | no | What they did, in words. |
| `mistake` | BOOLEAN | no | They took a plausible but worse option (24.2). |

### exec_proposal

A CFO or COO proposal waiting for the player (24.1). Pending proposals block Continue (23.1).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key. |
| `company_id` | INTEGER FK company | no | The company. |
| `seat` | VARCHAR(8) | no | `cfo` or `coo`. |
| `person_id` | INTEGER | no | The executive who proposed it. |
| `turn` | INTEGER | no | The month it was made. |
| `kind` | VARCHAR(8) | no | `round`, `loan` or `lease`. |
| `params` | JSON | no | The terms: a round's series and target, a loan's kind and amount, a lease's city and seats. |
| `text` | TEXT | no | The proposal in words. |
| `status` | VARCHAR(10) | no | `pending`, `approved`, `declined` or `lapsed`. |
| `resolved_turn` | INTEGER | yes | When it was answered. |

## Research and eras (migration `0028_research`, M11)

Every row belongs to a company (ADR-0020) except `era_arrival`, which is the world's. Existing saves start with no leads, projects or licences; eras whose historical month is before the save's turn are recorded as arrived on schedule.

### research_lead

A company's lead in one research domain beyond the world's baseline (formulas.md 21.1). Hidden for rivals: the API shows another company's lead only as a range (21.7).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `company_id` | INTEGER FK company | no | Primary key, with `domain`. |
| `domain` | VARCHAR(32) | no | `tech_frontier.yaml` domain key. |
| `lead` | FLOAT | no | Points of lead, >= 0; decays 1.5% a month. |

### research_project

A research project (21.3), or a rival's research action (21.6) when `unit_id` is NULL.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key. |
| `company_id` | INTEGER FK company | no | The company researching. |
| `domain` | VARCHAR(32) | no | The domain researched. |
| `unit_id` | INTEGER | yes | The org unit working on it; NULL for a rival's research action. |
| `start_turn` | INTEGER | no | The month it started. |
| `status` | VARCHAR(8) | no | `active` or `stopped`. |
| `budget_cents` | BIGINT | yes | Monthly budget; NULL = whatever full funding needs. |
| `end_turn` | INTEGER | yes | The month it stopped, or a rival action's last month. |
| `recent` | JSON | no | Lead gained in the last months (rnd.progress_window), oldest first; a dead end halves them. |
| `gained` | FLOAT | no | Lead gained in total, before decay. |
| `last_event` | VARCHAR(16) | yes | `breakthrough` or `dead_end`, the latest one. |
| `last_event_turn` | INTEGER | yes | When it happened. |

### era_arrival

An era milestone that has arrived (21.4).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `key` | VARCHAR(32) | no | Primary key: `eras.yaml` era key. |
| `turn` | INTEGER | no | The month it arrived. |
| `company_id` | INTEGER | yes | The company whose level reached the threshold; NULL on its historical date. |
| `months_early` | INTEGER | no | Months before its historical date (0 on schedule). |

### research_license

A licence of research lead from one company to another (21.5).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key. |
| `licensor_id` | INTEGER FK company | no | The company whose know-how it is. |
| `licensee_id` | INTEGER FK company | no | The company that gained the points. |
| `domain` | VARCHAR(32) | no | The domain. |
| `points` | FLOAT | no | Lead points granted. |
| `turn` | INTEGER | no | The month it was signed. |
| `price_cents` | BIGINT | no | Paid once by the licensee (licensing in); 0 for a royalty licence. |
| `royalty_bp` | INTEGER | no | Basis points of the licensee's monthly revenue in the domain's categories (licensing out); 0 if none. |
| `royalty_end_turn` | INTEGER | yes | The last month the royalty is paid. |

## Facilities, market goods and contracts (migration `0029_facilities`, M12a)

One facility model with kinds and one market-good model (ADR-0020 2-3; formulas.md 22). Existing saves start with no rows; their goods follow `components_history.yaml`.

### facility

A facility (22.2): a general or GPU data centre in M12a, more kinds later. The state holds facilities that are not closed; a closed one keeps its row.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key; max(id) + 1 is the next. |
| `company_id` | INTEGER FK company | no | The owner. |
| `kind` | VARCHAR(32) | no | `balance.facility.kinds` key: `data_centre_general` or `data_centre_gpu` (M12b adds `assembly_plant`). |
| `region` | VARCHAR(32) | no | regions.yaml key; it serves this region and the region whose neighbour it is (19.5). |
| `city` | VARCHAR(32) | yes | cities.yaml key; null for a regional site (for v3's sited kinds). |
| `capacity` | INTEGER | no | Units ordered (CU for data centres). |
| `on_time` | INTEGER | no | Units live from `ready_turn`; the rest from `late_turn` (a component shortage, 22.4). |
| `ordered_turn` | INTEGER | no | The month the build was ordered. |
| `ready_turn` | INTEGER | no | The month it goes live: ordered + the kind's build months. |
| `late_turn` | INTEGER | no | The month the late units arrive (equal to `ready_turn` when none are late). |
| `capex_cents` | BIGINT | no | The whole build's capex at the input good's index (a contract's for the units it covers). |
| `input_index` | FLOAT | no | The average index the capex was priced at. |
| `capex_paid_cents` | BIGINT | no | Capex paid so far, in equal monthly parts until `ready_turn` (to `1500_ppe`). |
| `depreciated_cents` | BIGINT | no | Depreciation booked so far (to `6700_depreciation` against `1510_accumulated_depreciation`). Book value is paid less depreciated, never below 0. |
| `status` | VARCHAR(16) | no | `building`, `live` or `closed`. |
| `unit_id` | INTEGER | yes | The org unit whose infrastructure people staff it (no FK). |
| `contract_id` | INTEGER | yes | The component contract it drew on. |
| `closed_turn` | INTEGER | yes | When it was sold. |
| `yield_rate` | FLOAT | no | M12b (`0031_hardware`), assembly plants: this month's yield after noise (stream `manufacturing`); 0 for data centres and before a plant's first live month. |
| `run_units` | FLOAT | no | M12b: units a plant ran last month for its company's own products. |
| `sold_units` | FLOAT | no | M12b: units a plant ran last month for contract-manufacturing customers. |

### supply_month

One market good's month (22.4). Rows exist only for months already played; the API shows months up to the current one, never later.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `good` | VARCHAR(32) | no | components_history.yaml key (`server`, `gpu`); with `turn`, the primary key. |
| `turn` | INTEGER | no | The month. |
| `price_index` | FLOAT | no | The index (January 2010 = 1.0). |
| `allocation` | FLOAT | no | Share of a build's units delivered on time (1.0 outside shortages). |
| `base` | FLOAT | no | The index without a shock's rise. |
| `change` | FLOAT | no | The trend's yearly change (fraction); after 2025 an AR(1) step each January. |
| `shock_turn` | INTEGER | yes | The latest shock's first month (after 2025 only). |
| `shock_months` | INTEGER | no | How long it runs. |
| `shock_rise` | FLOAT | no | Its rise on the trend (fraction), fading after it ends. |
| `shock_allocation` | FLOAT | no | Allocation while it runs. |
| `shock_kind` | VARCHAR(32) | yes | M17 (0041): a commodity shock's kind (`export_ban`, `demand_boom`, `supply_disruption`); null for components and history. |

### supply_contract

A component contract (22.4): a locked index for a volume of builds, take-or-pay at the end.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key. |
| `company_id` | INTEGER FK company | no | The buyer. |
| `good` | VARCHAR(32) | no | The component. |
| `price_index` | FLOAT | no | The locked index. |
| `signed_turn` | INTEGER | no | When it was signed. |
| `end_turn` | INTEGER | no | Its last month. |
| `volume` | INTEGER | no | Units of builds it covers. |
| `unit_value_cents` | BIGINT | no | Capex of one unit at the locked index (for take-or-pay). |
| `used` | INTEGER | no | Units built on it. |
| `status` | VARCHAR(16) | no | `active` or `settled`. |
| `settled_cents` | BIGINT | no | The take-or-pay charge when it ended. |

### facility_outage

A data-centre outage (22.5). The state holds the last 24 months.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key. |
| `facility_id` | INTEGER | no | The facility (no FK). |
| `company_id` | INTEGER FK company | no | Its owner. |
| `turn` | INTEGER | no | The month (indexed). |
| `customers_lost` | FLOAT | no | Customers its hosted products and Cloud hosting lost. |

### company_rival_key

A company's stable identity for its RNG keys (ADR-0013 amendment). Primary key `company_id`; the player's first company and rivals of older saves have no row.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `company_id` | INTEGER FK company | no | The rival. |
| `rival_key` | JSON | no | `[0, i]` incumbent at position i of incumbents.yaml, `[1, i]` entrant at position i of entrants.yaml, `[2, c, n]` the n-th startup founded in category c, `[4, n]` the player's n-th venture after the first (a serial founder's, M15r; kept when it is sold). |

New games number incumbents' products from 900,000 (10 per incumbent) and their key people and employments from 5,000,001 (100 per incumbent), by position in incumbents.yaml.

### New accounts

`1510_accumulated_depreciation` (asset, credit balance) and `6700_depreciation` (expense, with compute in cost of revenue). The cash flow counts both with investing, where depreciation cancels and a sale leaves its proceeds.

## Going public and the Chair (migration `0030_public_company`, M13)

A company's IPO chain, its life as a listed company and its appointed CEO (formulas.md 25). Every row belongs to a company (ADR-0020 7), so a v3 subsidiary can list on its own. Existing saves start with no rows: every company is private and founder-led. `save_meta.schema_version` becomes 30.

### listing

A company's IPO chain (25.2), from hiring the banks to the listing or a pull. Primary key `company_id`: hiring banks again after a pull replaces the row. The state holds every row.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `company_id` | INTEGER FK company | no | Primary key. |
| `bank` | VARCHAR(32) | no | `banks.yaml` key. |
| `hired_turn` | INTEGER | no | The month the banks were hired. |
| `status` | VARCHAR(16) | no | `hired`, `filing`, `roadshow`, `pricing`, `priced`, `listed` or `pulled`. |
| `filed_late` | BOOLEAN | yes | The S-1 choice restated a metric (a month's delay); null before the choice. |
| `roadshow_turn` | INTEGER | yes | The month the roadshow's events are due. |
| `ambition` | VARCHAR(8) | yes | `high`, `middle` or `low`. |
| `share_choice` | VARCHAR(8) | yes | `low`, `middle` or `high` (`ipo.share_sold`). |
| `dual_class` | BOOLEAN | yes | The listing gives the founder a dual-class structure. |
| `demand` | FLOAT | yes | Hidden (25.8): the book's draw; the API shows only its word. |
| `price_choice` | VARCHAR(8) | yes | `range`, `raise`, `cut` or `pull`. |
| `shares_before` | BIGINT | no | Fully diluted shares at the pricing. |
| `new_shares` | BIGINT | no | Shares issued in the offering. |
| `price_cents` | BIGINT | no | Per share: the bank's suggestion at pricing, then the final price. |
| `gross_cents` | BIGINT | no | Gross proceeds. |
| `fee_cents` | BIGINT | no | The banks' fee. |
| `first_day_return` | FLOAT | yes | The first day's return (fraction). |
| `close_cents` | BIGINT | no | The first day's closing price. |
| `listed_turn` | INTEGER | yes | The month it listed. |
| `pulled_turn` | INTEGER | yes | The month it was pulled. |
| `ticker` | VARCHAR(16) | no | The ticker ('' until set). |

### public_company

A listed company's market state (25.3-25.5). Primary key `company_id`. The state holds every row; a sold company's row is deleted when the founder founds again (its `share_month` history stays; M15r).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `company_id` | INTEGER FK company | no | Primary key. |
| `listed_turn` | INTEGER | no | The month it listed. |
| `ticker` | VARCHAR(16) | no | The ticker. |
| `dual_class` | BOOLEAN | no | Dual-class shares. |
| `listing_price_cents` | BIGINT | no | The IPO price per share. |
| `price_cents` | BIGINT | no | The share price at the last month end. |
| `sentiment` | FLOAT | no | Hidden (25.8): S, which also carries the future's drift. |
| `value_cents` | BIGINT | no | Hidden (25.8): V_f at the last month end. |
| `analysts` | JSON | no | `[[index, target_cents, rating], ...]`: position in `public.analysts.firms`, price target, `buy`/`hold`/`sell`. |
| `below_value_months` | INTEGER | no | Months the price was below the activist share of V_f per share (25.4). |
| `below_takeover_months` | INTEGER | no | Months market cap was below the takeover share of V_f (25.4). |
| `last_activist_turn` | INTEGER | yes | The last activist event. |
| `last_takeover_turn` | INTEGER | yes | The last takeover approach. |
| `beat_streak` | INTEGER | no | Consecutive beats. |
| `miss_streak` | INTEGER | no | Consecutive misses. |
| `results` | JSON | no | Each report's result (`beat`, `inline`, `miss`), oldest first, the last 8. |
| `quarter_revenue_cents` | BIGINT | no | The running quarter's revenue so far. |
| `quarter_op_cents` | BIGINT | no | The running quarter's operating result so far. |
| `dividend_cents` | BIGINT | no | Declared dividend per share, paid at the next month end. |
| `lapsed_seats` | INTEGER | no | Investor board seats lapsed since listing (25.7). |
| `pending` | JSON | no | Event choices done at the next phase 7: `activist_seat`, `activist_buyback`, `activist_fight` (25.4). |

### guidance

One quarter's guidance and, once reported, its result (25.4). Primary key `(company_id, quarter_turn)`. The state holds every row.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `company_id` | INTEGER FK company | no | The company. |
| `quarter_turn` | INTEGER | no | The quarter's first month. |
| `revenue_cents` | BIGINT | no | Guided revenue. |
| `margin_bp` | INTEGER | no | Guided operating margin, basis points. |
| `consensus_revenue_cents` | BIGINT | no | The analysts' consensus revenue. |
| `consensus_margin_bp` | INTEGER | no | The consensus margin, basis points. |
| `by_player` | BOOLEAN | no | The player set it (false: the default guidance). |
| `actual_revenue_cents` | BIGINT | yes | Reported revenue. |
| `actual_margin_bp` | INTEGER | yes | Reported margin, basis points. |
| `result` | VARCHAR(8) | yes | `beat`, `inline` or `miss`; null until reported. |
| `price_before_cents` | BIGINT | yes | The share price before the report. |
| `price_after_cents` | BIGINT | yes | The share price after it. |

### share_month

A listed company's month end (25.3): the chart's data. Primary key `(company_id, turn)`. Every month is kept; the state holds the last `public.history_months` (36). Rows are only appended.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `company_id` | INTEGER FK company | no | The company. |
| `turn` | INTEGER | no | The month. |
| `price_cents` | BIGINT | no | The month-end share price. |
| `shares` | BIGINT | no | Shares outstanding; market cap is price x shares. |
| `mark` | VARCHAR(16) | no | `listing`, a report's result (`beat`, `inline`, `miss`) or '' for the chart. |

### ceo

An appointed CEO (25.6); the founder is Chair while one serves. The state holds serving CEOs and those ended in the last `ceo.memory_months` (12); an ended one keeps its row.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key; max(id) + 1 is the next. |
| `company_id` | INTEGER FK company | no | The company. |
| `person_id` | INTEGER | no | The CEO (no FK). |
| `since_turn` | INTEGER | no | The month appointed. |
| `scopes` | JSON | no | The authority the Chair allows (`config.CEO_SCOPES` keys), a list. |
| `ended_turn` | INTEGER | yes | When the tenure ended; null while serving. |
| `end_reason` | VARCHAR(16) | yes | `replaced` (the board), `dismissed` (the Chair), `left`, or `acquired` (the company was sold, M15r). |
| `low_months` | INTEGER | no | Months of board confidence below `ceo.replace.below`. |
| `price_anchors` | JSON | no | `[[product_id, segment, cents], ...]`: the player's last prices; the CEO moves a price only within `ceo.price_band_pct` of these. |

### ceo_decision

One decision a CEO took (25.6). The state holds the last `ceo.memory_months` (12); indexed on `turn`.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key; max(id) + 1 is the next. |
| `company_id` | INTEGER FK company | no | The company. |
| `person_id` | INTEGER | no | The CEO (no FK). |
| `turn` | INTEGER | no | The month (indexed). |
| `scope` | VARCHAR(32) | no | The scope it fell under. |
| `text` | TEXT | no | What they did, in words. |
| `mistake` | BOOLEAN | no | A plausible but worse option. |
| `undo` | JSON | no | `[[key, value], ...]`: the action kind and fields that reverse it; `[]` when it cannot be overridden. |
| `overridden_turn` | INTEGER | yes | When the Chair overrode it. |

## Hardware, devices and fabless chips (migration `0031_hardware`, M12b; re-parented after M13's `0030_public_company`)

Assembly plants are the `assembly_plant` kind of `facility` (the three columns above); device, server, equipment and wafer goods are rows of `supply_month` after 2025. Existing saves start with no contracts and no production; M12b's eras the save is past are recorded in `era_arrival` on schedule (future eras at their seeded month).

### production_contract

A contract-manufacturing contract (kind `assembly`, 26.2) or a wafer contract (kind `wafer`, 26.3). The state holds active ones and those ended in the last 24 months.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key; max(id) + 1 is the next. |
| `company_id` | INTEGER FK company | no | The company that signed it. |
| `product_id` | INTEGER | no | The device, server or chip product it makes (no FK). |
| `kind` | VARCHAR(16) | no | `assembly` or `wafer`. |
| `supplier` | VARCHAR(32) | no | `hardware.contract.manufacturers` or `chips.contract.foundries` key. |
| `units` | INTEGER | no | A month: units assembled, or wafer starts. |
| `price_millicents` | BIGINT | no | A unit's fee (base x manufacturer x city), or a wafer's price at the foundry_wafer index locked at signing, in exact integer thousandths of a cent (0038_m15r; was FLOAT `price_cents` in 0031). Rounded to cents when a month posts. |
| `signed_turn` | INTEGER | no | The month it was signed; a contract signed before a shortage began keeps full allocation. |
| `end_turn` | INTEGER | no | The last month it covers. |
| `city` | VARCHAR(32) | yes | cities.yaml key where it is made (assembly). |
| `delivered` | FLOAT | no | Units (or wafers) delivered last month after allocation. |
| `used` | FLOAT | no | Units (or wafers) used last month. |
| `charged_cents` | BIGINT | no | Last month's take-or-pay on unused volume (to `6900_general_admin`). |
| `status` | VARCHAR(16) | no | `active` or `ended`. |

### production_month

One unit-sale product's month of production (26.2, 26.3), append-only. Primary key (`turn`, `product_id`). The state holds the last month's rows.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `turn` | INTEGER | no | The month. |
| `product_id` | INTEGER | no | The product (no FK). |
| `company_id` | INTEGER FK company | no | Its company. |
| `capacity` | FLOAT | no | Units (chips) it could make this month. Engine and history only; the API shows sources' availability. |
| `units` | FLOAT | no | Units sold (and made: build to order); a chip product's chips sold to the market. |
| `plant_units` | FLOAT | no | Good units from the company's plants. |
| `contract_units` | FLOAT | no | Units from its contracts. |
| `own_chips` | FLOAT | no | The company's own chips used (internal supply at cost, no revenue). |
| `bought_chips` | FLOAT | no | Chips bought at the market price. |
| `internal_units` | FLOAT | no | A chip product: chips its company's devices and servers used. |
| `bom_cents` | BIGINT | no | Bill of materials at the good's index, to `5000_cogs`. |
| `chip_cents` | BIGINT | no | Chips (own at cost, bought at market), to `5000_cogs`; a chip product: its market chips' cost. |
| `assembly_cents` | BIGINT | no | Contract fees and plants' cost per unit run, to `5000_cogs`. Plants' fixed cost posts in phase 6 ("Assembly plant operations", `5000_cogs`). |
| `lost_units` | FLOAT | no | Demand above what it could make, lost to the next-best product. |

`5000_cogs` (existing) now carries hardware's cost of goods: the player's from `production_month`, a rival's at its market's `hosting_cents` a unit.

## Executives' pitches and era windows (migration `0032_pitches`, M13b)

Existing saves start with no rows; without a `pitch_policy` row the Holiday spend limit is the default, 5% of cash.

### exec_pitch

A big move an executive proposes (formulas.md 27.1). Every pitch stays: executives' records count them all.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key; max(id) + 1 is the next. |
| `company_id` | INTEGER FK company | no | The company. |
| `seat` | VARCHAR(8) | no | The executive's seat (`cpo`, `cro`, `cto`, `coo`, `cmo`, `cfo`) or `ceo`. |
| `person_id` | INTEGER | no | The executive. |
| `turn` | INTEGER | no | The month it was pitched. |
| `kind` | VARCHAR(16) | no | `new_product`, `sunset`, `region`, `research`, `data_centre`, `office`, `plant`, `campaign` or `buyback`. |
| `params` | JSON | no | What approving runs: a category and segment, a product and region, a domain, a facility kind and size, a city, an amount. |
| `title` | TEXT | no | What, in a few words. |
| `why` | TEXT | no | Two or three driver numbers, from what the company can see. |
| `cost_cents` | BIGINT | no | Its cost over `pitch.cost_months` (12): the auto-approve test. |
| `capex_cents` | BIGINT | no | Up-front cost. |
| `monthly_cents` | BIGINT | no | Monthly cost. |
| `hires` | INTEGER | no | People it hires. |
| `unit` | VARCHAR(16) | no | The case's unit: `cents_month`, `cents`, `points`, `people` or `customers`. |
| `low` | BIGINT | no | The low case at 24 months, in `unit`. |
| `high` | BIGINT | no | The high case. |
| `risk` | TEXT | no | The risk, in words. |
| `central` | BIGINT | no | The central case from displayed estimates: a hit reaches it, the same yardstick for every executive. |
| `status` | VARCHAR(16) | no | `pending`, `approved`, `auto_approved` (on Holiday, under the limit), `declined`, `modified` or `lapsed` (still pending at the executive's next quarterly draw). |
| `resolved_turn` | INTEGER | yes | When it was answered. |
| `target_id` | INTEGER | yes | What approving created: a product, unit, facility or office. |
| `baseline` | BIGINT | no | The tracked measure when approved, in `unit`. |
| `outcome` | VARCHAR(16) | yes | `hit` (at or above `central`), `miss` or `too_early`, `pitch.record_months` after approval. |
| `outcome_turn` | INTEGER | yes | When it was scored. |
| `measured` | BIGINT | yes | The tracked measure when scored, in `unit`. |

### pitch_policy

The player's pitch settings per company (27.1).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `company_id` | INTEGER FK company | no | Primary key. |
| `auto_approve_cents` | BIGINT | yes | The Holiday spend limit; NULL = `pitch.auto_approve_cash_bp` of cash (5%); 0 = always ask. |
| `stop_for_big` | BOOLEAN | no | A Holiday stops for a pitch at or above the limit. |

### era_window

A player first mover's era window and the baseline its era report compares against (27.3).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `era_key` | VARCHAR(32) | no | Primary key, with `company_id`: `eras.yaml` era key. |
| `company_id` | INTEGER FK company | no | The first mover. |
| `start_turn` | INTEGER | no | The era's arrival. |
| `products` | JSON | no | `[product id, customers, MRR cents]` of each affected product at arrival. |
| `trend` | FLOAT | no | The company's monthly MRR growth over the 12 months before, as a fraction. |
| `demand` | JSON | no | `[category, addressable customers]` at arrival, for each of the era's categories. |
| `reported` | BOOLEAN | no | The era report was sent at the window's end. |

## The founder in public (migration `0033_press`, M14b)

Press moments, public promises, credibility, feuds with rival CEOs, rival CEOs' statements and recent departures (formulas.md 29), plus two side tables for the new hiring fields (29.5). Existing saves start with no rows. The hiring fields are side tables rather than new columns on `search` and `hiring_plan` because migration `0013_rivals` loads and writes those tables through the current models (the same reason as `search_level` and `search_city`). Everything here is public (29.6).

### press_moment

A press moment (29.1). Every moment keeps its row; the state holds the `pending` and `queued` ones and those raised in the last 12 months. Index `ix_press_moment_turn (turn)`.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key; max(id) + 1 is the next. |
| `company_id` | INTEGER FK company | no | The company in the news. |
| `trigger` | VARCHAR(32) | no | `breach`, `outage`, `layoffs`, `earnings`, `era`, `launch`, `acquisition`, `jab`, `rivalry` or `reminder` (a broken promise's "you said ..."). |
| `turn` | INTEGER | no | The month it was raised. |
| `status` | VARCHAR(16) | no | `pending`, `queued` (its event is set for `event_turn`), `skipped` (over the quarterly cap) or `answered`. |
| `event_turn` | INTEGER | yes | The month its event is shown. |
| `product_id` | INTEGER | yes | The product it concerns. |
| `rival_id` | INTEGER | yes | The rival company it names (`company.id`, no FK). |
| `facts` | JSON | no | `[key, value]` pairs of displayed facts, for the template and the LLM. |
| `tone` | VARCHAR(16) | yes | The answer: `bold`, `measured` or `deflect`. |
| `answered_turn` | INTEGER | yes | When it was answered. |
| `share_bp` | INTEGER | yes | A bold claim: the product's displayed share when it was made, bp. |
| `backfired` | BOOLEAN | no | The bold claim has backfired. |

### press_promise

A public promise (29.2), judged on displayed values only. The state holds every promise.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key; max(id) + 1 is the next. |
| `company_id` | INTEGER FK company | no | The company that promised. |
| `kind` | VARCHAR(32) | no | `ship`, `beat`, `research`, `no_layoffs` or `no_price_rise`. |
| `made_turn` | INTEGER | no | When it was made. |
| `deadline_turn` | INTEGER | no | When it is judged. |
| `moment_id` | INTEGER | yes | The press moment it was made in (`press_moment.id`, no FK). |
| `product_id` | INTEGER | yes | Ship, beat, no price rise: the product. |
| `rival_product_id` | INTEGER | yes | Beat: the rival product. |
| `domain` | VARCHAR(32) | yes | Research: the domain. |
| `level` | INTEGER | yes | Research: the displayed lead to reach. |
| `baseline` | INTEGER | no | The displayed value when made (quality or lead). |
| `prices` | JSON | no | No price rise: `[segment, price cents]` displayed when made. |
| `ambition` | FLOAT | no | How ambitious the promise was. |
| `audience` | FLOAT | no | The audience weight `a` when made. |
| `status` | VARCHAR(16) | no | `open`, `kept` or `broken`. |
| `resolved_turn` | INTEGER | yes | When it was kept or broken. |
| `reminder_turn` | INTEGER | yes | A broken promise's "you said ..." month. |

### credibility

A company's public credibility (29.3).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `company_id` | INTEGER FK company | no | Primary key. |
| `value` | FLOAT | no | Credibility, 0-100. |
| `history` | JSON | no | The last `press.cred_history` changes: `[turn, change, cause in words]`. |
| `fired_turn` | INTEGER | yes | The month `fired` counts, for a layoffs moment. |
| `fired` | INTEGER | no | People fired that month. |
| `staff_start` | INTEGER | no | Staff at the start of that month. |

### feud

The player's founder against one rival's CEO (29.4).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `company_id` | INTEGER FK company | no | Primary key, with `rival_id`: the player's company. |
| `rival_id` | INTEGER | no | The rival company (`company.id`, no FK). |
| `score` | FLOAT | no | The feud, 0-100. |
| `causes` | JSON | no | Its last changes: `[turn, change, cause in words]`. |
| `rivalry_turn` | INTEGER | yes | When it last reached rivalry. |

### rival_statement

A rival CEO's public statement (29.4). Every statement keeps its row; the state holds the last 24 months. Index `ix_rival_statement_turn (turn)`.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key; max(id) + 1 is the next. |
| `rival_id` | INTEGER | no | The rival company (`company.id`, no FK). |
| `person_id` | INTEGER | no | Its CEO. |
| `turn` | INTEGER | no | When it was said. |
| `kind` | VARCHAR(16) | no | `statement` (at its own launch or price cut), `jab` (aimed at the player; opens a moment) or `answer` (to a bold claim that named it). |
| `text` | TEXT | no | What was said. |
| `product_id` | INTEGER | yes | The product it concerns. |

### departure

Someone who resigned or was poached (29.5): the source of a Replace plan once their employment has ended. One row per person (a later departure replaces it); the state holds the last `recruit.replace_window` months (3). Index `ix_departure_turn (turn)`.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `person_id` | INTEGER | no | Primary key: the leaver (no FK). |
| `company_id` | INTEGER FK company | no | The company they left. |
| `role` | VARCHAR(64) | no | `roles.yaml` role. |
| `level` | VARCHAR(16) | no | Their level. |
| `unit_id` | INTEGER | yes | Their unit (`org_unit.id`, no FK); null = the company root. |
| `reason` | VARCHAR(16) | no | `resigned` or `poached`. |
| `turn` | INTEGER | no | The month they left. |
| `name` | VARCHAR(128) | no | Their name when they left, for the Replace plan's words. |

### search_interest

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `search_id` | INTEGER PK FK → search.id | no | The search. |
| `interest` | VARCHAR(32) | no | `interests.yaml` key: candidates with this interest only (29.5). No row: any interest. |

### hiring_plan_detail

A hiring plan's M14b fields (29.5). No row: all null.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `plan_id` | INTEGER PK FK → hiring_plan.id | no | The plan. |
| `interest` | VARCHAR(32) | yes | `interests.yaml` key: its searches find candidates with this interest only (a fee per search). |
| `replace_of` | INTEGER | yes | A Replace plan: the leaver it replaces (`person.id`, no FK). |
| `level` | VARCHAR(16) | yes | A Replace plan: the leaver's level; its searches generate candidates at it. |

## Mergers and acquisitions (migration `0034_mna`, M14)

The M&A records keep their fields in a JSON `data` column: each is the frozen record in `backend/tst/sim/mna/models.py` without its key columns, tuples as JSON lists. Saves made before M14 have no rows, so a company that never buys plays as before.

| Table | Key | Columns | Notes |
| --- | --- | --- | --- |
| `rival_listing` | `company_id` | `sentiment` (float) | A listed rival's sentiment S (28.1); its market cap is V_f × S. A row appears in a rival's first listed month (`listed_from` in `incumbents.yaml` / `entrants.yaml`). |
| `company_parent` | `company_id` | `parent_id` | A kept brand's parent (28.5, ADR-0020). No row: an independent company. |
| `mna_target_file` | `acquirer_id`, `target_id` | `data`: `problems` (list of `tech_debt`, `key_person_risk`, `customer_concentration`; **hidden** until diligence or closing), `diligence_turn`, `diligence_done_turn`, `board_bar` (**hidden**), `counter_cents`, `blocked_until` | What one acquirer knows of one target (28.2–28.3). |
| `mna_deal` | `id` | `data`: `acquirer_id`, `target_id`, `price_cents`, `cash_share` (0–1), `made_turn`, `status` (`accepted`, `review`, `blocked`, `refused` (blocked after a review, final), `closed`, `abandoned`, `failed`), `hostile`, `close_turn`, `review_end_turn`, `combined_share`, `market`, `blocked_draw` (**hidden**), `remedy_product_id`, `mode` (`brand`, `integrate`), `resolved_turn`, `loan_cents` | A deal on its way to closing (28.3–28.4). |
| `mna_acquisition` | `deal_id` | `data`: `acquirer_id`, `target_id`, `mode`, `closed_turn`, `price_cents`, `directive` (`grow`, `harvest`, `defend`), `distance`, `cost_before_cents`, `key_people`, `pool_kept`, `let_go`, `departed`, `problems`, `product_ids`, `unit_ids`, `person_ids` (everyone who came over) | A closed acquisition and its integration progress (28.5). |
| `mna_acquired_person` | `person_id` | `data`: `deal_id`, `until_turn`, `brand`, `flight_mult` | An acquired key person during culture clash (28.5); the row goes when clash ends or they leave. |

Rivals now also get a `finance_history` row: their monthly operating result in `op_history`, as the player's, for V_f's trailing margin (28.1). Accounts `1800_goodwill` and `1810_investment_subsidiaries` are new in `accounts.yaml`.

## Modes, scores, rankings and ventures (migration `0035_m15b`, M15b)

Each record keeps its fields in a JSON `data` column: the frozen record in `backend/tst/sim/modes/models.py` without its key columns. Saves made before M15b have no rows: a campaign with no score history, no rankings and no ventures. `save_meta.schema_version` is 35.

| Table | Key | Columns | Notes |
| --- | --- | --- | --- |
| `company_score` | `company_id`, `turn` | `data`: `score` (0–1,000), `value_cents` (market cap if listed, else the displayed value range's midpoint; never V_f), `growth`, `profit`, `leadership`, `reputation` (each 0–1), `revenue_cents` (trailing 12 months) | Every December's snapshot and the month a game ends (30.1). Public inputs only. |
| `game_mode` | `id` (always 1) | `data`: `kind` (`campaign`, `sandbox`, `scenario`), `start_turn`, `scenario` (a `scenarios.yaml` `historical` key), `rivals` (`all`, `half`, `none`), `eras` (`historical`, `seeded`), `result` (`success`, `failure`), `result_turn` | How the save plays (30.2–30.3). No row: a standard campaign. |
| `ranking` | `turn`, `kind`, `place` | `data`: `company_id`, `value` (revenue cents, or the list's 0–1 measure) | Each January's lists (30.4): `revenue` (top 50), `places`, `innovative`. |
| `product_quarter_mark` | `product_id` | `data`: `turn`, `quality`, `customers` | A product at the last quarterly reports: the next reports' starting values. Replaced each quarter. |
| `venture` | `company_id` | `data`: `name`, `founded_turn`, `ended_turn`, `outcome` (`exit`), `buyer_id`, `price_cents`, `proceeds_cents` (the founder's share), `kept_cents` (what they kept rather than invest) | A company the player sold (addendum 10). History, the score and the Hall of Fame show each apart. |

Also new: `save_meta.game_state` values `scenario_done` (a historical scenario judged) and `retired` (the founder retired after an exit); the knowledge actions `public_appearance`, `rival_approach` and `rival_diligence` in reveal records of rival CEOs (addendum 11); the `llm_text.kind` value `rival_story` (addendum 12); `mna_target_file.data` gains `counter_exact` (**hidden**), `rounds` and `strikes` (negotiation, addendum 9) and `mna_deal.data` gains `own_remedy_product_id` (addendum 15).

## Small rival startups (migration `0036_m15a`, M15a)

### startup_small

A rival startup's current run of month ends below `rivals.startup.small_staff` people (formulas.md 30.7 V5). At `rivals.startup.small_months` consecutive small month ends it closes (shut down or acqui-hired). No row: not small; the row is deleted when it grows back.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `company_id` | INTEGER FK company | no | Primary key: the startup. |
| `since_turn` | INTEGER | no | The first month end of the current small run. |

## The founder's life (migration `0037_founder`, M24)

The founder's own records (formulas.md 32). `founder_life`, `foundation` and `influence` keep their fields in a JSON `data` column: the frozen record in `backend/tst/sim/founder/models.py` without its key columns. Saves made before M24 have no rows: at the next month end their founder starts at stress 20 and every trait at 20. `save_meta.schema_version` is 37.

| Table | Key | Columns | Notes |
| --- | --- | --- | --- |
| `founder_life` | `person_id` | `data`: `stress` (0–100), `visionary`, `ruthless`, `beloved`, `reckless` (0–100 each), `burnout`, `burnout_turn`, `recovered_turn`, `burnouts`, `budget` (this month's energy budget), `rest_turn` (a month off taken at a burnout), `causes` ([turn, change, words] of stress), `trait_causes` ([turn, trait, change, words]), `holiday_months` | Public (32.8). Kept across a serial founder's companies. |
| `personal_entry` | `id` (autoincrement) | `turn`, `person_id`, `memo`, `source` (`secondary`, `dividend`, `exit`, `salary`, `gift`, `grant`), `lines` (JSON list of [account, cents], summing to 0) | The founder's own double-entry book (32.2, ADR-0003), apart from `ledger_entry`: only the `personal_accounts` of `accounts.yaml` (9100 personal cash, 9200 foundation endowment, 9300 personal spending, 9400 personal income), which no company entry may use. Append-only. |
| `foundation` | `person_id` | `data`: `name`, `cause` (`education`, `climate`, `health`, `local`), `created_turn`, `city` (local: a `cities.yaml` key), `region` (the founder's home region when created), `grants_cents` (lifetime), `last_grant_cents`, `last_grant_turn`, `gifts_cents` | 32.3. The endowment is the founder's 9200 balance. |
| `influence` | `company_id`, `region` | `data`: `value` (0–100), `spend_cents` (monthly lobbying), `risk` (**hidden**: the scandal risk), `scandal_turns`, `spent_cents`, `started_turn`, `second_story` (**hidden**: fighting the last scandal brings a second story) | 32.5. The API shows the risk only as an exposure word (low, medium, high) and never `second_story`. |

Also new: company account `6950_lobbying` (expense; monthly lobbying by region; scandal fines post to `6900_general_admin`); `decision_log` payloads carry `holiday` in a turn's `Decisions` (a Holiday month lowers stress); action kinds `sell_founder_shares`, `create_foundation`, `give_to_foundation` and `set_lobbying`; event templates `founder_burnout`, `founder_scandal` and `founder_first_grants` (trigger `founder_life`, effect `founder_step`).

## The founder's own investments (migration `0044_m26`, M26)

The founder's personal investing (formulas.md 37). Each table keeps a frozen record of `backend/tst/sim/founder/investing_models.py` in a JSON `data` column, without its key columns. Money is integer cents; stakes are millionths (ppm) of a startup. Saves made before M26 have no rows: rounds, the index and net worth are recorded from their next month end. `save_meta.schema_version` is 44.

| Table | Key | Columns | Notes |
| --- | --- | --- | --- |
| `startup_round` | `id` | `data`: `company_id`, `turn`, `raised_cents`, `post_cents` (the round's price), `source` (`founded`, `funded`, `venture`, `angel`, `backed`) | Every rival startup's round (15.4), corporate venture investment (31.5) and the founder's cheques (37.2). Public. |
| `angel_stake` | `id` | `data`: `person_id`, `company_id`, `stake_ppm`, `cost_cents`, `from_turn`, `last_post_cents`, `backed`, `founder_known`, `status` (`open`, `acquired`, `listed`, `failed`), `closed_turn`, `proceeds_cents`, `coi_turn`, `coi_answer` (`disclose`, `conceal`, `found`), `coi_found_turn` (**hidden**: the month a concealed conflict comes out) | The founder's stake in a private startup (37.2). |
| `personal_trade` | `id` | `data`: `person_id`, `company_id`, `turn`, `side` (`buy`, `sell`), `shares`, `price_cents`, `cost_cents`, `filed`, `sensitive_target_id` (the deal in preparation it was ahead of), `risk`, `public_turn`, `investigate_turn`, `gain_cents` (**hidden**: regulatory risk, when the news went public, the investigation's month drawn, the gain), `resolved`, `investigated_turn`, `finding_turn` | Trades of listed shares (37.3). The API shows only `sensitive`, `filed` and an opened investigation. |
| `public_holding` | `person_id`, `company_id` | `data`: `shares`, `cost_cents` | Listed shares held (37.3); for the founder's own company only the shares bought (they sit on its cap table). |
| `family_office` | `person_id` | `data`: `formed_turn`, `manager_id` (a generated person, kept loaded), `mandate` (`conservative`, `balanced`, `aggressive`), `returns` ([turn, return] the last 240 months) | The family office (37.4); its balance is the personal book's 9130. The manager's finance skill is hidden (shown as the revealed range). |
| `wealth_point` | `person_id`, `turn` | `data`: `cash_cents`, `angel_cents`, `public_cents`, `family_office_cents`, `own_stake_cents` | Net worth at each month end (37.5). |
| `market_index` | `turn` | `data`: `level` (1.0 in the first month recorded), `month_return`, `caps` ([company_id, market cap] of every listed company) | The value-weighted market index (37.4), the last 240 months. |
| `founder_network` | `person_id` | `data`: `turn` (the month they left) | People who left the player's companies (37.2), the last `angel.network_size`; their person records stay loaded. |

Also new: personal accounts `9110_angel_investments`, `9120_public_shares`, `9130_family_office` (assets), `9410_investment_gains`, `9430_dividends_received` (revenue), `9420_investment_losses` (expense) in `accounts.yaml`'s `personal_accounts`; `personal_entry.source` adds `angel`, `shares`, `family_office`, `dividends`, `fine`. Action kinds `join_round`, `back_startup`, `trade_shares`, `form_family_office`, `move_family_office`, `set_office_mandate`; event templates `personal_conflict`, `personal_filing`, `personal_investigation`, `personal_finding` (trigger `founder_life`, effect `founder_step` with `disclose`, `conceal`, `accept_finding`, `deny_finding`); RNG stream `personal` (53).

## Exact contract prices (migration `0038_m15r`, M15r)

`production_contract.price_cents` (FLOAT, 0031) becomes `price_millicents` (BIGINT): the unit fee or wafer price in exact integer thousandths of a cent (Codex review 4 finding 8). Existing rows convert once, `ROUND(price_cents x 1000)`. `save_meta.schema_version` becomes 38 (after M24's `0037_founder`).

Also from M15r, without a schema change: a sold company's `board_seat` rows (and their `board_seat_history`) are deleted when the founder founds again; `ceo.end_reason` may be `acquired`; the exit sale's `mna_deal` has `mode` `brand` and an `mna_acquisition` row from the month of the sale.

## The holding company and its subsidiaries (migration `0039_m16`, M16)

### group_ownership

One company's holding of another over a run of turns (formulas.md 31.1; Codex review 4 findings 2 and 3). Group membership, ultimate owners, consolidation and antitrust read it by period: a company is inside its owner's group from `from_turn` (the closing; its lines up to then are opening balances) to `to_turn` (inclusive; a disposal posts then), and inside its owner's owner's group while both hold. A company has at most one open holding. Upgraded saves get an open holding for each kept brand in `company_parent`, from its latest brand closing by that parent; a brand that had already failed is disposed of at the next month end. `save_meta.schema_version` is 39.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key. |
| `company_id` | INTEGER | no | The company held (indexed). |
| `owner_id` | INTEGER | no | Its direct owner. |
| `data` | JSON | no | `from_turn`, `to_turn` (null while held), `book_cents` (the owner's 1810 investment at closing: the company's book equity then), `equity_cents` (the company's equity accounts' balance then, debit positive: the investment now is `book_cents` less the change in the company's equity since), `stake_bp` (10,000 = 100%), `end_reason` (`failed`, `sold`, `spun_off`, `integrated`; null while held). |

### group_holding

The player's holding company (formulas.md 31.2), once formed: a `company` row ("<Name> Holdings", `is_player` true, stage 5, `rival_key` [5, n]) that holds the listing (`public_company`, `guidance`), the board (`board_seat`) and every cap-table holder but the operating company's option pool and grants; the operating company's cap table then holds one `group` entry for the holding company. The IPO chain's `listing` row stays the operating company's history. Events and inbox items for the holding company reach the player's inbox.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `company_id` | INTEGER | no | Primary key: the holding company. |
| `data` | JSON | no | `operating_id` (the company it was formed over, the one the player runs), `formed_turn`, `chair_id` (the founder, its Chair). |

### group_stake

A stake the group does not control (formulas.md 31.3, 31.5): bought on the market in a listed rival, a corporate venture investment in a startup's round, or what the group kept of a spin-off. 20–50% is an associate (equity method, `1820`): each month its carrying amount moves by the stake's share of the company's operating result (against `4910`). Under 20% it is a financial investment (`1830`) marked each December to fair value (against `4920`): the stake x the market cap if listed, else x the midpoint of the displayed value range (28.1; never the hidden value).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key. |
| `owner_id` | INTEGER | no | The group company holding it. |
| `company_id` | INTEGER | no | The company held. |
| `data` | JSON | no | `stake_bp`, `cost_cents`, `carrying_cents` (the owner's balance for it on 1820 or 1830), `from_turn`, `kind` (`market`, `venture`, `retained`), `to_turn` (null while held), `disclosed_bp` (the highest disclosure line crossed: 5%, 10%, 25%). |

### group_mandate

A subsidiary's mandate (formulas.md 31.4): what its CEO runs it for. It sets the directive the subsidiary decides under (grow -> grow, return cash -> harvest, margin -> defend) and the months of costs it keeps before its cash goes up (`group.mandate.*_keep_months`; without a mandate M14's `mna.sweep_months`). Each December its board scores the CEO against it.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `company_id` | INTEGER | no | Primary key: the subsidiary. |
| `data` | JSON | no | `kind` (`grow`, `margin`, `return_cash`), `set_turn`, `capex_limit_cents` (0: none), `categories`, `regions` (empty: any), `misses` (Decembers missed in a row), `last_review_turn`, `last_result` (e.g. "missed: revenue growth 12% (target 25%)"), `equity_cents` (its equity balance at the last review: what it paid up since is the change), `proposal` (the board proposes a new CEO). |

### group_pitch

A subsidiary CEO's request to the group for capital (31.4), each quarter on a draw (stream `group`), judged against the mandate; approved, its owner funds it (1810 against the subsidiary's 3000); unanswered by the next quarter, it lapses.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key. |
| `company_id` | INTEGER | no | The subsidiary. |
| `data` | JSON | no | `person_id` (its CEO), `turn`, `amount_cents`, `fits_mandate`, `status` (`pending`, `approved`, `declined`, `lapsed`), `resolved_turn`. |

### group_listing

A company the group listed (formulas.md 31.5): a carve-out (10–40% sold to the public; the group keeps control) or a spin-off (its shares given to the holding company's shareholders: an independent listed rival). Either trades like a listed rival (28.1: V_f x the sentiment in `rival_listing`, which it gets a row in).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `company_id` | INTEGER | no | Primary key: the company listed. |
| `data` | JSON | no | `listed_turn`, `kind` (`carve_out`, `spin_off`), `shares` (shares outstanding at listing, 10,000,000). |

### group_personal_stake

Shares the founder holds in their own name in a spun-off company (31.5): their pro-rata part of what was given out (their share of the holding company x the share distributed), a holding, not cash (M24's book holds cash only).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `person_id` | INTEGER | no | Primary key, with `company_id`: the founder. |
| `company_id` | INTEGER | no | Primary key, with `person_id`: the spun-off company. |
| `data` | JSON | no | `stake_bp`, `turn`. |

### group_transfer_flow

One company of the player's group supplying another (formulas.md 31.6): compute (the buyer's `6300_compute`) or chips (`5000_cogs`). Each month the buyer's spend on the good is supplied in-group: its outside purchase is reversed, the seller's cost is `group.supply_cost` (80%) of it, and the buyer pays the seller the transfer price (`5900_intercompany_purchases` / `4300_intercompany_sales`, both removed in consolidated statements). A flow ends when either company leaves the group.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key. |
| `data` | JSON | no | `seller_id`, `buyer_id`, `good` (`compute`, `chips`), `kind` (`cost`, `cost_plus`, `market`), `margin` (cost plus; null: `group.cost_plus`), `set_turn`, `unfair_months` (months running more than `group.fairness_band` from market while a company of the flow has minorities), `complaint` (a minority complaint stands: the minority-held company pays `group.complaint_legal` of its revenue a year in legal costs, 6900, and is valued `group.complaint_discount` lower), `complaint_turn`, `trailing` (the transfer price paid at the last 12 month ends: the intra-group share of 31.7's conglomerate discount), `ended_turn`. |

Event template `minority_complaint` (trigger `group`, critical; effect `group_step`: `correct_price` moves the flows under complaint to market, `defend_price` keeps them).

A subsidiary's cap table (`cap_entry`) opens the first time outsiders buy in: its owner's `group` entry for 10,000,000 shares, then `firm` entries for investors who bought a stake (an `investors.yaml` firm drawn on stream `group`) and a `group` "Public float" entry for a carve-out. A buyout removes them.

With minorities (a stake under 100%), a subsidiary's spare cash goes up as a **dividend** to every holder pro rata (its memo "Dividend to shareholders"; the owner's share against its 1810) instead of M14's sweep, and its owner no longer funds its shortfalls.

`group_ownership.data` also carries `rebases` ([turn, stake_bp, book_cents, equity_cents] at each stake change: from that turn the stake and the investment's basis are the rebase's; the investment is `book − stake × (equity now − equity)`), `goodwill_cents` (the goodwill an owner carries for a company passed to it inside the group; null: from the acquisition) and `common_control` (a reorganization: forming the holding company; the group's entry difference is equity, not goodwill). `end_reason` may be `transferred` (a brand passed from the operating company to the holding company).

Also new: company accounts `1820_investment_associates` (asset: 20–50% stakes, equity method), `1830_financial_investments` (asset: stakes under 20% at fair value, marked each December), `3500_non_controlling_interest` (equity: outside holders' share of consolidated subsidiaries, in consolidated statements), `4910_share_of_associates`, `4920_fair_value_gains` and `4930_gain_on_disposal` (revenue type, shown below the operating result as "other gains" and included in the net result), and `4990_nci_share_of_profit` (expense type, consolidated statements only: the outsiders' share of the net result, shown below it; the balance sheet's accumulated result is the owners'). A holding's end posts the owner's 1810 investment and the goodwill it booked out, any cash received in, and the difference to 4930 (a debit is a loss). `company_parent` stays the current direct owner; `group_ownership` is the history. RNG stream `group` (45). Balance keys `group.*` (balance.yaml).

## Prospecting and exploration (migration `0042_m18`, M18)

Each record keeps its dataclass fields in a JSON `data` column (`tst/db/exploration_io.py`). Upgraded saves get their geology at the migration, drawn exactly as a new game of the same seed draws it at turn 0 (stream `geology`). Account `6600_exploration` (expense): everything spent on exploration, expensed as spent; a project's sale posts to `4930_gain_on_disposal`. `save_meta.schema_version` is 42.

### exploration_block

Every block's hidden truth (formulas.md 34.1; ADR-0007). Read by the sim only; the API never reads it.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `region` | TEXT | no | Primary key with `idx`: a regions.yaml key. |
| `idx` | INTEGER | no | The block's index in its region, 0 to `geology.blocks_per_region` - 1. |
| `data` | JSON | no | `depth_m` (to the top of the ore; every block has one), `true_commodity` (a geology.yaml key, null: nothing), `true_kind` (hard_rock, brine, placer), `true_tonnage_mt`, `true_grade` (a fraction of ore), `true_recovery`, `true_infra_km`, `true_difficulty` (permitting, x the region's years), `true_sensitivity` (community, 0-1). |

### exploration_supplier_licence

A supplier's exploration licence (34.4): from game start, or from buying a project. Public.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `region` | TEXT | no | Primary key with `block`. |
| `block` | INTEGER | no | The block's index. |
| `data` | JSON | no | `supplier` (M17's suppliers.yaml key), `name`. |

### exploration_desk_study

A desk study of one commodity in one region (34.2).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key. |
| `company_id` | INTEGER | no | The group company that ran it. |
| `data` | JSON | no | `region`, `commodity`, `start_turn`, `done_turn` (the month it reports), `factor` (the team's reading factor: hidden, it would reveal skill; never sent to the API), `bands` (one of low, medium, high per block in index order once done; empty while it runs). |

### exploration_project

A licensed block and its pipeline (34.2-34.3). Revealed results, plus one hidden field.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key. |
| `company_id` | INTEGER | no | The group company exploring. |
| `data` | JSON | no | `region`, `block`, `licence_turn`, `expires_turn` (first month without the licence), `renewals`, `status` (active, permitted, refused, sold, relinquished, lapsed), `commodity`, `stage` (running now), `stage_start`, `stage_due`, `holes_left`, `paused_until` (an accident), `spent_cents`; survey `reading` (none, weak, strong) and `kind`; sampling `sample_center` and `sample_hw` (log grade, half-width at the stated confidence); estimate `category`, `est_holes`, `est_grade_center`/`_hw`, `est_tonnage_center`/`_hw` (log Mt), `est_turn`; the latest study's `level`, `capex_center`/`_hw` (log dollars), `opex_center`/`_hw` (log dollars a tonne of product), `recovery_center`/`_hw`, `npv_lo_cents`, `npv_mid_cents`, `npv_hi_cents`, `study_turn`; permitting `permit_start`, `hidden_due_turn` (the decision month, drawn from the block's hidden difficulty: never sent to the API), `benefit`, `pushes`, `protest_turn` (the month an open protest event is shown), `protests`, `permit_turn`; sale `sold_to`, `sale_cents`; `ended_turn`. |

### exploration_hole

A drill hole's assay (34.2): public once drilled; never changes.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `project_id` | INTEGER | no | Primary key with `n`. |
| `n` | INTEGER | no | The hole's number within the project, from 1. |
| `data` | JSON | no | `turn`, `assay` (a fraction of ore), `factor` (the team's range factor when drilled: hidden), `cost_cents`. |

## Mining operations (migration `0043_m19`, M19)

Each record keeps its dataclass fields in a JSON `data` column (`tst/db/mining_io.py`). A mine is also a `facility` row of kind `mine` (balance.yaml `facility.kinds.mine`, module `mining`): owner, region, capacity (t a year, rounded), status, the staffing unit and the study's capex estimate; the generic capex, depreciation, operating cost and sale skip it. A founded subsidiary is a `company` row (`is_player` false, no personality, `rival_key` (6, n)) with its parent in `company_parent` and its holding in `ownership`. New accounts: `1520_mineral_properties` (asset: a mine's capex as paid and its project's capitalized exploration spend, less depletion, write-offs and stakes sold), `2610_asset_retirement_obligation` (liability: reclamation provisioned a tonne from first output, paid after closure; 2600 is SAFEs'), `4400_revenue_commodities` (revenue: a mine's spot, contract and offtake sales), `6750_depletion` (expense: units-of-production depletion and closure write-offs), `6960_royalties` (expense: royalties and a state partner's share of the cash margin). `save_meta.schema_version` is 43.

### mine

A mine (formulas.md 35.2-35.4), by its facility's id. The hidden_* fields are true values (ADR-0007): read by the sim only; the API never reads them.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key: the mine's facility id. |
| `company_id` | INTEGER | no | The group company that owns it. |
| `data` | JSON | no | `project_id` (M18's project), `region`, `block`, `commodity` (geology.yaml key), `subtype` (open_pit, underground, brine), `level` (the study it was built on), `capacity_t` (product a year at the design grade), `design_grade`, `design_recovery` (the study's centres), `ordered_turn`, `ready_turn` (first production month), `estimate_cents` (the study's capex for this capacity), `hidden_overrun` (share over the estimate, hidden until revised), `hidden_ore_mt`, `hidden_grade`, `hidden_recovery` (the deposit's truth), `status` (building, producing, care, restarting, seized, closed), `revised_cents` (the whole capex once revised; null before), `capex_paid_cents`, `moved_cents` (exploration spend capitalized at the build), `depleted_cents` (1520 credited: depletion, write-offs, a state stake), `ore_mined_mt`, `product_t`, `first_output_turn`, `buyer_id`, `price_kind`, `margin` (group sales at the transfer price; null buyer: spot), `safety` (low, normal, high), `aro_cents`, `aro_paid_cents` (reclamation provisioned and paid), `closed_turn`, `close_reason` (depleted, chosen, sold_to_state, seized, sold), `below_months` (months running under the all-in cost), `crash_turn`, `crash_answered`, `care_since`, `restart_due`, `stopped_until` (no output through this month: an investigation, consultation or blockade), `accident_turn`, `accidents`, `protest_turn`, `protests`, `benefit` (a community benefit agreement), `state_share` (a state partner's stake), `ban_until` (an export ban's last month), `takeover_turn`, `arbitration_due`, `seized_book_cents`; `*_turn` fields of an open event are the month it is shown; `history` (the last 24 months, each `[turn, output_t, grade, price_usd_t, cost_usd_t, revenue_cents, margin_cents]`: revealed as mined). |

### mine_deal

A sale a mine signs as seller (35.3).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key. |
| `mine_id` | INTEGER | no | The mine. |
| `data` | JSON | no | `kind` (contract: a fixed price; offtake: a collar around the price at signing), `buyer`, `signed_turn`, `end_turn` (last month covered), `volume_t_year`, `signing_usd_t`, `floor_usd_t`, `ceiling_usd_t`, `delivered_t`, `last_usd_t`. |

### mine_rival_bid

A rival miner's bid for a group project or mine (35.5), open three months.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key. |
| `company_id` | INTEGER | no | The group company holding the asset. |
| `data` | JSON | no | `supplier` (suppliers.yaml key), `project_id` or `mine_id`, `cents`, `turn`, `expires_turn`, `status` (open, accepted, declined, lapsed). |

## Refining and wafers (migration `0045_m20`, M20)

A refinery is a `facility` row of a refinery kind (`silicon_smelter`, `poly_plant`, `poly_plant_semi`, `wafer_plant`, `li_converter`, `co_refinery`, `ree_separator`, `byproduct_recovery`; formulas.md 36.1); its `capex_cents` is the true capex with the hidden overrun, never sent to the API. Each record below keeps its dataclass fields in a JSON `data` column (`tst/db/refining_io.py`). Account `4410_materials_sales` (revenue): refined goods and wafers sold at spot or under contract; refineries' inputs, power and operations post to `5000_cogs`; supply between two group companies uses M16's `4300`/`5900`. RNG stream `refining` (51). Balance keys `refining.*` and `facility.kinds.<refinery kinds>`. Existing saves have no refineries. `save_meta.schema_version` is 45 (re-parented after M19's `0043_m19` and M26's `0044_m26`). Own-group mines (M19) feed refineries: `mine_fed` and `mine_protected` on a refinery.

### refinery

A refinery's own state beside its facility row (36.1-36.4).

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `facility_id` | INTEGER | no | Primary key: the plant's `facility.id`. |
| `company_id` | INTEGER | no | The owner. |
| `data` | JSON | no | `recipe` (a `refining.recipes` key), `estimate_cents` (the quoted capex the player saw), `host_id` (a by-product line's host plant), `curb_until` and `curb_run` (a power curb's last month and the share of capacity run), `stop_until` (an incident's stop and investigate: the last month at zero output), `incident_turn` (an open incident event's month), `incidents`, `last_depreciated_cents` (the facility's accumulated depreciation at the last month, for the month's charge), `mine_fed` (input units the group's mines supplied this month, in place of spot), `mine_protected` (last month's: input that keeps 100% allocation this month), `month` (the latest month: `turn`, `output`, `capacity`, `yield_`, inputs from `input_group`/`input_contract`/`input_spot` and `input_short`, `input_cents`, `power_cents`, `power_index`, `other_cents`, `fixed_cents`, `depreciation_cents`, `staff_cents`, output `to_group`/`to_contract`/`to_spot`, `revenue_cents`, `market_cents` and `unit_cost_cents` a unit), `history` (`[turn, output, unit cost, market price]` for the last `refining.history_months`). |

### refining_deal

A refinery contract (36.1): buy an input or sell an output at the signing month's price.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key. |
| `company_id` | INTEGER | no | The company. |
| `data` | JSON | no | `side` (`buy`, `sell`), `good`, `signed_turn`, `end_turn` (the last month covered), `monthly_volume` (volume units a month), `price_cents` (cents a unit), `taken` (so far), `last_taken` (last month), `charged_cents` (a buy contract's take-or-pay so far), `status` (`active`, `ended`). |

### refining_supply

The latest month's own-group supply lots (36.1-36.2), replaced each month.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `n` | INTEGER | no | Primary key: the lot's order. |
| `data` | JSON | no | `turn`, `facility_id` (the plant), `seller_id`, `buyer_id`, `good`, `volume`, `unit_cents` (the transfer price), `market_cents`, `product_id` (a wafer lot's chip product; null for commodities), `taken` (what the buyer used after production; the rest sold at spot). |

## Geopolitics and export controls (migration `0046_m22`, M22)

Countries, blocs, export controls and tariffs are data (`countries.yaml`, `export_controls.yaml`, `tariffs.yaml`; formulas.md 39), the same on every seed; `cities.yaml` gains `country` on every city. What play adds lives in `geo_record`, one row a record (`tst/db/geopolitics_io.py`). Accounts `5100_tariffs` and `5110_local_partner_share` (expense, cost of revenue). RNG stream `geopolitics` (55). Balance keys `geopolitics.*`. Existing saves have no records; history applies to them from data. `save_meta.schema_version` is 46. Never stored ahead of its month: a seeded tension month, an escalation's rule and a détente's suspension are added in phase 12 for the next month only.

### geo_record

Every geopolitical record, one row each, rewritten by collection when it changes.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `n` | INTEGER | no | Primary key: the collection's index x 1,000,000 + the record's position (keeps each collection's order). |
| `kind` | VARCHAR | no | The collection: `tension` (`turn`, `value` 0-100, `shock` `none`/`escalation`/`detente`: seeded months after 2025), `seeded_rules` (`rule_key` an export_controls.yaml `seeded` key, `start_turn`, `end_turn`), `suspensions` (`rule_key`, `start_turn`, `end_turn`: a seeded détente's), `licences` (`id`, `company_id`, `product_id`, `rule_key`, `country`, `requested_turn`, `decide_turn`, `status` `pending`/`approved`/`denied`/`expired`/`grey`, `until_turn`), `variants` (`product_id`, `turn`: a compliant variant's launch), `entity_listings` (`company_id`, `actor` a country or bloc, `turn`, `reason`), `sites` (`kind` `company`/`facility`, `id`, `country`, `local_partner`), `exits` (`product_id`, `region`, `segment`, `remaining` customers in closed destinations still on the books, `share` the blocked share last month), `geo_notices` (`turn`, `company_id`, `template_id`, `rule_key`: what a geopolitical event's {rule} names). |
| `data` | JSON | no | The record's fields, as listed under `kind`. |

## M25: files beside the saves (not tables)

`saves/profiles/<profile>.json` (M25 section 2, `tst/profile/store.py`): the player profile's achievements across every save; the profile is `TST_PROFILE` (default `default`). Written atomically under a lock after each committed turn and player action; never read by the sim and never part of a save. Keys: `version` (1), `profile`, `earned` (`{achievement key: {save, company, turn, date_label, earned_at (UTC ISO), seen}}`; `seen` is false until its toast has shown), `watch` (`{save slug: {downturn_from}}`: the month a running downturn began, for "a downturn without layoffs"). Sandbox and modded games add nothing. Achievements are defined in `backend/data/achievements.yaml` (key, title, description, kind, threshold or param, hidden), validated at startup and not hashed into saves.

`saves/mods/<name>.yaml` (M25 section 3, `tst/mods/store.py`): a named mod: `mod_format` (1), `description`, `files` (`{data file: changed values only}`, in each file's own shape; lists of records match by `key`, `id` or `name`). A new game started with it records `save_meta.mod_name`, `mod_hash` and `mod_overlay`.

`backend/data/advisor.yaml` (M25 section 1): the Explain panel's and Ask why's settings (`explain.history_months`, `events_months`, `drivers_named`; `ask.max_question_chars`, `max_answer_words`). Not game data and not hashed. Ask why's calls go to `llm_call_log` with `purpose` `explain`.

## Commodities, offtake and regional power (migration `0041_m17`, M17)

The twelve commodities (`commodities.yaml`; `quartz_hp`, `silicon_metal`, `polysilicon`, `gallium`, `germanium`, `copper`, `tin`, `tantalum`, `cobalt`, `lithium_carbonate`, `ndpr_oxide`, `neon`) and power by region (`power_<region>`, North America 1.0) are rows of `supply_month` (formulas.md 33.1, 33.5): `price_index` is a commodity's price over its 2010–2019 mean (a power row's index against North America), `base` the trend under a shock, `change` 0, and `shock_turn`, `shock_months`, `shock_rise`, `shock_allocation` and `shock_kind` the latest seeded shock after 2025 (a history row carries the history's shortage: its first month and the share). History to December 2025 comes from `commodities_history.yaml` and `power_history.yaml`, never the table. RNG stream `commodity` (47). Balance keys `commodity.*`, `offtake.*` and `power.*` (balance.yaml).

### commodity_deal

A company's commodity contract or offtake agreement (formulas.md 33.3). Prepayments sit in the existing `1200_prepaid` account until drawn against purchases.

| Column | Type | Null | Meaning |
| --- | --- | --- | --- |
| `id` | INTEGER | no | Primary key. |
| `company_id` | INTEGER | no | The buyer (indexed). |
| `data` | JSON | no | `kind` (`contract`: a fixed price for 6–36 months, take-or-pay on the unused volume at the end; `offtake`: 3–10 years with a supplier inside a collar, take-or-pay each month), `good`, `supplier` (suppliers.yaml key; offtakes), `signed_turn`, `end_turn` (the last month covered), `volume_year` (volume units a year), `signing_price`, `floor` and `ceiling` (the collar, the good's price unit; a contract's are its price), `prepaid_cents` and `prepaid_left_cents` (paid at signing, and not yet drawn), `status` (`active`, `ended`, `breached`), `taken` (volume taken so far), `last_taken` and `last_price` (last month's), `hedge_cents` (cost of goods saved against spot so far; negative when the deal cost more), `charged_cents` (take-or-pay so far), `closed_turn`. |
