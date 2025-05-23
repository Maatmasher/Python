#!/usr/bin/env python3
import sys
import psycopg2
from psycopg2 import OperationalError, Error

# Параметры скрипта (изменяйте эти значения)
SERVER_IPS = ["10.21.11.45", "10.100.105.9"]  # Список IP-адресов серверов
OUTPUT_FILE = "shop_ip.txt"  # Имя выходного файла


def write_ips_to_file(cursor, out_file):
    """Write shop IPs to the specified file."""
    query = """
        SELECT shop_ip 
        FROM topology_shop 
        WHERE shop_ip > '' 
        ORDER BY number
    """
    cursor.execute(query)

    for record in cursor:
        out_file.write(f"{record[0]}\n")


def create_connection(host, dbname, user, password):
    """Create and return a database connection."""
    conn = psycopg2.connect(
        host=host, dbname=dbname, user=user, password=password, connect_timeout=10
    )
    conn.autocommit = True
    return conn


def main():
    # Connection parameters
    dbname = "set"
    user = "postgres"
    password = "postgres"

    successful_connections = 0

    try:
        with open(OUTPUT_FILE, "w") as out_file:
            for server_ip in SERVER_IPS:
                server_ip = server_ip.strip()
                try:
                    conn = create_connection(server_ip, dbname, user, password)
                    with conn:
                        with conn.cursor() as cursor:
                            write_ips_to_file(cursor, out_file)
                    print(f"Successfully collected IPs from server {server_ip}")
                    successful_connections += 1

                except OperationalError as e:
                    print(
                        f"Failed to connect to server {server_ip}: {str(e)}",
                        file=sys.stderr,
                    )
                    continue
                except Error as e:
                    print(
                        f"Database error on server {server_ip}: {str(e)}",
                        file=sys.stderr,
                    )
                    continue

    except IOError as e:
        print(f"Failed to write to file {OUTPUT_FILE}: {str(e)}", file=sys.stderr)
        sys.exit(1)

    if successful_connections == 0:
        print("Error: Failed to connect to all servers", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"Successfully collected data from {successful_connections} server(s)")
        print(f"Results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
