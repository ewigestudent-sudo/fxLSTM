# data_sys/stat.py
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from system_base.logger import get_logger
from config import MAGIC_NUMBER

log = get_logger("StatManager")

class StatManager:
    def __init__(self, magic=MAGIC_NUMBER):
        self.magic = magic

    def get_trades_history(self, symbol=None, days=90):
        """
        Получает историю сделок и фильтрует их по ID агента (Symbol_TF)
        через комментарий или магическое число.
        """
        from_date = datetime.now() - timedelta(days=days)
        to_date = datetime.now()
        
        # 1. Запрашиваем всю историю сделок по магическому числу бота
        # Мы не используем group_filter по символу здесь, чтобы иметь возможность 
        # гибко фильтровать данные в DataFrame
        deals = mt5.history_deals_get(from_date, to_date)

        if deals is None or len(deals) == 0:
            #log.info(f"Нет сделок за последние {days} дней.")
            return pd.DataFrame(), {}

        # 2. Превращаем в DataFrame
        df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
        
        # 3. Базовая фильтрация: наш Magic Number и только закрытые сделки (OUT)
        df = df[(df['magic'] == self.magic) & (df['entry'] == mt5.DEAL_ENTRY_OUT)]
        
        if df.empty:
            return pd.DataFrame(), {}

        # 4. ФИЛЬТРАЦИЯ ПО ID АГЕНТА (Symbol_TF)
        # В 2026 году мы ожидаем, что в поле comment записан ID (напр. 'EURUSD_H1')
        # Если передан конкретный символ/ID, фильтруем по нему
        if symbol:
            # Сначала пробуем фильтровать по точному совпадению символа MT5
            # Затем по комментарию, если в нем хранится таймфрейм
            mask = (df['symbol'] == symbol) | (df['comment'] == symbol)
            df = df[mask]

        if df.empty:
            return pd.DataFrame(), {}

        # Форматирование времени и индексация
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        df = df.sort_index()

        return df, self._calculate_metrics(df)

    def _calculate_metrics(self, df):
        """Расчет финансовых метрик 2026"""
        total_trades = len(df)
        if total_trades == 0: return {}

        win_trades = df[df['profit'] > 0]
        loss_trades = df[df['profit'] <= 0]
        
        total_profit = df['profit'].sum()
        
        # Максимальная просадка
        returns = df['profit'].cumsum()
        peak = returns.expanding(min_periods=1).max()
        max_drawdown = (returns - peak).min()
        
        # Коэффициент Шарпа (дневной)
        daily_returns = df['profit'].resample('D').sum().fillna(0)
        sharpe_ratio = 0.0
        if daily_returns.std() > 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)

        return {
            "total_trades": total_trades,
            "win_rate_%": round((len(win_trades) / total_trades) * 100, 2),
            "total_profit_usd": round(total_profit, 2),
            "max_drawdown_usd": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe_ratio, 2)
        }
