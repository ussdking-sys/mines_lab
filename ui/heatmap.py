"""
ui/heatmap.py — Terminal probability and entropy heatmap rendering.

Renders colour-gradient heatmaps directly in the terminal using
ANSI colour blocks. No external graphics libraries required.
"""

from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from utils.config import BOARD_ROWS, BOARD_COLS, BOARD_SIZE
from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Colour gradient: cool (safe/low) → hot (dangerous/high)
# Maps a value 0-1 to a Rich colour string
# ---------------------------------------------------------------------------
GRADIENT_STEPS = [
    (0.00, "bright_blue"),
    (0.15, "cyan"),
    (0.30, "green"),
    (0.45, "bright_green"),
    (0.55, "yellow"),
    (0.70, "orange1"),
    (0.85, "red"),
    (1.00, "bold bright_red"),
]


def gradient_colour(value: float) -> str:
    """Return a Rich colour string for a normalised value (0-1)."""
    value = max(0.0, min(1.0, value))
    for threshold, colour in reversed(GRADIENT_STEPS):
        if value >= threshold:
            return colour
    return "bright_blue"


def heat_block(value: float, show_value: bool = True) -> str:
    """
    Return a Rich markup string for a heatmap cell.
    Uses a filled block character (█) with gradient colour.
    """
    colour   = gradient_colour(value)
    pct_str  = f"{value * 100:.0f}%" if show_value else "   "
    return f"[{colour}]{pct_str:>4}[/{colour}]"


