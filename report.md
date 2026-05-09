<div class="paper-header">

# Investment Research Agent: A Multi-Step LLM Pipeline for Equity Analysis

<div class="authors">Kavish Kumar &nbsp;·&nbsp; Advanced Natural Language Processing &nbsp;·&nbsp; Semester 6</div>

<div class="abstract-block">
<span class="abstract-label">Abstract</span> — Investment research requires gathering real financial data, interpreting it through multiple analytical lenses, and synthesising the findings into an actionable recommendation. These tasks cannot be compressed into a single LLM prompt: the model has no access to current financial figures, conflating descriptive analysis with prescriptive thesis construction causes selective evidence weighting, and a model anchors on its own output when asked to critique it. This paper presents a six-step multi-step LLM agent that chains a real-data tool call with five sequential LLM reasoning steps — each consuming the structured JSON output of its predecessor — to produce a professional equity research brief. Evaluated on Apple Inc. (AAPL), the agent demonstrates that step separation, adversarial role assignment, and explicit assumption surfacing each materially improve the specificity and reliability of the output relative to a single-prompt baseline.

**Keywords** — large language models, multi-step reasoning, tool use, financial NLP, prompt chaining, equity research
</div>

</div>

## I. Introduction

Large language models exhibit strong language understanding and general reasoning capabilities, but applying them to real-world analytical tasks reveals two structural gaps. First, LLMs have no access to current external data: asking a model to evaluate a stock's valuation without providing real financial figures produces hallucinated numbers that appear plausible but are factually wrong [4]. Second, complex analytical tasks decompose into cognitively distinct subtasks that produce better results when handled separately. Wei et al. [2] demonstrate that prompting a model to reason through intermediate steps before answering substantially improves accuracy on complex tasks; this insight motivates the chaining approach taken here.

Investment research is a natural fit for multi-step chaining. The task requires: (1) resolving a natural language query into a machine-readable form suitable for a tool call; (2) fetching real financial data the LLM cannot supply; (3) interpreting that data through the lens of fundamental analysis; (4) constructing a forward-looking investment thesis; (5) stress-testing the thesis from an adversarial perspective; and (6) synthesising the outputs into a structured report. Each step depends on the previous one, and no step can be skipped without breaking downstream reasoning. This paper describes the design, implementation, and evaluation of such an agent, and reflects on the architectural insights gained during development.

## II. Related Work

The ReAct framework [1] introduced interleaving reasoning traces with tool calls, establishing the pattern that directly inspires this agent's architecture: a tool call (Step 2) provides grounded observations that feed a reasoning chain (Steps 3–5). Toolformer [3] demonstrated that tool calls should be structurally separate from LLM reasoning steps, which motivates the clean boundary between Step 2 and Step 3 in our design. In the financial domain, BloombergGPT [4] established that finance tasks require grounded data inputs rather than relying on LLM training knowledge, and Lopez-Lira and Tang [5] showed that LLM-based analysis of financial text produces predictive signal above chance. FinGPT [6] informed the use of structured JSON output for financial reasoning steps.

## III. System Architecture

### A. Chain Overview

The agent maintains a single Python dictionary as shared state. Each step reads from the state, performs its task, and writes its output back, so all downstream steps accumulate context. Table I summarises the six-step chain.

<div class="table-caption">TABLE I: Agent Chain Structure</div>

| Step | Type | Input (from state) | Output (to state) |
|------|------|--------------------|-------------------|
| 1 | LLM | `user_query` | `parsed_query` {ticker, focus, questions, horizon} |
| 2 | Tool | `parsed_query.ticker` | `financial_data` (~25 metrics + news) |
| 3 | LLM | `financial_data`, `parsed_query` | `fundamental_analysis` {valuation, strengths, red_flags} |
| 4 | LLM | `fundamental_analysis`, `financial_data` | `investment_thesis` {bull, bear, assumptions} |
| 5 | LLM | `investment_thesis`, `fundamental_analysis`, `financial_data` | `thesis_critique` {challenges, risk_rating, scenarios} |
| 6 | LLM | all state | `final_report` (Markdown string) |

