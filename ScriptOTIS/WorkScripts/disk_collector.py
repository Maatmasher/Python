#!/usr/bin/env python3

import paramiko
import threading
import csv
import json
import time
import logging
import os
import getpass
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime


class DiskInfoCollector:
    def __init__(self, username, password=None, max_workers=50):
        self.username = username
        self.password = password
        self.max_workers = max_workers
        self.results = []
        self.errors = []
        self.lock = threading.Lock()

        # Получаем текущую директорию скрипта
        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        # Настройка логирования в текущей директории
        log_file = os.path.join(self.script_dir, "disk_collector.log")
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8"),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Рабочая директория: {self.script_dir}")

        # Запрос пароля, если не указан
        if not self.password:
            self.password = getpass.getpass(
                f"Введите пароль для пользователя {self.username}: "
            )

    def get_file_path(self, filename):
        """Получение полного пути к файлу в директории скрипта"""
        return os.path.join(self.script_dir, filename)

    def load_hosts_from_json(self, json_filename):
        """Загрузка хостов из JSON файла в текущей директории"""
        json_file_path = self.get_file_path(json_filename)

        try:
            if not os.path.exists(json_file_path):
                self.logger.error(
                    f"Файл {json_filename} не найден в директории {self.script_dir}"
                )
                return []

            with open(json_file_path, "r", encoding="utf-8") as f:
                hosts_data = json.load(f)

            hosts_info = []
            for ip, details in hosts_data.items():
                host_info = {
                    "ip": ip,
                    "server_ip": details.get("server_ip", "N/A"),
                    "type": details.get("type", "N/A"),
                    "status": details.get("status", "N/A"),
                }
                hosts_info.append(host_info)

            self.logger.info(f"Загружено {len(hosts_info)} хостов из {json_file_path}")
            return hosts_info

        except json.JSONDecodeError as e:
            self.logger.error(f"Ошибка парсинга JSON файла: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке JSON файла: {str(e)}")
            return []

    def collect_from_host(self, host_info):
        """Сбор информации о диске с одного хоста"""
        host_ip = host_info["ip"]
        start_time = time.time()

        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Подключение с паролем
            ssh.connect(
                host_ip,
                username=self.username,
                password=self.password,
                timeout=10,
                banner_timeout=10,
                auth_timeout=10,
                look_for_keys=False,  # Не искать SSH ключи
                allow_agent=False,  # Не использовать SSH агент
            )

            # Выполнение команды для получения информации о /dev/sda1
            stdin, stdout, stderr = ssh.exec_command(
                "df -h /dev/sda1 2>/dev/null | tail -1 || echo 'ERROR: /dev/sda1 not found'"
            )

            output = stdout.read().decode().strip()
            error_output = stderr.read().decode().strip()

            if output and not output.startswith("ERROR"):
                parts = output.split()
                if len(parts) >= 5:
                    # Проверяем, что первая колонка содержит /dev/sda1
                    if "/dev/sda1" in parts[0]:
                        execution_time = round(time.time() - start_time, 2)

                        with self.lock:
                            self.results.append(
                                {
                                    "IP": host_ip,
                                    # 'Server_IP': host_info['server_ip'],
                                    # 'Type': host_info['type'],
                                    # 'Status': host_info['status'],
                                    # 'Filesystem': parts[0],
                                    "Size": parts[1],
                                    "Used": parts[2],
                                    "Available": parts[3],
                                    "Use%": parts[4],
                                    # 'Mounted_on': parts[5] if len(parts) > 5 else '/',
                                    "Collection_Time": datetime.now().strftime(
                                        "%Y-%m-%d %H:%M:%S"
                                    ),
                                    "Response_Time": f"{execution_time}s",
                                }
                            )

                        self.logger.info(
                            f"✓ {host_ip}: успешно собрана информация ({execution_time}s)"
                        )
                    else:
                        self._log_error(
                            host_ip, "Filesystem не содержит /dev/sda1", host_info
                        )
                else:
                    self._log_error(host_ip, "Неверный формат вывода df", host_info)
            else:
                self._log_error(host_ip, f"Ошибка: {output or error_output}", host_info)

        except paramiko.AuthenticationException as e:
            self._log_error(
                host_ip, f"Ошибка аутентификации: неверный пароль", host_info
            )
        except paramiko.SSHException as e:
            self._log_error(host_ip, f"SSH ошибка: {str(e)}", host_info)
        except Exception as e:
            self._log_error(host_ip, f"Общая ошибка: {str(e)}", host_info)
        finally:
            try:
                ssh.close()  # type: ignore
            except:
                pass

    def _log_error(self, host_ip, error_msg, host_info):
        """Логирование ошибок"""
        with self.lock:
            self.errors.append(
                {
                    "IP": host_ip,
                    "Server_IP": host_info["server_ip"],
                    "Type": host_info["type"],
                    "Status": host_info["status"],
                    "Error": error_msg,
                    "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        self.logger.error(f"✗ {host_ip}: {error_msg}")

    def collect_all(self, json_filename, output_filename, errors_filename="errors.csv"):
        """Сбор данных со всех хостов"""
        # Загрузка хостов из JSON в текущей директории
        hosts_info = self.load_hosts_from_json(json_filename)

        if not hosts_info:
            self.logger.error("Не удалось загрузить хосты из JSON файла")
            return

        # Фильтрация только активных хостов (опционально)
        active_hosts = [h for h in hosts_info if h["status"] == "ACTIVE"]
        self.logger.info(f"Активных хостов: {len(active_hosts)} из {len(hosts_info)}")

        # Выбор хостов для обработки
        hosts_to_process = active_hosts

        start_time = time.time()
        self.logger.info(f"Начинаем сбор данных с {len(hosts_to_process)} хостов...")

        # Параллельное выполнение
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            executor.map(self.collect_from_host, hosts_to_process)

        total_time = round(time.time() - start_time, 2)

        # Сохранение успешных результатов
        output_file_path = self.get_file_path(output_filename)
        if self.results:
            with open(output_file_path, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = [
                    "IP",
                    # 'Server_IP',
                    # 'Type',
                    # 'Status',
                    # 'Filesystem',
                    "Size",
                    "Used",
                    "Available",
                    "Use%",
                    # 'Mounted_on',
                    "Collection_Time",
                    "Response_Time",
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.results)

            self.logger.info(f"✓ Результаты сохранены в {output_file_path}")

        # Сохранение ошибок
        errors_file_path = self.get_file_path(errors_filename)
        if self.errors:
            with open(errors_file_path, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = ["IP", "Server_IP", "Type", "Status", "Error", "Time"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.errors)

            self.logger.info(f"✗ Ошибки сохранены в {errors_file_path}")

        # Статистика
        self.print_statistics(len(hosts_to_process), total_time)

    def print_statistics(self, total_hosts, total_time):
        """Вывод статистики"""
        successful = len(self.results)
        failed = len(self.errors)

        print("\n" + "=" * 50)
        print("СТАТИСТИКА СБОРА ДАННЫХ")
        print("=" * 50)
        print(f"Рабочая директория: {self.script_dir}")
        print(f"Всего хостов обработано: {total_hosts}")
        print(f"Успешно: {successful}")
        print(f"Ошибок: {failed}")
        print(f"Успешность: {round(successful/total_hosts*100, 2)}%")
        print(f"Общее время выполнения: {total_time}s")
        print(f"Среднее время на хост: {round(total_time/total_hosts, 2)}s")
        print("=" * 50)


def load_config(config_filename="config.json"):
    """Загрузка конфигурации из файла"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(script_dir, config_filename)

    try:
        with open(config_file_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Не логируем пароль в конфиге для безопасности
            config_copy = config.copy()
            if "password" in config_copy:
                config_copy["password"] = "***"
            print(f"Конфигурация загружена: {config_copy}")
            return config
    except FileNotFoundError:
        print(
            f"Файл конфигурации {config_filename} не найден, используются значения по умолчанию"
        )
        return {
            "ssh_username": "tc",
            "max_workers": 50,
            "timeout": 10,
            "output_file": "disk_usage_results.csv",
            "errors_file": "collection_errors.csv",
        }


def get_password_from_user():
    """Безопасный ввод пароля"""
    while True:
        password = getpass.getpass("Введите SSH пароль: ")
        if password:
            confirm_password = getpass.getpass("Подтвердите пароль: ")
            if password == confirm_password:
                return password
            else:
                print("Пароли не совпадают. Попробуйте еще раз.")
        else:
            print("Пароль не может быть пустым.")


def list_files_in_directory():
    """Показать файлы в текущей директории"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"\nФайлы в рабочей директории {script_dir}:")
    try:
        files = os.listdir(script_dir)
        for file in sorted(files):
            file_path = os.path.join(script_dir, file)
            if os.path.isfile(file_path):
                size = os.path.getsize(file_path)
                print(f"  {file} ({size} байт)")
    except Exception as e:
        print(f"Ошибка при получении списка файлов: {e}")


# Пример использования
if __name__ == "__main__":
    # Показать файлы в текущей директории
    list_files_in_directory()

    # Загрузка конфигурации
    config = load_config()

    # Получение пароля
    password = None
    if "password" in config:
        password = config["password"]
        print("Пароль загружен из конфигурации")
    else:
        password = get_password_from_user()

    # Создание экземпляра коллектора
    collector = DiskInfoCollector(
        username=config["ssh_username"],
        password=password,
        max_workers=config["max_workers"],
    )

    # Запуск сбора данных
    collector.collect_all(
        json_filename="cash_ip_all.json",
        output_filename=config["output_file"],
        errors_filename=config["errors_file"],
    )
