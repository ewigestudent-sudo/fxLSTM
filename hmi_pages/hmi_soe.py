import streamlit as st
import sqlite3
import pandas as pd
import os
# Импортируем только то, что нужно для определения путей динамически
from config import DB_DIR, IS_SIMULATION
# Импортируем путь к системной БД, который мы определили в логгере
from system_base.logger import SYSTEM_DB_PATH 

# Функция для определения пути к торговой БД на лету
def get_trading_db_path():
    db_name = "simulation_main.db" if IS_SIMULATION else "forex_main.db"
    return os.path.join(DB_DIR, db_name)

def render_soe_page(symbol_tf_list):
    st.header("📜 Sequence of Events (SOE) Viewer")
    
    if not symbol_tf_list:
        symbol_tf_list = []

    # 1. Создаем вкладки
    tab_trading, tab_system = st.tabs(["Торговля", "Система"])

    with tab_trading:
        # Вкладка Торговля использует торговую БД
        render_log_table(get_trading_db_path(), symbol_tf_list, log_type='trading')

    with tab_system:
        # Вкладка Система использует системную БД
        # Для системных логов список агентов не нужен, передаем пустой список
        render_log_table(SYSTEM_DB_PATH, [], log_type='system')


def render_log_table(db_path, symbol_list, log_type):
    """
    Вспомогательная функция для отрисовки таблицы логов для конкретной БД.
    """
    # 1. Проверка наличия БД
    if not os.path.exists(db_path):
        st.error(f"База данных логов не найдена по пути: {db_path}")
        return

    # Определяем имя таблицы, как мы договорились в logger.py
    if log_type == 'trading':
        table_name = 'trading_events'
    else:
        table_name = 'system_events'
    
    # 2. Панель фильтров
    with st.expander(f"🔍 Фильтры ({'Торговля' if log_type == 'trading' else 'Система'})", expanded=True):
        f_col1, f_col2, f_col3 = st.columns([1, 1, 2])
        
        mod_filter = f_col1.multiselect(f"Модуль (Source) [{log_type}]:", 
            ["Trader", "Brain", "Orchestrator", "PositionManager", "Main", "SettingsManager"], 
            default=[])
        
        # Для системных логов фильтр агентов упрощен до SYSTEM
        current_symbols = symbol_list + ["SYSTEM"] if log_type == 'trading' else ["SYSTEM"]
        sym_filter = f_col2.multiselect("Агент (ID):", current_symbols, default=[])
        
        search_query = f_col3.text_input("Поиск в логах:", placeholder="Например: 'ордер' или 'error'...", key=f"search_{log_type}")

    # 3. Формирование SQL запроса
    query = f"SELECT timestamp, name as Module, level, symbol, message FROM {table_name} WHERE 1=1"
    params = []

    if mod_filter:
        query += f" AND name IN ({','.join(['?']*len(mod_filter))})"
        params.extend(mod_filter)
    
    if sym_filter:
        query += f" AND symbol IN ({','.join(['?']*len(sym_filter))})"
        params.extend(sym_filter)
        
    if search_query:
        query += " AND (message LIKE ? OR level LIKE ?)"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")

    query += " ORDER BY timestamp DESC LIMIT 1000"

    # 4. Чтение данных
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        df_logs = pd.read_sql(query, conn, params=params)
        conn.close()

        if not df_logs.empty:
            def style_log_rows(row):
                style = [''] * len(row)
                if row['level'] in ['ERROR', 'CRITICAL']:
                    style = ['background-color: rgba(255, 75, 75, 0.15); color: #FF4B4B'] * len(row)
                elif row['level'] == 'WARNING':
                    style = ['color: #FFFF00'] * len(row)
                return style

            st.dataframe(
                df_logs.style.apply(style_log_rows, axis=1), 
                use_container_width=True,
                height=500, # Уменьшил высоту, чтобы лучше вписывалось во вкладки
                column_config={
                    "timestamp": st.column_config.DatetimeColumn("Время", format="D MMM, HH:mm:ss"),
                    "message": st.column_config.TextColumn("Событие", width="large")
                }
            )
        else:
            st.info("События не найдены. Проверьте фильтры или активность системы.")

    except Exception as e:
        st.error(f"Ошибка доступа к SOE: {e}")

    # 5. Экспорт и очистка
    st.divider()
    c1, c2 = st.columns([1, 4])
    clear_button_key = f"clear_soe_{log_type}"
    confirm_key = f"confirm_clear_{log_type}"

    if c1.button("🧹 Очистить журнал", key=clear_button_key):
        if st.session_state.get(confirm_key):
            try:
                with sqlite3.connect(db_path, timeout=10) as conn:
                    conn.execute(f"DELETE FROM {table_name}")
                st.success("Журнал очищен.")
                st.session_state[confirm_key] = False
                st.rerun()
            except Exception as e:
                st.error(f"Не удалось очистить лог: {e}")
        else:
            st.session_state[confirm_key] = True
            st.warning("Нажмите еще раз для подтверждения удаления всей истории событий.")
