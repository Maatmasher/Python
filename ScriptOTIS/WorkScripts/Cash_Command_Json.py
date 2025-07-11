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

# ========= КОНФИГУРАЦИЯ ДЕЙСТВИЙ ===================================
# Настройки для включения/отключения различных действий
ACTIONS_CONFIG = {
    "ENABLE_PING": True,  # Включить проверку ping
    "ENABLE_SSH_TEST": True,  # Включить проверку SSH-логина
    "ENABLE_COMMAND": True,  # Включить выполнение команд через plink
    "ENABLE_CSV_LOGGING": True,  # Включить запись результатов в CSV
}

# Настройки условий выполнения
EXECUTION_CONDITIONS = {
    "REQUIRE_PING_FOR_SSH": True,  # SSH тест только если ping успешен
    "REQUIRE_SSH_FOR_COMMAND": True,  # Команда только если SSH успешен
    "REQUIRE_PING_FOR_COMMAND": True,  # Команда только если ping успешен
}

# Настройки логирования
LOGGING_CONFIG = {
    "LOG_PING_RESULTS": True,  # Логировать результаты ping
    "LOG_SSH_RESULTS": True,  # Логировать результаты SSH тестов
    "LOG_COMMAND_RESULTS": True,  # Логировать результаты выполнения команд
    "LOG_SKIPPED_ACTIONS": True,  # Логировать пропущенные действия
}

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
    if ACTIONS_CONFIG["ENABLE_CSV_LOGGING"]:
        with open(PING_CSV_FILE, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "Timestamp",
                    "Host",
                    "Device Type",
                    "Ping Status",
                    "SSH Login Status",
                    "Command Status",
                ]
            )


