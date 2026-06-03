"""
engine/probability_engine.py — Dynamic probability calculation engine.

Maintains and recalculates all probability state after each pick.
Implements:
  - Bayesian-style probability updating
  - Survival probability curves
  - Expected value calculations
  - Risk scoring
  - Optimal stopping analysis
  - Weighted cell probability distributions

DISCLAIMER:
  All probabilities assume uniformly random mine placement. They describe
  the statistical landscape, not the actual outcome of any specific game.
"""

import math
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from utils.helpers import (
    survival_probability, incremental_survival, shannon_entropy,
    expected_value, format_percent, format_odds,
    corner_cells, edge_cells, center_cells,
    combinations,
)
from utils.config import BOARD_SIZE, BOARD_ROWS, BOARD_COLS, VALID_TRAP_COUNTS
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CellState:
    """Represents the current known state of a single board cell."""
    index:        int
    row:          int
    col:          int
    is_revealed:  bool  = False    # True after player picks it and it's safe
    is_mine:      bool  = False    # True if the cell triggered a mine
    mine_prob:    float = 0.0      # Current probability this cell is a mine
    safe_prob:    float = 1.0      # Current probability this cell is safe
    zone:         str   = "inner"  # "corner", "edge", "inner"


@dataclass
class ProbabilityState:
    """
    Full probability state snapshot for one round.
    Recalculated after every pick event.
    """
    trap_count:         int
    total_cells:        int             = BOARD_SIZE
    revealed_safe:      int             = 0   # How many safe picks made so far
    remaining_cells:    int             = BOARD_SIZE
    remaining_traps:    int             = 0   # Updated each round start

    # Per-cell probabilities (list of 25 floats, one per cell)
    cell_mine_probs:    List[float]     = field(default_factory=list)

    # Aggregate metrics
    next_pick_survival: float           = 1.0   # P(next pick is safe)
    cumulative_survival:float           = 1.0   # P(all picks so far were safe)
    session_ev:         float           = 0.0   # Expected value of continuing

    # Optimal stopping metrics
    recommended_stop:   int             = 0     # Recommended safe pick depth
    max_safe_cells:     int             = 0     # Total safe cells on board

    # Risk metrics
    risk_score:         float           = 0.0   # 0 (none) to 1 (certain death)
    entropy:            float           = 0.0   # Shannon entropy of mine distribution


