import asyncio

from rich.console import Console

from models.idea import Idea
from models.proposal import Proposal
from models.report import RunReport
from tools.proposal_tool import generate_proposal
from utils.llm_client import LLMClient

console = Console()


async def run(
    ranked_ideas: list[Idea], llm: LLMClient, report: RunReport
) -> tuple[list[Idea], list[Proposal]]:
    """
    Select top 2 ideas and generate demo proposals for each concurrently.
    """
    console.print("[bold cyan]→ Selecting top 2 ideas and generating proposals...[/bold cyan]")
    top2 = ranked_ideas[:2]

    report.top_picks = [i.paper_title for i in top2]

    proposals = list(await asyncio.gather(*[generate_proposal(i, llm) for i in top2]))
    report.proposals_generated = len(proposals)
    return top2, proposals
