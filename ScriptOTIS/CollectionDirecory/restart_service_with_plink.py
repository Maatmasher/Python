def restart_service_with_plink(self, servers: List[str], command_file: str) -> bool:
    """Перезапускает службу на серверах используя PLINK"""
    try:
        # Путь к файлу с командами
        command_filepath = self.configurator.config_dir / command_file
        if not command_filepath.exists():
            logging.error(f"Файл команд {command_file} не найден")
            return False

        # Читаем команды из файла
        with open(command_filepath, "r", encoding="utf-8") as f:
            commands = [line.strip() for line in f.readlines() if line.strip()]

        # Путь к plink.exe
        plink_path = self.configurator.config_dir / "plink.exe"
        if not plink_path.exists():
            logging.error("plink.exe не найден")
            return False

        # Выполняем команды для каждого сервера
        for server_info in servers:
            # Извлекаем IP из формата "индекс-тип-ip-версия"
            parts = server_info.split("-")
            if len(parts) < 3:
                logging.error(f"Неверный формат строки сервера: {server_info}")
                continue

            server_ip = parts[2]
            logging.info(f"Перезапуск службы на сервере {server_ip}")

            for command in commands:
                try:
                    result = subprocess.run(
                        [str(plink_path), "-batch", server_ip, command],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )

                    if result.returncode != 0:
                        logging.error(
                            f"Ошибка выполнения команды на {server_ip}: {result.stderr}"
                        )
                        return False

                    logging.info(f"Команда выполнена на {server_ip}: {command}")

                except subprocess.TimeoutExpired:
                    logging.error(f"Таймаут выполнения команды на {server_ip}")
                    return False
                except Exception as e:
                    logging.error(f"Ошибка при выполнении команды на {server_ip}: {e}")
                    return False

            time.sleep(2)  # Пауза между серверами

        return True

    except Exception as e:
        logging.error(f"Общая ошибка при перезапуске служб: {e}")
        return False
