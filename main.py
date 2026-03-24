import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.markdown import Markdown
from rich.table import Table

import agents.analysis_agent as analysis_agent
import agents.pm_agent as pm_agent
import agents.research_agent as research_agent
from models.report import RunReport
from tools.memory_tool import init_db, mark_demo_approved, store_weekly_ideas
from utils.helpers import generate_newsletter, save_outputs
from utils.llm_client import LLMClient

console = Console()


def print_report(report: RunReport) -> None:
    table = Table(title="Run Report", border_style="cyan", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Papers fetched", str(report.papers_fetched))
    table.add_row("Keyword matches", str(report.papers_keyword_matched))
    table.add_row("Summarized", str(report.papers_summarized))
    table.add_row("Failed summarization", str(report.papers_failed_summarization))
    table.add_row("Past ideas in memory", str(report.past_ideas_in_memory))
    table.add_row("Skipped (no key idea)", str(report.ideas_skipped_no_key_idea))
    table.add_row("Novel", str(report.ideas_novel))
    table.add_row("Incremental", str(report.ideas_incremental))
    table.add_row("Proposals generated", str(report.proposals_generated))
    table.add_row("Proposals approved", str(report.proposals_approved))

    console.print()
    console.print(table)


async def main() -> None:
    console.print(Panel.fit(
        "[bold magenta]AI Research Desk[/bold magenta]\n"
        "Weekly arXiv cs.AI digest for FinServ + demo proposal generator",
        border_style="magenta",
    ))

    if not Confirm.ask("\n[bold]Run this week's AI research cycle?[/bold]", default=True):
        console.print("Exiting. See you next week!")
        sys.exit(0)

    console.print()

    # Initialise DB, LLM, and report
    init_db()
    report = RunReport()
    try:
        llm = LLMClient()
    except ValueError as e:
        console.print(f"[red]✗ LLM configuration error: {e}[/red]")
        sys.exit(1)

    # --- Research Agent ---
    try:
        ideas = await research_agent.run(llm, report)
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch/summarize papers: {e}[/red]")
        sys.exit(1)

    if not ideas:
        console.print("[red]✗ No ideas to process. Exiting.[/red]")
        print_report(report)
        report.save()
        sys.exit(1)

    # --- Analysis Agent ---
    ranked = await analysis_agent.run(ideas, report)

    # --- PM Agent ---
    top2, proposals = await pm_agent.run(ranked, llm, report)

    # --- Persist to DB ---
    store_weekly_ideas(ranked)

    # --- Generate & Save Newsletter ---
    console.print("[bold cyan]→ Generating newsletter...[/bold cyan]")
    newsletter = generate_newsletter(ranked, top2, proposals)
    save_outputs(newsletter, ranked, top2, proposals)
    console.print("  Saved to [bold]outputs/latest_newsletter.md[/bold]")

    # --- Display Newsletter ---
    console.print()
    console.print(Panel(Markdown(newsletter), title="Weekly Newsletter", border_style="green"))

    # --- Approval Step ---
    console.print()
    if Confirm.ask("[bold]Approve these 2 ideas for demo exploration?[/bold]", default=False):
        mark_demo_approved([i.paper_title for i in top2])
        report.proposals_approved = len(top2)

    # --- Run Report ---
    print_report(report)
    report_path = report.save()
    console.print(f"  Report saved to [bold]{report_path}[/bold]")


if __name__ == "__main__":
    asyncio.run(main())
