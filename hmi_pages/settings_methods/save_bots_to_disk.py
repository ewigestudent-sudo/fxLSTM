# hmi_pages/settings_methods/save_bots_to_disk.py (ИСПРАВЛЕННЫЙ ВАРИАНТ)
import os
import json
import tempfile
import streamlit as st
from root import config as cfg

def save_bots_to_disk():
    path = cfg.APP_CONFIG_PATH
    dir_name = os.path.dirname(path)
    
    # 1. Читаем текущий конфиг, чтобы не затереть другие параметры (режим, флаги)
    config_data = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception:
            pass

    # 2. Обновляем список иерархических ботов
    config_data["bots_list"] = st.session_state.get("bots_list", [])

    # 3. АТОМАРНАЯ ЗАПИСЬ
    try:
        # Создаем временный файл в той же директории, что и конфиг
        fd, temp_path = tempfile.mkstemp(dir=dir_name, text=True)
        with os.fdopen(fd, 'w', encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        
        # Заменяем оригинальный файл временным (атомарная операция в ОС)
        os.replace(temp_path, path)
        
    except Exception as e:
        # В случае ошибки удаляем временный файл, если он остался
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        raise RuntimeError(f"Критическая ошибка сохранения конфига: {e}")
