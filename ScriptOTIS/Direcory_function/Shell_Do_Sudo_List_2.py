import paramiko
import time
import os
import re
from datetime import datetime

# ========= КОНФИГУРАЦИЯ =========

# Получаем директорию, где находится скрипт
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
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

# ================================


def clean_output(text):
    """Очищает вывод от escape-последовательностей и лишних символов"""
    # Удаляем ANSI escape sequences
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    text = ansi_escape.sub("", text)

    # Удаляем другие управляющие символы
    text = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", text)

    # Удаляем символы возврата каретки и лишние пробелы
    text = text.replace("\r", "")

    # Удаляем множественные пустые строки
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    return text.strip()


def read_commands_from_file(file_path):
    """Читает команды из файла"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            commands = [line.strip() for line in f.readlines() if line.strip()]

        # Проверяем наличие финальной команды
        if not any("all command done" in cmd for cmd in commands):
            commands.append('echo "all command done"')

        return commands
    except FileNotFoundError:
        print(f"Файл с командами не найден: {file_path}")
        return ['echo "all command done"']


def read_servers_from_file(file_path):
    """Читает список серверов из файла"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            servers = [line.strip() for line in f.readlines() if line.strip()]
        return servers
    except FileNotFoundError:
        print(f"Файл с серверами не найден: {file_path}")
        return []


def _execute_shell_comands(
    host, username, password, commands, sudo_password=None, timeout=300
):
    """Выполняет команды с sudo/su через SSH с улучшенным логированием"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Словарь для хранения результатов выполнения команд
    command_results = []

    try:
        # Подключаемся к серверу
        ssh.connect(host, username=username, password=password)

        # Создаем интерактивную сессию
        shell = ssh.invoke_shell()
        time.sleep(1)

        # Очищаем начальный буфер
        if shell.recv_ready():
            shell.recv(4096)

        # Переходим в sudo su -
        shell.send(b"sudo su -\n")
        time.sleep(1)

        # Если запросит пароль
        if sudo_password and shell.recv_ready():
            output = shell.recv(1024).decode("utf-8", errors="replace")
            if "password" in output.lower():
                shell.send(f"{sudo_password}\n".encode("utf-8"))
                time.sleep(1)

        # Очищаем буфер после sudo
        if shell.recv_ready():
            shell.recv(4096)

        # Выполняем команды и собираем результаты
        for cmd in commands:
            # Очищаем буфер перед командой
            if shell.recv_ready():
                shell.recv(4096)

            # Отправляем команду с маркером для идентификации вывода
            marker = f"MARKER_{time.time()}"
            shell.send(f'echo "{marker}_START"\n'.encode("utf-8"))
            time.sleep(0.1)
            shell.send(f"{cmd}\n".encode("utf-8"))
            time.sleep(0.1)
            shell.send(f'echo "{marker}_END"\n'.encode("utf-8"))

            # Даем время на выполнение команды
            time.sleep(1)

            # Собираем вывод команды
            cmd_output = ""
            start_time = time.time()

            while time.time() - start_time < 10:  # Таймаут для одной команды
                if shell.recv_ready():
                    chunk = shell.recv(4096).decode("utf-8", errors="replace")
                    cmd_output += chunk

                    # Проверяем, получили ли мы конец вывода команды
                    if f"{marker}_END" in cmd_output:
                        break

                time.sleep(0.1)

            # Извлекаем только вывод команды
            if f"{marker}_START" in cmd_output and f"{marker}_END" in cmd_output:
                start_idx = cmd_output.find(f"{marker}_START") + len(f"{marker}_START")
                end_idx = cmd_output.find(f"{marker}_END")
                command_output = cmd_output[start_idx:end_idx].strip()

                # Очищаем вывод от лишних строк с echo и самой командой
                lines = command_output.split("\n")
                cleaned_lines = []
                for line in lines:
                    if (
                        not line.strip().startswith('echo "MARKER_')
                        and not line.strip() == cmd
                    ):
                        cleaned_lines.append(line)

                command_output = "\n".join(cleaned_lines).strip()
            else:
                command_output = "Не удалось получить вывод команды"

            # Очищаем вывод от escape-последовательностей
            command_output = clean_output(command_output)

            # Сохраняем результат
            command_results.append({"command": cmd, "output": command_output})

            # Проверяем, если это была последняя команда
            if "all command done" in cmd:
                break

        # Завершаем сессию
        shell.send(b"exit\n")  # Выход из root
        shell.send(b"exit\n")  # Выход из SSH
        time.sleep(1)

        # Логируем результаты
        log_results_improved(host, command_results, success=True)

        return command_results

    except Exception as e:
        log_results_improved(host, command_results, success=False, error=str(e))
        raise
    finally:
        ssh.close()


def log_results_improved(host, command_results, success=True, error=None):
    """Улучшенное логирование результатов выполнения команд"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"Время: {timestamp}\n")
        f.write(f"Сервер: {host}\n")
        f.write(f"Статус: {'УСПЕШНО' if success else 'ОШИБКА'}\n")

        if error:
            f.write(f"Ошибка: {error}\n")

        f.write(f"{'-'*70}\n")

        if command_results:
            for i, result in enumerate(command_results, 1):
                f.write(f"\nКоманда {i}: {result['command']}\n")
                f.write(f"Результат:\n")

                # Форматируем вывод с отступами
                output_lines = result["output"].split("\n")
                for line in output_lines:
                    if line.strip():  # Пропускаем пустые строки
                        f.write(f"  {line}\n")

                f.write(f"{'-'*30}\n")

        f.write(f"{'='*70}\n\n")


