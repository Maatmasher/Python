# ==============================================================

import paramiko


def manage_linux_service(host, username, password, service_name, action):
    """
    Действия: 'start', 'stop', 'restart', 'status'
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=username, password=password)

    if action == "status":
        cmd = f"systemctl status {service_name}"
    else:
        cmd = f"sudo systemctl {action} {service_name}"

    stdin, stdout, stderr = client.exec_command(cmd)
    output = stdout.read().decode()
    error = stderr.read().decode()
    client.close()
    return output, error


# Пример использования
output, error = manage_linux_service(
    "192.168.1.101", "user", "password123", "nginx", "restart"
)
