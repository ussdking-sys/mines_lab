"""
engine/game_engine.py — Mines game state machine.

Manages a single round of the Mines game:
  - Board setup (deterministic or randomised)
  - Cell representation and state transitions
  - Pick validation and outcome resolution
  - Game lifecycle (start → pick* → (cash out | mine hit) → end)

Cell symbols used in the terminal display:
  ?  — Unknown / unrevealed
  X  — Predicted safe (probability-based suggestion)
  O  — Predicted trap
  $  — Confirmed safe (player revealed, no mine)
  #  — Triggered mine (game over)
  *  — Known mine (revealed at game end or when server seed known)
"""

import secrets
import random
from typing import List, Optional, Dict, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from utils.config import (
    BOARD_SIZE, BOARD_ROWS, BOARD_COLS, VALID_TRAP_COUNTS,
    TRAP_PROFILES, RISK_PROFILES,
)
from utils.helpers import generate_client_seed
from utils.logger import get_logger

logger = get_logger(__name__)


class GameStatus(Enum):
    """Lifecycle state of a game round."""
    IDLE        = auto()   # No game in progress
    ACTIVE      = auto()   # Game started, picks allowed
    CASHED_OUT  = auto()   # Player cashed out safely
    MINE_HIT    = auto()   # Player triggered a mine


class CellSymbol:
    """Terminal display symbols for board cells."""
    UNKNOWN     = "?"   # Not yet revealed, no prediction
    SAFE_PRED   = "X"   # Predicted safe by probability engine
    TRAP_PRED   = "O"   # Predicted trap / high mine probability
    CONFIRMED   = "$"   # Player picked, confirmed safe
    MINE_HIT    = "#"   # Player hit this mine (game over)
    MINE_SHOW   = "*"   # Mine revealed at game end (not triggered)


@dataclass
class BoardCell:
    """State of a single board cell across its full lifecycle."""
    index:       int
    row:         int
    col:         int
    is_mine:     bool  = False    # True if this cell contains a mine
    is_revealed: bool  = False    # True after a safe pick
    is_hit:      bool  = False    # True if the mine was triggered here
    symbol:      str   = CellSymbol.UNKNOWN
    mine_prob:   float = 0.0      # Set by probability engine each update


@dataclass
class GameRound:
    """Complete record of a single game round."""
    round_id:       str
    trap_count:     int
    client_seed:    str
    server_seed:    Optional[str]
    nonce:          int
    risk_profile:   str
    mine_positions: List[int]
    picks:          List[int]                  = field(default_factory=list)
    status:         GameStatus                 = GameStatus.ACTIVE
    result:         str                        = ""   # "WIN" / "LOSS" / "CASHOUT"
    picks_survived: int                        = 0
    final_multiplier: float                    = 1.0
    mode:           str                        = "SIMULATION"  # or "DETERMINISTIC"


