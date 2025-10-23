#!/usr/bin/python3

import copy
import re
import json
from pathlib import Path
from typing import List, Dict, Tuple
import shutil
import sys
import subprocess
import os
import logging
import logging.handlers
import time
from datetime import datetime
import gzip


# Константы (Меняем на реальные пути и IP)
WORK_DIR: Path = Path(__file__).resolve().parent
LOG_DIR: Path = WORK_DIR / "logs"
goods_template: Path = WORK_DIR / "template_goods.json"
keys_template: Path = WORK_DIR / "template_keys.json"
delete_goods_template: Path = WORK_DIR / "template_delete_goods.json"
delete_all_template: Path = WORK_DIR / "template_delete_all.json"
TASK_MANAGER = Path(r"/opt/taskmanager/bin/TaskManager")
SOURCE_DIR = Path(
    r"/mnt/qload/Badfiles"
)  # Меняем на путь к папке, куда перемещает Qload файлы для весов
DESTINATION_DIR: Path = WORK_DIR / "Working"
SUCCEED_DIR: Path = DESTINATION_DIR / "SUCCEED"
ERROR_DIR: Path = DESTINATION_DIR / "ERROR"
TARGET_IPS: List[str] = [
    "10.7.36.127",
]  # IP адреса весов


def setup_logging() -> bool:
    """Настройка системы логирования"""
    try:
        LOG_DIR.mkdir(exist_ok=True)

        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        log_filename: Path = (
            LOG_DIR / f"task_manager_{datetime.now().strftime('%Y-%m-%d')}.log"
        )

        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=log_filename,
            when="midnight",  # Ротация в полночь
            interval=1,  # Каждый день
            backupCount=5,  # Хранить 5 дней логов
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.suffix = "%Y-%m-%d.log"

        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        logger.addHandler(file_handler)

        logging.info("=" * 50)
        logging.info("Запуск Task Manager скрипта")
        logging.info(f"Рабочая директория: {WORK_DIR}")
        logging.info(f"Директория логов: {LOG_DIR}")

        return True

    except Exception as e:
        print(f"Ошибка настройки логирования: {e}")
        return False


def setup_directories():
    """Создает необходимые директории если они не существуют"""
    try:
        SUCCEED_DIR.mkdir(parents=True, exist_ok=True)
        ERROR_DIR.mkdir(parents=True, exist_ok=True)
        logging.info("Директории SUCCEED и ERROR проверены/созданы")
        return True
    except Exception as e:
        logging.error(f"Ошибка создания директорий: {e}")
        return False


def move_file_to_result_dir(file_path: Path, success: bool) -> bool:
    """
    Перемещает CSV файл в SUCCEED или ERROR директорию

    Args:
        file_path: Путь к CSV файлу
        success: True если обработка успешна, False если ошибка

    Returns:
        True если перемещение успешно, False если ошибка
    """
    try:
        if success:
            target_dir: Path = SUCCEED_DIR
            log_message = "успешно обработан"
        else:
            target_dir: Path = ERROR_DIR
            log_message = "обработан с ошибками"

        destination_path: Path = target_dir / file_path.name

        counter = 1
        original_destination: Path = destination_path
        while destination_path.exists():
            name_parts: Tuple[str, str] = (
                original_destination.stem,
                original_destination.suffix,
            )
            new_name: str = f"{name_parts[0]}_{counter}{name_parts[1]}"
            destination_path = target_dir / new_name
            counter += 1

        shutil.move(str(file_path), str(destination_path))
        logging.info(
            f"Файл {file_path.name} {log_message} и перемещен в {target_dir.name}"
        )
        return True

    except Exception as e:
        logging.error(
            f"Ошибка перемещения файла {file_path} в результатную директорию: {e}"
        )
        return False


def cleanup_json_config(ip: str) -> bool:
    """
    Удаляет JSON конфигурационный файл после обработки

    Args:
        ip: IP адрес для которого был создан конфиг

    Returns:
        True если удаление успешно, False если ошибка
    """
    try:
        config_path: Path = DESTINATION_DIR / f"config_{ip}.json"

        if config_path.exists():
            config_path.unlink()
            logging.info(f"Конфигурационный файл удален: {config_path.name}")
            return True
        else:
            logging.warning(
                f"Конфигурационный файл не найден для удаления: {config_path.name}"
            )
            return False

    except Exception as e:
        logging.error(f"Ошибка удаления конфигурационного файла для IP {ip}: {e}")
        return False


