import asyncio, os, aiofiles, csv, glob, paramiko
from datetime import datetime

# ========= КОНФИГУРАЦИЯ =========
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
HOSTS_FILE = os.path.join(CURRENT_DIR, "ip_list_combined.txt")  # Список хостов
LOG_FILE = os.path.join(CURRENT_DIR, "command_combined.log")  # Единый лог-файл
PING_RESULTS_FILE = os.path.join(
    CURRENT_DIR, "ping_results_combined.csv"
)  # Файл с результатами ping
COMMAND_FILE = os.path.join(CURRENT_DIR, "command_combined.txt")
MAX_CONCURRENT_TASKS = 5  # Максимальное количество одновременных задач, не увлекайтесь
USER = "tc"
PASSWORD = "JnbcHekbn123"
SSH_PORT = 22  # Порт SSH
SSH_TIMEOUT = 30  # Таймаут соединения SSH
COMMAND_TIMEOUT = 1800  # Таймаут выполнения команд

# Параметры для загрузки файлов и выполнения команд
UPLOAD_FILE = True  # Флаг включения/выключения загрузки файлов
COMMAND_EXECUTE = True  # Флаг включения/выключения выполнения команд
UPLOAD_FOLDER = "/tmp"  # Путь на хосте куда загружать файлы
LOCAL_FILES = os.path.join(
    CURRENT_DIR, "upload_files"
)  # Директория с файлами для загрузки
# ================================


def setup_files():
    """Создаем лог-файлы и CSV с заголовками"""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("")  # Очищаем файл при запуске

    # Создаем CSV файл с заголовками
    with open(PING_RESULTS_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["IP", "Ping Status", "Timestamp"])

    # Создаем директорию для файлов загрузки если её нет
    if UPLOAD_FILE and not os.path.exists(LOCAL_FILES):
        os.makedirs(LOCAL_FILES, exist_ok=True)
        print(f"Создана директория для файлов загрузки: {LOCAL_FILES}")

def get_files_to_upload():
    """Получаем список файлов из директории для загрузки"""
    if not os.path.exists(LOCAL_FILES):
        return []

    files_list = []
    # Получаем все файлы из директории (не включая поддиректории)
    for file_path in glob.glob(os.path.join(LOCAL_FILES, "*")):
        if os.path.isfile(file_path):
            files_list.append(file_path)

    return files_list


async def log_message(message):
    """Запись сообщения в лог"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    print(log_entry.strip())
    async with aiofiles.open(LOG_FILE, "a", encoding="utf-8") as f:
        await f.write(log_entry)


async def record_ping_result(ip, status):
    """Записываем результат ping в CSV файл"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(PING_RESULTS_FILE, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([ip, status, timestamp])


