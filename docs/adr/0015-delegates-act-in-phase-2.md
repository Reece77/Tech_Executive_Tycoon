# ADR-0015: Delegates act in phase 2 through the player's actions

- Status: Accepted. Extends ADR-0013 (new stream) and ADR-0014 (who may act).
- Date: 2026-10-24
- Spec sections: §4, §5.3, §5.4, §6

## Context

ADR-0011 says everything is delegable, with quality set by the delegate's attributes. ADR-0014 made player actions pure functions with an `actor`, and kept `Decisions` for choices made during `advance_turn`. M2 adds the first delegates: staff who run hiring plans. They need a place in the turn, a source of randomness that cannot collide with the player's, and a rule for replay.

## Decision

1. **Delegates act in phase 2.** The phase keeps its ADR-0006 name (`rival_decisions`) and order; it now runs the AI decisions of every company's delegates (M2) and, from M5, rivals. `test_turn_order.py` does not change.
2. **Same actions, different actor.** A delegate's choices become ordinary `Action`s applied through `apply_action` with `actor_id` = the delegate. Energy, validation, the option pool and the offer pitch all apply. No rule exists only for delegates.
3. **Delegate energy.** Each delegate has `delegates.energy_per_month` energy on their own `person_state.energy`, reset after phase 12 with the founder's. Delegates never spend the founder's energy.
4. **Randomness.** Inside a delegate's action, randomness uses stream `delegate` (id 14), key `(person_id, n)`, where `n` counts that delegate's actions in the turn, starting at 0. The player's `actions` stream (keyed by `seq`) is untouched.
5. **Logging and replay.** Delegate actions are written to `decision_log` with `source = "delegate"` and the delegate's id, for history and the inbox. Replay does **not** re-apply them as inputs: they are recomputed by `advance_turn` from the plans in state. The replay test asserts the recomputed actions equal the logged ones.
6. **Ordering.** Plans are processed in plan-id order; within a plan, candidates are ranked deterministically (formulas.md §13.10), ties by id.

## Consequences

- Rivals in M5 reuse this machinery: a rival is a company whose every decision comes from delegates.
- A delegate who resigns or is fired leaves their plans without an owner; the plans pause and the inbox says so.

## Alternatives considered

- A separate delegate action set: duplicates rules and lets delegate behavior drift from the player's.
- Reusing the `actions` stream with continued `seq`: couples delegate randomness to how many actions the player took that turn.
