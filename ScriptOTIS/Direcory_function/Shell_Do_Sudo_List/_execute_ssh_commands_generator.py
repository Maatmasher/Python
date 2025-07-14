def _execute_ssh_commands_generator(
    host, commands, username=USERNAME, password=PASSWORD
):
    """Выполняет список SSH команд последовательно в рамках одной сессии"""
    ssh = None
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=username, password=password)

        print(f"SSH соединение с {host} установлено")

        for cmd_index, command in enumerate(commands, 1):
            try:
                print(f"Выполняем команду {cmd_index}/{len(commands)}: {command}")

                stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)
                output = []
                error = []
                start_time = time.time()

                while True:
                    while stdout.channel.recv_ready():
                        chunk = clean_ansi_escape(stdout.channel.recv(1024).decode())
                        output.append(chunk)
                        print(chunk, end="")

                    while stderr.channel.recv_stderr_ready():
                        chunk = clean_ansi_escape(
                            stderr.channel.recv_stderr(1024).decode()
                        )
                        error.append(chunk)
                        print(chunk, end="", file=sys.stderr)

                    if stdout.channel.exit_status_ready():
                        break

                    if time.time() - start_time > TIMEOUT:
                        yield False, f"Команда {cmd_index} превысила таймаут ({TIMEOUT}с): {command}", cmd_index
                        return

                    time.sleep(0.1)

                exit_status = stdout.channel.recv_exit_status()
                full_output = "".join(output).strip()
                full_error = "".join(error).strip()

                if exit_status == 0:
                    yield True, full_output, cmd_index
                else:
                    error_msg = (
                        full_error
                        if full_error
                        else f"Команда завершилась с кодом {exit_status}"
                    )
                    yield False, error_msg, cmd_index

            except Exception as e:
                yield False, f"Ошибка выполнения команды {cmd_index}: {str(e)}", cmd_index

    except (paramiko.AuthenticationException, paramiko.SSHException, socket.error) as e:
        yield False, f"Ошибка SSH соединения с {host}: {str(e)}", 0
    finally:
        if ssh:
            try:
                ssh.close()
                print(f"SSH соединение с {host} закрыто")
            except:
                pass
