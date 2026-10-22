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