async def log_execution(message):
    """Запись сообщения в лог выполнения"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    print(log_entry.strip())
    async with aiofiles.open(LOG_FILE, "a", encoding="utf-8") as f:
        await f.write(log_entry)


async def record_ping_result(
    host, device_type, ping_status, ssh_status, command_status="N/A"
):
    """Запись результата ping, SSH и команды в CSV файл"""
    if not ACTIONS_CONFIG["ENABLE_CSV_LOGGING"]:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(PING_CSV_FILE, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(
            [timestamp, host, device_type, ping_status, ssh_status, command_status]
        )


async def check_ping(host, device_type):
    """Асинхронная проверка ping"""
    if not ACTIONS_CONFIG["ENABLE_PING"]:
        if LOGGING_CONFIG["LOG_SKIPPED_ACTIONS"]:
            await log_execution(f"{host} ({device_type}) Ping проверка отключена")
        return None

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

        result = "TTL=" in stdout.decode()

        if LOGGING_CONFIG["LOG_PING_RESULTS"]:
            status = "Success" if result else "Failed"
            await log_execution(f"{host} ({device_type}) Ping: {status}")

        return result
    except Exception as e:
        if LOGGING_CONFIG["LOG_PING_RESULTS"]:
            await log_execution(f"{host} ({device_type}) Ping error: {str(e)}")
        return False


async def check_ssh_login(host, device_type, ping_success):
    """Асинхронная проверка SSH-логина"""
    if not ACTIONS_CONFIG["ENABLE_SSH_TEST"]:
        if LOGGING_CONFIG["LOG_SKIPPED_ACTIONS"]:
            await log_execution(f"{host} ({device_type}) SSH тест отключен")
        return None

    # Проверяем условие выполнения
    if (
        EXECUTION_CONDITIONS["REQUIRE_PING_FOR_SSH"]
        and ping_success is not None
        and not ping_success
    ):
        if LOGGING_CONFIG["LOG_SKIPPED_ACTIONS"]:
            await log_execution(
                f"{host} ({device_type}) SSH тест пропущен - ping не прошел"
            )
        return False

    try:
        cmd = SSH_TEST_CMD.format(user=USER, password=PASSWORD, host=host)
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        result = proc.returncode == 0 and "OK" in stdout.decode()

        if LOGGING_CONFIG["LOG_SSH_RESULTS"]:
            status = "Success" if result else "Failed"
            await log_execution(f"{host} ({device_type}) SSH: {status}")

        return result
    except Exception as e:
        if LOGGING_CONFIG["LOG_SSH_RESULTS"]:
            await log_execution(f"{host} ({device_type}) SSH error: {str(e)}")
        return False


async def run_plink(host, device_type, ping_success, ssh_success):
    """Асинхронное выполнение команды через plink"""
    if not ACTIONS_CONFIG["ENABLE_COMMAND"]:
        if LOGGING_CONFIG["LOG_SKIPPED_ACTIONS"]:
            await log_execution(f"{host} ({device_type}) Выполнение команды отключено")
        return None

    # Проверяем условия выполнения
    if (
        EXECUTION_CONDITIONS["REQUIRE_PING_FOR_COMMAND"]
        and ping_success is not None
        and not ping_success
    ):
        if LOGGING_CONFIG["LOG_SKIPPED_ACTIONS"]:
            await log_execution(
                f"{host} ({device_type}) Команда пропущена - ping не прошел"
            )
        return False

    if (
        EXECUTION_CONDITIONS["REQUIRE_SSH_FOR_COMMAND"]
        and ssh_success is not None
        and not ssh_success
    ):
        if LOGGING_CONFIG["LOG_SKIPPED_ACTIONS"]:
            await log_execution(
                f"{host} ({device_type}) Команда пропущена - SSH не прошел"
            )
        return False

    command_file = os.path.join(
        CURRENT_DIR, TYPE_COMMANDS.get(device_type, "command_default.txt")
    )

    if not os.path.exists(command_file):
        await log_execution(
            f"{host} ({device_type}) Файл команд {command_file} не найден для типа {device_type}"
        )
        return False

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
                if LOGGING_CONFIG["LOG_COMMAND_RESULTS"]:
                    await log_execution(
                        f"{host} ({device_type}) Команда выполнена успешно\n{stdout}"
                    )
                return True
            else:
                if LOGGING_CONFIG["LOG_COMMAND_RESULTS"]:
                    await log_execution(
                        f"{host} ({device_type}) Ошибка выполнения команды (код {proc.returncode})\n{stderr}"
                    )
                return False
        except asyncio.TimeoutError:
            if LOGGING_CONFIG["LOG_COMMAND_RESULTS"]:
                await log_execution(
                    f"{host} ({device_type}) Таймаут выполнения команды"
                )
            proc.kill()
            await proc.communicate()
            return False
    except Exception as e:
        if LOGGING_CONFIG["LOG_COMMAND_RESULTS"]:
            await log_execution(
                f"{host} ({device_type}) Критическая ошибка выполнения команды: {str(e)}"
            )
        return False


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
    ping_status = (
        "Success"
        if ping_success
        else "Failed" if ping_success is not None else "Disabled"
    )

    # Проверка SSH
    ssh_success = await check_ssh_login(host, device_type, ping_success)
    ssh_status = (
        "Success"
        if ssh_success
        else "Failed" if ssh_success is not None else "Disabled"
    )

    # Выполнение команды
    command_success = await run_plink(host, device_type, ping_success, ssh_success)
    command_status = (
        "Success"
        if command_success
        else "Failed" if command_success is not None else "Disabled"
    )

    # Запись результатов в CSV
    await record_ping_result(host, device_type, ping_status, ssh_status, command_status)

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

    # Вывод конфигурации
    await log_execution("=== КОНФИГУРАЦИЯ ДЕЙСТВИЙ ===")
    for action, enabled in ACTIONS_CONFIG.items():
        await log_execution(f"{action}: {'Включено' if enabled else 'Отключено'}")

    await log_execution("=== УСЛОВИЯ ВЫПОЛНЕНИЯ ===")
    for condition, enabled in EXECUTION_CONDITIONS.items():
        await log_execution(f"{condition}: {'Включено' if enabled else 'Отключено'}")

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
