"""
Step 4 — LLM: Investment Thesis Construction.

Why this is a separate step from Step 3 (analysis):
  The fundamental analysis (Step 3) is backward-looking: it describes what the
  numbers say about the company today. The thesis is forward-looking: it argues
  what those numbers imply about future returns. Forcing a step boundary prevents
  the LLM from conflating "the margin is high" (fact) with "therefore buy" (claim).
  In testing, a single combined step produced conclusions that were not grounded in
  the analysis — the LLM would skip straight to a stance without working through
  the evidence. Separating the steps fixes this.

System prompt design notes:
  - The explicit bull/bear structure enforces balanced analysis. Early versions of
    this prompt without that structure produced uniformly bullish outputs even for
    weak financials.
  - "conviction_level" was added after testing showed the recommendation alone was
    insufficient — two "buy" recommendations can represent very different confidence
    levels depending on the data quality.
  - The schema anchors Step 5's critique: the challenger LLM will receive this exact
    JSON and challenge each named assumption.
"""

import json
import anthropic
from utils import llm_call, extract_json, log_step


SYSTEM_PROMPT = """You are a portfolio manager constructing an investment thesis.
Given a fundamental analysis and supporting financial data, build a balanced bull and bear case.

Respond with valid JSON only — no markdown, no prose. Use exactly this schema:

{
  "overall_stance": "<bullish | bearish | neutral>",
  "conviction_level": "<high | medium | low>",
  "investment_summary": "<1-2 sentence plain-English summary of your position>",
  "bull_case": {
    "narrative": "<2-3 sentence argument for why the stock could outperform>",
    "catalysts": ["<catalyst 1>", "<catalyst 2>", "..."],
    "upside_target_rationale": "<brief explanation of what would drive price higher>"
  },
  "bear_case": {
    "narrative": "<2-3 sentence argument for why the stock could underperform>",
    "risks": ["<risk 1>", "<risk 2>", "..."],
    "downside_scenario": "<brief description of a realistic negative outcome>"
  },
  "key_assumptions": ["<assumption the thesis rests on 1>", "..."],
  "key_monitoring_metrics": ["<what to watch 1>", "..."],
  "recommended_action": "<buy | accumulate | hold | reduce | avoid>",
  "position_sizing_suggestion": "<small | medium | large | none>"
}

Rules:
- bull_case.catalysts and bear_case.risks must each have 2-4 items.
- key_assumptions must have 3-5 items — these will be stress-tested in the next step.
- Do not recommend "buy" with low conviction; use "accumulate" instead.
- Position sizing must match conviction: high→medium/large, low→small/none."""


def step4_investment_thesis(client: anthropic.Anthropic, state: dict) -> dict:
    """
    Input:  state["fundamental_analysis"] — from Step 3
            state["financial_data"]        — from Step 2 (for context)
            state["parsed_query"]          — user's time horizon and focus (from Step 1)
    Output: state["investment_thesis"] — structured thesis dict
    """
    log_step(4, "Investment thesis construction")

    fin = state["financial_data"]
    analysis = state["fundamental_analysis"]
    pq = state["parsed_query"]

    # Price context for the thesis
    price_context = {
        "current_price": fin.get("current_price"),
        "analyst_target_price": fin.get("analyst_target_price"),
        "price_change_3m_pct": fin.get("price_change_3m_pct"),
        "beta": fin.get("beta"),
        "fifty_two_week_high": fin.get("fifty_two_week_high"),
        "fifty_two_week_low": fin.get("fifty_two_week_low"),
    }

    user_prompt = f"""Build an investment thesis for {fin.get('company_name')} ({fin.get('ticker')}).

Context:
  Sector       : {fin.get('sector')}
  Analysis focus: {pq.get('analysis_focus')}
  Time horizon  : {pq.get('time_horizon')}

Price & analyst data:
{json.dumps(price_context, indent=2)}

Business overview (truncated):
{fin.get('business_summary', 'N/A')}

Fundamental analysis (from Step 3):
{json.dumps(analysis, indent=2)}

Construct a balanced bull and bear investment thesis as JSON."""

    raw = llm_call(client, SYSTEM_PROMPT, user_prompt, temperature=0.4)
    thesis = extract_json(raw)

    if "overall_stance" not in thesis:
        thesis = {
            "overall_stance": "neutral",
            "conviction_level": "low",
            "investment_summary": raw,
            "bull_case": {"narrative": "", "catalysts": [], "upside_target_rationale": ""},
            "bear_case": {"narrative": "", "risks": [], "downside_scenario": ""},
            "key_assumptions": [],
            "key_monitoring_metrics": [],
            "recommended_action": "hold",
            "position_sizing_suggestion": "small",
        }
        print("  [warn] JSON extraction failed; stored raw response.")

    state["investment_thesis"] = thesis

    print(f"  Stance      : {thesis.get('overall_stance')}")
    print(f"  Conviction  : {thesis.get('conviction_level')}")
    print(f"  Action      : {thesis.get('recommended_action')}")
    print(f"  Assumptions : {len(thesis.get('key_assumptions', []))} to be stress-tested in Step 5")

    return state
