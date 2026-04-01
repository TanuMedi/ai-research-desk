import os

# arXiv settings
ARXIV_QUERY = "cat:cs.AI"
MAX_PAPERS = 30
DAYS_LOOKBACK = 7
AGENT_KEYWORDS = [
    # AI / agent terms
    "agent",
    "multi-agent",
    "autonomous",
    "tool use",
    "tool-use",
    "reasoning",
    "planning",
    "llm agent",
    "agentic",
    "self-improving",
    "task decomposition",
    # FinServ application areas
    "trading",
    "financial",
    "fintech",
    "compliance",
    "fraud",
    "risk management",
    "credit",
    "regulatory",
    "banking",
    "portfolio",
    "market making",
    "settlement",
    "kyc",
    "anti-money laundering",
]

# Storage
_ROOT = os.path.dirname(__file__)
DB_PATH = os.path.join(_ROOT, "storage", "memory.db")
OUTPUT_DIR = os.path.join(_ROOT, "outputs")
LOG_DIR = os.path.join(_ROOT, "storage", "logs")

# LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # "claude" | "openai"
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
LLM_MAX_TOKENS = 4096
LLM_TEMP_FIXED = 0.0      # critic, evaluation, summarizer
LLM_TEMP_LOW = 0.2        # planner
LLM_TEMP_HIGH = 0.7       # proposal generation

# Memory
MEMORY_WEEKS_LIMIT = 4  # only load ideas from the last N weeks to keep context manageable

# Novelty detection
NOVELTY_THRESHOLD = 0.30  # Jaccard similarity cutoff; above this → "incremental"

# Embeddings
EMBEDDING_MODEL = "text-embedding-3-small"

# Scoring weights (must sum to 1.0)
WEIGHT_NOVELTY = float(os.getenv("WEIGHT_NOVELTY", "0.40"))
WEIGHT_RELEVANCE = float(os.getenv("WEIGHT_RELEVANCE", "0.30"))
WEIGHT_REPO_READINESS = float(os.getenv("WEIGHT_REPO_READINESS", "0.30"))

# Reporting
REPORT_TOP_IDEAS_COUNT = 8  # how many top ideas per source to feature in the newsletter

# Agent loop
MAX_CYCLES = 2 # max plan→execute→critique cycles before stopping
# Cap past ideas sent to planner to avoid bloating the prompt;
# 20 covers ~5 weeks at 3-5 ideas/week, enough for novelty comparison.
MAX_PAST_IDEAS_FOR_PLANNING = 20

# GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
