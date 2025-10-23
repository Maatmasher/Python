# main.py
import logging
from config_manager import ConfigManager
from unified_server_updater import UnifiedServerUpdater
from logger_manager import LoggerManager
from telegram_logger import setup_telegram_logging 

def main():
    try:
        # Конфигурация по умолчанию
        config = ConfigManager()
        # Способ 1: Загрузка из файла
        # config = ConfigManager("config.json")
        # Способ 2: Динамическое изменение конфигурации
        config.set("target_version", "10.4.19.7")
        config.set("centrum_host", "10.100.105.9")
        # config.set("max_iterations", 1)

        # Инициализируем LoggerManager до UnifiedServerUpdater
        logging_config = config.get("logging", {})
        logger_manager = LoggerManager(logging_config)
        logger_manager.setup_logging()  # <-- Настраиваем логгирование

        logging.getLogger("httpx").setLevel(logging.WARNING)

        # Подключаем Telegram-логгирование
        setup_telegram_logging()

        updater = UnifiedServerUpdater(config, logger_manager=logger_manager)

        # Запуск процесса обновления
        success = updater.update_servers_part_server()
        # Или сбор информации по нодам
        # success = updater.get_all_nodes()
        # updater.save_node_result()
        if success:
            updater.logger.warning("Работа скрипта завершена успешно")
        else:
            updater.logger.error("Работа скрипта завершена с ошибками")
    except Exception as e:
        # Используем базовый print для критических ошибок инициализации
        print(f"Критическая ошибка инициализации: {e}")
        raise

# Запуск скрипта. Инициализация настроек в функции main.
if __name__ == "__main__":
    main()