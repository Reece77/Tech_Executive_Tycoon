# AGENTS.md

This file is for ChatGPT, Codex, and any agent other than Claude Code or Cursor.

**All project rules live in `CLAUDE.md`. Read it first and follow it exactly.** The same rules apply to every agent; this file exists only so tools that look for `AGENTS.md` find them.

Then read, in order:

1. `docs/adr/README.md` — technical decisions that are already made. Do not re-decide them.
2. The task brief in `docs/tasks/` you were given.
3. The spec sections that brief cites in `docs/spec/game-design-spec.md`.

## If you are acting as a reviewer

When asked to review a diff or a milestone, check, in this order:

1. Does it meet every acceptance criterion in the brief? Quote any that are unmet.
2. Does it break any of the five rules in `CLAUDE.md` §2 (pure sim, seeded RNG, money in cents, transactional turns, LLM proposes only)?
3. Does it build anything outside the brief's scope?
4. Are tests meaningful (seeded, property-based where invariants exist), or do they only restate the implementation?
5. Any hidden true values leaking through API schemas?

Report findings as a numbered list with file and line references, most serious first. Do not rewrite the code unless asked.
