"""
utils/helpers.py — Shared utility functions used across all modules.

Contains formatting helpers, mathematical utilities, and terminal tools.
"""

import os
import time
import math
import secrets
import hashlib
from typing import List, Tuple, Optional
from rich.console import Console

console = Console()


# ---------------------------------------------------------------------------
# Terminal helpers
# ---------------------------------------------------------------------------

def clear_screen() -> None:
    """Clear terminal screen cross-platform."""
    os.system("cls" if os.name == "nt" else "clear")


def pause(prompt: str = "\n[dim]Press Enter to continue...[/dim]") -> None:
    """Pause execution and wait for user input."""
    console.print(prompt)
    input()


def animate_text(text: str, delay: float = 0.03, style: str = "cyan") -> None:
    """Print text character by character for a typewriter effect."""
    for char in text:
        console.print(char, end="", style=style)
        time.sleep(delay)
    console.print()


def progress_bar(value: float, width: int = 20, filled: str = "█", empty: str = "░") -> str:
    """
    Return an ASCII progress bar string.

    Args:
        value:  Float between 0.0 and 1.0
        width:  Total character width of the bar
        filled: Character for filled portion
        empty:  Character for empty portion
    """
    value     = max(0.0, min(1.0, value))
    filled_n  = int(round(value * width))
    empty_n   = width - filled_n
    return filled * filled_n + empty * empty_n


def colour_for_probability(p: float) -> str:
    """
    Return a Rich colour string representing a probability value.
    Green = safe, Yellow = moderate, Red = dangerous.
    """
    if p >= 0.80:
        return "bold green"
    elif p >= 0.60:
        return "green"
    elif p >= 0.40:
        return "yellow"
    elif p >= 0.20:
        return "orange1"
    else:
        return "bold red"


def colour_for_risk(risk: float) -> str:
    """
    Return a Rich colour string for a risk value (0=safe, 1=dangerous).
    Inverse of colour_for_probability.
    """
    return colour_for_probability(1.0 - risk)


# ---------------------------------------------------------------------------
# Mathematical utilities
# ---------------------------------------------------------------------------

def combinations(n: int, r: int) -> int:
    """Return C(n, r) — binomial coefficient."""
    if r > n or r < 0:
        return 0
    return math.comb(n, r)


def survival_probability(total_cells: int, traps: int, picks: int) -> float:
    """
    Calculate the probability of surviving exactly `picks` reveals
    on a board with `traps` mines and `total_cells` total cells.

    Uses the exact combinatorial formula:
        P = C(total - traps, picks) / C(total, picks)

    This is the theoretically correct probability for a uniformly
    random mine placement without replacement.

    Args:
        total_cells: Total number of cells on the board (25 for 5x5)
        traps:       Number of mines on the board
        picks:       Number of cells the player intends to reveal

    Returns:
        Float in [0, 1] representing survival probability.
    """
    safe_cells = total_cells - traps
    if picks > safe_cells:
        return 0.0
    num   = combinations(safe_cells, picks)
    denom = combinations(total_cells, picks)
    if denom == 0:
        return 0.0
    return num / denom


def incremental_survival(total_cells: int, traps: int, already_picked: int) -> float:
    """
    Probability of the NEXT single pick being safe, given that
    `already_picked` safe cells have already been revealed.

    Formula: (safe_remaining) / (cells_remaining)

    Args:
        total_cells:   Total board cells
        traps:         Total mines on board
        already_picked: Number of safe cells already revealed

    Returns:
        Float in [0, 1]
    """
    safe_remaining  = (total_cells - traps) - already_picked
    cells_remaining = total_cells - already_picked
    if cells_remaining <= 0:
        return 0.0
    return max(0.0, safe_remaining / cells_remaining)


def shannon_entropy(probabilities: List[float]) -> float:
    """
    Calculate Shannon entropy of a probability distribution.

    H = -Σ p_i * log2(p_i)

    Higher entropy = more uniform / less predictable distribution.

    Args:
        probabilities: List of probability values (should sum to 1.0)

    Returns:
        Float entropy value in bits.
    """
    h = 0.0
    for p in probabilities:
        if p > 0:
            h -= p * math.log2(p)
    return h


def expected_value(survival_prob: float, multiplier: float, stake: float = 1.0) -> float:
    """
    Calculate expected value of continuing one more pick.

    EV = P(survive) * multiplier * stake - (1 - P(survive)) * stake

    Args:
        survival_prob: Probability of surviving the next pick
        multiplier:    Payout multiplier if survived
        stake:         Bet size (defaults to 1 for relative comparison)

    Returns:
        Expected value float (positive = continue is +EV, negative = stop)
    """
    win  = survival_prob * multiplier * stake
    loss = (1.0 - survival_prob) * stake
    return win - loss


def format_percent(value: float, decimals: int = 2) -> str:
    """Format a float as a percentage string."""
    return f"{value * 100:.{decimals}f}%"


def format_odds(probability: float) -> str:
    """
    Express a probability as odds (e.g. 0.25 → '3:1 against').
    """
    if probability <= 0:
        return "∞:1 against"
    if probability >= 1:
        return "Certain"
    against = (1 - probability) / probability
    if against >= 1:
        return f"{against:.1f}:1 against"
    else:
        return f"1:{1/against:.1f} for"


# ---------------------------------------------------------------------------
# Seed / cryptography helpers
# ---------------------------------------------------------------------------

def generate_client_seed(length: int = 16) -> str:
    """Generate a random hex client seed using a cryptographically secure RNG."""
    return secrets.token_hex(length)


def generate_server_seed_hash(server_seed: str) -> str:
    """Return the SHA256 hash of a server seed (as would be published pre-game)."""
    return hashlib.sha256(server_seed.encode()).hexdigest()


def validate_hex_string(s: str) -> bool:
    """Return True if the string is a valid hexadecimal string."""
    try:
        int(s, 16)
        return True
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Board coordinate helpers
# ---------------------------------------------------------------------------

def index_to_coord(idx: int, cols: int = 5) -> Tuple[int, int]:
    """Convert a flat board index to (row, col)."""
    return divmod(idx, cols)


def coord_to_index(row: int, col: int, cols: int = 5) -> int:
    """Convert (row, col) to a flat board index."""
    return row * cols + col


def adjacent_cells(idx: int, rows: int = 5, cols: int = 5) -> List[int]:
    """Return indices of all orthogonally adjacent cells."""
    row, col = index_to_coord(idx, cols)
    neighbours = []
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = row + dr, col + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            neighbours.append(coord_to_index(nr, nc, cols))
    return neighbours


def corner_cells(rows: int = 5, cols: int = 5) -> List[int]:
    """Return indices of the four corner cells."""
    return [
        coord_to_index(0, 0, cols),
        coord_to_index(0, cols - 1, cols),
        coord_to_index(rows - 1, 0, cols),
        coord_to_index(rows - 1, cols - 1, cols),
    ]


def edge_cells(rows: int = 5, cols: int = 5) -> List[int]:
    """Return indices of all edge (non-corner) cells."""
    edges = []
    for r in range(rows):
        for c in range(cols):
            if (r == 0 or r == rows - 1 or c == 0 or c == cols - 1):
                idx = coord_to_index(r, c, cols)
                if idx not in corner_cells(rows, cols):
                    edges.append(idx)
    return edges


def center_cells(rows: int = 5, cols: int = 5) -> List[int]:
    """Return indices of interior (non-edge) cells."""
    all_cells = set(range(rows * cols))
    edge = set(edge_cells(rows, cols)) | set(corner_cells(rows, cols))
    return sorted(all_cells - edge)
