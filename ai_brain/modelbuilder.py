import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dropout, Dense
from tensorflow.keras.optimizers import Adam, RMSprop, SGD

class ModelBuilder:
    @staticmethod
    def build_lstm_model(window_size, n_features, settings=None):
        """Строит модель на основе настроек из БД (2026)."""
        # Если настройки не переданы, берем жесткие дефолты
        u = settings.get('lstm_units', 100) if settings else 100
        d = settings.get('dropout_rate', 0.2) if settings else 0.2
        lr = settings.get('learning_rate', 0.001) if settings else 0.001
        opt_name = settings.get('optimizer', 'Adam') if settings else 'Adam'

        model = Sequential()
        model.add(LSTM(units=u, return_sequences=True, input_shape=(window_size, n_features)))
        model.add(Dropout(d))
        
        # Второй слой: масштабируемый
        model.add(LSTM(units=max(u // 2, 10), return_sequences=False))
        model.add(Dropout(d))
        
        model.add(Dense(units=3)) # [Close, High, Low]

        opts = {'Adam': Adam, 'RMSprop': RMSprop, 'SGD': SGD}
        optimizer = opts.get(opt_name, Adam)(learning_rate=lr)
        
        model.compile(optimizer=optimizer, loss='mean_squared_error')
        return model
