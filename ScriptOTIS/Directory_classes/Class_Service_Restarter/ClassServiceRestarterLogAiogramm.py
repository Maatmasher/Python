import asyncio
import subprocess
import time
from typing import List
from pathlib import Path
import logging
import os
from aiogram import Bot, exceptions
from aiogram.client.default import DefaultBotProperties

# ==================== КОНФИГУРАЦИОННЫЕ ПАРАМЕТРЫ ====================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PLINK_DIR = os.path.join(CURRENT_DIR, "Plink")
COMMAND_FILE_CCM = os.path.join(PLINK_DIR, "ccm_commands.txt")
COMMAND_FILE_UNZIP = os.path.join(PLINK_DIR, "unzip_commands.txt")
SSH_USER = "otis"
SSH_PASSWORD = "MzL2qqOp"
PLINK_PATH = os.path.join(PLINK_DIR, "plink.exe")
PING_TIMEOUT = 1000  # мс
PLINK_TIMEOUT = 300  # сек (5 мин)

# --- Настройки Telegram-бота ---------------------------------------
TG_BOT_TOKEN = (
    "550546110:AAGmgVKJveoNUgZK34g4lEVe5ebRxbd73Sk"  # токен, выданный @BotFather
)
TG_DESTINATION_CHAT = -240451454  # ID чата (отрицательный для групп)
TG_LOG_LEVEL = logging.INFO  # что отправлять в TG
TG_MAX_MESSAGE_LEN = 4096  # лимит Telegram
# ===================================================================

# === Telegram-обработчик логов =====================================
#from aiogram import Bot, exceptions  # импорт после конфигурации, чтобы не ломать pylint


class TelegramLogHandler(logging.Handler):
    """
    При вызове emit() сообщение отправляется в чат.
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: int | str,
        level: int = logging.INFO,
        fmt: str | None = "%(asctime)s | %(levelname)s | %(message)s",
    ):
        super().__init__(level)
        default_props = DefaultBotProperties(parse_mode="HTML")
        self.bot = Bot(token=bot_token, default=default_props)
        self.chat_id = chat_id
        self.setFormatter(logging.Formatter(fmt))

    async def _async_send(self, text: str) -> None:
        for i in range(0, len(text), TG_MAX_MESSAGE_LEN):
            await self.bot.send_message(self.chat_id, text[i : i + TG_MAX_MESSAGE_LEN])

    def emit(self, record: logging.LogRecord) -> None:  # типизация уже верная
        try:
            message = self.format(record)
            asyncio.run(self._async_send(message))
        except exceptions.TelegramAPIError:
            # Telegram был недоступен — записываем проблему в стандартную систему логов,
            # передаём оригинальный record, а не None!
            super().handleError(record)
        except Exception:
            # При других ошибках поступаем так же
            super().handleError(record)


# ===================================================================

# === Настройка "обычного" логгера ==================================
log_file_path = os.path.join(CURRENT_DIR, "service_restarter.log")

root_logger = logging.getLogger()  # корневой логгер
root_logger.setLevel(logging.DEBUG)

# вывод в файл
file_handler = logging.FileHandler(log_file_path, encoding="utf-8", mode="w")
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
root_logger.addHandler(file_handler)

# вывод в консоль
console_handler = logging.StreamHandler()
console_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
root_logger.addHandler(console_handler)

# вывод в Telegram
tg_handler = TelegramLogHandler(
    bot_token=TG_BOT_TOKEN, chat_id=TG_DESTINATION_CHAT, level=TG_LOG_LEVEL
)
root_logger.addHandler(tg_handler)
# ===================================================================


class ServiceRestarter:
    def __init__(self):
        logging.debug("Инициализация ServiceRestarter")
        self.config_dir = Path(CURRENT_DIR)
        self.user = SSH_USER
        self.password = SSH_PASSWORD
        self.plink_path = Path(PLINK_PATH)
        logging.debug(f"Конфигурация: plink_path={self.plink_path}, user={self.user}")

    def restart_service_with_plink(self, servers: List[str], command_file: str) -> bool:
        """Перезапускает службу на серверах, используя PLINK"""
        logging.info(f"Начало обработки {len(servers)} серверов")
        try:
            command_filepath = Path(command_file)
            if not command_filepath.exists():
                logging.error(f"Файл команд {command_file} не найден")
                return False

            if not self.plink_path.exists():
                logging.error("plink.exe не найден")
                return False

            failed_servers: List[str] = []
            for server_info in servers:
                logging.info(f"Обработка сервера: {server_info}")
                parts = server_info.split("-")
                if len(parts) < 3:
                    logging.error(f"Неверный формат строки сервера: {server_info}")
                    failed_servers.append(server_info)
                    continue

                server_ip = parts[2]
                server_index = parts[0]

                if not self._check_ping(server_ip):
                    logging.warning(
                        f"Сервер {server_ip} (индекс {server_index}) недоступен по ping"
                    )
                    failed_servers.append(server_info)
                    continue

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
                            f"Ошибка выполнения на {server_ip}: "
                            f"Код {result.returncode}. Stderr: {result.stderr}"
                        )
                        failed_servers.append(server_info)
                except subprocess.TimeoutExpired:
                    logging.error(f"Таймаут выполнения команд на {server_ip}")
                    failed_servers.append(server_info)
                except Exception as e:  # noqa: BLE001
                    logging.exception(
                        f"Неожиданная ошибка при работе с {server_ip}: {e}"
                    )
                    failed_servers.append(server_info)

                time.sleep(2)  # пауза между серверами

            if failed_servers:
                logging.error(
                    f"Не удалось обработать {len(failed_servers)} серверов: {failed_servers}"
                )
                return False

            logging.info("Все серверы успешно обработаны")
            return True

        except Exception as e:  # noqa: BLE001
            logging.exception(f"Критическая ошибка: {e}")
            return False

    @staticmethod
    def _check_ping(host: str) -> bool:
        """Проверка доступности хоста через ping"""
        result = subprocess.run(
            ["ping", "-n", "1", "-w", str(PING_TIMEOUT), host],
            capture_output=True,
            text=True,
        )
        return "TTL=" in result.stdout


def main() -> None:
    logging.info("=== Запуск программы ===")
    servers = ["0-CENTRUM-10.9.30.101-10.4.16.5", "98989-RETAIL-10.9.30.102-10.4.16.5"]
    restarter = ServiceRestarter()
    ok = restarter.restart_service_with_plink(servers, COMMAND_FILE_CCM)
    logging.log(
        logging.INFO if ok else logging.ERROR,
        (
            "Все службы успешно перезапущены!"
            if ok
            else "Возникли ошибки при перезапуске служб."
        ),
    )
    logging.info("=== Завершение программы ===")


if __name__ == "__main__":
    main()
