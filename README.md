# Investment Research Agent

A multi-step LLM agent that takes a plain-English stock query and produces a
professional equity research brief through a six-step reasoning chain.

---

## What it does

Given a query like *"Is Apple a good long-term investment?"*, the agent:

1. Parses your question into a structured request (ticker, focus, horizon)
2. Fetches **real, live financial data** from Yahoo Finance (tool call)
3. Performs fundamental analysis on the data
4. Constructs a balanced investment thesis (bull and bear case)
5. Stress-tests the thesis from a risk manager's perspective
6. Synthesises everything into a polished Markdown research brief

---

## Chain structure

```
User query (string)
      │
      ▼
Step 1 — LLM: Parse query
      │   Output: {ticker, company_name, analysis_focus, key_questions, time_horizon}
      │
      ▼
Step 2 — TOOL: yfinance (Yahoo Finance)
      │   Input:  ticker from Step 1
      │   Output: ~25 real financial metrics + news headlines
      │
      ▼
Step 3 — LLM: Fundamental analysis
      │   Input:  financial metrics (Step 2) + user focus & questions (Step 1)
      │   Output: {valuation_assessment, strengths, weaknesses, red_flags, key_metrics_summary}
      │
      ▼
Step 4 — LLM: Investment thesis
      │   Input:  fundamental analysis (Step 3) + price context (Step 2) + time horizon (Step 1)
      │   Output: {overall_stance, bull_case, bear_case, key_assumptions, recommended_action}
      │
      ▼
Step 5 — LLM: Stress test / critique
      │   Input:  thesis + key_assumptions (Step 4) + red_flags (Step 3) + news (Step 2)
      │   Output: {challenged_assumptions, scenario_analysis, risk_rating, validity_score}
      │
      ▼
Step 6 — LLM: Final report
          Input:  all previous outputs
          Output: Markdown research brief (saved to output/)
```

No step can be removed without breaking the chain. Step 3 cannot run without the
real data from Step 2. Step 5 cannot challenge the assumptions without Step 4's
`key_assumptions` list. Step 6 cannot synthesise without Steps 3, 4, and 5.

---

## Setup

**Prerequisites:** Python 3.10+

```bash
pip install -r requirements.txt
```

**API key:**

Get an Anthropic API key from [console.anthropic.com](https://console.anthropic.com) and export it:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Running the agent

```bash
python agent.py "Analyse Apple stock for long-term growth investment"
python agent.py "Is Tesla a good buy right now? Focus on risk."
python agent.py "NVDA — value or overvalued? I have a 5-year horizon."
python agent.py "Analyse Microsoft as a dividend investment"
```

The agent prints step-by-step progress to the terminal.
When complete, it saves two files to the `output/` directory:

- `report_<TICKER>_<timestamp>.md` — the full research brief
- `state_<TICKER>_<timestamp>.json` — the complete shared state (all intermediate outputs)

---

## Handling unexpected input

The agent degrades gracefully:

| Problem | Behaviour |
|---------|-----------|
| Invalid ticker (Step 2 fails) | Chain continues in degraded mode; LLM steps flag missing data |
| LLM returns malformed JSON | `extract_json()` in `utils.py` strips markdown fences and retries; falls back to a safe default dict |
| Anthropic API transient error | `llm_call()` retries up to 3 times with exponential back-off |
| Completely unrecognised input | Step 1 falls back to using the raw string as company name |

---

## File structure

```
agent.py              — main orchestrator; runs the chain, saves output
utils.py              — Anthropic API client, llm_call(), extract_json(), log_step()
steps/
  __init__.py         — re-exports all step functions
  step1_parse.py      — LLM: parse user query
  step2_fetch.py      — TOOL: yfinance financial data fetch
  step3_analyze.py    — LLM: fundamental analysis
  step4_thesis.py     — LLM: investment thesis construction
  step5_critique.py   — LLM: stress test and risk critique
  step6_report.py     — LLM: final report synthesis
output/               — created at runtime; holds reports and state JSON
requirements.txt
README.md
```

---

## What each step receives and produces

| Step | Reads from state | Writes to state |
|------|-----------------|-----------------|
| 1 — Parse | `user_query` | `parsed_query` |
| 2 — Fetch | `parsed_query.ticker` | `financial_data`, `tool_call_success` |
| 3 — Analyze | `financial_data`, `parsed_query` | `fundamental_analysis` |
| 4 — Thesis | `fundamental_analysis`, `financial_data`, `parsed_query` | `investment_thesis` |
| 5 — Critique | `investment_thesis`, `fundamental_analysis`, `financial_data`, `parsed_query` | `thesis_critique` |
| 6 — Report | all of the above | `final_report` |

---

## Notes

- The agent uses **Anthropic Claude** (`claude-haiku-4-5-20251001` by default) for all LLM calls
  via the Anthropic Python SDK.
- Financial data is fetched live from Yahoo Finance via the `yfinance` Python library.
  Results reflect market data at the time of the run.
- This project does not use LangChain, LlamaIndex, or any agent framework.
  The chain is implemented directly in Python.
- Output is for educational purposes only and does not constitute financial advice.
