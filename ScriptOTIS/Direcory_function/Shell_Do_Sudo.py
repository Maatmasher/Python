import paramiko
import time
from datetime import datetime


def _execute_shell_comands(
    host, username, password, commands, sudo_password=None, timeout=300
):
    """Выполняет команды с sudo/su через SSH"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # Подключаемся к серверу
        ssh.connect(host, username=username, password=password)

        # Создаем интерактивную сессию
        shell = ssh.invoke_shell()
        time.sleep(1)  # Даем время на установку соединения

        # Если нужен sudo su -
        shell.send(b"sudo su -\n")
        time.sleep(1)  # Ждем выполнения команды

        # Если вдруг запросит пароль (но в вашем случае не требуется)
        if sudo_password and shell.recv_ready():
            output = shell.recv(1024).decode("utf-8", errors="replace")
            if "password" in output.lower():
                shell.send(f"{sudo_password}\n".encode("utf-8"))
                time.sleep(1)

        # Отправляем команды
        for cmd in commands:
            shell.send(f"{cmd}\n".encode("utf-8"))
            time.sleep(1)  # Даем время на выполнение

        # Завершаем сессию
        shell.send(b"exit\n")  # Выход из root-сессии
        shell.send(b"exit\n")  # Выход из SSH
        time.sleep(1)

        # Получаем вывод (если нужно)
        output = ""
        max_wait_time = timeout
        start_time = time.time()
        command_completed = False
        while time.time() - start_time < max_wait_time:
            if shell.recv_ready():
                chunk = shell.recv(4096).decode("utf-8", errors="replace")
                output += chunk

            if "all command done" in output:
                command_completed = True
                break
        else:
            time.sleep(0.1)
        # Проверяем, завершились ли команды
        if not command_completed:
            timeout_msg = f"TIMEOUT: Команды не завершились за {timeout} секунд"
            output += f"\n{timeout_msg}"
            log_result(host, commands + ["TIMEOUT"], output)

            # Попытка принудительного завершения
            try:
                shell.send(b"\x03")  # Ctrl+C
                time.sleep(1)
                shell.send(b"exit\n")
                shell.send(b"exit\n")
            except:
                pass

            raise TimeoutError(
                f"Команды на хосте {host} не завершились за {timeout} секунд"
            )

        # Логируем результат
        log_result(host, commands, output)
        return output

    except Exception as e:
        log_result(host, commands, str(e))
        raise
    finally:
        ssh.close()


def log_result(host, commands, output):
    """Логирует результат выполнения команд"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = "commands.log"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [{host}] Выполнены команды:\n")
        for cmd in commands:
            f.write(f" - {cmd}\n")
        f.write(f"Вывод:\n{output}\n")
        f.write("-" * 50 + "\n")


if __name__ == "__main__":
    try:
        host = "10.9.30.101"
        username = "otis"
        password = "MzL2qqOp"
        sudo_pass = None  # Если пароль не нужен, оставляем None

        commands = [
            "systemctl restart nginx",
            'echo "Nginx перезапущен"',
            'echo "all command done"',
        ]

        result = _execute_shell_comands(host, username, password, commands, sudo_pass)
        # print("Результат выполнения команд:")
        # print(result)

    except Exception as e:
        print(f"Ошибка: {e}")
