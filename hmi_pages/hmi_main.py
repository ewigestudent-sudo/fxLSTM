import streamlit as st
import json
import os
import tempfile
from pathlib import Path
from config import HMI_COMMANDS_PATH, BOT_STATES_PATH, IS_SIMULATION
from system_base.logger import get_logger

log = get_logger("DatabaseManager")

def load_css():
    """Загружает CSS-файл с тем же именем, что и текущий .py файл."""
    current_file = Path(__file__)
    css_file = current_file.with_suffix(".css")
    if css_file.exists():
        with open(css_file, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Подключаем стили hmi_main.css
load_css()

def _send_cmd(aid, action, value=True):
    """Безопасная атомарная отправка команды.
    command_name: FORCE_TRAIN, FORCE_FIT, FORCE_TEST, AUTO_TRAIN, AUTO_FIT, AUTO_TEST, PAUSE
    """
    cmd_key = f"{action}_{aid}" if aid else action
    try:
        current_cmds = {}
        if os.path.exists(HMI_COMMANDS_PATH):
            try:
                with open(HMI_COMMANDS_PATH, "r") as f:
                    current_cmds = json.load(f)
            except: pass
        
        # Если команда системная (глобальная), используем SYSTEM, иначе ID бота
        target_key = bot_id if bot_id else "SYSTEM"
        
        # Формируем структуру согласно требованиям 2026
        current_cmds[target_key] = {
            "active": True,
            "is_sim": IS_SIMULATION,
            "command": command_name,
            "permission": str(permission)  # Сохраняем как строку или bool по вашему желанию
        }
        
        fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(HMI_COMMANDS_PATH), text=True)
        with os.fdopen(fd, 'w', encoding="utf-8") as f:
            json.dump(current_cmds, f, indent=4, ensure_ascii=False)
        os.replace(temp_path, HMI_COMMANDS_PATH)
        
        # Логирование в журнал
        log.info(f"{target_key}: Подана команда {command_name} (Permission: {permission})")
        st.toast(f"Команда {command_name} отправлена для {target_key}")
        
    except Exception as e:
        st.error(f"Error: {e}")

def render_main_page():
    st.title(f"🚀 Monitor: {st.session_state.get('trading_mode', 'Active')}")

    bot_states = {}
    if os.path.exists(BOT_STATES_PATH):
        try:
            with open(BOT_STATES_PATH, "r") as f:
                bot_states = json.load(f)
        except: pass

    if st.button("▶️ START ALL (EDU -> TEST -> TRADE)", use_container_width=True, type="primary"):
        _send_cmd(None, "START_AUTO_ALL")

    st.divider()

    if not st.session_state.get('bots_list'):
        st.info("No bots configured.")
        return

    # Переработанная шапка: добавляем колонку для роли модели
    st.write("### Активные иерархические связки")
    
    for bot in st.session_state.get('bots_list', []):
        pair = bot['pair']
        magic = bot.get('magic', 'N/A')
        
        # Индикатор PERMISSION для всей связки (из состояния пары)
        pair_key = f"{pair}_{magic}"
        pair_state = bot_states.get(pair_key, {})
        permission = pair_state.get("permission", "RED")
        lamp = "🟢" if permission == "GREEN" else "🔴"
        
        # Контейнер для связки
        with st.container(border=True):
            cols_head = st.columns([4, 1, 1])
            cols_head.markdown(f"#### {lamp} Пара: {pair} | Magic: `{magic}`")
            
            # Общий заголовок таблицы внутри связки
            h_cols = st.columns([2, 0.8, 0.8, 0.8, 0.8, 1.2, 1.2])
            headers = ["РОЛЬ / ID / CONF", "EDU", "FIT", "TEST", "AUTO", "TRADE", "STATUS"]
            for col, text in zip(h_cols, headers):
                col.caption(text)

            # Итерируем по двум моделям: Младшая (JR) и Старшая (SR)
            for role in ["JR", "SR"]:
                role_name = "Младшая" if role == "JR" else "Старшая"
                tf = bot['jr_tf'] if role == "JR" else bot['sr_tf']
                bot_id = f"{pair}_{tf}"
                
                state = bot_states.get(bot_id, {})
                status = state.get("status", "WAIT")
                mse = state.get("mse", "0.000")
                conf = state.get("confidence", "0%") # Берем из stat.py через bot_states
                
                # Логика блокировки кнопки TRADE (исправлено: зависит от статуса конкретной модели)
                is_locked = status not in ["OK"]

                col_id, col_edu, col_fit, col_test, col_auto, col_trade, col_status = st.columns([2, 0.8, 0.8, 0.8, 0.8, 1.2, 1.2])

                # Вывод: Роль, ТФ, MSE и Доверие
                col_id.markdown(f"**{role_name}** ({tf})  \n`MSE: {mse}` | **Conf:** `{conf}`")

                # Кнопки управления (с исправленным синтаксисом кавычек)
                if col_edu.button("🎓", key=f"e_{bot_id}", help="EDUCATION"):
                    _send_cmd(bot_id, "FORCE_TRAIN")
                
                if col_fit.button("🔧", key=f"f_{bot_id}", help="FIT"):
                    _send_cmd(bot_id, "FORCE_FIT")
                    
                if col_test.button("🧪", key=f"t_{bot_id}", help="TEST"):
                    _send_cmd(bot_id, "FORCE_TEST")

                if col_auto.button("🔄", key=f"a_{bot_id}", help="AUTO CYCLE"):
                    _send_cmd(bot_id, "start_auto_cycle")
                
                # Кнопка TRADE: Глобальный запуск связки (обычно посылается для всей пары)
                if col_trade.button("✅ TRADE", key=f"p_{bot_id}", type="primary", 
                                   use_container_width=True, disabled=is_locked):
                    _send_cmd(bot_id, "start_trade")
                
                # Статус модели текстом
                col_status.code(status, language=None)

    if IS_SIMULATION:
        st.caption("ℹ️ Sim Mode Active")