class GameEngine:
    """
    Mines game engine — manages board state for one round at a time.

    Usage:
        engine = GameEngine()
        game = engine.new_game(trap_count=3, risk_profile="BALANCED")
        result = engine.pick(cell_index=12)
        if result["outcome"] == "SAFE":
            ...
        engine.cash_out()
    """

    def __init__(self, pf_engine=None):
        """
        Args:
            pf_engine: ProvablyFairEngine instance (optional).
                       If provided, deterministic board generation is available.
        """
        self.pf_engine    = pf_engine
        self._board:  List[BoardCell]       = []
        self._game:   Optional[GameRound]   = None
        self._history: List[GameRound]      = []

    # ------------------------------------------------------------------
    # Game lifecycle
    # ------------------------------------------------------------------

    def new_game(
        self,
        trap_count:   int,
        risk_profile: str               = "BALANCED",
        client_seed:  Optional[str]     = None,
        server_seed:  Optional[str]     = None,
        nonce:        Optional[int]     = None,
    ) -> GameRound:
        """
        Start a new game round.

        If server_seed is provided AND pf_engine is available:
            → Deterministic board generation (exact mine positions)
        Otherwise:
            → Cryptographically random simulation mode

        Args:
            trap_count:   Number of mines (must be 1, 3, 5, or 7)
            risk_profile: Player's declared risk appetite
            client_seed:  Player's seed (auto-generated if None)
            server_seed:  Optional server seed for deterministic play
            nonce:        Optional nonce override

        Returns:
            GameRound record for this round.
        """
        if trap_count not in VALID_TRAP_COUNTS:
            raise ValueError(f"trap_count must be one of {VALID_TRAP_COUNTS}")

        # Generate or use provided seeds
        client_seed = client_seed or generate_client_seed()
        nonce       = nonce or 1

        # Determine mine positions
        if server_seed and self.pf_engine:
            mine_positions = self.pf_engine.derive_mine_positions(
                server_seed, client_seed, nonce, trap_count
            )
            mode = "DETERMINISTIC"
            logger.info("Deterministic board generated from known seeds")
        else:
            mine_positions = self._random_mines(trap_count)
            mode = "SIMULATION"
            logger.info(f"Simulation board generated: {trap_count} random mines")

        # Build the board
        self._board = []
        for idx in range(BOARD_SIZE):
            row, col = divmod(idx, BOARD_COLS)
            self._board.append(BoardCell(
                index    = idx,
                row      = row,
                col      = col,
                is_mine  = idx in mine_positions,
                symbol   = CellSymbol.UNKNOWN,
                mine_prob= trap_count / BOARD_SIZE,
            ))

        import uuid
        self._game = GameRound(
            round_id      = str(uuid.uuid4())[:8],
            trap_count    = trap_count,
            client_seed   = client_seed,
            server_seed   = server_seed,
            nonce         = nonce,
            risk_profile  = risk_profile,
            mine_positions= mine_positions,
            mode          = mode,
        )

        logger.info(f"New game started: {trap_count} traps, profile={risk_profile}, mode={mode}")
        return self._game

    def pick(self, cell_index: int) -> Dict:
        """
        Reveal a cell. Returns an outcome dict.

        Possible outcomes:
          "SAFE"     — cell was safe, game continues
          "MINE"     — cell was a mine, game over
          "INVALID"  — cell already revealed or game not active

        Args:
            cell_index: 0-based index of the cell to reveal (0-24)

        Returns:
            Dict with keys: outcome, cell_index, picks_survived, symbol
        """
        if self._game is None or self._game.status != GameStatus.ACTIVE:
            return {"outcome": "INVALID", "reason": "No active game"}

        if cell_index < 0 or cell_index >= BOARD_SIZE:
            return {"outcome": "INVALID", "reason": "Cell index out of range"}

        cell = self._board[cell_index]

        if cell.is_revealed or cell.is_hit:
            return {"outcome": "INVALID", "reason": "Cell already revealed"}

        self._game.picks.append(cell_index)

        if cell.is_mine:
            # Mine triggered — game over
            cell.is_hit    = True
            cell.symbol    = CellSymbol.MINE_HIT
            self._game.status = GameStatus.MINE_HIT
            self._game.result = "LOSS"
            self._reveal_all_mines()
            logger.info(f"Mine hit at cell {cell_index}. Game over.")
            return {
                "outcome":       "MINE",
                "cell_index":    cell_index,
                "picks_survived": self._game.picks_survived,
                "symbol":        CellSymbol.MINE_HIT,
            }
        else:
            # Safe pick
            cell.is_revealed = True
            cell.symbol      = CellSymbol.CONFIRMED
            self._game.picks_survived += 1
            logger.info(f"Safe pick at cell {cell_index}. Total safe: {self._game.picks_survived}")
            return {
                "outcome":       "SAFE",
                "cell_index":    cell_index,
                "picks_survived": self._game.picks_survived,
                "symbol":        CellSymbol.CONFIRMED,
            }

    def cash_out(self) -> Dict:
        """
        End the game by cashing out (player walks away with winnings).
        Only valid during ACTIVE games with at least one safe pick.

        Returns:
            Dict summarising the cash-out.
        """
        if self._game is None or self._game.status != GameStatus.ACTIVE:
            return {"outcome": "INVALID", "reason": "No active game to cash out"}

        if self._game.picks_survived == 0:
            return {"outcome": "INVALID", "reason": "Must make at least one pick before cashing out"}

        self._game.status = GameStatus.CASHED_OUT
        self._game.result = "CASHOUT"
        self._reveal_all_mines()

        logger.info(f"Cash out: survived {self._game.picks_survived} picks")
        self._history.append(self._game)

        return {
            "outcome":       "CASHOUT",
            "picks_survived": self._game.picks_survived,
            "trap_count":    self._game.trap_count,
            "mine_positions": self._game.mine_positions,
        }

    def end_game(self) -> Optional[GameRound]:
        """Finalise and archive the current game. Returns the completed round."""
        if self._game is None:
            return None
        if self._game.status == GameStatus.ACTIVE:
            self._game.status = GameStatus.MINE_HIT
            self._game.result = "ABANDONED"
        if self._game not in self._history:
            self._history.append(self._game)
        completed = self._game
        self._game = None
        return completed

    # ------------------------------------------------------------------
    # Board access
    # ------------------------------------------------------------------

    def get_board(self) -> List[BoardCell]:
        """Return the current board state (25 cells)."""
        return self._board

    def get_cell(self, index: int) -> BoardCell:
        return self._board[index]

    def get_game(self) -> Optional[GameRound]:
        return self._game

    def is_active(self) -> bool:
        return self._game is not None and self._game.status == GameStatus.ACTIVE

    def update_cell_probabilities(self, probs: List[float]) -> None:
        """
        Accept updated mine probabilities from the ProbabilityEngine
        and apply them to board cells for display purposes.

        Args:
            probs: List of 25 floats, one per cell
        """
        for idx, prob in enumerate(probs[:BOARD_SIZE]):
            self._board[idx].mine_prob = prob
            # Update display symbol for unrevealed cells
            if not self._board[idx].is_revealed and not self._board[idx].is_hit:
                if prob >= 0.5:
                    self._board[idx].symbol = CellSymbol.TRAP_PRED
                else:
                    self._board[idx].symbol = CellSymbol.UNKNOWN

    def apply_safe_predictions(self, safe_indices: List[int]) -> None:
        """Mark specific cells as 'predicted safe' (X symbol)."""
        for idx in safe_indices:
            cell = self._board[idx]
            if not cell.is_revealed and not cell.is_hit:
                cell.symbol = CellSymbol.SAFE_PRED

    def get_history(self) -> List[GameRound]:
        """Return list of completed game rounds this session."""
        return self._history

    def get_session_stats(self) -> Dict:
        """Compute aggregate stats from this session's history."""
        if not self._history:
            return {}

        wins     = sum(1 for g in self._history if g.result == "CASHOUT")
        losses   = sum(1 for g in self._history if g.result == "LOSS")
        total    = len(self._history)
        avg_surv = sum(g.picks_survived for g in self._history) / total if total else 0

        return {
            "total_rounds":     total,
            "wins":             wins,
            "losses":           losses,
            "win_rate":         wins / total if total else 0.0,
            "avg_survival":     avg_surv,
            "max_survival":     max((g.picks_survived for g in self._history), default=0),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _random_mines(self, trap_count: int) -> List[int]:
        """
        Place mines randomly using secrets.SystemRandom (OS-level CSPRNG).
        This is the simulation-mode board generator.
        """
        rng       = secrets.SystemRandom()
        positions = rng.sample(range(BOARD_SIZE), trap_count)
        return sorted(positions)

    def _reveal_all_mines(self) -> None:
        """
        At game end, reveal all mine positions that weren't triggered.
        Triggered mines stay as '#'; others become '*'.
        """
        for cell in self._board:
            if cell.is_mine and not cell.is_hit:
                cell.symbol = CellSymbol.MINE_SHOW
