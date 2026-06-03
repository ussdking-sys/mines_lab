"""
engine/behavioral.py — Behavioral pattern analysis and tracking.

Monitors player decision patterns across rounds to detect and report
on risk appetite, continuation tendencies, and behavioral consistency.

Tone: Neutral, scientific, observational. No moralising.
Purpose: Provide analytical insight into decision-making patterns.

Tracked patterns:
  - Declared vs revealed risk appetite
  - Continuation tendencies vs EV-optimal stopping
  - Streak behaviour (win/loss runs)
  - Deviation from recommended stop points
  - Session-level risk exposure trends
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
import json
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DecisionEvent:
    """Record of a single player decision (continue or stop)."""
    round_id:          str
    pick_number:       int        # Which pick in the round (1-based)
    recommended_stop:  bool       # Was this pick past the recommended stop point?
    survival_prob:     float      # Probability of surviving this pick
    chose_continue:    bool       # True = player picked, False = cashed out
    ev_of_continue:    float      # EV of continuing at this point
    ev_of_cashout:     float      # EV of cashing out at this point
    outcome:           str        # "SAFE" / "MINE" / "CASHOUT"


@dataclass
class BehavioralProfile:
    """
    Computed behavioral profile for the current session.
    Updated after every round completion.
    """
    # Raw counts
    total_decisions:      int     = 0
    over_stop_decisions:  int     = 0   # Decisions made past recommended stop
    optimal_exits:        int     = 0   # Cash-outs at or before recommended stop
    early_exits:          int     = 0   # Cash-outs before recommended stop
    busts:                int     = 0   # Mine hits

    # Risk appetite score (0-100, computed from behaviour)
    # 0 = maximally conservative, 100 = maximally aggressive
    revealed_appetite:    float   = 50.0

    # Declared vs revealed gap
    declared_profile:     str     = "BALANCED"
    profile_alignment:    str     = "ALIGNED"   # "ALIGNED" / "CONSERVATIVE_BIAS" / "AGGRESSIVE_BIAS"
    alignment_gap:        float   = 0.0          # 0=perfect, 100=completely misaligned

    # Streak tracking
    current_win_streak:   int     = 0
    current_loss_streak:  int     = 0
    max_win_streak:       int     = 0
    max_loss_streak:      int     = 0

    # Continuation tendencies
    avg_picks_per_round:  float   = 0.0
    continuation_rate:    float   = 0.0   # How often player continues past first pick

    # Observations (generated automatically, non-judgemental)
    observations:         List[str] = field(default_factory=list)


# Map declared profiles to expected appetite scores for alignment calculation
PROFILE_APPETITE_RANGES = {
    "CONSERVATIVE": (0,   35),
    "BALANCED":     (35,  65),
    "AGGRESSIVE":   (65,  85),
    "ALL_IN":       (85, 100),
}


class BehavioralTracker:
    """
    Tracks and analyses player behavioral patterns across rounds.

    All observations are presented as statistical observations, not value judgements.
    The goal is to surface patterns the player may not be consciously aware of.
    """

    def __init__(self, db=None):
        self.db      = db
        self._events: List[DecisionEvent]  = []
        self._profile = BehavioralProfile()
        self._round_depths: List[int]      = []   # Pick depths per round
        self._round_results: List[str]     = []   # "WIN" / "LOSS" per round

    # ------------------------------------------------------------------
    # Event logging
    # ------------------------------------------------------------------

    def log_decision(
        self,
        round_id:         str,
        pick_number:      int,
        recommended_stop: bool,
        survival_prob:    float,
        chose_continue:   bool,
        ev_continue:      float,
        ev_cashout:       float,
        outcome:          str,
    ) -> None:
        """Record a single player decision event."""
        event = DecisionEvent(
            round_id         = round_id,
            pick_number      = pick_number,
            recommended_stop = recommended_stop,
            survival_prob    = survival_prob,
            chose_continue   = chose_continue,
            ev_of_continue   = ev_continue,
            ev_of_cashout    = ev_cashout,
            outcome          = outcome,
        )
        self._events.append(event)
        self._profile.total_decisions += 1

        if recommended_stop and chose_continue:
            self._profile.over_stop_decisions += 1

    def log_round_end(
        self,
        round_id:     str,
        result:       str,     # "CASHOUT" / "LOSS"
        picks_made:   int,
        recommended_stop_depth: int,
    ) -> None:
        """Record the end of a round and update behavioral metrics."""
        self._round_depths.append(picks_made)
        self._round_results.append(result)

        if result == "CASHOUT":
            if picks_made <= recommended_stop_depth:
                self._profile.optimal_exits += 1
                if picks_made < recommended_stop_depth:
                    self._profile.early_exits += 1
            self._profile.current_win_streak  += 1
            self._profile.current_loss_streak  = 0
            self._profile.max_win_streak = max(
                self._profile.max_win_streak,
                self._profile.current_win_streak,
            )
        elif result == "LOSS":
            self._profile.busts               += 1
            self._profile.current_loss_streak += 1
            self._profile.current_win_streak   = 0
            self._profile.max_loss_streak = max(
                self._profile.max_loss_streak,
                self._profile.current_loss_streak,
            )

        self._recompute_profile()
        logger.debug(f"Round end logged: {result}, picks={picks_made}, appetite={self._profile.revealed_appetite:.1f}")

    def set_declared_profile(self, profile: str) -> None:
        """Set the player's declared risk profile."""
        self._profile.declared_profile = profile
        self._recompute_alignment()

    # ------------------------------------------------------------------
    # Profile access
    # ------------------------------------------------------------------

    def get_profile(self) -> BehavioralProfile:
        return self._profile

    def get_observations(self) -> List[str]:
        """
        Return a list of analytical observations about the player's behaviour.
        All observations are neutral and descriptive.
        """
        return self._profile.observations

    def get_appetite_score(self) -> float:
        """Return the computed risk appetite score (0-100)."""
        return self._profile.revealed_appetite

    def get_alignment_report(self) -> Dict:
        """Return a summary of declared vs revealed profile alignment."""
        return {
            "declared":        self._profile.declared_profile,
            "revealed_score":  self._profile.revealed_appetite,
            "alignment":       self._profile.profile_alignment,
            "gap":             self._profile.alignment_gap,
            "description":     self._alignment_description(),
        }

    def get_event_history(self) -> List[DecisionEvent]:
        return self._events

    def export_session(self) -> Dict:
        """Export full behavioral data for storage."""
        return {
            "profile":       self._profile.__dict__,
            "round_depths":  self._round_depths,
            "round_results": self._round_results,
            "event_count":   len(self._events),
        }

    # ------------------------------------------------------------------
    # Internal computations
    # ------------------------------------------------------------------

    def _recompute_profile(self) -> None:
        """Recompute all derived behavioral metrics."""
        total_rounds = len(self._round_depths)
        if total_rounds == 0:
            return

        # Average picks per round
        self._profile.avg_picks_per_round = sum(self._round_depths) / total_rounds

        # Continuation rate: proportion of decisions where player chose to continue
        continue_events = [e for e in self._events if e.chose_continue]
        total_events    = len(self._events)
        self._profile.continuation_rate = (
            len(continue_events) / total_events if total_events > 0 else 0.5
        )

        # Risk appetite score (0-100):
        # Derived from: continuation rate, over-stop decisions, bust rate
        over_stop_rate = (
            self._profile.over_stop_decisions / total_events
            if total_events > 0 else 0
        )
        bust_rate    = self._profile.busts / total_rounds
        cont_rate    = self._profile.continuation_rate

        # Weighted composite: continuation tendency (40%), over-stop rate (40%), bust rate (20%)
        self._profile.revealed_appetite = round(
            (cont_rate * 40) + (over_stop_rate * 40) + (bust_rate * 20),
            1
        )

        self._recompute_alignment()
        self._generate_observations()

    def _recompute_alignment(self) -> None:
        """Compute alignment between declared and revealed risk profiles."""
        declared     = self._profile.declared_profile
        appetite     = self._profile.revealed_appetite
        low, high    = PROFILE_APPETITE_RANGES.get(declared, (35, 65))
        midpoint     = (low + high) / 2

        gap = appetite - midpoint
        self._profile.alignment_gap = abs(gap)

        if self._profile.alignment_gap < 10:
            self._profile.profile_alignment = "ALIGNED"
        elif gap > 0:
            self._profile.profile_alignment = "AGGRESSIVE_BIAS"
        else:
            self._profile.profile_alignment = "CONSERVATIVE_BIAS"

    def _generate_observations(self) -> None:
        """Generate neutral analytical observations from current metrics."""
        obs = []
        p   = self._profile

        if p.over_stop_decisions > 0 and p.total_decisions > 0:
            rate = p.over_stop_decisions / p.total_decisions
            obs.append(
                f"You continued past the probability-optimal stop point in "
                f"{rate:.0%} of decisions."
            )

        if p.max_loss_streak >= 3:
            obs.append(
                f"Maximum consecutive loss streak this session: {p.max_loss_streak} rounds."
            )

        if p.profile_alignment == "AGGRESSIVE_BIAS" and p.alignment_gap > 20:
            obs.append(
                f"Revealed risk appetite ({p.revealed_appetite:.0f}/100) is "
                f"significantly higher than declared profile ({p.declared_profile})."
            )

        if p.profile_alignment == "CONSERVATIVE_BIAS" and p.alignment_gap > 20:
            obs.append(
                f"Revealed risk appetite ({p.revealed_appetite:.0f}/100) is "
                f"notably lower than declared profile ({p.declared_profile})."
            )

        if p.busts > 0 and len(self._round_results) >= 5:
            recent = self._round_results[-5:]
            recent_losses = recent.count("LOSS")
            if recent_losses >= 3:
                obs.append(
                    f"{recent_losses} of the last 5 rounds ended in mine hits."
                )

        if p.early_exits > 0:
            obs.append(
                f"Early exits (cash-outs before optimal stop): {p.early_exits} rounds."
            )

        self._profile.observations = obs

    def _alignment_description(self) -> str:
        alignment = self._profile.profile_alignment
        gap       = self._profile.alignment_gap
        declared  = self._profile.declared_profile
        appetite  = self._profile.revealed_appetite

        if alignment == "ALIGNED":
            return f"Behaviour is consistent with declared {declared} profile."
        elif alignment == "AGGRESSIVE_BIAS":
            return (
                f"Declared {declared} (expected ~{sum(PROFILE_APPETITE_RANGES[declared])//2}/100), "
                f"revealed appetite {appetite:.0f}/100 — {gap:.0f} points above profile midpoint."
            )
        else:
            return (
                f"Declared {declared} (expected ~{sum(PROFILE_APPETITE_RANGES[declared])//2}/100), "
                f"revealed appetite {appetite:.0f}/100 — {gap:.0f} points below profile midpoint."
            )
