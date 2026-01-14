# FILE: root/config.py
import os
import json
import MetaTrader5 as mt5

# --- ПУТИ К ФАЙЛАМ (Финальная структура 2026) ---

# 1. Определение корня проекта
# Используем абсолютный путь к текущему файлу, чтобы ROOT_DIR всегда был fxLSTM
CURRENT_FILE_PATH = os.path.abspath(__file__)
CURRENT_DIR = os.path.dirname(CURRENT_FILE_PATH) # папка root
ROOT_DIR = os.path.dirname(CURRENT_DIR)          # папка fxLSTM

# 2. Справочник всех папок проекта (СНАРУЖИ папки root)
FOLDERS = {
    "MODELS": os.path.join(ROOT_DIR, "models"),
    "DATA": os.path.join(ROOT_DIR, "data_sys"),
    "SYSTEM": os.path.join(ROOT_DIR, "system_base"),
    "HMI_PAGES": os.path.join(ROOT_DIR, "hmi_pages"),
    "AGENTS": os.path.join(ROOT_DIR, "agents"),
    "AI_BRAIN": os.path.join(ROOT_DIR, "ai_brain")
}

# Глобальные константы путей директорий
MODELS_DIR = FOLDERS["MODELS"]
DB_DIR = FOLDERS["DATA"]
SYS_BASE_DIR = FOLDERS["SYSTEM"]
HMI_PAGES_DIR = FOLDERS["HMI_PAGES"]

# 3. Конфигурационные файлы
APP_CONFIG_PATH = os.path.join(SYS_BASE_DIR, "app_config.json")
BOT_STATES_PATH = os.path.join(SYS_BASE_DIR, "bot_states.json")
HMI_COMMANDS_PATH = os.path.join(HMI_PAGES_DIR, "hmi_commands.json")
USER_SETTINGS_FILE = os.path.join(HMI_PAGES_DIR, "user_visual_settings.json")
SYSTEM_DB_PATH = os.path.join(SYS_BASE_DIR, "system_events.db")

# --- ЗАГРУЗКА И СОХРАНЕНИЕ ПОЛЬЗОВАТЕЛЬСКИХ НАСТРОЕК ---
def load_app_config():
    """Загрузка конфигурации из JSON. Если файла нет - возврат дефолтов."""
    if os.path.exists(APP_CONFIG_PATH):
        try:
            with open(APP_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Дефолтные настройки для первого запуска
    return {"saved_mode": "SIM", "show_mode_dialog": True, "trading_allowed": False, "is_ready": False}

def save_app_config(config_data):
    """Сохранение конфигурации в JSON."""
    try:
        with open(APP_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Ошибка сохранения app_config: {e}")

app_cfg = load_app_config()

# --- СИСТЕМНЫЕ НАСТРОЙКИ ---
# Приоритет: переменная окружения -> файл конфига
IS_SIMULATION = (os.getenv("TRADING_MODE") == "SIMULATION") or (app_cfg.get("saved_mode") == "SIM")
# Убеждаемся, что при старте main.py этот флаг читается корректно из app_config

# Путь к БД (разделение файлов для исключения конфликтов истории)
DB_PATH = os.path.join(DB_DIR, "simulation_main.db" if IS_SIMULATION else "forex_main.db")

# Параметры нейросети
DEFAULT_WINDOW_SIZE = 60              
FEATURES = 7                  # [Open, High, Low, Close, Volume, RSI, ATR]
MAGIC_NUMBER = 202601         

# --- СПИСОК ВАЛЮТНЫХ ПАР И ТАЙМФРЕЙМОВ ---
SYMBOLS_LIST = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]

TF_SETTINGS = {
    mt5.TIMEFRAME_M15: {'rsi': 7,  'atr': 14, 'suffix': 'M15'},
    mt5.TIMEFRAME_H1:  {'rsi': 7,  'atr': 14, 'suffix': 'H1'},
    mt5.TIMEFRAME_H4:  {'rsi': 14, 'atr': 14, 'suffix': 'H4'},
    mt5.TIMEFRAME_D1:  {'rsi': 14, 'atr': 14, 'suffix': 'D1'}
}

ACTIVE_TIMEFRAMES = [mt5.TIMEFRAME_H1, mt5.TIMEFRAME_D1]
ACTIVE_AGENTS_IDS = [f"{s}_{TF_SETTINGS[t]['suffix']}" for s in SYMBOLS_LIST for t in ACTIVE_TIMEFRAMES]

# --- ТОРГОВЫЕ ПАРАМЕТРЫ ---
MIN_PROFIT_PTS = 200    
COMMISSION_PTS = 50     
BE_THRESHOLD = 0.5  

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_agent_id(symbol, tf_constant):
    suffix = TF_SETTINGS.get(tf_constant, {'suffix': 'TF'})['suffix']
    return f"{symbol}_{suffix}"

def get_model_path(agent_id):
    return os.path.join(MODELS_DIR, f"lstm_{agent_id}.h5")

def get_scaler_path(agent_id):
    return os.path.join(MODELS_DIR, f"scaler_{agent_id}.pkl")

# --- ЛОГИРОВАНИЕ ---
LOG_FILE = os.path.join(SYS_BASE_DIR, 'trading_bot_2026.log')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
