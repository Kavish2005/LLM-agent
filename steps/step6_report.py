"""
Step 6 — LLM: Generate Final Structured Report.

Why this is a separate step:
  The previous five steps produced JSON fragments — useful for the agent's internal
  reasoning but not directly readable. This step's sole job is synthesis and
  presentation: taking all structured outputs and producing a coherent, professional
  document a real user can act on. Separating synthesis from analysis keeps each
  LLM call focused on a single cognitive task.

System prompt design notes:
  - The system role switches to "research writer" to prime fluent prose output.
  - Section headers are specified in the prompt to ensure consistent structure
    across different stocks and queries. Without this constraint, early versions
    produced arbitrarily ordered sections.
  - The final recommendation and risk rating are explicitly injected into the prompt
    to guarantee they appear prominently — without this, the LLM buried them in
    flowing prose where users missed them.
  - temperature=0.6 here allows slightly more natural prose while the structured
    sections prevent drift.
"""

import json
import anthropic
from utils import llm_call, log_step


SYSTEM_PROMPT = """You are a senior investment research writer. Synthesise all provided analysis into
a professional equity research brief that a portfolio manager can act on directly.

Write in polished financial prose. Use the section headers below exactly as written.
Cite specific numbers where available. Be direct about the recommendation.

Required sections (use these exact headers in this order):
## Executive Summary
## Company Overview
## Financial Analysis
## Investment Thesis
## Risk Assessment
## Key Metrics to Monitor
## Conclusion & Recommendation

Do not include a disclaimer beyond one line at the very end."""


def step6_generate_report(client: anthropic.Anthropic, state: dict) -> dict:
    """
    Input:  state["financial_data"]        — from Step 2
            state["fundamental_analysis"]  — from Step 3
            state["investment_thesis"]     — from Step 4
            state["thesis_critique"]       — from Step 5
            state["parsed_query"]          — user's original questions (Step 1)
    Output: state["final_report"] — Markdown string (the deliverable)
    """
    log_step(6, "Synthesise final report")

    fin = state["financial_data"]
    pq = state["parsed_query"]
    thesis = state["investment_thesis"]
    critique = state["thesis_critique"]

    # Highlight the key signal figures in the prompt to ensure they surface in the report
    headline_figures = {
        "current_price": fin.get("current_price"),
        "market_cap": fin.get("market_cap"),
        "pe_ratio": fin.get("pe_ratio"),
        "revenue_growth_yoy": fin.get("revenue_growth_yoy"),
        "profit_margins": fin.get("profit_margins"),
        "debt_to_equity": fin.get("debt_to_equity"),
        "return_on_equity": fin.get("return_on_equity"),
        "analyst_target_price": fin.get("analyst_target_price"),
        "price_change_3m_pct": fin.get("price_change_3m_pct"),
        "beta": fin.get("beta"),
        "dividend_yield": fin.get("dividend_yield"),
    }

    user_prompt = f"""Write a full equity research brief for {fin.get('company_name')} ({fin.get('ticker')}).

━━━ KEY SIGNAL FIGURES (cite these, do not invent alternatives) ━━━
{json.dumps(headline_figures, indent=2)}

━━━ USER'S ORIGINAL QUESTIONS ━━━
{json.dumps(pq.get('key_questions', []), indent=2)}

━━━ RECOMMENDATION (must appear in Executive Summary and Conclusion) ━━━
Action     : {thesis.get('recommended_action', 'N/A').upper()}
Stance     : {thesis.get('overall_stance', 'N/A')}
Conviction : {thesis.get('conviction_level', 'N/A')}
Risk Rating: {critique.get('final_risk_rating', 'N/A').upper()}
Validity   : {critique.get('thesis_validity_score', 'N/A')}/10

━━━ FUNDAMENTAL ANALYSIS (Step 3) ━━━
{json.dumps(state['fundamental_analysis'], indent=2)}

━━━ INVESTMENT THESIS (Step 4) ━━━
{json.dumps(thesis, indent=2)}

━━━ RISK CRITIQUE (Step 5) ━━━
{json.dumps(critique, indent=2)}

━━━ SECTOR & INDUSTRY ━━━
{fin.get('sector')} → {fin.get('industry')}

Business overview: {fin.get('business_summary', 'N/A')}

Recent news: {json.dumps([n['title'] for n in fin.get('recent_news', [])])}

Now write the full research brief with all required sections."""

    raw = llm_call(client, SYSTEM_PROMPT, user_prompt, temperature=0.6)
    state["final_report"] = raw

    print(f"  Report length : {len(raw):,} characters")
    return state
