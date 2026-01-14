# agents/positionmanager.py
import MetaTrader5 as mt5
from system_base.logger import get_logger
from config import MAGIC_NUMBER # Предположим, вынесли в конфиг

log = get_logger("PositionManager")

class PositionManager:
    def __init__(self, magic=MAGIC_NUMBER):
        self.magic = magic

    def manage_all_positions(self, symbols_list):
        """
        Основная функция сопровождения, вызываемая из главного цикла (main.py).
        """
        if not mt5.initialize():
            log.error("MT5 не инициализирован в PositionManager")
            return

        for symbol in symbols_list:
            self._manage_symbol_positions(symbol)

    def _manage_symbol_positions(self, symbol):
        """Управление позициями по конкретному символу"""
        positions = mt5.positions_get(symbol=symbol)
        
        if positions is None or len(positions) == 0:
            return

        for pos in positions:
            # Проверяем magic-номер бота
            if pos.magic != self.magic:
                continue

            # Получаем актуальные параметры символа (кол-во знаков после запятой)
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                continue

            # ЛОГИКА БЕЗУБЫТКА (Breakeven)
            # Если цена прошла 50% пути до TP, переносим SL в точку открытия + минимальный спред
            
            # Для покупок (BUY)
            if pos.type == mt5.POSITION_TYPE_BUY:
                tp_dist = pos.tp - pos.price_open
                current_profit_dist = pos.price_current - pos.price_open
                
                if tp_dist > 0 and current_profit_dist >= (tp_dist * 0.5):
                    if pos.sl < pos.price_open: 
                        self._modify_sl(pos, pos.price_open, symbol, symbol_info.digits)

            # Для продаж (SELL)
            elif pos.type == mt5.POSITION_TYPE_SELL:
                tp_dist = pos.price_open - pos.tp
                current_profit_dist = pos.price_open - pos.price_current
                
                if tp_dist > 0 and current_profit_dist >= (tp_dist * 0.5):
                    if pos.sl > pos.price_open or pos.sl == 0:
                        self._modify_sl(pos, pos.price_open, symbol, symbol_info.digits)

    def _modify_sl(self, position, new_sl, symbol, digits):
        """Отправка запроса на изменение Stop Loss"""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": position.ticket,
            "symbol": symbol,
            "sl": round(new_sl, digits),
            "tp": position.tp,
        }
        
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            log.info(f"[{symbol}] Позиция {position.ticket} переведена в БЕЗУБЫТОК.")
        else:
            log.error(f"[{symbol}] Ошибка модификации SL #{position.ticket}: {result.comment}")

    def close_all_for_symbol(self, symbol):
        """Метод для shutdown_manager.py — экстренное закрытие всех позиций по ID"""
        positions = mt5.positions_get(symbol=symbol)
        if positions:
            for pos in positions:
                if pos.magic == self.magic:
                    # Логика закрытия (Market Close)
                    pass
