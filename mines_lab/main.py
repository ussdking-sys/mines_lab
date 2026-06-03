#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         MINES LAB — PROBABILITY CONSOLE                     ║
║              Provably Fair Analysis & Statistical Research Toolkit           ║
╚══════════════════════════════════════════════════════════════════════════════╝

main.py — Application entry point and main menu controller.

Launches the interactive terminal UI, initialises all subsystems, and routes
user input to the appropriate modules.

DISCLAIMER:
  This tool is a probability research, RNG visualisation, and statistical
  analysis environment. It does NOT predict cryptographically secure outcomes.
  Properly implemented provably fair systems are unpredictable without the
  true server seed. This application is for educational purposes only.
"""

import sys
import os

# ---------------------------------------------------------------------------
# Ensure the project root is on the Python path so all modules resolve cleanly
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich import box

from engine.game_engine import GameEngine
from engine.probability_engine import ProbabilityEngine
from engine.provably_fair import ProvablyFairEngine
from engine.monte_carlo import MonteCarloEngine
from engine.rng_analysis import RNGAnalyser
from engine.behavioral import BehavioralTracker
from storage.database import Database
from storage.session import SessionManager
from ui.board_renderer import BoardRenderer
from ui.dashboard import Dashboard
from ui.menus import MenuSystem
from ui.heatmap import HeatmapRenderer
from ui.charts import ChartRenderer
from research.research_mode import ResearchMode
from utils.config import Config
from utils.logger import get_logger

console = Console()
logger  = get_logger(__name__)


# ---------------------------------------------------------------------------
# ASCII banner
# ---------------------------------------------------------------------------
BANNER = """
[bold cyan]
███╗   ███╗██╗███╗   ██╗███████╗███████╗    ██╗      █████╗ ██████╗
████╗ ████║██║████╗  ██║██╔════╝██╔════╝    ██║     ██╔══██╗██╔══██╗
██╔████╔██║██║██╔██╗ ██║█████╗  ███████╗    ██║     ███████║██████╔╝
██║╚██╔╝██║██║██║╚██╗██║██╔══╝  ╚════██║    ██║     ██╔══██║██╔══██╗
██║ ╚═╝ ██║██║██║ ╚████║███████╗███████║    ███████╗██║  ██║██████╔╝
╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝    ╚══════╝╚═╝  ╚═╝╚═════╝
[/bold cyan]
[dim cyan]    Provably Fair Analysis · Probability Research · Statistical Console[/dim cyan]
"""

DISCLAIMER = (
    "[bold red]⚠  DISCLAIMER[/bold red]  "
    "This application is a [yellow]probability research and educational tool[/yellow]. "
    "It does [bold red]NOT[/bold red] predict cryptographically secure RNG outcomes. "
    "Provably fair systems are unpredictable without the true server seed. "
    "Simulations are statistical approximations only."
)


def print_banner() -> None:
    """Render the startup banner and disclaimer."""
    console.clear()
    console.print(BANNER)
    console.print(
        Panel(DISCLAIMER, border_style="red dim", padding=(0, 2)),
        justify="center"
    )
    console.print()


def initialise_subsystems(config: Config) -> dict:
    """
    Boot all subsystems and return them as a dependency bundle.
    Each subsystem is constructed once here and shared across the application.
    """
    logger.info("Initialising subsystems...")

    db           = Database(config.db_path)
    session_mgr  = SessionManager(db)
    prob_engine  = ProbabilityEngine()
    pf_engine    = ProvablyFairEngine()
    mc_engine    = MonteCarloEngine(prob_engine)
    rng_analyser = RNGAnalyser(db)
    behavioral   = BehavioralTracker(db)
    board_render = BoardRenderer(console)
    heatmap      = HeatmapRenderer(console)
    chart        = ChartRenderer(console)
    dashboard    = Dashboard(console)
    research     = ResearchMode(console, prob_engine, pf_engine, mc_engine, rng_analyser)

    return {
        "config":       config,
        "db":           db,
        "session":      session_mgr,
        "prob":         prob_engine,
        "pf":           pf_engine,
        "mc":           mc_engine,
        "rng":          rng_analyser,
        "behavioral":   behavioral,
        "board":        board_render,
        "heatmap":      heatmap,
        "chart":        chart,
        "dashboard":    dashboard,
        "research":     research,
        "console":      console,
    }


def main() -> None:
    """Application entry point."""
    # Load configuration (creates defaults on first run)
    config = Config()
    config.ensure_directories()

    print_banner()

    # Boot subsystems
    systems = initialise_subsystems(config)

    # Hand off to the menu system — all navigation lives there
    menu = MenuSystem(systems)
    menu.main_menu()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[dim cyan]Session terminated by user. Goodbye.[/dim cyan]\n")
        sys.exit(0)
    except Exception as exc:
        console.print(f"\n[bold red]Fatal error:[/bold red] {exc}")
        logger.exception("Unhandled exception in main")
        sys.exit(1)
