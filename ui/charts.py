"""
ui/charts.py — ASCII chart rendering for terminal visualisation.

Renders statistical charts directly in the terminal including:
  - Bar charts (strategy comparison, depth distribution)
  - Entropy quality indicators
  - Risk appetite gauges
  - Distribution histograms
"""

from typing import List, Dict, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box

from utils.helpers import format_percent, colour_for_probability, colour_for_risk, progress_bar
from utils.logger import get_logger

logger = get_logger(__name__)


class ChartRenderer:
    """
    Renders ASCII charts and visual indicators to the terminal.
    """

    def __init__(self, console: Console):
        self.console = console

    # ------------------------------------------------------------------
    # Horizontal bar chart
    # ------------------------------------------------------------------

    def render_bar_chart(
        self,
        data:      List[Tuple[str, float]],
        title:     str       = "BAR CHART",
        max_val:   float     = 1.0,
        width:     int       = 30,
        colour_fn: callable  = None,
        unit:      str       = "",
    ) -> None:
        """
        Render a horizontal bar chart.

        Args:
            data:     List of (label, value) tuples
            title:    Chart title
            max_val:  Value that corresponds to full bar width
            width:    Maximum bar width in characters
            colour_fn: Optional function(value) → colour string
            unit:     Unit suffix for value display (e.g. "%")
        """
        if not data:
            return

        if colour_fn is None:
            colour_fn = lambda v: colour_for_probability(v / max_val)

        max_label = max(len(label) for label, _ in data)

        self.console.print(f"\n[bold cyan]{title}[/bold cyan]")
        self.console.print("[dim]" + "─" * (max_label + width + 15) + "[/dim]")

        for label, value in data:
            bar_width   = int((value / max_val) * width) if max_val > 0 else 0
            bar_width   = min(bar_width, width)
            colour      = colour_fn(value)
            bar         = "█" * bar_width
            empty       = "░" * (width - bar_width)
            val_str     = f"{value:.3f}{unit}" if isinstance(value, float) else f"{value}{unit}"

            self.console.print(
                f"  [{colour}]{label:<{max_label}}[/{colour}]  "
                f"[{colour}]{bar}[/{colour}][dim]{empty}[/dim]  "
                f"[dim]{val_str}[/dim]"
            )

        self.console.print()

    # ------------------------------------------------------------------
    # Depth distribution histogram
    # ------------------------------------------------------------------

    def render_depth_histogram(
        self,
        depths:     List[int],
        max_depth:  int,
        title:      str = "SURVIVAL DEPTH DISTRIBUTION",
        width:      int = 30,
    ) -> None:
        """
        Render a histogram of survival depths from simulation results.

        Args:
            depths:    List of pick depths from simulation
            max_depth: Maximum possible depth (for x-axis)
            title:     Chart title
            width:     Bar width in characters
        """
        if not depths:
            return

        from collections import Counter
        freq  = Counter(depths)
        total = len(depths)
        max_f = max(freq.values()) if freq else 1

        self.console.print(f"\n[bold magenta]{title}[/bold magenta]")
        self.console.print(f"[dim]n={total} simulated rounds[/dim]\n")

        for depth in range(0, max_depth + 1):
            count  = freq.get(depth, 0)
            pct    = count / total
            bw     = int((count / max_f) * width)
            colour = colour_for_probability(depth / max_depth) if max_depth > 0 else "white"
            bar    = "█" * bw
            empty  = "░" * (width - bw)

            self.console.print(
                f"  [dim]{depth:2d} picks[/dim]  "
                f"[{colour}]{bar}[/{colour}][dim]{empty}[/dim]  "
                f"[dim]{count:5d}  ({pct:.1%})[/dim]"
            )

        self.console.print()

    # ------------------------------------------------------------------
    # Entropy quality gauge
    # ------------------------------------------------------------------

    def render_entropy_gauge(
        self,
        entropy:       float,
        normalised:    float,
        quality_label: str,
        seed_preview:  str = "",
    ) -> None:
        """
        Render a visual entropy quality gauge.

        Args:
            entropy:       Raw entropy value (bits per byte)
            normalised:    Entropy as fraction of max (0-1)
            quality_label: "EXCELLENT" / "GOOD" / "WEAK" / "POOR"
            seed_preview:  First few chars of seed for display
        """
        qual_colours = {
            "EXCELLENT": "bold green",
            "GOOD":      "green",
            "WEAK":      "yellow",
            "POOR":      "bold red",
        }
        colour = qual_colours.get(quality_label, "white")
        bar    = progress_bar(normalised, width=24)

        self.console.print(f"\n[bold cyan]ENTROPY ANALYSIS[/bold cyan]")
        if seed_preview:
            self.console.print(f"  Seed: [dim]{seed_preview}...[/dim]")
        self.console.print(f"  Raw Entropy:  [bold]{entropy:.4f}[/bold] bits/byte  (max 8.0)")
        self.console.print(
            f"  Quality:      [{colour}]{quality_label}[/{colour}]  "
            f"[{colour}]{bar}[/{colour}]  [{colour}]{normalised:.0%}[/{colour}]"
        )
        self.console.print()

    # ------------------------------------------------------------------
    # Risk appetite gauge
    # ------------------------------------------------------------------

    def render_appetite_gauge(
        self,
        declared:    str,
        revealed:    float,
        alignment:   str,
    ) -> None:
        """
        Render a visual comparison of declared vs revealed risk appetite.

        Args:
            declared:   Declared profile name (e.g. "BALANCED")
            revealed:   Revealed appetite score (0-100)
            alignment:  "ALIGNED" / "AGGRESSIVE_BIAS" / "CONSERVATIVE_BIAS"
        """
        from utils.config import RISK_PROFILES, TRAP_PROFILES

        # Profile position on 0-100 scale
        profile_positions = {
            "CONSERVATIVE": 17,
            "BALANCED":     50,
            "AGGRESSIVE":   72,
            "ALL_IN":       92,
        }
        declared_pos = profile_positions.get(declared, 50)
        revealed_pos = int(min(100, max(0, revealed)))

        scale_width = 40
        declared_x  = int(declared_pos / 100 * scale_width)
        revealed_x  = int(revealed_pos / 100 * scale_width)

        # Build the scale line
        scale = [" "] * scale_width
        if 0 <= declared_x < scale_width:
            scale[declared_x] = "D"
        if 0 <= revealed_x < scale_width:
            if revealed_x == declared_x:
                scale[revealed_x] = "B"  # Both at same position
            else:
                scale[revealed_x] = "R"

        scale_str = "".join(scale)

        # Colour coding
        align_col = {"ALIGNED": "green", "AGGRESSIVE_BIAS": "yellow", "CONSERVATIVE_BIAS": "cyan"}.get(alignment, "white")

        self.console.print(f"\n[bold blue]RISK APPETITE PROFILE[/bold blue]")
        self.console.print(f"  [dim]CONS  ──────────── BALANCED ────────────  ALIN[/dim]")
        self.console.print(f"  [dim]│[/dim]{scale_str}[dim]│[/dim]")
        self.console.print(f"  [dim]D = Declared ({declared_pos}/100)  R = Revealed ({revealed_pos}/100)[/dim]")
        self.console.print(f"  Alignment: [{align_col}]{alignment}[/{align_col}]")
        self.console.print()

    # ------------------------------------------------------------------
    # Strategy comparison table
    # ------------------------------------------------------------------

    def render_strategy_comparison(self, results: List, trap_count: int) -> None:
        """
        Render a quick strategy comparison bar chart from simulation results.
        """
        if not results:
            return

        self.console.print(
            f"\n[bold magenta]STRATEGY WIN RATES — {trap_count} TRAP{'S' if trap_count > 1 else ''}[/bold magenta]"
        )

        max_wr = max(r.win_rate for r in results) if results else 1.0
        data   = [(r.strategy.replace("_", " ").title(), r.win_rate) for r in results]

        self.render_bar_chart(
            data      = data,
            title     = "",
            max_val   = max(max_wr, 0.001),
            width     = 28,
            colour_fn = colour_for_probability,
            unit      = "",
        )

    # ------------------------------------------------------------------
    # Nonce sequence chart
    # ------------------------------------------------------------------

    def render_nonce_history(self, nonces: List[int], seed_preview: str) -> None:
        """Visualise nonce usage history to detect anomalies."""
        if not nonces:
            self.console.print("[dim]No nonce history for this seed.[/dim]")
            return

        self.console.print(f"\n[bold cyan]NONCE HISTORY[/bold cyan]  [dim]{seed_preview}...[/dim]")

        prev = None
        for n in nonces:
            if prev is not None and n != prev + 1:
                gap_col = "red" if n < prev else "yellow"
                gap_str = f"  [{gap_col}]← gap! (expected {prev+1}, got {n})[/{gap_col}]"
            else:
                gap_str = ""

            self.console.print(f"  [dim]Nonce[/dim] [bold]{n}[/bold]{gap_str}")
            prev = n

        self.console.print()
