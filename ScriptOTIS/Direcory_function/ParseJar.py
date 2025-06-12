import subprocess
from typing import Dict, List, Optional, Union
import logging


def run_configurator(
    key1: str,
    key2: str,
    jar_path: str = "E:\\Distributives\\mook\\ConfiguratorCmdClient-1.5.1.jar",
) -> Dict[str, Union[int, str]]:
    """
    Запускает ConfiguratorCmdClient и возвращает структурированные результаты

    Args:
        key1: значение для параметра -ch (обычно IP-адрес)
        key2: значение для параметра -f (путь к файлу)
        jar_path: путь к JAR-файлу утилиты

    Returns:
        Словарь с результатами выполнения:
        {
            'returncode': int,
            'stdout': str,
            'stderr': str,
            'success': bool
        }

    Raises:
        FileNotFoundError: если JAR-файл не найден
        subprocess.SubprocessError: при ошибках выполнения
    """
    try:
        result = subprocess.run(
            ["java", "-jar", jar_path, "-ch", key1, "-f", key2],
            check=False,  # Не генерировать исключение при ненулевом returncode
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        return {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "success": result.returncode == 0,
        }

    except FileNotFoundError as e:
        logging.error(f"JAR-файл не найден: {jar_path}")
        raise
    except subprocess.SubprocessError as e:
        logging.error(f"Ошибка выполнения команды: {e}")
        raise


def parse_configurator_output(output: str) -> List[Dict[str, str]]:
    """
    Парсит вывод ConfiguratorCmdClient в список словарей

    Args:
        output: сырой вывод из stdout

    Returns:
        Список словарей с параметрами устройств
    """
    devices = []
    for line in output.strip().split("\n"):
        if not line:
            continue
        device = {}
        for pair in line.split(";"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                device[key.strip()] = value.strip() if value.strip() != "null" else None
        devices.append(device)
    return devices


# Пример использования
if __name__ == "__main__":
    try:
        # Запуск конфигуратора
        config_result = run_configurator(
            key1="10.100.105.9", key2="E:\\Distributives\\mook\\server.txt"
        )

        if config_result["success"]:
            # Парсинг результатов
            devices = parse_configurator_output(config_result["stdout"])  # type: ignore
            print(f"Получены данные о {len(devices)} устройствах:")
            for device in devices:
                print(
                    f"Устройство {device.get('ip')} (тип: {device.get('type')}) (версия: {device.get('cv')}) (Состояние: {device.get('status')})"
                )
        else:
            print(f"Ошибка выполнения (код {config_result['returncode']}):")
            print(config_result["stderr"])

    except Exception as e:
        print(f"Критическая ошибка: {str(e)}")
