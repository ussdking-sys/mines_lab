# USAGE.md — Installation & Usage Guide

---

## Contents

1. [Requirements](#requirements)
2. [Linux / macOS Installation](#linux--macos-installation)
3. [Termux (Android) Installation](#termux-android-installation)
4. [Launching the Application](#launching-the-application)
5. [Main Menu Reference](#main-menu-reference)
6. [Playing a Game](#playing-a-game)
7. [Monte Carlo Simulation Lab](#monte-carlo-simulation-lab)
8. [Provably Fair Verifier](#provably-fair-verifier)
9. [RNG & Entropy Analysis](#rng--entropy-analysis)
10. [Behavioral Analytics](#behavioral-analytics)
11. [Research Mode](#research-mode)
12. [Session Report & Export](#session-report--export)
13. [Settings](#settings)
14. [Data Files & Storage](#data-files--storage)
15. [Troubleshooting](#troubleshooting)

---

## Requirements

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Python | 3.9+ | 3.11+ recommended |
| Terminal | ANSI colour support | All modern Linux/macOS/Windows terminals |
| Storage | ~10 MB | For database and exports |
| Internet | Not required | Fully offline |

Python package requirements are in `requirements.txt`.

---

## Linux / macOS Installation

```bash
# 1. Ensure Python 3.9+ is installed
python3 --version

# 2. (Optional but recommended) Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Clone or download the project
git clone <repo-url>
cd mines_lab

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run
python3 main.py
```

---

## Termux (Android) Installation

Termux is a free Android terminal emulator available on F-Droid.
**Use the F-Droid version** — the Play Store version is outdated.

### Step 1: Install Termux
Download from: https://f-droid.org/packages/com.termux/

### Step 2: Update packages
```bash
pkg update && pkg upgrade -y
```

### Step 3: Install Python
```bash
pkg install python -y
```

### Step 4: Install dependencies
```bash
# Navigate to the project directory
cd /path/to/mines_lab

# Install Python packages
pip install -r requirements.txt --break-system-packages
```

### Step 5: Launch
```bash
python main.py
```

### Termux tips

**Font size:** Pinch to zoom or use `Ctrl+Alt++` / `Ctrl+Alt+-`

**Full keyboard:** Install the Termux:Widget add-on or use a Bluetooth keyboard
for the best experience. The on-screen keyboard works but a physical keyboard
is much more comfortable.

**Keep session alive:** Install the Termux:Boot add-on to prevent Termux from
being killed in the background.

**Storage access:** If you want to access exports from your Android file manager:
```bash
termux-setup-storage
```
Then look for exports in `~/storage/shared/`.

**Recommended terminal font:** JetBrains Mono or any Nerd Font renders the
block characters used in heatmaps cleanly. Install via Termux's font settings.

---

## Launching the Application

```bash
python main.py
```

On first launch, Mines Lab will:
1. Create the `data/` directory
2. Initialise the SQLite database
3. Write default `data/config.json`
4. Display the startup banner and disclaimer
5. Enter the main menu

All subsequent launches load your saved settings and session history automatically.

---

## Main Menu Reference

```
[1]  Play Mines                  → Game setup and active gameplay
[2]  Monte Carlo Simulation Lab  → Strategy simulation and benchmarking
[3]  Provably Fair Verifier      → Verify a real game round's integrity
[4]  RNG & Entropy Analysis      → Analyse seeds and board distributions
[5]  Behavioral Analytics        → View your decision pattern profile
[6]  Session Report              → Stats summary and export
[7]  Research Mode               → Educational internals explorer
[8]  Settings                    → Configure the application
[Q]  Quit
```

---

## Playing a Game

### Step 1: Select a game profile

Choose one of four trap configurations. Each shows:
- Trap count
- Suggested risk appetite (with rationale)

```
# | Traps    | Suggested    | Rationale
1 | 🟢 1 Trap | CONSERVATIVE | Near-zero early risk...
2 | 🟡 3 Traps | BALANCED    | Standard configuration...
3 | 🟠 5 Traps | AGGRESSIVE  | Survival drops meaningfully...
4 | 🔴 7 Traps | ALL_IN      | Near coin-flip by pick 4...
```

### Step 2: Set risk appetite

Press Enter to accept the suggestion, or type 1–4 to override:
```
1. CONSERVATIVE  ← suggested
2. BALANCED
3. AGGRESSIVE
4. ALL_IN
```

If you override, the behavioral tracker notes the divergence between
your declared and suggested profiles as a baseline.

### Step 3: Configure seeds

All seed fields are optional. Press Enter to auto-generate or use defaults.

```
Client seed  → auto-generates a random hex string if blank
Server seed  → leave blank for simulation mode (recommended for normal use)
Nonce        → auto-increments from last used value
```

**Simulation mode** (no server seed): mines are placed by a secure random RNG.
Probability calculations are valid statistical estimates.

**Deterministic mode** (server seed provided): mines are derived cryptographically.
Use this when replaying or verifying a real game round.

### Step 4: Active gameplay

During a round you will see:
- The 5×5 board with colour-coded cells
- Live probability metrics panel
- Continue vs cash-out decision comparison

**Board actions:**
```
[P]  Pick a cell          → Enter row col (e.g. "2 3") or index 1-25
[H]  Show heatmap         → Full probability heatmap overlay
[C]  Cash out             → Lock in winnings (needs ≥1 safe pick)
[A]  Auto-pick            → Engine picks its top recommendation
[Q]  Abandon round        → Exit without recording a result
```

**Reading the board:**

```
?    Unknown cell — not yet revealed
▶X   Engine-recommended safe pick (lowest mine probability)
O    High mine probability — avoid
$    Confirmed safe — you revealed this
#    Mine triggered — game over
*    Mine location revealed at game end
```

**Reading the stats panel:**

```
Picks Made          How many safe cells revealed so far
Depth Progress      Bar showing progress toward max safe cells
Next Pick Survival  Probability the NEXT pick is safe
Cumulative Survival Probability you've survived all picks so far
Risk Score          Complement of next-pick survival (0=safe, 1=certain death)
Recommended Stop    Pick depth where EV of continuing turns negative
EV of Continuing    Expected value of making one more pick
```

**Decision panel:**

After your first pick, a panel compares:
- EV of cashing out (lock in current multiplier)
- EV of continuing (survival-weighted expected gain minus risk)
- Recommendation: CASH OUT or CONTINUE

---

## Monte Carlo Simulation Lab

Access via main menu **[2]**.

### Options

**1. Run single strategy simulation**
- Choose a strategy (random / edge_first / center_first / low_variance / aggressive / weighted_safest)
- Choose trap count (1 / 3 / 5 / 7)
- Set iteration count
- Choose risk profile (controls stop depth)
- Results show win rate, average depth, standard deviation, bust rate

**2. Compare all strategies**
- Runs all 6 strategies on one trap count
- Produces a ranked comparison table and bar chart

**3. Compare trap counts**
- Runs one strategy across all four trap counts
- Useful for understanding how trap density affects a strategy

**4. View last results**
- Displays the most recent simulation results table

**5. Export simulation results**
- Saves all simulation results to `exports/simulation_results.json`

### Iteration guide

| Iterations | Speed | Accuracy |
|-----------|-------|----------|
| 1,000 | Very fast | ±3–5% |
| 5,000 | Fast | ±1–2% |
| 10,000 | Moderate | ±0.5–1% |
| 50,000 | Slow | ±0.2–0.5% |
| 100,000 | Very slow | ±0.1% |

---

## Provably Fair Verifier

Access via main menu **[3]**.

Use this to verify a completed real game round.

You will need:
- The revealed **server seed** (published by the platform after the game)
- The **published server seed hash** (shown before the game)
- Your **client seed**
- The **nonce** for that round
- The trap count
- The mine positions that were shown at game end

The verifier will:
1. Check `SHA256(server_seed) == published_hash`
2. Re-derive the mine positions from the seeds
3. Compare derived positions to the claimed positions
4. Report VERIFIED or FAILED

You can also request a step-by-step cryptographic walkthrough of the
verification process.

---

## RNG & Entropy Analysis

Access via main menu **[4]**.

### Options

**1. Analyse seed entropy**
Enter any seed string. The analyser computes:
- Shannon entropy (bits/byte)
- Quality rating (EXCELLENT / GOOD / WEAK / POOR)
- Byte frequency distribution
- Specific anomaly flags

**2. Analyse board distribution**
Analyses all mine positions stored in the database for distributional uniformity.
Renders a frequency heatmap showing which cells have appeared as mines most often.

**3. Detect duplicate boards**
Scans all stored boards for identical mine layouts.
Duplicates suggest possible RNG weakness.

**4. View anomaly alerts**
Lists all anomalies detected this session:
- Seed reuse
- Nonce reuse
- Duplicate boards
- Low entropy seeds

**5. Nonce history check**
Enter a client seed to inspect its nonce usage history.
Flags gaps, regressions, and reuse in the sequence.

---

## Behavioral Analytics

Access via main menu **[5]**.

Displays your decision pattern profile for the current session:

**Risk appetite gauge**
Visual scale showing your declared profile position vs revealed appetite score.

**Alignment status**
- ALIGNED — behaviour matches declared profile
- AGGRESSIVE_BIAS — playing more aggressively than declared
- CONSERVATIVE_BIAS — playing more conservatively than declared

**Statistics panel**
- Total decisions made
- Over-stop decisions (picks past recommended stop)
- Optimal and early exits
- Mine hits (busts)
- Win/loss streak records
- Average picks per round
- Continuation rate

**Observations**
Neutral, factual observations generated from your decision history.
Examples:
- "You continued past the probability-optimal stop point in 34% of decisions."
- "Maximum consecutive loss streak this session: 4 rounds."
- "Revealed risk appetite (72/100) is significantly higher than declared profile (BALANCED)."

No value judgements are made. All observations are statistical descriptions.

---

## Research Mode

Access via main menu **[7]**.

### Sections

**1. Probability tables**
Full combinatorial probability tables for all four trap counts.
Shows: picks, C(safe,N), C(25,N), survival %, odds, next-pick %.

**2. Survival curve explorer**
Interactive ASCII chart of the survival probability curve.
Choose any trap count. Includes full EV table with recommendations.

**3. Provably fair cryptography walkthrough**
Step-by-step explanation of the full provably fair process.
Use auto-generated or real seeds. Explains each formula and why it matters.

**4. Fisher-Yates shuffle demonstration**
Live demonstration of the shuffle algorithm used to derive mine positions.
Shows each swap step with the current state of the position array.

**5. Monte Carlo internals**
Convergence demonstration: runs random strategy at 100, 1000, and 10000 iterations
and shows how empirical win rate converges toward theoretical survival probability.

**6. Shannon entropy calculator**
Enter any string. Computes entropy, shows byte frequency distribution,
flags anomalies, and provides a recommendation.

**7. Expected value deep-dive**
Full EV tables for all four trap counts. Shows the exact pick depth
where EV of continuing turns negative for each configuration.

**8. Seed processing visualiser**
Step-by-step trace of how seeds are processed into mine positions:
SHA256 hash → HMAC-SHA256 → bytes → floats → Fisher-Yates → mine indices.
Renders the resulting board visually.

---

## Session Report & Export

Access via main menu **[6]**.

Displays:
- Total rounds, wins, losses, win rate
- Average and maximum survival depth
- Behavioral analytics summary
- Survival curves for each trap count played this session

**Export to JSON**
Saves a complete session report including all round data, stats,
depth history, and behavioral profile to `exports/session_<id>_<timestamp>.json`.

---

## Settings

Access via main menu **[8]**.

```
[1]  Default iterations    Set the default Monte Carlo iteration count
[2]  Animation speed       Set the pick animation delay in seconds
[3]  Clear session data    Delete all stored rounds and sessions
[4]  View log file path    Show the path to the application log file
```

Settings are persisted in `data/config.json` between sessions.

---

## Data Files & Storage

```
data/
  mines_lab.db          SQLite database — all rounds, sessions, behavioral events
  config.json           User settings
  nonce_history.json    Per-seed nonce tracking (prevents reuse)
  mines_lab.log         Application log (errors, warnings, debug info)

exports/
  session_<id>_<ts>.json     Session exports
  simulation_results.json    Simulation export

backups/
  mines_lab_backup_<ts>.db   Database backups
```

**Nothing is sent externally.** All data stays on your device.

To back up your database manually:
```bash
cp data/mines_lab.db backups/my_backup.db
```

To reset everything:
```bash
rm -rf data/
python main.py  # reinitialises on next launch
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'rich'`
```bash
pip install -r requirements.txt
# On Termux:
pip install -r requirements.txt --break-system-packages
```

### Colours not displaying correctly
Ensure your terminal supports 256-colour ANSI. On Termux, try:
```bash
export TERM=xterm-256color
python main.py
```

### Board rendering looks broken (garbled characters)
Use a monospace font. JetBrains Mono, Fira Code, or DejaVu Sans Mono
all render the block characters correctly.

### Database error on startup
Delete the database file and let it reinitialise:
```bash
rm data/mines_lab.db
python main.py
```

### Nonce warning appears unexpectedly
The nonce tracker detected that the entered nonce has been used before
with this client seed. This is a safety warning — you can override it
if you are intentionally replaying a round for verification purposes.

### Application crashes on Termux
Ensure `pkg upgrade` has been run recently and Python is up to date:
```bash
pkg upgrade python
pip install --upgrade -r requirements.txt --break-system-packages
```

### Log file location
```
data/mines_lab.log
```
Check this file for detailed error messages if something goes wrong.
