# agents/trader.py
import MetaTrader5 as mt5
import json
import os
from system_base.logger import get_logger
from config import MAGIC_NUMBER, APP_CONFIG_PATH, MIN_PROFIT_PTS

# Использование системного логгера
log = get_logger("Trader")

class Trader:
    def __init__(self, magic=MAGIC_NUMBER):
        """
        Инициализация торгового модуля.
        magic: берется из config.py для идентификации сделок бота.
        """
        self.magic = magic
        self.commission_pts = 50  # 50 пипсов (5 пунктов)

    def _is_trading_allowed(self):
        """Проверка глобального флага Trading Allowed из app_config.json"""
        try:
            if not os.path.exists(APP_CONFIG_PATH):
                return False
            with open(APP_CONFIG_PATH, 'r') as f:
                config = json.load(f)
                return config.get("trading_allowed", False)
        except Exception as e:
            log.error(f"Ошибка чтения app_config.json: {e}")
            return False

    def _send_order(self, symbol, order_type, price, sl, tp, volume=0.01):
        """Внутренний метод отправки приказа в MT5"""
        
        # Проверка глобального разрешения перед каждой отправкой
        if not self._is_trading_allowed():
            log.warning(f"[{symbol}] Ордер отклонен: Торговля запрещена в настройках HMI.", extra={'symbol': symbol})
            return None

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            log.error(f"[{symbol}] Символ не найден в терминале MT5.", extra={'symbol': symbol})
            return None

        # Округляем цены
        price = round(price, symbol_info.digits)
        sl = round(sl, symbol_info.digits)
        tp = round(tp, symbol_info.digits)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "magic": self.magic,
            "comment": f"{symbol}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result is None:
            log.error(f"[{symbol}] Критический сбой: order_send вернул None", extra={'symbol': symbol})
            return None

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"[{symbol}] Ордер отклонен. Код: {result.retcode}, Ошибка: {result.comment}", extra={'symbol': symbol})
        else:
            log.info(f"[{symbol}] Сделка исполнена! Тикет: {result.order}, Цена: {price}, TP: {tp}", extra={'symbol': symbol})
        
        return result

    def execute_buy(self, symbol, target=None, stop=None):
        """Публичный метод для Orchestrator (symbol здесь - полный ID: EURUSD_H1)"""
        tick = mt5.symbol_info_tick(symbol)
        s_info = mt5.symbol_info(symbol)
        if tick is None or s_info is None: return
        
        curr_price = tick.ask
        
        # 1. Расчет Take Profit
        tp = target if target else curr_price + (MIN_PROFIT_PTS * s_info.point)
        
        if (tp - curr_price) < (MIN_PROFIT_PTS * s_info.point):
            log.info(f"[{symbol}] Сигнал BUY пропущен: малый профит.", extra={'symbol': symbol})
            return

        # 2. Расчет Stop Loss
        sl = stop if stop else curr_price - (200 * s_info.point)
        
        min_sl_dist = self.commission_pts * s_info.point
        if (curr_price - sl) < min_sl_dist:
            sl = curr_price - (min_sl_dist * 2)

        self._send_order(symbol, mt5.ORDER_TYPE_BUY, curr_price, sl, tp)

    def execute_sell(self, symbol, target=None, stop=None):
        """Публичный метод для Orchestrator (symbol здесь - полный ID: EURUSD_H1)"""
        tick = mt5.symbol_info_tick(symbol)
        s_info = mt5.symbol_info(symbol)
        if tick is None or s_info is None: return
        
        curr_price = tick.bid
        
        # 1. Расчет Take Profit
        tp = target if target else curr_price - (MIN_PROFIT_PTS * s_info.point)
        
        if (curr_price - tp) < (MIN_PROFIT_PTS * s_info.point):
            log.info(f"[{symbol}] Сигнал SELL пропущен: малый профит.", extra={'symbol': symbol})
            return

        # 2. Расчет Stop Loss
        sl = stop if stop else curr_price + (200 * s_info.point)
        
        min_sl_dist = self.commission_pts * s_info.point
        if (sl - curr_price) < min_sl_dist:
            sl = curr_price + (min_sl_dist * 2)

        self._send_order(symbol, mt5.ORDER_TYPE_SELL, curr_price, sl, tp)
