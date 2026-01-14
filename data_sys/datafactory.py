# FILE: data_sys/datafactory.py
import os, joblib, time
import pandas as pd
import pandas_ta as ta
import numpy as np
from data_sys.yfinance_provider import YFinanceProvider

# Пытаемся импортировать конфиг из пакета root (согласно структуре main.py)
try:
    from root import config as cfg
except ImportError:
    import config as cfg

from system_base.logger import get_logger
from data_sys.mt5_provider import MT5Provider

log = get_logger("DataFactory")

class DataFactory:
    """Процессор данных: индикаторы, кэширование скалеров и нормализация."""
    
    # Пункт 1: Кэш скалеров { "SYMBOL_TF": {"scaler": obj, "mtime": float} }
    _scalers_cache = {}

    @classmethod
    def _get_scaler(cls, symbol_tf, path):
        """Загружает скалер в память один раз или обновляет при изменении файла (mtime)."""
        try:
            current_mtime = os.path.getmtime(path)
            cached = cls._scalers_cache.get(symbol_tf)

            if not cached or cached['mtime'] < current_mtime:
                log.info(f"[{symbol_tf}] Загрузка/Обновление скалера из файла.")
                cls._scalers_cache[symbol_tf] = {
                    'scaler': joblib.load(path),
                    'mtime': current_mtime
                }
            return cls._scalers_cache[symbol_tf]['scaler']
        except Exception as e:
            log.error(f"[{symbol_tf}] Ошибка доступа к скалеру: {e}")
            return None

    @classmethod
    def clear_cache(cls, symbol_tf=None):
        """Пункт 5: Принудительная инвалидация кэша после переобучения (Education)."""
        if symbol_tf:
            cls._scalers_cache.pop(symbol_tf, None)
        else:
            cls._scalers_cache.clear()
        log.info(f"Кэш очищен для: {symbol_tf if symbol_tf else 'всех'}")

    @classmethod
    def get_data(cls, symbol, tf_str, window_size):
        """Пункт 4: Получение баров, расчет индикаторов и нормализация тензора."""
        
        # 1. Рассчитываем объем запроса (Окно + запас на прогрев индикаторов)
        # Для 2026 года берем запас 50, так как RSI/ATR обычно требуют 14-30 баров
        request_count = window_size + 50
        
        if cfg.IS_SIMULATION:
            raw_rates = YFinanceProvider.get_raw_rates(symbol, tf_str, request_count)
        else:
            raw_rates = MT5Provider.get_raw_rates(symbol, tf_str, request_count)

        if raw_rates is None:
            return None, None, None

        df = pd.DataFrame(raw_rates)
        
        # Проверка: пришло ли достаточно данных вообще?
        if len(df) < window_size:
            return None, None, None
            
        last_time = int(df['time'].iloc[-1])
        
        # 2. Подготовка базовых колонок
        df_features = df[['open', 'high', 'low', 'close', 'tick_volume']].copy()
        df_features.columns = ['open', 'high', 'low', 'close', 'volume']
        
        # 3. Добавление индикаторов (параметры из конфига)
        stg = next((v for k, v in cfg.TF_SETTINGS.items() if v['suffix'] == tf_str), {'rsi': 14, 'atr': 14})
        
        # Расчет индикаторов
        df_features.ta.rsi(length=stg['rsi'], append=True)
        df_features.ta.atr(length=stg['atr'], append=True)
        
        # Очистка от пустых значений в начале (прогрев)
        df_features.dropna(inplace=True)
        
        # ВАЖНАЯ ПРОВЕРКА 2026: осталось ли после dropna достаточно строк для окна?
        if len(df_features) < window_size:
            log.warning(f"[{symbol}_{tf_str}] Недостаточно данных после расчета индикаторов.")
            return None, last_time, None

        # Берем строго заданное в БД окно
        final_df = df_features.tail(window_size).copy()

        # Пункт 3: ПРИНУДИТЕЛЬНЫЙ строгий порядок колонок для нейросети
        expected_cols = ['open', 'high', 'low', 'close', 'volume', 'rsi', 'atr']
        final_df = final_df.reindex(columns=expected_cols)

        # Пункт 5: Извлекаем сырой ATR для RiskManager
        raw_atr = final_df['atr'].iloc[-1]

        # 4. Нормализация
        symbol_tf = f"{symbol}_{tf_str}"
        scaler_path = os.path.join(cfg.MODELS_DIR, f"scaler_{symbol_tf}.pkl")
        
        if not os.path.exists(scaler_path):
            log.error(f"[{symbol_tf}] Скалер не найден: {scaler_path}")
            return None, last_time, raw_atr
            
        scaler = cls._get_scaler(symbol_tf, scaler_path)
        if scaler is None:
            return None, last_time, raw_atr

        try:
            # Превращаем DataFrame в нормализованный тензор для LSTM
            normalized_data = scaler.transform(final_df)
            return normalized_data, last_time, raw_atr
        except Exception as e:
            log.error(f"[{symbol_tf}] Ошибка трансформации: {e}")
            return None, last_time, raw_atr

    @staticmethod
    def get_raw_ohlc(symbol, tf_str, count=1000):
        """Метод для DatabaseManager: получение чистых данных OHLCV."""
        rates = MT5Provider.get_raw_rates(symbol, tf_str, count)
        if rates is not None:
            df = pd.DataFrame(rates)[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
            df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
            return df
        return None
