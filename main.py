import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table

import config
from agents.agent_loop import run_init_phase, run_agent_loop
from evaluation.evaluator import evaluate_run
from tools.memory_tool import init_db
from tools.registry import build_default_registry
from utils.helpers import generate_newsletter, save_outputs
from utils.llm_client import LLMClient

console = Console()

DEFAULT_GOAL = (
    "Find 3-5 high-quality applied AI ideas from GitHub repos and arXiv papers."
    "Once you have identified potential ideas, assess them to see if they can be applied to financial services "
    "(trading, compliance, fraud detection, document processing)."
    "Ideas should be feasible, novel, and have clear business impact. "
    "Score and rank them, then generate demo proposals for the top 2."
)


def print_scores_table(scored_ideas: list) -> None:
    table = Table(title="Scored Ideas", border_style="cyan", show_lines=True)
    table.add_column("Rank", style="bold", width=4)
    table.add_column("Title", max_width=40)
    table.add_column("Final", justify="right")
    table.add_column("Novelty", justify="right")
    table.add_column("Relevance", justify="right")
    table.add_column("Repo Ready", justify="right")

    for i, idea in enumerate(scored_ideas[:8], 1):
        table.add_row(
            str(i),
            getattr(idea, "source_title", "")[:40],
            f"{getattr(idea, 'final_score', 0):.2f}",
            f"{getattr(idea, 'novelty_score', 0):.2f}",
            f"{getattr(idea, 'relevance_score', 0):.2f}",
            f"{getattr(idea, 'repo_readiness_score', 0):.2f}",
        )

    console.print()
    console.print(table)


def print_eval_table(evaluation: dict) -> None:
    table = Table(title="Evaluation Results", border_style="magenta", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    idea_q = evaluation.get("idea_quality", {})
    table.add_row("Idea quality (avg)", str(idea_q.get("average", "N/A")))

    proposal_q = evaluation.get("proposal_quality", {})
    table.add_row("Proposal quality (avg)", str(proposal_q.get("average", "N/A")))

    eff = evaluation.get("tool_efficiency", {})
    table.add_row("Tool calls (total)", str(eff.get("total_calls", 0)))
    table.add_row("Tool calls (successful)", str(eff.get("successful_calls", 0)))
    table.add_row("Tool calls (redundant)", str(eff.get("redundant_calls", 0)))
    table.add_row("Efficiency ratio", str(eff.get("efficiency_ratio", 0)))

    console.print()
    console.print(table)


async def main() -> None:
    console.print(Panel.fit(
        "[bold magenta]AI Research Desk v2[/bold magenta]\n"
        "Agentic AI research system with MCP-style tools",
        border_style="magenta",
    ))

    # --- Initialize ---
    init_db()
    try:
        llm_fixed = LLMClient(temperature=config.LLM_TEMP_FIXED)   # critic, evaluation, summarizer
        llm_low = LLMClient(temperature=config.LLM_TEMP_LOW)       # planner
        llm_high = LLMClient(temperature=config.LLM_TEMP_HIGH)     # proposal generation
    except ValueError as e:
        console.print(f"[red]✗ LLM configuration error: {e}[/red]")
        sys.exit(1)

    registry = build_default_registry()
    console.print(f"[green]✓ Registered {len(registry.list_tools())} tools[/green]")

    # --- Run Pipeline ---
    llms = {"fixed": llm_fixed, "low": llm_low, "high": llm_high}

    try:
        console.print(Panel.fit(
            "[bold cyan]Starting init phase...[/bold cyan]",
            border_style="cyan",
        ))
        state = await run_init_phase(DEFAULT_GOAL, llms, registry)

        console.print(Panel.fit(
            "[bold magenta]Starting refinement loop...[/bold magenta]",
            border_style="magenta",
        ))
        state = await run_agent_loop(state, registry)
    except Exception as e:
        console.print(f"[red]✗ Pipeline failed: {e}[/red]")
        sys.exit(1)

    # --- Results ---
    ideas = state.get("ideas", [])
    scored = state.get("scored_ideas", [])
    selected = state.get("selected_ideas", [])
    proposals = state.get("proposals", [])

    if not ideas:
        console.print("[red]✗ No ideas found. Try adjusting the goal or sources.[/red]")
        sys.exit(1)

    # Display scores
    if scored:
        print_scores_table(scored)

    # Generate & display newsletter
    if selected and proposals:
        console.print("\n[bold cyan]→ Generating newsletter...[/bold cyan]")
        newsletter = generate_newsletter(scored or ideas, selected, proposals)
        save_outputs(newsletter, scored or ideas, selected, proposals)
        console.print("  Saved to [bold]outputs/latest_newsletter.md[/bold]")
        console.print()
        console.print(Panel(Markdown(newsletter), title="Weekly Newsletter", border_style="green"))

    # --- Evaluation ---
    console.print("\n[bold cyan]→ Running evaluation...[/bold cyan]")
    evaluation = await evaluate_run(state, llm_fixed)
    state["evaluation"] = evaluation
    print_eval_table(evaluation)

    console.print("\n[bold green]✓ Run complete![/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
