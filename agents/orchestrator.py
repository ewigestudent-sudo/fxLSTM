# FILE: agents/orchestrator.py
# LOCATION: PROJ_AI_FOREX_2026/agents/
# DESCRIPTION: Логический центр. Управляет циклами обучения и диспетчеризацией через RiskManager.

import numpy as np
import MetaTrader5 as mt5
from ai_brain.education import Education
from ai_brain.adaptation import Adaptation
from ai_brain.testing import ModelTester
from agents.riskmanager import RiskManager
from system_base.control import ErrorController
from system_base.logger import get_logger

log = get_logger("Orchestrator")

class Orchestrator:
    def __init__(self, brain, db_manager, trader, symbol_tf):
        self.brain = brain
        self.db = db_manager
        self.trader = trader
        self.symbol_tf = symbol_tf
        
        # Модули
        self.ctrl = ErrorController()
        self.risk = RiskManager(self.symbol_tf, self.trader)
        self.educator = Education(self.brain, self.db)
        self.adapter = Adaptation(self.brain)
        self.tester = ModelTester()
        
        # Состояния
        self.needs_testing = True 
        self.fit_attempts = 0
        self.auto_cycle_counter = 0 # Защита от бесконечного зацикливания
        self.last_p_close = None 
        self.confidence_score = 0.0

    def run_auto_cycle(self, is_sim_mode=False):
        """Сквозной процесс АВТОМАТИКА (ТЗ п.4 + Self-Preservation)."""
        self.auto_cycle_counter += 1
        if self.auto_cycle_counter > 3:
            log.critical(f"[{self.symbol_tf}] СТОП: Рынок непредсказуем. Модель не проходит тесты.")
            return False

        log.info(f"[{self.symbol_tf}] Авто-цикл (Попытка {self.auto_cycle_counter})...")
        self.trader.close_all_for_symbol(self.symbol_tf) 
        
        if not self.educator.run_full_cycle(self.symbol_tf, is_sim_mode=is_sim_mode):
            return self.run_auto_cycle(is_sim_mode=is_sim_mode)

        return self._run_test_fit_loop(is_sim_mode)

    def _run_test_fit_loop(self, is_sim_mode):
        # 1. Запуск теста производительности
        test_passed, mse = self.tester.run_performance_test(
            self.symbol_tf, self.brain.model, None, None, self.brain.scaler
        )

        # 2. Расчет динамического порога на основе ATR
        multiplier = self.brain.settings.get('error_multiplier', 1.5)
        
        # ЗАГРУБЛЕНИЕ ДЛЯ СИМУЛЯЦИИ (ТЗ п.4): 
        # В режиме SIM увеличиваем множитель в 3 раза, чтобы гарантированно пройти тест
        if is_sim_mode:
            multiplier *= 3.0
            log.info(f"[{self.symbol_tf}] SIM-MODE: Порог теста загрублен (Multiplier x3)")

        # Получаем ATR последнего бара (индекс 6 согласно структуре DataFactory 2026)
        history = self.db.get_history(self.symbol_tf, limit=1)
        current_threshold = 0.001 # Дефолт
        if history is not None and len(history) > 0:
            # Если в истории 7 колонок (O,H,L,C,V,RSI,ATR), ATR — это индекс 6
            current_threshold = history[0][6] if len(history[0]) > 6 else 0.001
        
        # Рассчитываем итоговый порог валидации
        validation_gate = current_threshold * multiplier

        # 3. ПРОВЕРКА ВЕРДИКТА
        # В SIM-режиме мы можем принудительно считать тест пройденным, если ошибка в разумных пределах
        if test_passed or (is_sim_mode and mse < validation_gate):
            log.info(f"[{self.symbol_tf}] МОДЕЛЬ ВАЛИДНА. Переход в режим ТОРГОВЛЯ.")
            # Сброс всех системных состояний (КРИТИЧЕСКИ ВАЖНО)
            self.ctrl.reset()
            self.needs_testing = False
            self.fit_attempts = 0
            self.auto_cycle_counter = 0
            return True
        
        # 4. АВАРИЯ: Если ошибка в 2 раза выше порога — полный цикл EDUCATION
        if mse > (validation_gate * 2): 
            log.warning(f"[{self.symbol_tf}] АВАРИЯ: Огромная ошибка ({mse:.6f}). Полный цикл обучения.")
            return self.run_auto_cycle(is_sim_mode)

        # 5. ПРЕДУПРЕЖДЕНИЕ -> Попытка адаптации (FIT)
        if self.fit_attempts < 3:
            self.fit_attempts += 1
            log.info(f"[{self.symbol_tf}] FIT: Попытка адаптации {self.fit_attempts}/3 (MSE: {mse:.6f})")
            recent_data = self.db.get_history(self.symbol_tf, limit=100)
            self.adapter.apply(recent_data, epochs=1 if is_sim_mode else 5)
            return self._run_test_fit_loop(is_sim_mode)
        
        # Если адаптации не помогли — на полную переподготовку
        log.error(f"[{self.symbol_tf}] Адаптации исчерпаны. Перезапуск EDUCATION.")
        return self.run_auto_cycle(is_sim_mode)


    def process_new_bar(self, data, mode, global_trading_allowed, raw_atr):
        # 0. Защита: если модель на тестировании, выходим
        if self.needs_testing: return

        # 1. Контроль точности (MSE) и расчет индекса доверия для HMI
        # Сравниваем прогноз прошлого шага с фактом текущего закрытого бара
        fact_ohl = np.array([data[-1, 3], data[-1, 1], data[-1, 2]]) 
        mse = self.brain.calculate_mse(fact_ohl)
        self.confidence_score = self._calculate_confidence(mse)
        
        # Получаем индивидуальный множитель из настроек Brain (из БД)
        multiplier = self.brain.settings.get('error_multiplier', 1.5)
        
        if mode == 'simulation':
            multiplier *= 3.0
        
        # Рассчитываем динамический порог: Текущая волатильность * Множитель из БД
        dynamic_threshold = raw_atr * multiplier
        
        # Передаем новый динамический порог в контроллер
        status = self.ctrl.check(mse, dynamic_threshold)

        if status == "ERROR":
            # Точность упала ниже критического порога — переобучаем
            self._handle_rebuild(is_sim_mode=(mode == 'simulation'))
            return 

        # 2. Генерация НОВОГО прогноза
        p_close, p_high, p_low = self.brain.predict(data)
        
        # Получаем текущие котировки (Ask/Bid) из терминала
        tick = mt5.symbol_info_tick(self.symbol_tf)
        if not tick: return
        
        # 3. Риск-менеджмент: Сопровождение (Trailing Forecast)
        # Закрываем старые позиции, если новый прогноз стал хуже предыдущего
        self.risk.check_trailing_forecast(p_close, self.last_p_close)

        # 4. Риск-менеджмент: Вход (Evaluation)
        if (mode == 'trade') and global_trading_allowed and self.ctrl.is_model_valid:
            # ТЕПЕРЬ ПЕРЕДАЕМ raw_atr для динамического фильтра волатильности
            signal = self.risk.evaluate_entry(tick, p_close, p_high, p_low, raw_atr)
            
            if signal == 'BUY':
                self.trader.execute_buy(self.symbol_tf, target=p_close, stop=p_low)
            elif signal == 'SELL':
                self.trader.execute_sell(self.symbol_tf, target=p_close, stop=p_high)

        # Сохраняем прогноз для сравнения на следующем баре
        self.last_p_close = p_close


    def _calculate_confidence(self, mse):
        """Расчет индекса доверия (0-100%)."""
        if mse == 0 or not self.ctrl.history_mse or self.ctrl.last_threshold == 0:
            return 100.0
        
        avg_mse = sum(self.ctrl.history_mse) / len(self.ctrl.history_mse)
        
        ratio = mse / (avg_mse * self.brain.settings.get('error_multiplier', 1.5))
        return round(max(0, min(100, (1 - ratio) * 100)), 2)

    def _handle_rebuild(self, is_sim_mode=False):
        self.trader.close_all_for_symbol(self.symbol_tf)
        if self.educator.run_full_cycle(self.symbol_tf, is_sim_mode=is_sim_mode):
            self.needs_testing = True

    def manual_fit_trigger(self, is_sim_mode=False):
        self.trader.close_all_for_symbol(self.symbol_tf)
        recent_data = self.db.get_history(self.symbol_tf, limit=100)
        self.adapter.apply(recent_data, epochs=1 if is_sim_mode else 5)

    def run_test_diagnostics(self):
        passed, _ = self.tester.run_performance_test(self.symbol_tf, self.brain.model, None, None, self.brain.scaler)
        if passed: self.needs_testing = False
        return passed
        
    def handle_pair_rebuild(self, jr_needs_edu, sr_needs_edu):
    """Логика из ваших вводных по Scenario 2."""
    if self.queue.request_permission():
        try:
            # Учим тех, кому нужно (поочередно)
            if jr_needs_edu: self.educator_jr.run_full_cycle()
            if sr_needs_edu: self.educator_sr.run_full_cycle()
            
            # Специфика Scenario 2: если одна исправна, но имеет 1 варнинг -> на FIT
            if not jr_needs_edu and self.orch_jr.ctrl.warning_count > 0:
                self.adapter_jr.apply(recent_data)
            if not sr_needs_edu and self.orch_sr.ctrl.warning_count > 0:
                self.adapter_sr.apply(recent_data)
        finally:
            self.queue.release()