class ProbabilityEngine:
    """
    Core probability calculation engine.

    After each game event (pick, reveal, game start), call update() to
    recalculate all probability metrics. The engine maintains no game state
    itself — it receives state and returns calculations.
    """

    # Multiplier lookup tables per trap count and pick depth
    # These are representative; real multipliers vary by platform
    MULTIPLIER_TABLES = {
        1: {i: round(1.04 ** i, 4) for i in range(25)},
        3: {i: round(1.13 ** i, 4) for i in range(22)},
        5: {i: round(1.25 ** i, 4) for i in range(20)},
        7: {i: round(1.40 ** i, 4) for i in range(18)},
    }

    def __init__(self):
        self._state: Optional[ProbabilityState] = None
        self._cells: List[CellState]            = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def initialise(self, trap_count: int) -> ProbabilityState:
        """
        Set up probability state for a new game.

        Args:
            trap_count: Number of mines (must be 1, 3, 5, or 7)

        Returns:
            Initial ProbabilityState
        """
        if trap_count not in VALID_TRAP_COUNTS:
            raise ValueError(f"trap_count must be one of {VALID_TRAP_COUNTS}")

        safe_cells  = BOARD_SIZE - trap_count
        base_prob   = trap_count / BOARD_SIZE  # Uniform initial mine probability

        # Initialise all 25 cells
        self._cells = []
        for idx in range(BOARD_SIZE):
            row, col = divmod(idx, BOARD_COLS)
            zone = self._classify_zone(row, col)
            self._cells.append(CellState(
                index     = idx,
                row       = row,
                col       = col,
                mine_prob = base_prob,
                safe_prob = 1.0 - base_prob,
                zone      = zone,
            ))

        self._state = ProbabilityState(
            trap_count          = trap_count,
            remaining_traps     = trap_count,
            remaining_cells     = BOARD_SIZE,
            max_safe_cells      = safe_cells,
            cell_mine_probs     = [base_prob] * BOARD_SIZE,
            next_pick_survival  = 1.0 - base_prob,
            cumulative_survival = 1.0,
            recommended_stop    = self._compute_optimal_stop(trap_count, 0),
            risk_score          = base_prob,
            entropy             = self._compute_entropy(trap_count, BOARD_SIZE),
        )
        logger.info(f"Probability engine initialised: {trap_count} traps, {safe_cells} safe cells")
        return self._state

    def update_after_safe_pick(
        self,
        cell_index: int,
        known_mine_positions: Optional[List[int]] = None,
    ) -> ProbabilityState:
        """
        Recalculate all probabilities after a safe cell is revealed.

        If known_mine_positions is provided (server seed known), probabilities
        become exact (0 or 1 for each cell). Otherwise, Bayesian updating
        redistributes mine probability uniformly across unrevealed cells.

        Args:
            cell_index:           The cell index that was just safely revealed
            known_mine_positions: Mine positions if server seed is known

        Returns:
            Updated ProbabilityState
        """
        if self._state is None:
            raise RuntimeError("ProbabilityEngine.initialise() must be called first")

        # Mark the cell as revealed
        self._cells[cell_index].is_revealed = True
        self._cells[cell_index].mine_prob   = 0.0
        self._cells[cell_index].safe_prob   = 1.0

        self._state.revealed_safe   += 1
        self._state.remaining_cells -= 1

        # Recalculate mine probabilities
        if known_mine_positions is not None:
            self._apply_known_mines(known_mine_positions)
        else:
            self._redistribute_mine_probs()

        # Recalculate aggregate metrics
        self._recalculate_aggregates()
        return self._state

    def update_after_mine_hit(self, cell_index: int) -> ProbabilityState:
        """Called when a mine is triggered. Marks cell and finalises state."""
        if self._state is None:
            raise RuntimeError("Not initialised")
        self._cells[cell_index].is_mine    = True
        self._cells[cell_index].mine_prob  = 1.0
        self._cells[cell_index].safe_prob  = 0.0
        self._state.risk_score             = 1.0
        self._state.next_pick_survival     = 0.0
        return self._state

    def get_cell_probabilities(self) -> List[float]:
        """Return current mine probability for every cell (list of 25 floats)."""
        return [c.mine_prob for c in self._cells]

    def get_safe_probabilities(self) -> List[float]:
        """Return current safe probability for every cell (list of 25 floats)."""
        return [c.safe_prob for c in self._cells]

    def get_recommended_cells(
        self,
        strategy: str = "BALANCED",
        n: int = 5,
    ) -> List[Tuple[int, float]]:
        """
        Return the N cells with lowest mine probability (safest picks).
        Unrevealed cells only.

        Strategy modifiers:
          CONSERVATIVE → prefers edges and corners (empirically lower variance)
          BALANCED     → purely by mine probability
          AGGRESSIVE   → prefers inner cells (higher multiplier path in some systems)
          ALL_IN       → random from unrevealed

        Returns list of (cell_index, mine_probability) tuples.
        """
        unrevealed = [
            (c.index, c.mine_prob)
            for c in self._cells
            if not c.is_revealed and not c.is_mine
        ]

        if strategy == "CONSERVATIVE":
            # Apply a small zone bonus for edges/corners
            unrevealed = sorted(
                unrevealed,
                key=lambda x: x[1] + (0.01 if self._cells[x[0]].zone == "inner" else 0)
            )
        elif strategy == "AGGRESSIVE":
            # Prefer inner cells (ignore zone penalty)
            unrevealed = sorted(unrevealed, key=lambda x: x[1])
        elif strategy == "ALL_IN":
            import random
            random.shuffle(unrevealed)
        else:  # BALANCED
            unrevealed = sorted(unrevealed, key=lambda x: x[1])

        return unrevealed[:n]

    def survival_curve(self, trap_count: int, max_picks: int = None) -> List[Dict]:
        """
        Generate the full survival probability curve for a given trap count.
        Returns a list of dicts with pick depth, survival prob, and EV.
        """
        if max_picks is None:
            max_picks = BOARD_SIZE - trap_count

        curve = []
        for picks in range(max_picks + 1):
            surv = survival_probability(BOARD_SIZE, trap_count, picks)
            mult = self.MULTIPLIER_TABLES.get(trap_count, {}).get(picks, 1.0)
            ev   = expected_value(
                surv,
                mult,
                stake=1.0
            ) if picks > 0 else 0.0
            curve.append({
                "picks":    picks,
                "survival": surv,
                "mult":     mult,
                "ev":       ev,
            })
        return curve

    def compare_continue_vs_cashout(
        self,
        current_picks: int,
        trap_count:    int,
        current_multiplier: float,
    ) -> Dict:
        """
        Compare the EV of cashing out now vs continuing one more pick.

        Returns a dict with recommendation and supporting numbers.
        """
        # EV of cashing out: lock in current multiplier
        cashout_ev = current_multiplier

        # EV of continuing: survival-weighted gain vs loss
        next_survival = incremental_survival(
            BOARD_SIZE, trap_count, current_picks
        )
        next_mult = self.MULTIPLIER_TABLES.get(trap_count, {}).get(current_picks + 1, current_multiplier * 1.1)
        continue_ev = next_survival * next_mult - (1 - next_survival) * 1.0

        recommendation = "CASH OUT" if cashout_ev >= continue_ev else "CONTINUE"

        return {
            "current_picks":    current_picks,
            "cashout_ev":       cashout_ev,
            "continue_ev":      continue_ev,
            "next_survival":    next_survival,
            "next_multiplier":  next_mult,
            "recommendation":   recommendation,
            "ev_edge":          abs(cashout_ev - continue_ev),
        }

    def get_state(self) -> Optional[ProbabilityState]:
        return self._state

    def get_cells(self) -> List[CellState]:
        return self._cells

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _redistribute_mine_probs(self) -> None:
        """
        After a safe pick, uniformly redistribute remaining mine probability
        across unrevealed cells. This is Bayesian updating under the assumption
        of uniform prior mine placement.

        P(cell is mine | revealed cells are safe) =
            remaining_traps / remaining_unrevealed_cells
        """
        revealed_count  = sum(1 for c in self._cells if c.is_revealed or c.is_mine)
        unrevealed_count = BOARD_SIZE - revealed_count
        remaining_traps = self._state.remaining_traps

        if unrevealed_count == 0:
            return

        new_prob = remaining_traps / unrevealed_count if unrevealed_count > 0 else 0.0

        for cell in self._cells:
            if not cell.is_revealed and not cell.is_mine:
                cell.mine_prob = new_prob
                cell.safe_prob = 1.0 - new_prob
            elif cell.is_revealed:
                cell.mine_prob = 0.0
                cell.safe_prob = 1.0

        self._state.cell_mine_probs = [c.mine_prob for c in self._cells]

    def _apply_known_mines(self, mine_positions: List[int]) -> None:
        """
        When mine positions are deterministically known, set exact probabilities.
        Mine cells get prob=1.0, all others get prob=0.0.
        """
        for cell in self._cells:
            if cell.is_revealed or cell.is_mine:
                continue
            if cell.index in mine_positions:
                cell.mine_prob = 1.0
                cell.safe_prob = 0.0
            else:
                cell.mine_prob = 0.0
                cell.safe_prob = 1.0

        self._state.cell_mine_probs = [c.mine_prob for c in self._cells]

    def _recalculate_aggregates(self) -> None:
        """Recompute all aggregate probability metrics from current cell state."""
        traps     = self._state.trap_count
        picks     = self._state.revealed_safe
        remaining = BOARD_SIZE - picks

        self._state.remaining_cells    = remaining
        self._state.next_pick_survival = incremental_survival(BOARD_SIZE, traps, picks)
        self._state.cumulative_survival = survival_probability(BOARD_SIZE, traps, picks)
        self._state.risk_score         = 1.0 - self._state.next_pick_survival
        self._state.recommended_stop   = self._compute_optimal_stop(traps, picks)

        # Shannon entropy of mine distribution
        mine_probs = [c.mine_prob for c in self._cells if not c.is_revealed and not c.is_mine]
        self._state.entropy = shannon_entropy(mine_probs) if mine_probs else 0.0

        # EV of continuing
        mult = self.MULTIPLIER_TABLES.get(traps, {}).get(picks + 1, 1.0)
        self._state.session_ev = expected_value(
            self._state.next_pick_survival, mult
        )

    def _compute_optimal_stop(self, traps: int, current_picks: int) -> int:
        """
        Compute the EV-maximising stop depth for a given trap count.
        Returns the pick depth at which EV of continuing first becomes negative.
        """
        max_safe = BOARD_SIZE - traps
        for depth in range(current_picks, max_safe + 1):
            surv = incremental_survival(BOARD_SIZE, traps, depth)
            mult = self.MULTIPLIER_TABLES.get(traps, {}).get(depth + 1, 1.0)
            ev   = expected_value(surv, mult)
            if ev < 0:
                return depth
        return max_safe

    def _compute_entropy(self, traps: int, cells: int) -> float:
        """Shannon entropy of the initial uniform mine distribution."""
        p = traps / cells
        if p <= 0 or p >= 1:
            return 0.0
        return -p * math.log2(p) - (1 - p) * math.log2(1 - p)

    def _classify_zone(self, row: int, col: int) -> str:
        """Classify a cell as corner, edge, or inner."""
        is_edge_r = (row == 0 or row == BOARD_ROWS - 1)
        is_edge_c = (col == 0 or col == BOARD_COLS - 1)
        if is_edge_r and is_edge_c:
            return "corner"
        elif is_edge_r or is_edge_c:
            return "edge"
        return "inner"
