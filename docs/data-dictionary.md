# Data dictionary

Column-level reference for a save file (`saves/<slug>.tst.sqlite`). Kept current with the Alembic migrations in `backend/migrations/versions/`; ORM models are in `backend/tst/db/models.py`.

- **Schema version:** 1 (migration `0001_initial`). Alembic also records its revision in its own `alembic_version` table.
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
| `schema_version` | INTEGER | no | Schema version at creation; migrations that change the schema bump it. |

## company

The player company and (from M5) all rivals, handled by the same code (ADR-0010). Current-state table.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Company id. The player company is 1. |
| `name` | VARCHAR(80) | no | Display name. |
| `is_player` | BOOLEAN | no | True for the player's company. |
| `stage` | INTEGER | no | Company stage, 0 (solo founder) to 5 (conglomerate), spec §3. |
| `founded_turn` | INTEGER | no | Turn the company was founded. |

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
| `kpis` | JSON | no | `{cash_cents, monthly_burn_cents, headcount}` in M0. `cash_cents` equals the `1000_cash` balance through this turn; `monthly_burn_cents` is the net cash decrease this month (0 if cash did not fall); `headcount` is active employees (0 until M1a). |

Unique index `ux_turn_snapshot_turn_company (turn, company_id)`.

## decision_log

Decisions applied each turn, for replay and narrative. Append-only history.

| Column | Type | Null | Description |
| --- | --- | --- | --- |
| `id` | INTEGER PK | no | Row id. |
| `turn` | INTEGER | no | Turn the decisions were applied in. |
| `company_id` | INTEGER FK → company.id | no | Deciding company. |
| `kind` | VARCHAR(64) | no | `turn_decisions` for the per-turn `Decisions` object. |
| `payload` | JSON | no | Serialized `Decisions` (includes its `version`). |

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

## Files next to the saves

- `saves/index.json`: list of `{slug, company_name, scenario_id, difficulty, current_turn}`, rebuilt from the save files after each create and turn. The save files are the source of truth; a missing or corrupt index is rebuilt.
- `saves/backups/<slug>/<slug>.turn-<NNN>.sqlite`: periodic backup after every 12th committed turn; the newest 10 are kept.
- `saves/backups/<slug>/<slug>.turn-<NNN>.pre-migration-<rev>.sqlite`: backup taken before upgrading an older save; never pruned.
