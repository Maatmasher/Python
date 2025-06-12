import subprocess
import os
from typing import Dict, List, Optional
from pathlib import Path
import logging


class ConfiguratorClient:
    def __init__(self, centrum_host: str, config_dir: str = "."):
        """
        Инициализация клиента для работы с ConfiguratorCmdClient

        Args:
            centrum_host: IP-адрес центрального сервера
            config_dir: Директория для хранения файлов конфигурации
        """
        self.centrum_host = centrum_host
        self.config_dir = Path(config_dir)
        self.jar_path = self.config_dir / "ConfiguratorCmdClient-1.5.1.jar"

        # Создаем директорию если ее нет
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.jar_path.exists():
            raise FileNotFoundError(f"JAR файл не найден: {self.jar_path}")

    def _run_command(self, args: List[str]) -> Dict[str, List[Dict[str, str]]]:
        """
        Запускает команду ConfiguratorCmdClient и парсит вывод

        Args:
            args: Список аргументов для команды

        Returns:
            Словарь с распарсенными данными устройств
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
            logging.error(f"Ошибка выполнения команды: {e.stderr}")
            raise
        except Exception as e:
            logging.error(f"Неожиданная ошибка: {str(e)}")
            raise

    def _parse_output(self, output: str) -> Dict[str, List[Dict[str, str]]]:
        """
        Парсит вывод ConfiguratorCmdClient

        Args:
            output: Строка вывода из ConfiguratorCmdClient

        Returns:
            Словарь с распарсенными данными устройств
        """
        devices = []

        for line in output.splitlines():
            line = line.strip()
            if (
                not line
                or line.startswith("Current client version:")
                or line.startswith("-")
            ):
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

        return {"devices": devices}

    def get_all_nodes(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Получает информацию обо всех узлах центрального сервера

        Returns:
            Словарь с информацией об узлах
        """
        return self._run_command(["-ch", self.centrum_host, "--all"])

    def get_nodes_from_file(
        self, filename: str = "server.txt"
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        Получает состояние узлов из файла

        Args:
            filename: Имя файла с узлами (по умолчанию server.txt)

        Returns:
            Словарь с информацией об узлах
        """
        filepath = self.config_dir / filename
        return self._run_command(["-ch", self.centrum_host, "-f", str(filepath)])

    def update_servers(
        self, version: str, filename: str = "server.txt", no_backup: bool = True
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        Запускает обновление серверов из файла

        Args:
            version: Версия для обновления
            filename: Имя файла с узлами (по умолчанию server.txt)
            no_backup: Не создавать резервные копии

        Returns:
            Словарь с информацией об узлах
        """
        filepath = self.config_dir / filename
        args = ["-ch", self.centrum_host, "-f", str(filepath), "-sv", version]

        if no_backup:
            args.append("-nb")

        return self._run_command(args)

    def update_cash_devices(
        self,
        cash_type: str,
        version: str,
        filename: str = "server.txt",
        no_backup: bool = True,
        auto_restart: bool = True,
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        Запускает обновление кассовых устройств

        Args:
            cash_type: Тип кассового устройства (POS, SCO, SCO_3, Touch)
            version: Версия для обновления
            filename: Имя файла с узлами (по умолчанию server.txt)
            no_backup: Не создавать резервные копии
            auto_restart: Автоматический перезапуск

        Returns:
            Словарь с информацией об узлах
        """
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

        return self._run_command(args)
