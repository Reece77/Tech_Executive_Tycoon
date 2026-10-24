# ADR-0014: Immediate player actions and pending items

- Status: Accepted. §5 amended by ADR-0016 (founder energy switched off by default).
- Date: 2026-10-21
- Spec sections: §4, §5.3, §5.4, §13

## Context

The M1b brief said both that player actions are queued as `Decisions` and applied in phase 1 of the next turn, and that interviews "visibly narrow ranges" in the UI. If an interview were queued, the player would not see what they learned until after pressing Continue, and founder energy (reset in phase 1) would be spent against the wrong month. ADR-0004 already allows "explicit player actions" in their own short transactions.

## Decision

1. **Immediate actions.** Between turns, the player (or later a delegate) performs actions that take effect at once:

   ```python
   def apply_action(
       state: GameState, action: Action, rng: RngFactory,
       balance: Balance, data: GameData, ledger_balances: LedgerBalances,
   ) -> ActionResult:  # new_state, ledger_entries, log_items
   ```

   Pure, in `tst/sim/actions/`. Each `Action` is a frozen dataclass with an `actor_id` (the founder in M1). The API runs one action per short transaction: load, apply, persist, append a `decision_log` row.

2. **Turn of an action.** Actions belong to `state.turn` (the next turn to be played, as in M0). Ledger entries and log items they create carry that turn.

3. **Ordering and replay.** `decision_log` gains `seq` (1, 2, 3… within a turn). Randomness inside an action uses `rng.stream(state.turn, "actions", seq)` (ADR-0013). Replaying the starting state, then each turn's actions in `seq` order, then `advance_turn`, reproduces the save exactly.

4. **What is immediate and what is pending.**

   | Action | Takes effect | Resolved later |
   | --- | --- | --- |
   | Open search (network, job post, recruiter) | Energy spent; search recorded | Candidates generated in phase 12, visible next month |
   | Close job-post search | Monthly fee stops | — |
   | Interview, reference check | Energy spent; ranges narrow; tag rolls | — |
   | Make offer | Offer recorded as pending | Accepted or declined in phase 1 of the next turn |
   | Withdraw offer | Offer removed | — |
   | Fire | Employment ends; severance posted; morale penalty applied | — |

5. **Founder energy** is stored on the founder's `person_state.energy`. Actions check and spend it immediately. `advance_turn` resets it to `founder.energy_per_month` for the new turn, after phase 12, so the energy shown after Continue is the new month's budget.

6. **`Decisions`** remains the input for AI and delegated choices made during `advance_turn`. It stays empty in M1; delegates arrive in M2 and rivals in M5, and both will call the same action functions.

7. **Errors.** An invalid action (unknown id, insufficient energy, candidate already hired) raises a domain error, writes nothing, and maps to HTTP 400 or 404.

## Consequences

- The UI shows the result of an interview at once, and energy behaves like a monthly budget.
- Actions are replayable and tested with the same golden approach as turns.

## Alternatives considered

- Queue everything into `Decisions`: delays feedback by a month and makes the energy budget confusing.
- Mutate state outside the pure core for actions: breaks ADR-0002 and replay.