def cleanup_old_logs():
    """Очистка старых логов (более 5 дней)"""
    try:
        current_date = datetime.now()
        log_files = LOG_DIR.glob("*.log*")

        for log_file in log_files:
            try:
                if log_file.suffix == ".gz":
                    date_str = log_file.stem.split("_")[-1]
                else:
                    date_str = log_file.stem.split("_")[-1]

                file_date = datetime.strptime(date_str, "%Y-%m-%d")

                if (current_date - file_date).days > 5:
                    log_file.unlink()
                    logging.info(f"Удален старый лог: {log_file.name}")

            except (ValueError, IndexError):
                continue

    except Exception as e:
        logging.error(f"Ошибка при очистке старых логов: {e}")


def compress_old_logs():
    """Сжатие логов предыдущих дней"""
    try:
        log_files = LOG_DIR.glob("*.log")

        for log_file in log_files:
            if datetime.now().strftime("%Y-%m-%d") not in log_file.name:
                compressed_file = log_file.with_suffix(".log.gz")

                if not compressed_file.exists():
                    with open(log_file, "rb") as f_in:
                        with gzip.open(compressed_file, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)

                    log_file.unlink()
                    logging.info(
                        f"Сжат лог файл: {log_file.name} -> {compressed_file.name}"
                    )

    except Exception as e:
        logging.error(f"Ошибка при сжатии логов: {e}")


def extract_file_info(filename: str) -> Tuple[str, str, str]:
    """
    Извлекает хэш, timestamp и IP из имени файла
    Предполагает формат: [...hash...]timestamp_IPpart1_IPpart2_IPpart3_IPpart4.csv
    или [...hash1...][...hash2...]timestamp_IPpart1_IPpart2_IPpart3_IPpart4.csv
    """
    try:
        name_without_ext = filename[:-4] if filename.endswith(".csv") else filename
        logging.debug(f"Обработка имени файла: {name_without_ext}")

        ip_match = re.search(r"(\d+)_(\d+)_(\d+)_(\d+)(?:\.csv)?$", filename)
        if ip_match:
            ip_parts = ip_match.groups()
            ip = ".".join([str(int(part)) for part in ip_parts])
            logging.debug(f"Найден IP: {ip}")
        else:
            logging.error(
                f"Не найден IP-адрес в формате xxx_yyy_zzz_www в имени файла: {filename}"
            )
            return "", "", ""

        prefix_before_ip = name_without_ext[: ip_match.start() - 1]  # -1 для учета _

        timestamp_match = re.search(r"(\d{17})$", prefix_before_ip)
        if timestamp_match:
            timestamp = timestamp_match.group(1)
            logging.debug(f"Найден timestamp: {timestamp}")
        else:
            fallback_timestamp_match = re.search(r"(\d+)$", prefix_before_ip)
            if fallback_timestamp_match:
                timestamp = fallback_timestamp_match.group(1)
                logging.warning(f"Используется fallback для timestamp: {timestamp}")
            else:
                timestamp = ""
                logging.error(f"Не найден timestamp в имени файла: {filename}")
                return "", "", ""

        hash_part = prefix_before_ip[
            : timestamp_match.start() if timestamp_match else len(prefix_before_ip)
        ]

        logging.debug(
            f"Извлечена информация из файла {filename}: hash_part='{hash_part}', timestamp='{timestamp}', ip='{ip}'"
        )
        return hash_part, timestamp, ip
    except Exception as e:
        logging.error(f"Ошибка извлечения информации из файла {filename}: {e}")
        return "", "", ""


def group_files_by_ip(
    source_dir: Path, target_ips: List[str]
) -> Dict[str, List[Tuple[Path, str]]]:
    """
    Группирует файлы по IP адресам и сортирует по timestamp
    """
    ip_files = {}
    file_count = 0

    try:
        for file_path in source_dir.glob("*.csv"):
            hash_part, timestamp, ip = extract_file_info(file_path.name)
            file_count += 1

            if ip in target_ips:
                if ip not in ip_files:
                    ip_files[ip] = []
                ip_files[ip].append((file_path, timestamp))
                logging.info(f"Найден файл для IP {ip}: {file_path.name}")

        for ip in ip_files:
            ip_files[ip].sort(key=lambda x: x[1])
            logging.info(f"Для IP {ip} найдено {len(ip_files[ip])} файлов")

        logging.info(
            f"Всего обработано файлов: {file_count}, подходящих для целевых IP: {sum(len(files) for files in ip_files.values())}"
        )
        return ip_files

    except Exception as e:
        logging.error(f"Ошибка группировки файлов по IP: {e}")
        return {}


