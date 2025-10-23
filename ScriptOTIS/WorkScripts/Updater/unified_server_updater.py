import time
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Union
import json
import keyring
from getpass import getpass
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2 import sql

from config_manager import ConfigManager
from logger_manager import LoggerManager, create_logger_manager
from execute_command import CommandExecutor


# ==================== КОНФИГУРАЦИОННЫЕ ПАРАМЕТРЫ ====================

MAX_RETRIES_DEFAULT = 3
MAX_RETRIES_SINGLE = 3
DEFAULT_NO_BACKUP = True
DEFAULT_JAR = True

# ====================================================================


class UnifiedServerUpdater:
    """Унифицированный класс для работы с JAR-инструментом конфигурации и пошаговым обновлением серверов"""

    def __init__(
        self,
        config: Optional[ConfigManager] = None,
        logger_manager: Optional[LoggerManager] = None,
    ):
        # Инициализация конфигурации
        self.config = config or ConfigManager()
        self.current_iteration = 0

        # Инициализация логирования
        logging_config = self.config.get("logging", {})
        self.logger_manager = logger_manager or create_logger_manager(logging_config)
        # self.logger_manager.setup_logging()
        self.logger = self.logger_manager.get_logger(__name__)

        # Инициализация исполнителя команд
        self.command_executor = CommandExecutor(self.logger_manager)

        # Валидация конфигурации
        if not self.config.validate():
            self.logger.error("Невалидная конфигурация")
            raise ValueError("Невалидная конфигурация")

        self.logger.info("UnifiedServerUpdater инициализирован")

        # Инициализация остальных компонентов
        self._initialize_data_structures()
        self._init_components()

    def _init_components(self):
        """Инициализация компонентов на основе конфигурации"""
        # Инициализация Centrum
        self.centrum_host = self.config.get("centrum_host")
        self.logger.debug(f"Centrum host: {self.centrum_host}")
        # Инициализация SSH окружения
        self.service_name = self.config.get("service_name")
        self.logger.debug(f"Service name: {self.service_name}")
        self.ssh_user = self.config.get("ssh_user")
        self.logger.debug(f"SSH User: {self.ssh_user}")
        self.plink_timeout = self.config.get("plink_timeout")
        self.logger.debug(f"plink_timeout: {self.plink_timeout}")
        self.plink_path = Path(self.config.get("plink_path"))
        self.logger.debug(f"Plink_path: {self.plink_path}")
        self.password = self._init_password()
        self.logger.debug(f"Инициализация SSH пароля успешна")
        # Инициализация необходимой версии
        self.target_version = self.config.get("target_version")
        self.logger.debug(f"Target version: {self.target_version}")
        # Инициализация Postgres окружения
        self.db_user = self.config.get("db_user")
        self.db_table = self.config.get("db_table")
        self.db_service_name = self.config.get("db_service_name")
        self.db_host = self.config.get("db_host")
        self.db_port = self.config.get("db_port")
        self.db_name = self.config.get("db_name")
        self.db_password = None  # Будет инициализирован при первом обращении к БД
        # Инициализация Patch
        self.current_dir = self.config.get("current_dir")
        self.config_dir = self.config.get("config_dir")
        self.jar_path = Path(self.config.get("config_dir")) / self.config.get(
            "jar_name"
        )
        if not isinstance(self.config_dir, str):
            self.logger.warning("config_dir не является строкой, преобразуем")
            self.config_dir = str(self.config_dir)
        # Проверка существования JAR файла
        if not self.jar_path.exists():
            error_msg = f"JAR файл не найден: {self.jar_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        self.part_server_size = self.config.get("part_server_size")
        self.max_iterations = self.config.get("max_iterations")
        self.wait_between_retries = self.config.get("wait_between_retries")
        self.pre_update_timeout = self.config.get("pre_update_timeout")
        self.post_update_timeout = self.config.get("post_update_timeout")
        self.status_check_interval = self.config.get("status_check_interval")
        self.updated_servers: Set[str] = set()
        self.result_dict = {}
        self.jar_behavior = self.config.get("jar_behavior")
        self.logger.debug(f"JAR путь: {self.jar_path}")

        self.logger.debug("Компоненты успешно инициализированы")

    def _initialize_data_structures(self):
        """Инициализирует структуры данных в зависимости от режима"""
        self.work_tp: List[str] = []
        self.error_tp: List[str] = []
        self.update_tp: List[str] = []
        self.ccm_tp: List[str] = []
        self.unzip_tp: List[str] = []
        self.no_update_needed_tp: List[str] = []
        self.unavailable: List[str] = []
        self.node_result: Dict[str, Dict[str, Optional[str]]] = {}

    def _test_password(self, password: str) -> bool:
        """Проверяет, работает ли пароль (пробует подключиться через plink)"""
        try:
            # Формируем команду для проверки подключения
            test_cmd = [
                str(self.plink_path),
                "-ssh",
                f"{self.ssh_user}@{self.centrum_host}",
                "-pw",
                password,
                "-batch",
                "-no-trivial-auth",
                "echo OK",
            ]

            self.logger.debug(f"Тестирование пароля: {' '.join(test_cmd)}")

            result = subprocess.run(
                test_cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
            )

            # Проверяем, что команда выполнилась успешно и вернула "OK"
            if "OK" in result.stdout:
                self.logger.debug("Пароль валиден")
                return True
            else:
                self.logger.debug(f"Неверный ответ от сервера: {result.stdout}")
                return False

        except subprocess.CalledProcessError as e:
            self.logger.debug(f"Ошибка подключения (неверный пароль?): {e.stderr}")
            return False
        except subprocess.TimeoutExpired:
            self.logger.debug("Таймаут при проверке пароля")
            return False
        except Exception as e:
            self.logger.debug(f"Неожиданная ошибка при проверке пароля: {str(e)}")
            return False

    def _init_password(self) -> str:
        """Инициализирует пароль, проверяя keyring или запрашивая у пользователя"""
        try:
            password = keyring.get_password(self.service_name, self.ssh_user)

            if password is not None:
                self.logger.debug("Пароль найден в keyring, проверяем валидность...")
                if self._test_password(password):
                    self.logger.debug("Пароль из keyring валиден")
                    return password
                else:
                    self.logger.warning(
                        "Пароль из keyring не подходит. Требуется ввод нового пароля."
                    )
            else:
                self.logger.debug("Пароль не найден в keyring")

            # Если пароля нет или он невалидный — запрашиваем новый
            password = getpass(
                f"Введите пароль для пользователя {self.config.get('ssh_user')}: "
            )

            # Проверяем новый пароль перед сохранением
            if not self._test_password(password):
                raise ValueError("Введенный пароль недействителен")

            keyring.set_password(self.service_name, self.ssh_user, password)
            self.logger.info("Пароль успешно сохранён в keyring")
            return password

        except Exception as e:
            self.logger.error(f"Ошибка при работе с keyring: {str(e)}")
            raise RuntimeError("Не удалось инициализировать пароль") from e

    def _init_db_password(self) -> str:
        """Инициализирует пароль для базы данных"""
        try:
            db_password = keyring.get_password(self.db_service_name, self.db_user)
            # Если пароль есть в keyring, проверяем его валидность
            if db_password is not None:
                if self._test_db_connection(db_password):
                    return db_password
                self.logger.warning(
                    "Пароль БД из keyring не подходит. Требуется ввод нового пароля."
                )

            # Если пароля нет или он невалидный — запрашиваем новый
            db_password = getpass(
                f"Введите пароль для базы данных (пользователь {self.db_user}): "
            )

            # Проверяем новый пароль
            if self._test_db_connection(db_password):
                keyring.set_password(
                    self.db_service_name,
                    self.db_user,
                    db_password,
                )
                self.logger.info("Пароль БД успешно сохранён в keyring")
                return db_password
            else:
                raise ValueError("Неверный пароль для базы данных")

        except Exception as e:
            self.logger.error(f"Ошибка при работе с keyring для БД: {str(e)}")
            raise RuntimeError("Не удалось инициализировать пароль БД") from e

    def _test_db_connection(self, password: str) -> bool:
        """Проверяет подключение к базе данных"""
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=password,
                connect_timeout=5,
            )
            conn.close()
            return True
        except psycopg2.Error:
            return False
        except Exception:
            return False

    def _get_nodes_from_database(self) -> Dict[str, Dict[str, Optional[str]]]:
        """Получает информацию об узлах из базы данных PostgreSQL"""
        self.logger.info("Получение информации об узлах из базы данных PostgreSQL")

        try:
            # Получаем пароль для БД
            if not hasattr(self, "db_password") or self.db_password is None:
                self.db_password = self._init_db_password()

            # Подключаемся к базе данных
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password,
            )

            self.logger.debug(
                f"Успешное подключение к БД {self.db_name} на {self.db_host}:{self.db_port}"
            )

            with conn.cursor(cursor_factory=DictCursor) as cursor:
                # Выполняем запрос для получения всех узлов
                query = sql.SQL(
                    """
                    SELECT tp, type, cv, pv, online, ip, status, ul as ut, "locPatches" as local_patches, 
                        sel_date, ins_date 
                    FROM {table}
                    WHERE type IS NOT NULL
                    ORDER BY tp;
                """
                ).format(table=sql.Identifier(self.config.get("db_table")))

                self.logger.debug(f"Выполнение запроса: {query.as_string(conn)}")
                cursor.execute(query)

                rows = cursor.fetchall()
                self.logger.info(f"Получено {len(rows)} записей из базы данных")

            conn.close()

            # Конвертируем результат в нужный формат
            return self._convert_db_rows_to_nodes_format(rows)

        except psycopg2.Error as e:
            error_msg = f"Ошибка при работе с базой данных: {str(e)}"
            self.logger.error(error_msg)
            return {"error": {"message": error_msg}}
        except Exception as e:
            error_msg = f"Неожиданная ошибка при обращении к БД: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return {"error": {"message": error_msg}}

    def _convert_db_rows_to_nodes_format(
        self, rows
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Конвертирует строки из БД в формат словаря узлов"""
        self.logger.debug(f"Конвертация {len(rows)} строк из БД в формат узлов")

        nodes_dict = {}

        for row in rows:
            try:
                # Получаем данные из строки БД
                row_data = dict(row)

                # Определяем ключ для узла (приоритет: ip, затем tp)
                node_key = row_data.get("ip") or row_data.get("tp")
                if not node_key:
                    self.logger.warning(f"Пропуск строки без ip и tp: {row_data}")
                    continue

                # Формируем словарь узла в нужном формате
                node_info = {
                    "tp": self._safe_str_convert(row_data.get("tp")),
                    "type": self._safe_str_convert(row_data.get("type")),
                    "cv": self._safe_str_convert(row_data.get("cv")),
                    "pv": self._safe_str_convert(row_data.get("pv")),
                    "online": self._safe_str_convert(row_data.get("online")),
                    "status": self._safe_str_convert(row_data.get("status")),
                    "ip": self._safe_str_convert(row_data.get("ip")),
                    "ut": self._safe_str_convert(row_data.get("ut")),
                    "local patches": self._safe_str_convert(
                        row_data.get("local_patches")
                    ),
                }

                # Добавляем узел в результирующий словарь
                nodes_dict[node_key] = node_info

                self.logger.debug(
                    f"Добавлен узел {node_key}: type={node_info['type']}, status={node_info['status']}"
                )

            except Exception as e:
                self.logger.error(f"Ошибка при обработке строки БД: {row_data}, ошибка: {str(e)}")  # type: ignore
                continue

        self.logger.info(f"Успешно сконвертировано {len(nodes_dict)} узлов из БД")
        return nodes_dict

    def _safe_str_convert(self, value) -> Optional[str]:
        """Безопасная конвертация значения в строку"""
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip() if value.strip() else None
        # Для datetime объектов и других типов
        return str(value).strip() if str(value).strip() else None

    def _execute_command(
        self, args: List[str], max_retries: int = MAX_RETRIES_SINGLE
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Выполняет команду с повторами для недоступных узлов"""

        result = self.command_executor.execute_jar_command(
            self.jar_path, args, max_retries, self.config.get("wait_between_retries")
        )

        categorized_lists = self.command_executor.categorize_nodes(result)

        # Определяем целевые списки в зависимости от режима
        if self.jar_behavior:  # Перезапись - создаем новые списки
            work_tp = categorized_lists["work_tp"]
            error_tp = categorized_lists["error_tp"]
            update_tp = categorized_lists["update_tp"]
            ccm_tp = categorized_lists["ccm_tp"]
            unzip_tp = categorized_lists["unzip_tp"]
            no_update_needed_tp = categorized_lists["no_update_needed_tp"]
            unavailable = categorized_lists["unavailable"]
            result_dict = result
        else:  # Дополнение - расширяем существующие
            work_tp = self.work_tp + categorized_lists["work_tp"]
            error_tp = self.error_tp + categorized_lists["error_tp"]
            update_tp = self.update_tp + categorized_lists["update_tp"]
            ccm_tp = self.ccm_tp + categorized_lists["ccm_tp"]
            unzip_tp = self.unzip_tp + categorized_lists["unzip_tp"]
            no_update_needed_tp = (
                self.no_update_needed_tp + categorized_lists["no_update_needed_tp"]
            )
            unavailable = self.unavailable + categorized_lists["unavailable"]
            result_dict = {**self.result_dict, **result}

        # Убираем дубликаты в режиме дополнения
        if not self.jar_behavior:
            work_tp = list(dict.fromkeys(work_tp))
            error_tp = list(dict.fromkeys(error_tp))
            update_tp = list(dict.fromkeys(update_tp))
            ccm_tp = list(dict.fromkeys(ccm_tp))
            unzip_tp = list(dict.fromkeys(unzip_tp))
            no_update_needed_tp = list(dict.fromkeys(no_update_needed_tp))
            unavailable = list(dict.fromkeys(unavailable))
            no_update_needed_tp = list(dict.fromkeys(no_update_needed_tp))

        # Обновляем атрибуты класса
        self.work_tp = work_tp
        self.error_tp = error_tp
        self.update_tp = update_tp
        self.ccm_tp = ccm_tp
        self.unzip_tp = unzip_tp
        self.no_update_needed_tp = no_update_needed_tp
        self.unavailable = unavailable
        self.result_dict = result_dict

        return result

    def save_status_lists(self, prefix: str = ""):
        """Сохраняет все списки статусов в отдельные файлы"""
        self.logger.debug(f"Сохранение списков статусов с префиксом '{prefix}'")
        config_dir_path = Path(self.config_dir)

        lists_to_save = {
            self.config.get("files.work_tp"): self.work_tp,
            self.config.get("files.error_tp"): self.error_tp,
            self.config.get("files.update_tp"): self.update_tp,
            self.config.get("files.ccm_tp"): self.ccm_tp,
            self.config.get("files.unzip_tp"): self.unzip_tp,
            self.config.get("files.no_update_needed_tp"): self.no_update_needed_tp,
            self.config.get("files.unavailable_tp"): self.unavailable,
        }

        for orig_name, data in lists_to_save.items():
            # берём только имя файла, без каталогов
            base_name = Path(orig_name).name
            target_path = config_dir_path / f"{prefix}{base_name}"
            # удалить старый
            if target_path.exists():
                target_path.unlink()
            # записать новый
            if data:  # список не пуст
                target_path.write_text("\n".join(data), encoding="utf-8")
                self.logger.info("Записан %s (%d строк)", target_path, len(data))
            else:
                self.logger.debug("Список %s пуст – файл не создаётся", base_name)
        self._initialize_data_structures()

    def get_all_nodes(
        self, max_retries: int = MAX_RETRIES_DEFAULT
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Получить состояние всех узлов с Centrum по частям из файла node_list.txt или из БД"""

        # Определяем источник данных
        node_list_path = self.config.get_full_path("files.node_list")
        use_database = not node_list_path.exists()

        if use_database:
            self.logger.info(
                "Файл node_list.txt не найден. Получение данных из базы PostgreSQL"
            )

            # Получаем данные из БД
            db_result = self._get_nodes_from_database()
            if "error" in db_result:
                self.logger.error(
                    f"Ошибка получения данных из БД: {db_result['error']}"
                )
                return db_result

            self.logger.info(f"Получено {len(db_result)} узлов из базы данных")

            # Сохраняем результат и возвращаем
            self.node_result = db_result
            return db_result

        else:
            self.logger.info(
                "Получение состояния всех узлов с Centrum из файла node_list.txt"
            )

            # Существующая логика для работы с файлом
            # Читаем все номера серверов
            with open(node_list_path, "r", encoding="utf-8") as f:
                all_nodes = [line.strip() for line in f if line.strip()]

            if not all_nodes:
                self.logger.warning("Файл node_list.txt пуст")
                return {}

            self.logger.info(f"Найдено {len(all_nodes)} узлов в файле node_list.txt")

            # Разбиваем на группы по 10 серверов
            all_results: Dict[str, Dict[str, Optional[str]]] = {}
            chunk_size = 10

            for i in range(0, len(all_nodes), chunk_size):
                chunk = all_nodes[i : i + chunk_size]
                self.logger.info(
                    f"Обработка группы {i//chunk_size + 1}/{(len(all_nodes)-1)//chunk_size + 1}: {chunk}"
                )

                # Записываем текущую группу в server.txt
                server_list_path = self.config.get_full_path("server_list")
                with open(server_list_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(chunk))

                # Получаем состояние для текущей группы
                for _ in range(max_retries):
                    chunk_result = self.get_nodes_from_file()

                    # Проверяем на ошибки
                    if "error" in chunk_result:
                        self.logger.error(
                            f"Ошибка при получении состояния для группы {chunk}: {chunk_result['error']}"
                        )
                        # Продолжаем с следующей группой, но записываем ошибку
                        for node in chunk:
                            all_results[node] = {
                                "tp": node,
                                "status": "ERROR",
                                "message": f"Ошибка получения состояния: {chunk_result['error'].get('message', 'Unknown error')}",
                                "type": None,
                                "cv": None,
                                "pv": None,
                                "online": None,
                                "ip": None,
                                "ut": None,
                                "local patches": None,
                            }
                    else:
                        # Добавляем результаты текущей группы
                        all_results.update(chunk_result)

                # Пауза 3 секунды между группами
                if i + chunk_size < len(all_nodes):  # Не ждем после последней группы
                    self.logger.info("Ожидание 3 секунды перед следующей группой...")
                    time.sleep(3)

            # Фильтрация по типу (аналогично БД)
            all_results = {
                ip: node_data
                for ip, node_data in all_results.items()
                if node_data.get("type") is not None
            }

            self.logger.info(
                f"Все группы обработаны. Всего получено состояний: {len(all_results)}"
            )

            # Сохраняем объединенный результат
            self.node_result = all_results
            return all_results

    def get_nodes_from_file(self, filename: Optional[Union[Path, str]] = None) -> Dict:
        """Пример метода с использованием конфигурации"""
        if filename is None:
            filename = self.config.get_full_path("files.server_list")

        filepath = Path(self.config_dir) / filename
        self.logger.info(f"Получение состояния узлов из файла {filepath}")
        if self.jar_behavior:
            return self._execute_command(
                ["-ch", self.centrum_host, "-f", str(filepath)],
                MAX_RETRIES_SINGLE,
            )
        else:
            with open(filepath, "r", encoding="utf-8") as f:
                hosts_servers = [line.strip() for line in f if line.strip()]
                for host_server in hosts_servers:
                    args = ["-h", str(host_server), "-s"]
                    result = self._execute_command(args, MAX_RETRIES_SINGLE)
                    result_dict = {**self.result_dict, **result}
                    self.result_dict = result_dict
            return self.result_dict

    def update_servers(
        self,
        version_sv: str = None,
        filename: Union[Path, None] = None,
        no_backup: bool = DEFAULT_NO_BACKUP,
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Запустить обновление серверов список которых перечислены в файле"""
        if version_sv is None:
            version_sv = self.target_version
        if filename is None:
            filename = Path(self.config.get("files.server_list"))
        filepath = self.config_dir / filename

        self.logger.info(
            f"Запуск обновления серверов из файла {filepath} до версии {version_sv}"
        )
        if self.jar_behavior:
            args = ["-ch", self.centrum_host, "-f", str(filepath), "-sv", version_sv]
            if no_backup:
                args.append("-nb")
                self.logger.debug("Используется флаг no_backup (-nb)")
            return self._execute_command(args, MAX_RETRIES_SINGLE)
        else:
            with open(filepath, "r", encoding="utf-8") as f:
                hosts_servers = [line.strip() for line in f if line.strip()]
                for host_server in hosts_servers:
                    args = ["-h", str(host_server), "-s", "-v", version_sv]
                    if no_backup:
                        args.append("-nb")
                        self.logger.debug("Используется флаг no_backup (-nb)")
                    result = self._execute_command(args, MAX_RETRIES_SINGLE)
                    result_dict = {**self.result_dict, **result}
                    self.result_dict = result_dict
            return self.result_dict

    def save_node_result(self, filename: Union[Path, None] = None):
        """Сохранить результат в файл"""
        if filename is None:
            filename = Path(self.config.get("files.node_result"))
        filepath = self.current_dir / filename

        self.logger.info(f"Сохранение результатов в файл {filepath}")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.node_result, f, ensure_ascii=False, indent=2)
        self.logger.info(
            f"Результат сохранен в {filepath} (узлов: {len(self.node_result)})"
        )

    def extract_tp_index(self, tp: str) -> str:
        """Извлекает индекс из tp формата '1.0.индекс.0'"""
        self.logger.debug(f"Извлечение индекса из tp: {tp}")
        parts = tp.split(".")
        if len(parts) >= 3:
            if parts[3] == "0":
                result = parts[2]
            else:
                result = f"{parts[2]}.{parts[3]}"
            self.logger.debug(f"Извлеченный индекс: {result}")
            return result
        self.logger.debug(
            f"Не удалось извлечь индекс, возвращаем исходное значение: {tp}"
        )
        return tp

    def get_retail_servers_to_update(self, all_nodes: Dict) -> List[Dict]:
        """Получает список серверов RETAIL, которые нужно обновить"""
        self.logger.info("Поиск серверов RETAIL для обновления")
        servers_to_update = []

        for ip, node_data in all_nodes.items():
            node_type = node_data.get("type")
            current_version = node_data.get("cv")
            tp = node_data.get("tp", "")
            cur_ver = tuple(map(int, current_version.split(".")))
            need_ver = tuple(map(int, self.target_version.split(".")))

            self.logger.debug(
                f"Проверка узла {ip} (type={node_type}, version={current_version}, tp={tp})"
            )

            if (
                node_type == "RETAIL"
                and cur_ver < need_ver
                and ip not in self.updated_servers
            ):
                tp_index = self.extract_tp_index(tp)
                server_info = {
                    "ip": ip,
                    "tp": tp,
                    "current_version": current_version,
                    "tp_index": tp_index,
                }
                self.logger.debug(f"Добавление сервера для обновления: {server_info}")
                servers_to_update.append(server_info)

        self.logger.info(f"Найдено серверов для обновления: {len(servers_to_update)}")
        return servers_to_update

    def create_server_file(
        self, servers: List[Dict], filename: Union[Path, None] = None
    ) -> None:
        """Создает файл server.txt с индексами серверов"""
        if filename is None:
            filename = Path(self.config.get("files.server_list"))
        filepath = self.config_dir / filename

        self.logger.info(f"Создание файла {filepath} с {len(servers)} серверами")
        self.logger.debug(f"Список данных {servers} из которых собирается {filepath}")
        if self.jar_behavior:
            self.logger.debug(f"Создание файла {filepath} для метода с Centrum")
            with open(filepath, "w", encoding="utf-8") as f:
                for server in servers:
                    f.write(f"{server['tp_index']}\n")
                    self.logger.debug(f"Запись сервера в файл: {server['tp_index']}")
        else:
            self.logger.debug(f"Создание файла {filepath} для метода с Retail")
            with open(filepath, "w", encoding="utf-8") as f:
                for server in servers:
                    f.write(f"{server['ip']}\n")
                    self.logger.debug(f"Запись сервера в файл: {server['ip']}")
        self.logger.info(f"Файл {filename} успешно создан")

    def check_file_exists(self, filename: str) -> bool:
        """Проверяет существование файла"""
        config_dir_path = Path(self.config_dir)
        filepath = config_dir_path / filename
        exists = filepath.exists() and filepath.stat().st_size > 0
        self.logger.debug(f"Проверка файла {filename}: exists={exists}")
        return exists

    def read_file_lines(self, filename: str) -> List[str]:
        """Читает строки из файла, игнорируя строки с индексом '0'"""
        config_dir_path = Path(self.config_dir)
        filepath = config_dir_path / filename
        if not filepath.exists():
            self.logger.warning(f"Файл {filename} не существует")
            return []

        self.logger.debug(f"Чтение строк из файла {filename} (игнорируя индекс '0')")
        valid_lines = []

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue  # Пропускаем пустые строки

                # Разбиваем строку по первому "-" для проверки индекса
                parts = line.split("-", 1)
                if parts[0] == "0":
                    self.logger.debug(f"Игнорируем строку с индексом '0': {line}")
                    continue

                valid_lines.append(line)

        self.logger.debug(f"Прочитано строк (без '0'): {len(valid_lines)}")
        return valid_lines

    def command_with_plink(self, servers: List[str], restart_file: str) -> bool:
        """Перезапускает службу на серверах используя PLINK"""
        self.logger.info(f"Начало обработки {len(servers)} серверов")
        try:
            # Проверяем наличие необходимых файлов
            command_filepath = Path(restart_file)
            self.logger.debug(
                f"Проверка существования файла команд: {command_filepath}"
            )

            if not command_filepath.exists():
                self.logger.error(f"Файл команд {restart_file} не найден")
                return False
            else:
                self.logger.debug("Файл команд найден")

            self.logger.debug(f"Проверка существования plink: {self.plink_path}")
            if not self.plink_path.exists():
                self.logger.error("plink.exe не найден")
                return False
            else:
                self.logger.debug("plink.exe найден")

            # Обрабатываем каждый сервер
            failed_servers = []
            for server_info in servers:
                self.logger.info(f"Обработка сервера: {server_info}")

                # Извлекаем IP из формата "индекс-тип-ip-версия"
                parts = server_info.split("-")
                if len(parts) < 3:
                    self.logger.error(f"Неверный формат строки сервера: {server_info}")
                    failed_servers.append(server_info)
                    continue

                server_ip = parts[2]
                server_index = parts[0]
                self.logger.debug(
                    f"Извлеченные данные: ip={server_ip}, index={server_index}"
                )

                # Проверяем доступность через ping

                self.logger.debug(f"Проверка доступности {server_ip} через ping")
                if not self._check_ping(server_ip):
                    self.logger.warning(
                        f"Сервер {server_ip} (индекс {server_index}) недоступен по ping"
                    )
                    failed_servers.append(server_info)
                    continue
                else:
                    self.logger.debug("Сервер доступен по ping")

                # Выполняем команды через plink
                cmd = [
                    str(self.plink_path),
                    "-ssh",
                    f"{self.ssh_user}@{server_ip}",
                    "-pw",
                    self.password,
                    "-batch",
                    "-no-trivial-auth",
                    "-m",
                    str(command_filepath),
                ]
                self.logger.debug(f"Команда для выполнения: {' '.join(cmd)}")

                try:
                    self.logger.info(f"Запуск команд на сервере {server_ip}")

                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=self.config.get("plink_timeout"),
                        encoding="cp1251",
                    )

                    if result.returncode == 0:
                        self.logger.info(f"Команды успешно выполнены на {server_ip}")
                        if result.stdout:
                            self.logger.debug(f"Вывод команды:\n{result.stdout}")
                    else:
                        self.logger.error(
                            f"Ошибка выполнения на {server_ip}:\nКод возврата: {result.returncode}\nОшибка: {result.stderr}"
                        )
                        failed_servers.append(server_info)

                except subprocess.TimeoutExpired:
                    self.logger.error(
                        f"Таймаут выполнения команд на {server_ip} (превышено {self.config.get("plink_timeout")} сек)"
                    )
                    failed_servers.append(server_info)
                except Exception as e:
                    self.logger.error(
                        f"Неожиданная ошибка при работе с {server_ip}: {str(e)}",
                        exc_info=True,
                    )
                    failed_servers.append(server_info)

                # Пауза между серверами
                self.logger.debug("Пауза 2 секунды перед следующим сервером")
                time.sleep(2)

            # Итоговая проверка
            if failed_servers:
                self.logger.error(
                    f"Не удалось обработать {len(failed_servers)} серверов: {failed_servers}"
                )
                return False
            else:
                self.logger.warning("Все серверы успешно обработаны")
                return True

        except Exception as e:
            self.logger.error(
                f"Критическая ошибка в command_with_plink: {str(e)}",
                exc_info=True,
            )
            return False

    def _check_ping(self, host: str) -> bool:
        """Проверка доступности хоста через ping"""
        self.logger.debug(f"Выполнение ping для {host}")
        try:
            result = subprocess.run(
                ["ping", "-n", "4", "-w", str(self.config.get("ping_timeout")), host],
                capture_output=True,
                text=True,
            )
            if "TTL=" in result.stdout:
                self.logger.debug(f"Ping успешен для {host}")
                return True
            else:
                self.logger.debug(f"Ping не удался для {host}")
                return False
        except Exception as e:
            self.logger.error(f"Ошибка при выполнении ping для {host}: {str(e)}")
            return False

    def compare_servers_and_versions(
        self, work_servers: List[str], original_servers: List[Dict]
    ) -> Tuple[bool, List[str]]:
        """Сравнивает серверы из work_tp с исходными и проверяет версии"""
        self.logger.info("Сравнение серверов и версий")

        # 3. Игнорируем строки с индексом 0
        original_indices = {
            server["tp_index"]
            for server in original_servers
            # if server["tp_index"] != "0"
        }

        work_indices = set()
        incorrect_versions = []

        for server_info in work_servers:
            parts = server_info.split("-")
            if len(parts) >= 1:
                tp_index = parts[0]
                # Пропускаем серверы с индексом 0
                if tp_index == "0":
                    self.logger.debug(f"Игнорируем сервер с индексом 0: {server_info}")
                    continue

                work_indices.add(tp_index)
                self.logger.debug(f"Индекс из work_tp: {tp_index}")

                # Проверяем версию, если есть информация о версии в строке
                if len(parts) >= 4:
                    server_version = parts[3]
                    if server_version != self.target_version:
                        self.logger.warning(f"Неверная версия у сервера {server_info}")
                        incorrect_versions.append(server_info)

        self.logger.debug(f"Оригинальные индексы: {original_indices}")
        self.logger.debug(f"Индексы из work_tp (без 0): {work_indices}")

        if original_indices != work_indices:
            self.logger.error(
                f"Несоответствие серверов: ожидалось {original_indices}, получено {work_indices}"
            )
            return False, incorrect_versions

        if incorrect_versions:
            self.logger.error(f"Серверы с неправильными версиями: {incorrect_versions}")
            return False, incorrect_versions

        self.logger.warning(
            "Все серверы соответствуют ожидаемым и имеют правильные версии"
        )
        return True, []

    def _perform_pre_work(self):
        """Выполняет предварительные работы с сервером перед обновлением"""
        self.logger.info("Выполнение предварительных работ с сервером")
        work_servers = self.read_file_lines(self.config.get("files.work_tp"))
        if work_servers:
            self.logger.warning(f"Предварительные работы на серверах: {work_servers}")
            if not self.command_with_plink(
                work_servers, self.config.get("files.pre_update_commands")
            ):
                self.logger.error("Ошибка выполнения предварительных работ")
                return False
        self.logger.warning(f"Ожидание {self.config.get("pre_update_timeout")} секунд...")
        time.sleep(self.config.get("pre_update_timeout"))
        return True

    def _perform_post_work(self):
        """Выполняет дополнительные работы с сервером после обновления"""
        self.logger.info("Выполнение дополнительных работ с сервером после обновления")
        work_servers = self.read_file_lines(self.config.get("files.work_tp"))
        if work_servers:
            self.logger.warning(f"Дополнительные работы на серверах: {work_servers}")
            if not self.command_with_plink(
                work_servers, self.config.get("files.post_update_commands")
            ):
                self.logger.error("Ошибка выполнения дополнительных работ")
                return False
        self.logger.warning(f"Ожидание {self.config.get("post_update_timeout")} секунд...")
        time.sleep(self.config.get("post_update_timeout"))
        return True

    def _monitor_update_status(self, current_part_server: List[Dict]) -> bool:
        """Мониторит статус обновления для текущей итерации"""
        while True:
            self.logger.warning(
                f"Ожидание {self.config.get("status_check_interval") // 60} минут перед проверкой..."
            )
            time.sleep(self.config.get("status_check_interval"))

            # Получаем статус только для текущей итерации
            self.get_nodes_from_file()
            self.save_status_lists(prefix=self.config.get("status_prefix"))

            # Проверяем ошибки
            if self._check_errors():
                return False

            # Проверяем статусы обновления
            status_check = self._check_update_statuses(current_part_server)
            if status_check is not None:  # None означает продолжение ожидания
                return status_check

    def _check_errors(self) -> bool:
        """Проверяет наличие ошибок обновления"""
        if self.check_file_exists(
            self.config.get("status_prefix") + self.config.get("files.error_tp")
        ):
            error_servers = self.read_file_lines(
                self.config.get("status_prefix") + self.config.get("files.error_tp")
            )
            self.logger.error(f"Ошибки обновления на серверах: {error_servers}")
            return True
        return False

    def _check_update_statuses(self, current_part_server: List[Dict]) -> Optional[bool]:
        """Проверяет различные статусы обновления"""
        # Проверяем необходимость перезапуска служб
        if self._handle_service_restart(
            self.config.get("files.ccm_tp"),
            self.config.get("files.ccm_restart_commands"),
        ):
            return None
        if self._handle_service_restart(
            self.config.get("files.unzip_tp"),
            self.config.get("files.unzip_restart_commands"),
        ):
            return None

        # Обработка статуса update_tp (обновление в процессе)
        if self.check_file_exists(
            self.config.get("status_prefix") + self.config.get("files.update_tp")
        ):
            current_update_servers = set(
                self.read_file_lines(
                    self.config.get("status_prefix")
                    + self.config.get("files.update_tp")
                )
            )
            if not hasattr(self, "_update_servers_prev"):
                # Первое обнаружение - сохраняем и продолжаем ожидание
                self._update_servers_prev = current_update_servers
                self._update_servers_counter = 1
                self.logger.debug(
                    f"Обновление в процессе для серверов: {current_update_servers}"
                )
                return None
            elif current_update_servers == self._update_servers_prev:
                # Те же серверы в статусе update_tp
                self._update_servers_counter += 1
                if (
                    self._update_servers_counter >= 2
                ):  # Допускаем 1 повтора (2 проверки)
                    self.logger.error(
                        f"Серверы слишком долго в статусе обновления: {current_update_servers} (попытка {self._update_servers_counter})"
                    )
                    return False  # Считаем это ошибкой
                self.logger.warning(
                    f"Обновление затянулось для серверов: {current_update_servers} (попытка {self._update_servers_counter})"
                )
                return None
            else:
                # Изменился список серверов в update_tp - сбрасываем счетчик
                self._update_servers_prev = current_update_servers
                self._update_servers_counter = 1
                self.logger.debug(
                    f"Прогресс обновления: новые серверы в процессе - {current_update_servers}"
                )
                return None

        # Обработка статуса unavailable (недоступные серверы)
        if self.check_file_exists(
            self.config.get("status_prefix") + self.config.get("files.unavailable_tp")
        ):
            current_unavailable_servers = set(
                self.read_file_lines(
                    self.config.get("status_prefix")
                    + self.config.get("files.unavailable_tp")
                )
            )

            if not hasattr(self, "_unavailable_servers_prev"):
                # Первое обнаружение - сохраняем и продолжаем ожидание
                self._unavailable_servers_prev = current_unavailable_servers
                self._unavailable_servers_counter = 1
                self.logger.warning(
                    f"Обнаружены недоступные серверы: {current_unavailable_servers}"
                )
                return None
            elif current_unavailable_servers == self._unavailable_servers_prev:
                # Те же серверы остаются недоступными
                self._unavailable_servers_counter += 1
                if self._unavailable_servers_counter >= 2:
                    self.logger.error(
                        f"Серверы остаются недоступными: {current_unavailable_servers} (попытка {self._unavailable_servers_counter})"
                    )
                    return False
            else:
                # Изменился список недоступных серверов - сбрасываем счетчик
                self._unavailable_servers_prev = current_unavailable_servers
                self._unavailable_servers_counter = 1
                self.logger.warning(
                    f"Изменение списка недоступных серверов: {current_unavailable_servers}"
                )
                return None

        # Проверяем завершение обновления
        if self.check_file_exists(
            self.config.get("status_prefix") + self.config.get("files.work_tp")
        ):
            work_servers = self.read_file_lines(
                self.config.get("status_prefix") + self.config.get("files.work_tp")
            )
            servers_match, incorrect_versions = self.compare_servers_and_versions(
                work_servers, current_part_server
            )
            if servers_match and not incorrect_versions:
                # Сбрасываем счетчики при успешном завершении
                if hasattr(self, "_update_servers_prev"):
                    del self._update_servers_prev
                    del self._update_servers_counter
                if hasattr(self, "_unavailable_servers_prev"):
                    del self._unavailable_servers_prev
                    del self._unavailable_servers_counter
                return True

        return None

    def _handle_service_restart(self, status_file: str, commands_file: str) -> bool:
        """Обрабатывает перезапуск служб при необходимости"""
        if self.check_file_exists(self.config.get("status_prefix") + status_file):
            servers = self.read_file_lines(
                self.config.get("status_prefix") + status_file
            )
            self.logger.warning(f"Перезапуск служб на серверах: {servers}")
            if not self.command_with_plink(servers, commands_file):
                self.logger.error(f"Ошибка перезапуска служб ({status_file})")
                return False
            return True
        return False

    def update_servers_part_server(self) -> bool:
        """Основной метод обновления серверов по частям с сохранением состояния"""
        self.logger.warning("Начало пошагового обновления серверов")

        # Получаем все узлы один раз в начале
        self.logger.debug("Первоначальное получение списка всех узлов")
        initial_nodes = self.get_all_nodes(max_retries=MAX_RETRIES_DEFAULT)
        if "error" in initial_nodes:
            self.logger.error(f"Ошибка получения узлов: {initial_nodes['error']}")
            return False

        # Инициализируем node_result с исходными данными
        self.node_result = initial_nodes
        self.save_node_result()

        # Создаем копию для локальной работы, чтобы не перезаписывать node_result
        current_nodes_state = initial_nodes.copy()

        while True:
            self._initialize_data_structures()
            self.save_status_lists()
            self.save_status_lists(prefix=self.config.get("status_prefix"))
            if (
                self.config.get("max_iterations")
                and self.current_iteration >= self.max_iterations
            ):
                self.logger.warning(
                    f"Достигнуто максимальное количество итераций ({self.max_iterations})"
                )
                return True

            self.logger.warning(f"Итерация {self.current_iteration + 1}")

            # Используем актуальное состояние узлов
            servers_to_update = self.get_retail_servers_to_update(current_nodes_state)

            if not servers_to_update:
                self.logger.warning("Все серверы RETAIL уже обновлены до целевой версии")
                return True

            current_part_server = servers_to_update[: self.part_server_size]
            self.current_iteration += 1

            self.logger.warning(
                f"Обработка итерации: {[s['tp_index'] for s in current_part_server]}"
            )

            # Создаем временный файл для текущей итерации
            self.create_server_file(current_part_server)

            # Получаем статус только для текущей итерации (не перезаписываем основной словарь)
            self.logger.debug("Получение статуса серверов перед обновлением")
            part_server_nodes = self.get_nodes_from_file()
            self.node_result = part_server_nodes
            self.save_status_lists()

            # Предварительные работы(например копирование файлов обновления)
            if self.config.get("pre_update_work"):
                if not self._perform_pre_work():
                    return False

            # Запускаем обновление
            self.logger.warning(f"Запуск обновления до версии {self.target_version}")
            update_result = self.update_servers(version_sv=self.target_version)
            if "error" in update_result:
                self.logger.error(f"Ошибка обновления: {update_result['error']}")
                return False

            # Мониторим статус обновления
            if not self._monitor_update_status(current_part_server):
                return False

            # Обновляем состояние только для успешно обновленных узлов
            for server in current_part_server:
                ip = server["ip"]
                if ip in current_nodes_state:
                    current_nodes_state[ip]["cv"] = self.target_version
                    self.updated_servers.add(ip)
                    self.logger.debug(
                        f"Обновлена версия для {ip} -> {self.target_version}"
                    )

            # Синхронизируем с основным словарем и сохраняем
            self.node_result.update(current_nodes_state)
            self.save_node_result()

            # Работы после обновления(например очистка файлов обновления)
            if self.config.get("post_update_work"):
                if not self._perform_post_work():
                    return False

            # Удаляем временный файл с серверами текущей итерации
            server_file = Path(self.config_dir) / self.config.get("files.server_list")
            if server_file.exists():
                server_file.unlink()
                self.logger.debug(f"Удален временный файл {server_file}")

            # Продолжаем цикл для следующего итерации
        # Нужно добавить блок уборки мусора


if __name__ == "__main__":
    config = ConfigManager()
    updater = UnifiedServerUpdater(config)
