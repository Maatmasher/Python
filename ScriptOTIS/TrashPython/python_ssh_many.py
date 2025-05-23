import paramiko
from datetime import datetime

class SSHExecutor:
    def __init__(self, host, username, password=None, key_filename=None):
        self.host = host
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.shell = None

    def connect(self):
        """Устанавливает SSH соединение"""
        try:
            self.ssh.connect(
                hostname=self.host,
                username=self.username,
                password=self.password,
                key_filename=self.key_filename
            )
            self.shell = self.ssh.invoke_shell()
            return True
        except Exception as e:
            self._log_error(f"Ошибка подключения: {str(e)}")
            return False

    def execute_commands(self, commands):
        """Выполняет список команд последовательно"""
        if not self.connect():
            return None

        results = []
        try:
            for cmd in commands:
                # Для интерактивных команд используем shell
                if cmd.strip().endswith('&&') or cmd.strip().endswith(';'):
                    self.shell.send(cmd + "\n")
                    output = self._read_shell_output()
                else:
                    # Для одиночных команд используем exec_command
                    stdin, stdout, stderr = self.ssh.exec_command(cmd)
                    output = stdout.read().decode('utf-8').strip()
                    error = stderr.read().decode('utf-8').strip()

                    if error:
                        self._log_error(f"Ошибка выполнения команды '{cmd}': {error}")
                
                results.append({
                    'command': cmd,
                    'output': output,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                self._log_command(cmd, output)

            return results
        finally:
            self.close()

    def _read_shell_output(self, timeout=5):
        """Читает вывод из shell с таймаутом"""
        import time
        start_time = time.time()
        output = ""
        
        while time.time() - start_time < timeout:
            if self.shell.recv_ready():
                output += self.shell.recv(1024).decode('utf-8')
            else:
                time.sleep(0.1)
        
        return output.strip()

    def _log_command(self, command, output):
        """Логирует выполнение команды"""
        log_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Команда: {command}\n"
        log_entry += f"Вывод:\n{output}\n" if output else "Нет вывода\n"
        log_entry += "-"*50 + "\n"
        
        with open("ssh_commands.log", "a", encoding="utf-8") as f:
            f.write(log_entry)

    def _log_error(self, error_msg):
        """Логирует ошибки"""
        log_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ОШИБКА: {error_msg}\n"
        log_entry += "-"*50 + "\n"
        
        with open("ssh_errors.log", "a", encoding="utf-8") as f:
            f.write(log_entry)

    def close(self):
        """Закрывает соединение"""
        if self.shell:
            self.shell.close()
        self.ssh.close()

# Пример использования
if __name__ == "__main__":
    # Настройки подключения
    config = {
        'host': 'ваш_сервер',
        'username': 'ваш_пользователь',
        'password': 'ваш_пароль',  # Или используйте key_filename
        # 'key_filename': '/path/to/private_key'
    }

    # Список команд для выполнения
    commands = [
        'cd /tmp',
        'ls -l',
        'echo "Содержимое файла:" && cat test.txt',
        'df -h'
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
            print(f"Вывод:\n{res['output']}")
    else:
        print("Не удалось выполнить команды")