### B. Step Design

**Step 1 — Query parsing.** The user's natural language input (e.g., "Is Apple a good long-term investment?") is passed to an LLM with a strict JSON-only system prompt that enforces a fixed output schema: `{company_name, ticker, analysis_focus, key_questions, time_horizon}`. The temperature is set to 0.2 for deterministic extraction. This step exists because the entire chain — including the tool call — depends on a reliable ticker symbol. Without structured extraction, fuzzy input cannot drive Step 2.

**Step 2 — Financial data fetch (tool call).** Using the ticker from Step 1, the agent calls Yahoo Finance via the `yfinance` Python library and retrieves approximately 25 financial metrics: current price, P/E and forward P/E, PEG ratio, revenue and earnings growth, gross/operating/net margins, return on equity, debt-to-equity, current ratio, analyst consensus target, beta, dividend yield, 52-week range, and five recent news headlines. This is a tool call, not an LLM call, because language models cannot produce accurate current financial figures. Error handling catches invalid tickers, sets a `tool_call_success` flag, and degrades gracefully rather than crashing the chain.

**Step 3 — Fundamental analysis.** The LLM receives the financial metrics from Step 2 and the user's focus and questions from Step 1. Its system prompt assigns the role of senior equity analyst and enforces a JSON schema with fields for `valuation_assessment` (constrained to three values), `financial_strengths`, `financial_weaknesses`, `key_metrics_summary`, `competitive_position`, `red_flags`, and a `data_quality_note`. This step is separate from Step 4 because descriptive analysis and prescriptive thesis construction are cognitively distinct — combining them in testing caused the model to adopt a stance early and selectively weight evidence to support it.

**Step 4 — Investment thesis.** The LLM receives the fundamental analysis from Step 3, price context from Step 2, and time horizon from Step 1. It outputs a bull case, a bear case, a `recommended_action`, and critically a `key_assumptions` list of 3–5 items. The assumptions list is the structural dependency that connects Step 4 to Step 5: without it, the critique step has no specific claims to challenge and defaults to generic risk commentary. This design decision emerged from testing and is discussed further in Section VI.

**Step 5 — Stress test.** The LLM is assigned the role of risk manager and instructed to challenge every assumption from Step 4 by name. It also receives the `red_flags` from Step 3 and the news headlines from Step 2 to check whether the thesis ignored recent corporate events. Temperature is raised to 0.5 to encourage diverse challenges. The output includes `challenged_assumptions` with severity ratings, `scenario_analysis` (best/base/worst case), a `final_risk_rating`, and a `thesis_validity_score` (1–10).

**Step 6 — Report synthesis.** The LLM receives all prior outputs and synthesises them into a structured Markdown research brief with fixed section headers specified verbatim in the system prompt. The recommendation and risk rating are explicitly injected at the top of the user prompt rather than buried in nested JSON, ensuring they appear prominently in the output. Temperature is 0.6 to allow natural prose variation.

## IV. Tool Integration

The tool used is **yfinance**, a Python library that queries Yahoo Finance's public endpoint without requiring an API key. It was chosen over Alpha Vantage and Polygon.io because it is fully free-tier, returns data as a Python dict that integrates directly with the shared state object, and covers all metrics required for equity fundamental analysis. Its output enters the chain at Step 2 and is consumed by Steps 3, 4, 5, and 6. The data flows through the chain unmodified — each LLM step selects the subset of fields relevant to its task — which maintains a single authoritative source of financial truth throughout the reasoning chain.

## V. Experimental Results

