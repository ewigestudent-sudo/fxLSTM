# ai_brain/brain.py
import os
import numpy as np
import joblib
from config import MODELS_DIR, FEATURES
from ai_brain.modelbuilder import ModelBuilder
from system_base.logger import get_logger

from data_sys.databasemanager import DatabaseManager

log = get_logger("Brain")

class Brain:
    def __init__(self, symbol_tf):
        self.symbol_tf = symbol_tf
        self.db = DatabaseManager() # Добавлено
        
        # 1. ЧИТАЕМ НАСТРОЙКИ ИЗ БД (Индивидуальные для этой пары)
        self.settings = self.db.get_model_settings(self.symbol_tf)

        # Берем window_size из индивидуальных настроек БД
        self.window_size = self.settings.get('window_size', 60)        
        
        # 2. ПЕРЕДАЕМ НАСТРОЙКИ В СТРОИТЕЛЬ
        self.settings = self.db.get_model_settings(self.symbol_tf)
        self.window_size = self.settings.get('window_size', 60)
        # Теперь передаем ТОЛЬКО локальное значение:
        self.model = ModelBuilder.build_lstm_model(self.window_size, FEATURES, self.settings)
        
        self.last_prediction = None
        self.scaler = None
        
        self.weights_path = os.path.join(MODELS_DIR, f"lstm_{self.symbol_tf}.h5")
        self.scaler_path = os.path.join(MODELS_DIR, f"scaler_{self.symbol_tf}.pkl")

    def load_weights(self):
        if os.path.exists(self.weights_path):
            try:
                self.model.load_weights(self.weights_path)
                if os.path.exists(self.scaler_path):
                    self.scaler = joblib.load(self.scaler_path)
                    return True
                else:
                    log.error(f"[{self.symbol_tf}] Scaler (.pkl) не найден.")
            except Exception as e:
                log.error(f"[{self.symbol_tf}] Ошибка загрузки весов: {e}")
        return False

    def predict(self, data_window):
        """
        data_window: нормализованный тензор [WINDOW_SIZE, FEATURES]
        """
        if self.scaler is None:
            if not self.load_weights():
                raise RuntimeError(f"Модель для {self.symbol_tf} не готова.")

        x_input = np.expand_dims(data_window, axis=0)
        raw_pred = self.model.predict(x_input, verbose=0)[0] # Ожидаем [Close, High, Low] нормализованные
        
        # ДЕНОРМАЛИЗАЦИЯ (Индексы в Scaler: 0:Open, 1:High, 2:Low, 3:Close, 4:Vol, 5:RSI, 6:ATR)
        # ВАЖНО: В Education.py и DataFactory порядок должен быть именно таким.
        try:
            p_close = (raw_pred[0] - self.scaler.min_[3]) / self.scaler.scale_[3]
            p_high  = (raw_pred[1] - self.scaler.min_[1]) / self.scaler.scale_[1]
            p_low   = (raw_pred[2] - self.scaler.min_[2]) / self.scaler.scale_[2]
            
            self.last_prediction = np.array([p_close, p_high, p_low])
            return p_close, p_high, p_low
        except Exception as e:
            log.error(f"[{self.symbol_tf}] Ошибка денормализации: {e}")
            return None, None, None

    def calculate_mse(self, fact_ohl):
        """fact_ohl: [Close, High, Low] в реальных ценах"""
        if self.last_prediction is None: return 0.0
        # Считаем MSE в реальных котировках для ErrorController
        return np.mean((self.last_prediction - fact_ohl)**2)

    def prepare_adaptation_data(self, data_window):
        """Подготовка X и y для Adaptation.py"""
        # X: все бары кроме последнего, y: последний бар (целевые колонки 3, 1, 2)
        X = np.expand_dims(data_window, axis=0)
        # Нам нужно предсказать Close, High, Low следующего бара. 
        # В режиме адаптации мы берем факт текущего закрытого бара как y.
        y = np.expand_dims(data_window[-1, [3, 1, 2]], axis=0) 
        return X, y