async def check_ping(host):
    """Асинхронная проверка ping с записью результата в CSV"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping",
            "-n",
            "1",
            "-w",
            "1000",
            host,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if "TTL=" in stdout.decode():
            status = "Success"
            await record_ping_result(host, status)
            return True
        else:
            status = "Failed"
            await record_ping_result(host, status)
            return False
    except Exception as e:
        status = f"Error: {str(e)}"
        await record_ping_result(host, status)
        return False

async def create_ssh_connection(host):
    """Создает SSH соединение с хостом"""

    def _connect():
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(
                hostname=host,
                port=SSH_PORT,
                username=USER,
                password=PASSWORD,
                timeout=SSH_TIMEOUT,
                banner_timeout=SSH_TIMEOUT,
                auth_timeout=SSH_TIMEOUT,
            )
            return ssh, None
        except Exception as e:
            return None, str(e)

    try:
        ssh, error = await asyncio.to_thread(_connect)
        return ssh, error
    except Exception as e:
        return None, str(e)


async def run_ssh_sftp_upload(host):
    """Асинхронная загрузка файлов через SFTP"""
    files_to_upload = get_files_to_upload()

    if not files_to_upload:
        await log_message(f"{host}  Нет файлов для загрузки в директории {LOCAL_FILES}")
        return True

    success_count = 0
    total_files = len(files_to_upload)

    await log_message(f"{host}  Найдено файлов для загрузки: {total_files}")

    # Создаем SSH соединение
    ssh, error = await create_ssh_connection(host)
    if ssh is None:
        await log_message(
            f"{host}  Ошибка подключения SSH для загрузки файлов: {error}"
        )
        return False

    try:
        # Создаем SFTP клиент
        def _create_sftp():
            return ssh.open_sftp()

        sftp = await asyncio.to_thread(_create_sftp)

        try:
            # Проверяем и создаем директорию назначения если нужно
            def _check_and_create_dir():
                try:
                    sftp.stat(UPLOAD_FOLDER)
                except FileNotFoundError:
                    try:
                        sftp.mkdir(UPLOAD_FOLDER)
                        return f"Создана директория {UPLOAD_FOLDER}"
                    except Exception as e:
                        return f"Ошибка создания директории {UPLOAD_FOLDER}: {str(e)}"
                return None

            dir_result = await asyncio.to_thread(_check_and_create_dir)
            if dir_result:
                await log_message(f"{host}  {dir_result}")

            # Загружаем файлы
            for local_file in files_to_upload:
                filename = os.path.basename(local_file)
                remote_path = f"{UPLOAD_FOLDER}/{filename}"

                try:

                    def _upload_file():
                        sftp.put(local_file, remote_path)
                        return sftp.stat(remote_path)

                    stat_result = await asyncio.to_thread(_upload_file)
                    await log_message(
                        f"{host}  Файл {filename} успешно загружен ({stat_result.st_size} байт)"
                    )
                    success_count += 1

                except Exception as e:
                    await log_message(
                        f"{host}  Ошибка загрузки файла {filename}: {str(e)}"
                    )

        finally:
            sftp.close()

    except Exception as e:
        await log_message(f"{host}  Ошибка создания SFTP соединения: {str(e)}")
    finally:
        ssh.close()

    if success_count == total_files:
        await log_message(
            f"{host}  Все файлы ({success_count}/{total_files}) успешно загружены"
        )
        return True
    else:
        await log_message(f"{host}  Загружено файлов: {success_count}/{total_files}")
        return success_count > 0


async def run_ssh_commands(host):
    """Асинхронное выполнение команд через SSH"""
    # Читаем команды из файла
    try:
        with open(COMMAND_FILE, "r", encoding="utf-8") as f:
            commands = f.read().strip()
    except Exception as e:
        await log_message(f"{host}  Ошибка чтения файла команд: {str(e)}")
        return

    if not commands:
        await log_message(f"{host}  Файл команд пуст")
        return

    # Создаем SSH соединение
    ssh, error = await create_ssh_connection(host)
    if ssh is None:
        await log_message(
            f"{host}  Ошибка подключения SSH для выполнения команд: {error}"
        )
        return

    try:

        def _execute_commands():
            # Выполняем команды
            stdin, stdout, stderr = ssh.exec_command(commands, timeout=COMMAND_TIMEOUT)

            # Читаем результаты
            stdout_data = stdout.read().decode("utf-8", errors="ignore")
            stderr_data = stderr.read().decode("utf-8", errors="ignore")
            exit_status = stdout.channel.recv_exit_status()

            return stdout_data, stderr_data, exit_status

        try:
            stdout_data, stderr_data, exit_status = await asyncio.to_thread(
                _execute_commands
            )

            if exit_status == 0:
                await log_message(f"{host}  Команды выполнены успешно\n{stdout_data}")
            else:
                await log_message(
                    f"{host}  Ошибка выполнения команд (код {exit_status})\n{stderr_data}"
                )

        except asyncio.TimeoutError:
            await log_message(f"{host}  Таймаут выполнения команд")
        except Exception as e:
            await log_message(f"{host}  Ошибка выполнения команд: {str(e)}")

    finally:
        ssh.close()


async def process_host(host, remaining_counter):
    """Обработка одного хоста"""
    remaining = remaining_counter["total"] - remaining_counter["processed"]
    await log_message(f"Обработка {host} | Осталось хостов: {remaining}")

    ping_success = await check_ping(host)
    if ping_success:
        # Если включена загрузка файлов, сначала выполняем загрузку
        if UPLOAD_FILE:
            await log_message(f"{host}  Начинаем загрузку файлов...")
            upload_success = await run_ssh_sftp_upload(host)
            if upload_success:
                await log_message(f"{host}  Загрузка файлов завершена")
            else:
                await log_message(f"{host}  Ошибка при загрузке файлов")

        # Если включено выполнение команд, выполняем команды через SSH
        if COMMAND_EXECUTE:
            await log_message(f"{host}  Начинаем выполнение команд...")
            await run_ssh_commands(host)
        else:
            await log_message(f"{host}  Выполнение команд отключено")
    else:
        await log_message(f"{host}  Ping неуспешен, хост пропущен")

    remaining_counter["processed"] += 1


async def main():
    setup_files()

    # Проверяем конфигурацию
    if not UPLOAD_FILE and not COMMAND_EXECUTE:
        await log_message(
            "ВНИМАНИЕ: Отключены и загрузка файлов, и выполнение команд! Будет выполняться только ping."
        )

    # Проверяем наличие файлов для загрузки если включена загрузка
    if UPLOAD_FILE:
        files_to_upload = get_files_to_upload()
        if not files_to_upload:
            await log_message(
                f"ВНИМАНИЕ: Включена загрузка файлов, но в директории {LOCAL_FILES} нет файлов!"
            )
        else:
            await log_message(
                f"Найдено {len(files_to_upload)} файлов для загрузки в директории {LOCAL_FILES}"
            )

    # Проверяем наличие файла команд если включено выполнение команд
    if COMMAND_EXECUTE:
        if not os.path.exists(COMMAND_FILE):
            await log_message(
                f"ВНИМАНИЕ: Включено выполнение команд, но файл {COMMAND_FILE} не найден!"
            )

    # Чтение хостов
    async with aiofiles.open(HOSTS_FILE, "r") as f:
        hosts = [line.strip() async for line in f if line.strip()]

    total_hosts = len(hosts)
    await log_message(f"Начало обработки {total_hosts} хостов")

    # Логируем настройки
    config_status = []
    if UPLOAD_FILE:
        config_status.append(f"Загрузка файлов: включена (папка: {UPLOAD_FOLDER})")
    else:
        config_status.append("Загрузка файлов: отключена")

    if COMMAND_EXECUTE:
        config_status.append("Выполнение команд: включено")
    else:
        config_status.append("Выполнение команд: отключено")

    await log_message(" | ".join(config_status))

    # Счетчик обработанных хостов
    counter = {"total": total_hosts, "processed": 0}

    # Создаем семафор для ограничения количества одновременных задач
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

    async def limited_task(host):
        async with semaphore:
            await process_host(host, counter)

    # Запускаем задачи
    tasks = [limited_task(host) for host in hosts]
    await asyncio.gather(*tasks)

    await log_message(
        f"Обработка завершена. Всего обработано: {counter['processed']}/{counter['total']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
