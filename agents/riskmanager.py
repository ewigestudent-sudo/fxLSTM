# agents/RiskManager.py
# LOCATION: PROJ_AI_FOREX_2026/agents/
# DESCRIPTION: Модуль управления рисками. Расчет условий 1:3 и сопровождение позиций.

import MetaTrader5 as mt5
from system_base.logger import get_logger

log = get_logger("RiskManager")

class RiskManager:
    def __init__(self, symbol_tf, trader):
        self.symbol_tf = symbol_tf
        self.trader = trader

    def evaluate_entry(self, tick, p_close, p_high, p_low):
        """
        Проверка условия: Прибыль >= 3 * (Убыток + Спред + Комиссия).
        Возвращает: 'BUY', 'SELL' или None.
        """
        s_info = mt5.symbol_info(self.symbol_tf)
        if not s_info: return None
        
        spread = (tick.ask - tick.bid)
        comm = self.trader.commission_pts * s_info.point
        
        # ЛОГИКА BUY
        if p_close > tick.ask:
            profit = p_close - tick.ask
            # Риск: дистанция до стопа (Low) + издержки
            risk = (tick.ask - p_low) + spread + comm
            if profit >= 3 * risk and risk > 0:
                return 'BUY'
                
        # ЛОГИКА SELL
        elif p_close < tick.bid:
            profit = tick.bid - p_close
            # Риск: дистанция до стопа (High) + издержки
            risk = (p_high - tick.bid) + spread + comm
            if profit >= 3 * risk and risk > 0:
                return 'SELL'
                
        return None

    def evaluate_entry(self, tick, p_close, p_high, p_low, raw_atr):
        """
        Логика закрытия при ухудшении прогноза (Trailing Forecast).
        Закрывает сделку, если новый прогноз сулит снижение профита относительно старого.
        """
        # Новое условие 2026: Фильтр волатильности
        if (p_high - p_low) < raw_atr * 0.5:
            return None
            
        if last_p_close is None: return

        pos = mt5.positions_get(symbol=self.symbol_tf, magic=self.trader.magic)
        if not pos: return
        
        for p in pos:
            # BUY: Если новый прогноз ниже предыдущего — фиксируем что есть
            if p.type == mt5.ORDER_TYPE_BUY and current_p_close < last_p_close:
                self.trader.close_position(p.ticket, "Forecast Drop")
            # SELL: Если новый прогноз выше предыдущего — фиксируем
            elif p.type == mt5.ORDER_TYPE_SELL and current_p_close > last_p_close:
                self.trader.close_position(p.ticket, "Forecast Rise")
