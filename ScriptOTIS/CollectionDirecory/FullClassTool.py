import time
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Union
import logging
import json
import os

from requests import patch

# ==================== КОНФИГУРАЦИОННЫЕ ПАРАМЕТРЫ ====================
# Основные настройки
CENTRUM_HOST = "10.21.11.45"
CURRENT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = CURRENT_DIR / "updaterJar"
JAR_NAME = "ConfiguratorCmdClient-1.5.1.jar"
FILES_DIR = CURRENT_DIR / "Files"
PLINK_DIR = CURRENT_DIR / "Plink"
FILES_DIR.mkdir(exist_ok=True)


SSH_USER = "tc"
SSH_PASSWORD = "JnbcHekbn123"
PLINK_PATH = PLINK_DIR / "plink.exe"
PING_TIMEOUT = 1000  # мс
PLINK_TIMEOUT = 300  # секунды (5 минут)

# Настройки обновления
TARGET_VERSION = "10.4.15.11"
BATCH_SIZE = 2
MAX_ITERATIONS = 2  # None для неограниченного количества
MAX_RETRIES_DEFAULT = 3
MAX_RETRIES_SINGLE = 1

# Таймауты и интервалы
WAIT_BETWEEN_RETRIES = 2  # секунды
STATUS_CHECK_INTERVAL = 600  # 10 минут
SERVICE_RESTART_DELAY = 2  # секунды между перезапусками служб

# Имена файлов
FILES = {
    "server_list": FILES_DIR / "server.txt",
    "server_cash_list": FILES_DIR / "server_cash.txt",
    "node_result": FILES_DIR / "node_result.json",
    "ccm_restart_commands": PLINK_DIR / "ccm_restart",
    "unzip_restart_commands": PLINK_DIR / "unzip_restart",
    # Файлы статусов (с префиксом)
    "status_prefix": "server_",
    "work_tp": FILES_DIR / "work_tp.txt",
    "error_tp": FILES_DIR / "error_tp.txt",
    "update_tp": FILES_DIR / "update_tp.txt",
    "ccm_tp": FILES_DIR / "ccm_tp.txt",
    "unzip_tp": FILES_DIR / "unzip_tp.txt",
    "no_update_needed_tp": FILES_DIR / "no_update_needed_tp.txt",
}

# Настройки логирования
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_LEVEL = logging.INFO

# Настройки обновления по умолчанию
DEFAULT_NO_BACKUP = True
DEFAULT_AUTO_RESTART = True
# ====================================================================

# Настройка логирования
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)


