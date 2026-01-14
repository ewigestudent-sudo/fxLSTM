# sys/TestControl.py
import numpy as np
from system_base.control import ErrorController
from system_base.logger import get_logger

log = get_logger("TestControl_Unit")

def run_control_test():
    log.info("--- Запуск модульного теста ErrorController (v2026) ---")
    
    # Инициализируем контроллер с порогами из ТЗ: 
    # Warning (Adaptation) = 1.2, Error (Re-Education) = 1.8
    controller = ErrorController(threshold_warn=1.2, threshold_err=1.8)
    
    # 1. СТАБИЛЬНАЯ РАБОТА
    log.info("Этап 1: Формирование базовой линии (Baseline) стабильной работы.")
    baseline_mse = [0.00010] * 10  # 10 баров с одинаковой ошибкой
    for mse in baseline_mse:
        controller.check(mse)
    
    avg_mse = sum(controller.history_mse) / len(controller.history_mse)
    log.info(f"Базовая средняя ошибка установлена: {avg_mse:.6f}")

    # 2. ТЕСТ ПРЕДУПРЕЖДЕНИЯ (ADAPTATION)
    log.info("Этап 2: Имитация постепенного разлада (Warning).")
    # Ошибка 0.00013 — это > 1.2 от средней (0.00012)
    warn_mse = 0.00014 
    for i in range(1, 4):
        status = controller.check(warn_mse)
        log.info(f"Попытка {i}: MSE {warn_mse:.6f} -> Status: {status}")
        if i < 3:
            assert status == "OK", "Должно быть OK до 3-го предупреждения"
        else:
            assert status == "WARNING", "На 3-й раз должен быть WARNING"

    # 3. ТЕСТ КРИТИЧЕСКОГО СБОЯ (RE-EDUCATION)
    log.info("Этап 3: Имитация резкого скачка (Critical Error).")
    critical_mse = 0.00030 # Это > 1.8 от средней
    status = controller.check(critical_mse)
    log.info(f"MSE {critical_mse:.6f} -> Status: {status}")
    
    assert status == "ERROR", "Контроллер должен вернуть ERROR при резком скачке"
    assert controller.is_model_valid is False, "Флаг валидности должен сброситься"

    # 4. ТЕСТ КАРАНТИНА
    log.info("Этап 4: Проверка выхода из карантина (4 чистых прогноза).")
    for i in range(1, 6):
        status = controller.check(0.00010) # Возврат к норме
        log.info(f"Проверка {i}: MSE 0.00010 -> Status: {status}, Valid: {controller.is_model_valid}")
        if i < 4:
            assert controller.is_model_valid is False
        else:
            assert controller.is_model_valid is True

    log.info("✅ Тест ErrorController успешно пройден!")

if __name__ == "__main__":
    try:
        run_control_test()
    except AssertionError as e:
        log.critical(f"❌ ТЕСТ ПРОВАЛЕН: {e}")
    except Exception as e:
        log.critical(f"❌ Непредвиденная ошибка в тесте: {e}")
