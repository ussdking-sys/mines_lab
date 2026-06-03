"""
utils/config.py — Application configuration and path management.

Handles all path resolution, default settings, and first-run initialisation.
Settings are persisted in data/config.json between sessions.
"""

import os
import json
from pathlib import Path
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Default configuration values
# ---------------------------------------------------------------------------
DEFAULTS = {
    "version":          "1.0.0",
    "theme":            "cyberpunk",        # UI colour theme
    "default_traps":    3,                  # Default trap count (1/3/5/7)
    "animation_speed":  0.03,              # Seconds per animation frame
    "monte_carlo_iter": 10000,             # Default MC iteration count
    "nonce_start":      1,                 # Starting nonce value
    "auto_save":        True,              # Auto-save sessions
    "research_mode":    False,             # Research mode off by default
    "show_disclaimer":  True,              # Show disclaimer on launch
    "export_format":    "json",            # Default export format
    "log_level":        "WARNING",         # Logging verbosity
}

# Trap count → suggested risk profile mapping
TRAP_PROFILES = {
    1: {
        "label":     "1 Trap",
        "suggested": "CONSERVATIVE",
        "rationale": "Near-zero early risk. Optimal for deep runs and low-variance accumulation.",
        "color":     "green",
        "emoji":     "🟢",
    },
    3: {
        "label":     "3 Traps",
        "suggested": "BALANCED",
        "rationale": "Standard configuration. EV curve peaks at mid-depth; suits measured play.",
        "color":     "yellow",
        "emoji":     "🟡",
    },
    5: {
        "label":     "5 Traps",
        "suggested": "AGGRESSIVE",
        "rationale": "Survival drops meaningfully each pick. Short runs with early exits dominate EV.",
        "color":     "orange1",
        "emoji":     "🟠",
    },
    7: {
        "label":     "7 Traps",
        "suggested": "ALL_IN",
        "rationale": "Near coin-flip by pick 4. Long runs are statistically indefensible.",
        "color":     "red",
        "emoji":     "🔴",
    },
}

# Risk appetite definitions
RISK_PROFILES = {
    "CONSERVATIVE": {
        "description":    "Prioritises survival depth; recommends early cash-out",
        "stop_multiplier": 0.4,    # Stop at 40% of max safe picks
        "color":          "green",
        "short":          "CONS",
    },
    "BALANCED": {
        "description":    "EV-optimised; weighs continuation vs stop rationally",
        "stop_multiplier": 0.6,
        "color":          "yellow",
        "short":          "BLNC",
    },
    "AGGRESSIVE": {
        "description":    "Maximises expected picks before stop",
        "stop_multiplier": 0.8,
        "color":          "orange1",
        "short":          "AGGR",
    },
    "ALL_IN": {
        "description":    "No stopping recommendations — pure probability display",
        "stop_multiplier": 1.0,
        "color":          "red",
        "short":          "ALIN",
    },
}

# Valid trap counts (game design constraint)
VALID_TRAP_COUNTS = [1, 3, 5, 7]

# Board dimensions
BOARD_ROWS = 5
BOARD_COLS = 5
BOARD_SIZE = BOARD_ROWS * BOARD_COLS  # 25 cells


class Config:
    """
    Central configuration object. Loads from disk on init, saves on mutation.
    All path resolution is handled here so modules never hard-code paths.
    """

    def __init__(self, base_dir: str = None):
        # Resolve project root relative to this file
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent
        self.data_dir    = self.base_dir / "data"
        self.exports_dir = self.base_dir / "exports"
        self.backups_dir = self.base_dir / "backups"
        self.config_path = self.data_dir / "config.json"
        self.db_path     = str(self.data_dir / "mines_lab.db")
        self.nonce_path  = self.data_dir / "nonce_history.json"

        # Load or create settings
        self._settings = self._load()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get(self, key: str, default=None):
        return self._settings.get(key, default)

    def set(self, key: str, value) -> None:
        self._settings[key] = value
        self._save()

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        for d in [self.data_dir, self.exports_dir, self.backups_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def trap_profile(self, trap_count: int) -> dict:
        return TRAP_PROFILES.get(trap_count, TRAP_PROFILES[3])

    def risk_profile(self, appetite: str) -> dict:
        return RISK_PROFILES.get(appetite, RISK_PROFILES["BALANCED"])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    stored = json.load(f)
                # Merge with defaults so new keys are always present
                merged = {**DEFAULTS, **stored}
                return merged
            except Exception as exc:
                logger.warning(f"Config load failed ({exc}); using defaults")
        return dict(DEFAULTS)

    def _save(self) -> None:
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(self._settings, f, indent=2)
        except Exception as exc:
            logger.error(f"Config save failed: {exc}")
