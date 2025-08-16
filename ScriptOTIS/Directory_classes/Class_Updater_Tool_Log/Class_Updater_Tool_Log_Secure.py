import time
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Union
import logging
import json
import os
import keyring
from getpass import getpass

# ==================== КОНФИГУРАЦИОННЫЕ ПАРАМЕТРЫ ====================
# Основные настройки
CENTRUM_HOST = "10.21.11.45"
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(CURRENT_DIR, "updaterJar")
JAR_NAME = "ConfiguratorCmdClient-1.5.1.jar"
FILES_DIR = os.path.join(CURRENT_DIR, "Files")
PLINK_DIR = os.path.join(CURRENT_DIR, "Plink")
SSH_USER = "otis"
PLINK_PATH = os.path.join(PLINK_DIR, "plink.exe")

# Настройки обновления
TARGET_VERSION = "10.4.15.15"
part_server_SIZE = 5  # Сколько серверов за раз
MAX_ITERATIONS = None  # Количество итераций. None для неограниченного количества
MAX_RETRIES_DEFAULT = 3
MAX_RETRIES_SINGLE = 1
DEFAULT_NO_BACKUP = True  #
DEFAULT_AUTO_RESTART = True  #
PRE_UPDATE_WORK = True  # Флаг для предварительного скрипта перед обновлением
POST_UPDATE_WORK = True  # Флаг для скрипта после обновления


# Таймауты и интервалы
WAIT_BETWEEN_RETRIES = 2  # секунды
STATUS_CHECK_INTERVAL = 300  # 10 минут
PING_TIMEOUT = 2000  # мс
PLINK_TIMEOUT = 300  # секунды (5 минут)
PRE_UPDATE_TIMEOUT = 60  # Максимальное время на выполнение скрипта перед обновлением
POST_UPDATE_TIMEOUT = 60  # Максимальное время на выполнение скрипта после обновления

# Имена файлов
FILES = {
    "server_list": "server.txt",
    "server_cash_list": "server_cash.txt",
    "node_result": os.path.join(FILES_DIR, "node_result.json"),
    "ccm_restart_commands": os.path.join(PLINK_DIR, "ccm_commands.txt"),
    "unzip_restart_commands": os.path.join(PLINK_DIR, "unzip_commands.txt"),
    "pre_update_commands": os.path.join(PLINK_DIR, "pre_update_commands.txt"),
    "post_update_commands": os.path.join(PLINK_DIR, "post_update_commands.txt"),
    # Файлы статусов (с префиксом)
    "status_prefix": "server_",
    "work_tp": "work_tp.txt",
    "error_tp": "error_tp.txt",
    "update_tp": "update_tp.txt",
    "ccm_tp": "ccm_tp.txt",
    "unzip_tp": "unzip_tp.txt",
    "no_update_needed_tp": "no_update_needed_tp.txt",
    "unavailable_tp": "unavailable_tp.txt",
}
# ====================================================================

# Настройка логирования
log_format = "%(asctime)s - %(levelname)s - %(message)s"
log_level = logging.INFO

# Создаем логгер
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

# Создаем обработчик для вывода в консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(log_level)
console_handler.setFormatter(logging.Formatter(log_format))

# Создаем обработчик для записи в файл
file_handler = logging.FileHandler(
    filename=os.path.join(CONFIG_DIR, "updater.log"),
    encoding="utf-8",
    mode="w",  # 'a' - дописывать, 'w' - перезаписывать
)
file_handler.setLevel(log_level)
file_handler.setFormatter(logging.Formatter(log_format))

# Добавляем оба обработчика к логгеру
logger.addHandler(console_handler)
logger.addHandler(file_handler)


