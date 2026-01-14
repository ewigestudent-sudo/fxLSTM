# hmi_pages/settings_methods/login_dialog.py
import streamlit as st
from system_base.logger import get_logger

log = get_logger("AuthManager", db_type='system')

@st.dialog("Вход в MetaTrader 5")
def login_dialog():
    """Диалог авторизации: данные хранятся только в RAM сессии."""
    st.write("Данные удаляются при закрытии браузера.")
    login = st.text_input("Логин (Account ID)")
    password = st.text_input("Пароль", type="password")
    server = st.text_input("Сервер", value="MetaQuotes-Demo")
    
    if st.button("Подключить и сохранить в RAM"):
        if login and password:
            st.session_state.mt5_credentials = {
                "login": int(login),
                "password": password,
                "server": server
            }
            log.info(f"Пользователь {login} авторизован в RAM")
            st.success("Учетные данные приняты")
            st.rerun()
        else:
            st.error("Введите логин и пароль")
