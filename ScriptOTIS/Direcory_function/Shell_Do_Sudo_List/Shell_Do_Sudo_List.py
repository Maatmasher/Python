import paramiko, re, socket
import time
import os
from datetime import datetime

# ========= КОНФИГУРАЦИЯ =========

# Получаем директорию, где находится скрипт
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
COMMANDS_FILE = os.path.join(CURRENT_DIR, "commands.txt")
SERVERS_FILE = os.path.join(CURRENT_DIR, "servers.txt")
LOG_FILE = os.path.join(CURRENT_DIR, "commands.log")
END_CMD = "echo 'all command done'"

# Параметры подключения
USERNAME = "otis"
PASSWORD = "some_uber_ultra_pass"

# Параметры обработки серверов
COUNT_SERVER = 5
PAUSE_COMMAND = 450
TIMEOUT = 450

# ================================


def setup_files():
    """Инициализация файлов логов"""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("")


def clean_ansi_escape(text):
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def read_commands_from_file(file_path):
    """Читает команды из файла"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            commands = [line.strip() for line in f.readlines() if line.strip()]

        if not any("all command done" in cmd for cmd in commands):
            commands.append("echo 'all command done'")
        print(commands)
        return commands
    except FileNotFoundError:
        print(f"Файл с командами не найден: {file_path}")
        return ["echo 'all command done'"]


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


def _execute_ssh_commands_generator_with_sudo(
    host, commands, username=USERNAME, password=PASSWORD
):
    """Выполняет список SSH команд последовательно в рамках одной сессии с sudo su -"""
    ssh = None
    shell = None

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=username, password=password)

        print(f"SSH соединение с {host} установлено")

        # Создаем интерактивную оболочку
        shell = ssh.invoke_shell()

        # Ждем приглашение командной строки
        time.sleep(1)

        # Очищаем начальный вывод
        if shell.recv_ready():
            initial_output = shell.recv(4096).decode()
            # print(f"Начальный вывод: {clean_ansi_escape(initial_output)}")

        # Выполняем sudo su -
        print("Выполняем sudo su -")
        shell.send("sudo su -\n")  # type: ignore

        # Ждем завершения sudo su -
        time.sleep(2)

        # Читаем результат sudo su -
        sudo_output = ""
        start_time = time.time()
        while time.time() - start_time < 10:  # Таймаут 10 секунд для sudo
            if shell.recv_ready():
                chunk = shell.recv(1024).decode()
                sudo_output += chunk
                print(clean_ansi_escape(chunk), end="")

                # Проверяем, что мы получили root приглашение
                if "#" in chunk or "root@" in chunk:
                    break
            time.sleep(0.1)

        if "#" in sudo_output or "root@" in sudo_output:
            yield True, "sudo su - выполнен успешно", 0
        else:
            yield False, f"Не удалось выполнить sudo su -: {sudo_output}", 0
            return

        # Выполняем команды под root
        for cmd_index, command in enumerate(commands, 1):
            try:
                print(
                    f"Выполняем команду {cmd_index}/{len(commands)} под root: {command}"
                )

                # Отправляем команду
                shell.send(f"{command}\n")  # type: ignore

                # Читаем результат
                output = ""
                start_time = time.time()
                command_completed = False

                while time.time() - start_time < TIMEOUT:
                    if shell.recv_ready():
                        chunk = shell.recv(1024).decode()
                        clean_chunk = clean_ansi_escape(chunk)
                        output += clean_chunk
                        print(clean_chunk, end="")

                        # Проверяем завершение команды по приглашению
                        if "#" in chunk and (
                            command in output or len(output) > len(command)
                        ):
                            command_completed = True
                            break

                    time.sleep(0.1)

                if not command_completed:
                    yield False, f"Команда {cmd_index} превысила таймаут ({TIMEOUT}с): {command}", cmd_index
                    continue

                # Обрабатываем результат
                # Удаляем команду из вывода и приглашения
                lines = output.split("\n")
                filtered_lines = []
                for line in lines:
                    line = line.strip()
                    if line and not line.endswith("#") and command not in line:
                        filtered_lines.append(line)

                clean_output = "\n".join(filtered_lines).strip()

                # Проверяем на наличие ошибок
                if (
                    "command not found" in clean_output.lower()
                    or "permission denied" in clean_output.lower()
                ):
                    yield False, clean_output, cmd_index
                else:
                    yield True, clean_output, cmd_index

            except Exception as e:
                yield False, f"Ошибка выполнения команды {cmd_index}: {str(e)}", cmd_index

    except (paramiko.AuthenticationException, paramiko.SSHException, socket.error) as e:
        yield False, f"Ошибка SSH соединения с {host}: {str(e)}", 0
    finally:
        if shell:
            try:
                shell.close()
            except:
                pass
        if ssh:
            try:
                ssh.close()
                print(f"SSH соединение с {host} закрыто")
            except:
                pass


def process_servers():
    """Обрабатывает все серверы из файла с учетом настроек паузы"""
    servers = read_servers_from_file(SERVERS_FILE)
    commands = read_commands_from_file(COMMANDS_FILE)
    setup_files()

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
        print(f"\nОбрабатываем сервер {i}/{total_servers}: {server}")

        try:
            server_success = True
            commands_executed = 0

            for success, result, cmd_index in _execute_ssh_commands_generator_with_sudo(
                server, commands
            ):
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if success:
                    log_message = f"[{timestamp}] SUCCESS - {server} - Команда {cmd_index}: {result}\n"
                    print(f"   Команда {cmd_index} выполнена успешно")
                    commands_executed += 1
                else:
                    log_message = f"[{timestamp}] ERROR - {server} - Команда {cmd_index}: {result}\n"
                    print(f"   Команда {cmd_index} завершилась с ошибкой: {result}")
                    server_success = False

                    if cmd_index == 0:
                        break

                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(log_message)

            if server_success:
                print(
                    f"Сервер {server} обработан успешно ({commands_executed}/{len(commands)} команд)"
                )
            else:
                print(
                    f"Сервер {server} обработан с ошибками ({commands_executed}/{len(commands)} команд)"
                )

        except Exception as e:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            error_message = f"[{timestamp}] CRITICAL ERROR - {server}: {str(e)}\n"
            print(f"Критическая ошибка при обработке сервера {server}: {e}")

            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(error_message)

        processed_count += 1

        if processed_count % COUNT_SERVER == 0 and i < total_servers:
            print(
                f"\nОбработано {processed_count} серверов. Пауза на {PAUSE_COMMAND} секунд..."
            )

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
