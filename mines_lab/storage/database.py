"""
storage/database.py — SQLite database layer.

Handles all persistent storage:
  - Game rounds (seeds, picks, outcomes)
  - Session analytics
  - Simulation results
  - Behavioral event log
  - Nonce history (supplementary to the JSON file)

All data is stored locally in data/mines_lab.db.
"""

import sqlite3
import json
import time
from typing import List, Dict, Optional, Any
from pathlib import Path
from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS rounds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id        TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    trap_count      INTEGER NOT NULL,
    client_seed     TEXT,
    server_seed     TEXT,
    nonce           INTEGER,
    risk_profile    TEXT,
    mode            TEXT,
    mine_positions  TEXT,         -- JSON list
    picks           TEXT,         -- JSON list
    result          TEXT,         -- CASHOUT / LOSS / ABANDONED
    picks_survived  INTEGER,
    timestamp       REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT UNIQUE NOT NULL,
    started_at      REAL NOT NULL,
    ended_at        REAL,
    total_rounds    INTEGER DEFAULT 0,
    wins            INTEGER DEFAULT 0,
    losses          INTEGER DEFAULT 0,
    behavioral_data TEXT    -- JSON blob
);

CREATE TABLE IF NOT EXISTS simulations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy        TEXT NOT NULL,
    trap_count      INTEGER NOT NULL,
    iterations      INTEGER NOT NULL,
    win_rate        REAL,
    avg_depth       REAL,
    std_dev         REAL,
    bust_rate       REAL,
    run_time_ms     REAL,
    timestamp       REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS behavioral_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    round_id        TEXT NOT NULL,
    pick_number     INTEGER,
    survival_prob   REAL,
    chose_continue  INTEGER,  -- 1/0 boolean
    ev_continue     REAL,
    ev_cashout      REAL,
    outcome         TEXT,
    timestamp       REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rounds_session    ON rounds(session_id);
