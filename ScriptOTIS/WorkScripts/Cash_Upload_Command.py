import asyncio
import csv
from datetime import datetime
import os
import aiofiles
import glob

# ========= КОНФИГУРАЦИЯ =========
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
HOSTS_FILE = os.path.join(CURRENT_DIR, "ip_list_combined.txt")  # Список хостов
LOG_FILE = os.path.join(CURRENT_DIR, "command_combined.log")  # Единый лог-файл
PING_RESULTS_FILE = os.path.join(
    CURRENT_DIR, "ping_results_combined.csv"
)  # Файл с результатами ping
COMMAND_FILE = os.path.join(CURRENT_DIR, "command_combined.txt")
MAX_CONCURRENT_TASKS = 5  # Максимальное количество одновременных задач, не увлекайтесь
PLINK_CMD = "plink.exe -ssh {user}@{host} -pw {password} -batch -m {command_txt}"
USER = "tc"
PASSWORD = "JnbcHekbn123"

# Параметры для загрузки файлов и выполнения команд
UPLOAD_FILE = True  # Флаг включения/выключения загрузки файлов
COMMAND_EXECUTE = True  # Флаг включения/выключения выполнения команд
UPLOAD_FOLDER = "/tmp"  # Путь на хосте куда загружать файлы
PSCP_CMD = "pscp.exe -pw {password} -scp -P 22 {local_file} {user}@{host}:{remote_path}"
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


async def run_pscp(host):
    """Асинхронная загрузка файлов через pscp"""
    files_to_upload = get_files_to_upload()

    if not files_to_upload:
        await log_message(f"{host}  Нет файлов для загрузки в директории {LOCAL_FILES}")
        return True

    success_count = 0
    total_files = len(files_to_upload)

    await log_message(f"{host}  Найдено файлов для загрузки: {total_files}")

    for local_file in files_to_upload:
        filename = os.path.basename(local_file)
        remote_path = f"{UPLOAD_FOLDER}/{filename}"

        cmd = PSCP_CMD.format(
            password=PASSWORD,
            local_file=local_file,
            user=USER,
            host=host,
            remote_path=remote_path,
        )

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
                stdout = stdout.decode().strip()
                stderr = stderr.decode().strip()

                if proc.returncode == 0:
                    await log_message(f"{host}  Файл {filename} успешно загружен")
                    success_count += 1
                else:
                    await log_message(
                        f"{host}  Ошибка загрузки {filename} (код {proc.returncode}): {stderr}"
                    )

            except asyncio.TimeoutError:
                await log_message(f"{host}  Таймаут загрузки файла {filename}")
                proc.kill()
                await proc.communicate()

        except Exception as e:
            await log_message(
                f"{host}  Критическая ошибка при загрузке {filename}: {str(e)}"
            )

    if success_count == total_files:
        await log_message(
            f"{host}  Все файлы ({success_count}/{total_files}) успешно загружены"
        )
        return True
    else:
        await log_message(f"{host}  Загружено файлов: {success_count}/{total_files}")
        return success_count > 0  # Возвращаем True если хотя бы один файл загружен


async def run_plink(host):
    """Асинхронное выполнение команды через plink"""
    cmd = PLINK_CMD.format(
        user=USER, password=PASSWORD, command_txt=COMMAND_FILE, host=host
    )
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=1800)
            stdout = stdout.decode().strip()
            stderr = stderr.decode().strip()

            if proc.returncode == 0:
                await log_message(f"{host}  Команды выполнены успешно\n{stdout}")
            else:
                await log_message(
                    f"{host}  Ошибка выполнения команд (код {proc.returncode})\n{stderr}"
                )
        except asyncio.TimeoutError:
            await log_message(f"{host}  Таймаут выполнения команд")
            proc.kill()
            await proc.communicate()
    except Exception as e:
        await log_message(f"{host}  Критическая ошибка при выполнении команд: {str(e)}")


async def process_host(host, remaining_counter):
    """Обработка одного хоста"""
    remaining = remaining_counter["total"] - remaining_counter["processed"]
    await log_message(f"Обработка {host} | Осталось хостов: {remaining}")

    ping_success = await check_ping(host)
    if ping_success:
        # Если включена загрузка файлов, сначала выполняем загрузку
        if UPLOAD_FILE:
            await log_message(f"{host}  Начинаем загрузку файлов...")
            upload_success = await run_pscp(host)
            if upload_success:
                await log_message(f"{host}  Загрузка файлов завершена")
            else:
                await log_message(f"{host}  Ошибка при загрузке файлов")

        # Если включено выполнение команд, выполняем команды через plink
        if COMMAND_EXECUTE:
            await log_message(f"{host}  Начинаем выполнение команд...")
            await run_plink(host)
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
