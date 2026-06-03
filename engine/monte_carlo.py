"""
engine/monte_carlo.py — Monte Carlo simulation engine.

Runs thousands of simulated Mines rounds to benchmark strategies
and estimate long-term statistical outcomes.

DISCLAIMER:
  Monte Carlo results are statistical approximations based on uniform
  random mine placement. They do not predict real game outcomes.
  Real provably fair games use cryptographic RNG tied to seeds.
"""

import random
import secrets
import time
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from utils.config import BOARD_SIZE, VALID_TRAP_COUNTS
from utils.helpers import survival_probability, incremental_survival, corner_cells, edge_cells, center_cells
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SimulationResult:
    """Results from a single strategy simulation run."""
    strategy:         str
    trap_count:       int
    iterations:       int
    wins:             int             = 0    # Rounds where player cashed out
    losses:           int             = 0    # Rounds where player hit a mine
    total_picks:      int             = 0    # Sum of picks made across all rounds
    survival_depths:  List[int]       = field(default_factory=list)

    # Derived statistics (computed after run)
    win_rate:         float           = 0.0
    avg_depth:        float           = 0.0
    max_depth:        int             = 0
    min_depth:        int             = 0
    variance:         float           = 0.0
    std_dev:          float           = 0.0
    median_depth:     float           = 0.0
    bust_rate:        float           = 0.0   # % rounds ending in mine hit

    run_time_ms:      float           = 0.0


# ---------------------------------------------------------------------------
# Strategy definitions
# ---------------------------------------------------------------------------

