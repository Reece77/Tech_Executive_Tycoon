# ADR-0005: The LLM proposes, the engine disposes

- Status: Accepted
- Date: 2026-10-20
- Spec sections: §12

## Context

LLM-written events make each company's story feel specific, but model output can be malformed, contradictory, or extreme, and API calls cost money and can fail.

## Decision

1. **Adapter interface** in `tst/llm/base.py`:

   ```python
   class LLMAdapter(Protocol):
       def generate_event(self, request: EventRequest) -> EventDraft | None: ...
       def generate_text(self, request: TextRequest) -> str | None: ...
   ```

   Implementations: `AnthropicAdapter`, `MockLLMAdapter` (deterministic, used in all tests), `TemplateAdapter` (offline play). The active adapter is a setting; the game is fully playable with `TemplateAdapter`.

2. **Engine controls when and what.** The event director (in `tst/events/`) chooses the slot, category, severity, eligible targets, and the allowed effect types and value ranges before any LLM call. The LLM chooses only wording and which allowed effects to attach to each choice.
3. **Validation:** every draft passes `validate_event(draft, request) -> ValidatedEvent | Rejection`: JSON schema check, known effect types only, target ids drawn from the request's eligible list, values clamped to severity caps, cash effects capped as basis points of current cash or trailing revenue. One retry on rejection, then a template event of the same category.
4. **Context hygiene:** prompts contain only what the player could plausibly know: visible attributes, revealed ranges, behavior tags already revealed, public market data. Never hidden true values.
5. **Logging:** every call writes `llm_call_log` (turn, purpose, model, prompt hash, token counts, latency, outcome). Raw prompts and responses are stored only when `TST_LLM_DEBUG=1`.
6. **Budget: $10 a calendar month (Reece, 2026-10-27).** The setting `llm.monthly_budget_cents` (default 1000) is in real dollars, not tokens: each call's cost = input and output tokens from the API response × per-model prices held in settings (`llm.price_per_mtok_cents.<model>`, editable when prices change). Spend resets on the 1st of each real calendar month (the only wall-clock use, outside the sim). An on-screen meter shows spend against the budget; at 100% the director falls back to templates silently and logs it. The budget can be changed in settings, including to 0 for offline play.
7. **Model choice:** a small, fast model for flavor text; a larger model for multi-turn storylines. Model ids are settings, not code constants.

## Consequences

- Event effects are always legal and bounded, so balance testing can run with `MockLLMAdapter` and remain meaningful.
- Template events must cover every category and severity, because they are the fallback.

## Alternatives considered

- LLM decides effects freely: unbounded and untestable.
- No LLM: viable but loses the main source of narrative variety; kept as the offline mode instead.
