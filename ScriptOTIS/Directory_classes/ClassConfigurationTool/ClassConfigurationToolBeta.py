#!/usr/bin/env python3
import subprocess
from pathlib import Path
import logging
import os
from typing import Dict, List, Optional
import time

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
        self.centrum_host = centrum_host
        self.config_dir = Path(config_dir)
        self.jar_path = self.config_dir / jar_name
        self.last_result = {"devices": []}

        if not self.jar_path.exists():
            raise FileNotFoundError(f"JAR файл не найден: {self.jar_path}")

    def _execute_command(
        self, args: List[str], max_retries: int = 1
    ) -> Dict[str, List[Dict[str, str]]]:
        """Выполняет команду с повторами для недоступных узлов (только если max_retries > 1)"""
        all_devices = []
        unavailable_nodes = set()
        attempt = 0

        while attempt < max_retries:
            attempt += 1
            if max_retries > 1:
                logging.info(f"Попытка {attempt} из {max_retries}")

            try:
                result = subprocess.run(
                    ["java", "-jar", str(self.jar_path)] + args,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                )

                current_devices, current_unavailable = self._parse_output(result.stdout)

                # Объединяем результаты
                all_devices.extend(
                    [d for d in current_devices if d["tp"] not in unavailable_nodes]
                )
                unavailable_nodes.update(current_unavailable)

                # Если нет недоступных узлов или повторы не разрешены, завершаем
                if not current_unavailable or max_retries <= 1:
                    break

                # Ждем перед следующей попыткой
                if attempt < max_retries:
                    time.sleep(2)

            except subprocess.CalledProcessError as e:
                logging.error(f"Ошибка выполнения команды: {e.stderr}")
                if attempt == max_retries or max_retries <= 1:
                    return {"devices": [], "error": str(e.stderr)}  # type: ignore
                continue
            except Exception as e:
                logging.error(f"Неожиданная ошибка: {str(e)}")
                if attempt == max_retries or max_retries <= 1:
                    return {"devices": [], "error": str(e)}  # type: ignore
                continue

        # Добавляем None для недоступных узлов
        for node in unavailable_nodes:
            all_devices.append(
                {
                    "tp": node,
                    "type": None,
                    "cv": None,
                    "pv": None,
                    "online": None,
                    "status": "UNAVAILABLE",
                    "ip": None,
                    "ut": None,
                    "local patches": None,
                }
            )

        self.last_result = {"devices": all_devices}
        return self.last_result

    def _parse_output(self, output: str) -> tuple:
        """Парсит вывод, возвращает кортеж (устройства, недоступные_узлы)"""
        devices = []
        unavailable_nodes = set()

        for line in output.splitlines():
            line = line.strip()

            # Пропускаем служебные строки
            if not line or line.startswith(("Current client version:", "-")):
                continue

            # Обрабатываем сообщения о недоступности
            if "недоступен" in line.lower() or "unavailable" in line.lower():
                parts = line.split()
                for part in parts:
                    if part.replace(".", "").isdigit():  # Ищем номер узла
                        unavailable_nodes.add(part)
                        logging.warning(f"Узел {part} недоступен")
                continue

            # Парсим обычные записи об узлах
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

        return devices, unavailable_nodes

    def get_all_nodes(self, max_retries: int = 3) -> Dict[str, List[Dict[str, str]]]:
        """Получить информацию обо всех узлах с повторами для недоступных"""
        return self._execute_command(["-ch", self.centrum_host, "--all"], max_retries)

    def get_nodes_from_file(
        self, filename: str = "server.txt"
    ) -> Dict[str, List[Dict[str, str]]]:
        """Получить узлы из файла"""
        filepath = self.config_dir / filename
        return self._execute_command(["-ch", self.centrum_host, "-f", str(filepath)], 1)

    def update_servers(
        self,
        version: str,
        filename: str = "server.txt",
        no_backup: bool = True,
    ) -> Dict[str, List[Dict[str, str]]]:
        """Обновить серверы"""
        filepath = self.config_dir / filename
        args = ["-ch", self.centrum_host, "-f", str(filepath), "-sv", version]

        if no_backup:
            args.append("-nb")

        return self._execute_command(args, 1)

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

        return self._execute_command(args, 1)

    def save_last_result(self, filename: str = "last_result.json"):
        """Сохранить последний результат в файл"""
        import json

        filepath = self.config_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.last_result, f, ensure_ascii=False, indent=2)
        logging.info(f"Результат сохранен в {filepath}")


# Пример использования
if __name__ == "__main__":
    try:
        # Инициализация
        configurator = ConfiguratorTool(
            centrum_host="10.21.11.45",
            config_dir="C:\\Users\\iakushin.n\\Documents\\GitHub\\Python\\updaterJar",
        )

        # 1. Получить все узлы с повторами
        all_nodes = configurator.get_all_nodes(max_retries=3)
        print("Результат запроса всех узлов:")
        print(all_nodes)

        # 2. Обновить кассы (без повторов)
        # cash_update = configurator.update_cash_devices(
        #     cash_type="POS", version="10.4.14.14"
        # )
        # print("Результат обновления касс:")
        # print(cash_update)

        # Сохранить результат
        configurator.save_last_result()

    except Exception as e:
        logging.error(f"Критическая ошибка: {str(e)}")
