# sys/simulation.py
import sqlite3
import random
import time
import pandas as pd
import os
from config import DB_PATH, ACTIVE_AGENTS_IDS, TF_SETTINGS
from system_base.logger import get_logger

log = get_logger("Simulation")

class SimulationManager:
    def __init__(self):
        self.db_path = DB_PATH
        self._setup_db()

    def _setup_db(self):
        """Создает таблицы для всех активных агентов, если их нет"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                for aid in ACTIVE_AGENTS_IDS:
                    conn.execute(f"""
                        CREATE TABLE IF NOT EXISTS {aid} (
                            time INTEGER PRIMARY KEY, 
                            open REAL, high REAL, low REAL, close REAL, volume REAL
                        )
                    """)
            log.info(f"База симуляции {os.path.basename(self.db_path)} подготовлена.")
        except Exception as e:
            log.error(f"Ошибка инициализации симуляции: {e}")

    def generate_mock_data(self, days=30):
        """Наполняет таблицы случайными котировками для тестирования HMI_Charts"""
        log.info(f"Генерация мок-данных за {days} дней...")
        
        with sqlite3.connect(self.db_path) as conn:
            for aid in ACTIVE_AGENTS_IDS:
                start_time = int(time.time()) - (days * 86400)
                current_price = random.uniform(1.0500, 1.1500)
                
                # Определяем шаг времени на основе суффикса (H1, D1)
                tf_suffix = aid.split('_')[-1]
                step = 3600 if tf_suffix == 'H1' else 86400
                
                mock_entries = []
                for i in range(0, days * 86400, step):
                    timestamp = start_time + i
                    change = random.uniform(-0.0020, 0.0020)
                    open_p = current_price
                    close_p = open_p + change
                    high_p = max(open_p, close_p) + random.uniform(0, 0.0010)
                    low_p = min(open_p, close_p) - random.uniform(0, 0.0010)
                    
                    mock_entries.append((timestamp, open_p, high_p, low_p, close_p, random.randint(100, 1000)))
                    current_price = close_p

                conn.executemany(f"INSERT OR REPLACE INTO {aid} VALUES (?, ?, ?, ?, ?, ?)", mock_entries)
        log.info("Котировки для симуляции успешно сгенерированы.")

    def inject_test_logs(self):
        """Имитирует активность системы в SOE для проверки HMI_SOE"""
        levels = ["INFO", "WARNING", "ERROR"]
        modules = ["Brain", "Trader", "Orchestrator", "Control"]
        
        for _ in range(20):
            aid = random.choice(ACTIVE_AGENTS_IDS)
            mod = random.choice(modules)
            lvl = random.choice(levels)
            msg = f"SIM-EVENT: {random.choice(['Анализ завершен', 'Коррекция SL', 'MSE выше нормы'])}"
            
            # Используем системный логгер, который сам запишет в нужную БД
            if lvl == "INFO": log.info(msg, extra={'symbol': aid})
            elif lvl == "WARNING": log.warning(msg, extra={'symbol': aid})
            else: log.error(msg, extra={'symbol': aid})

def run_standalone_test():
    """Запуск симуляции как отдельного скрипта"""
    sim = SimulationManager()
    sim.generate_mock_data()
    sim.inject_test_logs()

if __name__ == "__main__":
    run_standalone_test()
