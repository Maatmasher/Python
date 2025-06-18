import subprocess
from pathlib import Path
import logging
from typing import Dict, List, Optional, Tuple
import time
import json

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
        self.node_result: Dict[str, Dict[str, Optional[str]]] = {}

        if not self.jar_path.exists():
            raise FileNotFoundError(f"JAR файл не найден: {self.jar_path}")

    def _execute_command(
        self, args: List[str], max_retries: int = 1
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Выполняет команду с повторами для недоступных узлов"""
        result_dict: Dict[str, Dict[str, Optional[str]]] = {}
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
                    encoding="cp1251",  # Кодировка cp1251 для русских символов
                    errors="replace",  # Заменяет некодируемые символы
                )

                if not result.stdout:
                    logging.warning("Пустой вывод от команды")
                    continue

                current_result, current_unavailable = self._parse_output(result.stdout)
                result_dict.update(current_result)
                unavailable_nodes.update(current_unavailable)

                if not current_unavailable or max_retries <= 1:
                    break

                if attempt < max_retries:
                    time.sleep(2)

            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if e.stderr else str(e)
                logging.error(f"Ошибка выполнения команды: {error_msg}")
                if attempt == max_retries or max_retries <= 1:
                    return {"error": {"message": error_msg}}
                continue
            except Exception as e:
                logging.error(f"Неожиданная ошибка: {str(e)}")
                if attempt == max_retries or max_retries <= 1:
                    return {"error": {"message": str(e)}}
                continue

        for node in unavailable_nodes:
            result_dict[node] = {
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

        self.node_result = result_dict
        return self.node_result

    def _parse_output(
        self, output: str
    ) -> Tuple[Dict[str, Dict[str, Optional[str]]], set]:
        """Парсит вывод команды"""
        if not output:
            return {}, set()

        devices_dict: Dict[str, Dict[str, Optional[str]]] = {}
        unavailable_nodes = set()

        try:
            for line in output.splitlines():
                line = line.strip()
                if not line or line.startswith(("Current client version:", "-")):
                    continue

                if "недоступен" in line.lower() or "unavailable" in line.lower():
                    parts = line.split()
                    for part in parts:
                        if part.replace(".", "").isdigit():
                            unavailable_nodes.add(part)
                            logging.warning(f"Узел {part} недоступен")
                    continue

                device: Dict[str, Optional[str]] = {}
                device_key = None

                for pair in line.split(";"):
                    pair = pair.strip()
                    if "=" in pair:
                        key, value = pair.split("=", 1)
                        key = key.strip()
                        value = (
                            value.strip() if value.strip().lower() != "null" else None
                        )
                        device[key] = value

                        if key == "ip" and value:
                            device_key = value
                        elif key == "tp" and value and not device_key:
                            device_key = value

                if device and device_key:
                    devices_dict[device_key] = device

        except Exception as e:
            logging.error(f"Ошибка при парсинге вывода: {str(e)}")
            return {}, set()

        return devices_dict, unavailable_nodes

    # Функция получить состояние всех узлов с Centrum
    def get_all_nodes(
        self, max_retries: int = 3
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Получить информацию обо всех узлах"""
        return self._execute_command(["-ch", self.centrum_host, "--all"], max_retries)

    # Получить состояние узлов перечисленных в файле
    def get_nodes_from_file(
        self, filename: str = "server.txt"
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Получить узлы из файла"""
        filepath = self.config_dir / filename
        return self._execute_command(["-ch", self.centrum_host, "-f", str(filepath)], 1)

    # Запустить обновление серверов список которых перечислены в файле
    def update_servers(
        self,
        version_sv: str,
        filename: str = "server.txt",
        no_backup: bool = True,
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Обновить серверы из файла без бэкапа базы по умолчанию"""
        filepath = self.config_dir / filename
        args = ["-ch", self.centrum_host, "-f", str(filepath), "-sv", version_sv]
        if no_backup:
            args.append("-nb")
        return self._execute_command(args, 1)

    # Запустить обновление касс по типу, список которых перечислены в файле
    def update_cash_devices(
        self,
        cash_type: str,
        version: str,
        filename: str = "server_cash.txt",
        no_backup: bool = True,
        auto_restart: bool = True,
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Обновить кассы из файла"""
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

    # Записать последний ответ от Jar в файл,
    def save_node_result(self, filename: str = "node_result.json"):
        """Сохранить результат в файл"""
        filepath = self.config_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.node_result, f, ensure_ascii=False, indent=2)
        logging.info(f"Результат сохранен в {filepath}")


if __name__ == "__main__":
    try:
        configurator = ConfiguratorTool(
            centrum_host="10.9.30.101",
            config_dir="C:\\Users\\iakushin.n\\Documents\\GitHub\\Python\\updaterJar",
        )

        # Тестирование
        # Получаем все узлы, пишем всё на экран и пишем node_result.json по умолчанию
        # all_nodes = configurator.get_all_nodes(max_retries=1)
        # print("Все узлы:")
        # for key, data in all_nodes.items():
        #     print(f"{key}: {data}")
        # configurator.save_node_result()
        # Получаем все узлы из файла, пишем всё на экран и пишем результат в server.json
        get_nodes_from_file = configurator.get_nodes_from_file()
        print("Узлы из файла:")
        for key, data in get_nodes_from_file.items():
            print(f"{key}: {data}")
        configurator.save_node_result(filename="server.json")

        # Запуск обновления серверов, просто выводим результат
        update_servers = configurator.update_servers(version_sv="10.4.15.2")
        print("Результат обновления серверов:\n")
        for key, data in update_servers.items():
            print(f"{key}: {data}")
        #configurator.save_answer_result(filename="server_update.json")

        # Запуск обновления касс, просто выводим результат
        cash_update = configurator.update_cash_devices(
            cash_type="POS", version="10.4.14.14"
        )
        print("\nРезультат обновления касс:")
        for key, data in cash_update.items():
            print(f"{key}: {data}")
        #configurator.save_answer_result(filename="server_cash_update.json")

    except Exception as e:
        logging.error(f"Ошибка какая то: {str(e)}")
