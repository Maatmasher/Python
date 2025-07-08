import paramiko
import time
import os
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

# =====================================
# СЕКЦИЯ КОНФИГУРАЦИИ
# =====================================

# Получаем директорию, где находится скрипт
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Пути к файлам (относительно директории скрипта)
COMMANDS_FILE = os.path.join(CURRENT_DIR, "commands.txt")
SERVERS_FILE = os.path.join(CURRENT_DIR, "servers.txt")
LOG_FILE = os.path.join(CURRENT_DIR, "commands.log")

# Параметры подключения
USERNAME = "otis"
PASSWORD = "MzL2qqOp"
SUDO_PASSWORD = None

# Параметры обработки серверов
COUNT_SERVER = 3
PAUSE_COMMAND = 30
TIMEOUT = 300

# Параметры логирования
LOG_LEVEL = logging.INFO
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(message)s"
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# =====================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# =====================================


def setup_logging():
    """Настройка системы логирования с детальной обработкой ошибок"""
    try:
        # Проверяем возможность записи в директорию
        if not os.path.exists(CURRENT_DIR):
            print(f"ОШИБКА: Директория не существует: {CURRENT_DIR}")
            return None

        if not os.access(CURRENT_DIR, os.W_OK):
            print(f"ОШИБКА: Нет прав на запись в директорию: {CURRENT_DIR}")
            return None

        # Создаем логгер
        logger = logging.getLogger("ssh_automation")
        logger.setLevel(LOG_LEVEL)

        # Очищаем существующие обработчики
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()

        # Создаем форматтер
        formatter = logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

        # Настраиваем файловый обработчик с ротацией
        try:
            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=LOG_MAX_SIZE,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(LOG_LEVEL)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            print(f"Файловый обработчик логов настроен: {LOG_FILE}")
        except Exception as file_error:
            print(f"ОШИБКА настройки файлового обработчика: {file_error}")
            # Продолжаем работу только с консольным обработчиком

        # Настраиваем консольный обработчик
        try:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(LOG_LEVEL)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            print("Консольный обработчик логов настроен")
        except Exception as console_error:
            print(f"ОШИБКА настройки консольного обработчика: {console_error}")

        # Проверяем, что хотя бы один обработчик добавлен
        if not logger.handlers:
            print(
                "КРИТИЧЕСКАЯ ОШИБКА: Не удалось настроить ни одного обработчика логов"
            )
            return None

        # Тестируем логгер
        logger.info("=" * 60)
        logger.info("НАЧАЛО СЕАНСА ЛОГИРОВАНИЯ")
        logger.info(f"Рабочая директория: {CURRENT_DIR}")
        logger.info(f"Файл логов: {LOG_FILE}")
        logger.info(f"Уровень логирования: {logging.getLevelName(LOG_LEVEL)}")
        logger.info("=" * 60)

        return logger

    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА при настройке логирования: {e}")
        return None


def get_fallback_logger():
    """Создает простейший логгер для случаев, когда основной не работает"""
    fallback_logger = logging.getLogger("fallback")
    fallback_logger.setLevel(logging.INFO)

    # Очищаем обработчики
    for handler in fallback_logger.handlers[:]:
        fallback_logger.removeHandler(handler)
        handler.close()

    # Добавляем только консольный обработчик
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    fallback_logger.addHandler(handler)

    return fallback_logger


def safe_log(level, message, *args, **kwargs):
    """Безопасное логирование с проверкой состояния логгера"""
    global logger

    if logger is None:
        print(f"[{level}] {message}")
        return

    try:
        getattr(logger, level.lower())(message, *args, **kwargs)
    except Exception as e:
        print(f"[ОШИБКА ЛОГИРОВАНИЯ] {message}")
        print(f"[ОШИБКА ЛОГИРОВАНИЯ] Причина: {e}")


# Инициализируем логгер
logger = setup_logging()

# Если основной логгер не инициализировался, используем резервный
if logger is None:
    print("Основной логгер не инициализирован. Используется резервный логгер.")
    logger = get_fallback_logger()

# =====================================
# ОСНОВНОЙ КОД
# =====================================


