# data_sys/yfinance_provider.py
import yfinance as yf
import pandas as pd
from system_base.logger import get_logger

log = get_logger("YFinanceProvider", db_type='system')

class YFinanceProvider:
    """Провайдер данных для режима симуляции (Yahoo Finance)."""
    @staticmethod
    def get_raw_rates(symbol, tf_str, count):
        # Маппинг ТФ: M15->15m, H1->1h, H4->1h, D1->1d
        yf_tf = {"M15": "15m", "H1": "1h", "H4": "1h", "D1": "1d"}.get(tf_str, "1h")
        try:
            data = yf.download(symbol, period="1mo", interval=yf_tf, progress=False)
            if data.empty: return None
            df = data.reset_index()
            df = df.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'tick_volume'})
            return df.tail(count).to_dict('records')
        except Exception as e:
            log.error(f"Ошибка YFinance [{symbol}]: {e}")
            return None