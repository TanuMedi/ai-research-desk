# AI Research Desk (MVP)

A weekly arXiv `cs.AI` digest and demo proposal generator powered by a multi-agent pipeline.

Every run fetches the latest AI research papers, filters for agentic/reasoning topics, ranks them by novelty, selects the top candidates, and produces a newsletter with demo proposals — all in one command.

## How it works

```
Research Agent → Analysis Agent → PM Agent → Newsletter + Memory
```

1. **Research Agent** — queries arXiv for `cs.AI` papers from the past 7 days, filters by agent-related keywords, and summarizes each paper via LLM.
2. **Analysis Agent** — scores and ranks the summarized ideas by novelty (Jaccard similarity against past ideas stored in SQLite).
3. **PM Agent** — selects the top 2 ideas and generates structured demo proposals.
4. **Output** — saves a Markdown newsletter to `outputs/latest_newsletter.md` and persists ideas to the local SQLite memory.

## Project structure

```
ai-research-desk/
├── agents/
│   ├── research_agent.py    # arXiv fetch + summarize
│   ├── analysis_agent.py    # novelty scoring + ranking
│   └── pm_agent.py          # top-2 selection + proposal generation
├── models/
│   ├── paper.py             # Paper dataclass
│   ├── idea.py              # Idea dataclass
│   └── proposal.py          # Proposal dataclass
├── tools/
│   ├── arxiv_tool.py        # arXiv API wrapper
│   ├── summarizer_tool.py   # LLM summarization
│   ├── proposal_tool.py     # LLM proposal generation
│   └── memory_tool.py       # SQLite persistence
├── utils/
│   ├── llm_client.py        # Claude / OpenAI client
│   ├── helpers.py           # Newsletter generation + file I/O
│   └── prompts.py           # LLM prompt templates
├── storage/                 # SQLite DB + logs (gitignored)
├── outputs/                 # Generated newsletters (gitignored)
├── config.py                # All configuration constants
├── main.py                  # Entry point
└── requirements.txt
```

## Setup

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Set your API key**

Create a `.env` file in the project root (this file is gitignored):

For Claude (default):
```bash
echo "ANTHROPIC_API_KEY=your_key_here" > .env
```

For OpenAI (also set `LLM_PROVIDER = "openai"` in `config.py`):
```bash
echo "OPENAI_API_KEY=your_key_here" > .env
```

**3. Run**

```bash
source .env && python main.py
```

**4. (Optional) Create a shortcut**

Add this alias to your `~/.zshrc` so you can run `research-desk` from anywhere:

```bash
alias research-desk="cd /path/to/ai-research-desk && source .env && python main.py"
```

Then reload your shell: `source ~/.zshrc`

You'll be prompted to confirm before each run, and again to approve the top 2 ideas for demo exploration.

## Configuration

All settings live in [config.py](config.py):

| Variable | Default | Description |
|---|---|---|
| `ARXIV_QUERY` | `cat:cs.AI` | arXiv category/query |
| `MAX_PAPERS` | `30` | Max papers to fetch per run |
| `DAYS_LOOKBACK` | `7` | How many days back to search |
| `LLM_PROVIDER` | `claude` | `claude` or `openai` |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude model ID |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model ID |
| `NOVELTY_THRESHOLD` | `0.35` | Jaccard similarity cutoff for novelty |

## Output

Each run saves to `outputs/`:
- `latest_newsletter.md` — the full weekly digest with summaries and proposals

Approved ideas are flagged in the SQLite database at `storage/memory.db` for deduplication in future runs.
