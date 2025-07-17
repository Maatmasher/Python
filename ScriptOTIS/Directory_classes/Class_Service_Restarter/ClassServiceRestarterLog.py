import subprocess
import time
from typing import List
from pathlib import Path
import logging
import os

# ==================== КОНФИГУРАЦИОННЫЕ ПАРАМЕТРЫ ====================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PLINK_DIR = os.path.join(CURRENT_DIR, "Plink")
COMMAND_FILE_CCM = os.path.join(PLINK_DIR, "ccm_commands.txt")
COMMAND_FILE_UNZIP = os.path.join(PLINK_DIR, "unzip_commands.txt")
SSH_USER = "otis"
SSH_PASSWORD = "MzL2qqOp"
PLINK_PATH = os.path.join(PLINK_DIR, "plink.exe")
PING_TIMEOUT = 1000  # мс
PLINK_TIMEOUT = 300  # секунды (5 минут)
# ====================================================================

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(CURRENT_DIR, "service_restarter.log"),
            encoding="utf-8",
            mode="w",  # 'a' - дописывать, 'w' - перезаписывать
        ),
        logging.StreamHandler(),
    ],
)


class ServiceRestarter:
    def __init__(self):
        logging.debug("Инициализация ServiceRestarter")
        self.config_dir = Path(CURRENT_DIR)
        self.user = SSH_USER
        self.password = SSH_PASSWORD
        self.plink_path = Path(PLINK_PATH)
        logging.debug(f"Конфигурация: plink_path={self.plink_path}, user={self.user}")

    def restart_service_with_plink(self, servers: List[str], command_file: str) -> bool:
        """Перезапускает службу на серверах используя PLINK"""
        logging.info(f"Начало обработки {len(servers)} серверов")
        try:
            # Проверяем наличие необходимых файлов
            command_filepath = Path(command_file)
            logging.debug(f"Проверка существования файла команд: {command_filepath}")

            if not command_filepath.exists():
                logging.error(f"Файл команд {command_file} не найден")
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
                f"Критическая ошибка в restart_service_with_plink: {str(e)}",
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


def main():
    logging.info("=== Запуск программы ===")
    servers = [
        "0-CENTRUM-10.9.30.101-10.4.16.5",
        "98989-RETAIL-10.9.30.102-10.4.16.5",
    ]
    command_file = COMMAND_FILE_CCM

    logging.info(f"Используется файл команд: {command_file}")
    logging.info(f"Список серверов: {servers}")

    restarter = ServiceRestarter()
    success = restarter.restart_service_with_plink(servers, command_file)

    if success:
        logging.info("Все службы успешно перезапущены!")
    else:
        logging.error("Возникли ошибки при перезапуске служб.")

    logging.info("=== Завершение программы ===")


if __name__ == "__main__":
    main()
