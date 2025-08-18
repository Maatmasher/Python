import asyncio, csv, os, aiofiles
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
PLINK_CMD = "plink.exe -ssh {user}@{host} -pw {password} -batch -m {command_txt}"
USER = "tc"
PASSWORD = "JnbcHekbn123"
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
                await log_message(f"{host}  Успешно\n{stdout}")
            else:
                await log_message(f"{host}  Ошибка (код {proc.returncode})\n{stderr}")
        except asyncio.TimeoutError:
            await log_message(f"{host}  Таймаут выполнения")
            proc.kill()
            await proc.communicate()
    except Exception as e:
        await log_message(f"{host}  Критическая ошибка: {str(e)}")


async def process_host(host, remaining_counter):
    """Обработка одного хоста"""
    remaining = remaining_counter["total"] - remaining_counter["processed"]
    await log_message(f"Обработка {host} | Осталось хостов: {remaining}")

    ping_success = await check_ping(host)
    if ping_success:
        await run_plink(host)

    remaining_counter["processed"] += 1


async def main():
    setup_files()

    # Чтение хостов
    async with aiofiles.open(HOSTS_FILE, "r") as f:
        hosts = [line.strip() async for line in f if line.strip()]

    total_hosts = len(hosts)
    await log_message(f"Начало обработки {total_hosts} хостов")

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
