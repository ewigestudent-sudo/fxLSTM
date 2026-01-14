# hmi_pages/settings_methods/save_lstm_config.py
import streamlit as st
from root.config import load_app_config, save_app_config

def save_lstm_config(config_data):
    """Обновляет только секцию LSTM в глобальном конфиге."""
    app_cfg = load_app_config()
    app_cfg['lstm_config'] = config_data
    save_app_config(app_cfg)
    st.toast("Параметры нейросети обновлены")