class StrategySelector:
    """
    Picks the next cell to reveal given a board state.
    Strategies operate on lists of unrevealed cell indices.
    """

    @staticmethod
    def random_pick(unrevealed: List[int], **kwargs) -> int:
        """Pick a uniformly random unrevealed cell."""
        return secrets.choice(unrevealed)

    @staticmethod
    def edge_first(unrevealed: List[int], **kwargs) -> int:
        """Prefer edge and corner cells over inner cells."""
        edges   = [i for i in unrevealed if i in edge_cells() or i in corner_cells()]
        corners = [i for i in unrevealed if i in corner_cells()]
        if corners:
            return secrets.choice(corners)
        if edges:
            return secrets.choice(edges)
        return secrets.choice(unrevealed)

    @staticmethod
    def center_first(unrevealed: List[int], **kwargs) -> int:
        """Prefer inner/center cells."""
        inner = center_cells()
        inners = [i for i in unrevealed if i in inner]
        if inners:
            return secrets.choice(inners)
        return secrets.choice(unrevealed)

    @staticmethod
    def low_variance(unrevealed: List[int], mine_probs: List[float] = None, **kwargs) -> int:
        """
        Pick the cell with the lowest mine probability.
        Statistically equivalent to random in uniform distribution,
        but demonstrates the concept for weighted distributions.
        """
        if mine_probs:
            valid = [(i, mine_probs[i]) for i in unrevealed]
            valid.sort(key=lambda x: x[1])
            return valid[0][0]
        return secrets.choice(unrevealed)

    @staticmethod
    def aggressive(unrevealed: List[int], target_depth: int = None, current_depth: int = 0, **kwargs) -> int:
        """Always continue regardless of risk; picks inner cells to maximise depth."""
        inner = [i for i in unrevealed if i in center_cells()]
        if inner:
            return secrets.choice(inner)
        return secrets.choice(unrevealed)

    @staticmethod
    def weighted_safest(unrevealed: List[int], mine_probs: List[float] = None, **kwargs) -> int:
        """Pick from the safest quartile of cells."""
        if mine_probs and len(unrevealed) > 1:
            valid = [(i, mine_probs[i]) for i in unrevealed]
            valid.sort(key=lambda x: x[1])
            top_n = max(1, len(valid) // 4)
            return valid[random.randint(0, top_n - 1)][0]
        return secrets.choice(unrevealed)


STRATEGIES = {
    "random":          StrategySelector.random_pick,
    "edge_first":      StrategySelector.edge_first,
    "center_first":    StrategySelector.center_first,
    "low_variance":    StrategySelector.low_variance,
    "aggressive":      StrategySelector.aggressive,
    "weighted_safest": StrategySelector.weighted_safest,
}


class MonteCarloEngine:
    """
    Runs Monte Carlo simulations of Mines strategies.

    Each simulation round:
      1. Randomly places mines (uniform distribution)
      2. Applies the chosen strategy to pick cells
      3. Stops when a mine is hit OR a stop condition is met
      4. Records the outcome and pick depth

    Stop conditions per risk profile:
      CONSERVATIVE → stop at 40% of max safe cells
      BALANCED     → stop at 60% of max safe cells
      AGGRESSIVE   → stop at 80%
      ALL_IN       → continue until mine or all safe cells revealed
    """

    STOP_RATIOS = {
        "CONSERVATIVE": 0.40,
        "BALANCED":     0.60,
        "AGGRESSIVE":   0.80,
        "ALL_IN":       1.00,
    }

    def __init__(self, prob_engine=None):
        self.prob_engine = prob_engine
        self._results: List[SimulationResult] = []

    def run(
        self,
        strategy:     str,
        trap_count:   int,
        iterations:   int  = 10_000,
        risk_profile: str  = "BALANCED",
        progress_cb:  Optional[Callable[[int, int], None]] = None,
    ) -> SimulationResult:
        """
        Run a Monte Carlo simulation.

        Args:
            strategy:     Name of the strategy to simulate (see STRATEGIES keys)
            trap_count:   Number of mines (1, 3, 5, or 7)
            iterations:   Number of rounds to simulate
            risk_profile: Controls when the strategy stops
            progress_cb:  Optional callback(current, total) for UI progress updates

        Returns:
            SimulationResult with full statistical breakdown.
        """
        if trap_count not in VALID_TRAP_COUNTS:
            raise ValueError(f"trap_count must be one of {VALID_TRAP_COUNTS}")

        if strategy not in STRATEGIES:
            raise ValueError(f"Unknown strategy: {strategy}. Choose from: {list(STRATEGIES.keys())}")

        picker    = STRATEGIES[strategy]
        stop_ratio = self.STOP_RATIOS.get(risk_profile, 0.60)
        max_safe  = BOARD_SIZE - trap_count
        stop_at   = max(1, int(max_safe * stop_ratio))

        result = SimulationResult(
            strategy    = strategy,
            trap_count  = trap_count,
            iterations  = iterations,
        )

        start_time = time.perf_counter()

        for i in range(iterations):
            if progress_cb and i % 500 == 0:
                progress_cb(i, iterations)

            depth = self._simulate_round(
                picker      = picker,
                trap_count  = trap_count,
                stop_at     = stop_at,
            )

            result.survival_depths.append(depth)

            if depth >= stop_at:
                result.wins += 1
            else:
                result.losses += 1

            result.total_picks += depth

        result.run_time_ms = (time.perf_counter() - start_time) * 1000

        # Compute derived statistics
        result = self._compute_stats(result)
        self._results.append(result)

        logger.info(
            f"MC simulation complete: {strategy}/{trap_count}traps/{iterations}iter "
            f"win_rate={result.win_rate:.2%} avg_depth={result.avg_depth:.2f}"
        )
        return result

    def run_all_strategies(
        self,
        trap_count:  int,
        iterations:  int = 5_000,
        risk_profile: str = "BALANCED",
        progress_cb: Optional[Callable] = None,
    ) -> List[SimulationResult]:
        """
        Run all strategies for a given trap count and return ranked results.

        Useful for the strategy comparison panel in the simulation lab.
        """
        results = []
        for strategy in STRATEGIES:
            result = self.run(
                strategy     = strategy,
                trap_count   = trap_count,
                iterations   = iterations,
                risk_profile = risk_profile,
            )
            results.append(result)
        # Sort by win rate descending
        return sorted(results, key=lambda r: r.win_rate, reverse=True)

    def compare_trap_counts(
        self,
        strategy:   str,
        iterations: int = 5_000,
        risk_profile: str = "BALANCED",
    ) -> Dict[int, SimulationResult]:
        """
        Run the same strategy across all valid trap counts.
        Returns a dict keyed by trap count.
        """
        results = {}
        for tc in VALID_TRAP_COUNTS:
            results[tc] = self.run(
                strategy     = strategy,
                trap_count   = tc,
                iterations   = iterations,
                risk_profile = risk_profile,
            )
        return results

    def get_results(self) -> List[SimulationResult]:
        """Return all simulation results from this session."""
        return self._results

    def export_results(self) -> List[Dict]:
        """Export results as a list of dicts for JSON serialisation."""
        export = []
        for r in self._results:
            export.append({
                "strategy":    r.strategy,
                "trap_count":  r.trap_count,
                "iterations":  r.iterations,
                "win_rate":    r.win_rate,
                "avg_depth":   r.avg_depth,
                "max_depth":   r.max_depth,
                "variance":    r.variance,
                "std_dev":     r.std_dev,
                "bust_rate":   r.bust_rate,
                "run_time_ms": r.run_time_ms,
            })
        return export

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _simulate_round(
        self,
        picker:     Callable,
        trap_count: int,
        stop_at:    int,
    ) -> int:
        """
        Simulate a single round. Returns the number of safe picks made.
        Stops when a mine is hit OR stop_at safe picks achieved.
        """
        # Place mines randomly
        mine_set   = set(random.sample(range(BOARD_SIZE), trap_count))
        unrevealed = list(range(BOARD_SIZE))
        random.shuffle(unrevealed)

        # Build uniform mine probs (for strategies that use them)
        mine_probs = [trap_count / BOARD_SIZE] * BOARD_SIZE

        safe_picks = 0

        while unrevealed and safe_picks < stop_at:
            # Strategy picks a cell
            cell = picker(unrevealed, mine_probs=mine_probs, current_depth=safe_picks)
            unrevealed.remove(cell)

            if cell in mine_set:
                # Mine hit — round ends
                return safe_picks

            # Safe pick
            safe_picks += 1

            # Update mine probs for remaining cells (Bayesian update)
            remaining_unrevealed = len(unrevealed)
            remaining_mines      = len(mine_set - {cell})
            if remaining_unrevealed > 0:
                new_prob = remaining_mines / remaining_unrevealed
                mine_probs = [
                    0.0 if i == cell else new_prob
                    for i in range(BOARD_SIZE)
                ]

        return safe_picks

    @staticmethod
    def _compute_stats(result: SimulationResult) -> SimulationResult:
        """Compute descriptive statistics from survival depth list."""
        import statistics
        depths = result.survival_depths

        if not depths:
            return result

        result.win_rate    = result.wins / result.iterations
        result.bust_rate   = result.losses / result.iterations
        result.avg_depth   = sum(depths) / len(depths)
        result.max_depth   = max(depths)
        result.min_depth   = min(depths)
        result.variance    = statistics.variance(depths) if len(depths) > 1 else 0.0
        result.std_dev     = statistics.stdev(depths) if len(depths) > 1 else 0.0

        sorted_depths      = sorted(depths)
        mid                = len(sorted_depths) // 2
        if len(sorted_depths) % 2 == 0:
            result.median_depth = (sorted_depths[mid - 1] + sorted_depths[mid]) / 2
        else:
            result.median_depth = float(sorted_depths[mid])

        return result
