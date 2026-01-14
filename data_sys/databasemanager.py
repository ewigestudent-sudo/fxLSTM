# data_sys/databasemanager.py
import sqlite3
import pandas as pd
import pandas_ta as ta
import os
import joblib
from sklearn.preprocessing import MinMaxScaler
from mpire import WorkerPool
from config import DB_PATH, MODELS_DIR, TF_SETTINGS
from system_base.logger import get_logger

log = get_logger("DatabaseManager")

def _process_symbol_data(args):
    """Параллельный препроцессинг для конкретной таблицы (Symbol_TF)"""
    symbol_tf, raw_values = args
    if raw_values is None or len(raw_values) < 100:
        return symbol_tf, None
    
    # 1. Создаем DataFrame
    df = pd.DataFrame(raw_values, columns=['open', 'high', 'low', 'close', 'volume'])
    
    # 2. Определяем настройки индикаторов по суффиксу из ID
    tf_suffix = symbol_tf.split('_')[-1]
    
    # Согласованный поиск настроек (идентично DataFactory)
    stg = next((v for k, v in TF_SETTINGS.items() if v['suffix'] == tf_suffix), 
               {'rsi': 14, 'atr': 14}) # Дефолтные значения 2026 года
    
    df.ta.rsi(length=stg.get('rsi', 14), append=True)
    df.ta.atr(length=stg.get('atr', 14), append=True)
    df.dropna(inplace=True)

    # 3. Нормализация (FEATURES = 7: O, H, L, C, V, RSI, ATR)
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_values = scaler.fit_transform(df)
    
    # 4. Сохранение скалера в models/ (для Brain.py и DataFactory.get_data)
    scaler_path = os.path.join(MODELS_DIR, f"scaler_{symbol_tf}.pkl")
    joblib.dump(scaler, scaler_path)
    
    return symbol_tf, scaled_values

class DatabaseManager:
    def __init__(self):
        db_dir = os.path.dirname(DB_PATH)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

    def _get_conn(self):
        return sqlite3.connect(DB_PATH)

    def update_database(self, symbol, tf_str):
        """
        Метод для актуализации данных перед препроцессингом (используется в TradingBot)
        """
        from data_sys.datafactory import DataFactory
        symbol_tf = f"{symbol}_{tf_str}"
        
        # Получаем свежие OHLCV из MT5
        rates_df = DataFactory.get_raw_ohlc(symbol, tf_str, count=2000)
        if rates_df is not None:
            self.save_rates(symbol_tf, rates_df)

    def save_rates(self, symbol_tf, rates_df):
        """Сохранение котировок в таблицу по ID"""
        try:
            with self._get_conn() as conn:
                conn.execute(f'''CREATE TABLE IF NOT EXISTS {symbol_tf} (
                    time INTEGER PRIMARY KEY, 
                    open REAL, high REAL, low REAL, close REAL, volume REAL)''')
                
                rates_df.to_sql(symbol_tf, conn, if_exists='append', index=False)
        except Exception as e:
            log.error(f"[{symbol_tf}] Ошибка записи в БД: {e}")

    def get_history(self, symbol_tf, limit=10000):
        """Загрузка данных из конкретной таблицы"""
        try:
            with self._get_conn() as conn:
                query = f"SELECT open, high, low, close, volume FROM {symbol_tf} ORDER BY time ASC LIMIT {limit}"
                return pd.read_sql(query, conn).values
        except Exception as e:
            log.error(f"[{symbol_tf}] Ошибка чтения истории: {e}")
            return None

    def load_training_data_parallel(self, symbol_tf_list):
        """Массовый препроцессинг данных из разных таблиц"""
        tasks = []
        with self._get_conn() as conn:
            for symbol_tf in symbol_tf_list:
                # Проверка существования таблицы
                cursor = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{symbol_tf}'")
                if cursor.fetchone():
                    query = f"SELECT open, high, low, close, volume FROM {symbol_tf} ORDER BY time ASC"
                    raw = pd.read_sql(query, conn).values
                    if len(raw) > 0:
                        tasks.append((symbol_tf, raw))
        
        if not tasks:
            return {}

        log.info(f"Запуск MPIRE препроцессинга для {len(tasks)} таблиц...")
        with WorkerPool(n_jobs=os.cpu_count()) as pool:
            results = pool.map(_process_symbol_data, tasks)
        
        return {res[0]: res[1] for res in results if res is not None}
    
    def get_model_settings(self, symbol_tf):
        """Получение настроек модели из БД (версия 2026 с window_size)."""
        defaults = {
            'window_size': 60,
            'epochs': 50, 
            'batch_size': 32, 
            'learning_rate': 0.001,
            'optimizer': 'Adam', 
            'lstm_units': 100, 
            'dropout_rate': 0.2,
            'error_multiplier': 1.5  # Множитель порога ATR (Новое 2026)
        }
        
        try:
            with self._get_conn() as conn:
                # Создаем таблицу с полным набором полей
                conn.execute("""CREATE TABLE IF NOT EXISTS model_settings (
                                model_id TEXT PRIMARY KEY,
                                window_size INTEGER,
                                epochs INTEGER, 
                                batch_size INTEGER,
                                learning_rate REAL, 
                                optimizer TEXT,
                                lstm_units INTEGER, 
                                dropout_rate REAL,
                                error_multiplier REAL)""")
                
                query = "SELECT * FROM model_settings WHERE model_id = ?"
                df = pd.read_sql(query, conn, params=(symbol_tf,))
                
                if df.empty:
                    cols = ', '.join(defaults.keys())
                    # Теперь у нас 9 знаков ? (model_id + 8 параметров)
                    conn.execute(f"INSERT INTO model_settings (model_id, {cols}) VALUES (?,?,?,?,?,?,?,?,?)",
                                 (symbol_tf, *defaults.values()))
                    conn.commit()
                    return defaults
                
                res = df.iloc[0].to_dict()
                res.pop('model_id')
                return res
        except Exception as e:
            log.error(f"[{symbol_tf}] Ошибка настроек в БД: {e}")
            return defaults

    def save_model_settings(self, symbol_tf, settings):
        """Запись настроек в БД."""
        try:
            with self._get_conn() as conn:
                # Добавляем error_multiplier=? в запрос
                query = """UPDATE model_settings SET 
                           window_size=?, epochs=?, batch_size=?, 
                           learning_rate=?, optimizer=?, lstm_units=?, 
                           dropout_rate=?, error_multiplier=? 
                           WHERE model_id=?""" # <-- Обновлено
                conn.execute(query, (
                    settings['window_size'], settings['epochs'], 
                    settings['batch_size'], settings['learning_rate'],
                    settings['optimizer'], settings['lstm_units'], 
                    settings['dropout_rate'], settings['error_multiplier'], # <-- Добавлено
                    symbol_tf
                ))
        except Exception as e:
            log.error(f"[{symbol_tf}] Ошибка сохранения настроек: {e}")
