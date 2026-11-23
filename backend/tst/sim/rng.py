"""Derived, seeded random streams (ADR-0002).

Each save stores one 64-bit master seed. A generator for a given turn and subsystem is
derived from it on demand, so no generator state is ever persisted, and adding a stream
never changes the draws of an existing one.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

import numpy as np

from tst.sim.errors import InvalidSeedError, UnknownStreamError

# Append-only. Never renumber or reuse an id: that would change every save's outcomes.
STREAM_IDS: Final = MappingProxyType(
    {
        "people_gen": 1,
        "hiring": 2,
        "morale": 3,
        "market": 4,
        "rivals": 5,
        "events": 6,
        "founder": 7,  # no key: founder build at game start (M1a)
        "growth": 8,  # key (person_id,): monthly skill growth noise (M1a)
        "reveal": 9,  # key (observer_company_id, person_id): range centre offsets (M1a)
        "tags": 10,  # key (person_id,): monthly tag reveal rolls (M1b)
        "resign": 11,  # key (person_id,): monthly resignation roll (M1b)
        "retire": 12,  # key (person_id,): monthly retirement roll (M1b)
        "actions": 13,  # key (action_seq,): randomness inside a player action (M1b)
        "delegate": 14,  # key (person_id, n): randomness inside a delegate's action (M2a)
        "product_dev": 15,  # key (product_id,): monthly development noise (M3, ADR-0017)
        "finance": 16,  # key (safe_id,) or (round_id, firm_index): investors' answers (M4)
        "board": 17,  # key (seat_id,): generating a director (M4)
        "rival_spawn": 18,  # key (category_index,): founding rival startups (M5, 15.4)
        # key (approach_id,): an employee's answer to a rival approach (M5, 15.6);
        # (approach_id, 1): whom a new approach targets (M10d, product manager 2026-11-02)
        "poach": 19,
        "entrants": 20,  # key (entrant_index,): a scheduled entrant's people (M8, 18.7)
        "macro": 21,  # key (indicator_index,), (99,) for downturns: indicators after 2025 (M10)
        "rival_region": 22,  # key (startup_id,): a rival startup's founding region (M9, 19.6)
        "supply": 26,  # key (good_index,): component indexes and shocks after 2025 (M12a, 22.4)
        "facility": 27,  # key (facility_id,): data-centre outages (M12a, 22.5)
        "research": 23,  # key (project_id,): breakthroughs and dead ends (M11, 21.3)
        "rival_research": 24,  # key (*rival key,): a researching rival's breakthroughs (M11, 21.6)
        "lead_reveal": 25,  # key (observer, company_id, domain_index): a lead range's offset (M11)
        "manufacturing": 30,  # key (facility_id,): assembly-plant yield noise (M12b, 26.2)
        "era_window": 31,  # key (era_index,): a future era's scheduled month, turn 0 (M12b, 26.4)
        "ipo": 33,  # key (company_id,): an IPO's book demand at pricing (M13, 25.2)
        # key (company_id,): a listed company's sentiment shock and analysts' targets (M13, 25.3)
        "market_sentiment": 34,
        # 35: reserved for lane B (M13)
        "pitch": 36,  # key (person_id,): an executive's quarterly pitch and quality draws (M13b)
        "mna": 37,  # key: the target's stable rival key, or (company_id,) for the player (M14)
        "integration": 38,  # key (person_id,): acquired people's monthly flight (M14)
        "rival_mna": 39,  # key: the acquirer's stable rival key (M14)
        # key (company_id,) for the player, the rival's stable key for a rival: press moments'
        # reminders, rival CEOs' statements and jabs (M14b, 29.4); 41-42 reserved for lane B
        "press": 40,
        "scenario": 43,  # key (index,): a historical scenario's staff, start month (M15b, 30.3)
        # key: the company's stable rival key, or (company_id,) for the player's companies:
        # stake purchases' price impact, minority complaints, board reviews (M16, 31)
        "group": 45,
        "founder_life": 46,  # key (company_id,): scandal draws (M24, 32.5)
        # key (0, good_index) for a commodity, (1, region_index) for power: prices after 2025
        # and shocks; (2, offtake_id) for a supplier's breach draw (M17, 33.1, 33.3, 33.5)
        "commodity": 47,
        # key (region index, block index[, tag]): hidden deposits at game start (M18, 34.1)
        "geology": 48,
        # key (tag, ...): desk studies (0, study), surveys (1, project), sampling (2, project),
        # holes (3, region index, block index, hole), estimates (4, project), studies
        # (5, project, level), permits (6, project), protests (7, project), sales (8, project),
        # minor events (9, project) (M18, 34.2-34.3)
        "exploration": 49,
        # key (tag, facility id): a refinery's capex overrun (0), incident (1), power curb (2)
        # and an incident answer's legal draw (3) (M20, 36.1, 36.4)
        "refining": 51,
        # key (facility id, tag[, ...]): a mine's construction months (0), overrun (1), grade
        # noise (2), accident (3), choices' draws (4) (M19, 35.2-35.4); refining 51 is M20's
        "mining": 50,
        # key (region index,): after 2025, nationalization and export-ban events, one
        # generator a region a month drawing a uniform per commodity, then kind and months
        # (M19, 35.4)
        "region_risk": 52,
        # key: (0, trade_id) an insider trade's investigation, (1, stake_id) a concealed
        # conflict's discovery, (2,) the family office's monthly noise, (3,) its manager
        # (M26, 37.2-37.4)
        "personal": 53,
        # key: (0, facility id) a fab's capex overrun, (1, facility id) its yield noise, and at
        # turn 0 (2, j) future node j's price and capital draws, (3, foundry index, generation)
        # a rival foundry's lag to a node after 2025, (4, foundry index, year) its capacity
        # growth that year (M21, 38.1-38.3)
        "fab": 54,
        # key (0,): the month's tension draws after 2025 (a normal, then escalation, détente
        # and rule uniforms); (1, licence id): a licence decision; (2, company id): an entity
        # listing (M22, 39.1-39.3)
        "geopolitics": 55,
        "automation": 56,  # M27a (formulas.md 40.3)
        "world": 57,  # M28 (formulas.md 41); 56 is M27a's automation
        # M36 (formulas.md 45; 58 is M31's platforms): (founder_id, member_index) a member's
        # generation; (founder_id, 0, k) life events of kind k; (person_id, 1) a child's
        # development; (founder_id, 2) a health step-back; (founder_id, 3, n) an action's draw
        "family": 59,
        "platforms": 58,  # M31 (formulas.md 44): developers, gatekeepers, rivals, standards
        # M32 (formulas.md 46): (0, region_index) grid outages and the seeded carbon, intensity
        # and queue path; (1, facility) a plant's overrun and forced outages; (2, entry) a queued
        # project's connection; (3, type_index) the game-wide learning and SMR-era draws
        "power": 60,
        "regulation": 62,  # M34 (formulas.md 48): investigations and their outcomes
        # M33 (formulas.md 47): (0, generation index) the quarter's allocation jitter;
        # (1, company id, stage index, attempt) a programme's draws and overrun; (2, foundry
        # index) a Chinese foundry's own EUV-class tools' month
        "equipment": 61,
        # M38 (formulas.md 49): (0, region_index) a region's EV-share speed and its approvals
        # after 2025, (0, n_regions) the game-wide learning rate; (1, product_id) autonomy
        # incidents; (2, facility) a cell plant's overrun and yield; (3, rival key) rival refreshes
        "vehicles": 63,
        # M41 (formulas.md 50): (0, study_id) a study's result; (1, submission_id) a review's
        # length and outcome; (2, facility or company) inspections and recalls; (3, product_id)
        # post-market signals; (4, regulator index) seeded review drift after 2025
        "medical": 64,
        # M37 (formulas.md 52): (0, series, *key) a data series' seeded continuation past its
        # last entry; (1, *rival key, year) a rival leader's retirement and successor; (2,
        # person_id, year) a founder's or family member's mortality; (3, category, year) entrants
        "dynasty": 65,
        # M39 (formulas.md 53): (0, region_index, year) installations' growth after 2025 and
        # (0, n_regions) the home humanoid window; (1, zone_id, city_index) a zone's incidents;
        # (2, region_index, zone_id) a zone's permit decision; (3, operator_index) rival entries
        "robotics": 66,
        # M42 (formulas.md 55): (0, programme_id) a molecule's hidden efficacy and safety; (1,
        # programme_id, stage, attempt) a readout; (2, review_id, k) a review; (3, programme_id,
        # region_index) generic entry; (4, rival, year) rivals' pipelines; (5, year) seeded rules;
        # (6, year, k) assets for licence; (7, kind, id, k) inspections and recalls; (8, id,
        # region) an HTA's length
        "pharma": 67,
        # M40 (formulas.md 56): (0, year) rivals' growth and (0, 0) the debris month; (1, product,
        # flight) a flight's failure, (1, 0, constellation, n) a bought launch's; (2, region_index,
        # company) a licence decision; (3, ...) a grounding's length and an event's answer
        "space": 68,
        # M44 (formulas.md 57): (0, government_index, year) seeded budgets and tenders; (1,
        # tender_id, round) rivals' bids, award tie-breaks and protests; (2, person_id) a staff
        # clearance, (2, 0, facility_id) a facility's; (3, contract_id, month) overruns and task
        # orders; (4, company_id, turn) staff reactions
        "defence": 69,
        # M47 (formulas.md 58.2): (kind index, *deal key) a counterpart's hidden zone, patience,
        # priorities, openness and revealed-range offsets, drawn at the month the talks open
        "negotiation": 70,
        "misc": 99,
    }
)

MAX_SEED: Final = 2**64 - 1


class RngFactory:
    """Hands out independent generators keyed by (turn, stream name, *entity keys).

    ADR-0013: every call site uses its own stream name, and draws that belong to one entity
    pass that entity's id as a key, so they do not depend on iteration order.
    """

    __slots__ = ("_master_seed",)

    def __init__(self, master_seed: int) -> None:
        if isinstance(master_seed, bool) or not isinstance(master_seed, int):
            raise InvalidSeedError(f"master seed must be an int, got {type(master_seed).__name__}")
        if not 0 <= master_seed <= MAX_SEED:
            raise InvalidSeedError(f"master seed must be in 0..2**64-1, got {master_seed}")
        self._master_seed = master_seed

    @property
    def master_seed(self) -> int:
        return self._master_seed

    def stream(self, turn: int, name: str, *key: int) -> np.random.Generator:
        if name not in STREAM_IDS:
            raise UnknownStreamError(f"unknown RNG stream {name!r}; add it to STREAM_IDS")
        if turn < 0:
            raise InvalidSeedError(f"turn must be >= 0 for an RNG stream, got {turn}")
        for part in key:
            if isinstance(part, bool) or not isinstance(part, int) or part < 0:
                raise InvalidSeedError(f"stream keys must be non-negative ints, got {key!r}")
        seq = np.random.SeedSequence(
            entropy=self._master_seed, spawn_key=(turn, STREAM_IDS[name], *key)
        )
        return np.random.Generator(np.random.PCG64(seq))
