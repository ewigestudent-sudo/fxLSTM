# FILE: root/hmi_pages/settings_methods/render_add_bot_row.py
import streamlit as st
from .get_available_assets import get_available_assets
from .save_bots_to_disk import save_bots_to_disk
from system_base.logger import get_logger

log = get_logger("DatabaseManager")

def render_add_bot_row(is_sim_mode):
    """Отрисовка формы добавления иерархической связки (JR + SR)."""
    assets = get_available_assets()
    p_key = "yfinance" if is_sim_mode else "mt5"

    if st.session_state.get('row_adding'):
        with st.container(border=True):
            # Расширяем колонки для размещения двух селекторов ТФ
            r1, r2_jr, r2_sr, r3, r4 = st.columns([2, 1, 1, 1, 1])
            
            # 1. Выбор пары
            new_p = r1.selectbox("Пара", assets[p_key]["symbols"], key="new_p", 
                                 label_visibility="collapsed", placeholder="Символ", index=None)
            
            # 2. Выбор Младшего ТФ (JR)
            new_t_jr = r2_jr.selectbox("JR TF", assets[p_key]["timeframes"], key="new_t_jr", 
                                       label_visibility="collapsed", placeholder="ТФ JR", index=None)
            
            # 3. Выбор Старшего ТФ (SR)
            new_t_sr = r2_sr.selectbox("SR TF", assets[p_key]["timeframes"], key="new_t_sr", 
                                       label_visibility="collapsed", placeholder="ТФ SR", index=None)
            
            # 4. Кнопка настройки LSTM (вызывает диалог с вкладками)
            if r3.button("⚙️ LSTM", use_container_width=True):
                if new_p and new_t_jr and new_t_sr:
                    st.session_state.lstm_ready = True
                    st.rerun()
                else:
                    st.error("Заполните Пару и оба ТФ!")
            
            # 5. Подтверждение (Apply)
            if r4.button("APPLY", type="primary", use_container_width=True):
                if new_p and new_t_jr and new_t_sr:
                    # Проверка: ТФ не должны быть одинаковыми (фича 2026)
                    if new_t_jr == new_t_sr:
                        st.error("Таймфреймы должны различаться!")
                        return

                    # Генерация уникального Magic для связки (2026000 + индекс)
                    new_magic = 2026000 + len(st.session_state.bots_list)
                    
                    st.session_state.bots_list.append({
                        "pair": new_p, 
                        "jr_tf": new_t_jr, 
                        "sr_tf": new_t_sr,
                        "magic": new_magic
                    })
                    
                    log.info(f"Создана иерархическая связка {new_p} (JR:{new_t_jr}/SR:{new_t_sr}) Magic:{new_magic}")
                    save_bots_to_disk()
                    st.session_state.row_adding = False
                    st.rerun()
                else:
                    st.error("Заполните все поля!")
    else:
        if st.button("➕ Добавить иерархическую пару", use_container_width=True):
            st.session_state.row_adding = True
            st.rerun()