class HeatmapRenderer:
    """
    Renders terminal heatmaps for probability distributions and entropy data.
    """

    def __init__(self, console: Console):
        self.console = console

    # ------------------------------------------------------------------
    # Mine probability heatmap (live game)
    # ------------------------------------------------------------------

    def render_mine_heatmap(
        self,
        probs:      List[float],
        title:      str = "MINE PROBABILITY HEATMAP",
        revealed:   Optional[List[int]] = None,
        hit_cells:  Optional[List[int]] = None,
    ) -> None:
        """
        Render a 5x5 heatmap of mine probabilities.
        Hot colours = higher mine probability.

        Args:
            probs:     List of 25 mine probability floats
            title:     Panel title
            revealed:  Indices of safely revealed cells (shown as SAFE)
            hit_cells: Indices of triggered mines (shown as MINE)
        """
        revealed  = set(revealed or [])
        hit_cells = set(hit_cells or [])

        table = Table(
            title        = f"[bold yellow]{title}[/bold yellow]",
            box          = box.MINIMAL,
            show_header  = True,
            header_style = "bold yellow dim",
            border_style = "yellow dim",
            padding      = (0, 1),
        )

        table.add_column("  ", style="bold yellow dim", width=2)
        for c in range(BOARD_COLS):
            table.add_column(f"C{c+1}", justify="center", width=7)

        for row in range(BOARD_ROWS):
            row_data = [f"[bold yellow dim]R{row+1}[/bold yellow dim]"]
            for col in range(BOARD_COLS):
                idx = row * BOARD_COLS + col

                if idx in hit_cells:
                    row_data.append("[bold red on red] MINE [/bold red on red]")
                elif idx in revealed:
                    row_data.append("[bold green] SAFE [/bold green]")
                else:
                    p      = probs[idx] if idx < len(probs) else 0.0
                    colour = gradient_colour(p)
                    bar    = self._mini_bar(p)
                    row_data.append(f"[{colour}]{p*100:4.1f}%[/{colour}]\n[dim]{bar}[/dim]")

            table.add_row(*row_data)

        self.console.print(table)
        self._render_gradient_scale()

    # ------------------------------------------------------------------
    # Frequency / entropy heatmap (from simulation or analysis data)
    # ------------------------------------------------------------------

    def render_frequency_heatmap(
        self,
        freq_data:  List[float],
        title:      str = "MINE FREQUENCY HEATMAP",
        subtitle:   str = "(from simulation/history data)",
    ) -> None:
        """
        Render a heatmap of normalised mine frequency per cell.
        Used in RNG analysis and Monte Carlo result visualisation.

        Args:
            freq_data: List of 25 floats, normalised to [0, 1] (1 = most frequent)
            title:     Panel title
        """
        table = Table(
            box          = box.MINIMAL,
            show_header  = True,
            header_style = "bold magenta dim",
            border_style = "magenta dim",
            padding      = (0, 1),
        )

        table.add_column("  ", style="bold magenta dim", width=2)
        for c in range(BOARD_COLS):
            table.add_column(f"C{c+1}", justify="center", width=8)

        for row in range(BOARD_ROWS):
            row_data = [f"[bold magenta dim]R{row+1}[/bold magenta dim]"]
            for col in range(BOARD_COLS):
                idx  = row * BOARD_COLS + col
                val  = freq_data[idx] if idx < len(freq_data) else 0.0
                colour = gradient_colour(val)
                block  = "██" if val > 0.7 else ("▓▓" if val > 0.4 else ("░░" if val > 0.1 else "  "))
                row_data.append(f"[{colour}]{block} {val*100:.0f}%[/{colour}]")
            table.add_row(*row_data)

        self.console.print(
            Panel(
                table,
                title    = f"[bold magenta]{title}[/bold magenta]",
                subtitle = f"[dim]{subtitle}[/dim]",
                border_style = "magenta dim",
            )
        )
        self._render_gradient_scale(style="magenta")

    # ------------------------------------------------------------------
    # Survival probability curve (ASCII chart)
    # ------------------------------------------------------------------

    def render_survival_curve(
        self,
        curve_data: List[dict],
        trap_count: int,
        width:      int = 40,
        height:     int = 12,
    ) -> None:
        """
        Render an ASCII survival probability curve for a given trap count.

        Args:
            curve_data: List of dicts from ProbabilityEngine.survival_curve()
            trap_count: Number of mines (for title)
            width:      Chart width in characters
            height:     Chart height in lines
        """
        if not curve_data:
            return

        picks   = [d["picks"]    for d in curve_data]
        survivals = [d["survival"] for d in curve_data]
        max_picks = max(picks) if picks else 1

        title = f"SURVIVAL PROBABILITY CURVE — {trap_count} TRAP{'S' if trap_count > 1 else ''}"
        self.console.print(f"\n[bold cyan]{title}[/bold cyan]")
        self.console.print(f"[dim]P(survive N picks) on 5×5 board[/dim]\n")

        # Render rows top to bottom (100% at top, 0% at bottom)
        for row_i in range(height, -1, -1):
            threshold = row_i / height
            pct_label = f"{threshold*100:3.0f}% "

            row_str = f"[dim cyan]{pct_label}[/dim cyan][dim]│[/dim]"
            for d in curve_data:
                bar_height = d["survival"]
                if bar_height >= threshold:
                    colour = gradient_colour(bar_height)
                    row_str += f"[{colour}]█[/{colour}]"
                else:
                    row_str += " "

            self.console.print(row_str)

        # X-axis
        axis_label  = "      └" + "─" * len(curve_data)
        tick_labels = "       " + "".join(
            str(d["picks"]) if d["picks"] % 2 == 0 else " "
            for d in curve_data
        )
        self.console.print(f"[dim]{axis_label}[/dim]")
        self.console.print(f"[dim cyan]{tick_labels}  picks[/dim cyan]")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mini_bar(self, value: float, width: int = 4) -> str:
        """Return a narrow ASCII bar for use inside table cells."""
        filled = int(round(value * width))
        empty  = width - filled
        return "█" * filled + "░" * empty

    def _render_gradient_scale(self, style: str = "yellow") -> None:
        """Print a horizontal gradient colour scale for reference."""
        scale = ""
        steps = 20
        for i in range(steps):
            val    = i / steps
            colour = gradient_colour(val)
            scale += f"[{colour}]█[/{colour}]"

        self.console.print(
            f"  [dim]LOW RISK[/dim] {scale} [dim]HIGH RISK[/dim]"
        )
        self.console.print()
