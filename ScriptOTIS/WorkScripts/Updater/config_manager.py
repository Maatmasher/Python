# config_manager.py
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging


class ConfigManager:
    """Класс для управления конфигурационными параметрами"""

    def __init__(self, config_file: Optional[str] = None):
        self._config: Dict[str, Any] = {}
        self._load_default_config()

        if config_file:
            self.load_from_file(config_file)

    def _load_default_config(self) -> None:
        """Загрузка конфигурации по умолчанию"""
        CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
        # Создаем папку для логов если её нет
        log_dir = os.path.join(CURRENT_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)

        self._config = {
            # Основные настройки
            "centrum_host": "10.21.11.45",
            "current_dir": CURRENT_DIR,
            "config_dir": os.path.join(CURRENT_DIR, "updaterJar"),
            "jar_name": "ConfiguratorCmdClient-1.5.1.jar",
            "files_dir": os.path.join(CURRENT_DIR, "Files"),
            "plink_dir": os.path.join(CURRENT_DIR, "Plink"),
            "jar_behavior": False,
            "ssh_user": "otis",
            "service_name": "UnifiedServerUpdater",
            "plink_path": os.path.join(CURRENT_DIR, "Plink", "plink.exe"),
            # Настройки подключения к БД
            "db_host": "10.21.11.201",
            "db_port": 5432,
            "db_name": "GD",
            "db_user": "postgres",
            "db_table": "tpl_muk",
            "db_service_name": "rn-otis-tools",
            # Настройки обновления
            "target_version": "10.4.17.15",
            "part_server_size": 5,
            "max_iterations": None,
            # "max_retries_default": 3,
            # "max_retries_single": 3,
            # "default_no_backup": True,
            "pre_update_work": True,
            "post_update_work": True,
            # Таймауты и интервалы
            "wait_between_retries": 3,
            "status_check_interval": 300,
            "ping_timeout": 2000,
            "plink_timeout": 300,
            "pre_update_timeout": 60,
            "post_update_timeout": 60,
            # Настройки логирования
            "logging": {
                "log_level": "INFO",
                "log_format": "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
                "date_format": "%Y-%m-%d %H:%M:%S",
                "log_to_console": True,
                "log_to_file": True,
                "log_directory": log_dir,
                "log_filename": "application.log",
                "max_file_size": 10485760,  # 10 MB
                "backup_count": 5,
                "encoding": "utf-8",
                "separate_module_logs": False,
            },
            # Имена файлов
            "status_prefix": "server_",
            "files": {
                "server_list": "server.txt",
                "node_list": os.path.join("Files", "node_list.txt"),
                "node_result": os.path.join("Files", "node_result.json"),
                "ccm_restart_commands": os.path.join(
                    CURRENT_DIR, "Plink", "ccm_commands.txt"
                ),
                "unzip_restart_commands": os.path.join(
                    CURRENT_DIR, "Plink", "unzip_commands.txt"
                ),
                "pre_update_commands": os.path.join(
                    CURRENT_DIR, "Plink", "pre_update_commands.txt"
                ),
                "post_update_commands": os.path.join(
                    CURRENT_DIR, "Plink", "post_update_commands.txt"
                ),
                "work_tp": "work_tp.txt",
                "error_tp": "error_tp.txt",
                "update_tp": "update_tp.txt",
                "ccm_tp": "ccm_tp.txt",
                "unzip_tp": "unzip_tp.txt",
                "no_update_needed_tp": "no_update_needed_tp.txt",
                "unavailable_tp": "unavailable_tp.txt",
            },
        }

    def load_from_file(self, config_file: str) -> None:
        """Загрузка конфигурации из JSON файла"""
        try:
            import json

            with open(config_file, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                self._config.update(file_config)
            logging.info(f"Конфигурация загружена из файла: {config_file}")
        except Exception as e:
            logging.warning(f"Не удалось загрузить конфигурацию из файла: {e}")

    def save_to_file(self, config_file: str) -> None:
        """Сохранение конфигурации в JSON файл"""
        try:
            import json

            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logging.info(f"Конфигурация сохранена в файл: {config_file}")
        except Exception as e:
            logging.error(f"Ошибка сохранения конфигурации: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Получение значения конфигурации"""
        try:
            # Поддержка вложенных ключей через точку
            if "." in key:
                keys = key.split(".")
                value = self._config
                for k in keys:
                    value = value[k]
                return value
            return self._config.get(key, default)
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """Установка значения конфигурации"""
        if "." in key:
            keys = key.split(".")
            config_level = self._config
            for k in keys[:-1]:
                if k not in config_level:
                    config_level[k] = {}
                config_level = config_level[k]
            config_level[keys[-1]] = value
        else:
            self._config[key] = value

    def get_full_path(self, file_key: str) -> Path:
        """Получение полного пути к файлу"""
        # Проверяем, является ли ключ файлом из раздела files
        if file_key.startswith("files."):
            # Это файл из раздела files
            file_name = self.get(file_key)
            if file_name is None:
                raise ValueError(f"Ключ {file_key} не найден в конфигурации")

            base_dir = self.get("config_dir")
            if base_dir is None:
                raise ValueError("Ключ config_dir не найден в конфигурации")

            return Path(base_dir) / file_name
        else:
            # Это обычный путь (не файл из раздела files)
            path_value = self.get(file_key)
            if path_value is None:
                raise ValueError(f"Ключ {file_key} не найден в конфигурации")

            return Path(path_value)

    def validate(self) -> bool:
        """Валидация конфигурации - проверяет только существование директорий и критически важных файлов"""
        # Проверяем существование директорий
        required_dirs = ["config_dir", "files_dir", "plink_dir"]

        for dir_key in required_dirs:
            try:
                dir_path = self.get_full_path(dir_key)
                if not dir_path.exists():
                    logging.info(f"Директория не существует, создаем:: {dir_path}")
                    # Создаем директорию с промежуточными папками
                    os.makedirs(dir_path, exist_ok=True)
                    continue
                    # return False
                if not dir_path.is_dir():
                    logging.error(f"Путь не является директорией: {dir_path}")
                    return False
            except ValueError as e:
                logging.error(f"Ошибка валидации директории: {e}")
                return False

        # Проверяем существование только критически важных файлов (которые должны существовать до запуска)
        critical_files = [
            "plink_path",
        ]

        for file_key in critical_files:
            try:
                file_path = self.get_full_path(file_key)
                if not file_path.exists():
                    logging.error(f"Критический файл не существует: {file_path}")
                    return False
                if not file_path.is_file():
                    logging.error(f"Путь не является файлом: {file_path}")
                    return False
            except ValueError as e:
                logging.error(f"Ошибка валидации файла: {e}")
                return False

        # Файлы, которые создаются в процессе работы (server.txt и другие) - не проверяем
        logging.info("Валидация конфигурации успешно пройдена")
        return True

    def __getitem__(self, key: str) -> Any:
        """Доступ к конфигурации через квадратные скобки"""
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Установка конфигурации через квадратные скобки"""
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        """Проверка наличия ключа в конфигурации"""
        try:
            self.get(key)
            return True
        except (KeyError, TypeError):
            return False

    @property
    def all_config(self) -> Dict[str, Any]:
        """Получение всей конфигурации (только для чтения)"""
        return self._config.copy()
