# FILE: ai_brain/testing.py
import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error
from system_base.logger import get_logger

log = get_logger("Testing")

class ModelTester:
    @staticmethod
    def run_performance_test(symbol_tf, model, X_test, y_test, scaler):
        """
        Финальная валидация модели после цикла Education.
        Проверка точности прогноза [Close, High, Low].
        """
        log.info(f"[{symbol_tf}] Запуск тестирования точности (2026)...")
        
        try:
            # 1. Получение предсказаний (нормализованных)
            predictions_scaled = model.predict(X_test, verbose=0)
            
            # 2. Расчет MSE в нормализованном виде
            mse = mean_squared_error(y_test, predictions_scaled)
            
            # 3. Денормализация для оценки в реальных ценах (Исправлено)
            # Индексы в скалере: 3 - Close, 1 - High, 2 - Low
            # Используем ту же логику, что и в Brain.predict()
            
            y_real_close = (y_test[:, 0] - scaler.min_[3]) / scaler.scale_[3]
            p_real_close = (predictions_scaled[:, 0] - scaler.min_[3]) / scaler.scale_[3]
            
            mae_price = mean_absolute_error(y_real_close, p_real_close)
            
            log.info(f"[{symbol_tf}] Тест завершен. MSE: {mse:.8f} | MAE (Price): {mae_price:.5f}")
            
            # 4. Критерий допуска
            # Возвращаем True, если расчет прошел успешно. 
            # Логику "прошел/не прошел по порогу" берет на себя Orchestrator.
            return True, mse

        except Exception as e:
            log.error(f"[{symbol_tf}] Ошибка при выполнении теста производительности: {e}")
            return False, 1.0 # Возвращаем высокую ошибку при сбое
