import paramiko
from datetime import datetime
import time


class SSHExecutor:
    def __init__(self, host, username, password=None, key_filename=None):
        self.host = host
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.shell = None
        self.connected = False

    def connect(self):
        """Устанавливает SSH соединение"""
        try:
            self.ssh.connect(
                hostname=self.host,
                username=self.username,
                password=self.password,
                key_filename=self.key_filename,
                timeout=10,  # Добавляем таймаут
            )
            self.connected = True
            return True
        except Exception as e:
            self._log_error(f"Ошибка подключения: {str(e)}")
            self.connected = False
            return False

    def execute_commands(self, commands):
        """Выполняет список команд последовательно"""
        if not self.connected and not self.connect():
            return None

        results = []
        try:
            for cmd in commands:
                result = {
                    "command": cmd,
                    "output": "",
                    "error": "",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

                try:
                    # Все команды выполняем через exec_command для надежности
                    stdin, stdout, stderr = self.ssh.exec_command(cmd, timeout=30)

                    # Ждем завершения команды
                    exit_status = stdout.channel.recv_exit_status()

                    # Читаем вывод
                    output = stdout.read().decode("utf-8").strip()
                    error = stderr.read().decode("utf-8").strip()

                    result["output"] = output
                    result["error"] = error
                    result["exit_status"] = exit_status

                    if exit_status != 0 or error:
                        self._log_error(
                            f"Команда '{cmd}' завершилась с ошибкой (статус {exit_status}): {error}"
                        )

                except Exception as e:
                    error_msg = f"Ошибка выполнения команды '{cmd}': {str(e)}"
                    result["error"] = error_msg
                    self._log_error(error_msg)

                self._log_command(cmd, result["output"], result["error"])
                results.append(result)

            return results

        finally:
            self.close()

    def _log_command(self, command, output, error):
        """Логирует выполнение команды"""
        log_entry = (
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Команда: {command}\n"
        )
        if output:
            log_entry += f"Вывод:\n{output}\n"
        if error:
            log_entry += f"Ошибка:\n{error}\n"
        log_entry += "-" * 50 + "\n"

        with open("ssh_commands.log", "a", encoding="utf-8") as f:
            f.write(log_entry)

    def _log_error(self, error_msg):
        """Логирует ошибки"""
        log_entry = (
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ОШИБКА: {error_msg}\n"
        )
        log_entry += "-" * 50 + "\n"

        with open("ssh_errors.log", "a", encoding="utf-8") as f:
            f.write(log_entry)

    def close(self):
        """Закрывает соединение"""
        try:
            if hasattr(self, "shell") and self.shell:
                self.shell.close()
            if hasattr(self, "ssh") and self.ssh:
                self.ssh.close()
        except:
            pass
        finally:
            self.connected = False


# Пример использования
if __name__ == "__main__":
    # Настройки подключения
    config = {
        "host": "10.9.30.101",
        "username": "otis",
        "password": "MzL2qqOp",  # Или используйте key_filename
        # 'key_filename': '/path/to/private_key'
    }

    # Список команд для выполнения
    commands = [
        "sudo su - << END_IN systemctl restart nginx END_IN",
        'echo "Тестовая команда"',
    ]

    # Создаем экземпляр и выполняем команды
    executor = SSHExecutor(**config)
    results = executor.execute_commands(commands)

    # Выводим результаты
    if results:
        print("Результаты выполнения команд:")
        for res in results:
            print(f"\nКоманда: {res['command']}")
            print(f"Время: {res['timestamp']}")
            print(f"Статус: {res.get('exit_status', 'N/A')}")
            if res["output"]:
                print(f"Вывод:\n{res['output']}")
            if res["error"]:
                print(f"Ошибка:\n{res['error']}")
    else:
        print("Не удалось выполнить команды")
