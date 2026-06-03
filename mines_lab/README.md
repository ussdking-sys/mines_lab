# MINES LAB
### Provably Fair Analysis · Probability Research · Statistical Console

```
███╗   ███╗██╗███╗   ██╗███████╗███████╗    ██╗      █████╗ ██████╗
████╗ ████║██║████╗  ██║██╔════╝██╔════╝    ██║     ██╔══██╗██╔══██╗
██╔████╔██║██║██╔██╗ ██║█████╗  ███████╗    ██║     ███████║██████╔╝
██║╚██╔╝██║██║██║╚██╗██║██╔══╝  ╚════██║    ██║     ██╔══██║██╔══██╗
██║ ╚═╝ ██║██║██║ ╚████║███████╗███████║    ███████╗██║  ██║██████╔╝
╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝    ╚══════╝╚═╝  ╚═╝╚═════╝
```

---

## ⚠ DISCLAIMER

> **This application is a probability research, RNG visualisation, and statistical
> analysis tool. It does NOT predict cryptographically secure game outcomes.**
>
> Properly implemented provably fair systems are mathematically unpredictable
> without the true server seed — which is intentionally withheld during play.
>
> All simulations, probability calculations, and recommendations are statistical
> approximations based on uniform random mine placement. They describe the
> mathematical landscape, not the outcome of any specific live game.
>
> **This tool is for educational purposes only.**

---

## What is Mines Lab?

Mines Lab is a fully interactive terminal application for studying the mathematics
of Mines-style gambling games. It functions as:

- A **probability research laboratory** — exact combinatorial calculations
- A **provably fair analysis toolkit** — cryptographic verification and education
- A **Monte Carlo simulation framework** — strategy benchmarking over thousands of rounds
- A **RNG quality analyser** — entropy and anomaly detection
- A **behavioral analytics console** — decision pattern tracking
- A **cyberpunk-styled hacker terminal** — because aesthetics matter

Everything runs locally in your terminal. No internet required. All data stored on-device.

---

## 🎮 Play the Game

> **[GAME LINK — TO BE UPDATED]**

---

## Features

| Module | Description |
|--------|-------------|
| 🎮 **Game Engine** | Full 5×5 Mines board simulation with all cell states |
| 🔐 **Provably Fair Engine** | SHA256, HMAC-SHA256, deterministic board generation, hash verification |
| 📊 **Probability Engine** | Bayesian updating, survival curves, EV calculations, optimal stopping |
| 🎲 **Monte Carlo Lab** | 6 strategies × all trap counts × configurable iterations |
| 🔬 **RNG Analyser** | Shannon entropy, frequency analysis, duplicate detection, anomaly alerts |
| 🧠 **Behavioral Tracker** | Declared vs revealed risk appetite, continuation patterns, streak analysis |
| 🗺 **Heatmap Renderer** | Colour-gradient probability and frequency heatmaps |
| 📈 **Dashboard** | Live game metrics, decision panels, session summaries |
| 🔭 **Research Mode** | Full transparency into all internal calculations |
| 💾 **Local Storage** | SQLite + JSON persistence, export/import, backup/replay |

---

## Quick Start

### Requirements
- Python 3.9+
- Terminal with ANSI colour support (all Linux/macOS terminals, Windows Terminal)
- Android Termux (see Termux installation guide below)

### Install and run

```bash
# 1. Clone or download the project
git clone <repo-url>
cd mines_lab

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch
python main.py
```

---

## Game Profiles

Mines Lab uses four fixed trap configurations, each with a suggested risk appetite:

| Profile | Traps | Suggested | Notes |
|---------|-------|-----------|-------|
| 🟢 1 Trap | 1 | CONSERVATIVE | Near-zero early risk; deep runs viable |
| 🟡 3 Traps | 3 | BALANCED | Standard config; EV peaks at mid-depth |
| 🟠 5 Traps | 5 | AGGRESSIVE | Meaningful tension from pick 1 |
| 🔴 7 Traps | 7 | ALL-IN | ~28% mine probability per cell; high variance |

