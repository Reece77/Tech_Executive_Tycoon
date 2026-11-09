"""What the Data editor withholds (M25 section 3; CLAUDE.md section 8, ADR-0007).

The editor shows data files, never a game's state. By default it keeps the API's hidden-name
rule all the same: fields the rule forbids (a rival's `cash_months`, a starting `share_bp`, a
formula's `noise` or `cap`) are left out of the form, the values and the comments, and a
change to one is refused. The player can turn on "Show spoiler fields" (PM ruling 2026-11-08;
`spoilers` on the editor routes), which shows and edits them; every game route keeps the rule.
The names mirror tests/integration/test_api.py's
`forbidden()`, and tests/integration/test_m25_mods.py checks every name in the editable files
against it, so the two cannot drift apart unnoticed."""

from __future__ import annotations

from typing import Any, Final

WITHHELD_NAMES: Final = frozenset(
    {
        "acceptance_probability",
        "affinity",
        "anthropic_api_key",
        "api_key",
        "approach_probability",
        "backfired",
        "base_output",
        "base_value",
        "base_value_cents",
        "below_takeover_months",
        "below_value_months",
        "bias",
        "block_probability",
        "blocked_draw",
        "board_bar",
        "book_demand",
        "cap",
        "capacity",
        "caps",
        "cash_base_cents",
        "cash_months",
        "chance",
        "contribution",
        "contributions",
        "current_ability",
        "d_i",
        "demand_draw",
        "dev_skill",
        "distressed",
        "effect_cap",
        "fundamental_value_cents",
        "marketing_skill",
        "master_seed",
        "mu",
        "multiple",
        "need",
        "needs",
        "noise",
        "o_i",
        "output",
        "p",
        "personality_weights",
        "poach_probability",
        "pool_headcount",
        "pool_skill",
        "potential_ability",
        "premium",
        "probability",
        "q_cap",
        "qcap",
        "quality_cap",
        "relationship_value",
        "reservation",
        "reservation_cents",
        "response",
        "response_chance",
        "risk_rate",
        "rival_cash_cents",
        "safe_probability",
        "sales_capacity",
        "scandal_chance",
        "scandal_risk",
        "second_story",
        "sell_skill",
        "sentiment",
        "share_bp",
        "start_value",
        "strength",
        "target_mult",
        "tender_chance",
        "trigger_strength",
        "utilities",
        "utility",
        "v_base",
        "valuation_noise",
        "valuation_noise_sd",
        "value_cents",
        "z",
    }
)
WITHHELD_PREFIXES: Final = ("true_", "hidden_")


def withheld(name: str) -> bool:
    return name in WITHHELD_NAMES or name.startswith(WITHHELD_PREFIXES)


def strip(value: Any) -> Any:
    """`value` without any withheld key, at any depth."""
    if isinstance(value, dict):
        return {k: strip(v) for k, v in value.items() if not withheld(str(k))}
    if isinstance(value, list):
        return [strip(v) for v in value]
    return value


def strip_spec(spec: dict[str, Any]) -> dict[str, Any]:
    out = dict(spec)
    if "fields" in out:
        out["fields"] = [
            {**f, "spec": strip_spec(f["spec"])} for f in out["fields"] if not withheld(f["name"])
        ]
    for key in ("item", "value"):
        if isinstance(out.get(key), dict):
            out[key] = strip_spec(out[key])
    return out


def path_withheld(path: list[str]) -> bool:
    """A change path through a withheld field (an item selector's own field included)."""
    for seg in path:
        name = seg[1:].split("=", 1)[0] if seg.startswith("@") else seg
        if withheld(name):
            return True
    return False
