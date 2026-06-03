"""
ui/board_renderer.py — Terminal board rendering with ANSI colours.

Renders the 5x5 Mines board in the terminal with:
  - Colour-coded cell states
  - Mine probability overlays
  - Zone annotations
  - Live update support
  - Coordinate labels
"""

import time
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.columns import Columns
from rich import box

from engine.game_engine import BoardCell, CellSymbol
from utils.helpers import colour_for_probability, progress_bar
from utils.config import BOARD_ROWS, BOARD_COLS
from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Cell colour maps — one colour per symbol
# ---------------------------------------------------------------------------
CELL_COLOURS = {
    CellSymbol.UNKNOWN:   ("dim white",       "?"),
    CellSymbol.SAFE_PRED: ("bold cyan",       "X"),
    CellSymbol.TRAP_PRED: ("bold red",        "O"),
    CellSymbol.CONFIRMED: ("bold green",      "$"),
    CellSymbol.MINE_HIT:  ("bold red on red", "#"),
    CellSymbol.MINE_SHOW: ("yellow",          "*"),
}


class BoardRenderer:
    """
    Renders the game board and associated overlays to the terminal.
    """

    def __init__(self, console: Console):
        self.console = console

    # ------------------------------------------------------------------
    # Main board render
    # ------------------------------------------------------------------

    def render_board(
        self,
        cells:        List[BoardCell],
        show_probs:   bool   = False,
        highlight:    Optional[List[int]] = None,
        title:        str    = "MINES BOARD",
        show_coords:  bool   = True,
    ) -> None:
        """
        Render the full 5x5 board to the terminal.

        Args:
            cells:       List of 25 BoardCell objects
            show_probs:  If True, show mine probability under each cell
            highlight:   List of cell indices to highlight (recommended cells)
            title:       Panel title string
            show_coords: Show row/col labels
        """
        highlight = highlight or []

        table = Table(
            box          = box.HEAVY_HEAD,
            show_header  = show_coords,
            header_style = "bold cyan dim",
            border_style = "cyan dim",
            padding      = (0, 1),
        )

        if show_coords:
            table.add_column("  ", style="bold cyan dim", width=2)
            for col in range(BOARD_COLS):
                table.add_column(str(col + 1), justify="center", width=7 if show_probs else 4)

        for row in range(BOARD_ROWS):
            row_data = [f"[bold cyan dim]{row + 1}[/bold cyan dim]"] if show_coords else []

            for col in range(BOARD_COLS):
                idx  = row * BOARD_COLS + col
                cell = cells[idx]

                colour, symbol = CELL_COLOURS.get(
                    cell.symbol, ("dim white", cell.symbol)
                )

                # Highlight recommended cells with a bright border indicator
                is_highlighted = idx in highlight
                if is_highlighted and cell.symbol in (CellSymbol.UNKNOWN, CellSymbol.SAFE_PRED):
                    colour = "bold bright_cyan"
                    symbol = "▶" + symbol

                cell_text = f"[{colour}]{symbol}[/{colour}]"

                if show_probs and not cell.is_revealed and not cell.is_hit:
                    prob_str  = f"{cell.mine_prob * 100:.0f}%"
                    prob_col  = colour_for_probability(1.0 - cell.mine_prob)
                    cell_text += f"\n[{prob_col} dim]{prob_str:>4}[/{prob_col} dim]"

                row_data.append(cell_text)

            table.add_row(*row_data)

        self.console.print(Panel(table, title=f"[bold cyan]{title}[/bold cyan]", border_style="cyan"))

    # ------------------------------------------------------------------
    # Compact board (single line per cell, no probabilities)
    # ------------------------------------------------------------------

    def render_board_compact(self, cells: List[BoardCell], title: str = "") -> None:
        """Render a compact 5x5 board for dashboard use."""
        lines = []
        for row in range(BOARD_ROWS):
            row_str = ""
            for col in range(BOARD_COLS):
                idx    = row * BOARD_COLS + col
                cell   = cells[idx]
                colour, symbol = CELL_COLOURS.get(cell.symbol, ("dim white", cell.symbol))
                row_str += f"[{colour}]{symbol}[/{colour}] "
            lines.append(row_str.strip())

        board_str = "\n".join(lines)
        if title:
            self.console.print(Panel(board_str, title=f"[dim]{title}[/dim]", border_style="dim cyan", padding=(1, 2)))
        else:
            self.console.print(board_str)

    # ------------------------------------------------------------------
    # Probability overlay
    # ------------------------------------------------------------------

    def render_probability_overlay(self, cells: List[BoardCell]) -> None:
        """
        Render a standalone probability grid showing mine % for each cell.
        Colour gradient: green (safe) → red (dangerous).
        """
        table = Table(
            title        = "[bold yellow]MINE PROBABILITY OVERLAY[/bold yellow]",
            box          = box.SIMPLE,
            show_header  = True,
            header_style = "bold yellow dim",
            border_style = "yellow dim",
        )

        table.add_column(" ", style="bold yellow dim", width=2)
        for c in range(BOARD_COLS):
            table.add_column(str(c + 1), justify="center", width=8)

        for row in range(BOARD_ROWS):
            row_data = [str(row + 1)]
            for col in range(BOARD_COLS):
                idx  = row * BOARD_COLS + col
                cell = cells[idx]

                if cell.is_revealed:
                    cell_str = "[green dim]SAFE[/green dim]"
                elif cell.is_hit:
                    cell_str = "[bold red]MINE[/bold red]"
                else:
                    pct   = cell.mine_prob * 100
                    colour = colour_for_probability(1.0 - cell.mine_prob)
                    bar    = progress_bar(cell.mine_prob, width=4)
                    cell_str = f"[{colour}]{pct:4.1f}%[/{colour}]\n[dim]{bar}[/dim]"

                row_data.append(cell_str)
            table.add_row(*row_data)

        self.console.print(table)

    # ------------------------------------------------------------------
    # Pick indicator animation
    # ------------------------------------------------------------------

    def animate_pick(self, cell_index: int, outcome: str, delay: float = 0.05) -> None:
        """
        Brief terminal animation for a cell pick event.
        Flashes the cell coordinate and outcome.
        """
        row = cell_index // BOARD_COLS + 1
        col = cell_index % BOARD_COLS + 1

        if outcome == "SAFE":
            symbol = "[bold green]$ SAFE![/bold green]"
        elif outcome == "MINE":
            symbol = "[bold red on red]  # MINE!  [/bold red on red]"
        else:
            symbol = "[dim]...[/dim]"

        self.console.print(f"  Cell ({row},{col}) → {symbol}")
        time.sleep(delay)

    # ------------------------------------------------------------------
    # Cell legend
    # ------------------------------------------------------------------

    def render_legend(self) -> None:
        """Print a colour-coded legend explaining cell symbols."""
        items = [
            ("[dim white]?[/dim white]", "Unknown / unrevealed"),
            ("[bold cyan]▶X[/bold cyan]", "Recommended safe pick"),
            ("[bold red]O[/bold red]", "High mine probability"),
            ("[bold green]$[/bold green]", "Confirmed safe"),
            ("[bold red]#[/bold red]", "Mine triggered (game over)"),
            ("[yellow]*[/yellow]", "Mine revealed at game end"),
        ]

        legend_text = "  ".join(
            f"{sym} {label}" for sym, label in items
        )
        self.console.print(
            Panel(legend_text, title="[dim]LEGEND[/dim]", border_style="dim", padding=(0, 1))
        )

    # ------------------------------------------------------------------
    # Cell coordinate input helper
    # ------------------------------------------------------------------

    def prompt_cell_input(self) -> Optional[int]:
        """
        Prompt the user to enter a cell coordinate (row, col) or flat index.
        Returns 0-based flat index, or None if input is invalid.
        """
        self.console.print(
            "\n[cyan]Enter cell[/cyan] [dim](row col)[/dim] or [dim](1-25)[/dim]: ",
            end=""
        )
        raw = input().strip()

        try:
            parts = raw.split()
            if len(parts) == 2:
                row, col = int(parts[0]) - 1, int(parts[1]) - 1
                if 0 <= row < BOARD_ROWS and 0 <= col < BOARD_COLS:
                    return row * BOARD_COLS + col
            elif len(parts) == 1:
                idx = int(parts[0]) - 1
                if 0 <= idx < 25:
                    return idx
        except (ValueError, IndexError):
            pass

        self.console.print("[red]Invalid cell. Use 'row col' (e.g. '2 3') or index 1-25.[/red]")
        return None
