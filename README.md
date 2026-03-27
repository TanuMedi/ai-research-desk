# AI Research Desk

## TL;DR

An end-to-end agentic AI system with a planner–executor loop that autonomously discovers, evaluates, and synthesizes GitHub and arXiv content into implementation-ready AI proposals using custom scoring and decision logic. Run it with `python main.py`.

---

## How it works
The system operates as an autonomous research agent with a planner–executor–critic loop that dynamically decides what to do next based on intermediate results.
```mermaid
flowchart TD
    A[Bootstrap: GitHub Retrieval] --> B[Planner (State-Aware)]
    B --> C[Execute Tool]
    C --> D[Update State]
    D --> B
    B --> E[Final Proposal]
```

### Plan → Execute → Critique cycle

The agent runs an iterative planner–executor–critic loop (up to `MAX_CYCLES`, default: 2), adapting its strategy based on intermediate results:

1. **Plan** — LLM generates an ordered list of steps from the goal, current state, available tools/skills, and past ideas
2. **Execute** — steps are dispatched to tools (external APIs) or skills (internal processing). The executor pauses after `github_search` completes, forcing a replan so the planner can reassess with updated state — e.g., skip arXiv if GitHub already found sufficient high-quality ideas
3. **Critique** — a sub-agent reviews proposals for specificity, feasibility, and differentiation. If improvements are needed, the cycle repeats

After the loop, evaluation runs (LLM-as-judge + tool efficiency metrics) and a newsletter is generated.

### Tools vs Skills vs Sub-agents

| Type | What it does | Examples |
|------|-------------|----------|
| **Tool** | Calls external APIs, registered in tool registry with MCP-style schemas | `github_search`, `arxiv_search`, `memory` |
| **Skill** | Internal processing, operates on state directly | `score_ideas`, `generate_proposals` |
| **Sub-agent** | Evaluates output quality | `critic` |

### Data sources

- **GitHub** (searched first) — repos for real implementations, computes leverage scores, summarizes into Ideas via LLM
- **arXiv** (fallback) — cs.AI papers, used when GitHub yields fewer than 3 ideas or novelty is low
- **Memory** — SQLite DB of past ideas for novelty comparison (capped to last 4 weeks)

### Scoring

Ideas are ranked using a weighted scoring framework: **novelty** (30%) + **leverage** (30%) + **relevance** (25%) + **feasibility** (15%), combining historical comparison, repository signals, and keyword alignment.

## Project structure

```
ai-research-desk/
├── agents/
│   ├── agent_loop.py          # Plan → Execute → Critique cycle
│   └── critic_agent.py        # Proposal quality sub-agent
├── tools/
│   ├── registry.py            # MCP-style tool registry
│   ├── github_tool.py         # GitHub search + Repo model + summarization
│   ├── arxiv_tool.py          # arXiv API + paper summarization
│   └── memory_tool.py         # SQLite persistence + novelty detection
├── skills/
│   ├── scoring.py             # Multi-factor idea scoring
│   └── proposal_generation.py # LLM proposal generation
├── models/
│   ├── paper.py               # arXiv paper model
│   ├── repo.py                # GitHub repo model
│   ├── idea.py                # Idea model (source-aware, with scores)
│   └── proposal.py            # Demo proposal model
├── executor/
│   ├── state_manager.py       # Shared agent state + status constants
│   └── tool_executor.py       # Tool invocation + logging
├── evaluation/
│   └── evaluator.py           # LLM-as-judge + efficiency metrics
├── utils/
│   ├── llm_client.py          # Claude / OpenAI async client
│   ├── summarizer.py          # LLM summarization (papers + repos)
│   ├── helpers.py             # Newsletter generation + file I/O
│   └── prompts.py             # All LLM prompt templates
├── storage/                   # SQLite DB + logs
├── outputs/                   # Generated newsletters
├── config.py                  # All configuration
├── main.py                    # Entry point
└── requirements.txt
```

## Setup

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Set your API key**

```bash
# For OpenAI (default)
export OPENAI_API_KEY=your_key_here

# For Claude (set LLM_PROVIDER=claude)
export ANTHROPIC_API_KEY=your_key_here
export LLM_PROVIDER=claude
```

Optional — for GitHub tool (higher rate limits):
```bash
export GITHUB_TOKEN=your_token_here
```

**3. Run**

```bash
python main.py
```

**4. (Optional) Create a shortcut**

```bash
alias research-desk="cd /path/to/ai-research-desk && python main.py"
```

## Configuration

All settings live in [config.py](config.py):

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `claude` or `openai` |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude model ID |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model ID |
| `LLM_MAX_TOKENS` | `4096` | Max tokens per LLM call |
| `MAX_CYCLES` | `2` | Max plan→execute→critique cycles |
| `ARXIV_QUERY` | `cat:cs.AI` | arXiv category/query |
| `MAX_PAPERS` | `30` | Max papers to fetch per run |
| `DAYS_LOOKBACK` | `7` | How many days back to search |
| `NOVELTY_THRESHOLD` | `0.30` | Jaccard similarity cutoff |
| `MEMORY_WEEKS_LIMIT` | `4` | Weeks of past ideas to load |
| `MAX_PAST_IDEAS_FOR_PLANNING` | `20` | Cap on past ideas in planner prompt |
| `REPORT_TOP_IDEAS_COUNT` | `8` | Ideas per source in newsletter |
| `GITHUB_TOKEN` | `""` | GitHub API token (env var) |

## Output

Each run produces:
- `outputs/latest_newsletter.md` — weekly digest with scores and proposals, split by source (arXiv / GitHub)
- `storage/logs/eval_<timestamp>.json` — evaluation scores (idea quality, proposal quality, tool efficiency)
- `storage/logs/week_<label>.json` — full data snapshot

See a sample output: [outputs/latest_newsletter.md](outputs/latest_newsletter.md)

## Design decisions

- **Plan → Execute → Critique cycles** — the agent dynamically plans which tools to call, executes them, then a critic sub-agent reviews output quality before the cycle repeats
- **Iterative planning with forced replanning checkpoint** — the executor pauses after `github_search` to force a replan with updated state, enabling conditional tool usage (e.g., skip arXiv if GitHub already found enough ideas)
- **Tools vs Skills** — tools call external APIs with MCP-style schemas; skills are internal processing that operate directly on state. This separation keeps the tool registry clean and skills composable
- **Source-aware ideas** — ideas track their origin (`arxiv` or `github`) through the `source` field, reflected in scoring, storage, and newsletter output
- **Multi-factor scoring** — combines novelty (Jaccard vs past ideas), leverage (GitHub repo signals), relevance (keyword match), and feasibility (repo completeness)
- **GitHub-first strategy** — GitHub repos are searched first for real implementations; arXiv is only used as a fallback when applied sources lack novelty
- **Evaluation framework** — LLM-as-judge rates output quality; tool efficiency (redundant calls, success rate) is tracked automatically
