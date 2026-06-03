# HOW_IT_WORKS.md — Script Architecture & Internal Systems

This document explains how every component of Mines Lab works internally.
It is written to be readable by someone new to the codebase.

---

## Module Map

```
main.py
  └── initialises all subsystems
  └── hands off to ui/menus.py

engine/
  ├── game_engine.py        — Board state machine
  ├── probability_engine.py — All probability mathematics
  ├── provably_fair.py      — Cryptographic operations
  ├── monte_carlo.py        — Simulation engine
  ├── rng_analysis.py       — Entropy and anomaly detection
  └── behavioral.py         — Decision pattern tracking

ui/
  ├── menus.py              — All navigation and game flow
  ├── board_renderer.py     — Board display
  ├── heatmap.py            — Colour gradient heatmaps
  ├── dashboard.py          — Stats and metrics panels
  └── charts.py             — ASCII charts and gauges

storage/
  ├── database.py           — SQLite operations
  └── session.py            — Session lifecycle

research/
  └── research_mode.py      — Educational internals explorer

utils/
  ├── config.py             — Constants and configuration
  ├── helpers.py            — Shared math and formatting utilities
  └── logger.py             — File-based logging
```

---

## Startup Flow

```
main.py
  1. Load Config (data/config.json, create defaults if missing)
  2. Print banner + disclaimer
  3. Initialise all subsystems (one instance each, shared by reference)
  4. Pass subsystem bundle → MenuSystem
  5. MenuSystem.main_menu() takes over — all flow is menu-driven from here
```

Subsystems are created once and injected throughout the application.
No global state. Every module receives what it needs via constructor arguments.

---

## Game Engine (`engine/game_engine.py`)

### Board representation

The board is a flat list of 25 `BoardCell` dataclass instances (row-major order):

```
Index:  0  1  2  3  4
        5  6  7  8  9
       10 11 12 13 14
       15 16 17 18 19
       20 21 22 23 24
```

Each `BoardCell` holds:
- `index`, `row`, `col` — position
- `is_mine` — True if this cell contains a mine
- `is_revealed` — True after a safe pick
- `is_hit` — True if the mine was triggered here
- `symbol` — display character (`?`, `$`, `#`, `*`, `X`, `O`)
- `mine_prob` — current probability estimate from the probability engine

### Mine placement

**Simulation mode** (no server seed):
```python
secrets.SystemRandom().sample(range(25), trap_count)
```
Uses the OS-level CSPRNG. Mines are placed uniformly at random.

**Deterministic mode** (server seed provided):
```python
pf_engine.derive_mine_positions(server_seed, client_seed, nonce, trap_count)
```
Mines are derived deterministically via HMAC-SHA256 + Fisher-Yates (see below).

### Game lifecycle

```
IDLE → new_game() → ACTIVE
ACTIVE → pick(safe cell) → ACTIVE  (continues)
ACTIVE → pick(mine cell) → MINE_HIT
ACTIVE → cash_out() → CASHED_OUT
```

---

## Probability Engine (`engine/probability_engine.py`)

### Initial state

At game start, all unrevealed cells share an equal mine probability:

```
P(cell is mine) = trap_count / 25
```

For 3 traps: `3/25 = 0.12` (12%) per cell.

### After a safe pick (Bayesian update)

When a cell is revealed as safe, it is removed from the pool.
Mine probability is redistributed uniformly across remaining unrevealed cells:

```
P(cell is mine) = remaining_traps / remaining_unrevealed_cells
```

This is the exact Bayesian posterior under the assumption of uniform
prior mine placement — equivalent to conditioning on the observed safe reveal.

### Survival probability formula

The probability of surviving exactly N picks on a board with T traps and
C total cells uses the exact combinatorial formula:

```
P(survive N picks) = C(C - T, N) / C(C, N)
```

Where `C(n, r)` is the binomial coefficient ("n choose r").

This is the hypergeometric distribution — it models sampling without
replacement from a population containing T "defective" items.

### Next-pick survival probability

The probability that the very next pick is safe, given K safe picks already made:

```
P(next safe) = (safe_remaining) / (cells_remaining)
             = (C - T - K) / (C - K)
```

This updates live after every pick during gameplay.

### Expected Value calculation