def read_commands_from_file(file_path):
    """Читает команды из файла"""
    try:
        safe_log("info", f"Чтение команд из файла: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            commands = [line.strip() for line in f.readlines() if line.strip()]

        if not any("all command done" in cmd for cmd in commands):
            commands.append('echo "all command done"')
            safe_log("info", 'Добавлена финальная команда: echo "all command done"')

        safe_log("info", f"Загружено {len(commands)} команд")
        return commands

    except FileNotFoundError:
        safe_log("error", f"Файл с командами не найден: {file_path}")
        return ['echo "all command done"']
    except Exception as e:
        safe_log("error", f"Ошибка при чтении файла команд: {e}")
        return ['echo "all command done"']


def read_servers_from_file(file_path):
    """Читает список серверов из файла"""
    try:
        safe_log("info", f"Чтение серверов из файла: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            servers = [line.strip() for line in f.readlines() if line.strip()]

        safe_log("info", f"Загружено {len(servers)} серверов")
        return servers

    except FileNotFoundError:
        safe_log("error", f"Файл с серверами не найден: {file_path}")
        return []
    except Exception as e:
        safe_log("error", f"Ошибка при чтении файла серверов: {e}")
        return []


def _execute_shell_comands(
    host, username, password, commands, sudo_password=None, timeout=300
):
    """Выполняет команды с sudo/su через SSH"""
    safe_log("info", f"Начало выполнения команд на сервере: {host}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        safe_log("info", f"Подключение к серверу {host}")
        ssh.connect(host, username=username, password=password)
        safe_log("info", f"Успешно подключился к серверу {host}")

        shell = ssh.invoke_shell()
        time.sleep(1)

        safe_log("debug", f"Выполнение sudo su - на сервере {host}")
        shell.send(b"sudo su -\n")
        time.sleep(1)

        if sudo_password and shell.recv_ready():
            output = shell.recv(1024).decode("utf-8", errors="replace")
            if "password" in output.lower():
                safe_log("debug", f"Отправка sudo пароля на сервере {host}")
                shell.send(f"{sudo_password}\n".encode("utf-8"))
                time.sleep(1)

        for i, cmd in enumerate(commands, 1):
            safe_log("info", f"Выполнение команды {i}/{len(commands)} на {host}: {cmd}")
            shell.send(f"{cmd}\n".encode("utf-8"))
            time.sleep(1)

        safe_log("debug", f"Завершение сессии на сервере {host}")
        shell.send(b"exit\n")
        shell.send(b"exit\n")
        time.sleep(1)

        output = ""
        max_wait_time = timeout
        start_time = time.time()
        command_completed = False

        safe_log(
            "info",
            f"Ожидание завершения команд на сервере {host} (timeout: {timeout}s)",
        )

        while time.time() - start_time < max_wait_time:
            if shell.recv_ready():
                chunk = shell.recv(4096).decode("utf-8", errors="replace")
                output += chunk

            if "all command done" in output:
                command_completed = True
                safe_log("info", f"Команды успешно завершены на сервере {host}")
                break

            time.sleep(0.1)

        if not command_completed:
            timeout_msg = f"TIMEOUT: Команды не завершились за {timeout} секунд"
            output += f"\n{timeout_msg}"
            safe_log(
                "error",
                f"TIMEOUT на сервере {host}: команды не завершились за {timeout} секунд",
            )
            log_command_result(host, commands + ["TIMEOUT"], output)

            try:
                shell.send(b"\x03")
                time.sleep(1)
                shell.send(b"exit\n")
                shell.send(b"exit\n")
                safe_log("warning", f"Принудительное завершение сессии на {host}")
            except Exception as cleanup_error:
                safe_log(
                    "error",
                    f"Ошибка при принудительном завершении на {host}: {cleanup_error}",
                )

            raise TimeoutError(
                f"Команды на хосте {host} не завершились за {timeout} секунд"
            )

        log_command_result(host, commands, output)
        safe_log("info", f"Обработка сервера {host} завершена успешно")
        return output

    except paramiko.AuthenticationException:
        safe_log("error", f"Ошибка аутентификации на сервере {host}")
        raise
    except paramiko.SSHException as ssh_error:
        safe_log("error", f"SSH ошибка на сервере {host}: {ssh_error}")
        raise
    except Exception as e:
        safe_log("error", f"Общая ошибка при выполнении команд на сервере {host}: {e}")
        log_command_result(host, commands, str(e))
        raise
    finally:
        try:
            ssh.close()
            safe_log("debug", f"SSH соединение с {host} закрыто")
        except Exception as close_error:
            safe_log(
                "warning", f"Ошибка при закрытии SSH соединения с {host}: {close_error}"
            )


def log_command_result(host, commands, output):
    """Логирует детальный результат выполнения команд"""
    safe_log("info", f"РЕЗУЛЬТАТ ВЫПОЛНЕНИЯ КОМАНД НА СЕРВЕРЕ {host}:")
    safe_log("info", f"Команды:")
    for i, cmd in enumerate(commands, 1):
        safe_log("info", f"  {i}. {cmd}")

    safe_log("info", f"Вывод команд:")
    for line in output.split("\n"):
        if line.strip():
            safe_log("info", f"  > {line}")

    safe_log("info", f"Завершено выполнение команд на сервере {host}")
    safe_log("info", "-" * 50)


def process_servers():
    """Обрабатывает все серверы из файла с учетом настроек паузы"""
    safe_log("info", "НАЧАЛО ОБРАБОТКИ СЕРВЕРОВ")

    servers = read_servers_from_file(SERVERS_FILE)
    commands = read_commands_from_file(COMMANDS_FILE)

    if not servers:
        safe_log("error", "Список серверов пуст или файл не найден!")
        return

    if not commands:
        safe_log("error", "Список команд пуст или файл не найден!")
        return

    safe_log("info", f"Параметры обработки:")
    safe_log("info", f"  - Количество серверов: {len(servers)}")
    safe_log("info", f"  - Количество команд: {len(commands)}")
    safe_log(
        "info", f"  - Пауза каждые {COUNT_SERVER} серверов на {PAUSE_COMMAND} секунд"
    )
    safe_log("info", f"  - Таймаут выполнения команд: {TIMEOUT} секунд")

    processed_count = 0
    successful_count = 0
    failed_count = 0
    total_servers = len(servers)

    for i, server in enumerate(servers, 1):
        safe_log("info", f"ОБРАБОТКА СЕРВЕРА {i}/{total_servers}: {server}")

        try:
            _execute_shell_comands(
                host=server,
                username=USERNAME,
                password=PASSWORD,
                commands=commands,
                sudo_password=SUDO_PASSWORD,
                timeout=TIMEOUT,
            )
            successful_count += 1
            safe_log("info", f"✓ Сервер {server} обработан успешно")

        except Exception as e:
            failed_count += 1
            safe_log("error", f"✗ Ошибка при обработке сервера {server}: {e}")

        processed_count += 1

        if processed_count % COUNT_SERVER == 0 and i < total_servers:
            safe_log(
                "info",
                f"Обработано {processed_count} серверов. Пауза на {PAUSE_COMMAND} секунд",
            )

            for remaining in range(PAUSE_COMMAND, 0, -1):
                print(f"Пауза: осталось {remaining} секунд...", end="\r")
                time.sleep(1)

            safe_log("info", "Пауза завершена. Продолжение обработки")
            print(f"Пауза завершена. Продолжаем обработку...")

    safe_log("info", "=" * 60)
    safe_log("info", "ИТОГОВАЯ СТАТИСТИКА ОБРАБОТКИ")
    safe_log("info", f"Всего серверов: {total_servers}")
    safe_log("info", f"Успешно обработано: {successful_count}")
    safe_log("info", f"Ошибок: {failed_count}")
    safe_log("info", f"Процент успешных: {(successful_count/total_servers)*100:.1f}%")
    safe_log("info", "=" * 60)


if __name__ == "__main__":
    # Создаем примерные файлы
    if not os.path.exists(COMMANDS_FILE):
        with open(COMMANDS_FILE, "w", encoding="utf-8") as f:
            f.write("systemctl restart nginx\n")
            f.write('echo "Nginx перезапущен"\n')
            f.write('echo "all command done"\n')
        safe_log("info", f"Создан файл с командами: {COMMANDS_FILE}")

    if not os.path.exists(SERVERS_FILE):
        with open(SERVERS_FILE, "w", encoding="utf-8") as f:
            f.write("10.9.30.101\n")
            f.write("10.9.30.102\n")
            f.write("10.9.30.103\n")
        safe_log("info", f"Создан файл с серверами: {SERVERS_FILE}")

    try:
        process_servers()
        safe_log("info", "Скрипт завершен успешно")
    except KeyboardInterrupt:
        safe_log("warning", "Обработка прервана пользователем")
    except Exception as e:
        safe_log("critical", f"Критическая ошибка: {e}")
    finally:
        safe_log("info", "ЗАВЕРШЕНИЕ СЕАНСА ЛОГИРОВАНИЯ")
        safe_log("info", "=" * 60)
