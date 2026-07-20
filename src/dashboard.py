import os
import sys
# Add parent directory to sys.path to resolve 'src' imports correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pandas as pd
import yfinance as yf
import streamlit as st
import yaml
import subprocess
import platform
from datetime import datetime
from typing import Dict, Any


CONFIG_FILE = "config.yaml"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            st.error(f"Error loading config file: {e}")
    return {}

def save_config(new_config):
    try:
        with open(CONFIG_FILE, "w") as f:
            yaml.safe_dump(new_config, f, default_flow_style=False, sort_keys=False)
        return True
    except Exception as e:
        st.error(f"Error saving config file: {e}")
        return False

ENV_FILE = ".env"

def load_env_vars():
    vars = {}
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            k, v = parts
                            vars[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass
    return vars

def save_env_vars(userid, password, trading_mode):
    try:
        lines = []
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, "r") as f:
                lines = f.readlines()
        
        new_lines = []
        keys_updated = set()
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in line:
                parts = stripped.split("=", 1)
                if len(parts) == 2:
                    k, _ = parts
                    k = k.strip()
                    if k == "IBKR_USERID":
                        new_lines.append(f'IBKR_USERID="{userid}"\n')
                        keys_updated.add("IBKR_USERID")
                    elif k == "IBKR_PASSWORD":
                        new_lines.append(f'IBKR_PASSWORD="{password}"\n')
                        keys_updated.add("IBKR_PASSWORD")
                    elif k == "IBKR_TRADING_MODE":
                        new_lines.append(f'IBKR_TRADING_MODE="{trading_mode}"\n')
                        keys_updated.add("IBKR_TRADING_MODE")
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        if "IBKR_USERID" not in keys_updated:
            new_lines.append(f'IBKR_USERID="{userid}"\n')
        if "IBKR_PASSWORD" not in keys_updated:
            new_lines.append(f'IBKR_PASSWORD="{password}"\n')
        if "IBKR_TRADING_MODE" not in keys_updated:
            new_lines.append(f'IBKR_TRADING_MODE="{trading_mode}"\n')
            
        with open(ENV_FILE, "w") as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        st.error(f"Error saving .env file: {e}")
        return False

def update_systemd_timer(interval_minutes: int):
    if platform.system() != "Linux":
        return
        
    if interval_minutes == 15:
        on_calendar_lines = """OnCalendar=Mon-Fri *-*-* 09:30,45:00 America/New_York
OnCalendar=Mon-Fri *-*-* 10,11,12,13,14,15:00,15,30,45:00 America/New_York
OnCalendar=Mon-Fri *-*-* 16:00:00 America/New_York"""
    elif interval_minutes == 60:
        on_calendar_lines = """OnCalendar=Mon-Fri *-*-* 09:30:00 America/New_York
OnCalendar=Mon-Fri *-*-* 10,11,12,13,14,15,16:00:00 America/New_York"""
    else:  # default 30
        on_calendar_lines = """OnCalendar=Mon-Fri *-*-* 09:30:00 America/New_York
OnCalendar=Mon-Fri *-*-* 10,11,12,13,14,15:00,30:00 America/New_York
OnCalendar=Mon-Fri *-*-* 16:00:00 America/New_York"""
        
    timer_content = f"""[Unit]
Description=Run Intelligent Invest Trading Cycle every {interval_minutes} minutes during trading hours

[Timer]
{on_calendar_lines}
Unit=trading-agent.service

[Install]
WantedBy=timers.target
"""
    try:
        timer_path = "/etc/systemd/system/trading-agent.timer"
        with open(timer_path, "w") as f:
            f.write(timer_content)
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "restart", "trading-agent.timer"], check=True)
    except Exception as e:
        st.error(f"Failed to update systemd timer: {e}")

