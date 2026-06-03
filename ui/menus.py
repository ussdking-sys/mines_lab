"""
ui/menus.py — Interactive menu system and game flow controller.

Handles all user navigation:
  - Main menu
  - Game setup (profile selection, seed configuration)
  - Active game loop (pick, cash out, view stats)
  - Simulation lab
  - RNG analysis
  - Provably fair verification
  - Behavioral analytics
  - Session reports
  - Settings
"""

import time
from typing import Optional, Dict, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.columns import Columns
from rich import box

from utils.config import (
    TRAP_PROFILES, RISK_PROFILES, VALID_TRAP_COUNTS,
    BOARD_SIZE,
)
from utils.helpers import (
    generate_client_seed, format_percent, format_odds,
    colour_for_probability, progress_bar,
)
from utils.logger import get_logger

logger = get_logger(__name__)

DISCLAIMER_SHORT = (
    "[bold red]⚠[/bold red]  [dim]Provably fair systems are cryptographically unpredictable "
    "without the true server seed. All probabilities are statistical estimates only.[/dim]"
)


class MenuSystem:
    """
    Main navigation controller. Holds references to all subsystems
    and routes user choices to the appropriate handlers.
    """

    def __init__(self, systems: dict):
        self.sys      = systems
        self.console  = systems["console"]
        self.config   = systems["config"]
        self.db       = systems["db"]
        self.session  = systems["session"]
        self.prob     = systems["prob"]
        self.pf       = systems["pf"]
        self.mc       = systems["mc"]
        self.rng      = systems["rng"]
        self.behav    = systems["behavioral"]
        self.board_r  = systems["board"]
        self.heatmap  = systems["heatmap"]
        self.chart    = systems["chart"]
        self.dash     = systems["dashboard"]
        self.research = systems["research"]

    # ==================================================================
    # MAIN MENU
    # ==================================================================

    def main_menu(self) -> None:
        """Root navigation menu. Loops until user exits."""
        while True:
            self.console.clear()
            self._print_header("MAIN MENU")
            self.console.print(DISCLAIMER_SHORT)
            self.console.print()

            options = {
                "1": ("Play Mines",                self._menu_play),
                "2": ("Monte Carlo Simulation Lab", self._menu_simulation),
                "3": ("Provably Fair Verifier",    self._menu_verifier),
                "4": ("RNG & Entropy Analysis",    self._menu_rng),
                "5": ("Behavioral Analytics",      self._menu_behavioral),
                "6": ("Session Report",            self._menu_session_report),
                "7": ("Research Mode",             self._menu_research),
                "8": ("Settings",                  self._menu_settings),
                "Q": ("Quit",                      None),
            }

            self._print_menu(options)
            choice = self._prompt_choice(list(options.keys()))

            if choice == "Q":
                self._quit()
                return

            _, handler = options[choice]
            if handler:
                handler()

    # ==================================================================
    # PLAY — GAME SETUP
    # ==================================================================

    def _menu_play(self) -> None:
        """Game setup: profile selection → seed config → game loop."""
        self.console.clear()
        self._print_header("GAME SETUP")

        # ── Step 1: Select game profile (trap count) ──
        self.console.print("\n[bold cyan]Select a game profile:[/bold cyan]\n")

        profile_table = Table(box=box.ROUNDED, border_style="cyan dim", show_header=True, header_style="bold cyan")
        profile_table.add_column("#",           width=4,  justify="center")
        profile_table.add_column("Traps",       width=8,  justify="center")
        profile_table.add_column("Suggested",   width=16)
        profile_table.add_column("Rationale",   width=52)

        for i, tc in enumerate(VALID_TRAP_COUNTS, 1):
            p    = TRAP_PROFILES[tc]
            col  = p["color"]
            sugg = RISK_PROFILES[p["suggested"]]["short"]
            profile_table.add_row(
                str(i),
                f"[{col}]{p['emoji']} {p['label']}[/{col}]",
                f"[{col}]{p['suggested']}[/{col}]",
                f"[dim]{p['rationale']}[/dim]",
            )

        self.console.print(profile_table)
        self.console.print()

        choice = self._prompt_number("Choose profile (1-4)", 1, 4)
        trap_count = VALID_TRAP_COUNTS[choice - 1]
        trap_prof  = TRAP_PROFILES[trap_count]

        self.console.print(
            f"\n  Selected: [{trap_prof['color']}]{trap_prof['emoji']} {trap_prof['label']}[/{trap_prof['color']}]"
        )
        suggested = trap_prof["suggested"]
        self.console.print(
            f"  Suggested appetite: [{RISK_PROFILES[suggested]['color']}]{suggested}[/{RISK_PROFILES[suggested]['color']}]"
            f"  — [dim]{RISK_PROFILES[suggested]['description']}[/dim]"
        )

        # ── Step 2: Accept or override risk appetite ──
        self.console.print("\n[bold cyan]Risk Appetite:[/bold cyan]")
        self.console.print(f"  [dim]Press Enter to accept suggestion ({suggested}), or choose:[/dim]")

        appetite_opts = {
            "1": "CONSERVATIVE",
            "2": "BALANCED",
            "3": "AGGRESSIVE",
            "4": "ALL_IN",
            "": suggested,   # default = suggested
        }
        for k, v in [("1","CONSERVATIVE"),("2","BALANCED"),("3","AGGRESSIVE"),("4","ALL_IN")]:
            col  = RISK_PROFILES[v]["color"]
            mark = " [bold cyan]← suggested[/bold cyan]" if v == suggested else ""
            self.console.print(f"  [{col}]{k}. {v}[/{col}]{mark}")

        raw = Prompt.ask("  Choice", default="").strip()
        risk_profile = appetite_opts.get(raw, suggested)
        self.behav.set_declared_profile(risk_profile)

        rp_col = RISK_PROFILES[risk_profile]["color"]
        self.console.print(f"\n  [{rp_col}]✓ Profile: {risk_profile}[/{rp_col}]")
        time.sleep(0.5)

        # Log divergence from suggestion
        if risk_profile != suggested:
            self.console.print(
                f"  [dim yellow]Note: You chose {risk_profile} vs suggested {suggested}. "
                f"Behavioral tracker has noted this.[/dim yellow]"
            )
            time.sleep(1)

        # ── Step 3: Seed configuration ──
        self.console.print("\n[bold cyan]Seed Configuration:[/bold cyan]")
        self.console.print("  [dim](All seeds optional — press Enter to auto-generate)[/dim]\n")

        client_seed = Prompt.ask(
            "  Client seed [dim](hex string, auto if blank)[/dim]",
            default=""
        ).strip() or generate_client_seed()

        server_seed = Prompt.ask(
            "  Server seed [dim](leave blank for simulation mode)[/dim]",
            default=""
        ).strip() or None

        nonce_current = self.pf.get_current_nonce(client_seed)
        nonce_str = Prompt.ask(
            f"  Nonce [dim](auto-increment default: {nonce_current})[/dim]",
            default=""
        ).strip()
        nonce = int(nonce_str) if nonce_str.isdigit() else nonce_current

        # Check for nonce reuse
        if self.pf.check_nonce_reuse(client_seed, nonce):
            self.console.print(f"\n  [bold yellow]⚠ Nonce {nonce} has been used before with this seed.[/bold yellow]")
            if not Confirm.ask("  Continue anyway?", default=False):
                return

        mode = "DETERMINISTIC" if server_seed else "SIMULATION"
        mode_col = "green" if mode == "DETERMINISTIC" else "yellow"
        self.console.print(f"\n  Mode: [{mode_col}]{mode}[/{mode_col}]")
        if mode == "SIMULATION":
            self.console.print(
                "  [dim]Simulation mode: mine positions are randomly generated. "
                "Real outcomes are unpredictable without the server seed.[/dim]"
            )
        else:
            self.console.print(
                "  [dim green]Deterministic mode: board derived from provided seeds.[/dim green]"
            )

        time.sleep(0.8)

        # ── Launch game ──
        self._run_game(
            trap_count   = trap_count,
            risk_profile = risk_profile,
            client_seed  = client_seed,
            server_seed  = server_seed,
            nonce        = nonce,
        )

    # ==================================================================
    # ACTIVE GAME LOOP
    # ==================================================================

    def _run_game(
        self,
        trap_count:   int,
        risk_profile: str,
        client_seed:  str,
        server_seed:  Optional[str],
        nonce:        int,
    ) -> None:
        """Main game loop for a single round."""
        from engine.game_engine import GameEngine, GameStatus

        game_engine = GameEngine(pf_engine=self.pf)

        # Start game
        game = game_engine.new_game(
            trap_count   = trap_count,
            risk_profile = risk_profile,
            client_seed  = client_seed,
            server_seed  = server_seed,
            nonce        = nonce,
        )

        # Initialise probability engine
        prob_state = self.prob.initialise(trap_count)

        # If deterministic mode, feed known mine positions to prob engine
        known_mines = game.mine_positions if server_seed else None

        self.console.clear()
        self._print_header(f"GAME — {trap_count} TRAP{'S' if trap_count > 1 else ''}  [{risk_profile}]")

        while game_engine.is_active():
            # ── Update cell probabilities ──
            cells      = game_engine.get_board()
            mine_probs = self.prob.get_cell_probabilities()
            game_engine.update_cell_probabilities(mine_probs)

            # Get recommended cells
            recommended = self.prob.get_recommended_cells(strategy=risk_profile, n=3)
            rec_indices = [idx for idx, _ in recommended]
            game_engine.apply_safe_predictions(rec_indices)

            # ── Render board ──
            self.console.clear()
            self._print_header(f"ACTIVE ROUND — {trap_count} TRAP{'S' if trap_count > 1 else ''}")
            self.console.print(DISCLAIMER_SHORT + "\n")

            self.board_r.render_board(
                cells       = cells,
                show_probs  = True,
                highlight   = rec_indices,
                title       = f"BOARD  [dim]mode={game.mode}[/dim]",
            )
            self.board_r.render_legend()

            # ── Render stats panel ──
            ps = self.prob.get_state()
            self.dash.render_game_stats(
                trap_count       = trap_count,
                picks_made       = ps.revealed_safe,
                next_survival    = ps.next_pick_survival,
                cumulative_surv  = ps.cumulative_survival,
                risk_score       = ps.risk_score,
                risk_profile     = risk_profile,
                recommended_stop = ps.recommended_stop,
                session_ev       = ps.session_ev,
                mode             = game.mode,
            )

            # ── Continue vs cash-out comparison ──
            if ps.revealed_safe > 0:
                from engine.probability_engine import ProbabilityEngine
                mult = ProbabilityEngine.MULTIPLIER_TABLES.get(trap_count, {}).get(ps.revealed_safe, 1.0)
                comparison = self.prob.compare_continue_vs_cashout(
                    current_picks      = ps.revealed_safe,
                    trap_count         = trap_count,
                    current_multiplier = mult,
                )
                self.dash.render_decision_panel(comparison)

            # ── Action menu ──
            self.console.print("\n[bold cyan]Actions:[/bold cyan]")
            actions = {
                "P": "Pick a cell",
                "H": "Show probability heatmap",
                "C": "Cash out" + (" [dim](need ≥1 pick)[/dim]" if ps.revealed_safe == 0 else ""),
                "A": "Auto-pick (engine recommendation)",
                "Q": "Abandon round",
            }
            for k, v in actions.items():
                self.console.print(f"  [{k}] {v}")

            choice = self._prompt_choice(["P", "H", "C", "A", "Q"])

            if choice == "Q":
                game_engine.end_game()
                self.console.print("[dim]Round abandoned.[/dim]")
                time.sleep(1)
                break

            elif choice == "H":
                revealed_idxs = [c.index for c in cells if c.is_revealed]
                hit_idxs      = [c.index for c in cells if c.is_hit]
                self.heatmap.render_mine_heatmap(
                    probs     = mine_probs,
                    revealed  = revealed_idxs,
                    hit_cells = hit_idxs,
                )
                input("\n[Enter to continue]")
                continue

            elif choice == "C":
                if ps.revealed_safe == 0:
                    self.console.print("[yellow]Must make at least one pick before cashing out.[/yellow]")
                    time.sleep(1)
                    continue
                result = game_engine.cash_out()
                self._handle_cashout(result, game, game_engine)
                break

            elif choice == "A":
                # Auto-pick: use engine's top recommendation
                if rec_indices:
                    cell_idx = rec_indices[0]
                    self.console.print(f"  [cyan]Auto-picking cell {cell_idx + 1}...[/cyan]")
                    time.sleep(0.4)
                else:
                    self.console.print("[yellow]No recommendation available.[/yellow]")
                    time.sleep(1)
                    continue
                pick_result = self._execute_pick(cell_idx, game_engine, known_mines, trap_count, game, ps)
                if pick_result == "GAME_OVER":
                    break

            elif choice == "P":
                cell_idx = self.board_r.prompt_cell_input()
                if cell_idx is None:
                    time.sleep(1)
                    continue
                pick_result = self._execute_pick(cell_idx, game_engine, known_mines, trap_count, game, ps)
                if pick_result == "GAME_OVER":
                    break

        # Increment nonce after round
        self.pf.increment_nonce(client_seed)

        # Save session data
        self.session.save_round(game_engine.get_history()[-1] if game_engine.get_history() else None)

        input("\n  [dim]Press Enter to return to main menu...[/dim]")

    def _execute_pick(self, cell_idx, game_engine, known_mines, trap_count, game, ps) -> str:
        """Execute a pick and handle the outcome. Returns 'GAME_OVER' or 'CONTINUE'."""
        result = game_engine.pick(cell_idx)

        if result["outcome"] == "INVALID":
            self.console.print(f"[yellow]{result.get('reason', 'Invalid pick.')}[/yellow]")
            time.sleep(1)
            return "CONTINUE"

        self.board_r.animate_pick(cell_idx, result["outcome"])

        if result["outcome"] == "SAFE":
            # Log behavioral decision
            past_stop = ps.revealed_safe >= ps.recommended_stop
            self.behav.log_decision(
                round_id         = game.round_id,
                pick_number      = result["picks_survived"],
                recommended_stop = past_stop,
                survival_prob    = ps.next_pick_survival,
                chose_continue   = True,
                ev_continue      = ps.session_ev,
                ev_cashout       = 1.0,
                outcome          = "SAFE",
            )
            # Update probability engine
            self.prob.update_after_safe_pick(cell_idx, known_mine_positions=known_mines)
            time.sleep(0.3)
            return "CONTINUE"

        elif result["outcome"] == "MINE":
            self.prob.update_after_mine_hit(cell_idx)
            self._handle_mine_hit(result, game, game_engine)
            self.behav.log_round_end(
                round_id              = game.round_id,
                result                = "LOSS",
                picks_made            = result["picks_survived"],
                recommended_stop_depth = ps.recommended_stop,
            )
            return "GAME_OVER"

        return "CONTINUE"

    def _handle_mine_hit(self, result: dict, game, game_engine) -> None:
        """Display mine-hit outcome screen."""
        self.console.print()
        self.console.print(Panel(
            f"[bold red]  💥  MINE TRIGGERED AT CELL {result['cell_index'] + 1}  💥  [/bold red]\n"
            f"  Survived [bold]{result['picks_survived']}[/bold] picks before bust.",
            border_style="bold red",
            padding=(1, 4),
        ))
        # Show final board
        cells = game_engine.get_board()
        self.board_r.render_board(cells, title="FINAL BOARD — MINE HIT")
        self.console.print(f"\n  [dim]Mines were at positions: {sorted(game.mine_positions)}[/dim]")
        time.sleep(1)

    def _handle_cashout(self, result: dict, game, game_engine) -> None:
        """Display cash-out success screen."""
        picks = result["picks_survived"]
        self.console.print()
        self.console.print(Panel(
            f"[bold green]  ✓  CASHED OUT SUCCESSFULLY  ✓  [/bold green]\n"
            f"  Survived [bold green]{picks}[/bold green] picks safely.",
            border_style="bold green",
            padding=(1, 4),
        ))
        cells = game_engine.get_board()
        self.board_r.render_board(cells, title="FINAL BOARD — CASHED OUT")
        self.console.print(f"\n  [dim]Mines were at positions: {sorted(game.mine_positions)}[/dim]")
        self.behav.log_round_end(
            round_id              = game.round_id,
            result                = "CASHOUT",
            picks_made            = picks,
            recommended_stop_depth = self.prob.get_state().recommended_stop if self.prob.get_state() else 0,
        )
        time.sleep(1)

    # ==================================================================
    # SIMULATION LAB
    # ==================================================================

    def _menu_simulation(self) -> None:
        """Monte Carlo simulation lab menu."""
        while True:
            self.console.clear()
            self._print_header("MONTE CARLO SIMULATION LAB")
            self.console.print(DISCLAIMER_SHORT + "\n")
            self.console.print(
                "[dim]Simulations estimate long-term statistical patterns. "
                "Results are approximations, not predictions.[/dim]\n"
            )

            options = {
                "1": "Run single strategy simulation",
                "2": "Compare all strategies (one trap count)",
                "3": "Compare trap counts (one strategy)",
                "4": "View last results",
                "5": "Export simulation results",
                "B": "Back",
            }
            self._print_menu(options)
            choice = self._prompt_choice(list(options.keys()))

            if choice == "B":
                return

            elif choice == "1":
                self._sim_single()

            elif choice == "2":
                self._sim_compare_strategies()

            elif choice == "3":
                self._sim_compare_trap_counts()

            elif choice == "4":
                results = self.mc.get_results()
                if results:
                    self.dash.render_simulation_results(results[-6:])
                else:
                    self.console.print("[dim]No simulation results yet.[/dim]")
                input("\n  [dim]Press Enter...[/dim]")

            elif choice == "5":
                self._export_simulation_results()

    def _sim_single(self) -> None:
        """Run a single strategy simulation."""
        self.console.print("\n[bold cyan]Strategy options:[/bold cyan]")
        strategies = list(self.mc.STOP_RATIOS.keys()) and [
            "random", "edge_first", "center_first",
            "low_variance", "aggressive", "weighted_safest",
        ]
        for i, s in enumerate(strategies, 1):
            self.console.print(f"  {i}. {s.replace('_', ' ').title()}")

        s_choice  = self._prompt_number("Strategy", 1, len(strategies))
        strategy  = strategies[s_choice - 1]
        tc        = self._prompt_trap_count()
        iters     = self._prompt_iterations()
        rp        = self._prompt_risk_profile()

        self.console.print(f"\n  [cyan]Running {iters:,} simulations...[/cyan]")
        result = self.mc.run(
            strategy     = strategy,
            trap_count   = tc,
            iterations   = iters,
            risk_profile = rp,
            progress_cb  = self._sim_progress,
        )

        self.console.print()
        self.dash.render_simulation_results([result])
        self.chart.render_depth_histogram(
            depths    = result.survival_depths,
            max_depth = BOARD_SIZE - tc,
        )
        input("\n  [dim]Press Enter...[/dim]")

    def _sim_compare_strategies(self) -> None:
        """Run all strategies for one trap count."""
        tc    = self._prompt_trap_count()
        iters = self._prompt_iterations(default=5000)
        rp    = self._prompt_risk_profile()

        self.console.print(f"\n  [cyan]Running all strategies × {iters:,} iterations...[/cyan]")
        results = self.mc.run_all_strategies(
            trap_count   = tc,
            iterations   = iters,
            risk_profile = rp,
        )

        self.console.print()
        self.dash.render_simulation_results(results)
        self.chart.render_strategy_comparison(results, tc)
        input("\n  [dim]Press Enter...[/dim]")

    def _sim_compare_trap_counts(self) -> None:
        """Run one strategy across all trap counts."""
        strategies = [
            "random", "edge_first", "center_first",
            "low_variance", "aggressive", "weighted_safest",
        ]
        for i, s in enumerate(strategies, 1):
            self.console.print(f"  {i}. {s.replace('_', ' ').title()}")

        s_choice  = self._prompt_number("Strategy", 1, len(strategies))
        strategy  = strategies[s_choice - 1]
        iters     = self._prompt_iterations(default=3000)
        rp        = self._prompt_risk_profile()

        results_by_tc = self.mc.compare_trap_counts(
            strategy     = strategy,
            iterations   = iters,
            risk_profile = rp,
        )

        self.console.print(f"\n[bold magenta]STRATEGY: {strategy.upper()} — ALL TRAP COUNTS[/bold magenta]\n")
        for tc, res in results_by_tc.items():
            self.console.print(f"  [bold]{tc} Trap{'s' if tc > 1 else ''}[/bold]  win={format_percent(res.win_rate)}  avg_depth={res.avg_depth:.2f}  std={res.std_dev:.2f}")

        input("\n  [dim]Press Enter...[/dim]")

    def _export_simulation_results(self) -> None:
        """Export simulation results to JSON."""
        import json
        from pathlib import Path
        results = self.mc.export_results()
        if not results:
            self.console.print("[dim]Nothing to export.[/dim]")
            time.sleep(1)
            return
        path = Path(self.config.exports_dir) / "simulation_results.json"
        with open(path, "w") as f:
            json.dump(results, f, indent=2)
        self.console.print(f"  [green]✓ Exported to {path}[/green]")
        time.sleep(1.5)

    # ==================================================================
    # PROVABLY FAIR VERIFIER
    # ==================================================================

    def _menu_verifier(self) -> None:
        """Provably fair verification tool."""
        self.console.clear()
        self._print_header("PROVABLY FAIR VERIFIER")

        self.console.print(
            "[dim]Enter all known round variables to verify board integrity.\n"
            "All fields except trap count are optional but verification\n"
            "requires server seed + client seed + nonce.[/dim]\n"
        )

        server_seed    = Prompt.ask("  Server seed (revealed post-game)").strip()
        published_hash = Prompt.ask("  Published server seed hash").strip()
        client_seed    = Prompt.ask("  Client seed").strip()
        nonce_str      = Prompt.ask("  Nonce").strip()
        tc             = self._prompt_trap_count()
        mines_str      = Prompt.ask("  Claimed mine positions (comma-separated, 0-based)").strip()

        try:
            nonce        = int(nonce_str)
            claimed_mines = [int(x.strip()) for x in mines_str.split(",") if x.strip().isdigit()]
        except ValueError:
            self.console.print("[red]Invalid nonce or mine positions.[/red]")
            input("\n  [dim]Press Enter...[/dim]")
            return

        self.console.print("\n  [cyan]Verifying...[/cyan]")
        time.sleep(0.6)

        report = self.pf.verify_full_round(
            server_seed    = server_seed,
            published_hash = published_hash,
            client_seed    = client_seed,
            nonce          = nonce,
            trap_count     = tc,
            claimed_mines  = claimed_mines,
        )

        self.console.clear()
        self._print_header("VERIFICATION RESULT")
        self.dash.render_verification_report(report)

        # Show step-by-step in research mode style
        if Confirm.ask("\n  Show step-by-step verification breakdown?", default=False):
            steps = self.pf.get_verification_steps(server_seed, client_seed, nonce)
            self.research.render_verification_steps(steps)

        input("\n  [dim]Press Enter...[/dim]")

    # ==================================================================
    # RNG & ENTROPY ANALYSIS
    # ==================================================================

    def _menu_rng(self) -> None:
        """RNG and entropy analysis menu."""
        while True:
            self.console.clear()
            self._print_header("RNG & ENTROPY ANALYSIS")

            options = {
                "1": "Analyse seed entropy",
                "2": "Analyse board distribution (from session history)",
                "3": "Detect duplicate boards",
                "4": "View anomaly alerts",
                "5": "Nonce history check",
                "B": "Back",
            }
            self._print_menu(options)
            choice = self._prompt_choice(list(options.keys()))

            if choice == "B":
                return

            elif choice == "1":
                seed = Prompt.ask("  Enter seed to analyse").strip()
                report = self.rng.analyse_seed(seed)
                self.chart.render_entropy_gauge(
                    entropy       = report.raw_entropy,
                    normalised    = report.normalised,
                    quality_label = report.quality_label,
                    seed_preview  = seed[:16],
                )
                if report.anomalies:
                    self.console.print("[bold yellow]Anomalies detected:[/bold yellow]")
                    for a in report.anomalies:
                        self.console.print(f"  [yellow]• {a}[/yellow]")
                self.console.print(f"\n  [dim]{report.recommendation}[/dim]")
                input("\n  [dim]Press Enter...[/dim]")

            elif choice == "2":
                boards = self.session.get_all_mine_positions()
                if not boards:
                    self.console.print("[dim]No board history available.[/dim]")
                    time.sleep(1.5)
                    continue
                tc = self._prompt_trap_count()
                analysis = self.rng.analyse_board_distribution(boards, tc)
                self.console.print(f"\n  [cyan]Analysed {analysis['total_boards']} boards[/cyan]")
                self.console.print(f"  Chi-square: [bold]{analysis['chi_square']:.3f}[/bold]")
                self.console.print(
                    f"  Uniform distribution likely: "
                    f"{'[green]YES[/green]' if analysis['uniform_likely'] else '[yellow]NO[/yellow]'}"
                )
                if analysis["flagged_cells"]:
                    self.console.print(f"  [yellow]Flagged cells (>50% deviation): {analysis['flagged_cells']}[/yellow]")

                # Render frequency heatmap
                freq_data = self.rng.generate_entropy_heatmap_data(boards)
                self.heatmap.render_frequency_heatmap(freq_data)
                input("\n  [dim]Press Enter...[/dim]")

            elif choice == "3":
                boards = self.session.get_all_mine_positions()
                dupes  = self.rng.detect_duplicate_boards(boards)
                if dupes:
                    self.console.print(f"\n  [bold yellow]⚠ {len(dupes)} duplicate board layout(s) detected[/bold yellow]")
                    for d in dupes[:5]:
                        self.console.print(f"    Mines: {d['board']}  first={d['first_seen']} dup_at={d['duplicate_at']}")
                else:
                    self.console.print("\n  [green]✓ No duplicate boards detected.[/green]")
                input("\n  [dim]Press Enter...[/dim]")

            elif choice == "4":
                alerts = self.rng.get_alerts()
                summary = self.rng.get_alert_summary()
                self.console.print(f"\n  Total alerts: [bold]{summary['total']}[/bold]")
                self.console.print(f"  HIGH: [red]{summary['high']}[/red]  MEDIUM: [yellow]{summary['medium']}[/yellow]  LOW: [dim]{summary['low']}[/dim]")
                for a in alerts[-10:]:
                    col = "red" if a.severity == "HIGH" else "yellow"
                    self.console.print(f"  [{col}][{a.severity}] {a.alert_type}[/{col}]: {a.description}")
                input("\n  [dim]Press Enter...[/dim]")

            elif choice == "5":
                seed = Prompt.ask("  Client seed to inspect").strip()
                history = self.pf.get_nonce_history(seed)
                self.chart.render_nonce_history(history, seed[:16])
                input("\n  [dim]Press Enter...[/dim]")

    # ==================================================================
    # BEHAVIORAL ANALYTICS
    # ==================================================================

    def _menu_behavioral(self) -> None:
        """Behavioral analytics menu."""
        self.console.clear()
        self._print_header("BEHAVIORAL ANALYTICS")
        self.console.print("[dim]Neutral, scientific analysis of decision patterns.[/dim]\n")

        profile = self.behav.get_profile()
        report  = self.behav.get_alignment_report()

        self.chart.render_appetite_gauge(
            declared  = report["declared"],
            revealed  = report["revealed_score"],
            alignment = report["alignment"],
        )

        self.console.print(f"  [dim]{report['description']}[/dim]\n")

        stats_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        stats_table.add_column("Metric", style="dim blue", width=28)
        stats_table.add_column("Value",  width=20)

        stats_table.add_row("Total Decisions",          str(profile.total_decisions))
        stats_table.add_row("Over-stop Decisions",      str(profile.over_stop_decisions))
        stats_table.add_row("Optimal Exits",            str(profile.optimal_exits))
        stats_table.add_row("Early Exits",              str(profile.early_exits))
        stats_table.add_row("Mine Hits (busts)",        str(profile.busts))
        stats_table.add_row("Win Streak (max)",         str(profile.max_win_streak))
        stats_table.add_row("Loss Streak (max)",        str(profile.max_loss_streak))
        stats_table.add_row("Avg Picks / Round",        f"{profile.avg_picks_per_round:.2f}")
        stats_table.add_row("Continuation Rate",        format_percent(profile.continuation_rate))

        self.console.print(stats_table)

        obs = self.behav.get_observations()
        if obs:
            self.console.print("\n  [bold blue]Observations:[/bold blue]")
            for o in obs:
                self.console.print(f"    [dim]• {o}[/dim]")

        input("\n  [dim]Press Enter...[/dim]")

    # ==================================================================
    # SESSION REPORT
    # ==================================================================

    def _menu_session_report(self) -> None:
        """Display full session analytics report."""
        self.console.clear()
        self._print_header("SESSION REPORT")

        stats   = self.session.get_session_stats()
        profile = self.behav.get_profile()

        self.dash.render_session_summary(stats, profile)

        # Survival curve for each trap config played
        rounds = self.session.get_rounds()
        trap_counts_used = list(set(r.get("trap_count") for r in rounds if r.get("trap_count")))
        for tc in trap_counts_used:
            curve = self.prob.survival_curve(tc)
            self.heatmap.render_survival_curve(curve, tc)

        # Export option
        if Confirm.ask("\n  Export session report to JSON?", default=False):
            path = self.session.export_session(self.config.exports_dir)
            self.console.print(f"  [green]✓ Exported to {path}[/green]")

        input("\n  [dim]Press Enter...[/dim]")

    # ==================================================================
    # RESEARCH MODE
    # ==================================================================

    def _menu_research(self) -> None:
        """Research mode — exposes internals and calculations."""
        self.research.run_research_menu()

    # ==================================================================
    # SETTINGS
    # ==================================================================

    def _menu_settings(self) -> None:
        """Settings menu."""
        self.console.clear()
        self._print_header("SETTINGS")

        options = {
            "1": f"Default iterations: {self.config.get('monte_carlo_iter'):,}",
            "2": f"Animation speed:    {self.config.get('animation_speed')}s",
            "3": "Clear session data",
            "4": "View log file path",
            "B": "Back",
        }
        self._print_menu(options)
        choice = self._prompt_choice(list(options.keys()))

        if choice == "1":
            n = self._prompt_number("New default iterations (1000-100000)", 1000, 100000)
            self.config.set("monte_carlo_iter", n)
            self.console.print(f"  [green]Updated to {n:,}[/green]")
        elif choice == "2":
            s = float(Prompt.ask("Animation speed (seconds, e.g. 0.02)", default="0.03"))
            self.config.set("animation_speed", s)
        elif choice == "3":
            if Confirm.ask("  Clear all session data?", default=False):
                self.session.clear()
                self.console.print("  [green]Session data cleared.[/green]")
        elif choice == "4":
            from utils.logger import _LOG_PATH
            self.console.print(f"  Log file: [dim]{_LOG_PATH}[/dim]")

        time.sleep(1)

    # ==================================================================
    # SHARED HELPERS
    # ==================================================================

    def _print_header(self, title: str) -> None:
        self.console.print(
            Panel(
                f"[bold cyan]{title}[/bold cyan]",
                border_style = "cyan dim",
                padding      = (0, 2),
            )
        )

    def _print_menu(self, options: dict) -> None:
        """
        Render a menu dict to the terminal.
        Values may be either plain label strings or (label, handler) tuples.
        Only the label string is ever printed.
        """
        self.console.print()
        for key, value in options.items():
            # Safely extract just the display label whether value is a
            # plain string (sub-menus) or a (label, handler) tuple (main menu)
            label   = value[0] if isinstance(value, tuple) else value
            key_col = "bold cyan" if key not in ("B", "Q") else "dim"
            self.console.print(f"  [{key_col}][{key}][/{key_col}]  {label}")
        self.console.print()

    def _prompt_choice(self, valid: List[str]) -> str:
        while True:
            raw = Prompt.ask("  Choice").strip().upper()
            if raw in [v.upper() for v in valid]:
                return raw.upper()
            self.console.print(f"  [red]Invalid choice. Options: {', '.join(valid)}[/red]")

    def _prompt_number(self, label: str, lo: int, hi: int) -> int:
        while True:
            raw = Prompt.ask(f"  {label} ({lo}-{hi})")
            if raw.isdigit() and lo <= int(raw) <= hi:
                return int(raw)
            self.console.print(f"  [red]Enter a number between {lo} and {hi}.[/red]")

    def _prompt_trap_count(self) -> int:
        self.console.print(
            f"  Trap count [dim]({'/'.join(str(t) for t in VALID_TRAP_COUNTS)})[/dim]: ",
            end="",
        )
        while True:
            raw = input().strip()
            if raw.isdigit() and int(raw) in VALID_TRAP_COUNTS:
                return int(raw)
            self.console.print(
                f"  [red]Must be one of {VALID_TRAP_COUNTS}:[/red] ",
                end="",
            )

    def _prompt_iterations(self, default: int = None) -> int:
        default = default or self.config.get("monte_carlo_iter", 10000)
        raw = Prompt.ask(f"  Iterations", default=str(default))
        try:
            return max(100, int(raw))
        except ValueError:
            return default

    def _prompt_risk_profile(self) -> str:
        profiles = ["CONSERVATIVE", "BALANCED", "AGGRESSIVE", "ALL_IN"]
        self.console.print("  Risk profile:")
        for i, p in enumerate(profiles, 1):
            col = RISK_PROFILES[p]["color"]
            self.console.print(f"    [{col}]{i}. {p}[/{col}]")
        idx = self._prompt_number("Choice", 1, 4)
        return profiles[idx - 1]

    def _sim_progress(self, current: int, total: int) -> None:
        pct = current / total
        bar = progress_bar(pct, 20)
        self.console.print(f"  [cyan]{bar}[/cyan] {pct:.0%}", end="\r")

    def _quit(self) -> None:
        self.console.print("\n[dim cyan]Saving session data...[/dim cyan]")
        self.session.close()
        self.console.print("[dim cyan]Goodbye.[/dim cyan]\n")
        time.sleep(0.5)
