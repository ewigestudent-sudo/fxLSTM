# FILE: ai_brain/validator.py
# LOCATION: PROJ_AI_FOREX_2026/ai_brain/
# DESCRIPTION: Модуль валидации в реальном времени. Ожидает 3-5 баров для подтверждения модели.

import numpy as np
from system_base.logger import get_logger

log = get_logger("Validator")

class RealTimeValidator:
    def __init__(self, symbol_tf, brain):
        self.symbol_tf = symbol_tf
        self.brain = brain
        self.validation_mse_history = []
        self.bars_needed = 5 # Ждем 5 баров для достоверного суждения
        self.bars_count = 0

    def check_new_bar(self, current_data):
        """
        Проверка нового бара в режиме ожидания TEST.
        Возвращает 0 (OK), 1 (Warning), 2 (Error) или -1 (In Progress).
        """
        self.bars_count += 1
        if self.bars_count < self.bars_needed: return -1
        
        # Получаем множитель из настроек Brain
        multiplier = self.brain.settings.get('error_multiplier', 1.5)
        dynamic_threshold = current_atr * multiplier
        warn_threshold = dynamic_threshold * 0.8

        # 1. Сравниваем прогноз прошлого бара с фактом
        fact_ohl = np.array([current_data[-1, 3], current_data[-1, 1], current_data[-1, 2]]) 
        mse = self.brain.calculate_mse(fact_ohl)
        self.validation_mse_history.append(mse)
        
        log.info(f"[{self.symbol_tf}] Валидация: Бар {self.bars_count}/5. MSE: {mse:.6f}")

        if self.bars_count < self.bars_needed:
            return -1 # Ждем дальше

        # 2. Вынесение финального вердикта
        avg_mse = np.mean(self.validation_mse_history)

        if  avg_mse > dynamic_threshold:
            log.error(f"[{self.symbol_tf}] ВАЛИДАЦИЯ ПРОВАЛЕНА: ERROR. MSE: {avg_mse:.6f}")
            return 2 # Error -> Education

        if avg_mse > warn_threshold:
            log.warning(f"[{self.symbol_tf}] ВАЛИДАЦИЯ WARNING. MSE: {avg_mse:.6f}")
            return 1 # Warning -> FIT
        
        log.info(f"[{self.symbol_tf}] ВАЛИДАЦИЯ УСПЕШНА: OK. MSE: {avg_mse:.6f}")
        return 0 # OK -> Trade

    def reset(self):
        self.validation_mse_history = []
        self.bars_count = 0
