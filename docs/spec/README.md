# Game design spec

`game-design-spec.md` is the Markdown export of the Claude Doc "Tech Startup Tycoon: Game Design and Technical Specification v1.0". The Doc is the editable source.

When the Doc changes, re-export it here and commit with a one-line note in `CHANGELOG.md`.

The Doc's two diagrams (value chain, runtime architecture) are written out as text in sections 8 and 14.

Where the spec and the ADRs differ on a technical detail, the ADRs win (see `CLAUDE.md` §1). Known differences today: the spec's `rng_state` table is replaced by derived random streams (ADR-0002); the component library is Mantine (ADR-0001).
