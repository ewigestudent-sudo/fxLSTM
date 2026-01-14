# FILE: ai_brain/adaptation.py
import tensorflow as tf
from system_base.logger import get_logger

log = get_logger("Adaptation")

class Adaptation:
    def __init__(self, brain):
        """
        brain: экземпляр класса Brain, содержащий модель и настройки из БД.
        """
        self.brain = brain

    def apply(self, data, epochs=None):
        """
        Легкая подстройка (Fine-tuning) на свежих данных.
        data: последний тензор данных [window_size, features]
        """
        if self.brain.model is None:
            log.error(f"[{self.brain.symbol_tf}] Адаптация невозможна: модель не загружена.")
            return

        try:
            # 1. Подготовка данных через метод Brain (уже учитывает динамическое окно)
            X, y = self.brain.prepare_adaptation_data(data)
            
            # 2. Получаем базовый LR из настроек БД этой модели
            # Берем из БД, если нет — используем текущий из оптимизатора
            base_lr = self.brain.settings.get('learning_rate', 0.001)
            
            # Для адаптации (Incremental Learning) используем 10% от базового LR,
            # чтобы не разрушить веса модели резким скачком.
            adaptation_lr = base_lr * 0.1
            
            # 3. Сохраняем старый LR и устанавливаем адаптивный
            old_lr = tf.keras.backend.get_value(self.brain.model.optimizer.lr)
            tf.keras.backend.set_value(self.brain.model.optimizer.lr, adaptation_lr)

            # 4. Короткое обучение
            # Количество эпох можно передать из Orchestrator (например, 1 для SIM, 5 для REAL)
            actual_epochs = epochs if epochs else 2

            log.info(f"[{self.brain.symbol_tf}] Fine-tuning (LR: {adaptation_lr:.6f}, Epochs: {actual_epochs})")

            history = self.brain.model.fit(
                X, y, 
                epochs=actual_epochs, 
                batch_size=1, 
                verbose=0
            )

            # 5. Восстанавливаем оригинальный LR
            tf.keras.backend.set_value(self.brain.model.optimizer.lr, old_lr)
            
            mse = history.history['loss'][-1]
            log.info(f"[{self.brain.symbol_tf}] Адаптация завершена. Local MSE: {mse:.6f}")
            
        except Exception as e:
            log.error(f"[{self.brain.symbol_tf}] Ошибка при адаптации: {e}")

    def force_update(self, X_batch, y_batch, epochs=5):
        """Принудительная адаптация на пакете свежих данных (например, после WARN)"""
        try:
            self.brain.model.fit(X_batch, y_batch, epochs=epochs, verbose=0, batch_size=len(X_batch))
            log.info(f"[{self.brain.symbol_tf}] Принудительная адаптация пакета выполнена.")
        except Exception as e:
            log.error(f"[{self.brain.symbol_tf}] Ошибка при force_update: {e}")
