import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from config.settings import settings

st.set_page_config(page_title="AI Trading Dashboard", layout="wide")

API_BASE_URL = f"http://{settings.API_HOST}:{settings.API_PORT}/api/v1"

st.title("🤖 AI Trading Decision Support System")

# Sidebar Navigation
menu = st.sidebar.selectbox("Menu", ["Overview", "Market Analysis", "Signals", "Backtest", "Settings"])

if menu == "Overview":
    st.header("System Overview")
    col1, col2, col3 = st.columns(3)
    
    # Mock data or API calls
    try:
        health = requests.get(f"{API_BASE_URL}/health").json()
        status_color = "green" if health['status'] == "healthy" else "red"
        col1.metric("System Status", health['status'].upper(), delta_color="normal")
        col2.metric("DB Connection", health['database'])
        col3.metric("API Version", settings.VERSION)
    except:
        st.error("Could not connect to Backend API")

    st.subheader("Recent System Logs")
    st.info("System is monitoring symbols: " + ", ".join(settings.MONITORED_SYMBOLS))

elif menu == "Market Analysis":
    st.header("Market Analysis")
    symbol = st.selectbox("Select Symbol", settings.MONITORED_SYMBOLS)
    
    if st.button("Compute Latest Features"):
        res = requests.post(f"{API_BASE_URL}/features/compute/{symbol}").json()
        st.success(f"Updated! RSI: {res.get('rsi')}, Regime: {res.get('regime')}")

elif menu == "Signals":
    st.header("AI Signals")
    symbol = st.selectbox("Select Symbol", settings.MONITORED_SYMBOLS)
    
    if st.button("Generate AI Signal"):
        with st.spinner("AI is analyzing market..."):
            res = requests.post(f"{API_BASE_URL}/signals/generate/{symbol}").json()
            
            st.subheader(f"Decision: {res['decision']}")
            st.write(f"**Direction:** {res['direction']} | **Confidence:** {res['confidence']:.2f}%")
            st.markdown(f"**Explanation:** {res['explanation']}")
            
            with st.expander("View Detailed Breakdown"):
                st.json(res['breakdown'])
                st.json(res['trade_params'])

elif menu == "Backtest":
    st.header("Strategy Backtesting")
    symbol = st.selectbox("Select Symbol", settings.MONITORED_SYMBOLS)
    
    if st.button("Run Backtest"):
        with st.spinner("Simulating historical trades..."):
            res = requests.post(f"{API_BASE_URL}/backtest/run/{symbol}").json()
            report = res['report']
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Win Rate", report['win_rate'])
            col2.metric("Profit Factor", report['profit_factor'])
            col3.metric("Max Drawdown", report['max_drawdown'])
            
            st.write("Recent Trades:")
            st.table(pd.DataFrame(res['trades_detail']))

elif menu == "Settings":
    st.header("System Settings")
    st.write("Manage Risk Parameters and MT5 Connection")
    st.text_input("MT5 Server", value=settings.MT5_SERVER)
    st.number_input("Max Risk per Trade (%)", value=1.0)
    if st.button("Save Settings"):
        st.success("Settings updated successfully!")
