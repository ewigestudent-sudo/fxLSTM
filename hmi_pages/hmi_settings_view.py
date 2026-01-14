import streamlit as st
from root.config import load_app_config
import hmi_pages.settings_methods as mth

def show_settings_view():
    """Главная страница настроек 2026."""
    if 'lstm_ready' not in st.session_state: st.session_state['lstm_ready'] = False
    if 'row_adding' not in st.session_state: st.session_state['row_adding'] = False
    
    st.header("⚙️ Настройки системы (2026)")
    
    app_cfg = load_app_config()
    is_sim = (app_cfg.get('saved_mode', 'SIM') == 'SIM')
    
    # Системные действия
    if not is_sim:
        if st.button("🔑 Login MT5"): mth.login_dialog()

    if st.button(f"🗑️ СБРОСИТЬ {('SIM' if is_sim else 'REAL')}", type="primary", use_container_width=True):
        mth.clear_system_databases()
        st.rerun()

    st.divider()

    # Секция ботов (Рендеринг через выносные функции)
    st.subheader("Конфигурация ботов")
    current_bots = st.session_state.get('bots_list', app_cfg.get("bots_list", []))
    st.session_state.bots_list = current_bots
    
    mth.render_bots_list(current_bots)      # Вызов из модуля методов
    mth.render_add_bot_row(is_sim)          # Вызов из модуля методов

    # Диалоги
    if st.session_state.get('lstm_ready'):
        mth.lstm_settings_dialog()
