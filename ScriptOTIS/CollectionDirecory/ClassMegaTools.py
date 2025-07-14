import subprocess
from pathlib import Path
import logging
from typing import Dict, List, Optional, Tuple, Set
import time
import json
import ipaddress
import unittest
from unittest.mock import Mock, patch
from dataclasses import dataclass
from enum import Enum

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

class NodeStatus(Enum):
    """Enum для статусов узлов"""
    IN_WORK = "IN_WORK"
    UPGRADE_ERROR_WITH_DOWNGRADE = "UPGRADE_ERROR_WITH_DOWNGRADE"
    FAST_REVERT = "FAST_REVERT"
    UPGRADE_PLANING = "UPGRADE_PLANING"
    UPGRADE_DOWNLOADING = "UPGRADE_DOWNLOADING"
    UPGRADE_WAIT_FOR_REBOOT = "UPGRADE_WAIT_FOR_REBOOT"
    CHECK_PERMISSIONS = "CHECK_PERMISSIONS"
    BACKUP = "BACKUP"
    APPLY_PATCH = "APPLY_PATCH"
    TEST_START = "TEST_START"
    CCM_UPDATE_RESTART = "CCM_UPDATE_RESTART"
    UNZIP_FILES = "UNZIP_FILES"
    NO_UPDATE_NEEDED = "NO_UPDATE_NEEDED"
    UNAVAILABLE = "UNAVAILABLE"
    SUCCESS = "SUCCESS"

@dataclass
class ConfiguratorConfig:
    """Конфигурация для ConfiguratorTool"""
    centrum_host: str
    config_dir: str = "."
    jar_name: str = "ConfiguratorCmdClient-1.5.1.jar"
    encoding: str = "cp1251"
    retry_delay: int = 2
    command_timeout: int = 300
    max_retries: int = 3

class ConfiguratorError(Exception):
    """Базовый класс для ошибок конфигуратора"""
    pass

class JarNotFoundError(ConfiguratorError):
    """Ошибка отсутствия JAR файла"""
    pass

class CommandExecutionError(ConfiguratorError):
    """Ошибка выполнения команды"""
    def __init__(self, message: str, command: List[str], stderr: str = None):
        super().__init__(message)
        self.command = command
        self.stderr = stderr

class ValidationError(ConfiguratorError):
    """Ошибка валидации данных"""
    pass

