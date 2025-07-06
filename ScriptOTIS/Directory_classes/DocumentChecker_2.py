#!/usr/bin/env python
import psycopg2
import time
import os
import paramiko
import socket
from datetime import datetime
from typing import List, Tuple, Optional, Dict
import logging

class DocumentChecker:
    """Класс для проверки и обработки документов без привязки к смене"""
    
    def __init__(self, config_dir: str = None):
        """
        Инициализация класса
        Args:
            config_dir: Директория с конфигурационными файлами
        """
        # Инициализируем logger в самом начале
        self.logger = None
        self._setup_logging()
        
        self.config_dir = config_dir or os.path.dirname(os.path.abspath(__file__))
        self.ip_file = os.path.join(self.config_dir, "cash_ip.txt")
        self.log_file = os.path.join(self.config_dir, "documents_check.csv")
        
        # Конфигурация подключений (лучше вынести в отдельный файл)
        self.db_config = {
            "database": "cash",
            "user": "postgres",
            "password": "postgres",
            "connect_timeout": 5,
            "client_encoding": "UTF-8"
        }
        
        self.ssh_config = {
            "username": "tc",
            "password": "JnbcHekbn123",
            "timeout": 10
        }
        
        # Загружаем хосты после инициализации logger
        self.hosts = self._load_hosts()
        
        # Логируем успешную инициализацию
        self.logger.info("DocumentChecker успешно инициализирован")
    
    def _setup_logging(self):
        """Настройка логирования"""
        try:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.StreamHandler(),  # Вывод в консоль
                    logging.FileHandler(
                        os.path.join(
                            self.config_dir if hasattr(self, 'config_dir') else os.path.dirname(os.path.abspath(__file__)),
                            'debug.log'
                        )
                    )
                ]
            )
            self.logger = logging.getLogger(self.__class__.__name__)
            self.logger.setLevel(logging.INFO)
        except Exception as e:
            # Если не удается настроить логирование, создаем простой logger
            self.logger = logging.getLogger(self.__class__.__name__)
            self.logger.addHandler(logging.StreamHandler())
            self.logger.setLevel(logging.INFO)
            self.logger.error(f"Ошибка настройки логирования: {e}")
    
    def _load_hosts(self) -> List[str]:
        """
        Загружает список хостов из файла
        
        Returns:
            Список IP-адресов хостов
        """
        try:
            with open(self.ip_file, 'r') as f:
                hosts = [line.strip() for line in f if line.strip()]
            if self.logger:
                self.logger.info(f"Загружено {len(hosts)} хостов из {self.ip_file}")
            return hosts
        except FileNotFoundError:
            if self.logger:
                self.logger.warning(f"Файл {self.ip_file} не найден. Используем пустой список хостов.")
            else:
                print(f"Файл {self.ip_file} не найден. Используем пустой список хостов.")
            return []
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка загрузки хостов: {e}")
            else:
                print(f"Ошибка загрузки хостов: {e}")
            return []
    
    def _write_log(self, message: str):
        """
        Записывает сообщение в лог-файл
        
        Args:
            message: Сообщение для записи
        """
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(message)
        except Exception as e:
            error_msg = f"Ошибка записи в лог-файл: {e}"
            if self.logger:
                self.logger.error(error_msg)
            else:
                print(error_msg)
    
    def _execute_ssh_command(self, host: str, command: str) -> Tuple[bool, str]:
        """
        Выполняет SSH команду на удаленном хосте
        Args:
            host: IP-адрес хоста
            command: Команда для выполнения
        Returns:
            Кортеж (успех, результат/ошибка)
        """
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                host,
                username=self.ssh_config["username"],
                password=self.ssh_config["password"],
                timeout=self.ssh_config["timeout"]
            )
            
            stdin, stdout, stderr = ssh.exec_command(command)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            ssh.close()
            
            if error:
                if self.logger:
                    self.logger.warning(f"SSH команда '{command}' на {host} вернула ошибку: {error}")
                return False, error
            
            if self.logger:
                self.logger.info(f"SSH команда '{command}' на {host} выполнена успешно")
            return True, output
            
        except (paramiko.AuthenticationException, paramiko.SSHException, socket.error) as e:
            error_msg = f"Ошибка SSH подключения к {host}: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            return False, str(e)
    
    def _get_database_connection(self, host: str) -> psycopg2.extensions.connection:
        """
        Создает подключение к базе данных
        
        Args:
            host: IP-адрес хоста с БД
            
        Returns:
            Объект подключения к БД
        """
        try:
            conn = psycopg2.connect(
                host=host,
                **self.db_config
            )
            if self.logger:
                self.logger.info(f"Успешное подключение к БД на {host}")
            return conn
        except psycopg2.Error as e:
            if self.logger:
                self.logger.error(f"Ошибка подключения к БД на {host}: {e}")
            raise
    
    def _check_documents_in_db(self, conn: psycopg2.extensions.connection) -> Tuple[bool, Optional[Tuple]]:
        """
        Проверяет наличие документов без смены в БД
        
        Args:
            conn: Подключение к БД
            
        Returns:
            Кортеж (найдены_документы, данные_последнего_документа)
        """
        try:
            with conn.cursor() as cursor:
                # Проверяем есть ли документы без смены
                cursor.execute("""
                    SELECT EXISTS(
                        SELECT 1 
                        FROM ch_purchase 
                        WHERE id_shift IS NULL
                        LIMIT 1
                    )
                """)
                exists_result = cursor.fetchone()
                exists = exists_result[0] if exists_result else False
                
                # Если документы есть, получаем последний
                last_doc = None
                if exists:
                    cursor.execute("""
                        SELECT id, datecreate, numberfield, kpk
                        FROM ch_purchase
                        WHERE id_shift IS NULL
                        ORDER BY datecreate DESC
                        LIMIT 1
                    """)
                    last_doc = cursor.fetchone()
                
                return exists, last_doc
        except psycopg2.Error as e:
            if self.logger:
                self.logger.error(f"Ошибка проверки документов в БД: {e}")
            raise
    
    def _fix_document_in_db(self, conn: psycopg2.extensions.connection) -> Optional[Tuple]:
        """
        Исправляет документ в БД, привязывая его к активной смене
        
        Args:
            conn: Подключение к БД
            
        Returns:
            Данные исправленного документа или None
        """
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
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
                                ELSE 1
                            END AS next_kpk
                        FROM (
                            SELECT MAX(kpk) AS kpk FROM ch_purchase WHERE checkstatus = '1' AND id_shift = (SELECT id FROM active_shift)
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
                    RETURNING id, datecommit, fiscaldocnum, numberfield;
                """)
                result = cursor.fetchone()
                if result and self.logger:
                    self.logger.info(f"Документ исправлен: ID={result[0]}")
                return result
        except psycopg2.Error as e:
            if self.logger:
                self.logger.error(f"Ошибка исправления документа в БД: {e}")
            raise
    
    def _format_log_message(self, timestamp: str, message_type: str, host: str, data: Dict = None) -> str:
        """
        Форматирует сообщение для записи в лог
        
        Args:
            timestamp: Временная метка
            message_type: Тип сообщения
            host: IP-адрес хоста
            data: Дополнительные данные
            
        Returns:
            Отформатированное сообщение
        """
        if data is None:
            data = {}
            
        if message_type == "found_document":
            return (
                f"[{timestamp}] Найден документ без смены:, "
                f"{host};ID={data.get('id', 'N/A')}, "
                f"Дата={data.get('date', 'N/A')}, "
                f"Номер={data.get('number', 'N/A')}, "
                f"КПК={data.get('kpk', 'N/A')},\n"
            )
        elif message_type == "no_documents":
            return f"[{timestamp}] Документов без смены не найдено ,,,,,,\n"
        elif message_type == "ssh_success":
            return f"[{timestamp}] SSH команда выполнена успешно на {host}: {data.get('result', '')}\n"
        elif message_type == "ssh_error":
            return f"[{timestamp}] Ошибка SSH на {host}: {data.get('error', '')}\n"
        elif message_type == "fixed_document":
            return (
                f"[{timestamp}] Исправлен документ без смены: "
                f"{host};ID={data.get('id', 'N/A')}; "
                f"Дата={data.get('date', 'N/A')}; "
                f"Номер документа={data.get('fiscaldocnum', 'N/A')}; "
                f"Номер чека={data.get('numberfield', 'N/A')};\n"
            )
        else:
            return f"[{timestamp}] {message_type}: {host} - {data}\n"
    
    def _process_remediation_actions(self, host: str, conn: psycopg2.extensions.connection):
        """
        Выполняет действия по исправлению найденных документов
        
        Args:
            host: IP-адрес хоста
            conn: Подключение к БД
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Останавливаем сервис
        if self.logger:
            self.logger.info(f"Останавливаем сервис на {host}")
        ssh_success, ssh_result = self._execute_ssh_command(host, "cash stop")
        log_message = self._format_log_message(
            timestamp, 
            "ssh_success" if ssh_success else "ssh_error",
            host,
            {"result": ssh_result} if ssh_success else {"error": ssh_result}
        )
        self._write_log(log_message)
        
        # Исправляем документ в БД
        if self.logger:
            self.logger.info(f"Исправляем документ в БД на {host}")
        fixed_doc = self._fix_document_in_db(conn)
        if fixed_doc:
            log_message = self._format_log_message(
                timestamp, 
                "fixed_document", 
                host,
                {
                    "id": fixed_doc[0],
                    "date": fixed_doc[1],
                    "fiscaldocnum": fixed_doc[2],
                    "numberfield": fixed_doc[3]
                }
            )
            self._write_log(log_message)
            print(f"Документ исправлен: {fixed_doc}")
        
        # Запускаем сервис
        if self.logger:
            self.logger.info(f"Запускаем сервис на {host}")
        ssh_success, ssh_result = self._execute_ssh_command(host, "cash start")
        log_message = self._format_log_message(
            timestamp, 
            "ssh_success" if ssh_success else "ssh_error",
            host,
            {"result": ssh_result} if ssh_success else {"error": ssh_result}
        )
        self._write_log(log_message)
    
    def check_single_host(self, host: str) -> bool:
        """
        Проверяет один хост на наличие документов без смены
        
        Args:
            host: IP-адрес хоста
            
        Returns:
            True если найдены документы без смены, False в противном случае
        """
        try:
            if self.logger:
                self.logger.info(f"Начинаем проверку хоста {host}")
            
            conn = self._get_database_connection(host)
            
            with conn:
                # Проверяем документы
                exists, last_doc = self._check_documents_in_db(conn)
                
                # Формируем и записываем лог
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if exists and last_doc:
                    log_message = self._format_log_message(
                        timestamp, 
                        "found_document", 
                        host,
                        {
                            "id": last_doc[0],
                            "date": last_doc[1],
                            "number": last_doc[2],
                            "kpk": last_doc[3]
                        }
                    )
                    self._write_log(log_message)
                    
                    # Выполняем исправительные действия
                    print(f"Обнаружен документ без смены на {host}. Выполняю исправительные действия...")
                    self._process_remediation_actions(host, conn)
                    
                elif exists:
                    log_message = f"[{timestamp}] Найден документ без смены (нет данных) ,,,,,,\n"
                    self._write_log(log_message)
                else:
                    log_message = self._format_log_message(timestamp, "no_documents", host)
                    self._write_log(log_message)
                
                return exists
                
        except psycopg2.Error as e:
            error_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Ошибка подключения к БД {host}: {e}\n"
            self._write_log(error_msg)
            if self.logger:
                self.logger.error(f"Database error for {host}: {e}")
            return False
        except Exception as e:
            error_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Неожиданная ошибка {host}: {e}\n"
            self._write_log(error_msg)
            if self.logger:
                self.logger.error(f"Unexpected error for {host}: {e}")
            return False
    
    def check_all_hosts(self) -> Dict[str, bool]:
        """
        Проверяет все хосты из списка
        
        Returns:
            Словарь с результатами проверки для каждого хоста
        """
        if not self.hosts:
            warning_msg = f"Не найдены IP-адреса в файле {self.ip_file}. Проверка не будет выполнена."
            if self.logger:
                self.logger.warning(warning_msg)
            else:
                print(warning_msg)
            return {}
        
        results = {}
        for host in self.hosts:
            if self.logger:
                self.logger.info(f"Проверка хоста: {host}")
            result = self.check_single_host(host)
            results[host] = result
            print(f"Результат проверки {host}: {'Документы найдены' if result else 'Документы не найдены'}")
        
        return results
    
    def run(self):
        """Основной метод для запуска проверки"""
        if self.logger:
            self.logger.info("Запуск проверки документов без смены")
        results = self.check_all_hosts()
        
        if results:
            success_msg = f"Проверка завершена. Результаты записаны в {self.log_file}"
            if self.logger:
                self.logger.info(success_msg)
            print(f"Смотри результат в лог файле: {self.log_file}")
        
        return results


def main():
    """Точка входа в программу"""
    try:
        checker = DocumentChecker()
        checker.run()
        time.sleep(5)
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()