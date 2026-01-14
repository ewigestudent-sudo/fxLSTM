# FILE: hmi_pages/settings_methods/lstm_settings_dialog.py
import streamlit as st
from data_sys.databasemanager import DatabaseManager
from config import TF_SETTINGS 

@st.dialog("Настройки Иерархии (2026)", width="large")
def lstm_settings_dialog():
    db = DatabaseManager()

    # 1. Получаем данные из селекторов (теперь два ТФ)
    raw_p = st.session_state.get('new_p')
    raw_t_jr = st.session_state.get('new_t_jr')
    raw_t_sr = st.session_state.get('new_t_sr')
    
    if not all([raw_p, raw_t_jr, raw_t_sr]):
        st.error("Ошибка: Пара или Таймфреймы не выбраны")
        return

    # 2. Формируем два ID для базы данных
    def get_sid(p, t):
        suffix = TF_SETTINGS.get(t, {}).get('suffix', str(t))
        return f"{p}_{suffix}"

    id_jr = get_sid(raw_p, raw_t_jr)
    id_sr = get_sid(raw_p, raw_t_sr)

    # 3. Вкладки для раздельной настройки
    tab_jr, tab_sr = st.tabs(["📉 Младшая модель (JR)", "📈 Старшая модель (SR)"])
    
    # Мы используем один общий словарь в session_state для хранения изменений из обеих вкладок
    # перед финальным сохранением в БД
    
    with tab_jr:
        st.caption(f"ID Младшей: {id_jr}")
        settings_jr = render_model_settings_form(id_jr, "jr_form")
        
    with tab_sr:
        st.caption(f"ID Старшей: {id_sr}")
        settings_sr = render_model_settings_form(id_sr, "sr_form")

    st.divider()
    
    # 4. Общие кнопки управления для ВСЕЙ связки
    c1, c2, c3 = st.columns(3)
    
    if c1.button("СБРОСИТЬ ОБЕ", use_container_width=True):
        defaults = {
            'window_size': 60, 'epochs': 50, 'batch_size': 32, 
            'learning_rate': 0.001, 'optimizer': 'Adam', 
            'lstm_units': 100, 'dropout_rate': 0.2, 'error_multiplier': 1.5
        }
        db.save_model_settings(id_jr, defaults)
        db.save_model_settings(id_sr, defaults)
        st.success("Настройки обеих моделей сброшены к дефолтам")
        st.rerun()

    if c2.button("СОХРАНИТЬ СВЯЗКУ", type="primary", use_container_width=True):
        # Пишем две записи в одну таблицу БД
        db.save_model_settings(id_jr, settings_jr)
        db.save_model_settings(id_sr, settings_sr)
        
        st.session_state.lstm_ready = False
        st.success(f"Связка {raw_p} сохранена (JR+SR)")
        st.rerun()
            
    if c3.button("ОТМЕНА", use_container_width=True):
        st.session_state.lstm_ready = False
        st.rerun()

def render_model_settings_form(symbol_tf, key_suffix):
    """
    Вспомогательная функция отрисовки полей. 
    Возвращает словарь с данными, НЕ выполняя сохранения в БД.
    """
    db = DatabaseManager()
    cfg = db.get_model_settings(symbol_tf)
    
    def get_f(k, d): return float(cfg.get(k, d))
    def get_i(k, d): return int(cfg.get(k, d))

    # Для вкладок лучше использовать не st.form, а просто контейнер полей, 
    # так как кнопка подтверждения одна на весь диалог
    win_size = st.number_input("Размер окна", 10, 500, get_i('window_size', 60), key=f"win_{key_suffix}")
    
    col1, col2 = st.columns(2)
    epochs = col1.number_input("Эпохи", 1, 200, get_i('epochs', 50), key=f"ep_{key_suffix}")
    batch = col2.number_input("Batch", 16, 128, get_i('batch_size', 32), step=16, key=f"bt_{key_suffix}")
    
    lr = st.number_input("Learning Rate", 0.0001, 0.1, get_f('learning_rate', 0.001), format="%e", key=f"lr_{key_suffix}")
    
    opts = ["Adam", "RMSprop", "SGD"]
    saved_opt = str(cfg.get('optimizer', 'Adam'))
    opt_idx = opts.index(saved_opt) if saved_opt in opts else 0
    opt = st.selectbox("Optimizer", opts, index=opt_idx, key=f"opt_{key_suffix}")
    
    st.markdown("---")
    col3, col4 = st.columns(2)
    units = col3.number_input("LSTM Units", 16, 256, get_i('lstm_units', 100), step=16, key=f"ut_{key_suffix}")
    drop = col4.number_input("Dropout", 0.0, 0.5, get_f('dropout_rate', 0.2), step=0.05, key=f"dr_{key_suffix}")
    
    # Возвращаем подготовленный словарь
    return {
        'window_size': win_size, 'epochs': epochs, 'batch_size': batch,
        'learning_rate': lr, 'optimizer': opt, 'lstm_units': units,
        'dropout_rate': drop, 'error_multiplier': get_f('error_multiplier', 1.5)
    }