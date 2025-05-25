#!/usr/bin/env python3
import sys
import psycopg2
import json
import os
from psycopg2 import OperationalError

# Общая конфигурация
DB_CONFIG = {
    'dbname': 'set',
    'user': 'postgres',
    'password': 'postgres',
    'connect_timeout': 5
}

# Конфигурация для сбора IP серверов
SHOP_QUERY = "SELECT shop_ip FROM topology_shop WHERE shop_ip > '' ORDER BY number"
SERVER_LIST_FILE = 'server_ips.tmp'

# Конфигурация для сбора cash_ip
CASH_TYPES = {
    'POS': "t2.cash_type = 'POS'",
    'SCO': "t2.cash_type = 'SCO'",
    'TOUCH': "t2.cash_type = 'TOUCH_2'"
}
OUTPUT_FILE = 'cash_ip_dict.json'

def get_server_ips(main_server_ip):
    """Получаем список всех серверов из главного сервера"""
    try:
        conn = psycopg2.connect(host=main_server_ip, **DB_CONFIG)
        conn.autocommit = True
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(SHOP_QUERY)
                return [row[0] for row in cursor.fetchall()]
    except OperationalError as e:
        print(f"Ошибка подключения к главному серверу {main_server_ip}: {str(e)}", file=sys.stderr)
        return None

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

def create_connection(host):
    """Создаем соединение с базой данных"""
    try:
        conn = psycopg2.connect(host=host, **DB_CONFIG)
        conn.autocommit = True
        return conn
    except OperationalError as e:
        print(f"Ошибка подключения к {host}: {str(e)}", file=sys.stderr)
        return None

def collect_cash_data(server_ips):
    """Собираем данные по кассовым терминалам со всех серверов"""
    cash_dict = {}
    
    for server_ip in server_ips:
        try:
            conn = create_connection(server_ip)
            if conn is None:
                continue
                
            with conn:
                with conn.cursor() as cursor:
                    for cash_type in CASH_TYPES:
                        ips = get_cash_ips(cursor, cash_type)
                        for ip in ips:
                            cash_dict[ip] = {
                                'server_ip': server_ip,
                                'type': cash_type,
                                'status': 'ACTIVE'
                            }
            
            print(f"Данные с сервера {server_ip} успешно собраны")
            
        except Exception as e:
            print(f"Ошибка при работе с сервером {server_ip}: {str(e)}", file=sys.stderr)
    
    return cash_dict

def save_to_json(data, filename):
    """Сохраняем данные в JSON-файл"""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"\nДанные успешно сохранены в {filename}")
    except IOError as e:
        print(f"Ошибка записи в файл: {str(e)}", file=sys.stderr)
        sys.exit(1)

def main():
    if len(sys.argv) != 2:
        print("Использование: python combined_script.py <главный_сервер_ip>")
        sys.exit(1)
    
    main_server_ip = sys.argv[1]
    
    # Этап 1: Получаем список всех серверов
    print("Получаем список серверов...")
    server_ips = get_server_ips(main_server_ip)
    if not server_ips:
        print("Не удалось получить список серверов", file=sys.stderr)
        sys.exit(1)
    
    # Этап 2: Собираем данные по кассам со всех серверов
    print(f"\nСобираем данные с {len(server_ips)} серверов...")
    cash_data = collect_cash_data(server_ips)
    
    # Этап 3: Сохраняем результат
    save_to_json(cash_data, OUTPUT_FILE)
    print(f"Всего собрано записей: {len(cash_data)}")

if __name__ == "__main__":
    main()