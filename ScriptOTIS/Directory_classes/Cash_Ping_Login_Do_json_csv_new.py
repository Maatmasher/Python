#!/usr/bin/env python3
import asyncio
import json
import csv
from datetime import datetime
import os
import aiofiles


class SSHCommandExecutor:
    """Класс для асинхронного выполнения SSH команд на множестве хостов"""
    
    def __init__(self, config=None):
        """Инициализация с конфигурацией"""
        # Базовая конфигурация
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Применяем пользовательскую конфигурацию или используем по умолчанию
        if config:
            self.config = config
        else:
            self.config = self._get_default_config()
        
        # Инициализация путей к файлам
        self.cash_ip_file = os.path.join(self.current_dir, self.config['cash_ip_file'])
        self.log_file = os.path.join(self.current_dir, self.config['log_file'])
        self.ping_csv_file = os.path.join(self.current_dir, self.config['ping_csv_file'])
        self.command_log_file = os.path.join(self.current_dir, self.config['command_log_file'])
        
        # SSH параметры
        self.user = self.config['user']
        self.password = self.config['password']
        self.plink_cmd = self.config['plink_cmd']
        self.ssh_test_cmd = self.config['ssh_test_cmd']
        
        # Параметры выполнения
        self.max_concurrent_tasks = self.config['max_concurrent_tasks']
        self.enable_command_log = self.config['enable_command_log']
        self.type_commands = self.config['type_commands']
        
        # Счетчики
        self.stats = {
            'total_hosts': 0,
            'processed_hosts': 0,
            'successful_commands': 0,
            'failed_commands': 0,
            'ping_failures': 0,
            'ssh_failures': 0
        }

    def _get_default_config(self):
        """Конфигурация по умолчанию"""
        return {
            'cash_ip_file': 'cash_ip_all.json',
            'log_file': 'execution.log',
            'ping_csv_file': 'ping_results.csv',
            'command_log_file': 'command_execution.csv',
            'enable_command_log': True,
            'max_concurrent_tasks': 15,
            'user': 'tc',
            'password': 'JnbcHekbn123',
            'plink_cmd': 'plink.exe -ssh {user}@{host} -pw {password} -batch -m {command_file}',
            'ssh_test_cmd': 'plink.exe -ssh {user}@{host} -pw {password} -batch echo OK',
            'type_commands': {
                'POS': 'command_POS.txt',
                'SCO': 'command_SCO.txt',
                'SCO_3': 'command_SCO_3.txt',
                'TOUCH': 'command_TOUCH.txt',
            }
        }

    def setup_files(self):
        """Инициализация файлов логов"""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        # Очищаем основной лог выполнения
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("")

        # Инициализация CSV файла для ping результатов
        with open(self.ping_csv_file, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Timestamp", "Host", "Device Type", "Ping Status", "SSH Login Status"])

        # Инициализация CSV файла для выполнения команд (если включено)
        if self.enable_command_log:
            with open(self.command_log_file, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    "Timestamp", 
                    "Host", 
                    "Device Type", 
                    "Command File", 
                    "Execution Status", 
                    "Return Code", 
                    "Duration (seconds)", 
                    "Output Preview",
                    "Error Preview"
                ])

    async def log_execution(self, message):
        """Запись сообщения в лог выполнения"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        print(log_entry.strip())
        async with aiofiles.open(self.log_file, "a", encoding="utf-8") as f:
            await f.write(log_entry)

    async def record_ping_result(self, host, device_type, ping_status, ssh_status):
        """Запись результата ping и SSH в CSV файл"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.ping_csv_file, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([timestamp, host, device_type, ping_status, ssh_status])

    async def record_command_execution(self, host, device_type, command_file, status, return_code, duration, stdout_preview, stderr_preview):
        """Запись результата выполнения команды в CSV файл"""
        if not self.enable_command_log:
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Ограничиваем длину превью вывода
        max_preview_length = 200
        stdout_preview = (stdout_preview[:max_preview_length] + "...") if len(stdout_preview) > max_preview_length else stdout_preview
        stderr_preview = (stderr_preview[:max_preview_length] + "...") if len(stderr_preview) > max_preview_length else stderr_preview
        
        # Заменяем переносы строк на пробелы для корректного CSV
        stdout_preview = stdout_preview.replace('\n', ' ').replace('\r', ' ')
        stderr_preview = stderr_preview.replace('\n', ' ').replace('\r', ' ')
        
        try:
            with open(self.command_log_file, "a", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    timestamp, 
                    host, 
                    device_type, 
                    os.path.basename(command_file), 
                    status, 
                    return_code, 
                    f"{duration:.2f}",
                    stdout_preview,
                    stderr_preview
                ])
        except Exception as e:
            await self.log_execution(f"Ошибка записи в лог команд: {str(e)}")

    async def check_ping(self, host):
        """Асинхронная проверка ping"""
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

            if "TTL=" in stdout.decode():
                return True
            return False
        except Exception:
            return False

    async def check_ssh_login(self, host):
        """Асинхронная проверка SSH-логина"""
        try:
            cmd = self.ssh_test_cmd.format(user=self.user, password=self.password, host=host)
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0 and "OK" in stdout.decode():
                return True
            return False
        except Exception:
            return False

    def get_command_file(self, device_type):
        """Получение файла команд с fallback на default"""
        # Пытаемся найти файл для конкретного типа
        if device_type in self.type_commands:
            specific_file = os.path.join(self.current_dir, self.type_commands[device_type])
            if os.path.exists(specific_file):
                return specific_file
        
        # Используем default файл
        default_file = os.path.join(self.current_dir, "command_default.txt")
        if os.path.exists(default_file):
            return default_file
        
        return None

    async def run_plink(self, host, device_type):
        """Асинхронное выполнение команды через plink"""
        command_file = self.get_command_file(device_type)
        
        if not command_file:
            await self.log_execution(
                f"{host} ({device_type}) Не найден ни специфичный файл команд, "
                f"ни command_default.txt"
            )
            if self.enable_command_log:
                await self.record_command_execution(
                    host, device_type, "N/A", "File Not Found", -1, 0, "", "Command file not found"
                )
            self.stats['failed_commands'] += 1
            return False
        
        # Логируем какой файл используется
        filename = os.path.basename(command_file)
        if filename == "command_default.txt":
            await self.log_execution(
                f"{host} ({device_type}) Используется файл по умолчанию: {filename}"
            )
        else:
            await self.log_execution(
                f"{host} ({device_type}) Используется специфичный файл: {filename}"
            )

        cmd = self.plink_cmd.format(
            user=self.user, password=self.password, command_file=command_file, host=host
        )

        start_time = datetime.now()
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=1800)
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                stdout_text = stdout.decode().strip()
                stderr_text = stderr.decode().strip()

                if proc.returncode == 0:
                    await self.log_execution(f"{host} ({device_type}) Успешно\n{stdout_text}")
                    if self.enable_command_log:
                        await self.record_command_execution(
                            host, device_type, command_file, "Success", proc.returncode, 
                            duration, stdout_text, stderr_text
                        )
                    self.stats['successful_commands'] += 1
                    return True
                else:
                    await self.log_execution(
                        f"{host} ({device_type}) Ошибка (код {proc.returncode})\n{stderr_text}"
                    )
                    if self.enable_command_log:
                        await self.record_command_execution(
                            host, device_type, command_file, "Error", proc.returncode, 
                            duration, stdout_text, stderr_text
                        )
                    self.stats['failed_commands'] += 1
                    return False
            except asyncio.TimeoutError:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                await self.log_execution(f"{host} ({device_type}) Таймаут выполнения")
                proc.kill()
                await proc.communicate()
                if self.enable_command_log:
                    await self.record_command_execution(
                        host, device_type, command_file, "Timeout", -1, 
                        duration, "", "Execution timeout"
                    )
                self.stats['failed_commands'] += 1
                return False
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            await self.log_execution(f"{host} ({device_type}) Критическая ошибка: {str(e)}")
            if self.enable_command_log:
                await self.record_command_execution(
                    host, device_type, command_file, "Critical Error", -1, 
                    duration, "", str(e)
                )
            self.stats['failed_commands'] += 1
            return False

    async def process_host(self, host_info):
        """Обработка одного хоста"""
        host = host_info["ip"]
        device_type = host_info["type"]

        remaining = self.stats['total_hosts'] - self.stats['processed_hosts']
        await self.log_execution(
            f"Обработка {host} ({device_type}) | Осталось хостов: {remaining}"
        )

        # Проверка ping
        ping_success = await self.check_ping(host)
        ping_status = "Success" if ping_success else "Failed"
        
        if not ping_success:
            self.stats['ping_failures'] += 1
        
        # Проверка SSH
        ssh_success = False
        if ping_success:  # Проверяем SSH только если ping успешен
            ssh_success = await self.check_ssh_login(host)
        
        ssh_status = "Success" if ssh_success else "Failed"
        
        if not ssh_success and ping_success:
            self.stats['ssh_failures'] += 1
        
        # Запись результатов в CSV
        await self.record_ping_result(host, device_type, ping_status, ssh_status)

        # Выполнение основной команды если оба теста успешны
        if ping_success and ssh_success:
            await self.run_plink(host, device_type)
        else:
            await self.log_execution(
                f"{host} ({device_type}) Пропуск выполнения команды. "
                f"Ping: {ping_status}, SSH: {ssh_status}"
            )

        self.stats['processed_hosts'] += 1

    async def load_hosts(self):
        """Загрузка хостов из JSON файла"""
        try:
            async with aiofiles.open(self.cash_ip_file, "r") as f:
                content = await f.read()
                cash_data = json.loads(content)
            return [{"ip": ip, "type": info["type"]} for ip, info in cash_data.items()]
        except Exception as e:
            await self.log_execution(f"Ошибка загрузки файла {self.cash_ip_file}: {str(e)}")
            return []

    async def print_statistics(self):
        """Вывод итоговой статистики"""
        await self.log_execution("=" * 60)
        await self.log_execution("ИТОГОВАЯ СТАТИСТИКА:")
        await self.log_execution(f"Всего хостов: {self.stats['total_hosts']}")
        await self.log_execution(f"Обработано хостов: {self.stats['processed_hosts']}")
        await self.log_execution(f"Успешных команд: {self.stats['successful_commands']}")
        await self.log_execution(f"Неуспешных команд: {self.stats['failed_commands']}")
        await self.log_execution(f"Ошибок ping: {self.stats['ping_failures']}")
        await self.log_execution(f"Ошибок SSH: {self.stats['ssh_failures']}")
        
        if self.stats['total_hosts'] > 0:
            success_rate = (self.stats['successful_commands'] / self.stats['total_hosts']) * 100
            await self.log_execution(f"Процент успешных команд: {success_rate:.2f}%")
        
        await self.log_execution("=" * 60)

    async def run(self):
        """Основной метод запуска"""
        self.setup_files()
        
        await self.log_execution("=" * 50)
        await self.log_execution("НАЧАЛО ВЫПОЛНЕНИЯ СКРИПТА")
        await self.log_execution(f"Лог выполнения команд: {'ВКЛЮЧЕН' if self.enable_command_log else 'ВЫКЛЮЧЕН'}")
        if self.enable_command_log:
            await self.log_execution(f"Файл лога команд: {self.command_log_file}")
        await self.log_execution(f"Максимальное количество одновременных задач: {self.max_concurrent_tasks}")
        await self.log_execution("=" * 50)

        # Загрузка списка касс из JSON
        hosts = await self.load_hosts()
        if not hosts:
            await self.log_execution("Нет хостов для обработки")
            return

        self.stats['total_hosts'] = len(hosts)
        await self.log_execution(f"Начало обработки {self.stats['total_hosts']} хостов")

        # Создаем семафор для ограничения количества одновременных действий
        semaphore = asyncio.Semaphore(self.max_concurrent_tasks)

        async def limited_task(host_info):
            async with semaphore:
                await self.process_host(host_info)

        # Запускаем задачи
        tasks = [limited_task(host) for host in hosts]
        await asyncio.gather(*tasks)

        await self.log_execution("Обработка завершена")
        await self.print_statistics()


# Пример использования
async def main():
    # Создание экземпляра с конфигурацией по умолчанию
    executor = SSHCommandExecutor()
    
    # Или с пользовательской конфигурацией
    # custom_config = {
    #     'enable_command_log': False,
    #     'max_concurrent_tasks': 15,
    #     'user': 'admin',
    #     'password': 'password123'
    # }
    # executor = SSHCommandExecutor(custom_config)
    
    await executor.run()


if __name__ == "__main__":
    asyncio.run(main())