def determine_scenario(file_path: Path) -> str:
    """
    Определяет сценарий обработки на основе первых двух строк файла
    """
    try:
        with open(file_path, "r", encoding="cp866") as file:
            first_line = file.readline().strip()
            second_line = file.readline().strip()

        if first_line.startswith("A;") and second_line.startswith("I;"):
            scenario = "scenario1"
        elif first_line.startswith("K;") and second_line.startswith("K;"):
            scenario = "scenario2"
        elif first_line.startswith("D;") and (
            first_line[2:].strip().isdigit() or first_line[2:].strip() == "ALL"
        ):
            scenario = "scenario3"
        else:
            scenario = "unknown"

        logging.info(f"Для файла {file_path.name} определен сценарий: {scenario}")
        return scenario

    except Exception as e:
        logging.error(f"Ошибка определения сценария для файла {file_path}: {e}")
        return "unknown"


def process_scenario1(file_path: Path, ip: str) -> bool:
    """
    Обработка по первому сценарию с использованием шаблона template_goods.json
    """
    logging.info(f"Начало обработки по сценарию 1: {file_path.name} для IP {ip}")
    success = False

    try:
        if not goods_template.exists():
            logging.error(f"Шаблон не найден: {goods_template}")
            return False

        with open(goods_template, "r", encoding="utf-8") as f:
            template_data = json.load(f)

        replacements = 0
        for command in template_data:
            for param in command.get("command_input_list", []):
                if param.get("param_value") == "%device_ip%":
                    param["param_value"] = ip
                    replacements += 1
                elif param.get("param_value") == "%path_to_csv%":
                    param["param_value"] = str(file_path)
                    replacements += 1

        output_filename = f"config_{ip}.json"
        output_path = DESTINATION_DIR / output_filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(template_data, f, ensure_ascii=False, indent=2)

        logging.info(
            f"Конфигурационный файл создан: {output_path} (замен: {replacements})"
        )
        success = run_task_manager(str(output_path))

        cleanup_json_config(ip)

        return success

    except Exception as e:
        logging.error(f"Ошибка обработки сценария 1 для файла {file_path}: {e}")
        cleanup_json_config(ip)
        return False


def process_scenario2(file_path: Path, ip: str) -> bool:
    """
    Обработка по второму сценарию с использованием шаблона template_keys.json
    """
    logging.info(f"Начало обработки по сценарию 2: {file_path.name} для IP {ip}")
    success = False

    try:
        if not keys_template.exists():
            logging.error(f"Шаблон не найден: {keys_template}")
            return False

        with open(keys_template, "r", encoding="utf-8") as f:
            template_data = json.load(f)

        replacements = 0
        for command in template_data:
            for param in command.get("command_input_list", []):
                if param.get("param_value") == "%device_ip%":
                    param["param_value"] = ip
                    replacements += 1
                elif param.get("param_value") == "%path_to_csv%":
                    param["param_value"] = str(file_path)
                    replacements += 1

        output_filename = f"config_{ip}.json"
        output_path = DESTINATION_DIR / output_filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(template_data, f, ensure_ascii=False, indent=2)

        logging.info(
            f"Конфигурационный файл создан: {output_path} (замен: {replacements})"
        )
        success = run_task_manager(str(output_path))

        cleanup_json_config(ip)

        return success

    except Exception as e:
        logging.error(f"Ошибка обработки сценария 2 для файла {file_path}: {e}")
        cleanup_json_config(ip)
        return False


