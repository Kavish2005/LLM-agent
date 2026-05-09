# Prompt Design Explanation

This appendix documents the full system prompt and user prompt for each LLM step in the chain, explains why each prompt is shaped the way it is, and shows one example of a prompt that was changed after testing.

---

## Step 1 — Parse user query

### System prompt
```
You are a financial query parser. Extract structured information from the user's investment research request.

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
- analysis_focus must be exactly one of the five options listed above.
```

### User prompt (template)
```
Parse this investment research request and return JSON:

"<user's raw query>"
```

### Design rationale
The instruction "Respond with valid JSON only — no markdown, no explanation, no prose" is the most critical constraint. Without it, the model typically wraps the JSON in a sentence like "Here is the parsed result:" which breaks downstream JSON parsing. The explicit schema with field names and example values prevents the model from inventing its own field names. The `analysis_focus` constraint to five exact values ensures Step 3's prompt can reference it without needing to normalise free-form text. Temperature is set to 0.2 (lowest in the chain) because this step requires deterministic extraction, not creative reasoning. The output of this step directly drives the tool call in Step 2 — an incorrect ticker here breaks the entire chain.

---

## Step 3 — Fundamental analysis

### System prompt
```
You are a senior equity analyst performing fundamental analysis on real financial data.

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
- financial_strengths and financial_weaknesses must each have 2-5 items.
```

### User prompt (template)
```
Perform fundamental analysis for <company_name> (<ticker>).

Sector: <sector> | Industry: <industry>
Analysis focus: <analysis_focus>
User's specific questions: <key_questions>
Note: Real financial data WAS/WAS NOT successfully retrieved via yfinance.

Key financial metrics:
<metrics dict — subset of ~20 fields>

Business summary (first 600 chars):
<business_summary>

Provide your structured fundamental analysis as JSON.
```

### Design rationale
The `data_quality_note` field was added after testing revealed a failure mode: when several metrics were null (common for small-cap stocks), the model silently invented plausible-sounding figures rather than acknowledging the gap. Adding an explicit field for data quality issues forces the model to flag uncertainty rather than paper over it. The user's `key_questions` from Step 1 are injected here so the analysis is targeted to what the user actually asked rather than generic. The `red_flags` field is structurally important — Step 5 reads it directly to seed the critique.

---

## Step 4 — Investment thesis

### System prompt
```
You are a portfolio manager constructing an investment thesis.
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
- Position sizing must match conviction: high→medium/large, low→small/none.
```

### User prompt (template)
```
Build an investment thesis for <company_name> (<ticker>).

Context:
  Sector        : <sector>
  Analysis focus: <analysis_focus>
  Time horizon  : <time_horizon>

Price & analyst data:
<price context dict>

Business overview (truncated):
<business_summary>

Fundamental analysis (from Step 3):
<fundamental_analysis dict>

Construct a balanced bull and bear investment thesis as JSON.
```

### Design rationale — includes prompt iteration example

**Version 1 (original):**
The original Step 4 system prompt did not require an explicit `key_assumptions` field. It only asked for bull/bear cases and a recommendation. The output was structurally fine but Step 5 had nothing concrete to challenge — the critique became generic ("consider macroeconomic conditions") rather than specific ("the thesis assumes services revenue will offset iPhone saturation — this rests on the unverified claim that Apple TV+ subscriber growth is accelerating").

**What it produced:** Step 5 outputs like: *"The thesis does not adequately consider macro risks."* — too vague to be useful.

**What was changed:** Added `key_assumptions` as a required field with 3-5 items in the schema, and added the rule note *"these will be stress-tested in the next step"* to signal to the model that this field has downstream consequences.

**Why the new version works better:** Step 5 now receives the exact list of assumptions from Step 4's JSON and is instructed to challenge all of them by name. This creates a concrete data dependency between the two steps and produces specific, named critiques rather than generic risk warnings.

---

## Step 5 — Critique and stress test

### System prompt
```
You are a risk manager stress-testing an investment thesis before it goes to committee.
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
- Do not simply restate what the thesis said. Challenge it.
```

### User prompt (template)
```
Stress-test this investment thesis for <company_name> (<ticker>).

Time horizon under review: <time_horizon>

Investment thesis to challenge (from Step 4):
<investment_thesis dict>

Supporting financial metrics (from Step 2):
<risk_metrics dict — selected subset>

Red flags already identified in fundamental analysis (from Step 3):
<red_flags list>

Recent news headlines (from Step 2 tool call):
<news_headlines list>

Challenge every key_assumption listed in the thesis. Produce a rigorous risk assessment as JSON.
```

### Design rationale
The adversarial role ("risk manager", "Be specific and adversarial — a great job review is worthless") is essential. Without it, the model defaults to a balanced tone that validates rather than challenges. Injecting the news headlines from Step 2 into this step's context checks whether the thesis accounted for recent events — the connection between the real-world tool call and the critique step. Temperature is set to 0.5 (slightly higher than other steps) to encourage more diverse challenges rather than repeating the same risk in different words.

---

## Step 6 — Final report

### System prompt
```
You are a senior investment research writer. Synthesise all provided analysis into
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

Do not include a disclaimer beyond one line at the very end.
```

### User prompt (template)
```
Write a full equity research brief for <company_name> (<ticker>).

KEY SIGNAL FIGURES (cite these, do not invent alternatives):
<headline_figures dict>

USER'S ORIGINAL QUESTIONS:
<key_questions>

RECOMMENDATION (must appear in Executive Summary and Conclusion):
Action: <recommended_action>
Stance: <overall_stance>
Conviction: <conviction_level>
Risk Rating: <final_risk_rating>
Validity: <thesis_validity_score>/10

FUNDAMENTAL ANALYSIS (Step 3): <full dict>
INVESTMENT THESIS (Step 4): <full dict>
RISK CRITIQUE (Step 5): <full dict>

Sector & Industry, business overview, recent news...

Now write the full research brief with all required sections.
```

### Design rationale
The required section headers are specified verbatim in the system prompt to ensure consistent structure across different queries and stocks. Without this, early test runs produced arbitrarily ordered sections — some omitting risk entirely, others burying the recommendation in the final paragraph. The recommendation, stance, and risk rating are explicitly injected at the top of the user prompt (not just present in the nested JSON dicts) so the model treats them as primary directives rather than buried context. Temperature is 0.6, the highest in the chain, because the final report benefits from natural prose variety rather than formulaic repetition.
