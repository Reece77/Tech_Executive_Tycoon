# ADR-0023: Conversations

**Status:** accepted (2026-11-22, product manager, from Reece's v6 decisions of 2026-11-21 and 2026-11-22) · **Milestones:** M47, M48, M49 · **Formulas:** §58 (and the later conversation sections)

## Context

v6 lets the player talk to the world: negotiations (M47), board meetings and earnings calls (M48), press and one-to-ones (M49). Free text from the player, and text from the LLM, must never become a way around the engine's rules or a leak of hidden values (ADR-0005, CLAUDE.md §2.5 and §8).

## Decision

1. **Conversations run between turns,** outside the simulation core, as a service like the event service. Each conversation is a record (`conversation`: kind, subject, counterpart, status, rounds) and each round is stored with its message, the scored moves and the engine's response, so a reload resumes exactly.
2. **The engine owns every outcome.** The LLM only (a) classifies the player's message into a closed set of moves per conversation kind (validated JSON; invalid output becomes `neutral`), (b) writes suggested replies from public facts, and (c) words the counterpart's response from the engine's decided reply. Move effects, bounds and outcomes are pure functions in `tst/sim/` taking state, moves and an RNG stream.
3. **Prompts use an allowlist,** as §16.5: public facts, revealed ranges and the conversation so far. A test plants hidden values in state and asserts none reach any prompt or reply.
4. **A separate monthly budget** (`llm.conversation_budget_cents`, default $10, a setting). Over budget, offline or in tests, conversations run in **template mode**: the player picks moves from labelled buttons, with identical engine behaviour.
5. **Skip is always available** and gives the median outcome, so conversations add depth without forcing it, and delegates use skip.
6. **The player's free text is untrusted input,** like LLM output. It is never executed and never inserted into a prompt as an instruction: it's quoted as the player's message, and the classifier's system prompt says so.

## Consequences

- Every conversation kind in M47–M49 is a set of moves with engine effects plus prompts. Adding a kind needs no change to this ADR.
- Determinism holds for a given sequence of moves; the LLM's classification is stored per round, so replays use the stored moves and never call the LLM.
