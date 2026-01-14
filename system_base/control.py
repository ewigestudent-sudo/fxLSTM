# sys/control.py
from system_base.logger import get_logger

log = get_logger("Control")

class ErrorController:
    def __init__(self, threshold_warn=None, threshold_err=None):
        """
        Инициализируется внутри каждого Orchestrator для конкретного Symbol_TF.
        """
        self.history_mse = []
        # Если пороги не переданы, берем глобальные из config.py
        self.threshold_warn = threshold_warn if threshold_warn else WARN_THRESHOLD
        self.threshold_err = threshold_err if threshold_err else ERR_THRESHOLD
        
        self.warning_count = 0                # Счетчик для запуска адаптации
        self.is_model_valid = True            # Флаг допуска к торгам (влияет на Trader)
        self.valid_forecasts_needed = 0       # "Карантин" после переобучения

    def check(self, current_mse, dynamic_threshold):
        self.threshold_err = dynamic_threshold  # Порог ERROR — это и есть наш ATR * multiplier
        self.threshold_warn = dynamic_threshold * 0.8 # Порог WARNING — 80% от лимита
        """
        Логика валидации модели 2026 года.
        Вызывается оркестратором при закрытии каждого нового бара.
        """
        if not self.history_mse:
            self.history_mse.append(current_mse)
            return "OK"

        # Рассчитываем скользящее среднее ошибки для оценки деградации
        avg_mse = sum(self.history_mse) / len(self.history_mse)
        
        # 1. КРИТИЧЕСКАЯ ОШИБКА (Сигнал к RE-EDUCATION)
        if current_mse > avg_mse * self.threshold_err:
            log.error(f"Критический сбой точности! MSE {current_mse:.6f} > Порог {avg_mse*self.threshold_err:.6f}")
            self.is_model_valid = False
            self.valid_forecasts_needed = 4 # Модель уходит на карантин на 4 бара
            self.warning_count = 0
            return "ERROR"

        # 2. ПРЕДУПРЕЖДЕНИЕ (Сигнал к ADAPTATION)
        if current_mse > avg_mse * self.threshold_warn:
            self.warning_count += 1
            log.warning(f"Warning {self.warning_count}/3: Повышенная ошибка прогноза.")
            if self.warning_count >= 3:
                self.warning_count = 0
                return "WARNING" # Оркестратор вызовет Adaptation.apply()
        else:
            # Снижаем счетчик предупреждений, если точность восстановилась
            self.warning_count = max(0, self.warning_count - 1)
            
            # Логика выхода из "карантина"
            if not self.is_model_valid:
                self.valid_forecasts_needed -= 1
                if self.valid_forecasts_needed <= 0:
                    self.is_model_valid = True
                    log.info("Модель успешно прошла валидацию. Торговля ВОЗОБНОВЛЕНА.")
                else:
                    log.info(f"Модель в карантине. Осталось подтверждений: {self.valid_forecasts_needed}")

        # Обновляем историю MSE (окно из последних 50 баров)
        self.history_mse.append(current_mse)
        if len(self.history_mse) > 50: 
            self.history_mse.pop(0)
            
        return "OK"
