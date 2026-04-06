IDEA_PROPOSAL_PROMPT = """You are an AI research analyst at a financial services firm. Analyze the following github repo or research paper and return a JSON object.

Title: {title}
Overview: {abstract}

Return ONLY valid JSON (no markdown, no explanation) with this exact structure:
{{
  "key_idea": "One sentence describing the core contribution",
  "methods": "One sentence describing the main methods or techniques used",
  "agent_relevance": true or false,
  "tags": ["tag1", "tag2", "tag3"]
}}

Set agent_relevance to true if the mentioned techniques could be applied to financial services: trading systems, risk management, compliance automation, fraud detection, customer service, document processing, regulatory reporting, or operational workflows in banking/capital markets.
Tags should be 2-5 short keywords covering both the AI technique and potential financial application (e.g. "multi-agent trading", "LLM compliance", "fraud-detection", "document-extraction").
"""

GENERATE_PROPOSAL_PROMPT = """You are a technical product manager on an AI engineering team at a financial services firm (think JP Morgan, Bloomberg, UBS). Based on the following idea extracted, write a demo proposal.

Idea Title: {idea_title}
Key Idea: {key_idea}
Methods: {methods}
Tags: {tags}

Return ONLY valid JSON (no markdown, no explanation) with this exact structure:
{{
  "idea_title": "Short descriptive title for the demo",
  "why_it_matters": "2-3 sentences on value and impact for a FinServ AI team — reference concrete benefits like cost savings, risk reduction, regulatory compliance, faster processing, or operational efficiency",
  "demo_scope": "2-3 sentences describing a concrete MVP demo a FinServ AI engineering team could prototype in 2-4 weeks, using realistic financial data sources (market data APIs, sample transactions, regulatory filings, etc.)",
  "data_requirements": "1-2 sentences on what data, APIs, or datasets are needed, noting any compliance or data-privacy considerations relevant to financial services"
}}
"""

# ---------------------------------------------------------------------------
# V2 — Planner Prompt
# ---------------------------------------------------------------------------

PLANNER_PROMPT = """
You are an AI research agent planner.

Your goal is:
{goal}

Current state:
{state_summary}

Available tools:
{tool_schemas}

Available skills (internal processing, not tools):
- score_ideas: Score and rank ideas using multi-factor scoring (novelty, relevance, repo_readiness). Use after ideas are gathered. Produces: scored_ideas, selected_ideas.
- generate_proposals: Generate demo proposals for selected ideas via LLM. Use after scoring. Produces: proposals.

Past ideas from memory (for novelty comparison):
{memory_context}

Generate an ordered plan of actions to achieve the goal from the current state.

Guidelines:
- NEVER call a search tool (github_search or arxiv_search) if ideas already exist in state (ideas_count >= 3)
- Avoid redundant tool calls — do not re-search a source that already produced results in state
- Each step must use a valid action name from the available tools or skills listed above
- Do NOT include "critic" or "STOP" as plan steps — those are handled automatically
- If ideas already exist in state, proceed directly to scoring and proposal generation
- If no ideas exist, begin with GitHub search
- Only use arXiv if GitHub yields fewer than 3 ideas or quality signals show low novelty
- Search for general AI ideas first — do not filter by domain during data gathering
- Domain relevance (e.g. financial services) is assessed separately during scoring
- Prefer GitHub for real implementations and applied techniques
- After ideas are gathered, include a scoring step
- After scoring, include proposal generation

Return ONLY valid JSON (no markdown, no backticks):
{{
  "steps": [
    {{"action": "tool_or_skill_name", "input": {{}}, "reasoning": "why this step"}}
  ]
}}
"""

# ---------------------------------------------------------------------------
# V2 — Critic Prompt
# ---------------------------------------------------------------------------

CRITIC_PROMPT = """You are a senior AI strategist reviewing demo proposals for a financial services firm.

PROPOSALS:
{proposals_json}

SCORES:
{scores_json} 

Evaluate each proposal on:
1. Specificity — is the demo scope concrete and actionable?
2. Feasibility — can an engineering team prototype this in 2-4 weeks?
3. Differentiation — does it offer something genuinely new vs existing tools?

Return ONLY valid JSON (no markdown, no explanation):
{{
  "needs_improvement": true or false,
  "issues": ["list of specific issues found"],
  "suggestions": ["list of actionable improvement suggestions"]
}}

Set needs_improvement to true only if there are real problems. Be constructive, not perfectionistic.
"""

# ---------------------------------------------------------------------------
# V2 — Evaluation Prompts
# ---------------------------------------------------------------------------

EVALUATE_IDEA_PROMPT = """Rate the following AI idea for financial services application.

Idea: {key_idea}
Methods: {methods}
Tags: {tags}

Return ONLY valid JSON (no markdown, no explanation):
{{
  "actionability": <1-5>,
  "novelty": <1-5>,
  "usefulness": <1-5>
}}
"""

EVALUATE_PROPOSAL_PROMPT = """Rate the following demo proposal for a FinServ AI team.

Title: {idea_title}
Why it matters: {why_it_matters}
Demo scope: {demo_scope}
Data requirements: {data_requirements}

Return ONLY valid JSON (no markdown, no explanation):
{{
  "clarity": <1-5>,
  "feasibility": <1-5>,
  "completeness": <1-5>
}}
"""

