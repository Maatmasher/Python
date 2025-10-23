# logger_manager.py
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import re

class SensitiveDataFilter(logging.Filter):
    """
    Фильтр, скрывающий чувствительные данные в сообщениях логов.
    """
    def __init__(self, patterns: Optional[list] = None):
        super().__init__()
        # Паттерны чувствительных данных (можно расширить)
        self.patterns = patterns or [
            # Пароли
            r'password\s*[:=]\s*["\']?([^"\']+)["\']?',
            r'pw\s+([^"\s]+)',  # для plink
            # Токены
            r'bot_token\s*[:=]\s*["\']?([^"\']+)["\']?',
            r'bot\s*[:=]\s*["\']?([^"\']+)["\']?',
            r'token\s*[:=]\s*["\']?([^"\']+)["\']?',
            # IP-адреса (опционально)
            # r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
            # И другие, если нужно
        ]

    def filter(self, record):
        # Обрабатываем сообщение
        record.msg = self._mask_sensitive(record.msg)
        # Обрабатываем аргументы (если есть)
        if record.args:
            args = list(record.args)
            for i, arg in enumerate(args):
                if isinstance(arg, str):
                    args[i] = self._mask_sensitive(arg)
            record.args = tuple(args)
        return True

    def _mask_sensitive(self, msg: str) -> str:
        if not isinstance(msg, str):
            return msg
        for pattern in self.patterns:
            msg = re.sub(pattern, r'\1 -> ***', msg, flags=re.IGNORECASE)
        return msg

class LoggerManager:
    """Класс для управления настройками и конфигурацией логирования"""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._default_config()
        self.loggers = {}

    def _default_config(self) -> None:
        """Установка конфигурации по умолчанию"""
        default_config = {
            "log_level": "INFO",
            "log_format": "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            "date_format": "%Y-%m-%d %H:%M:%S",
            "log_to_console": True,
            "log_to_file": True,
            "log_directory": "logs",
            "log_filename": "application.log",
            "max_file_size": 10485760,  # 10 MB
            "backup_count": 5,
            "encoding": "utf-8",
            "separate_module_logs": False,
        }
        # Обновляем конфигурацию значениями по умолчанию, если они не заданы
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value

    def setup_logging(self) -> None:
        """Настройка корневого логгера"""
        try:
            # Создаем директорию для логов если нужно
            if self.config["log_to_file"]:
                log_dir = Path(self.config["log_directory"])
                log_dir.mkdir(exist_ok=True)
                print(f"Директория для логов: {log_dir.absolute()}")  # Для отладки
            # Настраиваем корневой логгер
            root_logger = logging.getLogger()
            root_logger.setLevel(self._get_log_level())

            # --- НАЧАЛО НОВОГО КОДА ---
            # Добавляем фильтр к корневому логгеру
            root_logger.addFilter(SensitiveDataFilter())
            # --- КОНЕЦ НОВОГО КОДА ---

            # Очищаем существующие обработчики
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            # Добавляем обработчики
            if self.config["log_to_console"]:
                self._add_console_handler(root_logger)
            if self.config["log_to_file"]:
                self._add_file_handler(root_logger)
            logging.info("Логирование успешно настроено")
        except Exception as e:
            print(f"Ошибка настройки логирования: {e}")
            # Fallback к базовому логированию
            logging.basicConfig(level=logging.INFO)

    def get_logger(self, name: str, level: Optional[str] = None) -> logging.Logger:
        """Получение именованного логгера с настройками"""
        if name in self.loggers:
            return self.loggers[name]
        logger = logging.getLogger(name)
        if level:
            logger.setLevel(self._parse_log_level(level))
        else:
            logger.setLevel(self._get_log_level())
        # Если нужны отдельные обработчики для модулей
        if self.config.get("separate_module_logs"):
            self._setup_module_logger(logger, name)
        self.loggers[name] = logger
        return logger

    def _setup_module_logger(self, logger: logging.Logger, module_name: str) -> None:
        """Настройка отдельного логгера для модуля"""
        # Очищаем существующие обработчики модуля
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        formatter = logging.Formatter(
            self.config["log_format"], datefmt=self.config["date_format"]
        )
        # Консольный обработчик
        if self.config["log_to_console"]:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        # Файловый обработчик для модуля
        if self.config["log_to_file"]:
            module_filename = f"{module_name}.log"
            file_handler = self._create_file_handler(module_filename)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    def _add_console_handler(self, logger: logging.Logger) -> None:
        """Добавление консольного обработчика"""
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self._get_log_level())
        formatter = logging.Formatter(
            self.config["log_format"], datefmt=self.config["date_format"]
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    def _add_file_handler(self, logger: logging.Logger) -> None:
        """Добавление файлового обработчика"""
        try:
            file_handler = self._create_file_handler(self.config["log_filename"])
            file_handler.setLevel(self._get_log_level())
            formatter = logging.Formatter(
                self.config["log_format"], datefmt=self.config["date_format"]
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logging.error(f"Ошибка создания файлового обработчика: {e}")

    def _create_file_handler(self, filename: str) -> logging.Handler:
        """Создание файлового обработчика с ротацией"""
        log_path = Path(self.config["log_directory"]) / filename
        try:
            # Используем RotatingFileHandler для ротации логов
            from logging.handlers import RotatingFileHandler
            return RotatingFileHandler(
                log_path,
                maxBytes=self.config["max_file_size"],
                backupCount=self.config["backup_count"],
                encoding=self.config["encoding"],
            )
        except ImportError:
            # Fallback к обычному FileHandler
            return logging.FileHandler(log_path, encoding=self.config["encoding"])

    def _get_log_level(self) -> int:
        """Получение уровня логирования как числа"""
        return self._parse_log_level(self.config["log_level"])

    def _parse_log_level(self, level_str: str) -> int:
        """Парсинг строкового уровня логирования"""
        level_str = level_str.upper()
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        return levels.get(level_str, logging.INFO)

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Обновление конфигурации логирования"""
        self.config.update(new_config)
        self.setup_logging()  # Переapply настройки

    def get_current_config(self) -> Dict[str, Any]:
        """Получение текущей конфигурации"""
        return self.config.copy()

    def create_logger_with_context(
        self, name: str, context: Dict[str, str]
    ) -> logging.Logger:
        """Создание логгера с дополнительным контекстом"""
        logger = self.get_logger(name)
        # Добавляем фильтр для контекста
        class ContextFilter(logging.Filter):
            def __init__(self, context):
                super().__init__()
                self.context = context
            def filter(self, record):
                for key, value in self.context.items():
                    setattr(record, key, value)
                return True
        # Добавляем фильтр к логгеру
        context_filter = ContextFilter(context)
        logger.addFilter(context_filter)
        return logger

# Фабрика для удобного создания менеджера логирования
def create_logger_manager(config: Optional[Dict[str, Any]] = None) -> LoggerManager:
    """Создание менеджера логирования с конфигурацией"""
    return LoggerManager(config)