#!/usr/bin/env python3
import sys
import psycopg2
import json
import os
from psycopg2 import OperationalError

# Конфигурация
INPUT_FILE = 'shop_ips.txt'      # Файл со списком IP-адресов серверов
OUTPUT_FILE = 'cash_ip_dict.json' # Файл для сохранения словаря
DB_CONFIG = {
    'dbname': 'set',
    'user': 'postgres',
    'password': 'postgres',
    'connect_timeout': 5
}

# Типы кассовых терминалов
CASH_TYPES = {
    'POS': "t2.cash_type = 'POS'",
    'SCO': "t2.cash_type = 'SCO'",
    'TOUCH': "t2.cash_type = 'TOUCH_2'"
}

def read_server_ips(filename):
    """Читаем список IP-адресов серверов из файла"""
    if not os.path.exists(filename):
        print(f"Файл {filename} не найден в директории {os.getcwd()}", file=sys.stderr)
        sys.exit(1)
    
    with open(filename) as f:
        return [line.strip() for line in f if line.strip()]

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

def main():
    # Получаем список серверов из файла
    try:
        server_ips = read_server_ips(INPUT_FILE)
        if not server_ips:
            print(f"Файл {INPUT_FILE} пуст или не содержит валидных IP-адресов", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Ошибка чтения файла {INPUT_FILE}: {str(e)}", file=sys.stderr)
        sys.exit(1)

    cash_dict = {}  # Словарь для хранения результатов

    for server_ip in server_ips:
        try:
            conn = create_connection(server_ip)
            if conn is None:
                continue
                
            with conn:
                with conn.cursor() as cursor:
                    # Собираем данные по всем типам терминалов
                    for cash_type in CASH_TYPES:
                        ips = get_cash_ips(cursor, cash_type)
                        for ip in ips:
                            # Используем cash_ip как ключ, значение - информация о терминале
                            cash_dict[ip] = {
                                'server_ip': server_ip,
                                'type': cash_type,
                                'status': 'ACTIVE'
                            }
            
            print(f"Данные с сервера {server_ip} успешно собраны")
            
        except Exception as e:
            print(f"Ошибка при работе с сервером {server_ip}: {str(e)}", file=sys.stderr)

    # Записываем словарь в JSON-файл
    try:
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(cash_dict, f, indent=4, ensure_ascii=False)
        print(f"\nСловарь успешно сохранен в {OUTPUT_FILE}")
        print(f"Всего записей: {len(cash_dict)}")
    except IOError as e:
        print(f"Ошибка записи в файл: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()