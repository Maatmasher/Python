#!/usr/bin/env python
import psycopg2, time, os, paramiko, socket
from datetime import datetime

# Получаем путь к файлу cash_ip.txt в той же директории, что и скрипт
ip_file = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "cash_ip.txt"
)

# Читаем список хостов из файла
try:
    with open(ip_file, 'r') as f:
        hosts_cash = [line.strip() for line in f if line.strip()]
except FileNotFoundError:
    print(f"Файл {ip_file} не найден. Используем пустой список хостов.")
    hosts_cash = []

log_file = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "documents_check.csv", 
)  # Лог файл делает там же откуда запускается скрипт

def execute_ssh_command(host, command="echo 'Hello World'", username="tc", password="JnbcHekbn123"):
    """Выполняет SSH команду на удаленном хосте, хардкод паролей это ужасно"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=username, password=password, timeout=10)
        
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        
        ssh.close()
        
        if error:
            return False, error
        return True, output
        
    except (paramiko.AuthenticationException, paramiko.SSHException, socket.error) as e:
        return False, str(e)


def check_documents():
    """Проверяет наличие документов без привязки к смене и записывает результат в лог-файл"""
    try:
        # Параметры подключения, опять оно.... пароли в открытом виде
        conn = psycopg2.connect(
            host=host_cash,
            connect_timeout=3,
            database="cash",
            user="postgres",
            password="postgres",
            client_encoding="UTF-8",
        )

        with conn:
            with conn.cursor() as cursor:
                # Проверяем есть ли вообще чек
                cursor.execute(
                    """
                    SELECT EXISTS(
                        SELECT 1 
                        FROM ch_purchase 
                        WHERE id_shift IS NULL
                        LIMIT 1
                    )
                """
                )
                exists_result = cursor.fetchone()
                exists = exists_result[0] if exists_result else False

                # Если чек есть, получаем последний
                last_doc = None
                if exists:
                    cursor.execute(
                        """
                        SELECT id, datecreate, numberfield, kpk
                        FROM ch_purchase
                        WHERE id_shift IS NULL
                        ORDER BY datecreate DESC
                        LIMIT 1
                    """
                    )
                    last_doc = cursor.fetchone()

        # Сотворяем сообщение для записи в лог файл
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if exists and last_doc:
            message = (
                f"[{timestamp}] Найден документ без смены:  ,"
                f"{host_cash} ;"
                f"ID={last_doc[0] if last_doc[0] is not None else 'N/A'}, "  # собственно проверка полей
                f"Дата={last_doc[1] if last_doc[1] is not None else 'N/A'}, "  # если возвращается ничего или NULL
                f"Номер={last_doc[2] if last_doc[2] is not None else 'N/A'}, "  # то присваиваем N/A
                f"КПК={last_doc[3] if last_doc[3] is not None else 'N/A'} ,\n"
            )
        elif exists:
            message = f"[{timestamp}] Найден документ без смены (нет данных) ,,,,,,\n"
        else:
            message = f"[{timestamp}] Документов без смены не найдено ,,,,,,\n"

        # Записываем в лог файл
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(message)

        if exists and last_doc:
            print(f"Обнаружен документ без смены на {host_cash}. Выполняю дополнительные действия...")
            
            # Выполняем SSH команду
            ssh_success, ssh_result = execute_ssh_command(
                host_cash, 
                command="cash stop", # Можно слать только команду, логин и пароль есть в функции
                username="tc",  
                password="JnbcHekbn123"  
            )
            
            # Логируем результат SSH
            ssh_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if ssh_success:
                ssh_message = f"[{ssh_timestamp}] SSH команда выполнена успешно на {host_cash}: {ssh_result}\n"
            else:
                ssh_message = f"[{ssh_timestamp}] Ошибка SSH на {host_cash}: {ssh_result}\n"
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(ssh_message)

            with conn:
                with conn.cursor() as cursor:
                    # Вычисляем и записываем аннулированный чек
                    cursor.execute(
                    """
                    WITH active_shift AS (
                    SELECT id, cashnum, numshift
                    FROM ch_shift
                    WHERE shiftclose IS NULL
                    AND shiftopen IS NOT NULL
                    ORDER BY shiftcreate DESC
                    LIMIT 1
                ),
                max_document_numbers AS (
                    SELECT 
                        COALESCE(MAX(numberfield), 0) + 1 AS next_number
                    FROM (
                        SELECT MAX(numberfield) AS numberfield FROM ch_purchase WHERE id_shift = (SELECT id FROM active_shift)
                        UNION ALL
                        SELECT MAX(numberfield) AS numberfield FROM ch_withdrawal WHERE id_shift = (SELECT id FROM active_shift)
                        UNION ALL
                        SELECT MAX(numberfield) AS numberfield FROM ch_introduction WHERE id_shift = (SELECT id FROM active_shift)
                        UNION ALL
                        SELECT MAX(numberfield) AS numberfield FROM ch_reportshift WHERE id_shift = (SELECT id FROM active_shift)
                    ) AS all_documents
                ),
                kpk_calculation AS (
                    SELECT 
                        CASE 
                            WHEN EXISTS (
                                SELECT 1 FROM ch_purchase WHERE checkstatus = '1' AND id_shift = (SELECT id FROM active_shift)
                            ) THEN COALESCE(MAX(kpk), 0) + 1
                            ELSE  1
                        END AS next_kpk
                    FROM (
                        SELECT MAX(kpk) AS kpk FROM ch_purchase WHERE checkstatus = '1'  AND id_shift = (SELECT id FROM active_shift)
                    ) AS all_kpk
                ),
                last_unassigned_purchase AS (
                    SELECT id
                    FROM ch_purchase
                    WHERE id_shift IS NULL
                    ORDER BY datecreate DESC
                    LIMIT 1
                )
                UPDATE ch_purchase
                SET datecommit = datecreate + INTERVAL '1 minute',
                    fiscaldocnum = (SELECT next_kpk FROM kpk_calculation)::text || ';' || 
                                (SELECT next_number FROM max_document_numbers)::text,
                    numberfield = (SELECT next_number FROM max_document_numbers),
                    senttoserverstatus = '0',
                    checkstatus = '1',
                    id_shift = (SELECT id FROM active_shift),
                    kpk = (SELECT next_kpk FROM kpk_calculation)
                WHERE id = (SELECT id FROM last_unassigned_purchase)
                RETURNING id,datecommit, fiscaldocnum, numberfield;
                """
                )
                    anul_doc = cursor.fetchone()
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    message_anull = (
                f"[{timestamp}] Удалён документ без смены:  "
                f"{host_cash} ;"
                f"ID={anul_doc[0] if anul_doc[0] is not None else 'N/A'}; "  # собственно проверка полей
                f"Дата={anul_doc[1] if anul_doc[1] is not None else 'N/A'}; "  # если возвращается ничего или NULL
                f"Номер документа={anul_doc[2] if anul_doc[2] is not None else 'N/A'}; "  # то присваиваем N/A
                f"Номер чека ={anul_doc[3] if anul_doc[3] is not None else 'N/A'} ;\n"
            )
                    print(anul_doc)
                # Записываем в лог файл
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(message_anull)

            # Выполняем SSH команду
            ssh_success, ssh_result = execute_ssh_command(
                host_cash, 
                command="cash start",
                username="tc",  
                password="JnbcHekbn123"  
            )
            
            # Логируем результат SSH
            ssh_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if ssh_success:
                ssh_message = f"[{ssh_timestamp}] SSH команда выполнена успешно на {host_cash}: {ssh_result}\n"
            else:
                ssh_message = f"[{ssh_timestamp}] Ошибка SSH на {host_cash}: {ssh_result}\n"
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(ssh_message)

        return exists

    except psycopg2.Error as e:
        error_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Ошибка подключения к БД: ;;;;; {e}\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(error_msg)
        return False
    except Exception as e:
        error_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Неожиданная ошибка: ;;;;; {e}\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(error_msg)
        return False


if __name__ == "__main__":
    if not hosts_cash:
        print(f"Не найдены IP-адреса в файле {ip_file}. Проверка не будет выполнена.")
    else:
        for host_cash in hosts_cash:
            result = check_documents()
            print(
                f"Результат проверки {host_cash} : {'Документы найдены' if result else 'Документы не найдены'}"
            )
    print(f"Смотри результат в лог файле: {log_file}")
    time.sleep(5)