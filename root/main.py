# FILE: root/main.py
import sys
import os
import time
import json
import subprocess
import importlib
import MetaTrader5 as mt5


# --- 1. КОРРЕКТИРОВКА ПУТЕЙ ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# 2. Добавляем CURRENT_DIR в самое начало, чтобы "import config" искал сначала здесь
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import config as cfg
from system_base.logger import get_logger
from system_base.shutdown_manager import ShutdownManager
from agents.tradingbot import TradingBot
from agents.positionmanager import PositionManager

log = get_logger("SYS_MAIN",  db_type='system')

# Флаги состояния системы
mt5_initialized = False
bots_initialized = False
current_mode_is_sim = True  # По умолчанию SIM (согласно ТЗ)
is_ui_ready = False         # Ждем подтверждения из графического интерфейса

def start_hmi():
    """Запуск интерфейса Streamlit через интерпретатор Anaconda."""
    log.info("Запуск HMI Streamlit...")
    try:
        # Получаем абсолютный путь к hmi.py
        hmi_path = os.path.abspath(os.path.join(CURRENT_DIR, "hmi.py"))
        
        # Запуск через текущий python.exe с флагом -m (модуль)
        # Это универсальный способ для Anaconda/venv
        subprocess.Popen([sys.executable, "-m", "streamlit", "run", hmi_path])
        
    except Exception as e:
        log.error(f"Ошибка старта HMI: {e}")

def update_system_status():
    """Считывает настройки из app_config.json, установленные через HMI."""
    global current_mode_is_sim, is_ui_ready
    if os.path.exists(cfg.APP_CONFIG_PATH):
        try:
            with open(cfg.APP_CONFIG_PATH, "r", encoding="utf-8") as f:
                app_cfg = json.load(f)
            # Синхронизация режима (SIM или REAL)
            current_mode_is_sim = (app_cfg.get("saved_mode", "SIM") == "SIM")
            # Читаем флаг готовности (GUI ставит его в true после выбора режима)
            is_ui_ready = app_cfg.get("is_ready", False)
        except Exception as e:
            log.debug(f"Ошибка чтения app_config: {e}")

def initialize_mt5_and_bots(active_bots):
    """Инициализация терминала (если нужно) и создание торговых агентов."""
    global mt5_initialized, bots_initialized

    # Инициализация MT5 только если выбран режим REAL
    if not current_mode_is_sim:
        if not mt5.initialize():
            log.warning("MetaTrader 5 не обнаружен. Ожидание запуска терминала...")
            return False
        mt5_initialized = True

    log.info(f"Инициализация агентов. Режим: {'SIMULATION' if current_mode_is_sim else 'REAL'}")
    
    for aid in cfg.ACTIVE_AGENTS_IDS:
        try:
            symbol, tf = aid.split('_')
            # Передаем режим в зависимости от выбора пользователя
            mode_str = 'simulation' if current_mode_is_sim else 'trade'
            bot = TradingBot(symbol, tf, mode=mode_str)
            bot.initialize_bot() 
            active_bots.append(bot)
        except Exception as e:
            log.error(f"Ошибка инициализации бота {aid}: {e}")
    
    bots_initialized = True
    return True

def main():
    global bots_initialized, mt5_initialized
    
    log.info("--- ЗАПУСК ЯДРА AI_FOREX_2026 (ОЖИДАНИЕ ВЫБОРА В GUI) ---")

    shutdown_manager = ShutdownManager()
    start_hmi()  # Запускаем GUI сразу
    
    active_bots = []
    pos_manager = PositionManager()

    try:
        while True:
            # 1. Проверяем, нажал ли пользователь кнопку "Начать" в Streamlit
            update_system_status()

            # 2. Если UI еще не подтвердил готовность — бездействуем (Idle State)
            if not is_ui_ready:
                time.sleep(1)
                continue

            # 3. Как только GUI дал "добро", инициализируем ботов (единожды)
            if not bots_initialized:
                if not initialize_mt5_and_bots(active_bots):
                    time.sleep(1)
                    continue

            # 4. Обработка команд из очереди HMI (например, кнопка Stop или Смена режима)
            if os.path.exists(cfg.HMI_COMMANDS_PATH):
                # Логика обработки команд из hmi_commands.json
                # ...
                os.remove(cfg.HMI_COMMANDS_PATH)

            # 5. ОСНОВНОЙ РАБОЧИЙ ТИК
            for bot in active_bots:
                bot.tick()
            
            # Управление открытыми сделками (только в REAL)
            if not current_mode_is_sim:
                pos_manager.manage_all_positions(cfg.SYMBOLS_LIST)

            # 6. ЭКСПОРТ ДАННЫХ ДЛЯ ВИЗУАЛИЗАЦИИ
            try:
                states = {b.symbol_tf: b.get_state() for b in active_bots}
                with open(cfg.BOT_STATES_PATH, "w", encoding="utf-8") as f:
                    json.dump(states, f, indent=4)
            except:
                pass

            time.sleep(1)

    except KeyboardInterrupt:
        log.info("Система остановлена пользователем.")
    finally:
        # Корректное завершение работы
        if mt5_initialized or bots_initialized:
            shutdown_manager.execute(active_bots)
            if mt5_initialized:
                mt5.shutdown()

if __name__ == "__main__":
    main()
