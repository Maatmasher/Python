import subprocess
from pathlib import Path
import logging
from typing import Dict, List, Optional, Tuple, Set
import time
import json

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class ConfiguratorTool:
    """Инициализация класса, если не найдена JAR ошибка"""

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
        self.work_tp: List[str] = []
        self.error_tp: List[str] = []
        self.update_tp: List[str] = []
        self.ccm_tp: List[str] = []
        self.unzip_tp: List[str] = []
        self.no_update_needed_tp: List[str] = []  # Списки

        if not self.jar_path.exists():
            raise FileNotFoundError(f"JAR файл не найден: {self.jar_path}")

    def _execute_command(
        self, args: List[str], max_retries: int = 1
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Выполняет команду с повторами для недоступных узлов
        собирает списки узлов по их статусам
        Итоговые данные сохраняются в `self.node_result`"""
        result_dict: Dict[str, Dict[str, Optional[str]]] = {}
        unavailable_nodes: Set[str] = set()  # Список узлов недоступных
        success_nodes: Set[str] = set()  # Список узлов с запущенным обновлением
        no_update_needed_nodes: Set[str] = set()  # Список узлов не требующих обновления
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
                    encoding="cp1251",
                    errors="replace",
                )

                if not result.stdout:
                    logging.warning("Пустой вывод от команды")
                    continue

                (
                    current_result,
                    current_unavailable,
                    current_success,
                    current_no_update,
                ) = self._parse_output(result.stdout)
                result_dict.update(current_result)
                unavailable_nodes.update(current_unavailable)
                success_nodes.update(current_success)
                no_update_needed_nodes.update(current_no_update)

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

        # Заполнение недоступных узлов
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

        # Заполнение успешных узлов
        for node in success_nodes:
            if node not in result_dict:
                result_dict[node] = {
                    "tp": node,
                    "status": "SUCCESS",
                    "message": "успешно запланировано",
                    "type": None,
                    "cv": None,
                    "pv": None,
                    "online": None,
                    "ip": None,
                    "ut": None,
                    "local patches": None,
                }

        # Заполнение узлов, не требующих обновления
        for node in no_update_needed_nodes:
            if node not in result_dict:
                result_dict[node] = {
                    "tp": node,
                    "status": "NO_UPDATE_NEEDED",
                    "message": f"Обновление узла {node} не требуется",
                    "type": None,
                    "cv": None,
                    "pv": None,
                    "online": None,
                    "ip": None,
                    "ut": None,
                    "local patches": None,
                }

        self.node_result = result_dict
        self._categorize_nodes()
        return self.node_result

    def _parse_output(
        self, output: str
    ) -> Tuple[Dict[str, Dict[str, Optional[str]]], Set[str], Set[str], Set[str]]:
        """Парсим весь вывод stdout из JAR
        детально разбираем и формируем списки"""
        if not output:
            return {}, set(), set(), set()

        devices_dict: Dict[str, Dict[str, Optional[str]]] = {}
        unavailable_nodes: Set[str] = set()
        success_nodes: Set[str] = set()
        no_update_needed_nodes: Set[str] = set()

        try:
            for line in output.splitlines():
                line = line.strip()

                # Обработка успешных узлов
                if "успешно запланировано" in line:
                    for part in line.split():
                        if (
                            part.replace(".", "").isdigit()
                            and len(part.split(".")) >= 3
                        ):
                            success_nodes.add(part)
                            devices_dict[part] = {
                                "tp": part,
                                "status": "SUCCESS",
                                "message": f"Обновление узла {part} успешно запланировано",
                                "type": None,
                                "cv": None,
                                "pv": None,
                                "online": None,
                                "ip": None,
                                "ut": None,
                                "local patches": None,
                            }

                # Обработка недоступных узлов
                elif "недоступен" in line:
                    for part in line.split():
                        if (
                            part.replace(".", "").isdigit()
                            and len(part.split(".")) >= 3
                        ):
                            unavailable_nodes.add(part)
                            devices_dict[part] = {
                                "tp": part,
                                "status": "UNAVAILABLE",
                                "message": f"Узел {part} недоступен",
                                "type": None,
                                "cv": None,
                                "pv": None,
                                "online": None,
                                "ip": None,
                                "ut": None,
                                "local patches": None,
                            }

                # Обработка узлов, не требующих обновления
                elif "не требуется" in line:
                    for part in line.split():
                        if (
                            part.replace(".", "").isdigit()
                            and len(part.split(".")) >= 3
                        ):
                            no_update_needed_nodes.add(part)
                            devices_dict[part] = {
                                "tp": part,
                                "status": "NO_UPDATE_NEEDED",
                                "message": f"Обновление узла {part} не требуется",
                                "type": None,
                                "cv": None,
                                "pv": None,
                                "online": None,
                                "ip": None,
                                "ut": None,
                                "local patches": None,
                            }

            for line in output.splitlines():
                line = line.strip()
                if not line or line.startswith(("Current client version:", "-")):
                    continue

                device: Dict[str, Optional[str]] = {}
                device_key = None
                tp_value = None

                # Разбор по символу ";"
                for pair in line.split(";"):
                    pair = pair.strip()
                    if "=" in pair:
                        # Поиск пар "key=value"
                        key, value = pair.split("=", 1)
                        key = key.strip()
                        value = (
                            value.strip() if value.strip().lower() != "null" else None
                        )
                        device[key] = value

                        # Приоритет IP над tp для ключа устройства
                        if key == "ip" and value:
                            device_key = value
                        elif key == "tp" and value:
                            tp_value = value
                            if not device_key:  # Используем tp только если нет IP
                                device_key = value

                # Используем tp если IP не найден
                if not device_key and tp_value:
                    device_key = tp_value

                if device and device_key:
                    devices_dict[device_key] = device

                    # Проверка на недоступность узла
                    status = (device.get("status") or "").upper()
                    online = (device.get("online") or "").upper()

                    if (
                        status == "UNAVAILABLE" or online == "FALSE" or online == "NO"
                    ):  #
                        unavailable_nodes.add(device_key)

        except Exception as e:
            logging.error(f"Ошибка при парсинге вывода: {str(e)}")
            return {}, set(), set(), set()
        return devices_dict, unavailable_nodes, success_nodes, no_update_needed_nodes

    def _categorize_nodes(self):
        """Категоризация узлов по статусам
        в зависимости от статуса работаем с узлом дальше"""
        self.work_tp = []
        self.error_tp = []
        self.update_tp = []
        self.ccm_tp = []
        self.unzip_tp = []
        self.no_update_needed_tp = []

        for node_id, node_data in self.node_result.items():
            status = (node_data.get("status") or "").upper()
            node_type = (node_data.get("type") or "").strip()
            ip_node = (node_data.get("ip") or "").strip()
            tp = node_data.get("tp") or node_id
            version = (node_data.get("cv") or "").strip()
            if tp.split(".")[3] == "0":
                tp = tp.split(".")[2]
            else:
                tp = f"{tp.split('.')[2]}.{tp.split('.')[3]}"

            # Формируем строку для списка (tp-type)
            list_entry = f"{tp}"
            if node_type:
                list_entry += f"-{node_type}"
            if ip_node:
                list_entry += f"-{ip_node}"
            if version:
                list_entry += f"-{version}"

            # Категоризация по статусам
            if status == "IN_WORK":
                self.work_tp.append(list_entry)
            elif status in ("UPGRADE_ERROR_WITH_DOWNGRADE", "FAST_REVERT"):
                self.error_tp.append(list_entry)
            elif status in (
                "UPGRADE_PLANING",
                "UPGRADE_DOWNLOADING",
                "UPGRADE_WAIT_FOR_REBOOT",
                "CHECK_PERMISSIONS",
                "BACKUP",
                "APPLY_PATCH",
                "TEST_START",
            ):
                self.update_tp.append(list_entry)
            elif status == "CCM_UPDATE_RESTART":
                self.ccm_tp.append(list_entry)
            elif status == "UNZIP_FILES":
                self.unzip_tp.append(list_entry)
            elif status == "NO_UPDATE_NEEDED":
                self.no_update_needed_tp.append(list_entry)

    def save_status_lists(self, prefix: str = ""):
        """Сохраняет все списки статусов в отдельные файлы
        Для дальнейшей работой с ними"""
        lists_to_save = {
            "work_tp": self.work_tp,
            "error_tp": self.error_tp,
            "update_tp": self.update_tp,
            "ccm_tp": self.ccm_tp,
            "unzip_tp": self.unzip_tp,
            "no_update_needed_tp": self.no_update_needed_tp,
        }

        # Удаляем старые файлы
        for list_name in lists_to_save:
            filename = f"{prefix}{list_name}.txt" if prefix else f"{list_name}.txt"
            filepath = self.config_dir / filename
            if filepath.is_file():
                filepath.unlink()
        # Пишем новые файлы
        for list_name, data in lists_to_save.items():
            if not data:  # Пустой список не формируем
                continue
            filename = f"{prefix}{list_name}.txt" if prefix else f"{list_name}.txt"
            filepath = self.config_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(data))
            logging.info(f"Список {list_name} сохранен в {filepath}")

    # Функция получить состояние всех узлов с Centrum
    def get_all_nodes(
        self, max_retries: int = 3
    ) -> Dict[str, Dict[str, Optional[str]]]:
        return self._execute_command(["-ch", self.centrum_host, "--all"], max_retries)

    # Получить состояние узлов перечисленных в файле
    def get_nodes_from_file(
        self, filename: str = "server.txt"
    ) -> Dict[str, Dict[str, Optional[str]]]:
        filepath = self.config_dir / filename
        return self._execute_command(["-ch", self.centrum_host, "-f", str(filepath)], 1)

    # Запустить обновление серверов список которых перечислены в файлеб без бэкапа базы по умолчанию
    def update_servers(
        self,
        version_sv: str,
        filename: str = "server.txt",
        no_backup: bool = True,
    ) -> Dict[str, Dict[str, Optional[str]]]:
        filepath = self.config_dir / filename
        args = ["-ch", self.centrum_host, "-f", str(filepath), "-sv", version_sv]
        if no_backup:
            args.append("-nb")
        return self._execute_command(args, 1)

    # Запустить обновление касс по типу, список которых перечислены в файле, разом обновить кассы всех типов нельзя
    def update_cash_devices(
        self,
        cash_type: str,
        version: str,
        filename: str = "server_cash.txt",
        no_backup: bool = True,
        auto_restart: bool = True,
    ) -> Dict[str, Dict[str, Optional[str]]]:
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

    # Записать ответ от Jar в файл,
    def save_node_result(self, filename: str = "node_result.json"):
        """Сохранить результат в файл"""
        filepath = self.config_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.node_result, f, ensure_ascii=False, indent=2)
        logging.info(f"Результат сохранен в {filepath}")


if __name__ == "__main__":
    try:
        configurator = ConfiguratorTool(
            centrum_host="10.21.11.45",
            config_dir="C:\\Users\\iakushin.n\\Documents\\GitHub\\Python\\updaterJar",
        )

        # Тестирование
        # Получаем все узлы, пишем всё на экран и пишем node_result.json по умолчанию
        # all_nodes = configurator.get_all_nodes(max_retries=3)
        # print("Все узлы:")
        # for key, data in all_nodes.items():
        #     print(f"{key}: {data}")
        # configurator.save_node_result()
        # configurator.save_status_lists()

        # Получаем все узлы из файла, пишем всё на экран и пишем результат в server.json
        get_nodes_from_file = configurator.get_nodes_from_file()
        print("Узлы из файла:")
        for key, data in get_nodes_from_file.items():
            print(f"{key}: {data}")
        configurator.save_node_result(filename="server.json")
        configurator.save_status_lists(prefix="server_")

        # Запуск обновления серверов, просто выводим результат
        # update_servers = configurator.update_servers(version_sv="10.4.15.1")
        # print("Результат обновления серверов:")
        # for key, data in update_servers.items():
        #     print(f"{key}: {data}")
        # configurator.save_node_result(filename="server_update.json")
        # configurator.save_status_lists(prefix="server_update_")

        # Запуск обновления касс, просто выводим результат
        # cash_update = configurator.update_cash_devices(
        #     cash_type="POS", version="10.4.14.14"
        # )
        # print("\nРезультат обновления касс:")
        # for key, data in cash_update.items():
        #     print(f"{key}: {data}")
        # configurator.save_node_result(filename="server_cash_update.json")
        # configurator.save_status_lists(prefix="server_cash_update_")

    except Exception as e:
        logging.error(f"Ошибка какая то: {str(e)}")