class Validator:
    """Класс для валидации данных"""
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """Проверка корректности IP-адреса"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_file_exists(file_path: Path) -> bool:
        """Проверка существования файла"""
        return file_path.exists() and file_path.is_file()
    
    @staticmethod
    def validate_version_format(version: str) -> bool:
        """Проверка формата версии (x.x.x.x)"""
        try:
            parts = version.split('.')
            return len(parts) == 4 and all(part.isdigit() for part in parts)
        except:
            return False
    
    @staticmethod
    def validate_tp_format(tp: str) -> bool:
        """Проверка формата tp (x.x.x.x)"""
        try:
            parts = tp.split('.')
            return len(parts) == 4 and all(part.isdigit() for part in parts)
        except:
            return False

class OutputParser:
    """Класс для парсинга вывода команд"""
    
    def __init__(self, encoding: str = "cp1251"):
        self.encoding = encoding
    
    def parse_output(self, output: str) -> Tuple[Dict[str, Dict[str, Optional[str]]], Set[str], Set[str], Set[str]]:
        """Основной метод парсинга вывода"""
        if not output:
            return {}, set(), set(), set()

        devices_dict: Dict[str, Dict[str, Optional[str]]] = {}
        unavailable_nodes: Set[str] = set()
        success_nodes: Set[str] = set()
        no_update_needed_nodes: Set[str] = set()

        try:
            # Парсинг специальных статусов
            self._parse_special_statuses(output, success_nodes, unavailable_nodes, no_update_needed_nodes, devices_dict)
            
            # Парсинг структурированных данных
            structured_data = self._parse_structured_data(output)
            devices_dict.update(structured_data)
            
            # Обновление статусов недоступных узлов
            self._update_unavailable_statuses(devices_dict, unavailable_nodes)
            
        except Exception as e:
            logging.error(f"Ошибка при парсинге вывода: {str(e)}")
            return {}, set(), set(), set()
        
        return devices_dict, unavailable_nodes, success_nodes, no_update_needed_nodes
    
    def _parse_special_statuses(self, output: str, success_nodes: Set[str], 
                               unavailable_nodes: Set[str], no_update_needed_nodes: Set[str],
                               devices_dict: Dict[str, Dict[str, Optional[str]]]) -> None:
        """Парсинг специальных статусов из текста"""
        for line in output.splitlines():
            line = line.strip()
            
            if "успешно запланировано" in line:
                self._extract_ips_from_line(line, success_nodes, devices_dict, "SUCCESS", 
                                          "успешно запланировано")
            elif "недоступен" in line:
                self._extract_ips_from_line(line, unavailable_nodes, devices_dict, "UNAVAILABLE", 
                                          "недоступен")
            elif "не требуется" in line:
                self._extract_ips_from_line(line, no_update_needed_nodes, devices_dict, 
                                          "NO_UPDATE_NEEDED", "не требуется")
    
    def _extract_ips_from_line(self, line: str, node_set: Set[str], 
                              devices_dict: Dict[str, Dict[str, Optional[str]]], 
                              status: str, message_suffix: str) -> None:
        """Извлечение IP-адресов из строки"""
        for part in line.split():
            if self._is_ip_like(part):
                node_set.add(part)
                devices_dict[part] = self._create_device_entry(part, status, message_suffix)
    
    def _is_ip_like(self, text: str) -> bool:
        """Проверка на похожесть на IP-адрес"""
        return (text.replace(".", "").isdigit() and 
                len(text.split(".")) >= 3)
    
    def _create_device_entry(self, node: str, status: str, message_suffix: str) -> Dict[str, Optional[str]]:
        """Создание записи устройства"""
        return {
            "tp": node,
            "status": status,
            "message": f"Узел {node} {message_suffix}",
            "type": None,
            "cv": None,
            "pv": None,
            "online": None,
            "ip": None,
            "ut": None,
            "local patches": None,
        }
    
    def _parse_structured_data(self, output: str) -> Dict[str, Dict[str, Optional[str]]]:
        """Парсинг структурированных данных"""
        devices_dict: Dict[str, Dict[str, Optional[str]]] = {}
        
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith(("Current client version:", "-")):
                continue
            
            device_data = self._parse_device_line(line)
            if device_data:
                device_key = self._determine_device_key(device_data)
                if device_key:
                    devices_dict[device_key] = device_data
        
        return devices_dict
    
    def _parse_device_line(self, line: str) -> Optional[Dict[str, Optional[str]]]:
        """Парсинг строки с данными устройства"""
        device: Dict[str, Optional[str]] = {}
        
        for pair in line.split(";"):
            pair = pair.strip()
            if "=" in pair:
                key, value = pair.split("=", 1)
                key = key.strip()
                value = value.strip() if value.strip().lower() != "null" else None
                device[key] = value
        
        return device if device else None
    
    def _determine_device_key(self, device_data: Dict[str, Optional[str]]) -> Optional[str]:
        """Определение ключа устройства (приоритет IP над tp)"""
        ip_value = device_data.get("ip")
        tp_value = device_data.get("tp")
        
        if ip_value and Validator.validate_ip_address(ip_value):
            return ip_value
        elif tp_value and Validator.validate_tp_format(tp_value):
            return tp_value
        
        return None
    
    def _update_unavailable_statuses(self, devices_dict: Dict[str, Dict[str, Optional[str]]], 
                                   unavailable_nodes: Set[str]) -> None:
        """Обновление статусов недоступных узлов"""
        for device_key, device_data in devices_dict.items():
            status = (device_data.get("status") or "").upper()
            online = (device_data.get("online") or "").upper()
            
            if status == "UNAVAILABLE" or online in ("FALSE", "NO"):
                unavailable_nodes.add(device_key)

class ConfiguratorTool:
    """Улучшенный класс для работы с конфигуратором"""

    def __init__(self, config: ConfiguratorConfig):
        self.config = config
        self.config_dir = Path(config.config_dir)
        self.jar_path = self.config_dir / config.jar_name
        self.parser = OutputParser(config.encoding)
        self.validator = Validator()
        
        # Результаты и списки
        self.node_result: Dict[str, Dict[str, Optional[str]]] = {}
        self.work_tp: List[str] = []
        self.error_tp: List[str] = []
        self.update_tp: List[str] = []
        self.ccm_tp: List[str] = []
        self.unzip_tp: List[str] = []
        self.no_update_needed_tp: List[str] = []
        
        self._validate_initialization()

    def _validate_initialization(self) -> None:
        """Валидация при инициализации"""
        if not self.validator.validate_file_exists(self.jar_path):
            raise JarNotFoundError(f"JAR файл не найден: {self.jar_path}")
        
        if not self.validator.validate_ip_address(self.config.centrum_host):
            raise ValidationError(f"Некорректный IP-адрес centrum_host: {self.config.centrum_host}")
        
        if not self.config_dir.exists():
            raise ValidationError(f"Рабочая директория не существует: {self.config_dir}")

    def _execute_command(self, args: List[str], max_retries: int = None) -> Dict[str, Dict[str, Optional[str]]]:
        """Выполнение команды с улучшенной обработкой ошибок"""
        if max_retries is None:
            max_retries = self.config.max_retries
        
        result_dict: Dict[str, Dict[str, Optional[str]]] = {}
        unavailable_nodes: Set[str] = set()
        success_nodes: Set[str] = set()
        no_update_needed_nodes: Set[str] = set()
        
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            if max_retries > 1:
                logging.info(f"Попытка {attempt} из {max_retries}")

            try:
                full_command = ["java", "-jar", str(self.jar_path)] + args
                
                result = subprocess.run(
                    full_command,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding=self.config.encoding,
                    errors="replace",
                    timeout=self.config.command_timeout
                )

                if not result.stdout:
                    logging.warning("Пустой вывод от команды")
                    if attempt < max_retries:
                        time.sleep(self.config.retry_delay)
                        continue

                # Парсинг результата
                (current_result, current_unavailable, 
                 current_success, current_no_update) = self.parser.parse_output(result.stdout)
                
                result_dict.update(current_result)
                unavailable_nodes.update(current_unavailable)
                success_nodes.update(current_success)
                no_update_needed_nodes.update(current_no_update)

                if not current_unavailable or max_retries <= 1:
                    break

                if attempt < max_retries:
                    time.sleep(self.config.retry_delay)

            except subprocess.TimeoutExpired as e:
                last_error = CommandExecutionError(
                    f"Таймаут выполнения команды ({self.config.command_timeout}s)",
                    full_command
                )
                logging.error(f"Таймаут выполнения команды: {e}")
                
            except subprocess.CalledProcessError as e:
                last_error = CommandExecutionError(
                    f"Ошибка выполнения команды: {e.stderr or str(e)}",
                    full_command,
                    e.stderr
                )
                logging.error(f"Ошибка выполнения команды: {e.stderr or str(e)}")
                
            except Exception as e:
                last_error = CommandExecutionError(
                    f"Неожиданная ошибка: {str(e)}",
                    full_command
                )
                logging.error(f"Неожиданная ошибка: {str(e)}")
            
            if attempt == max_retries:
                return {"error": {"message": str(last_error), "command": " ".join(full_command)}}

        # Обработка результатов
        self._process_command_results(result_dict, unavailable_nodes, success_nodes, no_update_needed_nodes)
        
        self.node_result = result_dict
        self._categorize_nodes()
        return self.node_result

    def _process_command_results(self, result_dict: Dict[str, Dict[str, Optional[str]]], 
                               unavailable_nodes: Set[str], success_nodes: Set[str], 
                               no_update_needed_nodes: Set[str]) -> None:
        """Обработка результатов выполнения команды"""
        # Обработка различных типов узлов
        node_types = [
            (unavailable_nodes, "UNAVAILABLE", "недоступен"),
            (success_nodes, "SUCCESS", "успешно запланировано"),
            (no_update_needed_nodes, "NO_UPDATE_NEEDED", "не требуется обновление")
        ]
        
        for nodes, status, message in node_types:
            for node in nodes:
                if node not in result_dict:
                    result_dict[node] = self._create_node_result(node, status, message)

    def _create_node_result(self, node: str, status: str, message: str) -> Dict[str, Optional[str]]:
        """Создание записи результата для узла"""
        return {
            "tp": node,
            "status": status,
            "message": f"Узел {node} {message}",
            "type": None,
            "cv": None,
            "pv": None,
            "online": None,
            "ip": None,
            "ut": None,
            "local patches": None,
        }

    def _categorize_nodes(self) -> None:
        """Улучшенная категоризация узлов"""
        # Очистка списков
        self.work_tp = []
        self.error_tp = []
        self.update_tp = []
        self.ccm_tp = []
        self.unzip_tp = []
        self.no_update_needed_tp = []

        # Определение категорий статусов
        status_categories = {
            'work': [NodeStatus.IN_WORK.value],
            'error': [NodeStatus.UPGRADE_ERROR_WITH_DOWNGRADE.value, NodeStatus.FAST_REVERT.value],
            'update': [
                NodeStatus.UPGRADE_PLANING.value,
                NodeStatus.UPGRADE_DOWNLOADING.value,
                NodeStatus.UPGRADE_WAIT_FOR_REBOOT.value,
                NodeStatus.CHECK_PERMISSIONS.value,
                NodeStatus.BACKUP.value,
                NodeStatus.APPLY_PATCH.value,
                NodeStatus.TEST_START.value,
            ],
            'ccm': [NodeStatus.CCM_UPDATE_RESTART.value],
            'unzip': [NodeStatus.UNZIP_FILES.value],
            'no_update': [NodeStatus.NO_UPDATE_NEEDED.value]
        }

        for node_id, node_data in self.node_result.items():
            list_entry = self._create_list_entry(node_id, node_data)
            status = (node_data.get("status") or "").upper()
            
            # Категоризация
            if status in status_categories['work']:
                self.work_tp.append(list_entry)
            elif status in status_categories['error']:
                self.error_tp.append(list_entry)
            elif status in status_categories['update']:
                self.update_tp.append(list_entry)
            elif status in status_categories['ccm']:
                self.ccm_tp.append(list_entry)
            elif status in status_categories['unzip']:
                self.unzip_tp.append(list_entry)
            elif status in status_categories['no_update']:
                self.no_update_needed_tp.append(list_entry)

    def _create_list_entry(self, node_id: str, node_data: Dict[str, Optional[str]]) -> str:
        """Создание записи для списка"""
        tp = node_data.get("tp") or node_id
        node_type = (node_data.get("type") or "").strip()
        ip_node = (node_data.get("ip") or "").strip()
        version = (node_data.get("cv") or "").strip()
        
        # Обработка tp
        if self.validator.validate_tp_format(tp):
            parts = tp.split(".")
            if parts[3] == "0":
                tp_short = parts[2]
            else:
                tp_short = f"{parts[2]}.{parts[3]}"
        else:
            tp_short = tp

        # Формирование записи
        list_entry = tp_short
        if node_type:
            list_entry += f"-{node_type}"
        if ip_node:
            list_entry += f"-{ip_node}"
        if version:
            list_entry += f"-{version}"
        
        return list_entry

    def save_status_lists(self, prefix: str = "") -> None:
        """Сохранение списков статусов с валидацией"""
        lists_to_save = {
            "work_tp": self.work_tp,
            "error_tp": self.error_tp,
            "update_tp": self.update_tp,
            "ccm_tp": self.ccm_tp,
            "unzip_tp": self.unzip_tp,
            "no_update_needed_tp": self.no_update_needed_tp,
        }

        # Удаление старых файлов
        for list_name in lists_to_save:
            filename = f"{prefix}{list_name}.txt" if prefix else f"{list_name}.txt"
            filepath = self.config_dir / filename
            if filepath.exists():
                try:
                    filepath.unlink()
                except OSError as e:
                    logging.warning(f"Не удалось удалить файл {filepath}: {e}")

        # Сохранение новых файлов
        for list_name, data in lists_to_save.items():
            if not data:
                continue
            
            filename = f"{prefix}{list_name}.txt" if prefix else f"{list_name}.txt"
            filepath = self.config_dir / filename
            
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("\n".join(data))
                logging.info(f"Список {list_name} сохранен в {filepath}")
            except IOError as e:
                logging.error(f"Ошибка сохранения файла {filepath}: {e}")

    def get_all_nodes(self, max_retries: int = None) -> Dict[str, Dict[str, Optional[str]]]:
        """Получение всех узлов с валидацией"""
        return self._execute_command(["-ch", self.config.centrum_host, "--all"], max_retries)

    def get_nodes_from_file(self, filename: str = "server.txt") -> Dict[str, Dict[str, Optional[str]]]:
        """Получение узлов из файла с валидацией"""
        filepath = self.config_dir / filename
        if not self.validator.validate_file_exists(filepath):
            raise ValidationError(f"Файл не найден: {filepath}")
        
        return self._execute_command(["-ch", self.config.centrum_host, "-f", str(filepath)], 1)

    def update_servers(self, version_sv: str, filename: str = "server.txt", 
                      no_backup: bool = True) -> Dict[str, Dict[str, Optional[str]]]:
        """Обновление серверов с валидацией"""
        if not self.validator.validate_version_format(version_sv):
            raise ValidationError(f"Некорректный формат версии: {version_sv}")
        
        filepath = self.config_dir / filename
        if not self.validator.validate_file_exists(filepath):
            raise ValidationError(f"Файл не найден: {filepath}")
        
        args = ["-ch", self.config.centrum_host, "-f", str(filepath), "-sv", version_sv]
        if no_backup:
            args.append("-nb")
        
        return self._execute_command(args, 1)

    def update_cash_devices(self, cash_type: str, version: str, filename: str = "server_cash.txt",
                           no_backup: bool = True, auto_restart: bool = True) -> Dict[str, Dict[str, Optional[str]]]:
        """Обновление касс с валидацией"""
        if not self.validator.validate_version_format(version):
            raise ValidationError(f"Некорректный формат версии: {version}")
        
        filepath = self.config_dir / filename
        if not self.validator.validate_file_exists(filepath):
            raise ValidationError(f"Файл не найден: {filepath}")
        
        args = [
            "-ch", self.config.centrum_host,
            "-f", str(filepath),
            "-sv", version,
            "-cv", f"{cash_type}:{version}",
        ]
        if no_backup:
            args.append("-nb")
        if auto_restart:
            args.append("-ar")
        
        return self._execute_command(args, 1)

    def save_node_result(self, filename: str = "node_result.json") -> None:
        """Сохранение результатов с обработкой ошибок"""
        filepath = self.config_dir / filename
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.node_result, f, ensure_ascii=False, indent=2)
            logging.info(f"Результат сохранен в {filepath}")
        except IOError as e:
            logging.error(f"Ошибка сохранения файла {filepath}: {e}")

# Unit тесты
class TestConfiguratorTool(unittest.TestCase):
    """Unit тесты для ConfiguratorTool"""
    
    def setUp(self):
        """Настройка тестового окружения"""
        self.config = ConfiguratorConfig(
            centrum_host="127.0.0.1",
            config_dir="test_dir",
            jar_name="test.jar"
        )
    
    def test_validator_ip_validation(self):
        """Тест валидации IP-адресов"""
        self.assertTrue(Validator.validate_ip_address("192.168.1.1"))
        self.assertTrue(Validator.validate_ip_address("10.0.0.1"))
        self.assertFalse(Validator.validate_ip_address("256.1.1.1"))
        self.assertFalse(Validator.validate_ip_address("invalid"))
    
    def test_validator_version_validation(self):
        """Тест валидации версий"""
        self.assertTrue(Validator.validate_version_format("10.4.15.1"))
        self.assertTrue(Validator.validate_version_format("1.2.3.4"))
        self.assertFalse(Validator.validate_version_format("10.4.15"))
        self.assertFalse(Validator.validate_version_format("invalid"))
    
    def test_output_parser_ip_extraction(self):
        """Тест извлечения IP-адресов из текста"""
        parser = OutputParser()
        test_output = "Узел 192.168.1.1 успешно запланировано"
        
        result, unavailable, success, no_update = parser.parse_output(test_output)
        
        self.assertIn("192.168.1.1", success)
        self.assertIn("192.168.1.1", result)
        self.assertEqual(result["192.168.1.1"]["status"], "SUCCESS")
    
    def test_output_parser_structured_data(self):
        """Тест парсинга структурированных данных"""
        parser = OutputParser()
        test_output = "tp=1.0.54.0;type=RETAIL;cv=10.4.14.14;ip=10.100.103.54;status=IN_WORK"
        
        result, _, _, _ = parser.parse_output(test_output)
        
        self.assertIn("10.100.103.54", result)
        self.assertEqual(result["10.100.103.54"]["type"], "RETAIL")
        self.assertEqual(result["10.100.103.54"]["cv"], "10.4.14.14")
    
    @patch('subprocess.run')
    def test_command_execution_success(self, mock_run):
        """Тест успешного выполнения команды"""
        mock_run.return_value.stdout = "tp=1.0.1.0;ip=192.168.1.1;status=IN_WORK"
        mock_run.return_value.stderr = ""
        
        # Создаем mock файл
        with patch('pathlib.Path.exists', return_value=True):
            configurator = ConfiguratorTool(self.config)
            result = configurator._execute_command(["-ch", "127.0.0.1", "--all"])
        
        self.assertIn("192.168.1.1", result)
        self.assertEqual(result["192.168.1.1"]["status"], "IN_WORK")
    
    @patch('subprocess.run')
    def test_command_execution_error(self, mock_run):
        """Тест обработки ошибок выполнения команды"""
        mock_run.side_effect = subprocess.CalledProcessError(1, "java", stderr="Error message")
        
        with patch('pathlib.Path.exists', return_value=True):
            configurator = ConfiguratorTool(self.config)
            result = configurator._execute_command(["-ch", "127.0.0.1", "--all"])
        
        self.assertIn("error", result)
        self.assertIn("Error message", result["error"]["message"])

# Пример использования с улучшенной конфигурацией
if __name__ == "__main__":
    try:
        # Создание конфигурации
        config = ConfiguratorConfig(
            centrum_host="10.21.11.45",
            config_dir="C:\\Users\\iakushin.n\\Documents\\GitHub\\Python\\updaterJar",
            encoding="cp1251",
            retry_delay=3,
            command_timeout=600,
            max_retries=3
        )
        
        # Создание конфигуратора
        configurator = ConfiguratorTool(config)

        # Получение всех узлов
        all_nodes = configurator.get_all_nodes()
        
        if "error" in all_nodes:
            logging.error(f"Ошибка получения узлов: {all_nodes['error']}")
        else:
            print("Все узлы получены успешно")
            configurator.save_node_result()
            configurator.save_status_lists()

        # Запуск тестов
        unittest.main(argv=[''], exit=False)

    except ConfiguratorError as e:
        logging.error(f"Ошибка конфигуратора: {str(e)}")
    except Exception as e:
        logging.error(f"Неожиданная ошибка: {str(e)}")