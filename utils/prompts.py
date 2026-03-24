SUMMARIZE_PAPER_PROMPT = """You are an AI research analyst at a financial services firm. Analyze the following research paper and return a JSON object.

Paper Title: {title}
Abstract: {abstract}

Return ONLY valid JSON (no markdown, no explanation) with this exact structure:
{{
  "key_idea": "One sentence describing the core contribution",
  "methods": "One sentence describing the main methods or techniques used",
  "agent_relevance": true or false,
  "tags": ["tag1", "tag2", "tag3"]
}}

Set agent_relevance to true if the paper's techniques could be applied to financial services: trading systems, risk management, compliance automation, fraud detection, customer service, document processing, regulatory reporting, or operational workflows in banking/capital markets.
Tags should be 2-5 short keywords covering both the AI technique and potential financial application (e.g. "multi-agent trading", "LLM compliance", "fraud-detection", "document-extraction").
"""

GENERATE_PROPOSAL_PROMPT = """You are a technical product manager on an AI engineering team at a financial services firm (think JP Morgan, Bloomberg, UBS). Based on the following idea extracted from a research paper, write a demo proposal.

Idea Title: {idea_title}
Key Idea: {key_idea}
Methods: {methods}
Tags: {tags}
Novelty: {novelty_label}

Return ONLY valid JSON (no markdown, no explanation) with this exact structure:
{{
  "idea_title": "Short descriptive title for the demo",
  "why_it_matters": "2-3 sentences on value and impact for a FinServ AI team — reference concrete benefits like cost savings, risk reduction, regulatory compliance, faster processing, or operational efficiency",
  "novelty": "1-2 sentences on what makes this novel vs existing work",
  "demo_scope": "2-3 sentences describing a concrete MVP demo a FinServ AI engineering team could prototype in 2-4 weeks, using realistic financial data sources (market data APIs, sample transactions, regulatory filings, etc.)",
  "data_requirements": "1-2 sentences on what data, APIs, or datasets are needed, noting any compliance or data-privacy considerations relevant to financial services"
}}
"""
