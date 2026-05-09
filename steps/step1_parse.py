"""
Step 1 — LLM: Parse the user's natural language query into a structured dict.

Why this is a separate step:
  Every downstream step needs a reliable ticker symbol and analysis focus.
  Asking the user to supply these directly would make the agent less useful.
  By having the LLM extract them first, we can accept fuzzy input
  ("tell me about Apple") and still drive a precise tool call in Step 2.

System prompt design notes:
  - "Respond with valid JSON only" removes the need to strip prose from the output.
  - Explicit field names with descriptions prevent the LLM from inventing its own schema.
  - temperature=0.2 keeps ticker extraction deterministic.
"""

import json
import anthropic
from utils import llm_call, extract_json, log_step


SYSTEM_PROMPT = """You are a financial query parser. Extract structured information from the user's investment research request.

Respond with valid JSON only — no markdown, no explanation, no prose. Use exactly this schema:

{
  "company_name": "<full company name>",
  "ticker": "<stock ticker symbol, e.g. AAPL>",
  "analysis_focus": "<one of: growth | value | dividend | risk | general>",
  "key_questions": ["<question 1>", "<question 2>", "<question 3>"],
  "time_horizon": "<e.g. short-term (<1 year) | medium-term (1-3 years) | long-term (3+ years)>"
}

Rules:
- If the user does not supply a ticker, infer it from the company name.
- If the user does not specify a time horizon, default to "medium-term (1-3 years)".
- key_questions must have 3 to 5 items that reflect what the user actually wants to know.
- analysis_focus must be exactly one of the five options listed above."""


def step1_parse_query(client: anthropic.Anthropic, state: dict) -> dict:
    """
    Input:  state["user_query"]  — raw string from the user
    Output: state["parsed_query"] — dict with company_name, ticker, analysis_focus,
                                    key_questions, time_horizon
    """
    log_step(1, "Parse user query")

    user_prompt = (
        f'Parse this investment research request and return JSON:\n\n"{state["user_query"]}"'
    )

    raw = llm_call(client, SYSTEM_PROMPT, user_prompt, temperature=0.2)
    parsed = extract_json(raw)

    # Defensive fallback if extraction completely failed
    if "ticker" not in parsed:
        words = state["user_query"].upper().split()
        parsed = {
            "company_name": state["user_query"],
            "ticker": words[0] if words else "UNKNOWN",
            "analysis_focus": "general",
            "key_questions": [
                "What is the company's financial health?",
                "What are the growth prospects?",
                "Is the current valuation reasonable?",
            ],
            "time_horizon": "medium-term (1-3 years)",
        }
        print("  [warn] JSON extraction failed; using fallback parsed query.")

    state["parsed_query"] = parsed

    print(f"  Company : {parsed.get('company_name')}")
    print(f"  Ticker  : {parsed.get('ticker')}")
    print(f"  Focus   : {parsed.get('analysis_focus')}")
    print(f"  Horizon : {parsed.get('time_horizon')}")
    print(f"  Questions: {json.dumps(parsed.get('key_questions', []), indent=4)}")

    return state
