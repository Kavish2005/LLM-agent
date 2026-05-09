"""
Step 3 — LLM: Fundamental Analysis.

Why this is a separate step from Step 4 (thesis):
  Analysis and thesis are cognitively distinct tasks. Analysis answers "what do the
  numbers say?" — it is descriptive and rooted in data. The thesis in Step 4 answers
  "what should I do about it?" — it is prescriptive and forward-looking. Separating
  them prevents the LLM from jumping to conclusions before examining the data
  carefully, which in testing produced more calibrated and nuanced outputs.

System prompt design notes:
  - The JSON schema forces the LLM to produce categorised outputs (strengths vs.
    weaknesses) rather than prose that buries the key findings.
  - "valuation_assessment" is constrained to three values so Step 4 can use it
    programmatically in its prompt without re-parsing.
  - "data_quality_note" was added after early testing showed the LLM sometimes
    ignoring missing fields. The explicit field forces acknowledgement.
  - Including the user's key_questions ensures the analysis is targeted, not generic.
"""

import json
import anthropic
from utils import llm_call, extract_json, log_step


SYSTEM_PROMPT = """You are a senior equity analyst performing fundamental analysis on real financial data.

Respond with valid JSON only — no markdown, no prose. Use exactly this schema:

{
  "valuation_assessment": "<undervalued | fairly_valued | overvalued>",
  "valuation_reasoning": "<2-3 sentence explanation citing specific metrics>",
  "financial_strengths": ["<strength 1>", "<strength 2>", "..."],
  "financial_weaknesses": ["<weakness 1>", "<weakness 2>", "..."],
  "key_metrics_summary": {
    "profitability": "<concise assessment>",
    "growth": "<concise assessment>",
    "liquidity": "<concise assessment>",
    "leverage": "<concise assessment>"
  },
  "competitive_position": "<2-sentence assessment of competitive moat and sector standing>",
  "red_flags": ["<flag 1>", "..."],
  "data_quality_note": "<note any missing or suspicious data fields and their potential impact>"
}

Rules:
- Base every claim on the numbers provided. Do not hallucinate metrics.
- If a metric is missing (null / N/A), say so in data_quality_note rather than estimating.
- financial_strengths and financial_weaknesses must each have 2-5 items."""


def step3_fundamental_analysis(client: anthropic.Anthropic, state: dict) -> dict:
    """
    Input:  state["financial_data"]  — from Step 2 tool call
            state["parsed_query"]    — user's focus and questions (from Step 1)
    Output: state["fundamental_analysis"] — structured analysis dict
    """
    log_step(3, "Fundamental analysis")

    fin = state["financial_data"]
    pq = state["parsed_query"]

    # Build a concise snapshot of key figures to keep the prompt tight
    metrics_snapshot = {
        "pe_ratio": fin.get("pe_ratio"),
        "forward_pe": fin.get("forward_pe"),
        "peg_ratio": fin.get("peg_ratio"),
        "price_to_book": fin.get("price_to_book"),
        "ev_to_ebitda": fin.get("ev_to_ebitda"),
        "revenue_growth_yoy": fin.get("revenue_growth_yoy"),
        "earnings_growth_yoy": fin.get("earnings_growth_yoy"),
        "gross_margins": fin.get("gross_margins"),
        "operating_margins": fin.get("operating_margins"),
        "profit_margins": fin.get("profit_margins"),
        "return_on_equity": fin.get("return_on_equity"),
        "return_on_assets": fin.get("return_on_assets"),
        "debt_to_equity": fin.get("debt_to_equity"),
        "current_ratio": fin.get("current_ratio"),
        "quick_ratio": fin.get("quick_ratio"),
        "dividend_yield": fin.get("dividend_yield"),
        "payout_ratio": fin.get("payout_ratio"),
        "beta": fin.get("beta"),
        "analyst_target_price": fin.get("analyst_target_price"),
        "analyst_recommendation_mean": fin.get("analyst_recommendation_mean"),
        "fifty_two_week_high": fin.get("fifty_two_week_high"),
        "fifty_two_week_low": fin.get("fifty_two_week_low"),
        "price_change_3m_pct": fin.get("price_change_3m_pct"),
    }

    data_available = (
        "Note: Real financial data WAS successfully retrieved via yfinance."
        if state.get("tool_call_success")
        else "Note: Real financial data could NOT be retrieved. Rely on general knowledge but flag all uncertainty."
    )

    user_prompt = f"""Perform fundamental analysis for {fin.get('company_name')} ({fin.get('ticker')}).

Sector: {fin.get('sector')} | Industry: {fin.get('industry')}
Analysis focus: {pq.get('analysis_focus')}
User's specific questions: {json.dumps(pq.get('key_questions', []))}
{data_available}

Key financial metrics:
{json.dumps(metrics_snapshot, indent=2)}

Business summary (first 600 chars):
{fin.get('business_summary', 'N/A')}

Provide your structured fundamental analysis as JSON."""

    raw = llm_call(client, SYSTEM_PROMPT, user_prompt, temperature=0.3)
    analysis = extract_json(raw)

    # Fallback if JSON extraction failed entirely
    if "valuation_assessment" not in analysis:
        analysis = {
            "valuation_assessment": "unknown",
            "valuation_reasoning": raw,
            "financial_strengths": [],
            "financial_weaknesses": [],
            "key_metrics_summary": {},
            "competitive_position": "Parse error — see valuation_reasoning.",
            "red_flags": [],
            "data_quality_note": "JSON extraction failed; raw LLM response stored in valuation_reasoning.",
        }
        print("  [warn] JSON extraction failed; stored raw response.")

    state["fundamental_analysis"] = analysis

    print(f"  Valuation  : {analysis.get('valuation_assessment')}")
    print(f"  Strengths  : {len(analysis.get('financial_strengths', []))} item(s)")
    print(f"  Weaknesses : {len(analysis.get('financial_weaknesses', []))} item(s)")
    print(f"  Red flags  : {len(analysis.get('red_flags', []))} item(s)")

    return state