class UnifiedServerUpdater:
    """Унифицированный класс для работы с JAR-инструментом конфигурации и пошагового обновления серверов"""

    def __init__(
        self,
        centrum_host: str = CENTRUM_HOST,
        config_dir: Path = CONFIG_DIR,
        jar_name: str = JAR_NAME,
        target_version: str = TARGET_VERSION,
        batch_size: int = BATCH_SIZE,
        max_iterations: Optional[int] = MAX_ITERATIONS,
    ):
        # Параметры из ConfiguratorTool
        self.centrum_host = centrum_host
        print(self.centrum_host)
        self.config_dir = Path(config_dir)
        print(self.config_dir)
        self.jar_path = self.config_dir / jar_name
        self.node_result: Dict[str, Dict[str, Optional[str]]] = {}
        self.work_tp: List[str] = []
        self.error_tp: List[str] = []
        self.update_tp: List[str] = []
        self.ccm_tp: List[str] = []
        self.unzip_tp: List[str] = []
        self.no_update_needed_tp: List[str] = []

        # Параметры из ServerUpdater
        self.target_version = target_version
        self.batch_size = batch_size
        self.max_iterations = max_iterations
        self.current_iteration = 0
        self.updated_servers: Set[str] = set()

        if not self.jar_path.exists():
            raise FileNotFoundError(f"JAR файл не найден: {self.jar_path}")

    # ==================== Методы из ConfiguratorTool ====================

    def _execute_command(
        self, args: List[str], max_retries: int = MAX_RETRIES_SINGLE
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Выполняет команду с повторами для недоступных узлов"""
        result_dict: Dict[str, Dict[str, Optional[str]]] = {}
        unavailable_nodes: Set[str] = set()
        success_nodes: Set[str] = set()
        no_update_needed_nodes: Set[str] = set()
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
                    time.sleep(WAIT_BETWEEN_RETRIES)

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
        """Парсим весь вывод stdout из JAR"""
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
                        key, value = pair.split("=", 1)
                        key = key.strip()
                        value = (
                            value.strip() if value.strip().lower() != "null" else None
                        )
                        device[key] = value

                        if key == "ip" and value:
                            device_key = value
                        elif key == "tp" and value:
                            tp_value = value
                            if not device_key:
                                device_key = value

                if not device_key and tp_value:
                    device_key = tp_value

                if device and device_key:
                    devices_dict[device_key] = device

                    status = (device.get("status") or "").upper()
                    online = (device.get("online") or "").upper()

                    if status == "UNAVAILABLE" or online == "FALSE" or online == "NO":
                        unavailable_nodes.add(device_key)

        except Exception as e:
            logging.error(f"Ошибка при парсинге вывода: {str(e)}")
            return {}, set(), set(), set()
        return devices_dict, unavailable_nodes, success_nodes, no_update_needed_nodes

    def _categorize_nodes(self):
        """Категоризация узлов по статусам"""
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

            list_entry = f"{tp}"
            if node_type:
                list_entry += f"-{node_type}"
            if ip_node:
                list_entry += f"-{ip_node}"
            if version:
                list_entry += f"-{version}"

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
        """Сохраняет все списки статусов в отдельные файлы"""
        lists_to_save = {
            FILES["work_tp"]: self.work_tp,
            FILES["error_tp"]: self.error_tp,
            FILES["update_tp"]: self.update_tp,
            FILES["ccm_tp"]: self.ccm_tp,
            FILES["unzip_tp"]: self.unzip_tp,
            FILES["no_update_needed_tp"]: self.no_update_needed_tp,
        }

        # Удаляем старые файлы
        for filename in lists_to_save:
            filepath = (self.config_dir / filename).with_stem(prefix + filename.stem)
            if filepath.is_file():
                filepath.unlink()

        # Пишем новые файлы
        for filename, data in lists_to_save.items():
            if not data:
                continue
            filepath = (self.config_dir / filename).with_stem(prefix + filename.stem)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(data))
            logging.info(f"Список сохранен в {filepath}")

    def get_all_nodes(
        self, max_retries: int = MAX_RETRIES_DEFAULT
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Получить состояние всех узлов с Centrum"""
        return self._execute_command(["-ch", self.centrum_host, "--all"], max_retries)

    def get_nodes_from_file(
        self, filename: Union[Path, None] = None
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Получить состояние узлов перечисленных в файле"""
        if filename is None:
            filename = Path(FILES["server_list"])
        filepath: Path = self.config_dir / filename  # явно указываем тип Path
        print(filepath)
        return self._execute_command(
            [
                "-ch",
                self.centrum_host,
                "-f",
                str(filepath),
            ],  # преобразуем Path в str при использовании
            MAX_RETRIES_SINGLE,
        )

    def update_servers(
        self,
        version_sv: str = None,
        filename: Union[Path, None] = None,
        no_backup: bool = DEFAULT_NO_BACKUP,
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Запустить обновление серверов список которых перечислены в файле"""
        if version_sv is None:
            version_sv = self.target_version
        if filename is None:
            filename = Path(FILES["server_list"])
        filepath = self.config_dir / filename
        args = ["-ch", self.centrum_host, "-f", str(filepath), "-sv", version_sv]
        if no_backup:
            args.append("-nb")
        return self._execute_command(args, MAX_RETRIES_SINGLE)

    def update_cash_devices(
        self,
        cash_type: str,
        version: str = None,
        filename: Union[Path, None] = None,
        no_backup: bool = DEFAULT_NO_BACKUP,
        auto_restart: bool = DEFAULT_AUTO_RESTART,
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Запустить обновление касс по типу"""
        if version is None:
            version = self.target_version
        if filename is None:
            filename = Path(FILES["server_cash_list"])
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
        return self._execute_command(args, MAX_RETRIES_SINGLE)

    def save_node_result(self, filename: Union[Path, None] = None):
        """Сохранить результат в файл"""
        if filename is None:
            filename = Path(FILES["node_result"])
        filepath = self.config_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.node_result, f, ensure_ascii=False, indent=2)
        logging.info(f"Результат сохранен в {filepath}")

    # ==================== Методы из ServerUpdater ====================

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
        self, servers: List[Dict], filename: Union[Path, None] = None
    ) -> None:
        """Создает файл server.txt с индексами серверов"""
        if filename is None:
            filename = Path(FILES["server_list"])
        filepath = self.config_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for server in servers:
                f.write(f"{server['tp_index']}\n")

        logging.info(f"Создан файл {filename} с {len(servers)} серверами")

    def check_file_exists(self, filename: str) -> bool:
        """Проверяет существование файла"""
        filepath = self.config_dir / filename
        return filepath.exists() and filepath.stat().st_size > 0

    def read_file_lines(self, filename: str) -> List[str]:
        """Читает строки из файла"""
        filepath = self.config_dir / filename
        if not filepath.exists():
            return []

        with open(filepath, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines() if line.strip()]

    def restart_service_with_plink(self, servers: List[str], restart_file: str) -> bool:
        """Перезапускает службу на серверах используя PLINK"""
        try:
            restart_filepath = self.config_dir / restart_file
            if not restart_filepath.exists():
                logging.error(f"Файл команд {restart_file} не найден")
                return False

            for server in servers:
                logging.info(f"Перезапуск службы на сервере {server}")
                try:
                    # Здесь должна быть логика выполнения команд из файла restart_file
                    # Пример: subprocess.run(["plink.exe", "-batch", server, "command"], check=True)
                    time.sleep(SERVICE_RESTART_DELAY)
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
        current_nodes = self.get_nodes_from_file()

        original_indices = {server["tp_index"] for server in original_servers}
        work_indices = set()

        for server_info in work_servers:
            tp_index = server_info.split("-")[0]
            work_indices.add(tp_index)

        if original_indices != work_indices:
            logging.error(
                f"Несоответствие серверов: ожидалось {original_indices}, получено {work_indices}"
            )
            return False, []

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
            if self.max_iterations and self.current_iteration >= self.max_iterations:
                logging.info(
                    "Достигнуто максимальное количество итераций. Обновление завершено успешно."
                )
                return True

            all_nodes = self.get_all_nodes(max_retries=MAX_RETRIES_DEFAULT)
            if "error" in all_nodes:
                logging.error(f"Ошибка получения узлов: {all_nodes['error']}")
                return False

            servers_to_update = self.get_retail_servers_to_update(all_nodes)

            if not servers_to_update:
                logging.info("Все серверы RETAIL уже обновлены до целевой версии")
                return True

            current_batch = servers_to_update[: self.batch_size]
            self.current_iteration += 1

            logging.info(
                f"Итерация {self.current_iteration}: обновляем {len(current_batch)} серверов"
            )

            self.create_server_file(current_batch)

            logging.info(f"Запуск обновления до версии {self.target_version}")
            update_result = self.update_servers(version_sv=self.target_version)

            if "error" in update_result:
                logging.error(f"Ошибка запуска обновления: {update_result['error']}")
                return False

            while True:
                logging.info(
                    f"Ожидание {STATUS_CHECK_INTERVAL // 60} минут перед проверкой статуса..."
                )
                time.sleep(STATUS_CHECK_INTERVAL)

                self.get_nodes_from_file()
                self.save_status_lists(prefix=FILES["status_prefix"])

                if self.check_file_exists(FILES["status_prefix"] + FILES["error_tp"]):
                    error_servers = self.read_file_lines(
                        FILES["status_prefix"] + FILES["error_tp"]
                    )
                    logging.error(
                        f"Обнаружены ошибки обновления на серверах: {error_servers}"
                    )
                    return False

                if self.check_file_exists(FILES["status_prefix"] + FILES["update_tp"]):
                    update_servers = self.read_file_lines(
                        FILES["status_prefix"] + FILES["update_tp"]
                    )
                    logging.info(f"Серверы все еще обновляются: {update_servers}")
                    continue

                if self.check_file_exists(FILES["status_prefix"] + FILES["ccm_tp"]):
                    ccm_servers = self.read_file_lines(
                        FILES["status_prefix"] + FILES["ccm_tp"]
                    )
                    logging.info(f"Перезапуск CCM на серверах: {ccm_servers}")

                    if not self.restart_service_with_plink(
                        ccm_servers, FILES["ccm_restart_commands"]
                    ):
                        logging.error("Ошибка перезапуска CCM")
                        return False
                    continue

                if self.check_file_exists(FILES["status_prefix"] + FILES["unzip_tp"]):
                    unzip_servers = self.read_file_lines(
                        FILES["status_prefix"] + FILES["unzip_tp"]
                    )
                    logging.info(f"Перезапуск unzip на серверах: {unzip_servers}")

                    if not self.restart_service_with_plink(
                        unzip_servers, FILES["unzip_restart_commands"]
                    ):
                        logging.error("Ошибка перезапуска unzip")
                        return False
                    continue

                if self.check_file_exists(FILES["status_prefix"] + FILES["work_tp"]):
                    work_servers = self.read_file_lines(
                        FILES["status_prefix"] + FILES["work_tp"]
                    )
                    logging.info(f"Серверы в работе: {work_servers}")

                    servers_match, incorrect_versions = (
                        self.compare_servers_and_versions(work_servers, current_batch)
                    )

                    if not servers_match:
                        logging.error("Несоответствие серверов или версий")
                        return False

                    if not incorrect_versions:
                        logging.info(f"Батч {self.current_iteration} успешно обновлен")
                        for server in current_batch:
                            self.updated_servers.add(server["ip"])
                        break
                    else:
                        logging.error(
                            f"Серверы с неправильными версиями: {incorrect_versions}"
                        )
                        return False
                else:
                    continue


# Пример использования
if __name__ == "__main__":

    try:
        # Создаем унифицированный обновлятель
        updater = UnifiedServerUpdater()

        # Получить статус всех узлов
        all_nodes = updater.get_all_nodes()
        if all_nodes:
            logging.info("Все серверы успешно собраны!")
        else:
            logging.error("Сбор завершилось с ошибками")

        # Запускаем обновление
        # success = updater.update_servers_batch()

        # if success:
        #     logging.info("Все серверы успешно обновлены!")
        # else:
        #     logging.error("Обновление завершилось с ошибками")

    except Exception as e:
        logging.error(f"Критическая ошибка: {str(e)}")
