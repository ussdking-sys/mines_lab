"""
research/research_mode.py — Research Mode: educational internals explorer.

Exposes all internal calculations, probability tables, entropy measurements,
Monte Carlo internals, and seed processing steps in a transparent,
educational interface.

This mode makes the system understandable from first principles.
"""

import time
from typing import List, Dict, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.prompt import Prompt, Confirm
from rich import box

from utils.config import VALID_TRAP_COUNTS, BOARD_SIZE, BOARD_ROWS, BOARD_COLS
from utils.helpers import (
    survival_probability, incremental_survival, shannon_entropy,
    format_percent, format_odds, combinations,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class ResearchMode:
    """
    Transparent educational explorer for all internal engine systems.
    """

    def __init__(self, console, prob_engine, pf_engine, mc_engine, rng_analyser):
        self.console = console
        self.prob    = prob_engine
        self.pf      = pf_engine
        self.mc      = mc_engine
        self.rng     = rng_analyser

    # ==================================================================
    # RESEARCH MENU
    # ==================================================================

    def run_research_menu(self) -> None:
        """Research mode navigation."""
        while True:
            self.console.clear()
            self._header("🔭  RESEARCH MODE")
            self.console.print(
                "[dim]Full transparency into all internal calculations.\n"
                "This mode is educational — no claims about prediction are made.[/dim]\n"
            )

            options = {
                "1": "Probability tables (all trap counts)",
                "2": "Survival curve explorer",
                "3": "Provably fair cryptography walkthrough",
                "4": "Fisher-Yates shuffle demonstration",
                "5": "Monte Carlo internals",
                "6": "Shannon entropy calculator",
                "7": "Expected value deep-dive",
                "8": "Seed processing visualiser",
                "B": "Back",
            }

            for k, v in options.items():
                key_col = "bold magenta" if k not in ("B",) else "dim"
                self.console.print(f"  [{key_col}][{k}][/{key_col}]  {v}")

            self.console.print()
            raw = Prompt.ask("  Choice").strip().upper()

            if raw == "B":
                return
            elif raw == "1":
                self._probability_tables()
            elif raw == "2":
                self._survival_curve_explorer()
            elif raw == "3":
                self._pf_cryptography_walkthrough()
            elif raw == "4":
                self._fisher_yates_demo()
            elif raw == "5":
                self._monte_carlo_internals()
            elif raw == "6":
                self._entropy_calculator()
            elif raw == "7":
                self._ev_deep_dive()
            elif raw == "8":
                self._seed_processing_visualiser()

    # ==================================================================
    # PROBABILITY TABLES
    # ==================================================================

    def _probability_tables(self) -> None:
        """Show full probability tables for all trap counts."""
        self.console.clear()
        self._header("PROBABILITY TABLES")

        self.console.print(
            "[dim]P(survive N picks) = C(safe_cells, N) / C(total_cells, N)\n"
            "where safe_cells = total_cells - traps\n[/dim]"
        )

        for tc in VALID_TRAP_COUNTS:
            safe   = BOARD_SIZE - tc
            col    = self._trap_colour(tc)
            self.console.print(f"\n[{col}]── {tc} TRAP{'S' if tc > 1 else ''} ({safe} safe cells) ──[/{col}]")

            table = Table(
                box          = box.SIMPLE,
                show_header  = True,
                header_style = f"bold {col}",
                border_style = f"{col} dim",
                padding      = (0, 1),
            )
            table.add_column("Picks",         width=6,  justify="right")
            table.add_column("C(safe,picks)", width=14, justify="right")
            table.add_column("C(25,picks)",   width=14, justify="right")
            table.add_column("Survival %",    width=12, justify="right")
            table.add_column("Odds",          width=16)
            table.add_column("Next pick %",   width=12, justify="right")

            for picks in range(min(safe + 1, 16)):
                surv      = survival_probability(BOARD_SIZE, tc, picks)
                numer     = combinations(safe, picks)
                denom     = combinations(BOARD_SIZE, picks)
                next_surv = incremental_survival(BOARD_SIZE, tc, picks)
                odds      = format_odds(next_surv)

                from utils.helpers import colour_for_probability
                s_col = colour_for_probability(surv)
                n_col = colour_for_probability(next_surv)

                table.add_row(
                    str(picks),
                    f"{numer:,}",
                    f"{denom:,}",
                    f"[{s_col}]{surv*100:6.2f}%[/{s_col}]",
                    f"[dim]{odds}[/dim]",
                    f"[{n_col}]{next_surv*100:6.2f}%[/{n_col}]",
                )

            self.console.print(table)

        input("\n  [dim]Press Enter...[/dim]")

    # ==================================================================
    # SURVIVAL CURVE EXPLORER
    # ==================================================================

    def _survival_curve_explorer(self) -> None:
        """Interactive survival curve for any trap count."""
        self.console.clear()
        self._header("SURVIVAL CURVE EXPLORER")

        tc = self._pick_trap_count()
        curve = self.prob.survival_curve(tc)

        from ui.heatmap import HeatmapRenderer
        hm = HeatmapRenderer(self.console)
        hm.render_survival_curve(curve, tc)

        # Print EV table
        self.console.print("\n[bold cyan]EXPECTED VALUE TABLE[/bold cyan]")
        self.console.print("[dim]EV of continuing one more pick from each depth[/dim]\n")

        table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan", padding=(0, 1))
        table.add_column("Depth", width=7, justify="right")
        table.add_column("Survival", width=10, justify="right")
        table.add_column("Multiplier", width=11, justify="right")
        table.add_column("EV (continue)", width=14, justify="right")
        table.add_column("Recommendation", width=18)

        for d in curve:
            ev     = d["ev"]
            s      = d["survival"]
            from utils.helpers import colour_for_probability
            ev_col = "green" if ev >= 0 else "red"
            s_col  = colour_for_probability(s)
            rec    = "[green]CONTINUE[/green]" if ev >= 0 else "[red]STOP[/red]"

            table.add_row(
                str(d["picks"]),
                f"[{s_col}]{s*100:.2f}%[/{s_col}]",
                f"×{d['mult']:.4f}",
                f"[{ev_col}]{ev:+.4f}[/{ev_col}]",
                rec,
            )

        self.console.print(table)
        input("\n  [dim]Press Enter...[/dim]")

    # ==================================================================
    # PROVABLY FAIR CRYPTOGRAPHY WALKTHROUGH
    # ==================================================================

    def _pf_cryptography_walkthrough(self) -> None:
        """Step-by-step walkthrough of provably fair cryptography."""
        self.console.clear()
        self._header("PROVABLY FAIR CRYPTOGRAPHY WALKTHROUGH")

        self.console.print(
            "[dim]This walkthrough explains how provably fair Mines games work\n"
            "at a cryptographic level. You can use real seeds or generated examples.[/dim]\n"
        )

        use_example = Confirm.ask("  Use auto-generated example seeds?", default=True)

        if use_example:
            import secrets
            server_seed = secrets.token_hex(32)
            client_seed = secrets.token_hex(16)
            nonce       = 1
        else:
            server_seed = Prompt.ask("  Server seed").strip()
            client_seed = Prompt.ask("  Client seed").strip()
            nonce       = int(Prompt.ask("  Nonce", default="1"))

        tc = self._pick_trap_count()

        self.console.print(f"\n  [dim]Server seed:[/dim]  {server_seed}")
        self.console.print(f"  [dim]Client seed:[/dim]  {client_seed}")
        self.console.print(f"  [dim]Nonce:      [/dim]  {nonce}")
        self.console.print(f"  [dim]Trap count: [/dim]  {tc}\n")

        steps = self.pf.get_verification_steps(server_seed, client_seed, nonce)
        self.render_verification_steps(steps)

        # Show derived mines
        mines = self.pf.derive_mine_positions(server_seed, client_seed, nonce, tc)
        self.console.print(
            f"\n  [bold green]Derived mine positions:[/bold green]  {mines}\n"
            f"  [dim](These are the mine cell indices 0–24 for this seed combination)[/dim]\n"
        )

        # Entropy of the server seed
        report = self.rng.analyse_seed(server_seed)
        self.console.print(f"  Server seed entropy: [bold]{report.raw_entropy:.4f}[/bold] bits/byte  [{report.quality_label}]")

        input("\n  [dim]Press Enter...[/dim]")

    def render_verification_steps(self, steps: List[Dict]) -> None:
        """Render step-by-step verification breakdown (shared with verifier menu)."""
        for step in steps:
            self.console.print(f"\n  [bold cyan]Step {step['step']}: {step['title']}[/bold cyan]")
            self.console.print(f"  [dim]Formula:[/dim] [yellow]{step['formula']}[/yellow]")
            self.console.print(f"  [dim]Input:  [/dim] {step['input'][:60]}{'...' if len(str(step['input'])) > 60 else ''}")
            self.console.print(f"  [dim]Output: [/dim] [green]{str(step['output'])[:60]}{'...' if len(str(step['output'])) > 60 else ''}[/green]")
            self.console.print(f"  [dim]{step['explain']}[/dim]")
            time.sleep(0.1)

    # ==================================================================
    # FISHER-YATES SHUFFLE DEMO
    # ==================================================================

    def _fisher_yates_demo(self) -> None:
        """Demonstrate the Fisher-Yates shuffle used for board generation."""
        self.console.clear()
        self._header("FISHER-YATES SHUFFLE DEMONSTRATION")

        self.console.print(
            "[dim]The Fisher-Yates shuffle transforms hash bytes into a\n"
            "deterministic permutation of board positions [0..24].\n"
            "The first N positions after shuffling become mine locations.[/dim]\n"
        )

        import random, secrets
        seed_hex = secrets.token_hex(4)
        random.seed(int(seed_hex, 16))

        positions = list(range(BOARD_SIZE))
        self.console.print(f"  Initial positions: {positions}\n")
        self.console.print(f"  [dim]Seed used for demo: {seed_hex}[/dim]\n")

        # Step through the shuffle visually
        for i in range(BOARD_SIZE - 1, max(BOARD_SIZE - 8, 0), -1):
            j = random.randint(0, i)
            positions[i], positions[j] = positions[j], positions[i]
            self.console.print(
                f"  i={i:2d}  j={j:2d}  swap → "
                f"[dim]{positions[:6]}...[/dim]  "
                f"[cyan](swapped pos[{i}] ↔ pos[{j}])[/cyan]"
            )
            time.sleep(0.08)

        self.console.print(f"\n  [dim]...(continuing for all 25 positions)[/dim]")
        for i in range(max(BOARD_SIZE - 8, 0), 0, -1):
            j = random.randint(0, i)
            positions[i], positions[j] = positions[j], positions[i]

        self.console.print(f"\n  Final permutation: {positions}")

        for tc in VALID_TRAP_COUNTS:
            mines = sorted(positions[:tc])
            col   = self._trap_colour(tc)
            self.console.print(f"  [{col}]{tc} trap mines → {mines}[/{col}]")

        input("\n  [dim]Press Enter...[/dim]")

    # ==================================================================
    # MONTE CARLO INTERNALS
    # ==================================================================

    def _monte_carlo_internals(self) -> None:
        """Expose Monte Carlo simulation internals."""
        self.console.clear()
        self._header("MONTE CARLO INTERNALS")

        self.console.print(
            "[dim]Monte Carlo estimation works by running thousands of randomised\n"
            "trial rounds and recording outcomes. The law of large numbers ensures\n"
            "estimates converge toward true probabilities as iterations increase.\n[/dim]"
        )

        self.console.print("\n[bold cyan]Convergence demonstration:[/bold cyan]")
        self.console.print("[dim]Running 'random' strategy on 3-trap board at 100, 1000, 10000 iterations...[/dim]\n")

        for iters in [100, 1000, 10000]:
            result = self.mc.run(
                strategy     = "random",
                trap_count   = 3,
                iterations   = iters,
                risk_profile = "BALANCED",
            )
            # Theoretical win rate for BALANCED (60% of 22 safe cells = ~13 picks)
            # is computed from survival_probability
            theoretical = survival_probability(BOARD_SIZE, 3, int(0.6 * 22))
            diff = abs(result.win_rate - theoretical)
            self.console.print(
                f"  n={iters:>6,}  win_rate={result.win_rate:.4f}  "
                f"theoretical≈{theoretical:.4f}  "
                f"delta=[{'green' if diff < 0.05 else 'yellow'}]{diff:.4f}[/{'green' if diff < 0.05 else 'yellow'}]"
            )

        self.console.print(
            "\n  [dim]As n increases, empirical win rate converges toward theoretical survival probability.\n"
            "  This is the Central Limit Theorem in action.[/dim]"
        )

        input("\n  [dim]Press Enter...[/dim]")

    # ==================================================================
    # SHANNON ENTROPY CALCULATOR
    # ==================================================================

    def _entropy_calculator(self) -> None:
        """Interactive Shannon entropy calculator."""
        self.console.clear()
        self._header("SHANNON ENTROPY CALCULATOR")

        self.console.print(
            "[dim]Shannon entropy measures information density / unpredictability.\n"
            "Formula: H = -Σ p_i × log₂(p_i)\n"
            "Maximum for byte data: 8 bits/byte (256 equally likely values).\n[/dim]\n"
        )

        seed = Prompt.ask("  Enter a string or hex seed to analyse").strip()
        report = self.rng.analyse_seed(seed)

        self.console.print(f"\n  [bold]Entropy:[/bold]  {report.raw_entropy:.6f} bits/byte")
        self.console.print(f"  [bold]Max:    [/bold]  8.000000 bits/byte")
        self.console.print(f"  [bold]Quality:[/bold]  {report.quality_label}")
        self.console.print(f"  [bold]Norm:   [/bold]  {report.normalised:.4f}  ({report.normalised:.1%} of maximum)")

        # Byte frequency table (top 10)
        self.console.print("\n  [dim]Top byte frequencies:[/dim]")
        items = sorted(report.byte_distribution.items(), key=lambda x: -x[1])[:10]
        for byte_label, freq in items:
            from utils.helpers import progress_bar
            bar = progress_bar(freq, 20)
            self.console.print(f"    [dim]{byte_label}[/dim]  [cyan]{bar}[/cyan]  {freq:.4f}")

        if report.anomalies:
            self.console.print("\n  [bold yellow]Anomalies:[/bold yellow]")
            for a in report.anomalies:
                self.console.print(f"    [yellow]• {a}[/yellow]")

        self.console.print(f"\n  [dim]{report.recommendation}[/dim]")
        input("\n  [dim]Press Enter...[/dim]")

    # ==================================================================
    # EXPECTED VALUE DEEP DIVE
    # ==================================================================

    def _ev_deep_dive(self) -> None:
        """Detailed expected value analysis for all configurations."""
        self.console.clear()
        self._header("EXPECTED VALUE DEEP DIVE")

        self.console.print(
            "[dim]EV = P(safe) × payout_multiplier × stake − P(mine) × stake\n"
            "Positive EV = continuing is mathematically better than stopping.\n"
            "Negative EV = stopping is mathematically better than continuing.\n\n"
            "NOTE: EV is a long-run average. Any single round can deviate wildly.[/dim]\n"
        )

        from engine.probability_engine import ProbabilityEngine
        pe = ProbabilityEngine()

        for tc in VALID_TRAP_COUNTS:
            col   = self._trap_colour(tc)
            curve = pe.survival_curve(tc)

            self.console.print(f"\n[{col}]── {tc} TRAP{'S' if tc > 1 else ''} EV TABLE ──[/{col}]")

            table = Table(box=box.SIMPLE, show_header=True, header_style=f"bold {col}", padding=(0, 1))
            table.add_column("Picks", width=6, justify="right")
            table.add_column("P(next safe)", width=13, justify="right")
            table.add_column("Mult ×", width=9, justify="right")
            table.add_column("EV", width=10, justify="right")
            table.add_column("Decision", width=14)

            for d in curve[:12]:
                ev      = d["ev"]
                s       = d["survival"]
                ns      = incremental_survival(BOARD_SIZE, tc, d["picks"])
                ev_col  = "green" if ev >= 0 else "red"
                dec     = "[green]▶ CONTINUE[/green]" if ev >= 0 else "[red]■ STOP[/red]"

                table.add_row(
                    str(d["picks"]),
                    f"{ns*100:.2f}%",
                    f"{d['mult']:.4f}",
                    f"[{ev_col}]{ev:+.4f}[/{ev_col}]",
                    dec,
                )

            self.console.print(table)

        input("\n  [dim]Press Enter...[/dim]")

    # ==================================================================
    # SEED PROCESSING VISUALISER
    # ==================================================================

    def _seed_processing_visualiser(self) -> None:
        """Show how seeds are processed into board positions, step by step."""
        self.console.clear()
        self._header("SEED PROCESSING VISUALISER")

        import secrets as sec
        server_seed = sec.token_hex(32)
        client_seed = sec.token_hex(16)
        nonce       = 1
        tc          = 3

        self.console.print(f"  [dim]Generated example seeds:[/dim]")
        self.console.print(f"  server_seed = [green]{server_seed}[/green]")
        self.console.print(f"  client_seed = [cyan]{client_seed}[/cyan]")
        self.console.print(f"  nonce       = {nonce}")
        self.console.print(f"  trap_count  = {tc}\n")
        time.sleep(0.3)

        # Step 1: SHA256 of server seed
        seed_hash = self.pf.sha256(server_seed)
        self.console.print(f"  [bold]Step 1:[/bold] SHA256(server_seed)")
        self.console.print(f"    → [yellow]{seed_hash}[/yellow]")
        self.console.print(f"  [dim]This is published before the game as proof of commitment.[/dim]\n")
        time.sleep(0.2)

        # Step 2: HMAC message
        message = f"{client_seed}:{nonce}"
        self.console.print(f"  [bold]Step 2:[/bold] Build HMAC message")
        self.console.print(f"    message = '{message}'")
        self.console.print(f"  [dim]Client seed and nonce are combined.[/dim]\n")
        time.sleep(0.2)

        # Step 3: HMAC-SHA256
        combined = self.pf.hmac_sha256(server_seed, message)
        self.console.print(f"  [bold]Step 3:[/bold] HMAC-SHA256(key=server_seed, message)")
        self.console.print(f"    → [green]{combined}[/green]")
        self.console.print(f"  [dim]64 hex characters = 256 bits of randomness.[/dim]\n")
        time.sleep(0.2)

        # Step 4: Bytes
        raw_bytes = bytes.fromhex(combined)
        self.console.print(f"  [bold]Step 4:[/bold] Decode to bytes")
        self.console.print(f"    First 8 bytes: {list(raw_bytes[:8])}")
        self.console.print(f"  [dim]Each 4-byte chunk becomes one float in [0,1).[/dim]\n")
        time.sleep(0.2)

        # Step 5: Mines
        mines = self.pf.derive_mine_positions(server_seed, client_seed, nonce, tc)
        self.console.print(f"  [bold]Step 5:[/bold] Fisher-Yates shuffle → mine positions")
        self.console.print(f"    → [bold red]{mines}[/bold red]")
        self.console.print(f"  [dim]First {tc} positions after shuffle = mine locations.[/dim]\n")

        # Visual board
        self.console.print("  [bold]Result board:[/bold]")
        for row in range(BOARD_ROWS):
            row_str = "    "
            for col in range(BOARD_COLS):
                idx = row * BOARD_COLS + col
                if idx in mines:
                    row_str += "[bold red] * [/bold red]"
                else:
                    row_str += "[dim] · [/dim]"
            self.console.print(row_str)

        self.console.print(f"\n  [dim]* = mine position  · = safe cell[/dim]")
        input("\n  [dim]Press Enter...[/dim]")

    # ==================================================================
    # HELPERS
    # ==================================================================

    def _header(self, title: str) -> None:
        self.console.print(
            Panel(
                f"[bold magenta]{title}[/bold magenta]",
                border_style="magenta dim",
                padding=(0, 2),
            )
        )

    def _pick_trap_count(self) -> int:
        self.console.print(
            f"  Trap count [{'/'.join(str(t) for t in VALID_TRAP_COUNTS)}]: ",
            end=""
        )
        while True:
            raw = input().strip()
            if raw.isdigit() and int(raw) in VALID_TRAP_COUNTS:
                return int(raw)
            self.console.print("  [red]Invalid.[/red] ", end="")

    @staticmethod
    def _trap_colour(tc: int) -> str:
        return {1: "green", 3: "yellow", 5: "orange1", 7: "red"}.get(tc, "white")
