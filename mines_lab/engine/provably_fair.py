"""
engine/provably_fair.py — Provably fair verification and deterministic board generation.

Implements the cryptographic primitives used by provably fair Mines systems:

  - SHA256 hashing
  - HMAC-SHA256 combined seed processing
  - Deterministic board generation from known seeds
  - Hash verification and integrity checks
  - Nonce management

IMPORTANT:
  Deterministic board generation ONLY works when BOTH client seed AND server
  seed are known. If the server seed is unknown (the normal case during play),
  the system operates in simulation/approximation mode and makes NO claim to
  predict real outcomes.
"""

import hashlib
import hmac
import json
import struct
from typing import List, Optional, Tuple, Dict
from pathlib import Path
from utils.logger import get_logger
from utils.config import BOARD_SIZE, VALID_TRAP_COUNTS

logger = get_logger(__name__)


class ProvablyFairEngine:
    """
    Implements provably fair cryptographic operations.

    The typical provably fair flow is:
      1. Server generates a random server_seed before the game.
      2. Server publishes SHA256(server_seed) — the server_seed_hash.
      3. Player provides a client_seed (can be anything they choose).
      4. A nonce tracks how many bets have been made with this seed pair.
      5. After the game, the server reveals the true server_seed.
      6. Anyone can verify: SHA256(server_seed) == server_seed_hash,
         then re-derive the board to confirm it matches what was played.

    This class can:
      - Generate boards deterministically when all seeds are known.
      - Verify that a revealed server seed matches a published hash.
      - Explain each step of the process for educational display.
    """

    def __init__(self):
        self.nonce_file = Path(__file__).parent.parent / "data" / "nonce_history.json"
        self._nonce_history: Dict[str, List[int]] = self._load_nonce_history()

    # ------------------------------------------------------------------
    # Core cryptographic operations
    # ------------------------------------------------------------------

    def sha256(self, data: str) -> str:
        """Return the SHA256 hex digest of a UTF-8 string."""
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def hmac_sha256(self, key: str, message: str) -> str:
        """
        Return the HMAC-SHA256 hex digest.

        In provably fair systems this is typically computed as:
            HMAC-SHA256(key=server_seed, message=client_seed:nonce)

        This construction ensures:
          - The output is tied to both seeds simultaneously.
          - Neither party can manipulate the result unilaterally.
        """
        return hmac.new(
            key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def generate_combined_hash(
        self,
        server_seed: str,
        client_seed: str,
        nonce: int,
    ) -> str:
        """
        Generate the combined hash used to derive board positions.

        Message format: "{client_seed}:{nonce}"
        Key:            server_seed

        Returns the HMAC-SHA256 hex string (64 hex chars = 256 bits).
        """
        message = f"{client_seed}:{nonce}"
        result  = self.hmac_sha256(server_seed, message)
        logger.debug(f"Combined hash: HMAC-SHA256(server_seed, '{message}') = {result[:16]}...")
        return result

    # ------------------------------------------------------------------
    # Board generation
    # ------------------------------------------------------------------

    def derive_mine_positions(
        self,
        server_seed: str,
        client_seed: str,
        nonce: int,
        trap_count: int,
    ) -> List[int]:
        """
        Deterministically derive mine positions from known seeds.

        Algorithm (Fisher-Yates shuffle driven by HMAC output):
          1. Compute the combined HMAC-SHA256 hash.
          2. Expand the hash bytes into a seeded shuffle sequence.
          3. Apply Fisher-Yates to positions [0..24].
          4. The first `trap_count` positions after shuffling are mines.

        This matches the approach used by many provably fair Mines implementations.
        The exact algorithm may differ per platform; this is the common reference
        implementation.

        Args:
            server_seed: The revealed server seed string
            client_seed: The player's chosen client seed
            nonce:       Round nonce (increments each bet)
            trap_count:  Number of mines (1, 3, 5, or 7)

        Returns:
            Sorted list of mine cell indices (0-based, row-major)
        """
        if trap_count not in VALID_TRAP_COUNTS:
            raise ValueError(f"trap_count must be one of {VALID_TRAP_COUNTS}")

        # Step 1: Get the seed bytes from HMAC
        combined_hash = self.generate_combined_hash(server_seed, client_seed, nonce)
        hash_bytes    = bytes.fromhex(combined_hash)

        # Step 2: Generate a sequence of floats from the hash bytes
        # We use 4-byte chunks, interpreting each as a big-endian uint32
        # normalised to [0, 1). We may need more than 32 bytes, so we
        # chain additional hashes if needed (counter mode).
        floats = self._bytes_to_floats(combined_hash, needed=BOARD_SIZE)

        # Step 3: Fisher-Yates shuffle of positions [0..24] using the floats
        positions = list(range(BOARD_SIZE))
        for i in range(BOARD_SIZE - 1, 0, -1):
            j = int(floats[BOARD_SIZE - 1 - i] * (i + 1))
            j = min(j, i)  # Guard against floating point edge cases
            positions[i], positions[j] = positions[j], positions[i]

        # Step 4: First trap_count positions are mines
        mines = sorted(positions[:trap_count])
        logger.info(f"Derived {trap_count} mine positions: {mines}")
        return mines

    def _bytes_to_floats(self, hex_hash: str, needed: int) -> List[float]:
        """
        Convert a hex hash string into a list of floats in [0, 1).

        If more floats are needed than the hash provides (64 hex = 32 bytes = 8 floats
        as uint32), additional hashes are generated by appending a counter.
        """
        floats = []
        counter = 0
        current_hex = hex_hash

        while len(floats) < needed:
            raw = bytes.fromhex(current_hex)
            # Each 4 bytes → one uint32 → one float
            for i in range(0, len(raw) - 3, 4):
                chunk = raw[i:i+4]
                uint32_val = struct.unpack(">I", chunk)[0]
                floats.append(uint32_val / 0x100000000)  # Divide by 2^32

            if len(floats) < needed:
                # Extend by hashing the hash with an incrementing counter
                counter += 1
                extension_input = hex_hash + str(counter)
                current_hex = self.sha256(extension_input)

        return floats[:needed]

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_server_seed(self, server_seed: str, published_hash: str) -> bool:
        """
        Verify that a revealed server seed matches its pre-published hash.

        This is the core of provably fair verification:
          SHA256(server_seed) must equal the hash published before the game.

        Returns True if verification passes.
        """
        computed = self.sha256(server_seed)
        valid    = computed.lower() == published_hash.lower()
        logger.info(f"Server seed verification: {'PASS' if valid else 'FAIL'}")
        return valid

    def verify_full_round(
        self,
        server_seed: str,
        published_hash: str,
        client_seed: str,
        nonce: int,
        trap_count: int,
        claimed_mines: List[int],
    ) -> Dict:
        """
        Perform a full round verification:
          1. Verify server seed hash.
          2. Re-derive mine positions.
          3. Compare with claimed positions.

        Returns a detailed verification report dict.
        """
        seed_valid    = self.verify_server_seed(server_seed, published_hash)
        derived_mines = self.derive_mine_positions(server_seed, client_seed, nonce, trap_count)
        board_matches = sorted(derived_mines) == sorted(claimed_mines)

        report = {
            "seed_verified":   seed_valid,
            "board_matches":   board_matches,
            "fully_verified":  seed_valid and board_matches,
            "server_seed":     server_seed,
            "published_hash":  published_hash,
            "computed_hash":   self.sha256(server_seed),
            "client_seed":     client_seed,
            "nonce":           nonce,
            "derived_mines":   derived_mines,
            "claimed_mines":   sorted(claimed_mines),
            "trap_count":      trap_count,
        }
        return report

    def get_verification_steps(
        self,
        server_seed: str,
        client_seed: str,
        nonce: int,
    ) -> List[Dict]:
        """
        Return a step-by-step explanation of the verification process
        for display in Research Mode.
        """
        combined_hash = self.generate_combined_hash(server_seed, client_seed, nonce)
        seed_hash     = self.sha256(server_seed)
        message       = f"{client_seed}:{nonce}"

        steps = [
            {
                "step":    1,
                "title":   "Server seed hash (pre-game commitment)",
                "formula": "SHA256(server_seed)",
                "input":   server_seed,
                "output":  seed_hash,
                "explain": "Before the game starts, the server publishes this hash. "
                           "It proves the server cannot change the seed after you play.",
            },
            {
                "step":    2,
                "title":   "HMAC message construction",
                "formula": f'message = "{client_seed}:{nonce}"',
                "input":   f"client_seed={client_seed}, nonce={nonce}",
                "output":  message,
                "explain": "Your client seed and the round nonce are combined. "
                           "This ties the outcome to your inputs, preventing server manipulation.",
            },
            {
                "step":    3,
                "title":   "Combined hash generation",
                "formula": "HMAC-SHA256(key=server_seed, message=client_seed:nonce)",
                "input":   message,
                "output":  combined_hash,
                "explain": "The HMAC binds server and client seeds together. "
                           "Neither party alone can predict or influence this value.",
            },
            {
                "step":    4,
                "title":   "Fisher-Yates shuffle to derive positions",
                "formula": "shuffle([0..24]) using hash bytes as randomness",
                "input":   combined_hash[:32] + "...",
                "output":  "Mine positions (first N after shuffle)",
                "explain": "The hash bytes drive a deterministic shuffle of board positions. "
                           "The first N positions after shuffling become mine locations.",
            },
        ]
        return steps

    # ------------------------------------------------------------------
    # Nonce management
    # ------------------------------------------------------------------

    def get_current_nonce(self, client_seed: str) -> int:
        """Return the current nonce for a given client seed."""
        return self._nonce_history.get(client_seed, {}).get("current", 1)

    def increment_nonce(self, client_seed: str) -> int:
        """Increment and persist the nonce for a client seed. Returns new nonce."""
        record = self._nonce_history.setdefault(client_seed, {"current": 1, "history": []})
        old_nonce = record["current"]
        record["history"].append(old_nonce)
        record["current"] = old_nonce + 1
        self._save_nonce_history()
        logger.debug(f"Nonce incremented: {old_nonce} → {record['current']}")
        return record["current"]

    def set_nonce(self, client_seed: str, nonce: int) -> None:
        """Manually override the nonce for a client seed."""
        record = self._nonce_history.setdefault(client_seed, {"current": 1, "history": []})
        record["current"] = nonce
        self._save_nonce_history()
        logger.info(f"Nonce manually set to {nonce} for seed {client_seed[:8]}...")

    def get_nonce_history(self, client_seed: str) -> List[int]:
        """Return list of previously used nonces for a client seed."""
        return self._nonce_history.get(client_seed, {}).get("history", [])

    def check_nonce_reuse(self, client_seed: str, nonce: int) -> bool:
        """Return True if this nonce has already been used (potential anomaly)."""
        return nonce in self.get_nonce_history(client_seed)

    def _load_nonce_history(self) -> dict:
        if self.nonce_file.exists():
            try:
                with open(self.nonce_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_nonce_history(self) -> None:
        try:
            self.nonce_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.nonce_file, "w") as f:
                json.dump(self._nonce_history, f, indent=2)
        except Exception as exc:
            logger.error(f"Nonce history save failed: {exc}")
