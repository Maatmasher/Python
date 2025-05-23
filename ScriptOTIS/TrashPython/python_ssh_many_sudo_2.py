import paramiko, time
from datetime import datetime

def log_error(host, commands, error_msg):
    """Логирует ошибки в файл"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = "ssh_errors.log"
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] [{host}] Ошибка при выполнении команд:\n")
        for cmd in commands:
            f.write(f" - {cmd}\n")
        f.write(f"Сообщение об ошибке: {error_msg}\n")
        f.write("-" * 50 + "\n")

def log_result(host, commands, output):
    """Логирует результат выполнения команд"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = "sudo_commands.log"
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] [{host}] Выполнены команды:\n")
        for cmd in commands:
            f.write(f" - {cmd}\n")
        f.write(f"Вывод:\n{output}\n")
        f.write("-" * 50 + "\n")

def execute_sudo_commands(host, username, password, commands, sudo_password=None):
    """Выполняет команды с sudo/su через SSH"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Подключаемся к серверу
        ssh.connect(host, username=username, password=password)
        
        # Создаем интерактивную сессию
        shell = ssh.invoke_shell()
        time.sleep(1)
        
        # Преобразуем команды в bytes перед отправкой
        shell.send(b'sudo su -\n')  # Обратите внимание на префикс b
        time.sleep(1)
        
        if sudo_password:
            shell.send(f'{sudo_password}\n'.encode('utf-8'))
            time.sleep(1)
        
        for cmd in commands:
            shell.send(f'{cmd}\n'.encode('utf-8'))
            time.sleep(1)
        
        shell.send(b'exit\n')
        shell.send(b'exit\n')
        time.sleep(1)
        
        # Читаем вывод
        output = b''
        while shell.recv_ready():
            output += shell.recv(4096)
        
        # Декодируем вывод в строку
        decoded_output = output.decode('utf-8', errors='replace')
        
        log_result(host, commands, decoded_output)
        return decoded_output
        
    except Exception as e:
        error_msg = str(e)
        log_error(host, commands, error_msg)
        raise Exception(f"Ошибка при выполнении команд: {error_msg}")
    finally:
        try:
            ssh.close()
        except:
            pass

if __name__ == "__main__":
    try:
        host = "ваш_сервер"
        username = "ваш_пользователь"
        password = "ваш_пароль_ssh"
        sudo_pass = "ваш_пароль_sudo"
        
        commands = [
            'systemctl restart nginx',
            'echo "Nginx перезапущен"',
            'systemctl status nginx --no-pager'
        ]
        
        print("Выполняем команды на сервере...")
        result = execute_sudo_commands(host, username, password, commands, sudo_pass)
        print("Результат выполнения команд:")
        print(result)
        
    except Exception as e:
        print(f"Произошла ошибка: {e}")