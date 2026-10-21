# ADR-0004: One SQLite file per save, transactional turns, backups, history

- Status: Accepted
- Date: 2026-10-20
- Spec sections: §1 (pillar 5), §14, §15

## Context

"Nothing is lost" is a design pillar. Saves must survive crashes, schema upgrades, and agent mistakes, and history must be queryable for the History screen and LLM context.

## Decision

1. **One file per save:** `saves/<slug>.tst.sqlite`. A small `saves/index.json` lists saves for the main menu. Settings: `TST_SAVE_DIR` (default `./saves`).
2. **Pragmas on connect:** `journal_mode=WAL`, `foreign_keys=ON`, `synchronous=NORMAL`.
3. **Migrations:** Alembic runs against a specific save file. `tst new-game` creates the file and upgrades it to head. Opening an older save upgrades it after taking a backup.
4. **Turn transaction:** the API or CLI loads state, calls `advance_turn`, and writes all results (state updates, ledger entries, log, snapshot, `save_meta.current_turn += 1`) inside one `session.begin()` block. Any exception rolls back everything.
5. **Backups:** after every 12th committed turn and before any migration, copy the database with SQLite's online backup API to `saves/backups/<slug>/<slug>.turn-<NNN>.sqlite`. Keep the latest 10 periodic backups plus every pre-migration backup.
6. **History is append-only:** `turn_snapshot` (KPIs as JSON per company per turn), `decision_log`, `event`, `event_resolution`, `ledger_entry`, and `employment` (with start and end turns) are never updated or deleted, only appended or closed.
7. **Current-state tables** (`person_state`, `company`, etc.) may be updated in place, because history tables hold what is needed to reconstruct the past.

## Consequences

- Copying a save is copying one file.
- Agents must not write outside the turn transaction except for explicit player actions, which use their own short transactions and a `decision_log` row.
- Migration tests: every migration runs up from an empty database and from a fixture save made at the previous schema head.

## Alternatives considered

- One database for all saves: harder to back up, copy, or delete one game.
- Event sourcing for everything: maximally replayable, but too heavy for an agent-built personal project.
