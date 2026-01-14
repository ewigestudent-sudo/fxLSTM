# sys/shutdown_manager.py
import signal
import MetaTrader5 as mt5
import json
import os
from system_base.logger import get_logger
from config import APP_CONFIG_PATH

log = get_logger("Shutdown")

class ShutdownManager:
    def __init__(self):
        # В 2026 году решение о закрытии сделок зависит от настройки HMI
        self.close_on_exit = self._get_close_on_exit_setting()

    def _get_close_on_exit_setting(self):
        """Чтение флага из app_config.json"""
        if os.path.exists(APP_CONFIG_PATH):
            try:
                with open(APP_CONFIG_PATH, 'r') as f:
                    config = json.load(f)
                    # Предполагаем, что в app_config есть поле "close_on_exit": True/False
                    return config.get("close_on_exit", True) 
            except Exception as e:
                log.warning(f"Не удалось прочитать настройку закрытия при выходе: {e}")
        return True # Дефолтное безопасное поведение

    def execute(self, active_bots):
        """
        Основной метод, вызываемый из finally блока в main.py.
        """
        if not self.close_on_exit:
            log.info("Настройка 'Close all on Exit' отключена. Оставляем позиции открытыми.")
            return

        log.warning("ПОЛУЧЕН СИГНАЛ ЗАВЕРШЕНИЯ. Начинаю принудительное закрытие всех позиций...")

        # Используем логику PositionManager для закрытия по Symbol_TF
        # Нам нужно получить доступ к методу close_all_for_symbol в PositionManager
        # Так как PositionManager уже инстанцирован в main.py, мы можем вызвать его методы
        # (В данном коде просто имитируем вызов)
        
        symbols_to_close = set()
        for bot in active_bots:
            symbols_to_close.add(bot.symbol)

        for symbol in symbols_to_close:
            self._close_all_for_symbol(symbol)
            
        log.info("Все активные позиции закрыты. Система готова к выключению.")

    def _close_all_for_symbol(self, symbol):
        """
        Дублирование логики закрытия из PositionManager для автономности ShutdownManager
        """
        positions = mt5.positions_get(symbol=symbol)
        if positions:
            for pos in positions:
                # Отправка запроса на закрытие
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "position": pos.ticket,
                    "symbol": pos.symbol,
                    "volume": pos.volume,
                    "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                    "price": mt5.symbol_info_tick(pos.symbol).bid if pos.type == mt5.POSITION_TYPE_BUY else mt5.symbol_info_tick(pos.symbol).ask,
                    "magic": pos.magic,
                    "comment": "SHUTDOWN CLOSE",
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                mt5.order_send(request)
                log.info(f"Закрыта позиция #{pos.ticket} по {symbol}")

    def signal_handler(self, sig, frame):
        """Обработчик системных сигналов (Ctrl+C, SIGINT)"""
        log.warning(f"Системный сигнал {sig} получен.")
        # Здесь мы не вызываем execute(), т.к. это делается в finally блока main.py
        # Просто выходим из основного цикла
        sys.exit(0)
