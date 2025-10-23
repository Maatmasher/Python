# telegram_logger.py
import logging
import httpx
import keyring
from getpass import getpass
import re

# Идентификаторы для keyring
SERVICE_NAME = "TelegramLogger"
BOT_TOKEN_USERNAME = "bot_token"
CHAT_ID_USERNAME = "chat_id"

class NoNetworkFilter(logging.Filter):
    """
    Фильтр, исключающий логи от httpx, urllib3 и других сетевых библиотек.
    """
    def filter(self, record):
        # Проверяем, начинается ли имя логгера с одного из этих префиксов
        if record.name.startswith(('httpx', 'urllib3', 'requests')):
            return False
        return True

class TelegramHandler(logging.Handler):
    """
    Кастомный Handler для отправки логов в Telegram через Bot API.
    """
    def __init__(self, bot_token: str, chat_id: str, level: int = logging.WARNING):
        super().__init__(level=level)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        # Добавляем фильтр
        self.addFilter(NoNetworkFilter())

    def emit(self, record):
        log_message = self.format(record)
        # --- НАЧАЛО НОВОГО КОДА ---
        # Убираем токен из URL, если он вдруг попал в сообщение
        log_message = re.sub(r'bot[\w\d_:.-]+', 'bot***', log_message, flags=re.IGNORECASE)
        # --- КОНЕЦ НОВОГО КОДА ---
        try:
            httpx.post(
                self.url,
                data={
                    'chat_id': self.chat_id,
                    'text': log_message,
                    'parse_mode': 'HTML'
                },
                timeout=5.0
            )
        except Exception:
            # Если не удалось отправить, выводим в stderr
            self.handleError(record)

def get_telegram_credentials():
    """
    Получает токен и chat_id из keyring, если они там есть.
    Если нет — запрашивает у пользователя и сохраняет.
    """
    token = keyring.get_password(SERVICE_NAME, BOT_TOKEN_USERNAME)
    chat_id = keyring.get_password(SERVICE_NAME, CHAT_ID_USERNAME)

    if not token:
        token = getpass("Введите Telegram Bot Token: ")
        keyring.set_password(SERVICE_NAME, BOT_TOKEN_USERNAME, token)
        print("Bot Token сохранён в keyring.")

    if not chat_id:
        chat_id = getpass("Введите Telegram Chat ID: ")
        keyring.set_password(SERVICE_NAME, CHAT_ID_USERNAME, chat_id)
        print("Chat ID сохранён в keyring.")

    return token, chat_id

def setup_telegram_logging(
    log_level: int = logging.WARNING,
    log_format: str = None,
):
    """
    Настраивает TelegramHandler и добавляет его к корневому логгеру.
    Это позволяет логгировать всё, что использует logging, кроме сетевых библиотек.
    """
    bot_token, chat_id = get_telegram_credentials()

    # Проверим, не добавлен ли уже TelegramHandler к root_logger
    root_logger = logging.getLogger()
    if any(isinstance(handler, TelegramHandler) for handler in root_logger.handlers):
        logging.info("TelegramHandler уже добавлен к корневому логгеру.")
        return

    telegram_handler = TelegramHandler(bot_token=bot_token, chat_id=chat_id, level=log_level)

    # Устанавливаем формат, аналогичный остальным хендлерам
    formatter = logging.Formatter(log_format or "%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    telegram_handler.setFormatter(formatter)

    # Добавляем к корневому логгеру, чтобы перехватывать все сообщения
    root_logger.addHandler(telegram_handler)

    logging.info("TelegramHandler успешно добавлен к корневому логгеру.")