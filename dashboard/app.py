import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from config.settings import settings

API_BASE = f'http://{settings.API_HOST}:{settings.API_PORT}'
# Allow override via environment for Docker setups
import os
API_BASE = os.environ.get('API_BASE_URL', f'http://localhost:{settings.API_PORT}')

st.set_page_config(
    page_title='AI Trading System',
    page_icon='🤖',
    layout='wide',
    initial_sidebar_state='expanded',
)

# ------------------------------------------------------------------ #
#  Helpers                                                            #
# ------------------------------------------------------------------ #

def api_get(path: str):
    try:
        r = requests.get(f'{API_BASE}{path}', timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return None
    except Exception:
        return None


def api_post(path: str):
    try:
        r = requests.post(f'{API_BASE}{path}', timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {'error': str(e)}


def status_badge(val: str):
    colors = {'EXECUTE': '🟢', 'ALERT': '🟡', 'HOLD': '⚪', 'BUY': '🟢', 'SELL': '🔴'}
    return f"{colors.get(val, '⚪')} {val}"


# ------------------------------------------------------------------ #
#  Sidebar                                                            #
# ------------------------------------------------------------------ #
with st.sidebar:
    st.title('🤖 AI Trading')
    st.caption(f'API: `{API_BASE}`')

    health = api_get('/api/v1/health')
    if health:
        db_ok  = health.get('database') == 'connected'
        st.metric('Database', '✅ Connected' if db_ok  else '❌ Error')
        st.metric('API',      '✅ Online')
    else:
        st.error('❌ API Offline — is the server running?')

    st.divider()
    selected_symbol = st.selectbox('Symbol', settings.MONITORED_SYMBOLS)
    st.divider()
    if st.button('🔄 Refresh Data', use_container_width=True):
        st.rerun()

# ------------------------------------------------------------------ #
#  Main Tabs                                                          #
# ------------------------------------------------------------------ #
tab_signals, tab_train, tab_market, tab_health = st.tabs([
    '📊 Signals', '🧠 Model Training', '📈 Market Data', '🔧 System Health'
])

# ========== Tab 1: Signals ========== #
with tab_signals:
    st.header(f'Signal: {selected_symbol}')

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button('⚡ Compute Features', use_container_width=True):
            with st.spinner('Computing...'):
                res = api_post(f'/api/v1/features/compute/{selected_symbol}')
            if res and 'error' not in res:
                st.success('Features computed!')
                st.json(res)
            else:
                st.error(f'Error: {res}')

    with col2:
        if st.button('🔮 Generate Signal', use_container_width=True):
            with st.spinner('Generating signal...'):
                res = api_post(f'/api/v1/signals/generate/{selected_symbol}')
            if res and 'error' not in res:
                decision  = res.get('decision', 'N/A')
                direction = res.get('direction', 'N/A')
                conf      = res.get('confidence', 0)

                d_col = {'EXECUTE': 'green', 'ALERT': 'orange', 'HOLD': 'gray'}
                st.markdown(f"### :{d_col.get(decision, 'gray')}[{status_badge(decision)}]")

                m1, m2, m3 = st.columns(3)
                m1.metric('Direction',  status_badge(direction))
                m2.metric('Confidence', f'{conf:.1f}%')
                m3.metric('R:R', res.get('trade_params', {}).get('risk_reward', 'N/A'))

                if res.get('trade_params'):
                    tp = res['trade_params']
                    st.subheader('Trade Levels')
                    st.table(pd.DataFrame([{
                        'Entry':  tp.get('entry'),
                        'SL':     tp.get('stop_loss'),
                        'TP1':    tp.get('take_profit_1'),
                        'TP2':    tp.get('take_profit_2'),
                        'Risk Pips': tp.get('risk_pips'),
                    }]))

                with st.expander('Score Breakdown'):
                    breakdown = res.get('breakdown', {})
                    if breakdown:
                        chart_df = pd.DataFrame(
                            list(breakdown.items()),
                            columns=['Component', 'Score']
                        ).set_index('Component')
                        st.bar_chart(chart_df)

                with st.expander('Explanation'):
                    st.write(res.get('explanation', 'N/A'))
            else:
                st.error(f'Error: {res}')

    with col3:
        if st.button('📡 Poll Market Data', use_container_width=True):
            with st.spinner('Polling MT5...'):
                res = api_post(f'/api/v1/market/poll?symbol={selected_symbol}')
            if res:
                st.success(f"Queued: {res.get('status', res)}")
            else:
                st.error('Failed to poll')

# ========== Tab 2: Model Training ========== #
with tab_train:
    st.header('🧠 Model Training')
    st.info('Training uses the last 100+ computed feature records. Make sure to poll + compute features first.')

    if st.button(f'🚀 Train Model for {selected_symbol}', use_container_width=True):
        with st.spinner('Training... this may take 1–2 minutes'):
            res = api_post(f'/api/v1/model/train/{selected_symbol}')
        if res and 'error' not in res:
            st.success(f"Training queued: task_id = {res.get('task_id')}")
            st.caption('Check Celery worker logs for progress.')
        else:
            st.error(f'Error: {res}')

# ========== Tab 3: Market Data ========== #
with tab_market:
    st.header('📈 Market Data Poll')
    st.write('Trigger a full poll for all monitored symbols.')
    if st.button('🔄 Poll All Symbols', use_container_width=True):
        with st.spinner('Polling all symbols...'):
            res = api_post('/api/v1/market/poll')
        if res:
            st.success(f"Queued {res.get('count', '?')} tasks for: {res.get('symbols', [])}")
        else:
            st.error('Failed to poll')

    st.divider()
    st.subheader('Manual Symbol Poll')
    if st.button(f'Poll {selected_symbol}', use_container_width=True):
        with st.spinner(f'Polling {selected_symbol}...'):
            res = api_post(f'/api/v1/market/poll?symbol={selected_symbol}')
        if res:
            st.json(res)

# ========== Tab 4: System Health ========== #
with tab_health:
    st.header('🔧 System Health')
    health = api_get('/api/v1/health')
    if health:
        h1, h2, h3 = st.columns(3)
        h1.metric('Overall Status', health.get('status', 'unknown').upper())
        h2.metric('Database',       health.get('database', 'unknown'))
        h3.metric('Redis',          health.get('redis',    'unknown'))
        st.caption(f'Last checked: {datetime.now().strftime("%H:%M:%S")}')
    else:
        st.error('❌ Cannot reach API. Make sure `uvicorn api.main:app` is running.')
        st.code('uvicorn api.main:app --reload', language='bash')
