import subprocess
import keyring
import logging
import paramiko
from getpass import getpass
from typing import Optional

# Глобальные константы
PLINK_PATH: str = "plink"  # Путь к исполняемому файлу PuTTY plink
SSH_USER: str = "default_user"
CENTRUM_HOST: str = "example.com"
SERVICE_NAME: str = "my_service"

# Инициализация логгера (если не используется внешний)
logger = logging.getLogger(__name__)


def test_password(
    password: str,
    plink_path: str = PLINK_PATH,
    ssh_user: str = SSH_USER,
    centrum_host: str = CENTRUM_HOST,
    logger_instance: Optional[logging.Logger] = None,
) -> bool:
    """
    Проверяет, работает ли пароль (пробует подключиться через plink)
    """
    logger_instance = logger
    try:
        # Формируем команду для проверки подключения
        test_cmd = [
            plink_path,
            "-ssh",
            f"{ssh_user}@{centrum_host}",
            "-pw",
            password,
            "-batch",
            "-no-trivial-auth",
            "echo OK",
        ]

        # Не логируем сам пароль
        logger_instance.debug("Тестирование пароля через SSH...")

        result = subprocess.run(
            test_cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )

        # Проверяем, что команда выполнилась успешно и вернула "OK"
        if "OK" in result.stdout:
            logger_instance.debug("Пароль валиден")
            return True
        else:
            logger_instance.debug(f"Неверный ответ от сервера: {result.stdout}")
            return False

    except subprocess.CalledProcessError as e:
        logger_instance.debug("Ошибка подключения (неверный пароль?)")
        return False
    except subprocess.TimeoutExpired:
        logger_instance.debug("Таймаут при проверке пароля")
        return False
    except Exception as e:
        logger_instance.debug(f"Неожиданная ошибка при проверке пароля: {str(e)}")
        return False


def init_password(
    service_name: str = SERVICE_NAME,
    ssh_user: str = SSH_USER,
    logger_instance: Optional[logging.Logger] = None,
) -> str:
    """
    Инициализирует пароль: проверяет keyring, и если не найден или неверен — запрашивает у пользователя.
    """
    logger_instance = logger
    try:
        password = keyring.get_password(service_name, ssh_user)

        if password is not None:
            logger_instance.debug("Пароль найден в keyring, проверяем валидность...")
            if test_password(password, logger_instance=logger_instance):
                logger_instance.debug("Пароль из keyring валиден")
                return password
            else:
                logger_instance.warning("Пароль из keyring не подходит.")
        else:
            logger_instance.debug("Пароль не найден в keyring")

        # Запрашиваем пароль у пользователя только если его нет или он неверен
        password = getpass(f"Введите пароль для пользователя {SSH_USER}: ")

        # Проверяем новый пароль перед сохранением
        if not test_password(password, logger_instance=logger_instance):
            raise ValueError("Введенный пароль недействителен")

        keyring.set_password(service_name, ssh_user, password)
        logger_instance.info("Пароль успешно сохранён в keyring")
        return password

    except Exception as e:
        logger_instance.error(f"Ошибка при работе с keyring: {str(e)}")
        raise RuntimeError("Не удалось инициализировать пароль") from e


def test_password_with_paramiko(
    password: str,
    ssh_user: str = "default_user",
    centrum_host: str = "example.com",
    port: int = 22,
    timeout: int = 10,
    logger_instance: Optional[logging.Logger] = None,
) -> bool:
    logger_instance = logger_instance or logger

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(
            paramiko.AutoAddPolicy()
        )  # Автоприем ключа сервера

        client.connect(
            hostname=centrum_host,
            username=ssh_user,
            password=password,
            timeout=timeout,
            auth_timeout=timeout,
            port=port,
        )

        # Выполняем простую команду
        stdin, stdout, stderr = client.exec_command("echo OK")
        output = stdout.read().decode().strip()

        client.close()

        if output == "OK":
            logger_instance.debug("Пароль валиден")
            return True
        else:
            logger_instance.debug(f"Неверный ответ от сервера: {output}")
            return False

    except paramiko.AuthenticationException:
        logger_instance.debug("Ошибка аутентификации: неверный пароль")
        return False
    except paramiko.SSHException as e:
        logger_instance.debug(f"Ошибка SSH: {str(e)}")
        return False
    except Exception as e:
        logger_instance.debug(f"Неожиданная ошибка при проверке пароля: {str(e)}")
        return False
