"""
storage/session.py — Session lifecycle and analytics manager.

Manages the active session: round persistence, session-level aggregation,
export/import, and replay functionality.

A "session" is one continuous run of the application from launch to quit.
All rounds played, simulations run, and behavioral events are tied to
the current session_id.
"""

import uuid
import json
import time
from typing import List, Dict, Optional, Any
from pathlib import Path
from storage.database import Database
from utils.logger import get_logger

logger = get_logger(__name__)


class SessionManager:
    """
    Manages the active session and bridges between the game engine,
    behavioral tracker, and database.
    """

    def __init__(self, db: Database):
        self.db          = db
        self.session_id  = str(uuid.uuid4())
        self._rounds:    List[Dict] = []
        self._started_at = time.time()

        # Create session record in DB
        self.db.create_session(self.session_id)
        logger.info(f"Session started: {self.session_id}")

    # ------------------------------------------------------------------
    # Round management
    # ------------------------------------------------------------------

    def save_round(self, game_round) -> None:
        """
        Persist a completed GameRound to the database and in-memory list.

        Args:
            game_round: A GameRound dataclass instance (or None to skip)
        """
        if game_round is None:
            return

        # Convert dataclass to storable dict
        round_data = {
            "round_id":       game_round.round_id,
            "trap_count":     game_round.trap_count,
            "client_seed":    game_round.client_seed,
            "server_seed":    game_round.server_seed,
            "nonce":          game_round.nonce,
            "risk_profile":   game_round.risk_profile,
            "mode":           game_round.mode,
            "mine_positions": game_round.mine_positions,
            "picks":          game_round.picks,
            "result":         game_round.result,
            "picks_survived": game_round.picks_survived,
        }

        self._rounds.append(round_data)
        self.db.insert_round(self.session_id, round_data)
        logger.debug(f"Round saved: {game_round.round_id} result={game_round.result}")

    def get_rounds(self) -> List[Dict]:
        """Return all rounds played this session (in-memory list)."""
        return self._rounds

    def get_round_by_id(self, round_id: str) -> Optional[Dict]:
        """Find a specific round by its ID."""
        for r in self._rounds:
            if r.get("round_id") == round_id:
                return r
        return None

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def get_session_stats(self) -> Dict:
        """
        Compute aggregate statistics for the current session.
        Uses the database for accuracy (includes all persisted rounds).
        """
        return self.db.get_session_stats(self.session_id)

    def get_all_mine_positions(self) -> List[List[int]]:
        """
        Return all mine position lists from the entire database history
        (not just current session) for RNG analysis.
        """
        return self.db.get_all_mine_positions()

    def get_trap_count_breakdown(self) -> Dict[int, int]:
        """Count how many rounds were played per trap count this session."""
        breakdown: Dict[int, int] = {}
        for r in self._rounds:
            tc = r.get("trap_count", 0)
            breakdown[tc] = breakdown.get(tc, 0) + 1
        return breakdown

    def get_result_history(self) -> List[str]:
        """Return list of round results ('CASHOUT'/'LOSS') in order."""
        return [r.get("result", "") for r in self._rounds]

    def get_depth_history(self) -> List[int]:
        """Return list of picks_survived per round in order."""
        return [r.get("picks_survived", 0) for r in self._rounds]

    # ------------------------------------------------------------------
    # Export / import
    # ------------------------------------------------------------------

    def export_session(self, export_dir: str) -> str:
        """
        Export the full session to a JSON file.

        Returns:
            Path string of the exported file.
        """
        stats   = self.get_session_stats()
        payload = {
            "session_id":   self.session_id,
            "started_at":   self._started_at,
            "exported_at":  time.time(),
            "stats":        stats,
            "rounds":       self._rounds,
            "trap_breakdown": self.get_trap_count_breakdown(),
            "depth_history":  self.get_depth_history(),
            "result_history": self.get_result_history(),
        }

        filename = f"session_{self.session_id[:8]}_{int(time.time())}.json"
        path     = Path(export_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(payload, f, indent=2)

        logger.info(f"Session exported to {path}")
        return str(path)

    def import_session(self, file_path: str) -> Dict:
        """
        Load a previously exported session file.

        Returns:
            The session data dict.
        """
        with open(file_path) as f:
            data = json.load(f)
        logger.info(f"Session imported from {file_path}")
        return data

    def replay_round(self, round_id: str) -> Optional[Dict]:
        """
        Retrieve a round's data for replay / re-analysis.
        Returns the round dict, or None if not found.
        """
        # Try in-memory first
        r = self.get_round_by_id(round_id)
        if r:
            return r
        # Fall back to database
        rows = self.db.get_rounds(session_id=self.session_id, limit=1000)
        for row in rows:
            if row.get("round_id") == round_id:
                return row
        return None

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def backup_database(self, backup_dir: str) -> str:
        """
        Create a timestamped backup of the database file.

        Returns:
            Path string of the backup file.
        """
        backup_path = str(
            Path(backup_dir) / f"mines_lab_backup_{int(time.time())}.db"
        )
        self.db.backup(backup_path)
        logger.info(f"Database backed up to {backup_path}")
        return backup_path

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all session data (in-memory and database)."""
        self._rounds = []
        self.db.clear_all()
        # Reset session
        self.session_id  = str(uuid.uuid4())
        self._started_at = time.time()
        self.db.create_session(self.session_id)
        logger.info("Session data cleared and reset")

    def close(self) -> None:
        """Finalise the session on application exit."""
        try:
            self.db.close_session(self.session_id)
            self.db.close()
            logger.info(f"Session closed: {self.session_id}")
        except Exception as exc:
            logger.error(f"Session close error: {exc}")
