#! /usr/bin/env python
import psycopg2, time, os
from datetime import datetime

# Список касс
# hosts_cash = ['10.14.35.51']
hosts_cash = ["10.16.35.52", "10.131.0.51"]
log_file = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "documents_check.log",  # Вычисляем директорию откуда запускаем скрипт
)  # Лог файл делает там же откуда запускается скрипт


def check_documents():
    """Проверяет наличие документов без привязки к смене и записывает результат в лог-файл"""
    try:
        # Параметры подключения, замутить бы без хардкода паролей
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
                f"[{timestamp}] Найден документ без смены: "
                f"ID={last_doc[0] if last_doc[0] is not None else 'N/A'}, "  # собственно проверка полей
                f"Дата={last_doc[1] if last_doc[1] is not None else 'N/A'}, "  # если возвращается ничего или NULL
                f"Номер={last_doc[2] if last_doc[2] is not None else 'N/A'}, "  # то присваиваем N/A
                f"КПК={last_doc[3] if last_doc[3] is not None else 'N/A'}\n"
            )
        elif exists:
            message = f"[{timestamp}] Найден документ без смены (нет данных)\n"
        else:
            message = f"[{timestamp}] Документов без смены не найдено\n"

        # Записываем в лог файл
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(message)

        return exists

    except psycopg2.Error as e:
        error_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Ошибка подключения к БД: {e}\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(error_msg)
        return False
    except Exception as e:
        error_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Неожиданная ошибка: {e}\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(error_msg)
        return False


if __name__ == "__main__":
    for host_cash in hosts_cash:
        result = check_documents()
        print(
            f"Результат проверки {host_cash} : {'Документы найдены' if result else 'Документы не найдены'}"
        )
    print(f"Смотри результат в лог файле: {log_file}")
    time.sleep(5)
