"""
Step 2 — TOOL CALL: Fetch real financial data via yfinance (Yahoo Finance).

Why this is a tool call and not an LLM call:
  LLMs cannot produce accurate, current financial figures — they will hallucinate
  prices, P/E ratios, and revenue numbers. Using yfinance retrieves live data from
  Yahoo Finance, giving the analysis in Steps 3-5 a factual grounding.

Why this data shape:
  We pull the metrics that matter across all common analysis styles (growth, value,
  dividend, risk). Later steps filter what's relevant to the user's focus.
  News headlines are included so the critique step (Step 5) can flag whether the
  thesis ignores recent corporate events.

Error handling:
  If yfinance fails (network issue, invalid ticker, delisted stock), the agent does
  not abort. It sets tool_call_success=False and continues with a minimal placeholder
  so the downstream LLM steps can still run — they will note the missing data in
  their outputs rather than crashing the chain.
"""

from datetime import datetime
import yfinance as yf
from utils import log_step


def step2_fetch_financial_data(state: dict) -> dict:
    """
    Input:  state["parsed_query"]["ticker"]
    Output: state["financial_data"] — dict of real financial metrics + news
            state["tool_call_success"] — bool
    """
    log_step(2, "Fetch real financial data (Tool Call — yfinance)")

    ticker_symbol = state["parsed_query"].get("ticker", "").upper().strip()
    print(f"  Fetching data for ticker: {ticker_symbol}")

    try:
        tkr = yf.Ticker(ticker_symbol)
        info = tkr.info

        # Validate we actually got data back (yfinance returns empty dict for bad tickers)
        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            raise ValueError(f"No market data returned for '{ticker_symbol}'. Ticker may be invalid or delisted.")

        # Recent price history for momentum calculation
        hist = tkr.history(period="3mo")

        # Recent news (capped at 5 headlines)
        raw_news = tkr.news or []
        news = [
            {"title": n.get("title", ""), "publisher": n.get("publisher", "")}
            for n in raw_news[:5]
        ]

        # 3-month price change
        price_change_3m = None
        if not hist.empty and len(hist) >= 2:
            p_start = hist["Close"].iloc[0]
            p_end = hist["Close"].iloc[-1]
            price_change_3m = round(((p_end - p_start) / p_start) * 100, 2)

        # Build the structured financial data dict
        financial_data = {
            "ticker": ticker_symbol,
            "company_name": info.get("longName", ticker_symbol),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            # Price & valuation
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "ev_to_ebitda": info.get("enterpriseToEbitda"),
            # Income
            "revenue": info.get("totalRevenue"),
            "revenue_growth_yoy": info.get("revenueGrowth"),
            "gross_margins": info.get("grossMargins"),
            "operating_margins": info.get("operatingMargins"),
            "profit_margins": info.get("profitMargins"),
            "ebitda": info.get("ebitda"),
            # Returns & growth
            "return_on_equity": info.get("returnOnEquity"),
            "return_on_assets": info.get("returnOnAssets"),
            "earnings_growth_yoy": info.get("earningsGrowth"),
            "earnings_per_share": info.get("trailingEps"),
            "forward_eps": info.get("forwardEps"),
            # Balance sheet & liquidity
            "total_debt": info.get("totalDebt"),
            "total_cash": info.get("totalCash"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            # Dividends
            "dividend_yield": info.get("dividendYield"),
            "dividend_rate": info.get("dividendRate"),
            "payout_ratio": info.get("payoutRatio"),
            # Price range & analyst consensus
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "price_change_3m_pct": price_change_3m,
            "beta": info.get("beta"),
            "analyst_target_price": info.get("targetMeanPrice"),
            "analyst_recommendation_mean": info.get("recommendationMean"),  # 1=Strong Buy…5=Strong Sell
            "number_of_analyst_opinions": info.get("numberOfAnalystOpinions"),
            # Qualitative
            "business_summary": (info.get("longBusinessSummary") or "")[:600],
            "recent_news": news,
            "data_retrieved_at": datetime.now().isoformat(),
        }

        state["financial_data"] = financial_data
        state["tool_call_success"] = True

        # Human-readable confirmation
        mc = financial_data["market_cap"]
        mc_str = f"${mc / 1e9:.1f}B" if mc else "N/A"
        print(f"  Company : {financial_data['company_name']}")
        print(f"  Price   : ${financial_data['current_price']}")
        print(f"  Mkt Cap : {mc_str}")
        print(f"  P/E     : {financial_data['pe_ratio']}")
        print(f"  3m Chg  : {price_change_3m}%")
        print(f"  News    : {len(news)} headline(s) retrieved")

    except Exception as exc:
        print(f"  [error] Tool call failed: {exc}")
        # Graceful degradation — chain continues with a minimal placeholder
        state["financial_data"] = {
            "ticker": ticker_symbol,
            "company_name": state["parsed_query"].get("company_name", ticker_symbol),
            "sector": "Unknown",
            "industry": "Unknown",
            "error": str(exc),
            "note": (
                "Real financial data could not be retrieved. "
                "Downstream LLM steps will rely on general knowledge and should flag uncertainty."
            ),
            "recent_news": [],
            "data_retrieved_at": datetime.now().isoformat(),
        }
        state["tool_call_success"] = False
        print("  [warn] Continuing chain with degraded state (no live data).")

    return state