CREATE INDEX IF NOT EXISTS idx_rounds_timestamp  ON rounds(timestamp);
CREATE INDEX IF NOT EXISTS idx_behav_session     ON behavioral_events(session_id);
"""


class Database:
    """
    SQLite database wrapper providing typed insert/query methods.
    Automatically initialises schema on first connection.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._initialise_schema()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        try:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            logger.info(f"Database connected: {self.db_path}")
        except Exception as exc:
            logger.error(f"Database connection failed: {exc}")
            raise

    def _initialise_schema(self) -> None:
        try:
            self._conn.executescript(SCHEMA)
            self._conn.commit()
            logger.info("Database schema initialised")
        except Exception as exc:
            logger.error(f"Schema init failed: {exc}")

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            logger.info("Database connection closed")

    # ------------------------------------------------------------------
    # Round operations
    # ------------------------------------------------------------------

    def insert_round(self, session_id: str, round_data: dict) -> int:
        """Insert a completed game round. Returns the new row ID."""
        sql = """
            INSERT INTO rounds
            (round_id, session_id, trap_count, client_seed, server_seed,
             nonce, risk_profile, mode, mine_positions, picks, result,
             picks_survived, timestamp)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        row = (
            round_data.get("round_id", ""),
            session_id,
            round_data.get("trap_count", 0),
            round_data.get("client_seed", ""),
            round_data.get("server_seed"),
            round_data.get("nonce", 0),
            round_data.get("risk_profile", ""),
            round_data.get("mode", "SIMULATION"),
            json.dumps(round_data.get("mine_positions", [])),
            json.dumps(round_data.get("picks", [])),
            round_data.get("result", ""),
            round_data.get("picks_survived", 0),
            time.time(),
        )
        try:
            cursor = self._conn.execute(sql, row)
            self._conn.commit()
            return cursor.lastrowid
        except Exception as exc:
            logger.error(f"insert_round failed: {exc}")
            return -1

    def get_rounds(
        self,
        session_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict]:
        """Retrieve rounds, optionally filtered by session."""
        if session_id:
            sql = "SELECT * FROM rounds WHERE session_id=? ORDER BY timestamp DESC LIMIT ?"
            rows = self._conn.execute(sql, (session_id, limit)).fetchall()
        else:
            sql = "SELECT * FROM rounds ORDER BY timestamp DESC LIMIT ?"
            rows = self._conn.execute(sql, (limit,)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_all_mine_positions(self) -> List[List[int]]:
        """Return all stored mine position lists for RNG analysis."""
        rows = self._conn.execute(
            "SELECT mine_positions FROM rounds WHERE mine_positions IS NOT NULL"
        ).fetchall()
        result = []
        for row in rows:
            try:
                result.append(json.loads(row[0]))
            except Exception:
                pass
        return result

    def get_session_stats(self, session_id: str) -> Dict:
        """Aggregate stats for a single session."""
        row = self._conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN result='CASHOUT' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result='LOSS'    THEN 1 ELSE 0 END) as losses,
                AVG(picks_survived) as avg_survival,
                MAX(picks_survived) as max_survival
            FROM rounds WHERE session_id=?
        """, (session_id,)).fetchone()

        if not row or row["total"] == 0:
            return {}

        total = row["total"] or 0
        wins  = row["wins"]  or 0

        return {
            "total_rounds": total,
            "wins":         wins,
            "losses":       row["losses"] or 0,
            "win_rate":     wins / total if total else 0.0,
            "avg_survival": row["avg_survival"] or 0.0,
            "max_survival": row["max_survival"] or 0,
        }

    # ------------------------------------------------------------------
    # Session operations
    # ------------------------------------------------------------------

    def create_session(self, session_id: str) -> None:
        try:
            self._conn.execute(
                "INSERT OR IGNORE INTO sessions (session_id, started_at) VALUES (?, ?)",
                (session_id, time.time()),
            )
            self._conn.commit()
        except Exception as exc:
            logger.error(f"create_session failed: {exc}")

    def close_session(self, session_id: str, behavioral_data: dict = None) -> None:
        try:
            self._conn.execute(
                "UPDATE sessions SET ended_at=?, behavioral_data=? WHERE session_id=?",
                (time.time(), json.dumps(behavioral_data or {}), session_id),
            )
            self._conn.commit()
        except Exception as exc:
            logger.error(f"close_session failed: {exc}")

    # ------------------------------------------------------------------
    # Simulation storage
    # ------------------------------------------------------------------

    def insert_simulation(self, sim_data: dict) -> None:
        try:
            self._conn.execute("""
                INSERT INTO simulations
                (strategy, trap_count, iterations, win_rate, avg_depth,
                 std_dev, bust_rate, run_time_ms, timestamp)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                sim_data.get("strategy", ""),
                sim_data.get("trap_count", 0),
                sim_data.get("iterations", 0),
                sim_data.get("win_rate", 0),
                sim_data.get("avg_depth", 0),
                sim_data.get("std_dev", 0),
                sim_data.get("bust_rate", 0),
                sim_data.get("run_time_ms", 0),
                time.time(),
            ))
            self._conn.commit()
        except Exception as exc:
            logger.error(f"insert_simulation failed: {exc}")

    # ------------------------------------------------------------------
    # Behavioral events
    # ------------------------------------------------------------------

    def insert_behavioral_event(self, session_id: str, event: dict) -> None:
        try:
            self._conn.execute("""
                INSERT INTO behavioral_events
                (session_id, round_id, pick_number, survival_prob,
                 chose_continue, ev_continue, ev_cashout, outcome, timestamp)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                session_id,
                event.get("round_id", ""),
                event.get("pick_number", 0),
                event.get("survival_prob", 0),
                1 if event.get("chose_continue") else 0,
                event.get("ev_continue", 0),
                event.get("ev_cashout", 0),
                event.get("outcome", ""),
                time.time(),
            ))
            self._conn.commit()
        except Exception as exc:
            logger.error(f"insert_behavioral_event failed: {exc}")

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear_all(self) -> None:
        """Delete all stored data (requires user confirmation in caller)."""
        tables = ["rounds", "sessions", "simulations", "behavioral_events"]
        for t in tables:
            self._conn.execute(f"DELETE FROM {t}")
        self._conn.commit()
        logger.info("All database records cleared")

    def backup(self, backup_path: str) -> None:
        """Create a backup copy of the database."""
        import shutil
        shutil.copy2(self.db_path, backup_path)
        logger.info(f"Database backed up to {backup_path}")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict:
        """Convert a sqlite3.Row to a plain dict, deserialising JSON fields."""
        d = dict(row)
        for key in ("mine_positions", "picks"):
            if key in d and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except Exception:
                    d[key] = []
        return d
