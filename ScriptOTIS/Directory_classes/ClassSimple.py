#!/usr/bin/env python3
import subprocess
from pathlib import Path
import logging
from typing import Dict, List

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class ConfiguratorTool:
    def __init__(
        self,
        centrum_host: str,
        config_dir: str = ".",
        jar_name: str = "ConfiguratorCmdClient-1.5.1.jar",
    ):
        """
        Инициализация инструмента для работы с ConfiguratorCmdClient

        :param centrum_host: IP центрального сервера
        :param config_dir: Директория с файлами конфигурации
        :param jar_name: Имя JAR-файла утилиты
        """
        self.centrum_host = centrum_host
        self.config_dir = Path(config_dir)
        self.jar_path = self.config_dir / jar_name
        self.last_result = {"devices": []}

        # Проверка существования JAR-файла
        if not self.jar_path.exists():
            raise FileNotFoundError(f"JAR файл не найден: {self.jar_path}")

    def _execute_command(self, args: List[str]) -> Dict[str, List[Dict[str, str]]]:
        """
        Внутренний метод для выполнения команд
        :param args: Список аргументов команды
        :return: Результат выполнения (словарь с устройствами)
        """
        cmd = ["java", "-jar", str(self.jar_path)] + args

        try:
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            return self._parse_output(result.stdout)

        except subprocess.CalledProcessError as e:
            error_msg = f"Ошибка выполнения команды: {e.stderr}"
            logging.error(error_msg)
            return {"devices": [], "error": error_msg}  # type: ignore
        except Exception as e:
            error_msg = f"Неожиданная ошибка: {str(e)}"
            logging.error(error_msg)
            return {"devices": [], "error": error_msg}  # type: ignore

    def _parse_output(self, output: str) -> Dict[str, List[Dict[str, str]]]:
        """
        Парсинг вывода команды

        :param output: Вывод команды
        :return: Словарь с распарсенными данными
        """
        devices = []

        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith(("Current client version:", "-")):
                continue

            device = {}
            for pair in line.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    device[key.strip()] = (
                        value.strip() if value.strip().lower() != "null" else None
                    )

            if device:
                devices.append(device)

        self.last_result = {"devices": devices}
        return self.last_result

    def get_all_nodes(self) -> Dict[str, List[Dict[str, str]]]:
        """Получить информацию обо всех узлах"""
        return self._execute_command(["-ch", self.centrum_host, "--all"])

    def get_nodes_from_file(
        self, filename: str = "server.txt"
    ) -> Dict[str, List[Dict[str, str]]]:
        """Получить узлы из файла"""
        filepath = self.config_dir / filename
        return self._execute_command(["-ch", self.centrum_host, "-f", str(filepath)])

    def update_servers(
        self, version: str, filename: str = "server.txt", no_backup: bool = True
    ) -> Dict[str, List[Dict[str, str]]]:
        """Обновить серверы"""
        filepath = self.config_dir / filename
        args = ["-ch", self.centrum_host, "-f", str(filepath), "-sv", version]

        if no_backup:
            args.append("-nb")

        return self._execute_command(args)

    def update_cash_devices(
        self,
        cash_type: str,
        version: str,
        filename: str = "server.txt",
        no_backup: bool = True,
        auto_restart: bool = True,
    ) -> Dict[str, List[Dict[str, str]]]:
        """Обновить кассовые устройства"""
        filepath = self.config_dir / filename
        args = [
            "-ch",
            self.centrum_host,
            "-f",
            str(filepath),
            "-sv",
            version,
            "-cv",
            f"{cash_type}:{version}",
        ]

        if no_backup:
            args.append("-nb")
        if auto_restart:
            args.append("-ar")

        return self._execute_command(args)

    def save_last_result(self, filename: str = "last_result.json"):
        """Сохранить последний результат в файл"""
        import json

        filepath = self.config_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.last_result, f, ensure_ascii=False, indent=2)
        logging.info(f"Результат сохранен в {filepath}")


# Пример использования
if __name__ == "__main__":
    # Инициализация
    configurator = ConfiguratorTool(
        centrum_host="10.21.11.45", config_dir="/path/to/config"
    )

    # 1. Получить все узлы
    all_nodes = configurator.get_all_nodes()
    print("Все узлы:", all_nodes)

    # 2. Получить узлы из файла
    file_nodes = configurator.get_nodes_from_file()
    print("Узлы из файла:", file_nodes)

    # 3. Обновить серверы
    update_result = configurator.update_servers(version="10.4.14.14")
    print("Результат обновления серверов:", update_result)

    # 4. Обновить POS кассы
    cash_update = configurator.update_cash_devices(
        cash_type="POS", version="10.4.14.14"
    )
    print("Результат обновления касс:", cash_update)

    # Сохранить последний результат
    configurator.save_last_result()

    # Инициализация
configurator = ConfiguratorTool(
    centrum_host="10.21.11.45", config_dir="/path/to/config"
)

# 1. Получить информацию о всех узлах
result = configurator.get_all_nodes()

# 2. Получить узлы из файла (с другим именем файла)
result = configurator.get_nodes_from_file(filename="custom_servers.txt")

# 3. Обновить серверы (с созданием бэкапов)
result = configurator.update_servers(version="10.4.14.15", no_backup=False)

# 4. Обновить кассы типа Touch (без авторестарта)
result = configurator.update_cash_devices(
    cash_type="Touch", version="10.4.14.15", auto_restart=False
)

# Сохранить последний результат
configurator.save_last_result("last_update_result.json")
