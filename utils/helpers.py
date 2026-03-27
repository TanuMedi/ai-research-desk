import json
import os
from datetime import datetime, timezone

import config
from models.idea import Idea
from models.proposal import Proposal


def current_week_label() -> str:
    """Return week label, e.g. '2026-Mar-W12'."""
    now = datetime.now(timezone.utc)
    return f"{now.year}-{now.strftime('%b')}-W{now.isocalendar().week:02d}"


def generate_newsletter(
    all_ideas: list[Idea],
    top2: list[Idea],
    proposals: list[Proposal],
) -> str:
    week = current_week_label()
    lines = [f"# Weekly AI Research Digest — {week}", ""]

    # Top ideas by source
    arxiv_ideas = [i for i in all_ideas if i.source == "arxiv"]
    github_ideas = [i for i in all_ideas if i.source == "github"]

    if arxiv_ideas:
        lines.append("## Top Papers")
        lines.append("")
        for idea in arxiv_ideas[:config.REPORT_TOP_IDEAS_COUNT]:
            lines.append(f"- **[{idea.source_title}]({idea.source_link})**")
            lines.append(f"  {idea.key_idea}")
            lines.append("")

    if github_ideas:
        lines.append("## Top Repos")
        lines.append("")
        for idea in github_ideas[:config.REPORT_TOP_IDEAS_COUNT]:
            lines.append(f"- **[{idea.source_title}]({idea.source_link})**")
            lines.append(f"  {idea.key_idea}")
            lines.append("")

    # Key Trends (tags frequency)
    lines.append("## Key Trends")
    lines.append("")
    tag_counts: dict[str, int] = {}
    for idea in all_ideas:
        for tag in idea.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    for tag, count in top_tags:
        lines.append(f"- **{tag}** ({count} ideas)")
    lines.append("")

    # Selected Ideas for Demo
    lines.append("## Selected Ideas for Demo")
    lines.append("")
    for i, idea in enumerate(top2, 1):
        lines.append(f"### Idea {i}: {idea.source_title}")
        lines.append("")
        lines.append(f"**Key Idea:** {idea.key_idea}")
        lines.append("")
        lines.append(f"**Methods:** {idea.methods}")
        lines.append("")
        lines.append(f"**Novelty:** {idea.novelty_label.capitalize()} (similarity score: {idea.novelty_score:.2f})")
        lines.append("")
        lines.append(f"**Tags:** {', '.join(idea.tags)}")
        lines.append("")
        source_label = "arXiv" if idea.source == "arxiv" else "GitHub"
        lines.append(f"**Source:** [{idea.source_title}]({idea.source_link}) ({source_label})")
        lines.append("")
        lines.append(f"> {idea.source_summary[:300].rstrip()}...")
        lines.append("")

    # Proposed Demos
    lines.append("## Proposed Demos")
    lines.append("")
    for i, proposal in enumerate(proposals, 1):
        lines.append(f"### Demo {i}: {proposal.idea_title}")
        lines.append("")
        lines.append(f"**Why it matters:** {proposal.why_it_matters}")
        lines.append("")
        lines.append(f"**Novelty:** {proposal.novelty}")
        lines.append("")
        lines.append(f"**Demo scope:** {proposal.demo_scope}")
        lines.append("")
        lines.append(f"**Data requirements:** {proposal.data_requirements}")
        lines.append("")

    return "\n".join(lines)


def save_outputs(
    newsletter: str,
    all_ideas: list[Idea],
    top2: list[Idea],
    proposals: list[Proposal],
) -> None:
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.LOG_DIR, exist_ok=True)

    week = current_week_label()

    # Save newsletter 
    latest_path = os.path.join(config.OUTPUT_DIR, "latest_newsletter.md")
    with open(latest_path, "w") as f:
        f.write(newsletter)

    # Save weekly JSON log
    log_data = {
        "week": week,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "all_ideas": [i.model_dump() for i in all_ideas],
        "top2": [i.model_dump() for i in top2],
        "proposals": [p.model_dump() for p in proposals],
    }
    log_path = os.path.join(config.LOG_DIR, f"week_{week}.json")
    with open(log_path, "w") as f:
        json.dump(log_data, f, indent=2, default=str)