def process_scenario3(file_path: Path, ip: str) -> bool:
    """
    Обработка по третьему сценарию с использованием шаблона template_delete_goods.json или template_delete_all.json
    """
    logging.info(f"Начало обработки по сценарию 3: {file_path.name} для IP {ip}")
    success = False

    try:
        if not delete_goods_template.exists():
            logging.error(f"Шаблон не найден: {delete_goods_template}")
            return False
        if not delete_all_template.exists():
            logging.error(f"Шаблон не найден: {delete_all_template}")
            return False

        with open(delete_goods_template, "r", encoding="utf-8") as f:
            base_delete_template = json.load(f)

        with open(file_path, "r", encoding="cp866") as file:
            for line_num, line in enumerate(file, start=1):
                line = line.strip()
                number_str = line[2:]
                if number_str == "ALL":
                    with open(delete_all_template, "r", encoding="utf-8") as f:
                        template_data = json.load(f)
                    replacements = 0
                    for command in template_data:
                        for param in command.get("command_input_list", []):
                            if param.get("param_value") == "%device_ip%":
                                param["param_value"] = ip
                                replacements += 1

                    output_filename = f"config_{ip}.json"
                    output_path = DESTINATION_DIR / output_filename

                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(template_data, f, ensure_ascii=False, indent=2)

                    logging.info(
                        f"Конфигурационный файл создан: {output_path} (замен: {replacements})"
                    )
                    success = run_task_manager(str(output_path))

                    cleanup_json_config(ip)

                    return True
                else:
                    template_data = copy.deepcopy(base_delete_template)
                    replacements = 0
                    for command in template_data:
                        for param in command.get("command_input_list", []):
                            if param.get("param_value") == "%device_ip%":
                                param["param_value"] = ip
                                replacements += 1
                            elif param.get("param_value") == "%plu_number%":
                                param["param_value"] = str(number_str)
                                replacements += 1
                    output_filename = f"config_{ip}.json"
                    output_path = DESTINATION_DIR / output_filename

                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(template_data, f, ensure_ascii=False, indent=2)

                    logging.info(
                        f"Конфигурационный файл создан: {output_path} (замен: {replacements})"
                    )
                    success = run_task_manager(str(output_path))
                    if not success:
                        logging.error(
                            f"Ошибка удаления товара в строке {line_num} с PLU {number_str}"
                        )
                        cleanup_json_config(ip)
                        return False
        cleanup_json_config(ip)
        return True

    except Exception as e:
        logging.error(f"Ошибка обработки сценария 3 для файла {file_path}: {e}")
        cleanup_json_config(ip)
        return False


def analyze_connection_result(stdout: str, stderr: str) -> bool:
    """
    Анализирует вывод TaskManager для определения успешности подключения к устройству
    Простой анализ: ищем блок do_command 0 и проверяем наличие ключевых фраз ошибки
    Args:
        stdout: стандартный вывод
        stderr: вывод ошибок
    Returns:
        True если подключение успешно, False если есть ошибки подключения
    """
    # Объединяет оба вывода для анализа
    full_output = (stdout or "") + (stderr or "")

    # Ищет блок выполнения команды 0 (подключение)
    if "do_command 0" not in full_output:
        logging.warning("Не найдена команда подключения (do_command 0) в выводе")
        return False

    # Ищет строку "Result code for command 0 : <число>" в *всем* выводе
    # re.search ищет первое вхождение паттерна, можно будет отлавливать результат любой команды
    # r"Result code for command 0\s*:\s*(-?\d+)"
    #   - Result code for command 0 : - искомая строка
    #   - \s* - любое количество пробельных символов (включая 0)
    #   - (-?\d+) - захватывающая группа: опциональный минус и одна или более цифр (целое число)
    match = re.search(r"Result code for command 0\s*:\s*(-?\d+)", full_output)

    if match:
        result_code_str = match.group(1)
        try:
            result_code = int(result_code_str)  # Преобразуем в целое число
            logging.debug(f"Найден код результата команды 0: {result_code}")

            if result_code != 0:
                logging.error(
                    f"Найден код ошибки подключения: 'Result code for command 0 : {result_code}'"
                )
                return False  # Подключение неуспешно
            else:
                # Код 0 - успешное выполнение команды подключения
                logging.info("Код результата команды 0 равен 0 - подключение успешно")
                return True
        except ValueError:
            # Если не удалось преобразовать строку в число (маловероятно с текущим паттерном, но на всякий случай)
            logging.error(
                f"Ошибка преобразования кода результата в число: '{result_code_str}'"
            )
            return False
    else:
        if "'connect' error=-1" in full_output:
            logging.error(f"Найдена ошибка подключения: ''connect' error=-1'")
            return False

        logging.warning(
            "Не найдена строка с кодом результата для команды 0 (Result code for command 0 : ...)"
        )
        return False


