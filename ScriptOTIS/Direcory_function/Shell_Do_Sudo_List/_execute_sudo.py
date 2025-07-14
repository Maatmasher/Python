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
