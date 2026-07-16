import os
import json
import pandas as pd
import yfinance as yf
import streamlit as st
import yaml
import subprocess
import platform
from datetime import datetime

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

def update_systemd_timer(interval_minutes: int):
    if platform.system() != "Linux":
        return
        
    on_calendar = "Mon-Fri *-*-* 09,10,11,12,13,14,15:00,30:00"
    if interval_minutes == 15:
        on_calendar = "Mon-Fri *-*-* 09,10,11,12,13,14,15:00,15,30,45:00"
    elif interval_minutes == 60:
        on_calendar = "Mon-Fri *-*-* 09,10,11,12,13,14,15:00:00"
        
    timer_content = f"""[Unit]
Description=Run Intelligent Invest Trading Cycle every {interval_minutes} minutes during trading hours

[Timer]
OnCalendar={on_calendar}
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

portfolio_total = 100000.0  # Dry-run baseline
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
    """, unsafe_allow_html=True)

# Layout: Main Body
tab1, tab2, tab3 = st.tabs(["📊 Active Positions", "📜 System Logs", "⚙️ settings & Risk Rules"])

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

with tab3:
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
                    
                    watchlist_list = [t.strip().upper() for t in watchlist_text.split(",") if t.strip()]
                    cfg["watchlist"] = watchlist_list
                    
                    if save_config(cfg):
                        # Update systemd timer on EC2 host if running on Linux
                        update_systemd_timer(interval_minutes)
                        st.success("Configuration saved successfully! The next trading cycle will use these settings.")
                        st.rerun()

# Auto Refresh UI Checkbox
st.sidebar.write("### Refresh Controls")
if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

st.sidebar.info("Dashboard pulls state from trading_state.json and fetches real-time prices dynamically using Yahoo Finance API.")
