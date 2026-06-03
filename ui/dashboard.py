"""
ui/dashboard.py — Session statistics dashboard and live metrics panel.

Renders side-panel dashboards showing real-time game state,
probability metrics, behavioral scores, and session summaries.
"""

from typing import Optional, List, Dict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.rule import Rule
from rich import box

from utils.helpers import (
    format_percent, format_odds, progress_bar,
    colour_for_probability, colour_for_risk,
)
from utils.config import RISK_PROFILES, TRAP_PROFILES
from utils.logger import get_logger

logger = get_logger(__name__)


class Dashboard:
    """
    Renders statistics panels and dashboards to the terminal.
    """

    def __init__(self, console: Console):
        self.console = console

    # ------------------------------------------------------------------
    # Live game stats panel
    # ------------------------------------------------------------------

    def render_game_stats(
        self,
        trap_count:        int,
        picks_made:        int,
        next_survival:     float,
        cumulative_surv:   float,
        risk_score:        float,
        risk_profile:      str,
        recommended_stop:  int,
        session_ev:        float,
        mode:              str = "SIMULATION",
    ) -> None:
        """
        Render the live game statistics panel shown during active play.
        """
        safe_cells  = 25 - trap_count
        progress    = picks_made / safe_cells if safe_cells > 0 else 0

        # Colour coding
        surv_col    = colour_for_probability(next_survival)
        risk_col    = colour_for_risk(risk_score)
        ev_col      = "green" if session_ev >= 0 else "red"
        profile_col = RISK_PROFILES.get(risk_profile, {}).get("color", "white")

        # Progress bar
        bar = progress_bar(progress, width=18)
        bar_col = colour_for_probability(cumulative_surv)

        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), border_style="cyan dim")
        table.add_column("Metric", style="dim cyan", width=22)
        table.add_column("Value",  width=24)

        rows = [
            ("Trap Configuration",  f"[bold]{trap_count} TRAP{'S' if trap_count > 1 else ''}[/bold]"),
            ("Risk Profile",        f"[{profile_col}]{risk_profile}[/{profile_col}]"),
            ("Mode",                f"[dim]{'🔒 DETERMINISTIC' if mode == 'DETERMINISTIC' else '〜 SIMULATION'}[/dim]"),
            ("─" * 22,             "─" * 24),
            ("Picks Made",          f"[bold]{picks_made}[/bold] / {safe_cells} safe cells"),
            ("Depth Progress",      f"[{bar_col}]{bar}[/{bar_col}] {progress:.0%}"),
            ("─" * 22,             "─" * 24),
            ("Next Pick Survival",  f"[{surv_col}]{format_percent(next_survival)}[/{surv_col}]  ({format_odds(next_survival)})"),
            ("Cumulative Survival", f"[{surv_col}]{format_percent(cumulative_surv)}[/{surv_col}]"),
            ("Risk Score",          f"[{risk_col}]{risk_score:.2f}[/{risk_col}]  [{risk_col}]{progress_bar(risk_score, 8)}[/{risk_col}]"),
            ("─" * 22,             "─" * 24),
            ("Recommended Stop",    f"[bold]{recommended_stop}[/bold] picks"),
            ("EV of Continuing",    f"[{ev_col}]{session_ev:+.4f}[/{ev_col}]"),
        ]

        for label, value in rows:
            table.add_row(label, value)

        self.console.print(
            Panel(
                table,
                title    = "[bold cyan]LIVE GAME METRICS[/bold cyan]",
                subtitle = f"[dim]round in progress[/dim]",
                border_style = "cyan",
                padding  = (1, 1),
            )
        )

    # ------------------------------------------------------------------
    # Continue vs Cash-out comparison
    # ------------------------------------------------------------------

    def render_decision_panel(self, comparison: Dict) -> None:
        """
        Render the continue vs cash-out decision comparison panel.
        """
        cashout_ev   = comparison.get("cashout_ev", 0)
        continue_ev  = comparison.get("continue_ev", 0)
        next_surv    = comparison.get("next_survival", 0)
        recommendation = comparison.get("recommendation", "—")
        edge         = comparison.get("ev_edge", 0)

        rec_col = "green" if recommendation == "CASH OUT" else "yellow"
        surv_col = colour_for_probability(next_surv)

        table = Table(box=box.MINIMAL, show_header=False, padding=(0, 1), border_style="yellow dim")
        table.add_column("Option", style="bold", width=16)
        table.add_column("EV",     justify="right", width=10)
        table.add_column("Notes",  width=20)

        table.add_row(
            "[green]CASH OUT[/green]",
            f"[green]{cashout_ev:+.4f}[/green]",
            "Lock in current gain",
        )
        table.add_row(
            "[yellow]CONTINUE[/yellow]",
            f"[yellow]{continue_ev:+.4f}[/yellow]",
            f"Next survival: [{surv_col}]{format_percent(next_surv)}[/{surv_col}]",
        )

        self.console.print(
            Panel(
                table,
                title    = f"[bold yellow]DECISION ANALYSIS[/bold yellow]",
                subtitle = f"[{rec_col}]Recommendation: {recommendation}  (EV edge: {edge:.4f})[/{rec_col}]",
                border_style = "yellow",
            )
        )

    # ------------------------------------------------------------------
    # Session summary
    # ------------------------------------------------------------------

    def render_session_summary(self, stats: Dict, behavioral_profile=None) -> None:
        """
        Render a full session summary panel at the end of a session
        or when requested from the main menu.
        """
        self.console.print(Rule("[bold cyan]SESSION SUMMARY[/bold cyan]", style="cyan"))

        if not stats:
            self.console.print("[dim]No rounds played this session.[/dim]")
            return

        total  = stats.get("total_rounds", 0)
        wins   = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        win_rate = stats.get("win_rate", 0)
        avg_surv = stats.get("avg_survival", 0)
        max_surv = stats.get("max_survival", 0)

        win_col = colour_for_probability(win_rate)

        table = Table(box=box.ROUNDED, show_header=False, border_style="cyan dim", padding=(0, 2))
        table.add_column("Metric", style="cyan dim", width=26)
        table.add_column("Value",  width=20)

        table.add_row("Total Rounds",          str(total))
        table.add_row("Cash-outs (wins)",       f"[green]{wins}[/green]")
        table.add_row("Mine hits (losses)",     f"[red]{losses}[/red]")
        table.add_row("Win Rate",               f"[{win_col}]{format_percent(win_rate)}[/{win_col}]")
        table.add_row("Avg Survival Depth",     f"{avg_surv:.2f} picks")
        table.add_row("Max Survival Depth",     f"{max_surv} picks")

        self.console.print(table)

        if behavioral_profile:
            self._render_behavioral_summary(behavioral_profile)

    # ------------------------------------------------------------------
    # Simulation results table
    # ------------------------------------------------------------------

    def render_simulation_results(self, results: List) -> None:
        """
        Render a comparison table of Monte Carlo simulation results.
        """
        self.console.print(Rule("[bold magenta]SIMULATION RESULTS[/bold magenta]", style="magenta"))

        table = Table(
            box          = box.ROUNDED,
            show_header  = True,
            header_style = "bold magenta",
            border_style = "magenta dim",
            padding      = (0, 1),
        )

        table.add_column("Rank",      width=5,  justify="center")
        table.add_column("Strategy",  width=16)
        table.add_column("Win Rate",  width=10, justify="right")
        table.add_column("Avg Depth", width=10, justify="right")
        table.add_column("Std Dev",   width=8,  justify="right")
        table.add_column("Bust Rate", width=10, justify="right")
        table.add_column("Time(ms)",  width=9,  justify="right")

        for rank, r in enumerate(results, 1):
            wr_col   = colour_for_probability(r.win_rate)
            bust_col = colour_for_risk(r.bust_rate)
            table.add_row(
                f"#{rank}",
                r.strategy.replace("_", " ").title(),
                f"[{wr_col}]{format_percent(r.win_rate)}[/{wr_col}]",
                f"{r.avg_depth:.2f}",
                f"{r.std_dev:.2f}",
                f"[{bust_col}]{format_percent(r.bust_rate)}[/{bust_col}]",
                f"{r.run_time_ms:.0f}",
            )

        self.console.print(table)
        self.console.print(
            "[dim]Win rate = rounds reaching target depth. Bust rate = mine hits.[/dim]\n"
        )

    # ------------------------------------------------------------------
    # Provably fair verification report
    # ------------------------------------------------------------------

    def render_verification_report(self, report: Dict) -> None:
        """Display the result of a provably fair verification."""
        self.console.print(Rule("[bold green]VERIFICATION REPORT[/bold green]", style="green"))

        verified = report.get("fully_verified", False)
        status_col = "bold green" if verified else "bold red"
        status_str = "✓ VERIFIED" if verified else "✗ VERIFICATION FAILED"

        self.console.print(f"\n  [{status_col}]{status_str}[/{status_col}]\n")

        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("Field",  style="dim green", width=22)
        table.add_column("Value",  width=50)

        table.add_row("Seed Hash Verified",  "✓ YES" if report.get("seed_verified") else "✗ NO")
        table.add_row("Board Match",         "✓ YES" if report.get("board_matches")  else "✗ NO")
        table.add_row("Server Seed",         report.get("server_seed", "—")[:32] + "...")
        table.add_row("Published Hash",      report.get("published_hash", "—")[:32] + "...")
        table.add_row("Computed Hash",       report.get("computed_hash",  "—")[:32] + "...")
        table.add_row("Client Seed",         report.get("client_seed", "—"))
        table.add_row("Nonce",               str(report.get("nonce", "—")))
        table.add_row("Derived Mines",       str(report.get("derived_mines", [])))
        table.add_row("Claimed Mines",       str(report.get("claimed_mines", [])))

        self.console.print(table)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _render_behavioral_summary(self, profile) -> None:
        """Render the behavioral profile summary block."""
        self.console.print(Rule("[bold blue]BEHAVIORAL ANALYSIS[/bold blue]", style="blue"))

        appetite   = profile.revealed_appetite
        alignment  = profile.profile_alignment
        declared   = profile.declared_profile

        app_col    = "green" if appetite < 40 else ("yellow" if appetite < 70 else "red")
        align_col  = "green" if alignment == "ALIGNED" else "yellow"

        self.console.print(f"  Declared Profile:   [bold]{declared}[/bold]")
        self.console.print(f"  Revealed Appetite:  [{app_col}]{appetite:.0f}/100[/{app_col}]  [{app_col}]{progress_bar(appetite/100, 20)}[/{app_col}]")
        self.console.print(f"  Profile Alignment:  [{align_col}]{alignment}[/{align_col}]")

        if profile.observations:
            self.console.print("\n  [dim cyan]Observations:[/dim cyan]")
            for obs in profile.observations:
                self.console.print(f"    [dim]• {obs}[/dim]")

        self.console.print()
