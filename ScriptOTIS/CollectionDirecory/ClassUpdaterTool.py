import time
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
import logging
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


class ServerUpdater:
    """Класс для пошагового обновления серверов с контролем нагрузки"""

    def __init__(
        self,
        configurator: ConfiguratorTool,
        target_version: str = "10.4.15.11",
        batch_size: int = 5,
        max_iterations: Optional[int] = None,
    ):
        self.configurator = configurator
        self.target_version = target_version
        self.batch_size = batch_size
        self.max_iterations = max_iterations
        self.current_iteration = 0
        self.updated_servers: Set[str] = set()

    def extract_tp_index(self, tp: str) -> str:
        """Извлекает индекс из tp формата '1.0.индекс.0'"""
        parts = tp.split(".")
        if len(parts) >= 3:
            if parts[3] == "0":
                return parts[2]
            else:
                return f"{parts[2]}.{parts[3]}"
        return tp

    def get_retail_servers_to_update(self, all_nodes: Dict) -> List[Dict]:
        """Получает список серверов RETAIL, которые нужно обновить"""
        servers_to_update = []

        for ip, node_data in all_nodes.items():
            if (
                node_data.get("type") == "RETAIL"
                and node_data.get("cv") != self.target_version
                and ip not in self.updated_servers
            ):
                servers_to_update.append(
                    {
                        "ip": ip,
                        "tp": node_data.get("tp"),
                        "current_version": node_data.get("cv"),
                        "tp_index": self.extract_tp_index(node_data.get("tp", "")),
                    }
                )

        return servers_to_update

    def create_server_file(
        self, servers: List[Dict], filename: str = "server.txt"
    ) -> None:
        """Создает файл server.txt с индексами серверов"""
        filepath = self.configurator.config_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for server in servers:
                f.write(f"{server['tp_index']}\n")

        logging.info(f"Создан файл {filename} с {len(servers)} серверами")

    def check_file_exists(self, filename: str) -> bool:
        """Проверяет существование файла"""
        filepath = self.configurator.config_dir / filename
        return filepath.exists() and filepath.stat().st_size > 0

    def read_file_lines(self, filename: str) -> List[str]:
        """Читает строки из файла"""
        filepath = self.configurator.config_dir / filename
        if not filepath.exists():
            return []

        with open(filepath, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines() if line.strip()]

    def restart_service_with_plink(self, servers: List[str], restart_file: str) -> bool:
        """Перезапускает службу на серверах используя PLINK"""
        try:
            restart_filepath = self.configurator.config_dir / restart_file
            if not restart_filepath.exists():
                logging.error(f"Файл команд {restart_file} не найден")
                return False

            for server in servers:
                logging.info(f"Перезапуск службы на сервере {server}")
                try:
                    # Здесь должна быть логика выполнения команд из файла restart_file
                    # Пример: subprocess.run(["plink.exe", "-batch", server, "command"], check=True)
                    time.sleep(2)  # Имитация выполнения
                    logging.info(f"Служба на сервере {server} перезапущена")
                except subprocess.CalledProcessError as e:
                    logging.error(f"Ошибка перезапуска службы на {server}: {e}")
                    return False

            return True
        except Exception as e:
            logging.error(f"Ошибка при перезапуске служб: {e}")
            return False

    def compare_servers_and_versions(
        self, work_servers: List[str], original_servers: List[Dict]
    ) -> tuple[bool, List[str]]:
        """Сравнивает серверы из work_tp с исходными и проверяет версии"""
        # Получаем актуальные данные серверов
        current_nodes = self.configurator.get_nodes_from_file()

        # Сравниваем количество и индексы
        original_indices = {server["tp_index"] for server in original_servers}
        work_indices = set()

        for server_info in work_servers:
            # Извлекаем индекс из строки формата "индекс-тип-ip-версия"
            tp_index = server_info.split("-")[0]
            work_indices.add(tp_index)

        if original_indices != work_indices:
            logging.error(
                f"Несоответствие серверов: ожидалось {original_indices}, получено {work_indices}"
            )
            return False, []

        # Проверяем версии
        incorrect_versions = []
        for server_info in work_servers:
            parts = server_info.split("-")
            if len(parts) >= 4:
                server_version = parts[3]
                if server_version != self.target_version:
                    incorrect_versions.append(server_info)

        if incorrect_versions:
            logging.error(f"Серверы с неправильными версиями: {incorrect_versions}")
            return False, incorrect_versions

        return True, []

    def update_servers_batch(self) -> bool:
        """Основной метод обновления серверов по батчам"""
        logging.info("Начинаем пошаговое обновление серверов")

        while True:
            # Шаг 0: Проверка количества итераций
            if self.max_iterations and self.current_iteration >= self.max_iterations:
                logging.info(
                    "Достигнуто максимальное количество итераций. Обновление завершено успешно."
                )
                return True

            # Получаем все узлы
            all_nodes = self.configurator.get_all_nodes(max_retries=3)
            if "error" in all_nodes:
                logging.error(f"Ошибка получения узлов: {all_nodes['error']}")
                return False

            # Шаг 1: Получаем серверы для обновления
            servers_to_update = self.get_retail_servers_to_update(all_nodes)

            if not servers_to_update:
                logging.info("Все серверы RETAIL уже обновлены до целевой версии")
                return True

            # Берем следующий batch
            current_batch = servers_to_update[: self.batch_size]
            self.current_iteration += 1

            logging.info(
                f"Итерация {self.current_iteration}: обновляем {len(current_batch)} серверов"
            )

            # Создаем файл server.txt
            self.create_server_file(current_batch)

            # Шаг 2: Запуск обновления
            logging.info(f"Запуск обновления до версии {self.target_version}")
            update_result = self.configurator.update_servers(
                version_sv=self.target_version
            )

            if "error" in update_result:
                logging.error(f"Ошибка запуска обновления: {update_result['error']}")
                return False

            # Главный цикл ожидания завершения обновления
            while True:
                # Шаг 3: Ждем 10 минут
                logging.info("Ожидание 10 минут перед проверкой статуса...")
                time.sleep(600)  # 10 минут

                # Проверяем статусы
                self.configurator.get_nodes_from_file()
                self.configurator.save_status_lists(prefix="server_")

                # Шаг 4: Проверка ошибок
                if self.check_file_exists("server_error_tp.txt"):
                    error_servers = self.read_file_lines("server_error_tp.txt")
                    logging.error(
                        f"Обнаружены ошибки обновления на серверах: {error_servers}"
                    )
                    return False

                # Шаг 5: Проверка процесса обновления
                if self.check_file_exists("server_update_tp.txt"):
                    update_servers = self.read_file_lines("server_update_tp.txt")
                    logging.info(f"Серверы все еще обновляются: {update_servers}")
                    continue  # Возвращаемся к шагу 3

                # Шаг 6: Проверка CCM
                if self.check_file_exists("server_ccm_tp.txt"):
                    ccm_servers = self.read_file_lines("server_ccm_tp.txt")
                    logging.info(f"Перезапуск CCM на серверах: {ccm_servers}")

                    # Шаг 7: Перезапуск CCM
                    if not self.restart_service_with_plink(ccm_servers, "ccm_restart"):
                        logging.error("Ошибка перезапуска CCM")
                        return False
                    continue  # Возвращаемся к шагу 3

                # Шаг 8: Проверка unzip
                if self.check_file_exists("server_unzip_tp.txt"):
                    unzip_servers = self.read_file_lines("server_unzip_tp.txt")
                    logging.info(f"Перезапуск unzip на серверах: {unzip_servers}")

                    # Шаг 9: Перезапуск unzip
                    if not self.restart_service_with_plink(
                        unzip_servers, "unzip_restart"
                    ):
                        logging.error("Ошибка перезапуска unzip")
                        return False
                    continue  # Возвращаемся к шагу 3

                # Шаг 10: Проверка work_tp
                if self.check_file_exists("server_work_tp.txt"):
                    work_servers = self.read_file_lines("server_work_tp.txt")
                    logging.info(f"Серверы в работе: {work_servers}")

                    # Шаг 11: Сравнение серверов
                    servers_match, incorrect_versions = (
                        self.compare_servers_and_versions(work_servers, current_batch)
                    )

                    if not servers_match:
                        logging.error("Несоответствие серверов или версий")
                        return False

                    # Шаг 12: Проверка версий
                    if not incorrect_versions:
                        logging.info(f"Батч {self.current_iteration} успешно обновлен")
                        # Добавляем обновленные серверы в множество
                        for server in current_batch:
                            self.updated_servers.add(server["ip"])
                        break  # Переходим к следующему батчу (шаг 0)
                    else:
                        logging.error(
                            f"Серверы с неправильными версиями: {incorrect_versions}"
                        )
                        return False
                else:
                    # Нет файла work_tp, возвращаемся к шагу 3
                    continue


# Пример использования
if __name__ == "__main__":
    try:
        configurator = ConfiguratorTool(
            centrum_host="10.21.11.45",
            config_dir="C:\\Users\\iakushin.n\\Documents\\GitHub\\Python\\updaterJar",
        )

        # Создаем обновлятель с целевой версией и размером батча
        updater = ServerUpdater(
            configurator=configurator,
            target_version="10.4.15.11",
            batch_size=5,
            max_iterations=10,  # Опционально ограничиваем количество итераций
        )

        # Запускаем обновление
        success = updater.update_servers_batch()

        if success:
            logging.info("Все серверы успешно обновлены!")
        else:
            logging.error("Обновление завершилось с ошибками")

    except Exception as e:
        logging.error(f"Критическая ошибка: {str(e)}")
