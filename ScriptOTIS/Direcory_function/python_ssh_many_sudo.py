import paramiko
from datetime import datetime

def execute_sudo_commands(host, username, password, commands, sudo_password=None):
    """Выполняет команды с sudo/su через SSH"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Подключаемся к серверу
        ssh.connect(host, username=username, password=password)
        
        # Создаем интерактивную сессию
        shell = ssh.invoke_shell()
        
        # Отправляем команду sudo su -
        shell.send('sudo su -\n')
        
        # Ждем приглашения пароля (если требуется)
        time.sleep(1)
        if sudo_password:
            shell.send(f'{sudo_password}\n')
            time.sleep(1)
        
        # Отправляем все команды
        for cmd in commands:
            shell.send(f'{cmd}\n')
            time.sleep(0.5)  # Даем время на выполнение
        
        # Завершаем сессию
        shell.send('exit\n')
        shell.send('exit\n')
        time.sleep(1)
        
        # Получаем весь вывод
        output = ''
        while shell.recv_ready():
            output += shell.recv(1024).decode('utf-8')
        
        # Логируем результат
        log_result(host, commands, output)
        
        return output
        
    except Exception as e:
        log_error(host, commands, str(e))
        raise
    finally:
        ssh.close()

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

# Пример использования
if __name__ == "__main__":
    try:
        # Параметры подключения
        host = "ваш_сервер"
        username = "ваш_пользователь"
        password = "ваш_пароль_ssh"
        sudo_pass = "ваш_пароль_sudo"  # если требуется
        
        # Команды для выполнения внутри sudo su -
        commands = [
            'systemctl restart nginx',
            'echo "Nginx перезапущен"',
            'systemctl status nginx --no-pager'
        ]
        
        # Выполняем команды
        result = execute_sudo_commands(host, username, password, commands, sudo_pass)
        print("Результат выполнения команд:")
        print(result)
        
    except Exception as e:
        print(f"Ошибка: {e}")