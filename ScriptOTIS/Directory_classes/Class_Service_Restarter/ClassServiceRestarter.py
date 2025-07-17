import subprocess
import time
from typing import List
from pathlib import Path
import logging
import os


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PLINK_DIR = os.path.join(CURRENT_DIR, "Plink")
COMMAND_FILE_CCM = os.path.join(PLINK_DIR, "ccm_commands.txt")
COMMAND_FILE_UNZIP = os.path.join(PLINK_DIR, "unzip_commands.txt")
SSH_USER = "otis"
SSH_PASSWORD = "MzL2qqOp"
PLINK_PATH = os.path.join(PLINK_DIR, "plink.exe")
PING_TIMEOUT = 1000  # мс
PLINK_TIMEOUT = 300  # секунды (5 минут)

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(CURRENT_DIR, "service_restarter.log")),
        logging.StreamHandler(),
    ],
)


class ServiceRestarter:
    def __init__(self):
        self.config_dir = CURRENT_DIR
        self.user = SSH_USER
        self.password = SSH_PASSWORD
        self.plink_path = Path(PLINK_PATH)

    def restart_service_with_plink(self, servers: List[str], command_file: str) -> bool:
        """Перезапускает службу на серверах используя PLINK"""
        try:
            # Проверяем наличие необходимых файлов
            command_filepath: Path = Path(command_file)
            if not command_filepath.exists():
                logging.error(f"Файл команд {command_file} не найден")
                return False

            if not self.plink_path.exists():
                logging.error("plink.exe не найден")
                return False

            # Обрабатываем каждый сервер
            failed_servers = []
            for server_info in servers:
                # Извлекаем IP из формата "индекс-тип-ip-версия"
                parts = server_info.split("-")
                if len(parts) < 3:
                    logging.error(f"Неверный формат строки сервера: {server_info}")
                    failed_servers.append(server_info)
                    continue

                server_ip = parts[2]
                server_index = parts[0]

                # Проверяем доступность через ping
                if not self._check_ping(server_ip):
                    logging.warning(
                        f"Сервер {server_ip} (индекс {server_index}) недоступен по ping"
                    )
                    failed_servers.append(server_info)
                    continue

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

                try:
                    logging.info(
                        f"Выполнение команд на сервере {server_ip} (индекс {server_index})"
                    )

                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=300,  # 5 минут таймаут
                        encoding="cp1251",
                    )

                    if result.returncode == 0:
                        logging.info(f"Команды успешно выполнены на {server_ip}")
                        if result.stdout:
                            logging.debug(f"Вывод: {result.stdout}")
                    else:
                        logging.error(
                            f"Ошибка выполнения на {server_ip}: {result.stderr}"
                        )
                        failed_servers.append(server_info)

                except subprocess.TimeoutExpired:
                    logging.error(f"Таймаут выполнения команд на {server_ip}")
                    failed_servers.append(server_info)
                except Exception as e:
                    logging.error(f"Ошибка при работе с {server_ip}: {str(e)}")
                    failed_servers.append(server_info)

                # Пауза между серверами для снижения нагрузки
                time.sleep(2)

            # Итоговая проверка
            if failed_servers:
                logging.error(f"Не удалось обработать серверы: {failed_servers}")
                return False

            logging.info("Все серверы успешно обработаны")
            return True

        except Exception as e:
            logging.error(f"Критическая ошибка в restart_service_with_plink: {str(e)}")
            return False

    def _check_ping(self, host: str) -> bool:
        """Проверка доступности хоста через ping"""
        try:
            result = subprocess.run(
                ["ping", "-n", "1", "-w", "1000", host], capture_output=True, text=True
            )
            return "TTL=" in result.stdout
        except:
            return False


def main():
    # config_dir = PLINK_DIR  # Укажите правильный путь
    servers = [
        "0-CENTRUM-10.9.30.101-10.4.16.5",
        "98989-RETAIL-10.9.30.102-10.4.16.5",
    ]  # Список серверов в формате "индекс-тип-ip-версия"
    command_file = COMMAND_FILE_UNZIP  # Файл с командами для выполнения

    restarter = ServiceRestarter()
    success = restarter.restart_service_with_plink(servers, command_file)

    if success:
        logging.info("Все службы успешно перезапущены!")
    else:
        logging.error("Возникли ошибки при перезапуске служб.")


if __name__ == "__main__":
    main()
