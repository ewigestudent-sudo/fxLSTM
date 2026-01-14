# FILE: root/hmi.py
# LOCATION: PROJ_AI_FOREX_2026/root/
# DESCRIPTION: Точка входа HMI. Выбор режима при старте и навигация.

import streamlit as st
import os
import sys

# --- 1. КОРРЕКТИРОВКА ПУТЕЙ ДЛЯ СТРАНИЦ ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from root import config as cfg
# Импорт утилит и страниц
from hmi_pages.hmi_utils import load_app_settings, startup_dialog
import hmi_pages.hmi_main as hmi_main
from hmi_pages.hmi_settings_view import show_settings_view 
import hmi_pages.hmi_soe as hmi_soe
import hmi_pages.hmi_stat as hmi_stat
import hmi_pages.hmi_charts as hmi_charts


# --- ОСНОВНОЙ ИНТЕРФЕЙС ---

st.set_page_config(
    page_title="AI FOREX ORCHESTRATOR 2026", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

def main():
    # Передаем путь к конфигу в утилитарные функции
    settings = load_app_settings(cfg.APP_CONFIG_PATH)

    # 1. Проверка необходимости диалога запуска
    if settings.get("show_mode_dialog") and "session_initialized" not in st.session_state:
        startup_dialog(cfg.APP_CONFIG_PATH)
        st.stop()

    # 2. Инициализация списка ботов из файла (СИНХРОНИЗАЦИЯ С ФАЙЛОМ)
    if 'bots_list' not in st.session_state:
        st.session_state.bots_list = settings.get("bots_list", [])

    # 3. Определение необходимости показа боковой панели
    is_first_run = len(st.session_state.bots_list) == 0

    page = "⚙️ Настройки" # Дефолтная страница

 # 4. Логика отображения интерфейса и навигации (ИСПРАВЛЕННАЯ ВЕРСИЯ)
    if is_first_run:
        # Если список пуст, скрываем сайдбар и сразу показываем настройки
        st.sidebar.empty()
        st.sidebar.warning("⚠️ Требуется настройка пар")
        # Принудительно рендерим только страницу настроек в основном поле
        show_settings_view()
    else:
        # Если список НЕ пуст, показываем сайдбар и меню
        
        with st.sidebar:
            st.title("🤖 AI Orchestrator")
            mode_val = "SIMULATION" if cfg.IS_SIMULATION else "REAL-TIME"
            mode_color = "orange" if cfg.IS_SIMULATION else "#00FF00"
            st.markdown(f"Core: <span style='color:{mode_color}'>● <b>{mode_val}</b></span>", unsafe_allow_html=True)

            page = st.radio("Меню управления:", 
                ["📡 Мониторинг", "⚙️ Настройки", "📈 Аналитика", "📊 Кривые", "📜 Журнал (SOE)"])

            st.divider()
            
            if st.button("🚨 EMERGENCY STOP", type="primary", use_container_width=True):
                hmi_main._send_cmd(None, "STOP_ALL")
                st.error("Команда STOP_ALL отправлена!")

            if st.button("🧹 Clear Commands", use_container_width=True):
                if os.path.exists(cfg.HMI_COMMANDS_PATH):
                    os.remove(cfg.HMI_COMMANDS_PATH)
                    st.toast("Очередь команд очищена")

        # 5. Рендеринг страниц в основном поле, когда сайдбар активен
        if page == "📡 Мониторинг":
            hmi_main.render_main_page()
            
        elif page == "⚙️ Настройки":
            show_settings_view()
            
        elif page == "📈 Аналитика":
            current_agents = [f"{b['pair']}_{b['tf']}" for b in st.session_state.get('bots_list', [])]
            hmi_stat.render_stat_page(current_agents)
            
        elif page == "📊 Кривые":
            hmi_charts.render_charts_page()
            
        elif page == "📜 Журнал (SOE)":
            current_agents = [f"{b['pair']}_{b['tf']}" for b in st.session_state.get('bots_list', [])]
            hmi_soe.render_soe_page(current_agents)
            
        else:
            st.info(f"Раздел '{page}' не найден.")


if __name__ == "__main__":
    main()
