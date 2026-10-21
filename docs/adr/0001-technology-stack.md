# ADR-0001: Technology stack and dependency list

- Status: Accepted
- Date: 2026-10-20
- Spec sections: §14

## Context

The game is a local, single-player, table-heavy management sim built mostly by AI coding tools (Claude Code, Cursor, ChatGPT). Agents tend to add libraries freely, which causes drift. A fixed list keeps the codebase coherent.

## Decision

Run as a local web app: Python backend on `localhost:8000`, React front end on `localhost:5173` in development, served as static files by the backend later.

Backend (Python 3.12, managed with `uv`):

| Purpose | Package |
| --- | --- |
| API | `fastapi`, `uvicorn[standard]` |
| Models and validation | `pydantic` v2, `pydantic-settings` |
| Persistence | `sqlalchemy` 2.x, `alembic` |
| Numerics and RNG | `numpy` |
| Seed data | `pyyaml` |
| CLI | `typer` |
| LLM | `anthropic` (used only inside `tst/llm/`) |
| Dev | `pytest`, `hypothesis`, `ruff`, `mypy`, `pre-commit` |

Front end (Node 22 LTS, managed with `pnpm`):

| Purpose | Package |
| --- | --- |
| Build | `vite`, `typescript` |
| UI | `react`, `react-dom`, `react-router` |
| Server state | `@tanstack/react-query` |
| Tables | `@tanstack/react-table` |
| Charts | `recharts` |
| Components | `@mantine/core`, `@mantine/hooks` |
| API client generation | `openapi-typescript`, `openapi-fetch` |
| Dev | `eslint`, `prettier`, `vitest`, `@testing-library/react`, `@playwright/test` |

Root tooling: a `Makefile` with `check`, `dev`, `gen-api`, `golden` targets.

Adding any package not listed requires a short note in the task summary and Reece's approval.

## Consequences

- Two languages, but each is used where it is strongest: Python for numeric simulation and testing, TypeScript for a dense UI.
- `numpy` is available for vectorizing hot loops (rival employees, market share) later without a dependency change.
- Mantine chosen over shadcn/ui because its table, tabs, and form components are complete out of the box, which suits a data-dense UI built by agents.

## Alternatives considered

- Single TypeScript stack (Node + SQLite + React): fewer languages, but weaker numeric and property-testing tooling.
- Godot or Unity: graphics capability the design explicitly does not need.
- PostgreSQL: unnecessary operational overhead for a single-player local game.
- shadcn/ui: excellent, but copy-in components invite agent-driven variation across screens.