The agent was evaluated on the query *"Analyse Apple stock for long-term growth investment"*. Step 1 correctly extracted ticker `AAPL`, focus `growth`, and horizon `long-term (3+ years)`. Step 2 fetched a current price of \$293.32, P/E of 35.47, market capitalisation of \$4.31T, revenue growth of 16.6% YoY, and net profit margins of 27.2%. Step 3 classified the stock as **overvalued**, identifying four financial strengths (notably a 47.9% gross margin and 141% ROE) and five red flags including a 79.5x debt-to-equity ratio and a current ratio of 1.07. Step 4 produced a **neutral/accumulate** thesis with five named assumptions, including services revenue growth offsetting iPhone saturation. Step 5 challenged all five assumptions with specific severity ratings and produced a **HIGH** risk rating with validity score of **4/10**, noting that Vision Pro adoption data directly contradicted the innovation optionality assumption. Step 6 synthesised a 16,932-character research brief complete with sensitivity analysis. End-to-end latency was approximately 35 seconds.

## VI. Limitations

The most significant limitation is silent cascade degradation. When Step 2 returns incomplete data — common for smaller-cap and international tickers with limited Yahoo Finance coverage — downstream steps produce confident-sounding outputs that are factually wrong. The chain has no circuit-breaker that pauses when data quality falls below a minimum threshold. A solution would be a Python assertion layer between steps that validates LLM-stated figures against the raw Step 2 dict before passing conclusions downstream.

A second limitation is that Step 5's critique is performed by the same model family that constructed Step 4's thesis. Although the adversarial system prompt reduces anchoring, it cannot eliminate it. In practice, Step 5 challenged peripheral assumptions while leaving the overall stance intact. A genuinely independent critique would require either a different model or a human reviewer.

Third, the agent lacks a peer benchmarking step. Assertions such as "margins are high" or "P/E is elevated" are qualitative and unbenchmarked. Inserting a peer fetch step between Steps 2 and 3 — retrieving the same metrics for three to five sector competitors — would transform these into quantitative claims with sector context.

## VII. Conclusion

This paper presented a six-step investment research agent demonstrating that multi-step LLM chaining genuinely outperforms single-prompt approaches for tasks requiring external data, multi-perspective analysis, and self-critique. The most non-obvious architectural insight was that requiring Step 4 to explicitly surface its own assumptions as structured output — rather than embedding them implicitly in prose — transformed Step 5 from a generic risk commentary generator into a specific, named-assumption challenger. This principle generalises: any step that constructs an argument in a multi-step chain should be required to surface its assumptions as structured output so the next step can challenge them by name. A second insight is that the `tool_call_success` flag and graceful degradation pattern are necessary but insufficient — the chain needs active data quality checks, not just passive fallbacks, to prevent cascading errors from propagating invisibly through downstream reasoning steps.

---

## References

[1] S. Yao, J. Zhao, D. Yu, N. Du, I. Shafran, K. Narasimhan, and Y. Cao, "ReAct: Synergizing reasoning and acting in language models," *ICLR 2023*.

[2] J. Wei, X. Wang, D. Schuurmans, M. Bosma, F. Xia, E. Chi, Q. Le, and D. Zhou, "Chain-of-thought prompting elicits reasoning in large language models," *NeurIPS 2022*.

[3] T. Schick, J. Dwivedi-Yu, R. Dessì, R. Raileanu, M. Lomeli, L. Zettlemoyer, N. Cancedda, and T. Scialom, "Toolformer: Language models can teach themselves to use tools," *NeurIPS 2023*.

[4] S. Wu, O. Irsoy, S. Lu, V. Dabravolski, M. Dredze, S. Gehrmann, P. Kambadur, D. Rosenberg, and G. Mann, "BloombergGPT: A large language model for finance," *arXiv:2303.17564*, 2023.

[5] A. Lopez-Lira and Y. Tang, "Can ChatGPT forecast stock price movements? Return predictability from a large language model," *arXiv:2304.07619*, 2023.

[6] H. Yang, X. Liu, and C. D. Wang, "FinGPT: Open-source financial large language models," *arXiv:2306.06031*, 2023.

[7] T. Kojima, S. S. Gu, M. Reid, Y. Matsuo, and Y. Iwasawa, "Large language models are zero-shot reasoners," *NeurIPS 2022*.
