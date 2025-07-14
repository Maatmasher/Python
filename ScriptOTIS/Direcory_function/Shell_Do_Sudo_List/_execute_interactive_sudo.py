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