```
EV(continue) = P(safe) × multiplier × stake  −  P(mine) × stake
```

When EV is positive, continuing is mathematically better in expectation.
When EV turns negative, cashing out is the rational choice.

The **recommended stop point** is the pick depth where EV of continuing
first becomes negative for the current trap count and multiplier table.

### Known mine mode

When server seed is provided (deterministic mode), the probability engine
receives the actual mine positions and sets exact probabilities:
- Mine cells: `probability = 1.0`
- Safe cells: `probability = 0.0`

This makes the heatmap show certainty rather than estimates.

---

## Provably Fair Engine (`engine/provably_fair.py`)

### Hash operations

```python
SHA256(data)                          → 64 hex chars
HMAC-SHA256(key=server_seed,
            message=client_seed:nonce) → 64 hex chars
```

### Board generation algorithm

```
1. Compute: combined_hash = HMAC-SHA256(server_seed, f"{client_seed}:{nonce}")
2. Decode combined_hash to 32 raw bytes
3. Convert bytes to floats in [0,1):
     For each 4-byte chunk: float = uint32_value / 2^32
   (Extend by hashing further if more floats needed)
4. Apply Fisher-Yates shuffle to positions [0..24] using the floats:
     for i from 24 down to 1:
         j = floor(float[24-i] × (i+1))
         swap positions[i] and positions[j]
5. First trap_count positions after shuffle = mine locations
```

This is the standard reference implementation used by many provably fair
Mines platforms. The exact algorithm may vary per platform.

### Verification flow

```
Given: server_seed (revealed post-game), published_hash, client_seed, nonce

Step 1: SHA256(server_seed) == published_hash?
  → Confirms server did not change the seed after you played

Step 2: derive_mine_positions(server_seed, client_seed, nonce, trap_count)
  → Re-derive the board from scratch

Step 3: derived_mines == claimed_mines?
  → Confirms the board shown to you matches cryptographic derivation
```

### Nonce management

- Each `(client_seed, nonce)` pair must be unique.
- The nonce increments after every round automatically.
- Nonce history is persisted in `data/nonce_history.json`.
- Reuse detection triggers an anomaly alert.

---

## Monte Carlo Engine (`engine/monte_carlo.py`)

### What it does

Runs N simulated rounds using a chosen strategy and trap count,
records the survival depth of each round, then computes statistics.

### Simulation round logic

```
1. Place trap_count mines randomly (uniform distribution)
2. Build unrevealed cell list [0..24]
3. Loop:
   a. Strategy picks a cell from unrevealed list
   b. If mine → round ends, record depth
   c. If safe → increment depth, update mine probs
   d. If depth >= stop_at → round ends as win
4. Record final depth
```

### Stop conditions

Each risk profile maps to a fraction of maximum safe cells:

```
CONSERVATIVE → stop at 40% of (25 - trap_count)
BALANCED     → stop at 60%
AGGRESSIVE   → stop at 80%
ALL_IN       → stop at 100% (play to completion)
```

### Strategies

| Strategy | Pick logic |
|----------|-----------|
| `random` | Uniform random from unrevealed cells |
| `edge_first` | Prefer corner cells, then edge cells |
| `center_first` | Prefer inner 9 cells |
| `low_variance` | Pick cell with lowest current mine probability |
| `weighted_safest` | Pick from safest quartile of cells |
| `aggressive` | Prefer inner cells; never stops early |

Note: In a uniform distribution (simulation mode), `random`, `low_variance`,
and `weighted_safest` produce statistically equivalent results because all
unrevealed cells have equal mine probability. The differences emerge when
weighted probability distributions are used (deterministic mode).

### Statistics computed

After N iterations:
- Win rate (rounds reaching stop depth)
- Average / max / min / median survival depth
- Variance and standard deviation
- Bust rate (mine hits)
- Run time in milliseconds

---

## RNG Analyser (`engine/rng_analysis.py`)

### Shannon entropy

```
H = −Σ p_i × log₂(p_i)
```

Measures information density of the seed's byte distribution.
Maximum is 8 bits/byte (256 equally likely byte values).

Quality thresholds:
```
≥ 7.5 bits/byte → EXCELLENT
≥ 6.5 bits/byte → GOOD
≥ 5.0 bits/byte → WEAK
<  5.0 bits/byte → POOR
```

