import subprocess
from pathlib import Path
import logging
from typing import Dict, List, Optional #, Union, Tuple
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class ConfiguratorTool:
    def __init__(
        self,
        centrum_host: str,
        config_dir: str = ".",
        jar_name: str = "ConfiguratorCmdClient-1.5.1.jar",
    ):
        self.centrum_host = centrum_host
        self.config_dir = Path(config_dir)
        self.jar_path = self.config_dir / jar_name
        self.last_result: Dict[str, Dict[str, Optional[str]]] = {}

        if not self.jar_path.exists():
            raise FileNotFoundError(f"JAR файл не найден: {self.jar_path}")

    def _execute_command(
        self, args: List[str], max_retries: int = 1
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Выполняет команду с повторами для недоступных узлов"""
        result_dict: Dict[str, Dict[str, Optional[str]]] = {}
        attempt = 0

        while attempt < max_retries:
            attempt += 1
            if max_retries > 1:
                logging.info(f"Попытка {attempt} из {max_retries}")

            try:
                result = subprocess.run(
                    ["java", "-jar", str(self.jar_path)] + args,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='cp1251',
                    errors='replace'
                )

                if not result.stdout:
                    logging.warning("Пустой вывод от команды")
                    continue

                # Обработка успешного ответа
                if "успешно запланировано" in result.stdout:
                    node_id = self._extract_node_id(result.stdout)
                    if node_id:
                        result_dict[node_id] = {
                            "status": "SUCCESS",
                            "message": result.stdout.strip()
                        }
                        self.last_result = result_dict
                        return result_dict
                    else:
                        return {
                            "status": "SUCCESS",
                            "message": result.stdout.strip()
                        } # type: ignore

                current_result = self._parse_output(result.stdout)
                result_dict.update(current_result)

                if max_retries <= 1:
                    break

                if attempt < max_retries:
                    time.sleep(2)

            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if e.stderr else str(e)
                logging.error(f"Ошибка выполнения команды: {error_msg}")
                if attempt == max_retries or max_retries <= 1:
                    return {"error": {"message": error_msg}}
                continue
            except Exception as e:
                logging.error(f"Неожиданная ошибка: {str(e)}")
                if attempt == max_retries or max_retries <= 1:
                    return {"error": {"message": str(e)}}
                continue

        self.last_result = result_dict
        return result_dict

    def _extract_node_id(self, output: str) -> Optional[str]:
        """Извлекает ID узла из сообщения об успешном обновлении"""
        for line in output.splitlines():
            if "успешно запланировано" in line:
                parts = line.split()
                for part in parts:
                    if part.replace(".", "").isdigit():
                        return part
        return None

    def _parse_output(self, output: str) -> Dict[str, Dict[str, Optional[str]]]:
        """Парсит вывод команды"""
        if not output:
            return {}

        devices_dict: Dict[str, Dict[str, Optional[str]]] = {}

        try:
            for line in output.splitlines():
                line = line.strip()
                if not line or line.startswith(("Current client version:", "-")):
                    continue

                device: Dict[str, Optional[str]] = {}
                device_key = None
                
                for pair in line.split(";"):
                    pair = pair.strip()
                    if "=" in pair:
                        key, value = pair.split("=", 1)
                        key = key.strip()
                        value = value.strip() if value.strip().lower() != "null" else None
                        device[key] = value
                        
                        if key == "ip" and value:
                            device_key = value
                        elif key == "tp" and value and not device_key:
                            device_key = value

                if device and device_key:
                    devices_dict[device_key] = device

        except Exception as e:
            logging.error(f"Ошибка при парсинге вывода: {str(e)}")
            return {}

        return devices_dict

    def get_all_nodes(self, max_retries: int = 3) -> Dict[str, Dict[str, Optional[str]]]:
        """Получить информацию обо всех узлах"""
        return self._execute_command(["-ch", self.centrum_host, "--all"], max_retries)

    def get_nodes_from_file(
        self, filename: str = "server.txt"
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Получить узлы из файла"""
        filepath = self.config_dir / filename
        return self._execute_command(["-ch", self.centrum_host, "-f", str(filepath)], 1)

    def update_servers(
        self,
        version: str,
        filename: str = "server.txt",
        no_backup: bool = True,
        timeout: int = 20
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Обновить серверы"""
        filepath = self.config_dir / filename
        args = [
            "-ch", self.centrum_host,
            "-f", str(filepath),
            "-t", str(timeout),
            "-sv", version
        ]
        if no_backup:
            args.append("-nb")
        return self._execute_command(args, 1)

    def update_cash_devices(
        self,
        cash_type: str,
        version: str,
        filename: str = "server.txt",
        no_backup: bool = True,
        auto_restart: bool = True,
        timeout: int = 20
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Обновить кассовые устройства"""
        filepath = self.config_dir / filename
        args = [
            "-ch", self.centrum_host,
            "-f", str(filepath),
            "-t", str(timeout),
            "-sv", version,
            "-cv", f"{cash_type}:{version}",
        ]
        if no_backup:
            args.append("-nb")
        if auto_restart:
            args.append("-ar")
        return self._execute_command(args, 1)

    def save_last_result(self, filename: str = "last_result.json"):
        """Сохранить результат в файл"""
        import json
        filepath = self.config_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.last_result, f, ensure_ascii=False, indent=2)
        logging.info(f"Результат сохранен в {filepath}")


if __name__ == "__main__":
    try:
        configurator = ConfiguratorTool(
            centrum_host="10.9.30.101", 
            config_dir="C:\\Users\\iakushin.n\\Documents\\GitHub\\Python\\updaterJar"
        )

        # Тестирование обновления серверов
        # print("Обновление серверов:")
        # update_result = configurator.update_servers(
        #     version="10.4.15.2",
        #     filename="server.txt",
        #     timeout=20
        # )
        # print(update_result)

        # get_nodes_from_file = configurator.get_nodes_from_file()
        # print("Узлы из файла:")
        # for key, data in get_nodes_from_file.items():
        #     print(f"{key}: {data}")

        # Сохраняем результат
        configurator.save_last_result()

    except Exception as e:
        logging.error(f"Ошибка в основном потоке: {str(e)}")