def log_result(host, commands, output):
    """Старая функция логирования для совместимости"""
    # Эта функция больше не используется, но оставлена для совместимости
    pass


def process_servers():
    """Обрабатывает все серверы из файла с учетом настроек паузы"""
    # Читаем список серверов и команд
    servers = read_servers_from_file(SERVERS_FILE)
    commands = read_commands_from_file(COMMANDS_FILE)

    if not servers:
        print("Список серверов пуст или файл не найден!")
        return

    if not commands:
        print("Список команд пуст или файл не найден!")
        return

    print(f"Загружено {len(servers)} серверов для обработки")
    print(f"Загружено {len(commands)} команд")
    print(f"Настройки: пауза каждые {COUNT_SERVER} серверов на {PAUSE_COMMAND} секунд")
    print(f"Рабочая директория: {CURRENT_DIR}")
    print("-" * 50)

    # Создаем заголовок в лог-файле
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{'#'*70}\n")
        f.write(
            f"# НАЧАЛО НОВОЙ СЕССИИ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        f.write(f"# Серверов для обработки: {len(servers)}\n")
        f.write(f"# Команд для выполнения: {len(commands)}\n")
        f.write(f"{'#'*70}\n")

    processed_count = 0
    total_servers = len(servers)

    for i, server in enumerate(servers, 1):
        print(f"Обрабатывается сервер {i}/{total_servers}: {server}")

        try:
            _execute_shell_comands(
                host=server,
                username=USERNAME,
                password=PASSWORD,
                commands=commands,
                sudo_password=SUDO_PASSWORD,
                timeout=TIMEOUT,
            )
            print(f"✓ Сервер {server} обработан успешно")

        except Exception as e:
            print(f"✗ Ошибка при обработке сервера {server}: {e}")

        processed_count += 1

        # Проверяем, нужна ли пауза
        if processed_count % COUNT_SERVER == 0 and i < total_servers:
            print(
                f"\nОбработано {processed_count} серверов. Пауза на {PAUSE_COMMAND} секунд..."
            )

            # Обратный отсчет
            for remaining in range(PAUSE_COMMAND, 0, -1):
                print(f"Осталось {remaining} секунд...", end="\r")
                time.sleep(1)

            print(f"Пауза завершена. Продолжаем обработку...")
            print("-" * 50)

    print(f"\nВсе серверы обработаны! Общее количество: {processed_count}")


if __name__ == "__main__":
    # Создаем примерные файлы, если они не существуют
    if not os.path.exists(COMMANDS_FILE):
        with open(COMMANDS_FILE, "w", encoding="utf-8") as f:
            f.write("systemctl status nginx\n")
            f.write("df -h\n")
            f.write('echo "all command done"\n')
        print(f"Создан файл с командами: {COMMANDS_FILE}")

    if not os.path.exists(SERVERS_FILE):
        with open(SERVERS_FILE, "w", encoding="utf-8") as f:
            f.write("10.9.30.101\n")
            f.write("10.9.30.102\n")
        print(f"Создан файл с серверами: {SERVERS_FILE}")

    try:
        process_servers()
    except KeyboardInterrupt:
        print("\nОбработка прервана пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
