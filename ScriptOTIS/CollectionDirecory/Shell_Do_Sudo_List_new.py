import paramiko, socket
import time
import os
from datetime import datetime

# ========= КОНФИГУРАЦИЯ =========

# Получаем директорию, где находится скрипт
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
COMMANDS_FILE = os.path.join(CURRENT_DIR, "commands.txt")  # Файл со списком команд
SERVERS_FILE = os.path.join(
    CURRENT_DIR, "servers.txt"
)  # Файл со списком серверов (IP адреса)
LOG_FILE = os.path.join(CURRENT_DIR, "commands.log")  # Файл логов

# Параметры подключения
USERNAME = "otis"
PASSWORD = "MzL2qqOp"
# SUDO_PASSWORD = "MzL2qqOp"  # Если пароль не нужен, оставляем None


# Параметры обработки серверов
COUNT_SERVER = 2  # Количество серверов для обработки до паузы
PAUSE_COMMAND = 30  # Пауза в секундах после обработки COUNT_SERVER серверов
TIMEOUT = 600  # Таймаут выполнения команд в секундах
# ================================


def read_commands_from_file(file_path):
    """Читает команды из файла"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            commands = [line.strip() for line in f.readlines() if line.strip()]

        # Проверяем наличие финальной команды
        if not any("all command done" in cmd for cmd in commands):
            commands.append("echo 'all command done'")
        print(commands)
        return commands
    except FileNotFoundError:
        print(f"Файл с командами не найден: {file_path}")
        return ["echo 'all command done'"]  # Возвращаем минимальный набор команд


def read_servers_from_file(file_path):
    """Читает список серверов из файла"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            servers = [line.strip() for line in f.readlines() if line.strip()]
        print(servers)
        return servers
    except FileNotFoundError:
        print(f"Файл с серверами не найден: {file_path}")
        return []


def _execute_ssh_command(
    host, command="sudo su -", username=USERNAME, password=PASSWORD
):
    """Выполняет SSH команду на удаленном хосте"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=username, password=password, timeout=10)

        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode("utf-8").strip()
        error = stderr.read().decode("utf-8").strip()

        ssh.close()

        if error:
            return False, error
        return True, output

    except (paramiko.AuthenticationException, paramiko.SSHException, socket.error) as e:
        return False, str(e)


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

    processed_count = 0
    total_servers = len(servers)

    for i, server in enumerate(servers, 1):
        print(f"Обрабатывается сервер {i}/{total_servers}: {server}")
        try:
            ssh_success, ssh_result = _execute_ssh_command(host=server)
            ssh_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if ssh_success:
                ssh_message = f"[{ssh_timestamp}] SSH команда выполнена успешно на {server}: {ssh_result}\n"
            else:
                ssh_message = (
                    f"[{ssh_timestamp}] Ошибка SSH на {server}: {ssh_result}\n"
                )
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(ssh_message)

            for cmd in commands:
                ssh_success, ssh_result = _execute_ssh_command(
                    host=server,
                    command=cmd,
                )
                ssh_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if ssh_success:
                    ssh_message = f"[{ssh_timestamp}] SSH команда выполнена успешно на {server}: {ssh_result}\n"
                else:
                    ssh_message = (
                        f"[{ssh_timestamp}] Ошибка SSH на {server}: {ssh_result}\n"
                    )
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(ssh_message)

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
    try:
        process_servers()
    except KeyboardInterrupt:
        print("\nОбработка прервана пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
