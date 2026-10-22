# M0: Foundation

**Goal:** an empty company can be created, advanced through 24 monthly turns from the CLI and from the browser, and persisted deterministically, with all tooling and guardrails in place.

**Spec sections:** §1, §4, §14, §15 · **ADRs:** 0001, 0002, 0003, 0004, 0006, 0008, 0009, 0011, 0012

## Context

This milestone builds the skeleton every later system plugs into. There is almost no gameplay yet: the company has only a founder placeholder (a name and starting cash) and a fixed monthly cost. What matters is that the shape is right: a pure sim, derived RNG streams, integer-cents double-entry ledger, transactional turns, generated API client, and a Football Manager-style UI shell.

## Out of scope

People attributes, hiring, products, revenue, rivals' behavior, events, LLM calls. Do not stub these beyond what is listed below.

## Sub-tasks (commit after each)

### 1. Repository and tooling
- Create the layout in `CLAUDE.md` §4 (empty packages with `__init__.py` where needed).
- `backend/pyproject.toml` with the ADR-0001 dependencies, `uv` managed, Python 3.12. Ruff (line length 100, rules `E,F,I,B,UP,SIM,RUF`), mypy strict for `tst/sim` and `tst/events`.
- `frontend/` via Vite React-TS template with the ADR-0001 packages; ESLint, Prettier, Vitest configured; `pnpm typecheck` script.
- Root `Makefile`: `check`, `dev` (runs uvicorn and vite together), `gen-api`, `golden`, `fmt`.
- `.gitignore` (saves/, .env, node_modules, .venv, __pycache__, dist), `.env.example` with `ANTHROPIC_API_KEY=` and `TST_SAVE_DIR=./saves`.
- `pre-commit` config running ruff, ruff-format, and a check that `frontend/src/api` matches regeneration.
- `CHANGELOG.md` with an "Unreleased" section.

### 2. Sim primitives (`backend/tst/sim/`)
- `calendar.py`: `TURN_ZERO = (2010, 1)`, `turn_to_ym`, `ym_to_turn`, `format_turn(turn) -> "Jan 2010"`. Property test: round-trip for turns 0..1000.
- `rng.py`: `STREAM_IDS` (append-only; start with `"people_gen": 1, "hiring": 2, "morale": 3, "market": 4, "rivals": 5, "events": 6, "misc": 99`) and `RngFactory` per ADR-0002. Tests: same `(seed, turn, name)` gives identical draws; different names give different draws; unknown name raises.
- `money.py`: `Cents`, `cents()`, `pct_of()` per ADR-0003. Tests including rounding.
- `ledger.py`: `LedgerLine`, `LedgerEntry` with a constructor that raises `UnbalancedEntryError` if lines do not sum to zero. Hypothesis test.
- `errors.py`: base `SimError` and the errors above.
- `state.py`: frozen dataclasses `GameState(save_meta, turn, companies: tuple[CompanyState, ...])`, `CompanyState(id, name, is_player, stage, founded_turn)`. Cash is not a field (ADR-0003); a helper computes it from ledger balances passed in.
- `decisions.py`: `Decisions` (empty dataclass for now, versioned for later).
- `turn.py`: `advance_turn(state, decisions, rng, balance, ledger_balances) -> TurnResult`, exactly as defined in ADR-0012, with the 12 phases from ADR-0006 as named no-op functions in a fixed list, except phase 6 (payroll and operating costs) which posts the monthly `company.base_monthly_cost_cents` from balance as one ledger entry (debit `6900_general_admin`, credit `1000_cash`) for each company. `TurnResult(new_state, ledger_entries, log_items, snapshot, event_requests)` per ADR-0012; `event_requests` is always empty in M0.
- `snapshot.py`: per-company KPI dict `{cash_cents, monthly_burn_cents, headcount}`.
- `tests/unit/test_sim_purity.py` per ADR-0002 (scan imports and banned calls in `tst/sim/**`).
- `tests/unit/test_turn_order.py` asserting the phase list.

### 3. Data loading (`backend/data/`, schemas in `tst/sim/data_models.py`, loader in `tst/loader.py`)
- `balance.yaml` with `company.base_monthly_cost_cents` (comment: placeholder overhead until payroll exists), `scenario.<id>.starting_cash_cents` (values in `docs/formulas.md` §8a; balance.yaml is the only place the number lives), `difficulty.<level>.starting_cash_mult_bp`, `backup.every_n_turns: 12`, `backup.keep_periodic: 10`.
- `scenarios.yaml` with the four scenarios from ADR-0011 (id, name, description, `available_in: v1|v3`). No numbers here; the loader fails if a scenario id has no matching `scenario.<id>` block in `balance.yaml`. Only v1 scenarios selectable now.
- `accounts.yaml` with the chart of accounts from ADR-0003.
- Pydantic schemas in `tst/sim/data_models.py` (no file access). `tst/loader.py` (outside the sim) provides `load_all(path) -> LoadedData` with `balance`, `game_data`, and `hashes`; it reads and validates the YAML and fails clearly on bad data. Test with a deliberately broken fixture file. The purity test must fail if anything in `tst/sim` imports `yaml`, `pathlib`, `os`, `io`, or `tst.loader`, or calls `open`.
- Record SHA-256 of data files in save metadata (ADR-0008).

