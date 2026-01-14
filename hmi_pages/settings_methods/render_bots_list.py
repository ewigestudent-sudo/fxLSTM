# /hmi_pages/settings_methods/render_bots_list.py
import streamlit as st
from .save_bots_to_disk import save_bots_to_disk
from system_base.logger import get_logger

log = get_logger("DatabaseManager")

def render_bots_list(bots_list):
    """Отрисовка списка существующих агентов в UI."""
    if not bots_list:
        st.caption("Список торговых пар пуст. Добавьте первую пару ниже.")
        return

    for idx, bot in enumerate(bots_list):
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            c1.info(f"Пара: **{bot['pair']}**")
            c2.info(f"ТФ: **{bot['tf']}**")
            c3.empty() 
            if c4.button("➖", key=f"del_{idx}", use_container_width=True):
                log.info(f"Удалён бот {idx}")
                st.session_state.bots_list.pop(idx)
                save_bots_to_disk()
                st.rerun()
