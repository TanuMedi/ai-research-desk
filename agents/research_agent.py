from rich.console import Console

import config
from models.idea import Idea
from models.report import RunReport
from tools.arxiv_tool import fetch_recent_papers
from tools.summarizer_tool import summarize_papers_batch
from utils.llm_client import LLMClient

console = Console()


async def run(llm: LLMClient, report: RunReport) -> list[Idea]:
    """
    Fetch papers from arXiv, summarize them concurrently, and return
    agent-relevant ideas.
    """
    console.print("[bold cyan]→ Fetching papers from arXiv...[/bold cyan]")
    papers = await fetch_recent_papers()
    report.papers_fetched = len(papers)

    if not papers:
        console.print("[yellow]⚠ No papers found. Check your network or arXiv availability.[/yellow]")
        return []

    # Pre-filter by keywords before spending LLM calls
    relevant_papers = [
        p for p in papers
        if any(kw in (p.title + " " + p.summary).lower() for kw in config.AGENT_KEYWORDS)
    ]
    report.papers_keyword_matched = len(relevant_papers)

    if not relevant_papers:
        console.print("[yellow]⚠ No papers matched agent keywords this week.[/yellow]")
        return []

    console.print(f"  Summarizing [bold]{len(relevant_papers)}[/bold] papers...")
    ideas = await summarize_papers_batch(relevant_papers, llm)
    report.papers_summarized = len(ideas)
    report.papers_failed_summarization = len(relevant_papers) - len(ideas)

    return ideas