### 4. Persistence (`backend/tst/db/`, `backend/migrations/`)
- Engine factory per save file with the pragmas from ADR-0004.
- ORM models and the first Alembic migration for: `save_meta` (name, master_seed, created_turn, current_turn, data_hashes JSON, schema version), `company`, `account`, `ledger_entry`, `ledger_line`, `turn_snapshot`, `decision_log`, `turn_log`.
- Mappers ORM ⇄ sim dataclasses.
- `repository.py`: `create_save(name, seed, scenario)`, `load_state(session)`, `apply_turn_result(session, result)`, `ledger_balances(session, turn)`.
- `run_turn(save_path)` that opens one transaction, loads, calls `advance_turn`, applies, commits; rolls back on any exception. Test: inject an exception in phase 9 and verify the database is unchanged.
- Backups per ADR-0004 using `sqlite3` online backup. Test with a 25-turn run: 2 backups exist.
- `docs/data-dictionary.md` covering every column created.

### 5. CLI (`backend/tst/cli.py`, Typer)
- `tst new-game --seed INT --name SLUG --scenario garage_bootstrap --company-name TEXT`
- `tst advance --save SLUG --turns N`
- `tst inspect --save SLUG` prints date, cash, burn, runway in months.
- `tst list` lists saves.

### 6. Golden and determinism tests (`backend/tests/golden/`)
- Fixture runs seeds 1..10 for 24 turns and stores per-turn snapshots as JSON.
- `--update-golden` pytest option regenerates them.
- A test runs the same seed twice in separate save files and asserts identical snapshots and ledger rows.

### 7. API (`backend/tst/api/`)
- `GET /api/saves` · `POST /api/saves` (name, seed optional, scenario, company_name) · `GET /api/saves/{save_id}`. A missing seed is generated in the API layer with `secrets.randbits(63)` and stored; the sim never generates seeds.
- `GET /api/saves/{save_id}/overview` → date label, turn, cash_cents, monthly_burn_cents, runway_months, last 12 snapshots
- `POST /api/saves/{save_id}/advance` → new overview
- `GET /api/meta/scenarios`
- Domain errors mapped to 4xx with a stable `{code, message}` body.
- `scripts/export_openapi.py` writes `openapi.json` without starting a server.
- Integration tests with FastAPI `TestClient`.

### 8. Front-end shell (`frontend/`)
- `pnpm gen:api` per ADR-0009; commit generated files.
- Dark theme tokens in `src/styles/tokens.css`; Mantine dark color scheme; tabular numerals.
- Layout: left nav (Inbox, Overview, People, Recruitment, Org, Products, Finance, Competitors, History; only Overview is live, others show an "Arrives in Mx" placeholder), top bar with company name, in-game date, cash, and a prominent Continue button.
- Main menu screen: list saves, create new game form (company name, scenario, optional seed).
- Overview screen: KPI tiles (cash, monthly burn, runway) and a 12-month cash line chart.
- Continue calls `/advance`, invalidates queries, shows a spinner; Space/Enter shortcut.
- `src/lib/format.ts` with `formatMoney(cents)` and tests.
- Playwright smoke test: create game, press Continue twice, date reads "Mar 2010", cash dropped by two months of overhead.

## Acceptance criteria

- [ ] `make check` passes on a clean clone after `uv sync` and `pnpm install`.
- [ ] `tst new-game --seed 42 --name dev --scenario garage_bootstrap --company-name "Test Co"` then `tst advance --save dev --turns 24` completes, and `tst inspect` shows "Jan 2012".
- [ ] Two saves with the same seed and no decisions produce identical snapshots and ledger rows for 24 turns (golden test).
- [ ] Every ledger entry balances (property test); cash equals the `1000_cash` ledger balance at every turn.
- [ ] An exception injected mid-turn leaves the save unchanged (test).
- [ ] A 25-turn run leaves exactly 2 periodic backups.
- [ ] The sim purity test passes and fails when a forbidden import is temporarily added (demonstrated in the test via a fixture module).
- [ ] The browser flow works: create a game, see Jan 2010, press Continue, see Feb 2010 and lower cash.
- [ ] `frontend/src/api` is generated, committed, and in sync.
- [ ] `docs/data-dictionary.md` describes every table and column.

## Manual check (Reece)

1. `make dev`, open `http://localhost:5173`.
2. Create "Garage Test" with the garage bootstrap scenario.
3. Press Continue 12 times; confirm the date reaches Jan 2011 and the cash chart slopes down.
4. Stop the server, restart it, reopen the save; confirm nothing was lost.

## Decisions made

