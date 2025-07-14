import paramiko, sys, re, socket
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
END_CMD = "echo 'all command done'"

# Параметры подключения
USERNAME = "otis"
PASSWORD = "MzL2qqOp"


# Параметры обработки серверов
COUNT_SERVER = 5  # Количество серверов для обработки до паузы
PAUSE_COMMAND = 1800  # Пауза в секундах после обработки COUNT_SERVER серверов
TIMEOUT = 1800  # Таймаут выполнения команд в секундах
# ================================


def setup_files():
    """Инициализация файлов логов"""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("")  # Очищаем лог выполнения


def clean_ansi_escape(text):
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


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


def _execute_sudo(host, username=USERNAME, password=PASSWORD):
    """Выполняет SSH команду на удаленном хосте"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=username, password=password, timeout=10)

        stdin, stdout, stderr = ssh.exec_command(
            command="sudo su -", timeout=5, get_pty=True
        )
        output = stdout.read().decode("utf-8").strip()
        error = stderr.read().decode("utf-8").strip()
        stdin, stdout, stderr = ssh.exec_command(command="\n", timeout=5, get_pty=True)
        output += stdout.read().decode("utf-8").strip()
        error += stderr.read().decode("utf-8").strip()
        stdin, stdout, stderr = ssh.exec_command(
            command="echo 'sudo done'", timeout=5, get_pty=True
        )
        output += stdout.read().decode("utf-8").strip()
        error += stderr.read().decode("utf-8").strip()
        stdin, stdout, stderr = ssh.exec_command(
            command="echo '\n'", timeout=5, get_pty=True
        )
        output += stdout.read().decode("utf-8").strip()
        error += stderr.read().decode("utf-8").strip()
        ssh.close()

        if error:
            return False, clean_ansi_escape(error)
        return True, clean_ansi_escape(output)

    except (
        paramiko.AuthenticationException,
        paramiko.SSHException,
        socket.error,
        TimeoutError,
    ) as e:
        return False, str(e)


def _execute_interactive_sudo(
    host, command="sudo su -", username=USERNAME, password=PASSWORD, timeout=5
):
    ssh = None
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=username, password=password)

        chan = ssh.invoke_shell()
        chan.settimeout(timeout)

        # Отправка команды
        chan.send(command.encode("utf-8") + "\n".encode("utf-8"))

        # Ожидание вывода
        output = []
        start_time = time.time()

        while True:
            if chan.recv_ready():
                data = clean_ansi_escape(chan.recv(1024).decode())
                output.append(data)
                if "password" in data.lower():  # Если запросит пароль
                    chan.send(password.encode("utf-8") + "\n".encode("utf-8"))
            elif time.time() - start_time > timeout:
                break
            time.sleep(0.1)

        return True, "".join(output)
    except Exception as e:
        return False, str(e)
    finally:
        if ssh:
            ssh.close()


def _execute_ssh_command(host, command, username=USERNAME, password=PASSWORD):
    """Выполняет SSH команду на удаленном хосте"""
    ssh = None
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=username, password=password)
        stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)
        output = []
        error = []
        start_time = time.time()

        while True:
            # Чтение stdout
            while stdout.channel.recv_ready():
                chunk = clean_ansi_escape(stdout.channel.recv(1024).decode())
                output.append(chunk)
                print(chunk, end="")

            # Чтение stderr
            while stderr.channel.recv_stderr_ready():
                chunk = clean_ansi_escape(stderr.channel.recv_stderr(1024).decode())
                error.append(chunk)
                print(chunk, end="", file=sys.stderr)

            # Проверка завершения
            if stdout.channel.exit_status_ready():
                break

            # Защита от зависания
            if time.time() - start_time > TIMEOUT:
                raise TimeoutError(f"Command execution timed out{command}")

            time.sleep(0.1)

        exit_status = stdout.channel.recv_exit_status()
        full_output = "".join(output).strip()
        full_error = "".join(error).strip()

        if exit_status == 0:
            return True, full_output
        else:
            return False, (
                full_error
                if full_error
                else f"Command failed with status {exit_status}"
            )

    except (paramiko.AuthenticationException, paramiko.SSHException, socket.error) as e:
        return False, str(e)
    finally:
        if ssh:
            try:
                ssh.close()
            except:
                pass


def process_servers():
    """Обрабатывает все серверы из файла с учетом настроек паузы"""
    # Читаем список серверов и команд
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
        # try:
        #     print(f"Обрабатывается сервер {i}/{total_servers}: {server}")
        #     sudo_success, sudo_result = _execute_sudo(
        #         host=server,
        #     )
        #     sudo_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        #     if sudo_success:
        #         sudo_message = f"[{sudo_timestamp}] Sudo команда выполнена успешно на {server}: {sudo_result}\n"
        #     else:
        #         sudo_message = (
        #             f"[{sudo_timestamp}] Ошибка Sudo на {server}: {sudo_result}\n"
        #         )
        #     with open(LOG_FILE, "a", encoding="utf-8") as f:
        #         f.write(sudo_message)
        # except Exception as e:
        #     print(f"✗ Ошибка при обработке сервера {server}: {e}")
        try:
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