### Board distribution analysis

Over many boards, mine positions should be uniformly distributed
across all 25 cells. The analyser computes:

- Per-cell frequency (actual vs expected)
- Chi-square statistic for uniformity
- Cells with >50% deviation from expected frequency

A low chi-square (< 36.4 for 24 degrees of freedom, p < 0.05)
suggests the distribution is consistent with uniform randomness.

### Anomaly types

| Anomaly | Severity | Meaning |
|---------|----------|---------|
| `SEED_REUSE` | HIGH | Same seed used twice |
| `NONCE_REUSE` | HIGH | Same nonce used with same seed |
| `DUPLICATE_BOARD` | HIGH | Identical mine layout appeared twice |
| `LOW_ENTROPY` | MEDIUM | Seed has weak randomness |

---

## Behavioral Tracker (`engine/behavioral.py`)

### Risk appetite score (0–100)

Computed from three behavioural signals:

```
appetite = (continuation_rate × 40)
         + (over_stop_rate × 40)
         + (bust_rate × 20)
```

Where:
- `continuation_rate` = proportion of decisions where player chose to continue
- `over_stop_rate` = proportion of decisions made past recommended stop depth
- `bust_rate` = proportion of rounds ending in mine hit

### Profile alignment

Each declared risk profile corresponds to an expected appetite range:

```
CONSERVATIVE → [0, 35]
BALANCED     → [35, 65]
AGGRESSIVE   → [65, 85]
ALL_IN       → [85, 100]
```

The alignment score measures how far the revealed appetite deviates
from the midpoint of the declared profile's range.

- Gap < 10 → ALIGNED
- Gap ≥ 10, revealed > expected → AGGRESSIVE_BIAS
- Gap ≥ 10, revealed < expected → CONSERVATIVE_BIAS

### What is tracked

Every pick decision is logged as a `DecisionEvent`:
- Was this pick past the recommended stop point?
- What was the survival probability at this moment?
- Did the player choose to continue?
- What were the EVs of each option?
- What was the outcome?

This builds a complete decision history that can be exported.

---

## Storage Architecture

### SQLite (`storage/database.py`)

Four tables:

| Table | Contents |
|-------|----------|
| `rounds` | Every game round — seeds, picks, outcome, mine positions |
| `sessions` | Session metadata — timestamps, aggregate stats |
| `simulations` | Monte Carlo run summaries |
| `behavioral_events` | Per-decision event log |

WAL journal mode is used for write performance and crash safety.

### JSON files

| File | Contents |
|------|----------|
| `data/config.json` | User settings and preferences |
| `data/nonce_history.json` | Per-seed nonce usage history |
| `exports/*.json` | Session exports |

### Session manager (`storage/session.py`)

Acts as the bridge between the game engine and database:
- Receives `GameRound` objects from the game engine
- Serialises and persists them to SQLite
- Provides aggregated stats back to the UI
- Handles export, import, backup, and replay

---

## UI Rendering Pipeline

```
Game state change
  └── ProbabilityEngine.update_after_safe_pick()
        └── Returns updated ProbabilityState
  └── GameEngine.update_cell_probabilities(probs)
        └── Updates BoardCell.mine_prob and symbol for each cell
  └── BoardRenderer.render_board(cells, show_probs=True)
        └── Builds Rich Table, one row per board row
        └── Colours each cell by symbol and probability
  └── Dashboard.render_game_stats(probability_state)
        └── Live metrics panel with progress bars and EV
  └── Dashboard.render_decision_panel(comparison)
        └── Continue vs cash-out EV comparison
```

All rendering uses the `rich` library. No curses. No external TUI framework.
The terminal is redrawn by clearing the screen (`console.clear()`) and
re-rendering the full UI on each game event.

---

## Data Flow Summary

```
User input
  → menus.py (orchestrates everything)
      → game_engine.py (manages board state)
      → probability_engine.py (recalculates probabilities)
      → provably_fair.py (handles seeds/verification)
      → behavioral.py (logs decisions)
      → board_renderer.py / dashboard.py / heatmap.py (renders output)
      → session.py → database.py (persists everything)
```
