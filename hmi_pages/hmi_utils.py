# FILE: hmi_pages/hmi_utils.py

import streamlit as st
import json
import os

# Путь к конфигу будет импортирован в hmi.py
# from root import config as cfg 

def load_app_settings(config_path):
    """Загрузка системного конфига (app_config.json)"""
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"show_mode_dialog": True, "saved_mode": "REAL", "trading_allowed": False, "bots_list": []}

def save_app_settings(settings, config_path):
    """Сохранение системного конфига"""
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)

@st.dialog("Настройка запуска системы 2026")
def startup_dialog(config_path):
    st.write("Приветствуем! Выберите режим работы для текущей сессии:")
    
    current_settings = load_app_settings(config_path)
    
    mode = st.radio("Режим работы ядра:", 
                    ["Симуляция (Simulation)", "Реальная торговля (Real Mode)"], 
                    index=1 if current_settings.get("saved_mode") == "REAL" else 0)
    
    remember = st.checkbox("Запомнить выбор и не показывать это окно при следующем запуске", 
                           value=not current_settings.get("show_mode_dialog", True))
    
    st.info("Примечание: Выбор режима влияет на используемую БД и точность обучения.")

    if st.button("ПОДТВЕРДИТЬ И ВОЙТИ", use_container_width=True):
        current_settings["saved_mode"] = "REAL" if "Реальная" in mode else "SIM"
        current_settings["show_mode_dialog"] = not remember
        save_app_settings(current_settings, config_path)
        
        st.session_state["session_initialized"] = True
        st.success("Настройки применены! Перезагрузка...")
        st.rerun()
