#!/usr/bin/env python3
import sys
import psycopg2
from psycopg2 import OperationalError, Error

# Параметры скрипта (изменяйте эти значения)
SERVER_IPS = ["10.21.11.45", "10.100.105.9"]  # Список IP-адресов серверов
OUTPUT_FILE = "shop_ip.txt"  # Имя выходного файла


def write_ips_to_file(cursor, filename):
    """Write shop IPs to the specified file."""
    try:
        with open(filename, "w") as out_file:
            query = """
                SELECT shop_ip 
                FROM topology_shop 
                WHERE shop_ip > '' 
                ORDER BY number
            """
            cursor.execute(query)

            for record in cursor:
                out_file.write(f"{record[0]}\n")

    except IOError as e:
        raise IOError(f"Failed to write to file {filename}: {str(e)}")


def create_connection(host, dbname, user, password):
    """Create and return a database connection."""
    try:
        conn = psycopg2.connect(
            host=host, dbname=dbname, user=user, password=password, connect_timeout=5
        )
        conn.autocommit = True
        return conn
    except OperationalError as e:
        raise OperationalError(f"Connection to database {host} failed: {str(e)}")


def main():
    # Connection parameters
    dbname = "set"
    user = "postgres"
    password = "postgres"

    success = False
    last_error = None

    for server_ip in SERVER_IPS:
        server_ip = server_ip.strip()
        try:
            conn = create_connection(server_ip, dbname, user, password)
            with conn:
                with conn.cursor() as cursor:
                    write_ips_to_file(cursor, OUTPUT_FILE)
            print(f"Successfully wrote IPs using server {server_ip} to {OUTPUT_FILE}")
            success = True
            break  # Успешно подключились к одному из серверов

        except (Error, IOError) as e:
            last_error = str(e)
            print(f"Failed with server {server_ip}: {str(e)}", file=sys.stderr)
            continue

    if not success:
        print(
            f"Error: All connection attempts failed. Last error: {last_error}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
