#!/usr/bin/env python3
import asyncio
import json
import csv
from datetime import datetime
import os
import aiofiles
import paramiko
from concurrent.futures import ThreadPoolExecutor 


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
USER = "tc"
PASSWORD = "JnbcHekbn123"

# ========= КОНФИГУРАЦИЯ ДЕЙСТВИЙ ===================================
# Настройки для включения/отключения различных действий
ACTIONS_CONFIG = {
    "ENABLE_PING": True,  # Включить проверку ping
    "ENABLE_SSH_TEST": True,  # Включить проверку SSH-логина
    "ENABLE_COMMAND": True,  # Включить выполнение команд 
    "ENABLE_CSV_LOGGING": True,  # Включить запись результатов в CSV
}

# Настройки условий выполнения
EXECUTION_CONDITIONS = {
    "REQUIRE_PING_FOR_SSH": True,  # SSH тест только если ping успешен
    "REQUIRE_SSH_FOR_COMMAND": True,  # Команда только если SSH успешен
    "REQUIRE_PING_FOR_COMMAND": True,  # Команда только если ping успешен
    "IGNORE_VERSIONS": ["10.4.17.8"],  # Версии для игнорирования (можно добавить несколько)
}

# Настройки логирования
LOGGING_CONFIG = {
    "LOG_PING_RESULTS": True,  # Логировать результаты ping
    "LOG_SSH_RESULTS": True,  # Логировать результаты SSH тестов
    "LOG_COMMAND_RESULTS": True,  # Логировать результаты выполнения команд
    "LOG_SKIPPED_ACTIONS": True,  # Логировать пропущенные действия
    "LOG_IGNORED_HOSTS": True,  # Логировать игнорируемые хосты
}

""" Команды: банальная копипаста
    И так то сделано только для синхронизации патчей"""
TYPE_COMMANDS = {
    "POS": "command_POS.txt",
    "SCO": "command_SCO.txt",
    "SCO_3": "command_SCO_3.txt",
    "TOUCH_2": "command_TOUCH.txt",
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
                    "Version",
                    "Ping Status",
                    "SSH Login Status",
                    "Command Status",
                    "Notes",
                ]
            )

def execute_ssh_commands_sync(host, username, password, commands, timeout=1800):
    """Синхронное выполнение команд через SSH с использованием Paramiko"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    stdout_data = ""
    stderr_data = ""
    returncode = 0
    
    try:
        client.connect(host, username=username, password=password, timeout=10)
        
        for command in commands:
            if not command.strip() or command.startswith('#'):
                continue
                
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            stdout_data += stdout.read().decode().strip() + "\n"
            stderr_data += stderr.read().decode().strip() + "\n"
            returncode = stdout.channel.recv_exit_status()
            
            if returncode != 0:
                break
                
    except Exception as e:
        stderr_data = str(e)
        returncode = 1
    finally:
        client.close()
        
    return stdout_data, stderr_data, returncode

async def log_execution(message):
    """Запись сообщения в лог выполнения"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    print(log_entry.strip())
    async with aiofiles.open(LOG_FILE, "a", encoding="utf-8") as f:
        await f.write(log_entry)

async def record_ping_result(
    host, device_type, version, ping_status, ssh_status, command_status="N/A", notes=""
):
    """Запись результата ping, SSH и команды в CSV файл"""
    if not ACTIONS_CONFIG["ENABLE_CSV_LOGGING"]:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(PING_CSV_FILE, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(
            [
                timestamp,
                host,
                device_type,
                version,
                ping_status,
                ssh_status,
                command_status,
                notes,
            ]
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
    """Асинхронная проверка SSH-логина с использованием Paramiko"""
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
        def ssh_test_sync():
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(host, username=USER, password=PASSWORD, timeout=15)
                return True
            except Exception:
                return False
            finally:
                client.close()

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, ssh_test_sync)

        if LOGGING_CONFIG["LOG_SSH_RESULTS"]:
            status = "Success" if result else "Failed"
            await log_execution(f"{host} ({device_type}) SSH: {status}")

        return result
    except Exception as e:
        if LOGGING_CONFIG["LOG_SSH_RESULTS"]:
            await log_execution(f"{host} ({device_type}) SSH error: {str(e)}")
        return False

async def run_paramiko(host, device_type, ping_success, ssh_success):
    """Асинхронное выполнение команды через SSH с использованием Paramiko"""
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

    try:
        # Читаем команды из файла
        async with aiofiles.open(command_file, 'r') as f:
            commands = (await f.read()).splitlines()

        # Выполняем команды через SSH в отдельном потоке
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            stdout, stderr, returncode = await loop.run_in_executor(
                pool,
                execute_ssh_commands_sync,
                host, USER, PASSWORD, commands
            )

        if returncode == 0:
            if LOGGING_CONFIG["LOG_COMMAND_RESULTS"]:
                await log_execution(
                    f"{host} ({device_type}) Команда выполнена успешно\n{stdout}"
                )
            return True
        else:
            if LOGGING_CONFIG["LOG_COMMAND_RESULTS"]:
                await log_execution(
                    f"{host} ({device_type}) Ошибка выполнения команды (код {returncode})\n{stderr}"
                )
            return False
    except asyncio.TimeoutError:
        if LOGGING_CONFIG["LOG_COMMAND_RESULTS"]:
            await log_execution(
                f"{host} ({device_type}) Таймаут выполнения команды"
            )
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
    version = host_info.get("version", "N/A")

    # Проверяем, нужно ли игнорировать этот хост
    if version in EXECUTION_CONDITIONS.get("IGNORE_VERSIONS", []):
        if LOGGING_CONFIG["LOG_IGNORED_HOSTS"]:
            await log_execution(
                f"{host} ({device_type}) Пропущен - версия {version} в списке игнорируемых"
            )
        await record_ping_result(
            host,
            device_type,
            version,
            "N/A",
            "N/A",
            "N/A",
            f"Ignored due to version {version}",
        )
        remaining_counter["processed"] += 1
        return

    remaining = remaining_counter["total"] - remaining_counter["processed"]
    await log_execution(
        f"Обработка {host} ({device_type}) версия {version} | Осталось хостов: {remaining}"
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
    command_success = await run_paramiko(host, device_type, ping_success, ssh_success)
    command_status = (
        "Success"
        if command_success
        else "Failed" if command_success is not None else "Disabled"
    )

    # Запись результатов в CSV
    await record_ping_result(
        host, device_type, version, ping_status, ssh_status, command_status
    )

    remaining_counter["processed"] += 1

async def load_hosts():
    """Загрузка хостов из JSON файла"""
    try:
        async with aiofiles.open(CASH_IP_FILE, "r") as f:
            content = await f.read()
            cash_data = json.loads(content)
        return [
            {"ip": ip, "type": info["type"], "version": info.get("version", "N/A")}
            for ip, info in cash_data.items()
        ]
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
        if condition != "IGNORE_VERSIONS":  # Для списка версий специальный вывод
            await log_execution(f"{condition}: {'Включено' if enabled else 'Отключено'}")
    
    # Вывод игнорируемых версий
    ignore_versions = EXECUTION_CONDITIONS.get("IGNORE_VERSIONS", [])
    if ignore_versions:
        await log_execution(f"IGNORE_VERSIONS: {', '.join(ignore_versions)}")
    else:
        await log_execution("IGNORE_VERSIONS: Нет")

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
