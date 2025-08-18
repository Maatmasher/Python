def collect_merchant_info(self, host_info):
    """Сбор merchant информации с одного хоста"""
    host_ip = host_ip = host_info["ip"]
    start_time = time.time()

    commands = {
        "sbpMerchantId": 'awk -F\'[ ="]+\' \'/key="sbpMerchantId"/ {for(i=1;i<=NF;i++) if($i=="value") print $(i+1)}\' /home/tc/storage/crystal-cash/config/register-external-systems.xml',
        "secretKey": 'awk -F\'[ ="]+\' \'/key="secretKey"/ {for(i=1;i<=NF;i++) if($i=="value") print $(i+1)}\' /home/tc/storage/crystal-cash/config/register-external-systems.xml',
        "account": 'awk -F\'[ ="]+\' \'/key="account"/ {for(i=1;i<=NF;i++) if($i=="value") print $(i+1)}\' /home/tc/storage/crystal-cash/config/register-external-systems.xml',
    }

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Подключение с паролем
        ssh.connect(
            host_ip,
            username=self.username,
            password=self.password,
            timeout=10,
            banner_timeout=10,
            auth_timeout=10,
            look_for_keys=False,
            allow_agent=False,
        )

        results = {}
        for key, cmd in commands.items():
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode().strip()
            error_output = stderr.read().decode().strip()

            if output and not error_output:
                results[key] = output
            else:
                results[key] = None
                self.logger.warning(
                    f"{host_ip}: не удалось получить {key}, ошибка: {error_output or 'нет вывода'}"
                )

        execution_time = round(time.time() - start_time, 2)

        with self.lock:
            self.results.append(
                {
                    "IP": host_ip,
                    "SbpMerchantId": results["sbpMerchantId"],
                    "SecretKey": results["secretKey"],
                    "Account": results["account"],
                    "Collection_Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Response_Time": f"{execution_time}s",
                }
            )

        self.logger.info(
            f"✓ {host_ip}: успешно собрана merchant информация ({execution_time}s)"
        )

    except paramiko.AuthenticationException as e:
        self._log_error(host_ip, f"Ошибка аутентификации: неверный пароль", host_info)
    except paramiko.SSHException as e:
        self._log_error(host_ip, f"SSH ошибка: {str(e)}", host_info)
    except Exception as e:
        self._log_error(host_ip, f"Общая ошибка: {str(e)}", host_info)
    finally:
        try:
            ssh.close()
        except:
            pass
