# Data dictionary

Column-level reference for a save file (`saves/<slug>.tst.sqlite`). Kept current with the Alembic migrations in `backend/migrations/versions/`; ORM models are in `backend/tst/db/models.py`.

- **Schema version:** 3 (migrations `0001_initial`, `0002_people`, `0003_hiring`). Alembic also records its revision in its own `alembic_version` table.
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
| `schema_version` | INTEGER | no | Current schema version; each schema migration sets it (3 after `0003_hiring`). |
| `next_person_id` | INTEGER | no | Next person id to assign. Ids are never reused, because people leave the live state (M1b sweep rule 2). |
| `next_search_id` | INTEGER | no | Next search id. |
| `next_offer_id` | INTEGER | no | Next offer id. |
| `next_employment_id` | INTEGER | no | Next employment id. |

## company

The player company and (from M5) all rivals, handled by the same code (ADR-0010). Current-state table.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Company id. The player company is 1. |
| `name` | VARCHAR(80) | no | Display name. |
| `is_player` | BOOLEAN | no | True for the player's company. |
| `stage` | INTEGER | no | Company stage, 0 (solo founder) to 5 (conglomerate), spec §3. |
| `founded_turn` | INTEGER | no | Turn the company was founded. |
| `mission` | JSON | no | List of two `interests.yaml` keys (formulas.md §7); empty for saves made before M1b. |

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

Index `ix_ledger_line_entry (entry_id)`.

## turn_snapshot

Month-end KPIs per company per turn, written by phase 11. Append-only history.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Row id. |
| `turn` | INTEGER | no | Turn the snapshot closes. |
| `company_id` | INTEGER FK → company.id | no | Company. |
| `kpis` | JSON | no | `{cash_cents, monthly_burn_cents, headcount}`. `cash_cents` equals the `1000_cash` balance through this turn; `monthly_burn_cents` is the net cash decrease this month (0 if cash did not fall); `headcount` counts the company's `active` and `notice` employments (1 for the founder from turn 0). |

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
| `seq` | INTEGER | yes | Order of a player action within its turn (1, 2, 3…; ADR-0014); null for the per-turn `turn_decisions` row. |

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

Energy, stress and morale; one row per person who has any (M1b: the founder's energy, employees' morale).

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER PK, FK → person.id | no | Person. |
| `energy` | FLOAT | yes | Founder energy left this month (formulas.md §6); reset after phase 12. |
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
| `channel` | VARCHAR(16) | no | `network`, `job_post` or `recruiter`. |
| `actor_id` | INTEGER FK → person.id | no | Who opened it; their judgment of talent scouts its candidates. |
| `opened_turn` | INTEGER | no | Turn opened. |
| `status` | VARCHAR(16) | no | `open` or `closed`. Network and recruiter searches close after their one batch. |
| `closed_turn` | INTEGER | yes | Turn closed. |

Index `ix_search_company_status (company_id, status)`.

### candidate

A generated person available to one company. Primary key `person_id`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER PK, FK → person.id | no | The candidate. |
| `company_id` | INTEGER FK → company.id | no | Company that found them. |
| `search_id` | INTEGER FK → search.id | no | Search that found them. |
| `created_turn` | INTEGER | no | Turn whose phase 12 generated the batch. |
| `expires_turn` | INTEGER | no | They leave in phase 12 of this turn unless hired. |
| `status` | VARCHAR(16) | no | `open`, `hired`, `declined`, `expired`, or `withdrawn` (reserved for M2). |
| `resolved_turn` | INTEGER | yes | Turn the status left `open`. |

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

Index `ix_offer_company_status (company_id, status)`.

### person_morale_log

Month-end morale per employee, append-only. Primary key `(person_id, turn)`.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `person_id` | INTEGER FK → person.id | no | Employee. |
| `turn` | INTEGER | no | Turn closed. |
| `morale` | FLOAT | no | Morale after phase 8. |

## Files next to the saves

- `saves/index.json`: list of `{slug, company_name, scenario_id, difficulty, current_turn}`, rebuilt from the save files after each create and turn. The save files are the source of truth; a missing or corrupt index is rebuilt.
- `saves/backups/<slug>/<slug>.turn-<NNN>.sqlite`: periodic backup after every 12th committed turn; the newest 10 are kept.
- `saves/backups/<slug>/<slug>.turn-<NNN>.pre-migration-<rev>.sqlite`: backup taken before upgrading an older save; never pruned.