Settled with Reece during the build: the `advance_turn` signature (ADR-0012), starting cash only in `balance.yaml` (formulas.md §8a), and the loader outside the sim (`tst/loader.py`). Engineering decisions made by the agent:

- **Turn semantics.** `GameState.turn` and `save_meta.current_turn` are the next turn to play. Starting cash is a turn-0 ledger entry posted at creation. `ledger_balances(session, through_turn=T)` is both the opening balance of turn T and its closing balance once played.
- **KPIs.** `monthly_burn_cents` is the net cash decrease in the month (0 if cash rose). Runway is whole months, `cash // burn`, and is null when not burning. `headcount` is 0 until people exist (M1a).
- **Equity account per scenario.** `scenarios.yaml` carries `starting_equity_account` (an account code, not a number), because §8a credits common equity for founder money and preferred equity for the funded spinout. The loader checks that it is an equity account.
- **Seeds.** `RngFactory` accepts 0..2⁶⁴−1, but saves store 0..2⁶³−1 because SQLite integers are signed 64-bit. The API generates `secrets.randbits(63)`.
- **Extra `save_meta` columns.** `scenario_id` and `difficulty` are stored so the state can be rebuilt. Difficulty defaults to `standard`; `--difficulty` (CLI) and `difficulty` (API) are optional.
- **Balance validation.** `balance.yaml` must define exactly the four ADR-0011 difficulties. The dotted-path difficulty overlay from ADR-0008 is not built (nothing needs it yet).
- **Chart of accounts.** Codes not named in the docs were chosen to fit ADR-0003's list (for example `1100_receivables`, `4000_revenue_subscriptions`, `7000_interest`).
- **Purity scanner.** Besides the ADR-0002 list, it bans `socket`, `subprocess`, `shutil`, `urllib`, `http`, `importlib`, `tst.config`, and calls to `eval`/`exec`/`__import__`. `numpy.random` may appear outside `rng.py` only as the `Generator` type.
- **Transactions.** pysqlite's implicit transactions are disabled and SQLAlchemy emits `BEGIN` (the documented recipe), so `session.begin()` is one real SQLite transaction. Engines use `NullPool`, so no file handle outlives a request.
- **Data hashes** normalize CRLF to LF, so a Windows checkout hashes the same as Linux.
- **Save index.** `saves/index.json` is rebuilt from the save files after each create and turn; the files are the source of truth, and a missing or corrupt index is rebuilt.
- **Backups.** Pre-migration backups are named `<slug>.turn-<NNN>.pre-migration-<rev>.sqlite` and are never pruned.
- **API.** Errors map to 404 (not found), 409 (exists), 400 (other domain errors), and 422 (request validation), all as `{code, message}`. Every route has an `operationId`. The master seed is not returned, so it cannot reveal hidden values later.
- **Generated client.** `openapi.json` is committed in `frontend/src/api/` next to `schema.d.ts` and `client.ts`. openapi-typescript runs with `defaultNonNullable: false`, so request fields with server defaults stay optional.
- **Front end.** The save slug is derived from the company name ("Garage Test" → `garage-test`). Overview is the landing screen until Inbox arrives in M1b. Besides Space/Enter for Continue, keys 1–9 jump to nav screens (from `.cursor/rules/20-frontend.mdc`). Keys are ignored on focused buttons and links so one press never advances twice.
- **Playwright** is `make e2e`, not part of `make check`, because it starts servers and needs a browser. It runs its own API and Vite on ports 8765/5175 with a temporary save folder. `PLAYWRIGHT_CHANNEL=msedge` uses an installed browser instead of downloading Chromium.
- **Line endings.** `.gitattributes` pins LF for text files. A fresh Windows clone (autocrlf) otherwise failed Prettier and the API-sync check. The sync check compares content with `git diff` rather than `git status`.
- **ESLint.** The current Vite template ships oxlint instead of ESLint, so ESLint was configured by hand with the plugins the classic template used (see Follow-ups).

## Follow-ups

- **Needs approval (dependencies outside ADR-0001).** The ESLint setup uses `@eslint/js`, `typescript-eslint`, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`, and `globals`; the Vite template also brings `@vitejs/plugin-react` and `@types/node`. FastAPI's `TestClient` needs `httpx2`, which currently arrives only through `anthropic`. Pinning it as an explicit dev dependency would stop a future `anthropic` release from breaking the tests.
- ADR-0008's heuristic test for numeric literals in `tst/sim` is not built (not in this brief).
- ADR-0003's "assets = liabilities + equity" property needs closing entries or retained earnings; today the test checks that each company's ledger sums to zero. It belongs with statements in M4.
- The difficulty overlay mechanism (`difficulty.<level>` overriding by dotted path) is unbuilt; only `starting_cash_mult_bp` is read.
- All ten golden seeds are identical until a subsystem draws from an RNG stream (M1a).
- Run `uv run --project backend pre-commit install` once per clone to enable the hooks.
- On this machine, `uv python install 3.12` reported a harmless error creating its minor-version link; the interpreter works.
