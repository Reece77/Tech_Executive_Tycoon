# ADR-0009: OpenAPI is the contract; the TypeScript client is generated

- Status: Accepted
- Date: 2026-10-20
- Spec sections: §13, §14

## Context

Two tools (Claude Code and Cursor) will edit backend and front end, often in separate sessions. Hand-written client types drift from the API.

## Decision

- FastAPI response and request models (in `tst/api/schemas/`) are the single source of the API shape. Every route declares `response_model`.
- `make gen-api` (or `pnpm gen:api`) exports `openapi.json` from the app without starting a server, then runs `openapi-typescript` to write `frontend/src/api/schema.d.ts`; `frontend/src/api/client.ts` wraps `openapi-fetch`.
- Generated files are committed and never hand-edited. `make check` fails if regenerating changes them.
- Routes are versionless (`/api/...`) because there is one client.
- Save-scoped routes: `/api/saves`, `/api/saves/{save_id}/...`. The API opens the requested save file per request.
- Money fields are integers with a `_cents` suffix. Attribute fields are `{min: int, max: int}` objects.

## Consequences

- A backend schema change is a two-step change (backend, then regenerate) and is caught by `make check` if forgotten.

## Alternatives considered

- tRPC or GraphQL: extra machinery for a single local client.
- Hand-written types: drift.
