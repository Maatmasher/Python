import asyncio
#import subprocess
from datetime import datetime
import os
import aiofiles

# Конфигурация
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
HOSTS_FILE = os.path.join(CURRENT_DIR, "ip_list.txt")  # Список хостов
LOG_DIR = os.path.join(CURRENT_DIR, "logs")
COMMAND_FILE = os.path.join(CURRENT_DIR, "command.txt")
MAX_CONCURRENT_TASKS = 10  # Максимальное количество одновременных задач
PLINK_CMD = "plink.exe -ssh {user}@{host} -pw {password} -batch -m {command_txt}"
USER = "tc"
PASSWORD = "JnbcHekbn123"  # Лучше использовать SSH-ключи!


def setup_logging():
    """Создаем папку для логов"""
    os.makedirs(LOG_DIR, exist_ok=True)


async def log_message(host, message):
    """Запись сообщения в лог хоста"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    print(f"{host}: {log_entry.strip()}")
    log_file = f"{LOG_DIR}/{host.replace('.', '_')}.log"
    async with aiofiles.open(log_file, "a", encoding="utf-8") as f:
        await f.write(log_entry)


async def check_ping(host):
    """Асинхронная проверка ping"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-n", "1", "-w", "1000", host,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if "TTL=" in stdout.decode():
            await log_message(host, f" Ping успешен")
            return True
        else:
            await log_message(host, f" Ping не прошел")
            return False
    except Exception as e:
        await log_message(host, f" Ошибка ping: {str(e)}")
        return False


async def run_plink(host):
    """Асинхронное выполнение команды через plink"""
    cmd = PLINK_CMD.format(user=USER, password=PASSWORD, command_txt=COMMAND_FILE, host=host)
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=3600)
            stdout = stdout.decode().strip()
            stderr = stderr.decode().strip()
            
            if proc.returncode == 0:
                await log_message(host, f" Успешно\n{stdout}")
            else:
                await log_message(host, f" Ошибка (код {proc.returncode})\n{stderr}")
        except asyncio.TimeoutError:
            await log_message(host, " Таймаут выполнения")
            proc.kill()
            await proc.communicate()
    except Exception as e:
        await log_message(host, f" Критическая ошибка: {str(e)}")


async def process_host(host):
    """Обработка одного хоста"""
    if await check_ping(host):
        await run_plink(host)


async def main():
    setup_logging()

    # Чтение хостов
    async with aiofiles.open(HOSTS_FILE, "r") as f:
        hosts = [line.strip() async for line in f if line.strip()]

    print(f"Всего хостов: {len(hosts)}")

    # Создаем семафор для ограничения количества одновременных задач
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

    async def limited_task(host):
        async with semaphore:
            await process_host(host)

    # Запускаем задачи
    tasks = [limited_task(host) for host in hosts]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())