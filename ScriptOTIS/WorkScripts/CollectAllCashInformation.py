import psycopg2
import json
import sys
from psycopg2 import OperationalError

# ========= КОНФИГУРАЦИЯ =========
MAIN_SERVERS = [  # Список Centrum для получения shop_ip
    "10.21.11.45",
    "10.100.105.9",
]

DB_CONFIG = {  # Параметры подключения к БД
    "dbname": "set",
    "user": "postgres",
    "password": "postgres",
    "connect_timeout": 10,
}

CASH_TYPES = {  # Типы кассовых терминалов
    "POS": "t2.cash_type = 'POS'",
    "SCO": "t2.cash_type = 'SCO'",
    "SCO_3": "t2.cash_type = 'SCO_3'",
    "TOUCH": "t2.cash_type = 'TOUCH'" "",
}

OUTPUT_FILE = "cash_ip_all.json"  # Файл для сохранения результатов
# ================================


def get_server_ips(main_servers):
    """Получаем список всех серверов из главных серверов"""
    all_servers = set()

    for server_ip in main_servers:
        try:
            conn = psycopg2.connect(host=server_ip, **DB_CONFIG)
            conn.autocommit = True
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT shop_ip FROM topology_shop WHERE shop_ip > '' ORDER BY number"
                    )
                    servers = {row[0] for row in cursor.fetchall()}
                    all_servers.update(servers)
                    print(f"Получено {len(servers)} серверов с {server_ip}")

        except OperationalError as e:
            print(
                f"Ошибка подключения к главному серверу {server_ip}: {str(e)}",
                file=sys.stderr,
            )
            continue

    return sorted(all_servers)


def get_cash_ips(cursor, cash_type):
    """Получаем IP-адреса кассовых терминалов указанного типа"""
    query = f"""
        SELECT t1.cash_ip 
        FROM cash_cash as t1  
        JOIN cash_template as t2 ON t1.template_id=t2.id 
        WHERE t1.status = 'ACTIVE' 
          AND t1.cash_ip IS NOT NULL 
          AND {CASH_TYPES[cash_type]}
        ORDER BY t1.number
    """
    cursor.execute(query)
    return [row[0] for row in cursor.fetchall()]


def collect_cash_data(server_ips):
    """Собираем данные по кассам со всех серверов"""
    cash_dict = {}

    for server_ip in server_ips:
        try:
            conn = psycopg2.connect(host=server_ip, **DB_CONFIG)
            conn.autocommit = True
            with conn:
                with conn.cursor() as cursor:
                    for cash_type in CASH_TYPES:
                        ips = get_cash_ips(cursor, cash_type)
                        for ip in ips:
                            cash_dict[ip] = {
                                "server_ip": server_ip,
                                "type": cash_type,
                                "status": "ACTIVE",
                            }
            print(f" Данные с {server_ip} успешно собраны")

        except OperationalError as e:
            print(f"Ошибка подключения к {server_ip}: {str(e)}", file=sys.stderr)
        except Exception as e:
            print(f"Ошибка при работе с {server_ip}: {str(e)}", file=sys.stderr)

    return cash_dict


def save_results(data, filename):
    """Сохраняем результаты в JSON-файл"""
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except IOError as e:
        print(f"Ошибка записи в файл: {str(e)}", file=sys.stderr)
        return False


def main():
    print("=== Начало работы скрипта ===")
    print(f"Главные серверы: {', '.join(MAIN_SERVERS)}")

    # Этап 1: Получаем список всех серверов
    print("\n[1/3] Получение списка серверов...")
    server_ips = get_server_ips(MAIN_SERVERS)

    if not server_ips:
        print("Не удалось получить список серверов", file=sys.stderr)
        return

    print(f"Всего найдено серверов: {len(server_ips)}")

    # Этап 2: Сбор данных по кассам
    print("\n[2/3] Сбор данных по кассам...")
    cash_data = collect_cash_data(server_ips)

    if not cash_data:
        print("Не удалось собрать данные по кассам", file=sys.stderr)
        return

    # Этап 3: Сохранение результатов
    print("\n[3/3] Сохранение результатов...")
    if save_results(cash_data, OUTPUT_FILE):
        print(f"Данные успешно сохранены в {OUTPUT_FILE}")
        print(f"Всего собрано касс: {len(cash_data)}")
    else:
        print("Не удалось сохранить результаты", file=sys.stderr)


if __name__ == "__main__":
    main()
    print("\n=== Работа скрипта завершена ===")
