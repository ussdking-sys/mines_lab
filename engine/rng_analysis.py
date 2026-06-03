"""
engine/rng_analysis.py — RNG quality and entropy analysis tools.

Analyses randomness quality, detects anomalies, and visualises
entropy characteristics of game seed data.

Implements:
  - Shannon entropy estimation
  - Frequency distribution analysis
  - Seed reuse and nonce anomaly detection
  - Duplicate board detection
  - Weak randomness identification
  - Statistical abnormality alerts
"""

import math
import hashlib
import json
from typing import List, Dict, Optional, Tuple
from collections import Counter
from dataclasses import dataclass, field
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EntropyReport:
    """Results of an entropy analysis run."""
    seed:             str
    raw_entropy:      float   = 0.0    # Shannon entropy of seed bytes
    normalised:       float   = 0.0    # Entropy as fraction of max (0-1)
    quality_label:    str     = ""     # "EXCELLENT" / "GOOD" / "WEAK" / "POOR"
    byte_distribution: Dict  = field(default_factory=dict)
    anomalies:        List[str] = field(default_factory=list)
    recommendation:   str    = ""


@dataclass
class AnomalyAlert:
    """A detected anomaly in seed or nonce data."""
    alert_type:  str    # "SEED_REUSE" / "NONCE_REUSE" / "DUPLICATE_BOARD" / "LOW_ENTROPY"
    severity:    str    # "HIGH" / "MEDIUM" / "LOW"
    description: str
    data:        Dict   = field(default_factory=dict)