# Page Configuration
st.set_page_config(
    page_title="Intelligent Invest Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Shared Design Standards - Zinc/Dark Aesthetics)
st.markdown("""
<style>
    /* Main Layout */
    .stApp {
        background-color: #09090b;
        color: #fafafa;
        font-family: 'DM Sans', sans-serif;
    }
    
    /* Card design */
    .kpi-card {
        background-color: #18181b;
        border: 1px solid #27272a;
        padding: 24px;
        border-radius: 8px;
        margin-bottom: 16px;
    }
    .kpi-title {
        color: #a1a1aa;
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .kpi-val {
        color: #fafafa;
        font-size: 28px;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
    }
    
    /* Table headers styling */
    th {
        color: #a1a1aa !important;
        font-weight: 600 !important;
    }
    
    /* Code logs container */
    .log-container {
        background-color: #09090b;
        border: 1px solid #27272a;
        padding: 16px;
        border-radius: 6px;
        max-height: 400px;
        overflow-y: scroll;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: #71717a;
        white-space: pre-wrap;
    }
    
    /* Form Submit Button Styling */
    div[data-testid="stFormSubmitButton"] button {
        background-color: #2563eb !important;
        color: #ffffff !important;
        border: 1px solid #3b82f6 !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.5rem !important;
        border-radius: 6px !important;
        cursor: pointer !important;
    }
    div[data-testid="stFormSubmitButton"] button:hover {
        background-color: #1d4ed8 !important;
        color: #ffffff !important;
        border-color: #2563eb !important;
    }
    
    /* Regular Button Styling */
    div.stButton > button {
        background-color: #4c1d95 !important;
        color: #ffffff !important;
        border: 1px solid #7c3aed !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.5rem !important;
        border-radius: 6px !important;
        cursor: pointer !important;
        transition: all 0.3s ease;
    }
    div.stButton > button:hover {
        background-color: #6d28d9 !important;
        color: #ffffff !important;
        border-color: #8b5cf6 !important;
        box-shadow: 0 0 10px rgba(124, 58, 237, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# Helper: Load local trading state
STATE_FILE = "trading_state.json"
LOG_FILE = "trading_system.log"

def load_trading_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Error loading state file: {e}")
    return {"active_trades": {}}

# Helper: Load last N lines of logs
def load_system_logs(n=100):
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
                return lines[-n:]
        except Exception as e:
            return [f"Error reading logs: {e}"]
    return ["Log file not found yet. Run the trading system to generate logs."]

# Dashboard App Header
st.title("📈 Intelligent Invest")
st.subheader("Multi-Agent Quantitative Trading System Dashboard")

# Fetch state and configuration
state = load_trading_state()
cfg = load_config()
active_trades = state.get("active_trades", {})
net_liq = state.get("net_liquidation", 100000.0)
cash = state.get("cash", 100000.0)

# Calculate KPIs
total_allocated = 0.0
total_market_value = 0.0
total_unrealized_pnl = 0.0

active_positions_count = len(active_trades)

# Live Data Processing
positions_list = []
if active_positions_count > 0:
    for symbol, details in active_trades.items():
        entry_price = details.get("entry_price", 0.0)
        stop_loss = details.get("stop_loss_price", 0.0)
        qty = details.get("quantity", 0)
        initial_capital = details.get("initial_capital", qty * entry_price)
        
        # Fetch current price via yfinance
        current_price = entry_price
        try:
            ticker_obj = yf.Ticker(symbol)
            # Fetch latest 1d price
            hist = ticker_obj.history(period="1d")
            if not hist.empty:
                current_price = hist["Close"].iloc[-1]
        except Exception as e:
            pass
        
        market_value = qty * current_price
        pnl = market_value - initial_capital
        pnl_pct = (pnl / initial_capital * 100) if initial_capital > 0 else 0.0
        
        total_allocated += initial_capital
        total_market_value += market_value
        total_unrealized_pnl += pnl
        
        positions_list.append({
            "Symbol": symbol,
            "Shares": qty,
            "Risk Tier": details.get("risk_tier", "moderate").upper(),
            "Entry Price": f"${entry_price:.2f}",
            "Current Price": f"${current_price:.2f}",
            "Stop Loss": f"${stop_loss:.2f}",
            "Initial Capital": f"${initial_capital:,.2f}",
            "Market Value": f"${market_value:,.2f}",
            "P&L ($)": f"${pnl:,.2f}",
            "Return (%)": f"{pnl_pct:+.2f}%",
            "pnl_raw": pnl
        })

# Layout: Metric Cards
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Active Positions</div>
        <div class="kpi-val">{active_positions_count}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Total Capital Invested</div>
        <div class="kpi-val">${total_allocated:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Portfolio Net Liquidation</div>
        <div class="kpi-val">${net_liq:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    color = "#10b981" if total_unrealized_pnl >= 0 else "#ef4444"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Total Unrealized P&L</div>
        <div class="kpi-val" style="color: {color};">${total_unrealized_pnl:+,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

# Calculate deployed capital by risk tier
high_deployed = sum(details.get("initial_capital", 0.0) for symbol, details in active_trades.items() if details.get("risk_tier", "moderate") == "high")
mod_deployed = sum(details.get("initial_capital", 0.0) for symbol, details in active_trades.items() if details.get("risk_tier", "moderate") == "moderate")
low_deployed = sum(details.get("initial_capital", 0.0) for symbol, details in active_trades.items() if details.get("risk_tier", "moderate") == "low")

# Load allocation percentages
cfg_alloc = load_config()
alloc_pcts = cfg_alloc.get("allocation", {"high_risk_pct": 0.30, "moderate_risk_pct": 0.40, "low_risk_pct": 0.30})
high_target_pct = alloc_pcts.get("high_risk_pct", 0.30)
mod_target_pct = alloc_pcts.get("moderate_risk_pct", 0.40)
low_target_pct = alloc_pcts.get("low_risk_pct", 0.30)

portfolio_total = net_liq
high_target_cap = portfolio_total * high_target_pct
mod_target_cap = portfolio_total * mod_target_pct
low_target_cap = portfolio_total * low_target_pct

st.write("### Risk Tier Capital Allocation")
col_tier1, col_tier2, col_tier3 = st.columns(3)
with col_tier1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">🔴 High Risk / High Return (Target: {high_target_pct*100:.0f}%)</div>
        <div class="kpi-val">${high_deployed:,.2f} / ${high_target_cap:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with col_tier2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">🟡 Moderate Risk (Target: {mod_target_pct*100:.0f}%)</div>
        <div class="kpi-val">${mod_deployed:,.2f} / ${mod_target_cap:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with col_tier3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">🟢 Low Risk (Target: {low_target_pct*100:.0f}%)</div>
        <div class="kpi-val">${low_deployed:,.2f} / ${low_target_cap:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)# Helper: compile learnings
def compile_learnings_feedback(state: Dict[str, Any]) -> str:
    completed = state.get("completed_trades", [])
    if not completed:
        return ""
    
    successful = [t for t in completed if t.get("realized_pnl", 0) > 0]
    failed = [t for t in completed if t.get("realized_pnl", 0) <= 0]
    
    feedback = f"Total Completed Trades: {len(completed)} ({len(successful)} wins, {len(failed)} losses)\n"
    if successful:
        symbols = [t['symbol'] for t in successful[-5:]]
        feedback += f"- Recent Profitable Tickers: {', '.join(symbols)}\n"
    if failed:
        symbols = [t['symbol'] for t in failed[-5:]]
        feedback += f"- Recent Losing/Stopped-out Tickers: {', '.join(symbols)}\n"
    
    if successful:
        avg_tech_win = sum(t.get("analysis", {}).get("tech_score", 5.0) for t in successful) / len(successful)
        avg_fund_win = sum(t.get("analysis", {}).get("fund_score", 5.0) for t in successful) / len(successful)
        feedback += f"- Successful Trades Avg Scores: Tech: {avg_tech_win:.1f}/10, Fund: {avg_fund_win:.1f}/10\n"
    if failed:
        avg_tech_loss = sum(t.get("analysis", {}).get("tech_score", 5.0) for t in failed) / len(failed)
        avg_fund_loss = sum(t.get("analysis", {}).get("fund_score", 5.0) for t in failed) / len(failed)
        feedback += f"- Failed Trades Avg Scores: Tech: {avg_tech_loss:.1f}/10, Fund: {avg_fund_loss:.1f}/10\n"
        
    return feedback

# Layout: Main Body
tab1, tab2, tab_candidates, tab_prompts, tab_manual, tab3, tab4 = st.tabs(["📊 Active Positions", "📜 Trade Log & AI Learnings", "🔍 Candidate Analysis Log", "🛠️ LLM Agent Prompts", "🎯 On-Demand Ticker Target", "📁 System Logs", "⚙️ Settings & Risk Rules"])

with tab1:
    st.write("### Portfolio Breakdown")
    if len(positions_list) > 0:
        df_positions = pd.DataFrame(positions_list)
        # Drop raw columns
        df_positions_display = df_positions.drop(columns=["pnl_raw"])
        st.dataframe(df_positions_display, use_container_width=True)
    else:
        st.info("No active positions currently tracked. Run the agent cycle to scan for entries.")

with tab2:
    st.write("### AI Brain Feed & Portfolio Learnings")
    learnings = compile_learnings_feedback(state)
    if learnings:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #1e1b4b 0%, #311042 100%); border: 1px solid #4c1d95; padding: 24px; border-radius: 8px; margin-bottom: 24px;">
            <h4 style="margin-top:0; color:#fafafa; font-family:'DM Sans', sans-serif; display:flex; align-items:center; gap:8px;">
                🧠 AI Portfolio Learnings Loop
            </h4>
            <p style="color:#c084fc; font-family:'JetBrains Mono', monospace; font-size:14px; white-space:pre-line; margin-bottom:0;">
                {learnings}
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No completed trades recorded yet. The system will automatically build learnings once trades are closed.")

    st.write("### Completed Trades History")
    completed_trades = state.get("completed_trades", [])
    if completed_trades:
        completed_list = []
        for t in completed_trades:
            pnl = t.get("realized_pnl", 0.0)
            ret_pct = t.get("return_pct", 0.0) * 100
            
            scores = t.get("analysis", {})
            scores_str = f"Tech: {scores.get('tech_score', 'N/A')}, Fund: {scores.get('fund_score', 'N/A')}, News: {scores.get('news_score', 'N/A')}"
            
            completed_list.append({
                "Symbol": t.get("symbol"),
                "Risk Tier": t.get("risk_tier", "moderate").upper(),
                "Qty": t.get("quantity", 0),
                "Entry Price": f"${t.get('entry_price', 0.0):.2f}",
                "Exit Price": f"${t.get('exit_price', 0.0):.2f}",
                "Realized P&L": f"${pnl:+,.2f}",
                "Return (%)": f"{ret_pct:+.2f}%",
                "Exit Reason": t.get("exit_reason", ""),
                "Entry Scores Snapshot": scores_str,
                "Purchased At": t.get("purchased_at", "")[:19].replace("T", " "),
                "Sold At": t.get("sold_at", "")[:19].replace("T", " ")
            })
        st.dataframe(pd.DataFrame(completed_list), use_container_width=True)
    else:
        st.info("No completed trades history yet.")

with tab_candidates:
    st.write("### Ticker Scanning & Qualification Log")
    st.markdown("This log records every candidate asset evaluated by the analysis agents during watchlist scans, showing individual agent scores and the qualification outcome.")
    
    candidate_evals = state.get("candidate_evaluations", [])
    
    if len(candidate_evals) == 0:
        st.info("No candidates evaluated yet. Run a trading cycle to generate analysis data.")
    else:
        # Build pandas DataFrame for display
        rows = []
        for item in candidate_evals:
            analysis = item.get("analysis", {})
            rows.append({
                "Timestamp": item.get("timestamp", "").split("T")[0] + " " + item.get("timestamp", "").split("T")[1][:8] if "T" in item.get("timestamp", "") else item.get("timestamp", ""),
                "Ticker": item.get("symbol"),
                "Risk Tier": item.get("risk_tier", "moderate").upper(),
                "Earnings Check": "Passed" if analysis.get("earnings_checked") == "PASSED" else "Triggered Shield",
                "News Score": f"{analysis.get('news_score')}/10" if analysis.get('news_score') is not None else "-",
                "News Verdict": analysis.get("news_verdict") if analysis.get("news_verdict") is not None else "-",
                "Tech Score": f"{analysis.get('tech_score')}/10" if analysis.get('tech_score') is not None else "-",
                "Tech Verdict": analysis.get("tech_verdict") if analysis.get("tech_verdict") is not None else "-",
                "Fund Score": f"{analysis.get('fund_score')}/10" if analysis.get('fund_score') is not None else "-",
                "Fund Verdict": analysis.get("fund_verdict") if analysis.get("fund_verdict") is not None else "-",
                "Growth Play?": "Yes" if analysis.get("growth_evaluated") == "YES" and "GROWTH_PLAY" in str(analysis.get("fund_verdict", "")) else ("No" if analysis.get("growth_evaluated") == "YES" else "-"),
                "R&D Intensity": f"{analysis.get('rnd_intensity_pct', 0.0):.1f}%" if analysis.get("growth_evaluated") == "YES" else "-",
                "YoY Revenue Growth": f"{analysis.get('revenue_growth_pct', 0.0):.1f}%" if analysis.get("growth_evaluated") == "YES" else "-",
                "Status": item.get("status")
            })
        df_evals = pd.DataFrame(rows)
        st.dataframe(df_evals, use_container_width=True)

with tab_prompts:
    st.write("### 🛠️ Refine LLM Agent Prompts & Skills")
    st.markdown("Customize the instructions and formatting guidelines sent to the LLM-powered specialized analyst agents.")
    
    cfg_prompts = load_config()
    prompts_section = cfg_prompts.get("prompts", {})
    
    with st.form("prompts_form"):
        st.write("#### 1. Technical Analysis Agent Prompt")
        tech_sys = st.text_area("System Prompt", 
                                value=prompts_section.get("technical_analysis", {}).get("system_prompt", "You are a professional quantitative technical analyst."),
                                key="tech_sys_prompt")
        
        default_tech_usr = """Analyze the following technical indicator profile for stock ticker '{symbol}':
- Current Price: ${close:.2f}
- 14-day RSI: {rsi:.1f}
- 50-day Simple Moving Average (SMA): ${sma_50:.2f}
- 200-day Simple Moving Average (SMA): ${sma_200:.2f}
- 14-day Average True Range (ATR): ${atr:.2f}
- Volume Spike Detected: {volume_spike}
{learnings_str}
Provide a verdict. You must respond in a valid JSON structure:
{{
    "verdict": "BULLISH" | "NEUTRAL" | "BEARISH",
    "score": float (0.0 to 10.0),
    "rationale": "Short analysis of indicators, support levels, and momentum."
}}
Do not add any markup or markdown wraps besides the raw JSON."""
        tech_usr = st.text_area("User Prompt Template",
                                value=prompts_section.get("technical_analysis", {}).get("user_prompt_template", default_tech_usr),
                                height=250, key="tech_usr_prompt")
        
        st.write("#### 2. Fundamental Analysis Agent Prompt")
        fund_sys = st.text_area("System Prompt",
                                value=prompts_section.get("fundamental_analysis", {}).get("system_prompt", "You are an experienced equity research analyst."),
                                key="fund_sys_prompt")
        
        default_fund_usr = """Evaluate the financial fundamentals of company ticker '{symbol}':
- Trailing P/E: {pe_ratio}
- Forward P/E: {forward_pe}
- PEG Ratio: {peg_ratio}
- Debt to Equity Ratio: {debt_to_equity}
- Year-over-Year Revenue Growth: {rev_growth}
- Profit Margin: {margin}
- Free Cash Flow: {fcf}
{learnings_str}
Provide a fundamental strength score. Verify if company is financially healthy, has clean debt margins, and positive free cash flows.
Respond in a valid JSON structure:
{{
    "verdict": "FAVORABLE" | "NEUTRAL" | "UNFAVORABLE",
    "score": float (0.0 to 10.0),
    "rationale": "Brief critique of valuation, debt burden, and growth profile."
}}
Do not add any markup or markdown wraps besides the raw JSON."""
        fund_usr = st.text_area("User Prompt Template",
                                value=prompts_section.get("fundamental_analysis", {}).get("user_prompt_template", default_fund_usr),
                                height=250, key="fund_usr_prompt")
        
        st.write("#### 3. News Sentiment Agent Prompt")
        news_sys = st.text_area("System Prompt",
                                value=prompts_section.get("news_sentiment", {}).get("system_prompt", "You are a financial news intelligence analyst."),
                                key="news_sys_prompt")
        
        default_news_usr = """Analyze the recent headlines for stock '{symbol}':
{news_summary}
{learnings_str}
Identify any negative/positive binary events (lawsuits, product recalls, FDA approvals, executive departures).
Provide a news sentiment verdict. Respond in valid JSON structure:
{{
    "verdict": "POSITIVE" | "NEUTRAL" | "NEGATIVE",
    "binary_event_detected": boolean,
    "sentiment_score": float (0.0 to 10.0),
    "rationale": "Brief summary of news landscape."
}}
Do not add any markup or markdown wraps besides the raw JSON."""
        news_usr = st.text_area("User Prompt Template",
                                value=prompts_section.get("news_sentiment", {}).get("user_prompt_template", default_news_usr),
                                height=250, key="news_usr_prompt")
        
        st.write("#### 4. Growth & R&D Analysis Agent Prompt")
        growth_sys = st.text_area("System Prompt",
                                  value=prompts_section.get("growth_rnd_evaluation", {}).get("system_prompt", "You are a growth investing specialist and corporate finance expert."),
                                  key="growth_sys_prompt")
        
        default_growth_usr = """Evaluate the growth reinvestment profile of company ticker '{symbol}':
- Latest Annual Revenue: ${revenue:,.2f}
- Latest Annual R&D Expenditure: ${rnd_exp:,.2f}
- R&D Intensity (R&D / Revenue): {rnd_intensity:.1%}
- Year-over-Year Revenue Growth: {revenue_growth:.1%}
- Net Profit Margin: {net_margin:.1%}
{learnings_str}
Determine if this company represents a high-quality growth company that is deliberately trading short-term profitability for massive R&D reinvestment and market share scaling.
Respond in a valid JSON structure:
{{
    "verdict": "FAVORABLE" | "NEUTRAL" | "UNFAVORABLE",
    "score": float (0.0 to 10.0),
    "rationale": "Critique of R&D reinvestment efficiency, revenue growth momentum, and long-term scaling outlook."
}}
Do not add any markup or markdown wraps besides the raw JSON."""
        growth_usr = st.text_area("User Prompt Template",
                                  value=prompts_section.get("growth_rnd_evaluation", {}).get("user_prompt_template", default_growth_usr),
                                  height=250, key="growth_usr_prompt")
        
        st.write("#### 📊 Quantitative Skills (Math-based, Non-LLM)")
        st.info("The remaining skills (**CalculatePositionSize**, **CalculateIndicators**, and **FetchEarningsCalendar**) are mathematical and logical modules. Their rules (RSI boundaries, stop loss percentages, position size caps) can be configured dynamically under the **Settings & Risk Rules** tab.")
        
        save_prompts_btn = st.form_submit_button("Save Prompts & Refine Skills")
        if save_prompts_btn:
            if "prompts" not in cfg_prompts:
                cfg_prompts["prompts"] = {}
                
            cfg_prompts["prompts"]["technical_analysis"] = {
                "system_prompt": tech_sys,
                "user_prompt_template": tech_usr
            }
            cfg_prompts["prompts"]["fundamental_analysis"] = {
                "system_prompt": fund_sys,
                "user_prompt_template": fund_usr
            }
            cfg_prompts["prompts"]["news_sentiment"] = {
                "system_prompt": news_sys,
                "user_prompt_template": news_usr
            }
            cfg_prompts["prompts"]["growth_rnd_evaluation"] = {
                "system_prompt": growth_sys,
                "user_prompt_template": growth_usr
            }
            
            if save_config(cfg_prompts):
                st.success("LLM Agent prompts refined and skills updated successfully!")
                st.rerun()

with tab_manual:
    st.write("### 🎯 On-Demand Ticker Analysis & Investment")
    st.markdown("Enter any stock ticker to run real-time agent evaluations and optionally execute a bracket order to add it to your portfolio.")
    
    col_t1, col_t2 = st.columns([2, 1])
    with col_t1:
        manual_ticker = st.text_input("Ticker Symbol", value="", placeholder="e.g. NVDA, TSLA, AAPL").upper().strip()
    with col_t2:
        manual_tier = st.selectbox("Risk Tier", options=["low", "moderate", "high"], index=1)
        
    run_btn = st.button("Run Real-Time Agent Analysis")
    
    if manual_ticker:
        # Cache or store the analysis in st.session_state so it persists across button clicks!
        if run_btn:
            with st.spinner(f"Running specialized agents analysis on {manual_ticker}..."):
                try:
                    import yfinance as yf
                    from src.llm import LLMClient
                    from src.skills.market_data import CalculateIndicatorsSkill
                    from src.agents.specialized import TechnicalAgent, FundamentalAgent, NewsAgent, GrowthAgent
                    
                    ticker_obj = yf.Ticker(manual_ticker)
                    df_hist = ticker_obj.history(period="1y")
                    if df_hist.empty:
                        st.error(f"Could not find historical data or ticker symbol '{manual_ticker}'")
                    else:
                        # 1. Technical Data
                        calc = CalculateIndicatorsSkill()
                        df_indicators = calc.execute(df_hist)
                        last_row = df_indicators.iloc[-1]
                        
                        # Detect volume spike
                        avg_vol = df_indicators["Volume"].rolling(20).mean().iloc[-1]
                        volume_spike = bool(last_row["Volume"] > 2 * avg_vol)
                        
                        cand_data = {
                            "symbol": manual_ticker,
                            "close": float(last_row["Close"]),
                            "rsi": float(last_row["RSI"]),
                            "sma_50": float(last_row["SMA_50"]),
                            "sma_200": float(last_row["SMA_200"]),
                            "atr": float(last_row["ATR"]),
                            "volume_spike": volume_spike
                        }
                        
                        # Initialize Agents
                        llm = LLMClient(provider=cfg.get("llm", {}).get("provider"), model=cfg.get("llm", {}).get("model"))
                        tech_agent = TechnicalAgent(llm=llm)
                        fund_agent = FundamentalAgent(llm=llm)
                        news_agent = NewsAgent(llm=llm)
                        growth_agent = GrowthAgent(llm=llm)
                        
                        # 2. Run Evaluations
                        # Earnings Shield
                        passed_shield, shield_reason = news_agent.check_earnings_shield(manual_ticker, days_range=cfg.get("rules", {}).get("earnings_shield_days", 3))
                        # News
                        news_analysis = news_agent.analyze_news(manual_ticker)
                        # Technical
                        tech_analysis = tech_agent.analyze(manual_ticker, cand_data)
                        # Fundamental
                        fund_analysis = fund_agent.analyze(manual_ticker)
                        # Growth
                        growth_analysis = growth_agent.analyze(manual_ticker)
                        
                        # Save to session_state
                        st.session_state["manual_analysis"] = {
                            "ticker": manual_ticker,
                            "cand_data": cand_data,
                            "passed_shield": passed_shield,
                            "shield_reason": shield_reason,
                            "news": news_analysis,
                            "tech": tech_analysis,
                            "fund": fund_analysis,
                            "growth": growth_analysis
                        }
                except Exception as e:
                    st.error(f"Analysis failed: {e}")
                    
        # Render analysis if present in session_state
        if "manual_analysis" in st.session_state and st.session_state["manual_analysis"]["ticker"] == manual_ticker:
            ana = st.session_state["manual_analysis"]
            cand_data = ana["cand_data"]
            
            st.write("---")
            st.write(f"### Real-Time Scorecard for {manual_ticker} (${cand_data['close']:.2f})")
            
            # Metric Columns
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.metric("Technical Score", f"{ana['tech'].get('score', 5.0):.1f}/10", ana["tech"].get("verdict"))
            with col_m2:
                st.metric("Fundamental Score", f"{ana['fund'].get('score', 5.0):.1f}/10", ana["fund"].get("verdict"))
            with col_m3:
                st.metric("News Sentiment", f"{ana['news'].get('sentiment_score', 5.0):.1f}/10", ana["news"].get("verdict"))
            with col_m4:
                st.metric("Growth R&D Score", f"{ana['growth'].get('score', 5.0):.1f}/10", ana["growth"].get("verdict"))
                
            # Details expanders
            with st.expander("📊 Technical Indicators Profile"):
                st.markdown(f"""
                - **Price**: ${cand_data['close']:.2f}
                - **14-day RSI**: {cand_data['rsi']:.1f}
                - **50-day SMA**: ${cand_data['sma_50']:.2f}
                - **200-day SMA**: ${cand_data['sma_200']:.2f}
                - **Volume Spike**: {'Yes' if cand_data['volume_spike'] else 'No'}
                - **ATR**: ${cand_data['atr']:.2f}
                
                **Technical Rationale**:
                {ana['tech'].get('rationale')}
                """)
                
            with st.expander("🏛️ Fundamentals & Financial Health"):
                st.markdown(f"""
                **Fundamental Rationale**:
                {ana['fund'].get('rationale')}
                """)
                
            with st.expander("📰 News & Binary Events"):
                st.markdown(f"""
                - **Earnings Shield Status**: {'PASSED' if ana['passed_shield'] else f'SHIELD ACTIVE ({ana["shield_reason"]})'}
                - **Binary Event Detected**: {'Yes' if ana['news'].get('binary_event_detected') else 'No'}
                
                **News Rationale**:
                {ana['news'].get('rationale')}
                """)
                
            with st.expander("🚀 Growth & R&D Reinvestment Profile"):
                st.markdown(f"""
                - **R&D Intensity**: {ana['growth'].get('rnd_intensity_pct', 0.0):.1f}%
                - **YoY Revenue Growth**: {ana['growth'].get('revenue_growth_pct', 0.0):.1f}%
                - **Net Profit Margin**: {ana['growth'].get('net_margin_pct', 0.0):.1f}%
                
                **Growth Rationale**:
                {ana['growth'].get('rationale')}
                """)
                
            # Action Section
            st.write("### 🛍️ Investment Action")
            
            # Check qualification criteria
            rules_cfg = cfg.get("rules", {})
            growth_rules = rules_cfg.get("growth_reinvestment_rules", {})
            
            passed_news = ana["news"].get("verdict") != "NEGATIVE" and ana["news"].get("sentiment_score", 5.0) >= rules_cfg.get("min_news_score", 5.0)
            passed_tech = ana["tech"].get("verdict") == "BULLISH" and ana["tech"].get("score", 5.0) >= rules_cfg.get("min_technical_score", 7.0)
            
            # Traditional Fund Pass
            passed_fund = ana["fund"].get("verdict") != "UNFAVORABLE" and ana["fund"].get("score", 5.0) >= rules_cfg.get("min_fundamental_score", 5.0)
            
            # Growth Fund Pass Override
            is_growth_override = False
            if not passed_fund and manual_tier in ["high", "moderate"] and growth_rules.get("enabled", True):
                passed_rnd = (ana["growth"].get("rnd_intensity_pct", 0.0) / 100.0) >= (growth_rules.get("min_rnd_intensity_pct", 10.0) / 100.0)
                passed_rev = (ana["growth"].get("revenue_growth_pct", 0.0) / 100.0) >= (growth_rules.get("min_revenue_growth_pct", 15.0) / 100.0)
                passed_score = ana["growth"].get("score", 5.0) >= growth_rules.get("min_growth_score", 6.5)
                if ana["growth"].get("verdict") == "FAVORABLE" and passed_rnd and passed_rev and passed_score:
                    is_growth_override = True
                    
            eligible = ana["passed_shield"] and passed_news and passed_tech and (passed_fund or is_growth_override)
            
            if eligible:
                st.success("✅ This ticker **passes all criteria** for the selected risk/return level!")
            else:
                st.warning("⚠️ This ticker **does not pass** all default screening criteria.")
                
            force_buy = st.checkbox("Force override screening filters and purchase anyway", value=False)
            
            custom_qty = 1
            if force_buy:
                custom_qty = st.number_input("Custom Purchase Quantity (Shares)", min_value=1, max_value=100, value=1, step=1)
            
            if eligible or force_buy:
                if st.button(f"Execute Buy Order for {manual_ticker}"):
                    with st.spinner("Connecting to broker and executing bracket order..."):
                        try:
                            import asyncio
                            from src.broker import BrokerAgent
                            from src.agents.specialized import RiskAgent
                            
                            # Initialize Broker Connection
                            broker = BrokerAgent(host=cfg.get("broker", {}).get("host", "127.0.0.1"),
                                                 port=int(cfg.get("broker", {}).get("port", 4002)),
                                                 client_id=int(cfg.get("broker", {}).get("client_id", 88)))
                            
                            # Risk Manager Sizing
                            risk_agent = RiskAgent(
                                max_positions=cfg.get("risk", {}).get("max_positions", 5),
                                max_cap_pct=cfg.get("risk", {}).get("max_capital_pct", 0.20),
                                risk_pct=cfg.get("risk", {}).get("risk_per_trade_pct", 0.01),
                                min_stop_loss_pct=cfg.get("risk", {}).get("min_stop_loss_pct", 0.05),
                                max_stop_loss_pct=cfg.get("risk", {}).get("max_stop_loss_pct", 0.07)
                            )
                            
                            # Calculate tier allocation target limit
                            alloc_pct = cfg.get("allocation", {}).get(f"{manual_tier}_risk_pct", 0.30)
                            target_tier_cap = net_liq * alloc_pct
                            deployed_tier_cap = sum(details.get("initial_capital", 0.0) 
                                                    for details in active_trades.values() 
                                                    if details.get("risk_tier", "moderate") == manual_tier)
                            available_tier_cap = target_tier_cap - deployed_tier_cap
                            
                            # Size position
                            sizing = risk_agent.calculate_position_size(
                                portfolio_value=net_liq,
                                entry_price=cand_data["close"],
                                atr=cand_data["atr"],
                                available_tier_capital=available_tier_cap
                            )
                            
                            qty = sizing["quantity"]
                            if force_buy:
                                qty = int(custom_qty)
                                
                            stop_loss_val = sizing.get("stop_loss_price", cand_data["close"] * 0.95)
                            
                            if qty <= 0:
                                st.error("Sizing returned 0 quantity. Insufficient allocated capital in this risk tier.")
                            else:
                                async def place_order():
                                    await broker.connect()
                                    order_id = await broker.execute_buy(manual_ticker, qty, stop_loss_val)
                                    await broker.disconnect()
                                    return order_id
                                    
                                try:
                                    loop = asyncio.get_event_loop()
                                except RuntimeError:
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    
                                order_id = loop.run_until_complete(place_order())
                                
                                if order_id:
                                    # Save new position to state
                                    state = load_state()
                                    state["active_trades"][manual_ticker] = {
                                        "entry_price": cand_data["close"],
                                        "stop_loss_price": sizing["stop_loss_price"],
                                        "quantity": qty,
                                        "initial_capital": sizing["capital_required"],
                                        "purchased_at": datetime.now().isoformat(),
                                        "order_id": order_id,
                                        "risk_tier": manual_tier,
                                        "analysis": {
                                            "news_score": ana["news"].get("sentiment_score"),
                                            "news_verdict": ana["news"].get("verdict"),
                                            "tech_score": ana["tech"].get("score"),
                                            "tech_verdict": ana["tech"].get("verdict"),
                                            "fund_score": ana["fund"].get("score") if not is_growth_override else ana["growth"].get("score"),
                                            "fund_verdict": ana["fund"].get("verdict") if not is_growth_override else "GROWTH_PLAY",
                                            "rnd_intensity_pct": ana["growth"].get("rnd_intensity_pct"),
                                            "revenue_growth_pct": ana["growth"].get("revenue_growth_pct"),
                                            "net_margin_pct": ana["growth"].get("net_margin_pct")
                                        }
                                    }
                                    
                                    # Log evaluation too
                                    eval_entry = {
                                        "symbol": manual_ticker,
                                        "risk_tier": manual_tier,
                                        "timestamp": datetime.now().isoformat(),
                                        "status": "Purchased (Manual Target)",
                                        "analysis": {
                                            "earnings_checked": "PASSED" if ana["passed_shield"] else "TRIGGERED",
                                            "news_score": ana["news"].get("sentiment_score"),
                                            "news_verdict": ana["news"].get("verdict"),
                                            "tech_score": ana["tech"].get("score"),
                                            "tech_verdict": ana["tech"].get("verdict"),
                                            "fund_score": ana["fund"].get("score") if not is_growth_override else ana["growth"].get("score"),
                                            "fund_verdict": ana["fund"].get("verdict") if not is_growth_override else "GROWTH_PLAY",
                                            "growth_evaluated": "YES" if is_growth_override else "NO",
                                            "rnd_intensity_pct": ana["growth"].get("rnd_intensity_pct"),
                                            "revenue_growth_pct": ana["growth"].get("revenue_growth_pct"),
                                            "net_margin_pct": ana["growth"].get("net_margin_pct")
                                        }
                                    }
                                    state["candidate_evaluations"].append(eval_entry)
                                    save_state(state)
                                    
                                    st.success(f"🎉 Order placed successfully! Bought {qty} shares of {manual_ticker} (Order ID: {order_id})")
                                    st.rerun()
                                else:
                                    st.error("Broker returned None for Order ID. Purchase failed.")
                        except Exception as e:
                            st.error(f"Order placement failed: {e}")

with tab3:
    st.write("### Latest Agent Execution Logs")
    logs = load_system_logs(100)
    log_text = "".join(logs)
    
    st.markdown(f"""
    <pre class="log-container">{log_text}</pre>
    """, unsafe_allow_html=True)

with tab4:
    st.write("### Configure Trading & Risk Rules")
    cfg = load_config()
    if cfg:
        with st.form("config_form"):
            st.write("#### General Settings")
            col_gen1, col_gen2 = st.columns(2)
            with col_gen1:
                dry_run = st.toggle("Dry Run Mode", value=cfg.get("trading", {}).get("dry_run", True),
                                    help="In Dry Run mode, system analyzes candidates and simulates orders without placing them at the broker.")
            with col_gen2:
                interval_minutes = st.selectbox("Execution Interval (Minutes)", options=[15, 30, 60],
                                                index=[15, 30, 60].index(cfg.get("scheduler", {}).get("interval_minutes", 30)),
                                                help="How frequently the trading agent executes scans and evaluations during market hours.")
            
            st.write("#### Broker Gateway Settings")
            col_broker1, col_broker2, col_broker3 = st.columns(3)
            with col_broker1:
                broker_host = st.text_input("Broker Host", value=cfg.get("broker", {}).get("host", "127.0.0.1"),
                                            help="IP address of the IB Gateway or TWS workstation.")
            with col_broker2:
                broker_port = st.number_input("Broker Port", min_value=1, max_value=65535, step=1,
                                              value=int(cfg.get("broker", {}).get("port", 4002)),
                                              help="API port: 4002 for paper trading, 4001 for live trading.")
            with col_broker3:
                broker_client_id = st.number_input("Broker Client ID", min_value=0, max_value=999, step=1,
                                                   value=int(cfg.get("broker", {}).get("client_id", 88)),
                                                   help="Unique client connection ID for IB Gateway API.")
            
            env_vars = load_env_vars()
            col_cred1, col_cred2 = st.columns(2)
            with col_cred1:
                broker_username = st.text_input("IBKR Username / User ID", value=env_vars.get("IBKR_USERID", ""),
                                                help="Username for your Interactive Brokers paper or live account.")
            with col_cred2:
                broker_password = st.text_input("IBKR Password", type="password", value=env_vars.get("IBKR_PASSWORD", ""),
                                                help="Password for your Interactive Brokers paper or live account.")
            
            st.write("#### Risk & Sizing Rules")
            col_risk1, col_risk2 = st.columns(2)
            with col_risk1:
                max_positions = st.number_input("Max Open Positions", min_value=1, max_value=20, step=1,
                                                value=int(cfg.get("risk", {}).get("max_positions", 5)))
                max_capital_pct = st.slider("Max Capital Per Position (%)", min_value=5, max_value=50, 
                                            value=int(cfg.get("risk", {}).get("max_capital_pct", 0.20) * 100)) / 100.0
                risk_per_trade_pct = st.slider("Portfolio Risk Per Trade (%)", min_value=0.1, max_value=5.0, step=0.1,
                                                value=float(cfg.get("risk", {}).get("risk_per_trade_pct", 0.01) * 100)) / 100.0
            with col_risk2:
                min_stop_loss_pct = st.slider("Minimum Stop Loss Distance (%)", min_value=1.0, max_value=15.0, step=0.5,
                                              value=float(cfg.get("risk", {}).get("min_stop_loss_pct", 0.05) * 100)) / 100.0
                max_stop_loss_pct = st.slider("Maximum Stop Loss Distance (%)", min_value=1.0, max_value=25.0, step=0.5,
                                              value=float(cfg.get("risk", {}).get("max_stop_loss_pct", 0.07) * 100)) / 100.0
                trail_trigger_pct = st.slider("Trailing Stop Trigger Threshold (%)", min_value=1.0, max_value=20.0, step=0.5,
                                              value=float(cfg.get("risk", {}).get("trail_trigger_pct", 0.03) * 100)) / 100.0
 
            st.write("#### Portfolio Allocation Targets")
            high_pct_val = int(cfg.get("allocation", {}).get("high_risk_pct", 0.30) * 100)
            mod_pct_val = int(cfg.get("allocation", {}).get("moderate_risk_pct", 0.40) * 100)
            low_pct_val = int(cfg.get("allocation", {}).get("low_risk_pct", 0.30) * 100)
 
            col_alloc1, col_alloc2, col_alloc3 = st.columns(3)
            with col_alloc1:
                high_risk_pct_input = st.slider("High Risk Allocation (%)", min_value=0, max_value=100, step=5, value=high_pct_val)
            with col_alloc2:
                mod_risk_pct_input = st.slider("Moderate Risk Allocation (%)", min_value=0, max_value=100, step=5, value=mod_pct_val)
            with col_alloc3:
                low_risk_pct_input = st.slider("Low Risk Allocation (%)", min_value=0, max_value=100, step=5, value=low_pct_val)
            
            total_alloc_sum = high_risk_pct_input + mod_risk_pct_input + low_risk_pct_input
            if total_alloc_sum != 100:
                st.warning(f"⚠️ Allocations currently sum to **{total_alloc_sum}%**. They MUST sum to exactly 100% to save.")

            st.write("#### Analysis Agent Skip Thresholds")
            rules_section = cfg.get("rules", {})
            col_th1, col_th2 = st.columns(2)
            with col_th1:
                min_fundamental_score = st.slider("Minimum Fundamental Score (0-10)", min_value=1.0, max_value=10.0, step=0.5,
                                                  value=float(rules_section.get("min_fundamental_score", 5.0)),
                                                  help="Skip candidates with a fundamental rating below this value.")
                min_technical_score = st.slider("Minimum Technical Score (0-10)", min_value=1.0, max_value=10.0, step=0.5,
                                                value=float(rules_section.get("min_technical_score", 7.0)),
                                                help="Skip candidates with a technical rating below this value.")
            with col_th2:
                min_news_score = st.slider("Minimum News Sentiment Score (0-10)", min_value=1.0, max_value=10.0, step=0.5,
                                           value=float(rules_section.get("min_news_score", 5.0)),
                                           help="Skip candidates with news sentiment score below this value.")
                earnings_shield_days = st.slider("Earnings Shield Window (Days)", min_value=1, max_value=10, step=1,
                                                 value=int(rules_section.get("earnings_shield_days", 3)),
                                                 help="Skip candidates if earnings date is within +/- N days.")
            
            st.write("#### Growth & R&D Reinvestment Rules")
            growth_section = rules_section.get("growth_reinvestment_rules", {})
            col_gr1, col_gr2 = st.columns(2)
            with col_gr1:
                growth_enabled = st.toggle("Enable Growth & R&D Overrides", value=bool(growth_section.get("enabled", True)),
                                           help="Allows candidates in High/Moderate risk tiers with strong revenue growth and heavy R&D intensity to pass the fundamental filter even if traditional fundamentals are unfavorable.")
                min_growth_score_val = st.slider("Minimum Growth Agent Score (0-10)", min_value=1.0, max_value=10.0, step=0.5,
                                                 value=float(growth_section.get("min_growth_score", 6.5)),
                                                 help="Qualified growth override plays must receive at least this score from the Growth Agent.")
            with col_gr2:
                min_rnd_intensity_val = st.slider("Minimum R&D Intensity (%)", min_value=0.0, max_value=40.0, step=1.0,
                                                  value=float(growth_section.get("min_rnd_intensity_pct", 10.0)),
                                                  help="Latest annual R&D expenditure divided by revenue must be at least this percentage.")
                min_revenue_growth_val = st.slider("Minimum YoY Revenue Growth (%)", min_value=0.0, max_value=50.0, step=1.0,
                                                   value=float(growth_section.get("min_revenue_growth_pct", 15.0)),
                                                   help="Latest annual year-over-year revenue growth must be at least this percentage.")

            st.write("#### Risk Tier Specifications")
            tier_rules = cfg.get("tier_rules", {})
            tier_rules_inputs = {}
            for tier in ["high", "moderate", "low"]:
                st.write(f"**{tier.upper()} RISK TIER RULES**")
                col_t1, col_t2, col_t3, col_t4 = st.columns(4)
                
                tier_conf = tier_rules.get(tier, {})
                with col_t1:
                    t_guidelines = st.text_input(f"LLM Search Guidelines ({tier})", value=tier_conf.get("guidelines", ""), key=f"{tier}_guidelines_input")
                with col_t2:
                    t_min_rsi = st.slider(f"Min RSI ({tier})", min_value=10, max_value=90, value=int(tier_conf.get("min_rsi", 45)), key=f"{tier}_min_rsi_input")
                with col_t3:
                    t_max_rsi = st.slider(f"Max RSI ({tier})", min_value=20, max_value=95, value=int(tier_conf.get("max_rsi", 70)), key=f"{tier}_max_rsi_input")
                with col_t4:
                    t_req_trend = st.toggle(f"Require Trend Shield ({tier})", value=bool(tier_conf.get("require_trend", True)), key=f"{tier}_req_trend_input")
                
                tier_rules_inputs[tier] = (t_guidelines, t_min_rsi, t_max_rsi, t_req_trend)
 
            st.write("#### Watchlist Tickers")
            current_watchlist = ", ".join(cfg.get("watchlist", []))
            watchlist_text = st.text_area("Watchlist (comma-separated tickers)", value=current_watchlist, 
                                          help="Enter ticker symbols separated by commas (e.g. AAPL, MSFT, NVDA).")
            
            submit_btn = st.form_submit_button("Save Configuration & Rules")
            if submit_btn:
                if total_alloc_sum != 100:
                    st.error("Cannot save: Portfolio Allocation Targets must sum to exactly 100%.")
                else:
                    if "trading" not in cfg:
                        cfg["trading"] = {}
                    cfg["trading"]["dry_run"] = dry_run
                    
                    if "risk" not in cfg:
                        cfg["risk"] = {}
                    cfg["risk"]["max_positions"] = max_positions
                    cfg["risk"]["max_capital_pct"] = max_capital_pct
                    cfg["risk"]["risk_per_trade_pct"] = risk_per_trade_pct
                    cfg["risk"]["min_stop_loss_pct"] = min_stop_loss_pct
                    cfg["risk"]["max_stop_loss_pct"] = max_stop_loss_pct
                    cfg["risk"]["trail_trigger_pct"] = trail_trigger_pct
                    
                    if "allocation" not in cfg:
                        cfg["allocation"] = {}
                    cfg["allocation"]["high_risk_pct"] = high_risk_pct_input / 100.0
                    cfg["allocation"]["moderate_risk_pct"] = mod_risk_pct_input / 100.0
                    cfg["allocation"]["low_risk_pct"] = low_risk_pct_input / 100.0
                    
                    if "scheduler" not in cfg:
                        cfg["scheduler"] = {}
                    cfg["scheduler"]["interval_minutes"] = interval_minutes
                    
                    if "broker" not in cfg:
                        cfg["broker"] = {}
                    cfg["broker"]["host"] = broker_host
                    cfg["broker"]["port"] = broker_port
                    cfg["broker"]["client_id"] = broker_client_id
                    
                    if "rules" not in cfg:
                        cfg["rules"] = {}
                    cfg["rules"]["min_fundamental_score"] = min_fundamental_score
                    cfg["rules"]["min_technical_score"] = min_technical_score
                    cfg["rules"]["min_news_score"] = min_news_score
                    cfg["rules"]["earnings_shield_days"] = earnings_shield_days
                    
                    if "growth_reinvestment_rules" not in cfg["rules"]:
                        cfg["rules"]["growth_reinvestment_rules"] = {}
                    cfg["rules"]["growth_reinvestment_rules"]["enabled"] = growth_enabled
                    cfg["rules"]["growth_reinvestment_rules"]["min_growth_score"] = min_growth_score_val
                    cfg["rules"]["growth_reinvestment_rules"]["min_rnd_intensity_pct"] = min_rnd_intensity_val
                    cfg["rules"]["growth_reinvestment_rules"]["min_revenue_growth_pct"] = min_revenue_growth_val

                    if "tier_rules" not in cfg:
                        cfg["tier_rules"] = {}
                    for tier in ["high", "moderate", "low"]:
                        t_g, t_min, t_max, t_req = tier_rules_inputs[tier]
                        cfg["tier_rules"][tier] = {
                            "guidelines": t_g,
                            "min_rsi": int(t_min),
                            "max_rsi": int(t_max),
                            "require_trend": bool(t_req)
                        }
                    
                    watchlist_list = [t.strip().upper() for t in watchlist_text.split(",") if t.strip()]
                    cfg["watchlist"] = watchlist_list
                    
                    if save_config(cfg):
                        # Save environment variables and check for docker restart
                        trading_mode = "live" if broker_port == 4001 else "paper"
                        credentials_changed = (
                            broker_username != env_vars.get("IBKR_USERID") or
                            broker_password != env_vars.get("IBKR_PASSWORD") or
                            trading_mode != env_vars.get("IBKR_TRADING_MODE")
                        )
                        
                        if save_env_vars(broker_username, broker_password, trading_mode):
                            if credentials_changed:
                                try:
                                    # Restart docker container
                                    subprocess.run(["docker", "compose", "-f", "docker-compose.ib.yaml", "down"], check=False)
                                    subprocess.run(["docker", "compose", "-f", "docker-compose.ib.yaml", "up", "-d"], check=False)
                                    st.info("Credentials or mode changed. IB Gateway container restarted. Please check MFA on your mobile device.")
                                except Exception as e:
                                    st.error(f"Failed to restart IB Gateway container: {e}")
 
                            # Update systemd timer on EC2 host if running on Linux
                            update_systemd_timer(interval_minutes)
                            st.success("Configuration saved successfully! The next trading cycle will use these settings.")
                            st.rerun()

st.sidebar.write("### Account Summary")
st.sidebar.metric("Net Liquidation", f"${net_liq:,.2f}")
st.sidebar.metric("Available Cash", f"${cash:,.2f}")

st.sidebar.write("### Broker Session")
if st.sidebar.button("🔌 Reconnect Broker & Trigger 2FA"):
    with st.spinner("Reconnecting to live gateway..."):
        try:
            # Run docker compose restart command
            subprocess.run(["docker", "compose", "-f", "docker-compose.ib.yaml", "down"], check=False)
            subprocess.run(["docker", "compose", "-f", "docker-compose.ib.yaml", "up", "-d"], check=False)
            st.sidebar.success("Gateway restarted. Check your device for the 2FA push!")
        except Exception as e:
            st.sidebar.error(f"Failed to restart gateway: {e}")

st.sidebar.write("### Agent Control")
if st.sidebar.button("🚀 Run Trading Cycle Now"):
    with st.spinner("Executing live trading cycle scan and evaluation..."):
        try:
            python_bin = sys.executable
            proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            main_py_path = os.path.join(proj_root, "src", "main.py")
            env = os.environ.copy()
            env["PYTHONPATH"] = proj_root
            result = subprocess.run([python_bin, main_py_path], cwd=proj_root, env=env, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                st.sidebar.success("Trading cycle completed successfully!")
                st.rerun()
            else:
                st.sidebar.error(f"Cycle failed: {result.stderr or result.stdout}")
        except Exception as e:
            st.sidebar.error(f"Failed to execute trading cycle: {e}")

# Auto Refresh UI Checkbox
st.sidebar.write("### Refresh Controls")
if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

st.sidebar.info("Dashboard pulls state from trading_state.json and fetches real-time prices dynamically using Yahoo Finance API.")
