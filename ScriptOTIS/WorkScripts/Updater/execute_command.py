import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

from logger_manager import LoggerManager

MAX_RETRIES_SINGLE = 3


class CommandExecutor:
    """Класс для выполнения команд с повторами и обработкой результатов"""

    def __init__(self, logger_manager: LoggerManager):
        self.logger = logger_manager.get_logger(__name__)
        self.logger.info("CommandExecutor инициализирован")

    def execute_jar_command(
        self,
        jar_path: Path,
        args: List[str],
        max_retries: int = MAX_RETRIES_SINGLE,
        wait_between_retries: int = 3,
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Выполняет команду JAR с повторами для недоступных узлов"""
        self.logger.debug(f"Выполнение команды: args={args}, max_retries={max_retries}")

        result_dict: Dict[str, Dict[str, Optional[str]]] = {}
        unavailable_nodes: Set[str] = set()
        success_nodes: Set[str] = set()
        no_update_needed_nodes: Set[str] = set()
        attempt = 0

        while attempt < max_retries:
            attempt += 1
            if max_retries > 1:
                self.logger.info(f"Попытка {attempt} из {max_retries}")

            try:
                self.logger.debug(
                    f"Запуск subprocess.run с командой: java -jar {jar_path} {' '.join(args)}"
                )

                result = subprocess.run(
                    ["java", "-jar", str(jar_path)] + args,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="cp1251",
                    errors="replace",
                )

                if not result.stdout:
                    self.logger.warning("Пустой вывод от команды")
                    continue

                self.logger.debug(
                    f"Получен вывод команды (первые 200 символов): {result.stdout[:200]}..."
                )

                (
                    current_result,
                    current_unavailable,
                    current_success,
                    current_no_update,
                ) = self._parse_output(result.stdout)

                self.logger.debug(
                    f"Результат парсинга: nodes={len(current_result)}, unavailable={len(current_unavailable)}, "
                    f"success={len(current_success)}, no_update={len(current_no_update)}"
                )

                result_dict.update(current_result)
                unavailable_nodes.update(current_unavailable)
                success_nodes.update(current_success)
                no_update_needed_nodes.update(current_no_update)

                if not current_unavailable or max_retries <= 1:
                    self.logger.debug(
                        "Нет недоступных узлов или max_retries <= 1, завершаем попытки"
                    )
                    break

                if attempt < max_retries:
                    self.logger.debug(
                        f"Ожидание {wait_between_retries} секунд перед следующей попыткой"
                    )
                    time.sleep(wait_between_retries)

            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if e.stderr else str(e)
                self.logger.error(f"Ошибка выполнения команды: {error_msg}")
                if attempt == max_retries or max_retries <= 1:
                    self.logger.error(
                        "Достигнуто максимальное количество попыток, возвращаем ошибку"
                    )
                    return {"error": {"message": error_msg}}
                continue
            except Exception as e:
                self.logger.error(f"Неожиданная ошибка: {str(e)}", exc_info=True)
                if attempt == max_retries or max_retries <= 1:
                    self.logger.error(
                        "Достигнуто максимальное количество попыток, возвращаем ошибку"
                    )
                    return {"error": {"message": str(e)}}
                continue

        # Заполнение недоступных узлов
        for node in unavailable_nodes:
            self.logger.debug(f"Добавление недоступного узла: {node}")
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
                self.logger.debug(f"Добавление успешного узла: {node}")
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
                self.logger.debug(f"Добавление узла, не требующего обновления: {node}")
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

        self.logger.info(
            f"Команда выполнена. Всего узлов: {len(result_dict)}, "
            f"успешных: {len(success_nodes)}, недоступных: {len(unavailable_nodes)}, "
            f"не требующих обновления: {len(no_update_needed_nodes)}"
        )

        return result_dict

    def _parse_output(
        self, output: str
    ) -> Tuple[Dict[str, Dict[str, Optional[str]]], Set[str], Set[str], Set[str]]:
        """Парсим весь вывод stdout из JAR с учетом двух методов работы"""
        self.logger.debug("Начало парсинга вывода команды")

        if not output:
            self.logger.warning("Пустой вывод для парсинга")
            return {}, set(), set(), set()

        devices_dict: Dict[str, Dict[str, Optional[str]]] = {}
        unavailable_nodes: Set[str] = set()
        success_nodes: Set[str] = set()
        no_update_needed_nodes: Set[str] = set()

        # Определяем метод работы по первой строке
        first_line = output.splitlines()[0].strip() if output.splitlines() else ""
        is_method_one = first_line.startswith("-ch")
        is_method_two = first_line.startswith("-h")

        self.logger.debug(
            f"Метод работы: {'1 (Centrum)' if is_method_one else '2 (Retail)' if is_method_two else 'неопределен'}"
        )

        try:
            self.logger.debug("Парсинг строк вывода для статусов обновления")
            for line in output.splitlines():
                line = line.strip()
                self.logger.debug(f"Обработка строки: {line}")

                # Обработка успешных узлов
                if "успешно запланировано" in line:
                    self.logger.debug(f"Найдена строка успешного обновления: {line}")

                    # Для метода 1 ищем TP, для метода 2 ищем IP
                    if is_method_one:
                        # Метод 1: ищем TP (формат 1.0.xxx.0)
                        for part in line.split():
                            if (
                                part.replace(".", "").isdigit()
                                and len(part.split(".")) >= 3
                            ):
                                self.logger.debug(
                                    f"Добавление успешного узла (TP): {part}"
                                )
                                success_nodes.add(part)
                    elif is_method_two:
                        # Метод 2: ищем IP в предыдущей строке команды
                        for prev_line in output.splitlines():
                            if (
                                prev_line.strip().startswith("-h")
                                and "успешно запланировано" in line
                            ):
                                parts = prev_line.split()
                                if len(parts) >= 2:
                                    ip = parts[1]
                                    if self._is_valid_ip(ip):
                                        self.logger.debug(
                                            f"Добавление успешного узла (IP): {ip}"
                                        )
                                        success_nodes.add(ip)
                                        break

                # Обработка недоступных узлов
                elif "недоступен" in line:
                    self.logger.debug(f"Найдена строка недоступного узла: {line}")

                    if is_method_one:
                        # Метод 1: ищем TP
                        for part in line.split():
                            if (
                                part.replace(".", "").isdigit()
                                and len(part.split(".")) >= 3
                            ):
                                self.logger.debug(
                                    f"Добавление недоступного узла (TP): {part}"
                                )
                                unavailable_nodes.add(part)
                    elif is_method_two:
                        # Метод 2: ищем IP в предыдущей строке команды
                        for prev_line in output.splitlines():
                            if (
                                prev_line.strip().startswith("-h")
                                and "недоступен" in line
                            ):
                                parts = prev_line.split()
                                if len(parts) >= 2:
                                    ip = parts[1]
                                    if self._is_valid_ip(ip):
                                        self.logger.debug(
                                            f"Добавление недоступного узла (IP): {ip}"
                                        )
                                        unavailable_nodes.add(ip)
                                        break

                # Обработка узлов, не требующих обновления
                elif "не требуется" in line or "совпадают" in line:
                    self.logger.debug(
                        f"Найдена строка узла, не требующего обновления: {line}"
                    )

                    if is_method_one:
                        # Метод 1: ищем TP
                        for part in line.split():
                            if (
                                part.replace(".", "").isdigit()
                                and len(part.split(".")) >= 3
                            ):
                                self.logger.debug(
                                    f"Добавление узла, не требующего обновления (TP): {part}"
                                )
                                no_update_needed_nodes.add(part)
                    elif is_method_two:
                        # Метод 2: ищем IP в предыдущей строке команды
                        for prev_line in output.splitlines():
                            if prev_line.strip().startswith("-h") and (
                                "не требуется" in line or "совпадают" in line
                            ):
                                parts = prev_line.split()
                                if len(parts) >= 2:
                                    ip = parts[1]
                                    if self._is_valid_ip(ip):
                                        self.logger.debug(
                                            f"Добавление узла, не требующего обновления (IP): {ip}"
                                        )
                                        no_update_needed_nodes.add(ip)
                                        break

            self.logger.debug("Парсинг строк вывода для детальной информации об узлах")
            for line in output.splitlines():
                line = line.strip()
                self.logger.debug(f"Обработка строки данных: {line}")

                if not line or line.startswith(
                    ("Current client version:", "-", "Текущая и целевая")
                ):
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
                    self.logger.debug(
                        f"Добавление/обновление узла {device_key}: {device}"
                    )
                    devices_dict[device_key] = device

                    status = (device.get("status") or "").upper()
                    online = (device.get("online") or "").upper()

                    if status == "UNAVAILABLE" or online == "FALSE" or online == "NO":
                        self.logger.debug(
                            f"Узел {device_key} недоступен (status={status}, online={online})"
                        )
                        unavailable_nodes.add(device_key)

        except Exception as e:
            self.logger.error(f"Ошибка при парсинге вывода: {str(e)}", exc_info=True)
            return {}, set(), set(), set()

        self.logger.info(
            f"Парсинг завершен. Узлов: {len(devices_dict)}, "
            f"недоступных: {len(unavailable_nodes)}, "
            f"успешных: {len(success_nodes)}, "
            f"не требующих обновления: {len(no_update_needed_nodes)}"
        )

        return devices_dict, unavailable_nodes, success_nodes, no_update_needed_nodes

    def _is_valid_ip(self, ip: str) -> bool:
        """Проверяет, является ли строка валидным IP-адресом"""
        try:
            parts = ip.split(".")
            if len(parts) != 4:
                return False
            for part in parts:
                if not part.isdigit() or not 0 <= int(part) <= 255:
                    return False
            return True
        except:
            return False

    def categorize_nodes(
        self, node_result: Dict[str, Dict[str, Optional[str]]]
    ) -> Dict[str, List[str]]:
        """Категоризация узлов по статусам с учетом метода работы"""
        self.logger.debug("Начало категоризации узлов по статусам")

        categorized_lists = {
            "work_tp": [],
            "error_tp": [],
            "update_tp": [],
            "ccm_tp": [],
            "unzip_tp": [],
            "no_update_needed_tp": [],
            "unavailable": [],
        }

        # Определяем метод работы по первому ключу в node_result
        is_method_two = False
        if node_result:
            first_key = next(iter(node_result.keys()))
            if self._is_valid_ip(first_key):
                is_method_two = True

        self.logger.debug(
            f"Метод категоризации: {'2 (Retail)' if is_method_two else '1 (Centrum)'}"
        )

        for node_id, node_data in node_result.items():
            status = (node_data.get("status") or "").upper()
            node_type = (node_data.get("type") or "").strip()
            ip_node = (node_data.get("ip") or "").strip()
            tp = node_data.get("tp") or node_id
            version = (node_data.get("cv") or "").strip()

            # Для метода 2 используем IP как идентификатор, находим TP из node_result
            if is_method_two and self._is_valid_ip(node_id):
                # Ищем соответствующий TP для этого IP
                ip_node = node_id
                tp = node_data.get("tp") or ""

                # Если TP не найден в данных, пытаемся найти в основном словаре
                if not tp:
                    for other_node_id, other_data in node_result.items():
                        if other_data.get("ip") == node_id:
                            tp = other_data.get("tp") or ""
                            break

            # Обработка формата tp
            if tp and "." in tp:
                tp_parts = tp.split(".")
                if len(tp_parts) >= 4 and tp_parts[3] == "0":
                    tp_index = tp_parts[2]
                else:
                    tp_index = (
                        f"{tp_parts[2]}.{tp_parts[3]}" if len(tp_parts) >= 4 else tp
                    )
            else:
                tp_index = tp

            # Формирование записи
            list_entry_parts = []
            if tp_index and tp_index != "0":
                list_entry_parts.append(tp_index)
            if node_type:
                list_entry_parts.append(node_type)
            if ip_node:
                list_entry_parts.append(ip_node)
            if version:
                list_entry_parts.append(version)

            list_entry = "-".join(list_entry_parts)

            # Категоризация
            if status == "IN_WORK":
                categorized_lists["work_tp"].append(list_entry)
            elif status in ("UPGRADE_ERROR_WITH_DOWNGRADE", "FAST_REVERT"):
                categorized_lists["error_tp"].append(list_entry)
            elif status in (
                "UPGRADE_PLANING",
                "UPGRADE_DOWNLOADING",
                "UPGRADE_WAIT_FOR_REBOOT",
                "CHECK_PERMISSIONS",
                "BACKUP",
                "APPLY_PATCH",
                "TEST_START",
            ):
                categorized_lists["update_tp"].append(list_entry)
            elif status == "CCM_UPDATE_RESTART":
                categorized_lists["ccm_tp"].append(list_entry)
            elif status == "UNZIP_FILES":
                categorized_lists["unzip_tp"].append(list_entry)
            elif status == "NO_UPDATE_NEEDED":
                categorized_lists["no_update_needed_tp"].append(list_entry)
            elif status == "UNAVAILABLE":
                categorized_lists["unavailable"].append(list_entry)

        return categorized_lists


# Просто комментарий