Suggestions are advisory — you can override to any profile. Overrides are
tracked by the behavioral analytics system as baseline declared-vs-revealed divergence.

---

## Risk Profiles

| Profile | Stop Multiplier | Description |
|---------|----------------|-------------|
| CONSERVATIVE | 40% of safe cells | Prioritises survival depth and early exit |
| BALANCED | 60% of safe cells | EV-optimised; rationally weighs continue vs stop |
| AGGRESSIVE | 80% of safe cells | Pushes for maximum pick depth |
| ALL-IN | 100% (no stop) | Pure probability display; no stop recommendation |

---

## Cell Symbols

| Symbol | Meaning |
|--------|---------|
| `?` | Unknown / unrevealed |
| `▶X` | Recommended safe pick (engine suggestion) |
| `O` | High mine probability |
| `$` | Confirmed safe (player revealed) |
| `#` | Triggered mine (game over) |
| `*` | Mine revealed at game end (not triggered) |

---

## Modes

### Simulation Mode (default)
When no server seed is provided, mines are placed using a cryptographically
secure OS-level RNG (`secrets.SystemRandom`). Probability calculations are
statistically valid but do not correspond to any real game outcome.

### Deterministic Mode
When both `client_seed` and `server_seed` are provided, the board is derived
deterministically using HMAC-SHA256 + Fisher-Yates shuffle — matching the
reference provably fair algorithm used by many Mines platforms.
This allows post-game verification and replay.

---

## Project Structure

```
mines_lab/
│
├── main.py                     ← Application entry point
│
├── engine/
│   ├── game_engine.py          ← Board state, pick logic, game lifecycle
│   ├── probability_engine.py   ← Bayesian probability, EV, optimal stopping
│   ├── provably_fair.py        ← SHA256, HMAC, board generation, verification
│   ├── monte_carlo.py          ← Simulation engine, 6 strategies
│   ├── rng_analysis.py         ← Entropy, frequency analysis, anomaly detection
│   └── behavioral.py          ← Risk appetite scoring, decision tracking
│
├── ui/
│   ├── menus.py                ← All navigation and game flow
│   ├── board_renderer.py       ← 5×5 board rendering, cell colours, animations
│   ├── heatmap.py              ← Probability and frequency heatmaps
│   ├── dashboard.py            ← Stats panels, decision analysis, summaries
│   └── charts.py               ← ASCII bar charts, histograms, gauges
│
├── storage/
│   ├── database.py             ← SQLite layer (rounds, sessions, behavioral events)
│   └── session.py              ← Session lifecycle, export/import, replay
│
├── research/
│   └── research_mode.py        ← Educational internals explorer
│
├── utils/
│   ├── config.py               ← Configuration, constants, profile tables
│   ├── helpers.py              ← Math utilities, formatting, board geometry
│   └── logger.py               ← Centralised logging to data/mines_lab.log
│
├── data/                       ← Auto-created on first run
│   ├── mines_lab.db            ← SQLite database
│   ├── config.json             ← Persisted settings
│   └── nonce_history.json      ← Per-seed nonce tracking
│
├── exports/                    ← Session exports, simulation results
├── backups/                    ← Database backups
├── docs/                       ← Full documentation
│
├── requirements.txt
└── README.md
```

---

## Documentation

| File | Contents |
|------|----------|
| [`docs/RULES.md`](docs/RULES.md) | How the Mines game works; trap configs; provably fair basics |
| [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) | Script architecture, module map, internal algorithms |
| [`docs/USAGE.md`](docs/USAGE.md) | Full installation guide, menu walkthrough, feature reference |

---

## Termux Installation

See [`docs/USAGE.md`](docs/USAGE.md) for the complete Termux setup guide.

Quick version:
```bash
pkg update && pkg upgrade
pkg install python
pip install -r requirements.txt --break-system-packages
python main.py
```

---

## License

This project is for educational and research purposes.
See disclaimer at the top of this file.
