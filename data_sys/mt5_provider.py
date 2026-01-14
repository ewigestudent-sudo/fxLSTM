# FILE: data_sys/mt5_provider.py
import MetaTrader5 as mt5
import time
from system_base.logger import get_logger

log = get_logger("MT5Provider")

class MT5Provider:
    """Отвечает только за сетевой обмен с терминалом MT5 (ТЗ 2026)."""
    
    TF_STRING_MAP = {
        "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1
    }

    @classmethod
    def get_raw_rates(cls, symbol, tf_str, count):
        """Получение баров с логикой 3-х попыток (Пункт 2 решений)."""
        tf_mt5 = cls.TF_STRING_MAP.get(tf_str)
        if tf_mt5 is None:
            log.error(f"[{symbol}] Некорректный таймфрейм: {tf_str}")
            return None

        for attempt in range(3):
            # Запрос к терминалу
            rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 0, count)
            
            if rates is not None and len(rates) >= count:
                return rates
            
            log.warning(f"[{symbol}] Попытка {attempt+1}/3 не удалась. Ожидание...")
            time.sleep(0.2 * (attempt + 1)) # Пропорциональная пауза
            
        log.error(f"[{symbol}] Не удалось получить {count} баров после всех попыток.")
        return None

    @staticmethod
    def check_terminal():
        """Проверка коннекта к торговому серверу."""
        try:
            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                return False
            return terminal_info.connected
        except Exception as e:
            log.error(f"Ошибка проверки терминала: {e}")
            return False