class UnifiedServerUpdater:
    """Унифицированный класс для работы с JAR-инструментом конфигурации и пошаговым обновлением серверов"""

    def __init__(
        self,
        centrum_host: str = CENTRUM_HOST,
        config_dir: str = CONFIG_DIR,
        jar_name: str = JAR_NAME,
        target_version: str = TARGET_VERSION,
        part_server_size: int = part_server_SIZE,
        max_iterations: Optional[int] = MAX_ITERATIONS,
        service_name: str = "UnifiedServerUpdater",
    ):
        logger.debug("Инициализация UnifiedServerUpdater")
        logger.debug(
            f"Параметры: centrum_host={centrum_host}, config_dir={config_dir}, "
            f"jar_name={jar_name}, target_version={target_version}, "
            f"part_server_size={part_server_size}, max_iterations={max_iterations}"
        )

        # Параметры из ConfiguratorTool
        self.centrum_host = centrum_host
        self.config_dir = Path(config_dir)
        self.jar_path = self.config_dir / jar_name
        self.node_result: Dict[str, Dict[str, Optional[str]]] = {}
        self.work_tp: List[str] = []
        self.error_tp: List[str] = []
        self.update_tp: List[str] = []
        self.ccm_tp: List[str] = []
        self.unzip_tp: List[str] = []
        self.no_update_needed_tp: List[str] = []
        self.unavailable: List[str] = []

        # Параметры из ServerUpdater
        self.target_version = target_version
        self.part_server_size = part_server_size
        self.max_iterations = max_iterations
        self.current_iteration = 0
        self.updated_servers: Set[str] = set()

        # Параметры из ServiceRestarter
        self.user = SSH_USER
        self.plink_path = Path(PLINK_PATH)
        self.service_name = service_name
        self.password = self._init_password()

        logging.debug(f"Конфигурация: plink_path={self.plink_path}, user={self.user}")

        if not self.jar_path.exists():
            error_msg = f"JAR файл не найден: {self.jar_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        logger.info("UnifiedServerUpdater успешно инициализирован")

    def _init_password(self) -> str:
        """Инициализирует пароль, проверяя keyring или запрашивая у пользователя"""
        try:
            password = keyring.get_password(self.service_name, self.user)
            # Если пароль есть в keyring, проверяем его валидность
            if password is not None:
                if self._test_password(password):  # Нужно реализовать метод проверки
                    return password
                logger.warning(
                    "Пароль из keyring не подходит. Требуется ввод нового пароля."
                )

            # Если пароля нет или он невалидный — запрашиваем новый
            password = getpass(f"Введите пароль для пользователя {self.user}: ")
            keyring.set_password(self.service_name, self.user, password)
            logger.info("Пароль успешно сохранён в keyring")
            return password
        except Exception as e:
            logger.error(f"Ошибка при работе с keyring: {str(e)}")
            raise RuntimeError("Не удалось инициализировать пароль") from e

    def _test_password(self, password: str) -> bool:
        """Проверяет, работает ли пароль (например, пробует подключиться)."""
        try:
            # Пример: пробуем выполнить простую команду через SSH
            test_cmd = f"plink.exe -ssh {self.user}@{self.centrum_host} -pw {password} -batch echo OK"
            subprocess.run(
                test_cmd, check=True, shell=True, timeout=5, capture_output=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
        except Exception:
            return False

    # ==================== Методы из ConfiguratorTool ====================

    def _execute_command(
        self, args: List[str], max_retries: int = MAX_RETRIES_SINGLE
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Выполняет команду с повторами для недоступных узлов"""
        logger.debug(f"Выполнение команды: args={args}, max_retries={max_retries}")

        result_dict: Dict[str, Dict[str, Optional[str]]] = {}
        unavailable_nodes: Set[str] = set()
        success_nodes: Set[str] = set()
        no_update_needed_nodes: Set[str] = set()
        attempt = 0

        while attempt < max_retries:
            attempt += 1
            if max_retries > 1:
                logger.info(f"Попытка {attempt} из {max_retries}")

            try:
                logger.debug(
                    f"Запуск subprocess.run с командой: java -jar {self.jar_path} {' '.join(args)}"
                )

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
                    logger.warning("Пустой вывод от команды")
                    continue

                logger.debug(
                    f"Получен вывод команды (первые 200 символов): {result.stdout[:200]}..."
                )

                (
                    current_result,
                    current_unavailable,
                    current_success,
                    current_no_update,
                ) = self._parse_output(result.stdout)

                logger.debug(
                    f"Результат парсинга: nodes={len(current_result)}, unavailable={len(current_unavailable)}, "
                    f"success={len(current_success)}, no_update={len(current_no_update)}"
                )

                result_dict.update(current_result)
                unavailable_nodes.update(current_unavailable)
                success_nodes.update(current_success)
                no_update_needed_nodes.update(current_no_update)

                if not current_unavailable or max_retries <= 1:
                    logger.debug(
                        "Нет недоступных узлов или max_retries <= 1, завершаем попытки"
                    )
                    break

                if attempt < max_retries:
                    logger.debug(
                        f"Ожидание {WAIT_BETWEEN_RETRIES} секунд перед следующей попыткой"
                    )
                    time.sleep(WAIT_BETWEEN_RETRIES)

            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if e.stderr else str(e)
                logger.error(f"Ошибка выполнения команды: {error_msg}")
                if attempt == max_retries or max_retries <= 1:
                    logger.error(
                        "Достигнуто максимальное количество попыток, возвращаем ошибку"
                    )
                    return {"error": {"message": error_msg}}
                continue
            except Exception as e:
                logger.error(f"Неожиданная ошибка: {str(e)}", exc_info=True)
                if attempt == max_retries or max_retries <= 1:
                    logger.error(
                        "Достигнуто максимальное количество попыток, возвращаем ошибку"
                    )
                    return {"error": {"message": str(e)}}
                continue

        # Заполнение недоступных узлов
        for node in unavailable_nodes:
            logger.debug(f"Добавление недоступного узла: {node}")
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
                logger.debug(f"Добавление успешного узла: {node}")
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
                logger.debug(f"Добавление узла, не требующего обновления: {node}")
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
        logger.debug("Вызов _categorize_nodes для классификации узлов")
        self._categorize_nodes()

        logger.info(
            f"Команда выполнена. Всего узлов: {len(result_dict)}, "
            f"успешных: {len(success_nodes)}, недоступных: {len(unavailable_nodes)}, "
            f"не требующих обновления: {len(no_update_needed_nodes)}"
        )

        return self.node_result

    def _parse_output(
        self, output: str
    ) -> Tuple[Dict[str, Dict[str, Optional[str]]], Set[str], Set[str], Set[str]]:
        """Парсим весь вывод stdout из JAR"""
        logger.debug("Начало парсинга вывода команды")

        if not output:
            logger.warning("Пустой вывод для парсинга")
            return {}, set(), set(), set()

        devices_dict: Dict[str, Dict[str, Optional[str]]] = {}
        unavailable_nodes: Set[str] = set()
        success_nodes: Set[str] = set()
        no_update_needed_nodes: Set[str] = set()

        try:
            logger.debug("Парсинг строк вывода для статусов обновления")
            for line in output.splitlines():
                line = line.strip()
                logger.debug(f"Обработка строки: {line}")

                # Обработка успешных узлов
                if "успешно запланировано" in line:
                    logger.debug(f"Найдена строка успешного обновления: {line}")
                    for part in line.split():
                        if (
                            part.replace(".", "").isdigit()
                            and len(part.split(".")) >= 3
                        ):
                            logger.debug(f"Добавление успешного узла: {part}")
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
                    logger.debug(f"Найдена строка недоступного узла: {line}")
                    for part in line.split():
                        if (
                            part.replace(".", "").isdigit()
                            and len(part.split(".")) >= 3
                        ):
                            logger.debug(f"Добавление недоступного узла: {part}")
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
                    logger.debug(
                        f"Найдена строка узла, не требующего обновления: {line}"
                    )
                    for part in line.split():
                        if (
                            part.replace(".", "").isdigit()
                            and len(part.split(".")) >= 3
                        ):
                            logger.debug(
                                f"Добавление узла, не требующего обновления: {part}"
                            )
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

            logger.debug("Парсинг строк вывода для детальной информации об узлах")
            for line in output.splitlines():
                line = line.strip()
                logger.debug(f"Обработка строки данных: {line}")

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
                    logger.debug(f"Добавление/обновление узла {device_key}: {device}")
                    devices_dict[device_key] = device

                    status = (device.get("status") or "").upper()
                    online = (device.get("online") or "").upper()

                    if status == "UNAVAILABLE" or online == "FALSE" or online == "NO":
                        logger.debug(
                            f"Узел {device_key} недоступен (status={status}, online={online})"
                        )
                        unavailable_nodes.add(device_key)

        except Exception as e:
            logger.error(f"Ошибка при парсинге вывода: {str(e)}", exc_info=True)
            return {}, set(), set(), set()

        logger.info(
            f"Парсинг завершен. Узлов: {len(devices_dict)}, "
            f"недоступных: {len(unavailable_nodes)}, "
            f"успешных: {len(success_nodes)}, "
            f"не требующих обновления: {len(no_update_needed_nodes)}"
        )

        return devices_dict, unavailable_nodes, success_nodes, no_update_needed_nodes

    def _categorize_nodes(self):
        """Категоризация узлов по статусам"""
        logger.debug("Начало категоризации узлов по статусам")

        self.work_tp = []
        self.error_tp = []
        self.update_tp = []
        self.ccm_tp = []
        self.unzip_tp = []
        self.no_update_needed_tp = []
        self.unavailable = []

        for node_id, node_data in self.node_result.items():
            status = (node_data.get("status") or "").upper()
            node_type = (node_data.get("type") or "").strip()
            ip_node = (node_data.get("ip") or "").strip()
            tp = node_data.get("tp") or node_id
            version = (node_data.get("cv") or "").strip()

            logger.debug(
                f"Обработка узла {node_id} (tp={tp}, status={status}, type={node_type}, version={version})"
            )

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

            logger.debug(f"Формирование записи для списка: {list_entry}")

            if status == "IN_WORK":
                self.work_tp.append(list_entry)
                logger.debug(f"Добавлен в work_tp: {list_entry}")
            elif status in ("UPGRADE_ERROR_WITH_DOWNGRADE", "FAST_REVERT"):
                self.error_tp.append(list_entry)
                logger.debug(f"Добавлен в error_tp: {list_entry}")
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
                logger.debug(f"Добавлен в update_tp: {list_entry}")
            elif status == "CCM_UPDATE_RESTART":
                self.ccm_tp.append(list_entry)
                logger.debug(f"Добавлен в ccm_tp: {list_entry}")
            elif status == "UNZIP_FILES":
                self.unzip_tp.append(list_entry)
                logger.debug(f"Добавлен в unzip_tp: {list_entry}")
            elif status == "NO_UPDATE_NEEDED":
                self.no_update_needed_tp.append(list_entry)
                logger.debug(f"Добавлен в no_update_needed_tp: {list_entry}")
            elif status == "UNAVAILABLE":
                self.unavailable.append(list_entry)
                logger.debug(f"Добавлен в unavailable: {list_entry}")

        logger.info(
            f"Категоризация завершена. work_tp: {len(self.work_tp)}, "
            f"error_tp: {len(self.error_tp)}, update_tp: {len(self.update_tp)}, "
            f"ccm_tp: {len(self.ccm_tp)}, unzip_tp: {len(self.unzip_tp)}, "
            f"no_update_needed_tp: {len(self.no_update_needed_tp)}, "
            f"unavailable: {len(self.unavailable)}"
        )

    def save_status_lists(self, prefix: str = ""):
        """Сохраняет все списки статусов в отдельные файлы"""
        logger.debug(f"Сохранение списков статусов с префиксом '{prefix}'")

        lists_to_save = {
            FILES["work_tp"]: self.work_tp,
            FILES["error_tp"]: self.error_tp,
            FILES["update_tp"]: self.update_tp,
            FILES["ccm_tp"]: self.ccm_tp,
            FILES["unzip_tp"]: self.unzip_tp,
            FILES["no_update_needed_tp"]: self.no_update_needed_tp,
            FILES["unavailable_tp"]: self.unavailable,
        }

        for orig_name, data in lists_to_save.items():
            # берём только имя файла, без каталогов
            base_name = Path(orig_name).name
            target_path = self.config_dir / f"{prefix}{base_name}"
            # удалить старый
            if target_path.exists():
                target_path.unlink()
            # записать новый
            if data:  # список не пуст
                target_path.write_text("\n".join(data), encoding="utf-8")
                logger.info("Записан %s (%d строк)", target_path, len(data))
            else:
                logger.debug("Список %s пуст – файл не создаётся", base_name)

        # Удаляем старые файлы
        # for filename in lists_to_save:
        #     filepath: Path = self.config_dir / (prefix + filename)
        #     if filepath.is_file():
        #         logger.debug(f"Удаление старого файла: {filepath}")
        #         filepath.unlink()

        # Пишем новые файлы
        # for filename, data in lists_to_save.items():
        #     if not data:
        #         logger.debug(f"Нет данных для сохранения в {filename}")
        #         continue

        #     filepath: Path = self.config_dir / (prefix + filename)
        #     with open(filepath, "w", encoding="utf-8") as f:
        #         f.write("\n".join(data))
        #     logger.info(f"Список сохранен в {filepath} (записей: {len(data)})")

    def get_all_nodes(
        self, max_retries: int = MAX_RETRIES_DEFAULT
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Получить состояние всех узлов с Centrum"""
        logger.info("Получение состояния всех узлов с Centrum")
        return self._execute_command(["-ch", self.centrum_host, "--all"], max_retries)

    def get_nodes_from_file(
        self, filename: Union[Path, None] = None
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Получить состояние узлов перечисленных в файле"""
        if filename is None:
            filename = Path(FILES["server_list"])
        filepath: Path = self.config_dir / filename
        logger.info(f"Получение состояния узлов из файла {filepath}")
        return self._execute_command(
            ["-ch", self.centrum_host, "-f", str(filepath)],
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

        logger.info(
            f"Запуск обновления серверов из файла {filepath} до версии {version_sv}"
        )

        args = ["-ch", self.centrum_host, "-f", str(filepath), "-sv", version_sv]
        if no_backup:
            args.append("-nb")
            logger.debug("Используется флаг no_backup (-nb)")

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

        logger.info(
            f"Запуск обновления касс типа {cash_type} из файла {filepath} до версии {version}"
        )

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
            logger.debug("Используется флаг no_backup (-nb)")
        if auto_restart:
            args.append("-ar")
            logger.debug("Используется флаг auto_restart (-ar)")

        return self._execute_command(args, MAX_RETRIES_SINGLE)

    def save_node_result(self, filename: Union[Path, None] = None):
        """Сохранить результат в файл"""
        if filename is None:
            filename = Path(FILES["node_result"])
        filepath = self.config_dir / filename

        logger.info(f"Сохранение результатов в файл {filepath}")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.node_result, f, ensure_ascii=False, indent=2)
        logger.info(f"Результат сохранен в {filepath} (узлов: {len(self.node_result)})")

    # ==================== Методы из ServerUpdater ====================

    def extract_tp_index(self, tp: str) -> str:
        """Извлекает индекс из tp формата '1.0.индекс.0'"""
        logger.debug(f"Извлечение индекса из tp: {tp}")
        parts = tp.split(".")
        if len(parts) >= 3:
            if parts[3] == "0":
                result = parts[2]
            else:
                result = f"{parts[2]}.{parts[3]}"
            logger.debug(f"Извлеченный индекс: {result}")
            return result
        logger.debug(f"Не удалось извлечь индекс, возвращаем исходное значение: {tp}")
        return tp

    def get_retail_servers_to_update(self, all_nodes: Dict) -> List[Dict]:
        """Получает список серверов RETAIL, которые нужно обновить"""
        logger.info("Поиск серверов RETAIL для обновления")
        servers_to_update = []

        for ip, node_data in all_nodes.items():
            node_type = node_data.get("type")
            current_version = node_data.get("cv")
            tp = node_data.get("tp", "")

            logger.debug(
                f"Проверка узла {ip} (type={node_type}, version={current_version}, tp={tp})"
            )

            if (
                node_type == "RETAIL"
                and current_version != self.target_version
                and ip not in self.updated_servers
            ):
                tp_index = self.extract_tp_index(tp)
                server_info = {
                    "ip": ip,
                    "tp": tp,
                    "current_version": current_version,
                    "tp_index": tp_index,
                }
                logger.debug(f"Добавление сервера для обновления: {server_info}")
                servers_to_update.append(server_info)

        logger.info(f"Найдено серверов для обновления: {len(servers_to_update)}")
        return servers_to_update

    def create_server_file(
        self, servers: List[Dict], filename: Union[Path, None] = None
    ) -> None:
        """Создает файл server.txt с индексами серверов"""
        if filename is None:
            filename = Path(FILES["server_list"])
        filepath = self.config_dir / filename

        logger.info(f"Создание файла {filepath} с {len(servers)} серверами")

        with open(filepath, "w", encoding="utf-8") as f:
            for server in servers:
                f.write(f"{server['tp_index']}\n")
                logger.debug(f"Запись сервера в файл: {server['tp_index']}")

        logger.info(f"Файл {filename} успешно создан")

    def check_file_exists(self, filename: str) -> bool:
        """Проверяет существование файла"""
        filepath = self.config_dir / filename
        exists = filepath.exists() and filepath.stat().st_size > 0
        logger.debug(f"Проверка файла {filename}: exists={exists}")
        return exists

    def read_file_lines(self, filename: str) -> List[str]:
        """Читает строки из файла, игнорируя строки с индексом '0'"""
        filepath = self.config_dir / filename
        if not filepath.exists():
            logger.warning(f"Файл {filename} не существует")
            return []

        logger.debug(f"Чтение строк из файла {filename} (игнорируя индекс '0')")
        valid_lines = []

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue  # Пропускаем пустые строки

                # Разбиваем строку по первому "-" для проверки индекса
                parts = line.split("-", 1)
                if parts[0] == "0":
                    logger.debug(f"Игнорируем строку с индексом '0': {line}")
                    continue

                valid_lines.append(line)

        logger.debug(f"Прочитано строк (без '0'): {len(valid_lines)}")
        return valid_lines

    def command_with_plink(self, servers: List[str], restart_file: str) -> bool:
        """Перезапускает службу на серверах используя PLINK"""
        logging.info(f"Начало обработки {len(servers)} серверов")
        try:
            # Проверяем наличие необходимых файлов
            command_filepath = Path(restart_file)
            logging.debug(f"Проверка существования файла команд: {command_filepath}")

            if not command_filepath.exists():
                logging.error(f"Файл команд {restart_file} не найден")
                return False
            else:
                logging.debug("Файл команд найден")

            logging.debug(f"Проверка существования plink: {self.plink_path}")
            if not self.plink_path.exists():
                logging.error("plink.exe не найден")
                return False
            else:
                logging.debug("plink.exe найден")

            # Обрабатываем каждый сервер
            failed_servers = []
            for server_info in servers:
                logging.info(f"Обработка сервера: {server_info}")

                # Извлекаем IP из формата "индекс-тип-ip-версия"
                parts = server_info.split("-")
                if len(parts) < 3:
                    logging.error(f"Неверный формат строки сервера: {server_info}")
                    failed_servers.append(server_info)
                    continue

                server_ip = parts[2]
                server_index = parts[0]
                logging.debug(
                    f"Извлеченные данные: ip={server_ip}, index={server_index}"
                )

                # Проверяем доступность через ping

                logging.debug(f"Проверка доступности {server_ip} через ping")
                if not self._check_ping(server_ip):
                    logging.warning(
                        f"Сервер {server_ip} (индекс {server_index}) недоступен по ping"
                    )
                    failed_servers.append(server_info)
                    continue
                else:
                    logging.debug("Сервер доступен по ping")

                # Выполняем команды через plink
                cmd = [
                    str(self.plink_path),
                    "-ssh",
                    f"{self.user}@{server_ip}",
                    "-pw",
                    self.password,
                    "-batch",
                    "-m",
                    str(command_filepath),
                ]
                logging.debug(f"Команда для выполнения: {' '.join(cmd)}")

                try:
                    logging.info(f"Запуск команд на сервере {server_ip}")

                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=PLINK_TIMEOUT,
                        encoding="cp1251",
                    )

                    if result.returncode == 0:
                        logging.info(f"Команды успешно выполнены на {server_ip}")
                        if result.stdout:
                            logging.debug(f"Вывод команды:\n{result.stdout}")
                    else:
                        logging.error(
                            f"Ошибка выполнения на {server_ip}:\nКод возврата: {result.returncode}\nОшибка: {result.stderr}"
                        )
                        failed_servers.append(server_info)

                except subprocess.TimeoutExpired:
                    logging.error(
                        f"Таймаут выполнения команд на {server_ip} (превышено {PLINK_TIMEOUT} сек)"
                    )
                    failed_servers.append(server_info)
                except Exception as e:
                    logging.error(
                        f"Неожиданная ошибка при работе с {server_ip}: {str(e)}",
                        exc_info=True,
                    )
                    failed_servers.append(server_info)

                # Пауза между серверами
                logging.debug("Пауза 2 секунды перед следующим сервером")
                time.sleep(2)

            # Итоговая проверка
            if failed_servers:
                logging.error(
                    f"Не удалось обработать {len(failed_servers)} серверов: {failed_servers}"
                )
                return False
            else:
                logging.info("Все серверы успешно обработаны")
                return True

        except Exception as e:
            logging.error(
                f"Критическая ошибка в command_with_plink: {str(e)}",
                exc_info=True,
            )
            return False

    def _check_ping(self, host: str) -> bool:
        """Проверка доступности хоста через ping"""
        logging.debug(f"Выполнение ping для {host}")
        try:
            result = subprocess.run(
                ["ping", "-n", "1", "-w", str(PING_TIMEOUT), host],
                capture_output=True,
                text=True,
            )
            if "TTL=" in result.stdout:
                logging.debug(f"Ping успешен для {host}")
                return True
            else:
                logging.debug(f"Ping не удался для {host}")
                return False
        except Exception as e:
            logging.error(f"Ошибка при выполнении ping для {host}: {str(e)}")
            return False

    def compare_servers_and_versions(
        self, work_servers: List[str], original_servers: List[Dict]
    ) -> tuple[bool, List[str]]:
        """Сравнивает серверы из work_tp с исходными и проверяет версии"""
        logger.info("Сравнение серверов и версий")

        # 3. Игнорируем строки с индексом 0
        original_indices = {
            server["tp_index"]
            for server in original_servers
            # if server["tp_index"] != "0"
        }

        work_indices = set()
        incorrect_versions = []

        for server_info in work_servers:
            parts = server_info.split("-")
            if len(parts) >= 1:
                tp_index = parts[0]
                # Пропускаем серверы с индексом 0
                if tp_index == "0":
                    logger.debug(f"Игнорируем сервер с индексом 0: {server_info}")
                    continue

                work_indices.add(tp_index)
                logger.debug(f"Индекс из work_tp: {tp_index}")

                # Проверяем версию, если есть информация о версии в строке
                if len(parts) >= 4:
                    server_version = parts[3]
                    if server_version != self.target_version:
                        logger.warning(f"Неверная версия у сервера {server_info}")
                        incorrect_versions.append(server_info)

        logger.debug(f"Оригинальные индексы: {original_indices}")
        logger.debug(f"Индексы из work_tp (без 0): {work_indices}")

        if original_indices != work_indices:
            logger.error(
                f"Несоответствие серверов: ожидалось {original_indices}, получено {work_indices}"
            )
            return False, incorrect_versions

        if incorrect_versions:
            logger.error(f"Серверы с неправильными версиями: {incorrect_versions}")
            return False, incorrect_versions

        logger.info("Все серверы соответствуют ожидаемым и имеют правильные версии")
        return True, []

    def _perform_pre_work(self):
        """Выполняет предварительные работы с сервером перед обновлением"""
        logger.info("Выполнение предварительных работ с сервером")
        work_servers = self.read_file_lines(FILES["work_tp"])
        if work_servers:
            logger.info(f"Предварительные работы на серверах: {work_servers}")
            if not self.command_with_plink(work_servers, FILES["pre_update_commands"]):
                logger.error("Ошибка выполнения предварительных работ")
                return False
        logger.info(f"Ожидание {PRE_UPDATE_TIMEOUT} секунд...")
        time.sleep(PRE_UPDATE_TIMEOUT)
        return True

    def _perform_post_work(self):
        """Выполняет дополнительные работы с сервером после обновления"""
        logger.info("Выполнение дополнительных работ с сервером после обновления")
        work_servers = self.read_file_lines(FILES["work_tp"])
        if work_servers:
            logger.info(f"Дополнительные работы на серверах: {work_servers}")
            if not self.command_with_plink(work_servers, FILES["post_update_commands"]):
                logger.error("Ошибка выполнения дополнительных работ")
                return False
        logger.info(f"Ожидание {POST_UPDATE_TIMEOUT} секунд...")
        time.sleep(POST_UPDATE_TIMEOUT)
        return True

    def _monitor_update_status(self, current_part_server: List[Dict]) -> bool:
        """Мониторит статус обновления для текущей итерации"""
        while True:
            logger.info(
                f"Ожидание {STATUS_CHECK_INTERVAL // 60} минут перед проверкой..."
            )
            time.sleep(STATUS_CHECK_INTERVAL)

            # Получаем статус только для текущей итерации
            self.get_nodes_from_file()
            self.save_status_lists(prefix=FILES["status_prefix"])

            # Проверяем ошибки
            if self._check_errors():
                return False

            # Проверяем статусы обновления
            status_check = self._check_update_statuses(current_part_server)
            if status_check is not None:  # None означает продолжение ожидания
                return status_check

    def _check_errors(self) -> bool:
        """Проверяет наличие ошибок обновления"""
        if self.check_file_exists(FILES["status_prefix"] + FILES["error_tp"]):
            error_servers = self.read_file_lines(
                FILES["status_prefix"] + FILES["error_tp"]
            )
            logger.error(f"Ошибки обновления на серверах: {error_servers}")
            return True
        return False

    def _check_update_statuses(self, current_part_server: List[Dict]) -> Optional[bool]:
        """Проверяет различные статусы обновления"""
        # Проверяем необходимость перезапуска служб
        if self._handle_service_restart(FILES["ccm_tp"], FILES["ccm_restart_commands"]):
            return None
        if self._handle_service_restart(
            FILES["unzip_tp"], FILES["unzip_restart_commands"]
        ):
            return None

        # Обработка статуса update_tp (обновление в процессе)
        if self.check_file_exists(FILES["status_prefix"] + FILES["update_tp"]):
            current_update_servers = set(
                self.read_file_lines(FILES["status_prefix"] + FILES["update_tp"])
            )
            if not hasattr(self, "_update_servers_prev"):
                # Первое обнаружение - сохраняем и продолжаем ожидание
                self._update_servers_prev = current_update_servers
                self._update_servers_counter = 1
                logger.debug(
                    f"Обновление в процессе для серверов: {current_update_servers}"
                )
                return None
            elif current_update_servers == self._update_servers_prev:
                # Те же серверы в статусе update_tp
                self._update_servers_counter += 1
                if (
                    self._update_servers_counter >= 2
                ):  # Допускаем 1 повтора (2 проверки)
                    logger.error(
                        f"Серверы слишком долго в статусе обновления: {current_update_servers} (попытка {self._update_servers_counter})"
                    )
                    return False  # Считаем это ошибкой
                logger.warning(
                    f"Обновление затянулось для серверов: {current_update_servers} (попытка {self._update_servers_counter})"
                )
                return None
            else:
                # Изменился список серверов в update_tp - сбрасываем счетчик
                self._update_servers_prev = current_update_servers
                self._update_servers_counter = 1
                logger.debug(
                    f"Прогресс обновления: новые серверы в процессе - {current_update_servers}"
                )
                return None

        # Обработка статуса unavailable (недоступные серверы)
        if self.check_file_exists(FILES["status_prefix"] + FILES["unavailable_tp"]):
            current_unavailable_servers = set(
                self.read_file_lines(FILES["status_prefix"] + FILES["unavailable_tp"])
            )

            if not hasattr(self, "_unavailable_servers_prev"):
                # Первое обнаружение - сохраняем и продолжаем ожидание
                self._unavailable_servers_prev = current_unavailable_servers
                self._unavailable_servers_counter = 1
                logger.warning(
                    f"Обнаружены недоступные серверы: {current_unavailable_servers}"
                )
                return None
            elif current_unavailable_servers == self._unavailable_servers_prev:
                # Те же серверы остаются недоступными
                self._unavailable_servers_counter += 1
                if self._unavailable_servers_counter >= 2:
                    logger.error(
                        f"Серверы остаются недоступными: {current_unavailable_servers} (попытка {self._unavailable_servers_counter})"
                    )
                    return False
            else:
                # Изменился список недоступных серверов - сбрасываем счетчик
                self._unavailable_servers_prev = current_unavailable_servers
                self._unavailable_servers_counter = 1
                logger.warning(
                    f"Изменение списка недоступных серверов: {current_unavailable_servers}"
                )
                return None

        # Проверяем завершение обновления
        if self.check_file_exists(FILES["status_prefix"] + FILES["work_tp"]):
            work_servers = self.read_file_lines(
                FILES["status_prefix"] + FILES["work_tp"]
            )
            servers_match, incorrect_versions = self.compare_servers_and_versions(
                work_servers, current_part_server
            )
            if servers_match and not incorrect_versions:
                # Сбрасываем счетчики при успешном завершении
                if hasattr(self, "_update_servers_prev"):
                    del self._update_servers_prev
                    del self._update_servers_counter
                if hasattr(self, "_unavailable_servers_prev"):
                    del self._unavailable_servers_prev
                    del self._unavailable_servers_counter
                return True

        return None

    def _handle_service_restart(self, status_file: str, commands_file: str) -> bool:
        """Обрабатывает перезапуск служб при необходимости"""
        if self.check_file_exists(FILES["status_prefix"] + status_file):
            servers = self.read_file_lines(FILES["status_prefix"] + status_file)
            logger.info(f"Перезапуск служб на серверах: {servers}")
            if not self.command_with_plink(servers, commands_file):
                logger.error(f"Ошибка перезапуска служб ({status_file})")
                return False
            return True
        return False

    def update_servers_part_server(self) -> bool:
        """Основной метод обновления серверов по частям с сохранением состояния"""
        logger.info("Начало пошагового обновления серверов")

        # Получаем все узлы один раз в начале
        logger.debug("Первоначальное получение списка всех узлов")
        initial_nodes = self.get_all_nodes(max_retries=MAX_RETRIES_DEFAULT)
        if "error" in initial_nodes:
            logger.error(f"Ошибка получения узлов: {initial_nodes['error']}")
            return False

        # Инициализируем node_result с исходными данными
        self.node_result = initial_nodes
        self.save_node_result()

        # Создаем копию для локальной работы, чтобы не перезаписывать node_result
        current_nodes_state = initial_nodes.copy()

        while True:
            if self.max_iterations and self.current_iteration >= self.max_iterations:
                logger.info(
                    f"Достигнуто максимальное количество итераций ({self.max_iterations})"
                )
                return True

            logger.info(f"Итерация {self.current_iteration + 1}")

            # Используем актуальное состояние узлов
            servers_to_update = self.get_retail_servers_to_update(current_nodes_state)

            if not servers_to_update:
                logger.info("Все серверы RETAIL уже обновлены до целевой версии")
                return True

            current_part_server = servers_to_update[: self.part_server_size]
            self.current_iteration += 1

            logger.info(
                f"Обработка итерации: {[s['tp_index'] for s in current_part_server]}"
            )

            # Создаем временный файл для текущей итерации
            self.create_server_file(current_part_server)

            # Получаем статус только для текущей итерации (не перезаписываем основной словарь)
            logger.debug("Получение статуса серверов перед обновлением")
            part_server_nodes = self.get_nodes_from_file()
            self.save_status_lists()

            # Предварительные работы(например копирование файлов обновления)
            if PRE_UPDATE_WORK:
                if not self._perform_pre_work():
                    return False

            # Запускаем обновление
            logger.info(f"Запуск обновления до версии {self.target_version}")
            update_result = self.update_servers(version_sv=self.target_version)
            if "error" in update_result:
                logger.error(f"Ошибка обновления: {update_result['error']}")
                return False

            # Мониторим статус обновления
            if not self._monitor_update_status(current_part_server):
                return False

            # Обновляем состояние только для успешно обновленных узлов
            for server in current_part_server:
                ip = server["ip"]
                if ip in current_nodes_state:
                    current_nodes_state[ip]["cv"] = self.target_version
                    self.updated_servers.add(ip)
                    logger.debug(f"Обновлена версия для {ip} -> {self.target_version}")

            # Синхронизируем с основным словарем и сохраняем
            self.node_result.update(current_nodes_state)
            self.save_node_result()

            # Предварительные работы(например копирование файлов обновления)
            if POST_UPDATE_WORK:
                if not self._perform_post_work():
                    return False

            # Удаляем временный файл с серверами текущей итерации
            server_file = self.config_dir / FILES["server_list"]
            if server_file.exists():
                server_file.unlink()
                logger.debug(f"Удален временный файл {server_file}")

            # Продолжаем цикл для следующего итерации


# Пример использования
if __name__ == "__main__":
    try:
        logger.info("=== Начало работы скрипта ===")

        # Создаем унифицированный обновлятель
        logger.debug("Создание экземпляра UnifiedServerUpdater")
        updater = UnifiedServerUpdater()

        # Запускаем обновление
        logger.info("Запуск процесса обновления")
        success = updater.update_servers_part_server()

        if success:
            logger.info("Все серверы успешно обновлены!")
        else:
            logger.error("Обновление завершилось с ошибками")

    except Exception as e:
        logger.critical(f"Критическая ошибка: {str(e)}", exc_info=True)
    finally:
        logger.info("=== Завершение работы скрипта ===")
