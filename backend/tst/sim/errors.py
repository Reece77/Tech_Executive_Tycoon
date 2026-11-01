"""Domain errors. Each has a stable `code` that the API returns in its error body."""

from __future__ import annotations

from typing import ClassVar


class SimError(Exception):
    """Base class for all domain errors."""

    code: ClassVar[str] = "sim_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnbalancedEntryError(SimError):
    code = "unbalanced_entry"


class UnknownStreamError(SimError):
    code = "unknown_stream"


class InvalidMoneyError(SimError):
    code = "invalid_money"


class InvalidDateError(SimError):
    code = "invalid_date"


class InvalidSeedError(SimError):
    code = "invalid_seed"


class UnknownScenarioError(SimError):
    code = "unknown_scenario"


class ScenarioUnavailableError(SimError):
    code = "scenario_unavailable"


class UnknownDifficultyError(SimError):
    code = "unknown_difficulty"


class InvalidSaveNameError(SimError):
    code = "invalid_save_name"


class SaveNotFoundError(SimError):
    code = "save_not_found"


class SaveExistsError(SimError):
    code = "save_exists"


class InvalidCompanyNameError(SimError):
    code = "invalid_company_name"


class InvalidFounderError(SimError):
    code = "invalid_founder"


class UnknownKnowledgeActionError(SimError):
    code = "unknown_knowledge_action"


class InvalidMissionError(SimError):
    code = "invalid_mission"


# --- Player actions (M1b, ADR-0014) ---------------------------------------------------------


class NotFoundError(SimError):
    """Base for unknown ids; the API returns 404."""

    code = "not_found"


class UnknownPersonError(NotFoundError):
    code = "unknown_person"


class UnknownCandidateError(NotFoundError):
    code = "unknown_candidate"


class UnknownSearchError(NotFoundError):
    code = "unknown_search"


class UnknownOfferError(NotFoundError):
    code = "unknown_offer"


class UnknownRoleError(SimError):
    code = "unknown_role"


class InvalidActionError(SimError):
    code = "invalid_action"


class InsufficientEnergyError(SimError):
    code = "insufficient_energy"


class InsufficientCashError(SimError):
    code = "insufficient_cash"


class OptionPoolError(SimError):
    code = "option_pool"


class OfferExistsError(SimError):
    code = "offer_exists"


# --- Organization (M2a) ---------------------------------------------------------------------


class UnknownUnitError(NotFoundError):
    code = "unknown_unit"


class UnknownPlanError(NotFoundError):
    code = "unknown_plan"


class OrgRuleError(SimError):
    """An org action would break a rule of formulas.md 13.1 (units and reporting lines)."""

    code = "org_rule"


class InterviewRequired(SimError):  # named by ADR-0016
    """An offer needs a prior interview by the offering company (ADR-0016)."""

    code = "interview_required"


class ReplayMismatchError(SimError):
    """Replay recomputed different delegate actions than the save logged (ADR-0015)."""

    code = "replay_mismatch"


# --- Products (M3a) -------------------------------------------------------------------------


class UnknownProductError(NotFoundError):
    code = "unknown_product"


class ProductRuleError(SimError):
    """A product action would break a rule of formulas.md 11.2 or 11.3."""

    code = "product_rule"


class LaunchNotReadyError(ProductRuleError):
    """Launch refused below the thresholds; the message names what is missing (11.2)."""

    code = "launch_not_ready"


class FinanceRuleError(SimError):
    """A finance action would break a rule of formulas.md 14.4-14.7."""

    code = "finance_rule"


class UnknownTermSheetError(NotFoundError):
    code = "unknown_term_sheet"


class UnknownSafeError(NotFoundError):
    code = "unknown_safe"


class SaveBusyError(SimError):
    """Another write to the same save is in progress (M6 sub-task 0)."""

    code = "save_busy"


class UpgradeNeededError(SimError):
    """A save from before the latest migration could not be upgraded (M6 sub-task 0)."""

    code = "upgrade_needed"


class CriticalEventOpenError(SimError):
    """Continue is blocked until the player answers a critical event (ADR-0006, amended)."""

    code = "critical_event_open"

    def __init__(self, message: str, event_id: int) -> None:
        super().__init__(message)
        self.event_id = event_id


class EventError(SimError):
    """An event choice that cannot be made (closed, not shown yet, unknown key)."""

    code = "invalid_event_choice"


class GameOverError(SimError):
    """The game has ended (bankruptcy or the founder's removal); ADR-0018 section 4."""

    code = "game_over"


class UnknownCityError(SimError):  # M9 (19.1)
    code = "unknown_city"


class GeoRuleError(SimError):
    """An office or regional launch that the rules do not allow (M9, 19.2, 19.5)."""

    code = "geo_rule"
