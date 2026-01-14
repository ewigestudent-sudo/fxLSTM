# FILE: ai_brain/education.py
# LOCATION: PROJ_AI_FOREX_2026/ai_brain/
# DESCRIPTION: Модуль первичного обучения модели с использованием динамических настроек из БД.

import numpy as np
import joblib
import os
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
# Удален WINDOW_SIZE, так как он теперь в brain.window_size
from root.config import MODELS_DIR, FEATURES 
from system_base.logger import get_logger
from ai_brain.testing import ModelTester

log = get_logger("Education")

class Education:
    def __init__(self, brain, db_manager):
        self.brain = brain
        self.db = db_manager

    def run_full_cycle(self, symbol_tf, is_sim_mode=False):
        """
        Полный цикл обучения.
        Параметры окна, эпох и батча берутся из индивидуальных настроек БД (brain.settings).
        """
        # 1. Получаем актуальные настройки из объекта brain (синхронизировано с БД)
        stg = self.brain.settings
        win_size = self.brain.window_size
        db_epochs = stg.get('epochs', 20)
        db_batch = stg.get('batch_size', 32)

        # ТЗ п.4: Загрубление параметров для симуляции
        if is_sim_mode:
            log.info(f"[{symbol_tf}] Режим Simulation: параметры обучения загрублены.")
            actual_epochs = 1  # Минимум для проверки функционала
            data_limit = 2000  # Сокращенный объем данных
            current_batch = 16
        else:
            actual_epochs = db_epochs
            data_limit = 100000
            current_batch = db_batch

        log.info(f"[{symbol_tf}] Запуск EDUCATION (Эпох: {actual_epochs}, Окно: {win_size}, Лимит: {data_limit})")
        
        # 2. Загрузка данных
        raw_data = self.db.get_history(symbol_tf, limit=data_limit)
        # Используем win_size вместо WINDOW_SIZE
        if raw_data is None or len(raw_data) < win_size * 2:
            log.error(f"[{symbol_tf}] Недостаточно данных для обучения.")
            return False

        # 3. DataFrame и расчет 7 признаков (OHLCV + RSI + ATR)
        df = pd.DataFrame(raw_data, columns=['open', 'high', 'low', 'close', 'volume'])
        
        import pandas_ta as ta
        df.ta.rsi(length=14, append=True)
        df.ta.atr(length=14, append=True)
        df.dropna(inplace=True)

        # 4. Масштабирование
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled_data = scaler.fit_transform(df.values)
        
        # 5. Подготовка последовательностей (Используем win_size)
        X, y = self._prepare_sequences(scaled_data, win_size, target_cols=[3, 1, 2])
        
        split = int(len(X) * 0.9)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        # 6. Обучение модели
        self.brain.model.fit(
            X_train, y_train, 
            epochs=actual_epochs, 
            batch_size=current_batch, 
            validation_data=(X_test, y_test),
            verbose=0
        )
        
        # 7. Тестирование качества
        tester = ModelTester()
        is_valid, mse_score = tester.run_performance_test(symbol_tf, self.brain.model, X_test, y_test, scaler)
        
        if not is_valid and not is_sim_mode:
            log.warning(f"[{symbol_tf}] Низкая точность MSE: {mse_score:.6f}")

        # 8. Сохранение артефактов (п.3 ТЗ)
        self.brain.model.save_weights(self.brain.weights_path)
        joblib.dump(scaler, self.brain.scaler_path)
        
        # Обновляем скалер в памяти объекта brain для немедленной работы
        self.brain.scaler = scaler
        
        log.info(f"[{symbol_tf}] EDUCATION завершен. MSE: {mse_score:.6f}")
        return True

    def _prepare_sequences(self, data, window, target_cols):
        X, y = [], []
        for i in range(len(data) - window):
            X.append(data[i : (i + window)])
            y.append(data[i + window, target_cols])
        return np.array(X), np.array(y)
