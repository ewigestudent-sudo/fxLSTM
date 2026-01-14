import logging
import sys
import sqlite3
import os
# Используем пути из конфига
from config import DB_PATH, LOG_FILE, LOG_FORMAT, SYSTEM_DB_PATH

class SQLiteHandler(logging.Handler):
    """
    Обработчик логов для SQLite.
    Позволяет писать логи в разные таблицы или БД в зависимости от db_path.
    """
    def __init__(self, db_path, table_name='logs'):
        super().__init__()
        self.db_path = db_path
        self.table_name = table_name
        self._prepare_db()

    def _prepare_db(self):
        """Инициализация таблицы логов с индексами для быстрого поиска в HMI."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL") # Режим WAL для 2026 (параллельный доступ)
            cursor = conn.cursor()
            # Имя таблицы параметризовано
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    timestamp DATETIME DEFAULT (datetime('now','localtime')),
                    name TEXT,
                    level TEXT,
                    symbol TEXT,
                    message TEXT
                )
            """)
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_symbol ON {self.table_name}(symbol)")
            conn.commit()
            conn.close()
        except Exception as e:
            # В случае сбоя инициализации БД, печатаем в консоль
            print(f"Ошибка инициализации БД логов ({self.db_path}): {e}")

    def emit(self, record):
        # Не блокируем основной поток трейдинга при записи лога
        try:
            # Извлекаем ID агента (symbol_tf), если передан в extra={'symbol': '...'}
            symbol = getattr(record, 'symbol', 'SYSTEM')
            
            conn = sqlite3.connect(self.db_path, timeout=5)
            cursor = conn.cursor()
            # Вставляем данные в нужную таблицу
            cursor.execute(
                f"INSERT INTO {self.table_name} (name, level, symbol, message) VALUES (?, ?, ?, ?)", 
                (record.name, record.levelname, symbol, record.getMessage())
            )
            conn.commit()
            conn.close()
        except Exception:
            # В 2026 году важно, чтобы сбой записи лога не остановил торговлю
            pass 

def get_logger(name, db_type='trading'):
    """
    Оркестратор логирования для всех модулей проекта.
    db_type='trading' (по умолчанию) пишет в торговую БД (DB_PATH).
    db_type='system' пишет в системную БД (SYSTEM_DB_PATH).
    """
    logger = logging.getLogger(name)
    # Если логгер уже настроен (есть обработчики), возвращаем его сразу
    if logger.handlers: 
        return logger 
    
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)

    # 1. Терминал (Консоль)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    
    # 2. Файловый лог (sys/trading_bot_2026.log)
    try:
        fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception as e:
        print(f"Не удалось создать файл лога: {e}")

    # 3. SQLite лог - выбор БД и имени таблицы в зависимости от типа
    if db_type == 'system':
        db_path_to_use = SYSTEM_DB_PATH 
        table_name = 'system_events' # Отдельная таблица/БД для системных событий
    else:
        db_path_to_use = DB_PATH
        table_name = 'trading_events' # Отдельная таблица/БД для торговых событий

    sqh = SQLiteHandler(db_path_to_use, table_name=table_name)
    logger.addHandler(sqh)

    return logger