def run_task_manager(config_path: str) -> bool:
    """
    Запускает TaskManager с указанным конфигурационным файлом
    Анализирует вывод для определения успешности подключения к устройству
    """
    logging.info(f"Запуск TaskManager с конфигом: {config_path}")

    if not os.path.exists(TASK_MANAGER):
        logging.error(f"Файл TaskManager не найден: {TASK_MANAGER}")
        return False

    if not os.path.exists(config_path):
        logging.error(f"Конфигурационный файл не найден: {config_path}")
        return False

    try:
        result = subprocess.run(
            [str(TASK_MANAGER), config_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=300,
            shell=False,
        )

        # Анализирует вывод для определения успешности подключения
        connection_success = analyze_connection_result(result.stdout, result.stderr)
        # Можно ещё проверок накидать, но пока условный пинг

        if result.returncode == 0:
            logging.info("TaskManager завершен с кодом возврата 0")
        else:
            logging.warning(
                f"TaskManager завершен с кодом возврата {result.returncode}"
            )

        if result.stdout:
            logging.debug(f"STDOUT TaskManager: {result.stdout}")
        if result.stderr:
            logging.debug(f"STDERR TaskManager: {result.stderr}")

        if connection_success:
            logging.info("Подключение к устройству успешно установлено")
            return True
        else:
            logging.error("Ошибка подключения к устройству")
            return False

    except Exception as e:
        logging.error(f"Неожиданная ошибка при запуске TaskManager: {e}")
        return False


def move_processed_file(file_path: Path, ip: str, timestamp: str) -> Path:
    """
    Перемещает файл из исходной директории в DESTINATION_DIR с новым именем

    Returns:
        Путь к перемещенному файлу в DESTINATION_DIR
    """
    try:
        if not DESTINATION_DIR.exists():
            DESTINATION_DIR.mkdir(parents=True, exist_ok=True)
            logging.info(f"Создана директория: {DESTINATION_DIR}")

        new_filename = f"{timestamp}_{ip}.csv"
        destination_path = DESTINATION_DIR / new_filename

        counter = 1
        original_destination = destination_path
        while destination_path.exists():
            name_parts = original_destination.stem, original_destination.suffix
            new_name = f"{name_parts[0]}_{counter}{name_parts[1]}"
            destination_path = DESTINATION_DIR / new_name
            counter += 1

        shutil.move(str(file_path), str(destination_path))
        logging.info(
            f"Файл перемещен в рабочую директорию: {file_path.name} -> {destination_path.name}"
        )
        return destination_path

    except Exception as e:
        logging.error(f"Ошибка перемещения файла {file_path}: {e}")
        raise


def delete_old_files(
    directory: Path, days: int = 5, pattern: str = "*"
) -> Tuple[int, int]:
    """
    Удаляет файлы старше указанного количества дней в директории

    Args:
        directory: Путь к директории для очистки
        days: Количество дней (файлы старше этого возраста будут удалены)
        pattern: Шаблон для поиска файлов (например, "*.csv", "*.log")

    Returns:
        Кортеж (удалено_файлов, удалено_папок)
    """
    try:
        if not directory.exists():
            logging.warning(f"Директория для очистки не существует: {directory}")
            return 0, 0

        # Вычисляем пороговую дату
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        deleted_files = 0
        deleted_dirs = 0

        logging.info(
            f"Начало очистки директории {directory} (файлы старше {days} дней)"
        )

        for item in directory.rglob(pattern):
            try:
                # Получаем время последнего изменения файла
                file_time = item.stat().st_mtime

                if file_time < cutoff_time:
                    if item.is_file():
                        item.unlink()
                        deleted_files += 1
                        logging.debug(f"Удален старый файл: {item.name}")
                    elif item.is_dir():
                        if not any(item.iterdir()):
                            item.rmdir()
                            deleted_dirs += 1
                            logging.debug(f"Удалена пустая папка: {item.name}")

            except Exception as e:
                logging.error(f"Ошибка удаления {item}: {e}")
                continue

        logging.info(
            f"Очистка завершена. Удалено файлов: {deleted_files}, папок: {deleted_dirs}"
        )
        return deleted_files, deleted_dirs

    except Exception as e:
        logging.error(f"Критическая ошибка при очистке директории {directory}: {e}")
        return 0, 0


def main():
    """Основная функция скрипта"""
    # Настройка логирования
    if not setup_logging():
        print("Не удалось настроить логирование. Завершение работы.")
        sys.exit(1)

    try:
        # Очистка и сжатие старых логов
        cleanup_old_logs()
        compress_old_logs()

        # Создание директорий для результатов
        if not setup_directories():
            logging.error("Не удалось создать необходимые директории")
            sys.exit(1)

        logging.info("=" * 50)
        logging.info("Начало обработки файлов")
        logging.info(f"Целевые IP: {', '.join(TARGET_IPS)}")
        logging.info(f"Исходная папка: {SOURCE_DIR}")
        logging.info(f"Рабочая папка: {DESTINATION_DIR}")
        logging.info(f"Папка успешных: {SUCCEED_DIR}")
        logging.info(f"Папка ошибок: {ERROR_DIR}")

        # Проверяет существование исходной папки
        if not SOURCE_DIR.exists():
            logging.error(f"Исходная папка не существует: {SOURCE_DIR}")
            sys.exit(1)

        # Группирует файлы по IP
        ip_files = group_files_by_ip(SOURCE_DIR, TARGET_IPS)

        # Проверяет есть ли файлы для обработки
        if not ip_files:
            logging.warning("Файлы с указанными IP адресами не найдены")
            logging.info("Завершение работы")
            return

        logging.info(f"Найдены файлы для IP: {list(ip_files.keys())}")

        # Статистика обработки
        processed_count = 0
        error_count = 0
        succeed_files = []
        error_files = []

        # Обрабатывает файлы для каждого IP
        for ip, files in ip_files.items():
            logging.info(f"Обработка файлов для IP {ip}: найдено {len(files)} файлов")

            for file_path, timestamp in files:
                logging.info(
                    f"Обработка файла: {file_path.name} (timestamp: {timestamp})"
                )
                current_file_path = None

                try:
                    # Перемещает файл в рабочую директорию
                    current_file_path = move_processed_file(file_path, ip, timestamp)

                    # Определяет сценарий обработки
                    scenario = determine_scenario(current_file_path)

                    # Обрабатывает файл по соответствующему сценарию
                    success = False
                    if scenario == "scenario1":
                        success = process_scenario1(current_file_path, ip)
                    elif scenario == "scenario2":
                        success = process_scenario2(current_file_path, ip)
                    elif scenario == "scenario3":
                        success = process_scenario3(current_file_path, ip)
                    else:
                        logging.warning(
                            f"Неизвестный сценарий для файла {current_file_path.name}"
                        )
                        success = False

                    # Перемещает файл в соответствующую директорию результата
                    move_success = move_file_to_result_dir(current_file_path, success)

                    if success and move_success:
                        processed_count += 1
                        succeed_files.append(current_file_path.name)
                        logging.info(
                            f"Файл успешно обработан: {current_file_path.name}"
                        )
                    else:
                        error_count += 1
                        error_files.append(current_file_path.name)
                        logging.error(
                            f"Файл обработан с ошибками: {current_file_path.name}"
                        )

                except Exception as e:
                    error_count += 1
                    if current_file_path:
                        error_files.append(current_file_path.name)
                        # Пытается переместить файл в ERROR даже при критической ошибке
                        try:
                            move_file_to_result_dir(current_file_path, False)
                        except:
                            pass  # Игнорируем ошибки при перемещении
                    logging.error(
                        f"Критическая ошибка обработки файла {file_path.name}: {e}"
                    )

        # Финальная статистика
        delete_old_files(SOURCE_DIR)
        delete_old_files(ERROR_DIR)
        delete_old_files(SUCCEED_DIR)
        logging.info("=" * 50)
        logging.info(f"ОБРАБОТКА ЗАВЕРШЕНА")
        logging.info(f"Успешно обработано: {processed_count} файлов")
        logging.info(f"С ошибками: {error_count} файлов")
        logging.info(f"Всего: {processed_count + error_count} файлов")

        if succeed_files:
            logging.info(f"Успешные файлы: {', '.join(succeed_files)}")
        if error_files:
            logging.warning(f"Файлы с ошибками: {', '.join(error_files)}")

        if error_count > 0:
            logging.warning("Были ошибки при обработке файлов")

    except Exception as e:
        logging.critical(f"Критическая ошибка в основной функции: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
