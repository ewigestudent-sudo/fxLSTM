# FILE: agents/tradingbot.py
# LOCATION: PROJ_AI_FOREX_2026/agents/
# DESCRIPTION: Контейнер агента. Управляет статусами, транслирует команды 
# из main.py в оркестратор и предоставляет данные для HMI (п.4 ТЗ).

from config import APP_CONFIG_PATH
from ai_brain.brain import Brain
from agents.orchestrator import Orchestrator
from data_sys.databasemanager import DatabaseManager
from data_sys.datafactory import DataFactory
from agents.trader import Trader
import json
import os

class TradingBot:
    def __init__(self, symbol, timeframe, mode='trade', global_trader=None):
        self.symbol = symbol
        self.tf = timeframe
        self.symbol_tf = f"{symbol}_{timeframe}"
        self.mode = mode # 'trade' или 'simulation'
        
        # Модули (структура 2026)
        self.db = DatabaseManager()
        self.brain_jr = Brain(f"{symbol}_{tf_junior}")
        self.brain_sr = Brain(f"{symbol}_{tf_senior}")       
        
        self.trader = global_trader if global_trader else Trader()
            
        # Оркестратор связывает мозг, данные и торговлю
        self.orch = Orchestrator(self.brain, self.db, self.trader, self.symbol_tf)
        
        # Метрики и состояния для HMI_Main
        self.last_time = 0
        self.is_active = True      
        self.status = "INIT"       # INIT, TRAINING, TESTING, WAIT_TEST, OK, WARN, ERROR, PAUSED
        self.current_mse = 0.0
        self.warnings = 0
        self.manual_stop = True    # По умолчанию стоим (ТЗ п.4: ждем кнопку START)

    def _get_global_allow_flag(self):
        """Проверка разрешения на торговлю из app_config.json (ТЗ)"""
        try:
            if os.path.exists(APP_CONFIG_PATH):
                with open(APP_CONFIG_PATH, 'r') as f:
                    config = json.load(f)
                    return config.get("trading_allowed", False)
        except: pass
        return False

    def initialize_bot(self, force_train=False, is_sim_mode=False):
        """
        Подготовка: загрузка весов или запуск EDUCATION.
        ТЗ п.4: Принудительный статус WAIT_TEST после обучения.
        """
        if not self.brain.load_weights() or force_train:
            self.status = "TRAINING"
            self.db.update_database(self.symbol, self.tf)
            # ТЗ п.4: Передаем флаг симуляции для загрубления
            self.orch._handle_rebuild(is_sim_mode=is_sim_mode) 
            self.status = "WAIT_TEST" 
        else:
            self.status = "OK"

    def run_auto_cycle_start(self, is_sim_mode=False):
        """
        Сценарий АВТОМАТИКА: Education -> Test -> Trade.
        Оптимизация: защита от бесконечного цикла (Self-Preservation).
        """
        self.status = "TRAINING"
        # Запуск итерационного процесса в Orchestrator (реализуем на след. шаге)
        success = self.orch.run_auto_cycle(is_sim_mode=is_sim_mode)
        
        if success:
            self.manual_stop = False
            self.status = "OK"
        else:
            self.status = "FATAL_ERROR" # Рынок непредсказуем
            self.manual_stop = True

    def run_diagnostic_test(self):
        """Метод для кнопки TEST в HMI (ТЗ п.4)"""
        self.status = "TESTING"
        # Вызов тестирования через оркестратор
        result = self.orch.run_test_diagnostics()
        
        if result:
            self.status = "OK"
            # Если тест пройден успешно, разрешаем торговлю, если не было ручного стопа
            # self.manual_stop = False # Опционально, зависит от того, нужно ли сразу в бой
        else:
            self.status = "WAIT_TEST" # Тест провален, торговля запрещена
        return result

    def tick(self):
        """Обновленный цикл 2026: Иерархия JR + SR таймфреймов."""
        
        # 1. Проверка ручной остановки
        if self.manual_stop:
            if self.status not in ["TRAINING", "TESTING", "WAIT_TEST", "FATAL_ERROR"]:
                self.status = "PAUSED"
            return

        # 2. ПОЛУЧЕНИЕ ДАННЫХ ДЛЯ ОБОИХ ТАЙМФРЕЙМОВ
        # Получаем данные Младшего ТФ (например, M15)
        data_jr, time_jr, atr_jr = DataFactory.get_data(
            self.symbol, self.tf_jr, self.brain_jr.window_size
        )
        
        # Получаем данные Старшего ТФ (например, H1)
        data_sr, time_sr, atr_sr = DataFactory.get_data(
            self.symbol, self.tf_sr, self.brain_sr.window_size
        )

        # Валидация наличия данных для обеих моделей
        if data_jr is None or data_sr is None:
            return

        # 3. ПРОВЕРКА НОВОГО БАРА (по младшему ТФ)
        if time_jr != self.last_time:
            # Проверяем заполненность окон
            if len(data_jr) == self.brain_jr.window_size and len(data_sr) == self.brain_sr.window_size:
                
                # А) Генерация прогнозов
                # Младшая модель дает точку входа
                p_close_jr, p_high_jr, p_low_jr = self.brain_jr.predict(data_jr)
                # Старшая модель дает глобальный вектор
                p_close_sr, _, _ = self.brain_sr.predict(data_sr)

                # Б) ПРИМЕНЕНИЕ ИЕРАРХИЧЕСКОГО ФИЛЬТРА (Ваша новая логика)
                # BUY: Прогноз JR выше текущей цены И прогноз SR еще выше (тренд подтвержден)
                # SELL: Прогноз JR ниже текущей цены И прогноз SR еще ниже
                current_price = data_jr[-1, 3] # Close последнего бара
                
                allow_by_hierarchy = False
                if p_close_jr > current_price and p_close_sr > p_close_jr:
                    allow_by_hierarchy = True # Глобальный аптренд подтвержден
                elif p_close_jr < current_price and p_close_sr < p_close_jr:
                    allow_by_hierarchy = True # Глобальный даунтренд подтвержден

                # В) ПЕРЕДАЧА В ОРКЕСТРАТОР
                trading_allowed = self._get_global_allow_flag() and allow_by_hierarchy
                
                # Важно: Оркестратор работает по младшему ТФ, но с учетом фильтра старшего
                self.orch.process_new_bar(
                    data_jr, 
                    self.mode, 
                    trading_allowed, 
                    atr_jr, 
                    hierarchical_signal={'p_sr': p_close_sr} # Передаем для доп. контроля в RiskManager
                )

                # 4. ОБНОВЛЕНИЕ МЕТРИК ДЛЯ HMI (по основной торговой модели JR)
                self.current_mse = self.orch.ctrl.history_mse[-1] if self.orch.ctrl.history_mse else 0
                self.warnings = self.orch.ctrl.warning_count
                self._update_visual_status()

                self.last_time = time_jr

    def _update_visual_status(self):
        """Вынос логики статуса в отдельный метод для чистоты tick()"""
        if self.orch.needs_testing:
            self.status = "WAIT_TEST"
        elif not self.orch.ctrl.is_model_valid:
            self.status = "ERROR"
        elif self.warnings > 0:
            self.status = "WARN (FIT)"
        else:
            self.status = "OK"


    def get_state(self):
        """Срез данных для экспорта в bot_states.json для HMI (2026 Style)"""
        return {
            "id": self.symbol_tf,
            "status": self.status,
            "mse": f"{self.current_mse:.6f}",
            "confidence": f"{self.orch.confidence_score}%", # Индекс доверия (оптимизация)
            "warnings": self.warnings,
            "is_active": not self.manual_stop,
            "mode": self.mode
        }
        
    def _check_pair_permission(self):
    """Сценарий 3: Проверка готовности пары к торгам."""
    # Условия: Обе исправны, нет варнингов, доверие > 80%
    jr_ok = (self.orch_jr.ctrl.is_model_valid and 
             self.orch_jr.ctrl.warning_count == 0 and 
             self.orch_jr.confidence_score > 80)
    
    sr_ok = (self.orch_sr.ctrl.is_model_valid and 
             self.orch_sr.ctrl.warning_count == 0 and 
             self.orch_sr.confidence_score > 80)
    
    if jr_ok and sr_ok:
        self.permission_lamp = "GREEN"
        return True
    else:
        self.permission_lamp = "RED"
        # Сценарий 1 и 2: Если хоть одна не в норме — закрываем всё
        self.trader.close_all_for_symbol(self.symbol_tf)
        return False
