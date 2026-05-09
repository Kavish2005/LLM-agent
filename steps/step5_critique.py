"""
Step 5 — LLM: Critique and Stress Test.

Why this is a separate step from Step 4 (thesis):
  The same LLM that built the thesis cannot objectively critique it — it will
  anchor on its own prior output. Placing the critique in a fresh LLM call with
  a different system role (risk manager, not portfolio manager) breaks this anchor.
  In testing, Step 5 caught cases where Step 4 built a bullish thesis while the
  fundamental analysis contained red flags it had not weighted heavily enough.

System prompt design notes:
  - The system role "risk manager" primes the LLM to be adversarial by default.
  - "challenged_assumptions" receives the exact list from Step 4 so the critique is
    targeted rather than generic. This is the key data dependency between Step 4 and 5.
  - The validity_score (1-10) is used in the final report header to give readers a
    quick signal without requiring them to read the full critique.
  - Receiving the news headlines from Step 2 ensures the critique checks whether
    the thesis considered recent events — a failure mode discovered in testing where
    the thesis ignored a recent earnings miss visible in the news data.
  - temperature=0.5 is slightly higher here to encourage more diverse challenges.
"""

import json
import anthropic
from utils import llm_call, extract_json, log_step


SYSTEM_PROMPT = """You are a risk manager stress-testing an investment thesis before it goes to committee.
Your job is to challenge every assumption, find logical gaps, and identify what could go wrong.
Be specific and adversarial — a "great job" review is worthless.

Respond with valid JSON only — no markdown, no prose. Use exactly this schema:

{
  "thesis_validity_score": <integer 1-10>,
  "strongest_points": ["<point 1>", "..."],
  "challenged_assumptions": [
    {
      "assumption": "<exact assumption from the thesis>",
      "challenge": "<why this assumption might be wrong>",
      "severity": "<high | medium | low>"
    }
  ],
  "missing_analysis": ["<what was not considered 1>", "..."],
  "macro_risks": ["<macro or sector-level risk 1>", "..."],
  "scenario_analysis": {
    "best_case": "<brief description and what drives it>",
    "base_case": "<brief description and what drives it>",
    "worst_case": "<brief description and what drives it>"
  },
  "final_risk_rating": "<low | medium | high | very_high>",
  "recommendation_to_analyst": "<what to investigate or re-examine before acting on this thesis>"
}

Rules:
- challenged_assumptions must cover ALL assumptions from the thesis, not a subset.
- thesis_validity_score of 8+ requires strong evidence from the data; 5- requires specific critique.
- Do not simply restate what the thesis said. Challenge it."""


def step5_critique_thesis(client: anthropic.Anthropic, state: dict) -> dict:
    """
    Input:  state["investment_thesis"]     — from Step 4
            state["fundamental_analysis"]  — from Step 3
            state["financial_data"]        — from Step 2 (news headlines, raw metrics)
            state["parsed_query"]          — user's time horizon (from Step 1)
    Output: state["thesis_critique"] — structured critique dict
    """
    log_step(5, "Critique & stress test")

    fin = state["financial_data"]
    thesis = state["investment_thesis"]
    analysis = state["fundamental_analysis"]
    pq = state["parsed_query"]

    # Selected metrics for the critique context (different slice from Step 3)
    risk_metrics = {
        "pe_ratio": fin.get("pe_ratio"),
        "debt_to_equity": fin.get("debt_to_equity"),
        "current_ratio": fin.get("current_ratio"),
        "beta": fin.get("beta"),
        "revenue_growth_yoy": fin.get("revenue_growth_yoy"),
        "profit_margins": fin.get("profit_margins"),
        "payout_ratio": fin.get("payout_ratio"),
        "analyst_recommendation_mean": fin.get("analyst_recommendation_mean"),
        "price_change_3m_pct": fin.get("price_change_3m_pct"),
    }

    news_headlines = [n.get("title", "") for n in fin.get("recent_news", [])]

    user_prompt = f"""Stress-test this investment thesis for {fin.get('company_name')} ({fin.get('ticker')}).

Time horizon under review: {pq.get('time_horizon')}

Investment thesis to challenge (from Step 4):
{json.dumps(thesis, indent=2)}

Supporting financial metrics (from Step 2):
{json.dumps(risk_metrics, indent=2)}

Red flags already identified in fundamental analysis (from Step 3):
{json.dumps(analysis.get('red_flags', []))}

Recent news headlines (from Step 2 tool call):
{json.dumps(news_headlines)}

Challenge every key_assumption listed in the thesis. Produce a rigorous risk assessment as JSON."""

    raw = llm_call(client, SYSTEM_PROMPT, user_prompt, temperature=0.5)
    critique = extract_json(raw)

    if "thesis_validity_score" not in critique:
        critique = {
            "thesis_validity_score": 5,
            "strongest_points": [],
            "challenged_assumptions": [],
            "missing_analysis": [],
            "macro_risks": [],
            "scenario_analysis": {"best_case": "", "base_case": "", "worst_case": ""},
            "final_risk_rating": "medium",
            "recommendation_to_analyst": raw,
        }
        print("  [warn] JSON extraction failed; stored raw response.")

    state["thesis_critique"] = critique

    score = critique.get("thesis_validity_score", "N/A")
    risk = critique.get("final_risk_rating", "N/A")
    challenged = len(critique.get("challenged_assumptions", []))
    print(f"  Validity score     : {score}/10")
    print(f"  Risk rating        : {risk}")
    print(f"  Assumptions probed : {challenged}")
    print(f"  Missing analysis   : {len(critique.get('missing_analysis', []))} item(s)")

    return state
