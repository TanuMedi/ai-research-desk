from rich.console import Console

from models.idea import Idea
from models.report import RunReport
from tools.memory_tool import classify_novelty, get_past_ideas

console = Console()


async def run(ideas: list[Idea], report: RunReport) -> list[Idea]:
    """
    Load past ideas, classify novelty for each new idea via Jaccard similarity,
    then rank by novelty (novel > incremental) and tag count.
    """
    console.print("[bold cyan]→ Running novelty analysis...[/bold cyan]")
    past_ideas = get_past_ideas()
    report.past_ideas_in_memory = len(past_ideas)

    scored_ideas = []
    skipped = 0
    for idea in ideas:
        result = classify_novelty(idea, past_ideas)
        if result is None:
            skipped += 1
            continue
        idea.novelty_score, idea.novelty_label = result
        scored_ideas.append(idea)

    report.ideas_skipped_no_key_idea = skipped
    report.ideas_novel = sum(1 for i in scored_ideas if i.novelty_label == "novel")
    report.ideas_incremental = sum(1 for i in scored_ideas if i.novelty_label == "incremental")

    # Rank: novel first, then by tag count (more tags = more specific/interesting)
    ranked = sorted(
        scored_ideas,
        key=lambda i: (i.novelty_label == "novel", len(i.tags)),
        reverse=True,
    )
    return ranked
