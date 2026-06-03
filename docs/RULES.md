# RULES.md — How Mines Works

> **[GAME LINK — TO BE UPDATED]**

---

## The Mines Game

Mines is a grid-based gambling game played on a 5×5 board (25 cells).
A number of hidden mines are randomly placed on the board before the round begins.
The player does not know where the mines are.

---

## Objective

Reveal as many safe cells as possible, then **cash out** before hitting a mine.

- Each safe reveal increases a running multiplier applied to your bet.
- Hitting a mine ends the round and forfeits the bet.
- Cashing out at any point locks in the current multiplier as your payout.

---

## How a Round Works

```
1. Select a trap count (1, 3, 5, or 7 mines).
2. Place your bet.
3. The board shows 25 hidden cells.
4. Click/select a cell to reveal it.
   → Safe: multiplier increases, continue or cash out.
   → Mine: round ends, bet lost.
5. Repeat until you cash out or hit a mine.
```

---

## Trap Configurations

Mines Lab supports exactly four trap counts matching the game design:

### 🟢 1 Trap — Conservative Territory
- **Mine density:** 1/25 = **4% per unrevealed cell** (initial)
- **Maximum safe picks:** 24
- Low variance. Long runs are viable. Early mine hits are rare but possible.
- Multipliers grow slowly. Deep runs required for meaningful gains.

### 🟡 3 Traps — Standard Configuration
- **Mine density:** 3/25 = **12% per unrevealed cell** (initial)
- **Maximum safe picks:** 22
- Balanced risk/reward. EV curve peaks around picks 10–14.
- The most common configuration. Suitable for measured, disciplined play.

### 🟠 5 Traps — High Risk
- **Mine density:** 5/25 = **20% per unrevealed cell** (initial)
- **Maximum safe picks:** 20
- Meaningful danger from the first pick. Multipliers increase faster.
- Short-to-medium runs dominate long-term EV.

### 🔴 7 Traps — Maximum Tension
- **Mine density:** 7/25 = **28% per unrevealed cell** (initial)
- **Maximum safe picks:** 18
- Approximately a coin-flip by pick 4. Very high variance.
- Multipliers are steep but survival probability collapses quickly.

---

## Multipliers

Each trap count has its own multiplier curve. The multiplier increases
with each safe pick, compensating for the accumulated risk taken.

Example progression (representative, actual values vary by platform):

| Picks | 1 Trap | 3 Traps | 5 Traps | 7 Traps |
|-------|--------|---------|---------|---------|
| 1     | ×1.04  | ×1.13   | ×1.25   | ×1.40   |
| 3     | ×1.12  | ×1.44   | ×1.95   | ×2.74   |
| 5     | ×1.22  | ×1.84   | ×3.05   | ×5.38   |
| 10    | ×1.48  | ×3.39   | ×9.31   | ×28.9   |

*Actual platform multipliers may differ. Mines Lab uses representative tables
for EV calculations — verify exact multipliers on your platform.*

---

## Cash Out vs Continue

At any point after revealing at least one safe cell, you may cash out.

The decision to continue involves a trade-off:
- **Cash out**: lock in the current multiplier × your bet. Guaranteed.
- **Continue**: risk losing everything for a higher multiplier.

Mines Lab calculates the **Expected Value (EV)** of each option at every pick
depth to help you understand the statistical merits of each choice.

**EV is a long-run average. Any single round can deviate from it.**

---

## Provably Fair System

Most serious Mines platforms use a provably fair system to prove their RNG
cannot be manipulated after you place a bet.

### How it works

```
Before the game:
  1. Server generates a random server_seed
  2. Server publishes SHA256(server_seed) — the commitment hash
     (You can verify this hash exists before placing your bet)

During the game:
  3. You provide a client_seed (anything you choose)
  4. A nonce tracks your bet count with this seed pair

After the game:
  5. Server reveals the true server_seed
  6. You verify: SHA256(server_seed) == the published hash ✓
  7. You re-derive the board: HMAC-SHA256(server_seed, client_seed:nonce)
  8. Confirm the derived board matches what was played ✓
```

### What this proves

- The server committed to the outcome **before** you chose your seed (step 2).
- The server cannot change the server_seed after the fact without invalidating the hash.
- Neither party alone can predict or influence the combined hash output.
- You can independently verify every round you play.

### What it does NOT prove

- It does not protect you if the server never published a hash before your game.
- It does not prevent the house edge built into the multiplier structure.
- Knowing the client seed and nonce only does NOT let you predict the server seed.

### The key insight

**The server seed is unknown to you during play.** This is intentional and necessary.
Without the server seed, the board is cryptographically unpredictable — even with
your client seed and nonce, you cannot derive the mine positions.

This is why Mines Lab clearly marks all probability calculations as statistical
estimates, not predictions of real game outcomes.

---

## Seeds and Nonce Explained

| Variable | Who controls it | When known | Purpose |
|----------|----------------|------------|---------|
| `server_seed` | The platform | After the game | Generates the random outcome |
| `server_seed_hash` | The platform | Before the game | Proof of commitment |
| `client_seed` | You | Always | Your contribution to randomness |
| `nonce` | Auto-incremented | Always | Unique identifier per bet |

---

## House Edge

The multiplier tables are designed so that the platform retains a small
percentage of all bets in expectation (the house edge). Mines Lab's EV
calculations reflect this — at higher pick depths, EV eventually turns negative.

The **recommended stop point** shown during play is the depth at which the
EV of continuing first becomes negative under the configured multiplier table.

---

## Responsible Play

Mines is a game of chance. Probability optimisation improves decision quality
but cannot overcome:
- Cryptographic unpredictability of the server seed
- The house edge embedded in multiplier tables
- The inherent variance of any probabilistic system

No betting strategy can guarantee profits over the long run against a
mathematically sound house edge.
