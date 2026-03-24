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
DB_PATH = os.path.join(os.path.dirname(__file__), "storage", "memory.db")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
LOG_DIR = os.path.join(os.path.dirname(__file__), "storage", "logs")

# LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # "claude" | "openai"
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Novelty detection
NOVELTY_THRESHOLD = 0.30  # Jaccard similarity cutoff; above this → "incremental"

# Reporting
REPORT_TOP_PAPERS_COUNT = 8  # how many top papers to feature in the newsletter