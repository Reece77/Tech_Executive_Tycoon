# CLAUDE.md — Tech Startup Tycoon

Read this file fully before every task. It is the contract between the owner (Reece) and any coding agent working in this repository.

## 1. What this project is

A single-player, turn-based business management game for personal use. The player founds a tech startup in **January 2010** and grows it, over a **360-turn (30-year)** standard campaign, into a vertically integrated conglomerate spanning software, cloud, hardware, chips, and minerals. Interface and people depth follow Football Manager; economic depth and supply chains follow Capitalism Lab.

- Design source of truth: `docs/spec/game-design-spec.md` (export of the Claude Doc "Tech Startup Tycoon: Game Design and Technical Specification v1.0").
- Technical decisions: `docs/adr/` (start with `docs/adr/README.md`).
- Current task: the brief in `docs/tasks/` named in your instructions.

Precedence: on technical matters (stack, schema shape, RNG, persistence) ADRs override the spec, and ADR-0011 records Reece's answers to the spec's open questions. Any other conflict: stop and ask. Never resolve a conflict by guessing.

## 2. The five rules that matter most

1. **The simulation core is pure.** Code in `backend/tst/sim/` never imports `tst.db`, `tst.api`, or `tst.llm`; never reads the clock; never touches the network or filesystem; never uses the global `random` module or `numpy.random` module-level functions. It takes state + decisions + an RNG factory + balance config and returns new state + ledger entries + log. (ADR-0002)
2. **Randomness is seeded and derived.** Get a generator only from `RngFactory.stream(turn, name)`. Never call `random.Random()` or `np.random.default_rng()` directly. Same seed + same decisions must give identical results. (ADR-0002)
3. **Money is integer cents.** Never use `float` for money. All cash movement is a balanced double-entry `LedgerEntry`. (ADR-0003)
4. **One turn = one database transaction.** A crash mid-turn must leave the save exactly as it was before the turn. (ADR-0004)
5. **The LLM proposes, the engine disposes.** LLM output is untrusted JSON: validated, clamped, and applied by engine code. The LLM never receives hidden true values and never writes state. (ADR-0005)

## 3. Scope discipline

- Build only what the current task brief lists. Put better ideas or missing systems under "Follow-ups" in your final summary; do not build them.
- Do not add systems from a later milestone or phase (v2: divisions, IPO, hardware, R&D tree; v3: mining, fabs, holding companies), not even as stubs, unless the brief says so.
- Do not add dependencies outside ADR-0001 without asking. If one is genuinely needed, propose it with a one-line reason.
- Do not reformat or refactor files unrelated to the task.

## 4. Repository map

```text
CLAUDE.md                  this file
AGENTS.md                  pointer for ChatGPT/Codex and other agents
.cursor/rules/             Cursor rules (same rules, scoped by path)
Makefile                   make check / make dev
docs/
  spec/                    game design spec (exported)
  adr/                     architecture decision records
  tasks/                   milestone task briefs
  data-dictionary.md       column-level schema reference (kept current with migrations)
  formulas.md              formula reference (added during M1)
backend/
  pyproject.toml
  tst/                     python package ("tst" = Tech Startup Tycoon)
    sim/                   PURE engine: models, calendar, rng, turn pipeline, people, org, products, market, finance
    events/                director, context builder, validator, template library
    llm/                   adapter interface + anthropic, mock, template adapters
    db/                    SQLAlchemy models, repositories, sim<->db mappers, session/backup helpers
    api/                   FastAPI app, routers, request/response schemas
    loader.py              reads and validates backend/data YAML (outside sim; ADR-0008)
    cli.py                 headless commands (new-game, advance, inspect)
    config.py              settings (paths, env vars)
  data/                    seed YAML: balance.yaml, names, roles, skills, tags, interests, regions, rivals
  migrations/              Alembic
  tests/                   unit/ property/ golden/ integration/
frontend/
  src/
    api/                   GENERATED client — never hand-edit
    screens/ components/ hooks/ lib/
tools/                     balance runner, save inspector, seed tools
saves/                     local save files (git-ignored)
```

## 5. Commands

Backend (from `backend/`):

```bash
uv sync                                       # install
uv run pytest -q -n auto                      # all tests, in parallel (pytest-xdist, added in M5 sub-task 0)
uv run pytest tests/golden -q                 # determinism and golden seeds
uv run ruff check . && uv run ruff format --check .
uv run mypy tst
uv run tst new-game --seed 42 --name dev      # create a save (runs migrations on the new file)
uv run tst advance --save dev --turns 12      # advance headless
uv run tst inspect --save dev                 # print company summary
uv run uvicorn tst.api.app:app --reload       # API on :8000
```

Frontend (from `frontend/`):

```bash
pnpm install
pnpm dev                                      # Vite on :5173, proxies /api to :8000
pnpm gen:api                                  # regenerate src/api from backend OpenAPI
pnpm lint && pnpm typecheck && pnpm test
```

Root:

```bash
make check     # backend lint + types + tests, frontend lint + types + tests. Must pass before you finish.
make check-fast  # the same without the golden tests, for local iteration only
make dev       # run API and front end together
```

## 6. Definition of done (every task)

