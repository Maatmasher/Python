import threading
import subprocess
from datetime import datetime
import os

# Конфигурация
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
HOSTS_FILE = os.path.join(CURRENT_DIR, "ip_list.txt")  # Список хостов
LOG_DIR = os.path.join(CURRENT_DIR, "logs")
COMMAND_FILE = os.path.join(CURRENT_DIR, "command.txt")
MAX_THREADS = 7
PLINK_CMD = "plink.exe -ssh {user}@{host} -pw {password} -batch -m {command_txt}"
USER = "tc"
PASSWORD = "JnbcHekbn123"  # Лучше использовать SSH-ключи!


def setup_logging():
    """Создаем папку для логов"""
    os.makedirs(LOG_DIR, exist_ok=True)


def log_message(thread_id, message):
    """Запись сообщения в лог потока"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    print(f"Thread-{thread_id}: {log_entry.strip()}")
    with open(f"{LOG_DIR}/thread_{thread_id}.log", "a", encoding="utf-8") as f:
        f.write(log_entry)


def process_hosts(thread_id, hosts):
    """Обработка списка хостов в одном потоке"""
    for host in hosts:
        try:
            # Проверка ping
            ping_result = subprocess.run(
                ["ping", "-n", "1", "-w", "1000", host],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if "TTL=" in ping_result.stdout:
                log_message(thread_id, f"{host} 🟢 Ping успешен")

                # Выполнение команды через plink
                cmd = PLINK_CMD.format(user=USER, password=PASSWORD, host=host)
                result = subprocess.run(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0:
                    log_message(thread_id, f"{host} ✅ Успешно\n{result.stdout}")
                else:
                    log_message(thread_id, f"{host} ⚠️ Ошибка\n{result.stderr}")
            else:
                log_message(thread_id, f"{host} 🔴 Ping не прошел")

        except subprocess.TimeoutExpired:
            log_message(thread_id, f"{host} ⌛ Таймаут выполнения")
        except Exception as e:
            log_message(thread_id, f"{host} ‼️ Критическая ошибка: {str(e)}")


def main():
    setup_logging()

    # Чтение и разделение хостов
    with open(HOSTS_FILE, "r") as f:
        hosts = [line.strip() for line in f if line.strip()]

    # Разделение на 7 частей
    chunk_size = len(hosts) // MAX_THREADS + 1
    chunks = [hosts[i : i + chunk_size] for i in range(0, len(hosts), chunk_size)]

    # Запуск потоков
    threads = []
    for i, chunk in enumerate(chunks, 1):
        thread = threading.Thread(
            target=process_hosts, args=(i, chunk), name=f"Thread-{i}"
        )
        thread.start()
        threads.append(thread)

    # Ожидание завершения
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()