class RNGAnalyser:
    """
    Analyses randomness quality and detects suspicious patterns.

    All analysis is statistical — it cannot determine whether a specific
    provably fair system is compromised, only flag patterns that deviate
    from expected random behaviour.
    """

    # Entropy quality thresholds (bits per byte, max=8)
    ENTROPY_EXCELLENT = 7.5
    ENTROPY_GOOD      = 6.5
    ENTROPY_WEAK      = 5.0
    # Below 5.0 = POOR

    def __init__(self, db=None):
        self.db = db
        self._seen_seeds:   List[str]       = []
        self._seen_boards:  List[List[int]] = []
        self._nonce_log:    Dict[str, List[int]] = {}
        self._alerts:       List[AnomalyAlert]   = []

    # ------------------------------------------------------------------
    # Entropy analysis
    # ------------------------------------------------------------------

    def analyse_seed(self, seed: str) -> EntropyReport:
        """
        Perform a full entropy analysis on a seed string.

        Calculates Shannon entropy of the byte distribution of the seed
        (or its hash bytes if the seed is not hex).

        Args:
            seed: Seed string (client seed, server seed, or any string)

        Returns:
            EntropyReport with full analysis.
        """
        # Get raw bytes — if hex, decode directly; otherwise encode to UTF-8
        try:
            raw_bytes = bytes.fromhex(seed)
        except ValueError:
            raw_bytes = seed.encode("utf-8")

        entropy       = self._shannon_entropy_bytes(raw_bytes)
        max_entropy   = 8.0  # Maximum possible for byte data (log2(256))
        normalised    = entropy / max_entropy

        # Byte frequency distribution
        byte_counts   = Counter(raw_bytes)
        total_bytes   = len(raw_bytes)
        distribution  = {
            f"0x{byte:02X}": count / total_bytes
            for byte, count in sorted(byte_counts.items())
        }

        # Quality classification
        if entropy >= self.ENTROPY_EXCELLENT:
            quality = "EXCELLENT"
        elif entropy >= self.ENTROPY_GOOD:
            quality = "GOOD"
        elif entropy >= self.ENTROPY_WEAK:
            quality = "WEAK"
        else:
            quality = "POOR"

        # Anomaly detection
        anomalies = []
        if entropy < self.ENTROPY_WEAK:
            anomalies.append(f"Low entropy detected: {entropy:.2f} bits/byte (expected ≥7.5)")
        if len(set(raw_bytes)) < len(raw_bytes) * 0.5:
            anomalies.append("High byte repetition — seed may not be sufficiently random")
        if len(raw_bytes) < 8:
            anomalies.append("Seed is very short — shorter seeds have smaller key spaces")

        recommendation = self._entropy_recommendation(quality)

        report = EntropyReport(
            seed              = seed[:16] + "..." if len(seed) > 16 else seed,
            raw_entropy       = entropy,
            normalised        = normalised,
            quality_label     = quality,
            byte_distribution = distribution,
            anomalies         = anomalies,
            recommendation    = recommendation,
        )

        logger.info(f"Entropy analysis: {quality} ({entropy:.3f} bits/byte)")
        return report

    def analyse_board_distribution(
        self, boards: List[List[int]], trap_count: int
    ) -> Dict:
        """
        Analyse a collection of board mine positions for distributional anomalies.

        In a truly random system, mine positions should be uniformly distributed
        across all 25 cells over many rounds.

        Args:
            boards:      List of mine position lists
            trap_count:  Expected mines per board

        Returns:
            Dict with frequency analysis and anomaly flags.
        """
        if not boards:
            return {"error": "No boards to analyse"}

        from utils.config import BOARD_SIZE
        cell_freq = Counter()
        for board in boards:
            for pos in board:
                cell_freq[pos] += 1

        total_boards     = len(boards)
        expected_freq    = (trap_count / BOARD_SIZE) * total_boards
        expected_pct     = trap_count / BOARD_SIZE

        # Compute deviation from expected for each cell
        cell_analysis = {}
        for cell in range(BOARD_SIZE):
            actual_freq = cell_freq.get(cell, 0)
            actual_pct  = actual_freq / total_boards
            deviation   = abs(actual_pct - expected_pct) / expected_pct if expected_pct > 0 else 0
            cell_analysis[cell] = {
                "frequency":  actual_freq,
                "pct":        actual_pct,
                "expected":   expected_pct,
                "deviation":  deviation,
                "flagged":    deviation > 0.5,  # >50% deviation from expected
            }

        flagged_cells = [c for c, d in cell_analysis.items() if d["flagged"]]
        chi_sq        = self._chi_square_uniformity(cell_freq, total_boards, trap_count, BOARD_SIZE)

        return {
            "total_boards":    total_boards,
            "trap_count":      trap_count,
            "expected_freq":   expected_freq,
            "cell_analysis":   cell_analysis,
            "flagged_cells":   flagged_cells,
            "chi_square":      chi_sq,
            "uniform_likely":  chi_sq < 36.4,  # p<0.05 for 24 df
            "anomaly_count":   len(flagged_cells),
        }

    def detect_duplicate_boards(self, boards: List[List[int]]) -> List[Dict]:
        """
        Detect if the same mine layout appeared more than once.
        Duplicate boards suggest possible RNG weakness or seed reuse.
        """
        seen       = {}
        duplicates = []

        for i, board in enumerate(boards):
            key = tuple(sorted(board))
            if key in seen:
                duplicates.append({
                    "board":        list(key),
                    "first_seen":   seen[key],
                    "duplicate_at": i,
                    "severity":     "HIGH",
                })
            else:
                seen[key] = i

        if duplicates:
            alert = AnomalyAlert(
                alert_type  = "DUPLICATE_BOARD",
                severity    = "HIGH",
                description = f"{len(duplicates)} duplicate board layout(s) detected",
                data        = {"count": len(duplicates)},
            )
            self._alerts.append(alert)
            logger.warning(f"Duplicate boards detected: {len(duplicates)}")

        return duplicates

    def check_seed_reuse(self, seed: str) -> bool:
        """
        Check if a seed has been seen before in this session.
        Returns True if this is a reuse (potential anomaly).
        """
        is_reuse = seed in self._seen_seeds
        if is_reuse:
            self._alerts.append(AnomalyAlert(
                alert_type  = "SEED_REUSE",
                severity    = "HIGH",
                description = f"Seed '{seed[:12]}...' has been used before",
                data        = {"seed_prefix": seed[:12]},
            ))
        else:
            self._seen_seeds.append(seed)
        return is_reuse

    def check_nonce_anomaly(self, client_seed: str, nonce: int) -> List[str]:
        """
        Detect nonce-related anomalies:
          - Nonce reuse (same nonce for same seed)
          - Non-sequential nonce (gap in sequence)
          - Nonce regression (going backwards)

        Returns list of anomaly description strings.
        """
        history = self._nonce_log.setdefault(client_seed, [])
        anomalies = []

        if nonce in history:
            anomalies.append(f"Nonce {nonce} has already been used with this seed")
            self._alerts.append(AnomalyAlert(
                alert_type  = "NONCE_REUSE",
                severity    = "HIGH",
                description = f"Nonce {nonce} reused with seed {client_seed[:8]}...",
                data        = {"nonce": nonce},
            ))

        if history:
            expected_next = max(history) + 1
            if nonce < expected_next - 1:
                anomalies.append(f"Nonce regression: expected ≥{expected_next}, got {nonce}")
            elif nonce > expected_next + 5:
                anomalies.append(f"Large nonce gap: expected ~{expected_next}, got {nonce}")

        history.append(nonce)
        return anomalies

    def get_alerts(self) -> List[AnomalyAlert]:
        """Return all anomaly alerts collected this session."""
        return self._alerts

    def get_alert_summary(self) -> Dict:
        """Return a summary of alerts by severity."""
        high   = sum(1 for a in self._alerts if a.severity == "HIGH")
        medium = sum(1 for a in self._alerts if a.severity == "MEDIUM")
        low    = sum(1 for a in self._alerts if a.severity == "LOW")
        return {
            "total": len(self._alerts),
            "high":   high,
            "medium": medium,
            "low":    low,
        }

    def generate_entropy_heatmap_data(self, boards: List[List[int]]) -> List[float]:
        """
        Generate per-cell mine frequency as a normalised list (0-1),
        suitable for heatmap rendering. Value 1.0 = most frequently mined cell.

        Returns list of 25 floats.
        """
        from utils.config import BOARD_SIZE
        freq = Counter()
        for board in boards:
            for pos in board:
                freq[pos] += 1

        if not freq:
            return [0.0] * BOARD_SIZE

        max_freq = max(freq.values())
        return [freq.get(i, 0) / max_freq for i in range(BOARD_SIZE)]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _shannon_entropy_bytes(data: bytes) -> float:
        """Shannon entropy of a byte sequence, in bits per byte."""
        if not data:
            return 0.0
        freq = Counter(data)
        total = len(data)
        entropy = 0.0
        for count in freq.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    @staticmethod
    def _chi_square_uniformity(
        freq: Counter, total: int, traps: int, board_size: int
    ) -> float:
        """
        Chi-square statistic for uniformity of mine position distribution.
        Lower = more uniform (better).
        """
        expected = (traps / board_size) * total
        chi_sq   = 0.0
        for cell in range(board_size):
            observed = freq.get(cell, 0)
            if expected > 0:
                chi_sq += (observed - expected) ** 2 / expected
        return chi_sq

    @staticmethod
    def _entropy_recommendation(quality: str) -> str:
        recs = {
            "EXCELLENT": "Seed exhibits excellent randomness. No concerns.",
            "GOOD":      "Seed quality is acceptable. Minor non-uniformity present.",
            "WEAK":      "Seed shows signs of weak randomness. Consider using a freshly generated seed.",
            "POOR":      "Seed quality is poor. This seed may have been manually typed or has very low entropy. Use a randomly generated seed instead.",
        }
        return recs.get(quality, "")
