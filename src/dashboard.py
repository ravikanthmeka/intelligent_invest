import os
import json
import pandas as pd
import yfinance as yf
import streamlit as st
from datetime import datetime

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

# Fetch state
state = load_trading_state()
active_trades = state.get("active_trades", {})

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
        <div class="kpi-title">Current Portfolio Value</div>
        <div class="kpi-val">${total_market_value:,.2f}</div>
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

# Layout: Main Body
tab1, tab2 = st.tabs(["📊 Active Positions", "📜 System Logs"])

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
    st.write("### Latest Agent Execution Logs")
    logs = load_system_logs(100)
    log_text = "".join(logs)
    
    st.markdown(f"""
    <pre class="log-container">{log_text}</pre>
    """, unsafe_allow_html=True)

# Auto Refresh UI Checkbox
st.sidebar.write("### Refresh Controls")
if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

st.sidebar.info("Dashboard pulls state from trading_state.json and fetches real-time prices dynamically using Yahoo Finance API.")
