#!/usr/bin/env python3
import asyncio
import json
import csv
from datetime import datetime
import os
import aiofiles

# ========= КОНФИГУРАЦИЯ =============================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CASH_IP_FILE = os.path.join(
    CURRENT_DIR, "cash_ip_all.json"
)  # Файл с IP касс, ключ это IP. Так как словарь, можно навернуть параметров.
LOG_FILE = os.path.join(
    CURRENT_DIR, "execution.log"
)  # Лог с результатами выполнения команд
PING_CSV_FILE = os.path.join(CURRENT_DIR, "ping_results.csv")  # CSV с результатами ping
COMMAND_TEMPLATE = "command_{type}.txt"  # Шаблон файла команд
MAX_CONCURRENT_TASKS = (
    5  # Максимальное количество одновременных задач, меняем насколько не боимся)
)
PLINK_CMD = "plink.exe -ssh {user}@{host} -pw {password} -batch -m {command_file}"
SSH_TEST_CMD = "plink.exe -ssh {user}@{host} -pw {password} -batch echo OK"
USER = "tc"
PASSWORD = "JnbcHekbn123"
""" Команды: банальная копипаста
    И так то сделано только для синхронизации патчей"""
TYPE_COMMANDS = {
    "POS": "command_POS.txt",
    "SCO": "command_SCO.txt",
    "SCO_3": "command_SCO_3.txt",
    "TOUCH": "command_TOUCH.txt",
}
# ====================================================================


def setup_files():
    """Инициализация файлов логов"""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("")  # Очищаем лог выполнения

    """Инициализация CSV файла с заголовками"""
    with open(PING_CSV_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Timestamp", "Host", "Device Type", "Ping Status", "SSH Login Status"])


async def log_execution(message):
    """Запись сообщения в лог выполнения"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    print(log_entry.strip())
    async with aiofiles.open(LOG_FILE, "a", encoding="utf-8") as f:
        await f.write(log_entry)


async def record_ping_result(host, device_type, ping_status, ssh_status):
    """Запись результата ping и SSH в CSV файл"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(PING_CSV_FILE, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([timestamp, host, device_type, ping_status, ssh_status])


async def check_ping(host, device_type):
    """Асинхронная проверка ping"""
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
            return True
        return False
    except Exception:
        return False


async def check_ssh_login(host):
    """Асинхронная проверка SSH-логина"""
    try:
        cmd = SSH_TEST_CMD.format(user=USER, password=PASSWORD, host=host)
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode == 0 and "OK" in stdout.decode():
            return True
        return False
    except Exception:
        return False


async def run_plink(host, device_type):
    """Асинхронное выполнение команды через plink"""
    command_file = os.path.join(
        CURRENT_DIR, TYPE_COMMANDS.get(device_type, "command_default.txt")
    )

    if not os.path.exists(command_file):
        await log_execution(
            f"{host}  Файл команд {command_file} не найден для типа {device_type}"
        )
        return

    cmd = PLINK_CMD.format(
        user=USER, password=PASSWORD, command_file=command_file, host=host
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
                await log_execution(f"{host} ({device_type}) Успешно\n{stdout}")
            else:
                await log_execution(
                    f"{host} ({device_type}) Ошибка (код {proc.returncode})\n{stderr}"
                )
        except asyncio.TimeoutError:
            await log_execution(f"{host} ({device_type}) Таймаут выполнения")
            proc.kill()
            await proc.communicate()
    except Exception as e:
        await log_execution(f"{host} ({device_type}) Критическая ошибка: {str(e)}")


async def process_host(host_info, remaining_counter):
    """Обработка одного хоста"""
    host = host_info["ip"]
    device_type = host_info["type"]

    remaining = remaining_counter["total"] - remaining_counter["processed"]
    await log_execution(
        f"Обработка {host} ({device_type}) | Осталось хостов: {remaining}"
    )

    # Проверка ping
    ping_success = await check_ping(host, device_type)
    ping_status = "Success" if ping_success else "Failed"
    
    # Проверка SSH
    ssh_success = False
    if ping_success:  # Проверяем SSH только если ping успешен
        ssh_success = await check_ssh_login(host)
    
    ssh_status = "Success" if ssh_success else "Failed"
    
    # Запись результатов в CSV
    await record_ping_result(host, device_type, ping_status, ssh_status)

    # Выполнение основной команды если оба теста успешны
    if ping_success and ssh_success:
        await run_plink(host, device_type)
    else:
        await log_execution(
            f"{host} ({device_type}) Пропуск выполнения команды. "
            f"Ping: {ping_status}, SSH: {ssh_status}"
        )

    remaining_counter["processed"] += 1


async def load_hosts():
    """Загрузка хостов из JSON файла"""
    try:
        async with aiofiles.open(CASH_IP_FILE, "r") as f:
            content = await f.read()
            cash_data = json.loads(content)
        return [{"ip": ip, "type": info["type"]} for ip, info in cash_data.items()]
    except Exception as e:
        await log_execution(f"Ошибка загрузки файла {CASH_IP_FILE}: {str(e)}")
        return []


async def main():
    setup_files()

    # Загрузка списка касс из JSON
    hosts = await load_hosts()
    if not hosts:
        await log_execution("Нет хостов для обработки")
        return

    total_hosts = len(hosts)
    await log_execution(f"Начало обработки {total_hosts} хостов")

    # Счетчик обработанных касс
    counter = {"total": total_hosts, "processed": 0}

    # Создаем семафор для ограничения количества одновременных действий
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

    async def limited_task(host_info):
        async with semaphore:
            await process_host(host_info, counter)

    # Запускаем задачи
    tasks = [limited_task(host) for host in hosts]
    await asyncio.gather(*tasks)

    await log_execution(
        f"Обработка завершена. Всего обработано: {counter['processed']}/{counter['total']}"
    )


if __name__ == "__main__":
    asyncio.run(main())