- [ ] Every acceptance criterion in the brief is met, and you state how each was verified.
- [ ] `make check` passes.
- [ ] New engine logic has unit tests; randomness has a seeded test; invariants (ledger balances, attributes in 1–20) have Hypothesis property tests.
- [ ] Golden snapshots unchanged, or intentionally regenerated with `uv run pytest tests/golden --update-golden` and the reason recorded in `CHANGELOG.md`.
- [ ] Schema changes have an Alembic migration, and `docs/data-dictionary.md` is updated.
- [ ] New tunable numbers live in `backend/data/balance.yaml` with a comment (unit + intent), not in code.
- [ ] Any design decision the spec and ADRs did not cover is written down (a new ADR, or the brief's "Decisions made" section).
- [ ] Final message: summary, files touched, how each criterion was verified, follow-ups.

### Merging (from 2026-10-27, Reece's decision; pull-request route from 2026-11-03)

`main` is protected: changes arrive only through a pull request whose `check` shards pass on a branch that is up to date with `main`. When every box above is ticked, `make e2e` passes, and the `check` run on your pushed branch is green:

1. Merge `main` into your branch if it has moved (resolve `CHANGELOG.md` conflicts by keeping both sides' lines), push, and wait for `check` to go green again.
2. Open a pull request into `main` and merge it with a **merge commit** (not squash or rebase). The merge commit's message ends with the trailer `Milestone-Tag: mX-done` (the milestone id). Wait for the `check` run on `main` to go green. If it fails, fix it at once through another pull request (that fix's merge commit carries the trailer instead).
3. The `tag-milestone` workflow tags the commit: when `check` succeeds on `main` and the head commit has a `Milestone-Tag:` trailer whose tag doesn't exist yet, it creates and pushes that tag. Confirm the tag appeared (`git ls-remote --tags origin mX-done`). Cloud sessions cannot push tags themselves (HTTP 403).
4. If the instructions name a next brief, start it on a new branch from the updated `main`; otherwise stop and report.

Never force-push, rewrite `main`'s history, or merge with a red check (`check` and, from 2026-11-08, `e2e`). The product manager reviews after the merge and sends any fixes as a follow-up brief.

## 7. Conventions

Python
- Python 3.12, full type hints, `mypy --strict` for `tst/sim` and `tst/events`.
- Sim models: `@dataclass(frozen=True, slots=True)`. Return new objects; never mutate inputs. Use `dataclasses.replace`.
- IDs are `int`. Turn 0 = January 2010. Convert with `tst.sim.calendar` only.
- Attributes are `float` in [1.0, 20.0] internally, shown as rounded `int`. Clamp on every write with `clamp_attr()`.
- No `print` in library code; use `logging.getLogger(__name__)`.
- Domain errors live in `tst.sim.errors`; the API maps them to HTTP status codes.

TypeScript / React
- Strict TypeScript, function components, hooks. TanStack Query for server state; TanStack Table for every table.
- Never hand-edit `frontend/src/api/`; regenerate it.
- No business logic in the front end. Format numbers; never compute game values.
- Money arrives as integer cents; display with `formatMoney()` from `src/lib/format.ts`.
- Dark theme by default; information density over decoration.

Data
- Seed and balance data are YAML in `backend/data/`, validated by Pydantic at load. Invalid data fails at startup.
- Real company and commodity names are allowed (personal use). Real companies start at approximate 2010 values and diverge after turn 0.

## 8. Never

- Never expose hidden true values (potential, hidden traits, true deposit grade) through the API or in an LLM prompt. The API returns only revealed ranges for the viewing company.
- Never call the Anthropic API in tests; use `MockLLMAdapter`.
- Never commit secrets. `ANTHROPIC_API_KEY` comes from `.env` (git-ignored).
- Never edit an applied migration or delete golden snapshots to make tests pass.
- Never weaken a test to make it pass. If a test is wrong, say so and explain why.
- Never use floats for money, wall-clock time in the sim, or unseeded randomness.

## 9. When unsure

Ask one short, specific question with your proposed default. Pause rather than invent game design. Engineering details (naming, internal structure) you may decide and note in your summary.

### Decision rules (product manager, 2026-11-08)

Most stops in v2 were predictable. Decide these yourself, record each decision with its numbers in the brief's "Decisions made", and carry on:

1. **Your milestone's own target misses:** tune the keys your brief lists as yours, as far as needed. Record before and after values.
2. **An earlier milestone's guard fails on your branch but passes on `main`:**
   - first check whether a balance **script** lacks behaviour a sensible player would have (as M13b's and M15a's founder scripts lacked regions and new categories); if so, fix the script in `tst/balance/` (never the game) and record why;
   - otherwise, if your own keys bring it back without breaking your targets, do that;
   - otherwise stop and report.
3. **A failure that also happens on a clean `main`** (prove it by running `main` in a separate worktree, with a table): it is not yours. Record it with its evidence, name the fix milestone running or next, and continue to merge. Never add it to `known_misses.py` yourself.
4. **Seed luck:** a guard that misses on seeds 1–10 but passes on seeds 11–40 on both `main` and your branch is seed variance; record both readings and treat it as rule 3. If your branch differs from `main` on 30 seeds, it's real: apply rule 2.
5. **Flaky or timing-dependent tests:** make them wait on state, not time, or fix the fixture. Never add retries, longer sleeps or looser checks.
6. **Turn-time budgets:** run them alone (`make check-timing`). If over budget alone, profile and make the slow step proportional to what changes, with identical results (state-cache check, golden snapshots). Stop only if it is still over after that.
7. **Long runs:** don't run the nightly or weekly suites locally for more than an hour. Dispatch the GitHub workflow on your branch instead (`gh workflow run nightly.yml --ref <branch>`), and write any local long run's output to a file.
8. **Lanes:** once the other lane has merged, its file ownership lapses, and you may fix integration bugs in its files.
9. **Docs branches named in your instructions:** open and merge them (docs only, merge commit) before you start.

**Always stop and ask** for: a P1-level defect; changing how an earlier milestone's target is measured, or its band; a design question the spec, ADRs and brief don't answer; anything that weakens a hidden-value guarantee (CLAUDE.md §8); editing an applied migration; a guard that rules 1–4 can't resolve.
