# hmi_pages/settings_methods/clear_system_databases.py

import os, json, streamlit as st
from root import config as cfg

def clear_system_databases():
    """Полная очистка торговой истории текущего режима."""
    if os.path.exists(cfg.DB_PATH):
        os.remove(cfg.DB_PATH)
    if os.path.exists(cfg.BOT_STATES_PATH):
        with open(cfg.BOT_STATES_PATH, "w") as f:
            json.dump({}, f)
    st.session_state.bots_list.clear()
    # Импортируем локально во избежание круговых зависимостей
    from .save_bots_to_disk import save_bots_to_disk
    save_bots_to_disk()
