import subprocess
from pprint import pprint


def parse_configurator_output(output):
    """Парсит вывод ConfiguratorCmdClient в список словарей"""
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


def run_configurator(
    key1, key2, jar_path="E:\\Distributives\\mook\\ConfiguratorCmdClient-1.5.1.jar"
):
    result = subprocess.run(
        ["java", "-jar", jar_path, "-ch", key1, "-f", key2],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


result = subprocess.run(
    [
        "java",
        "-jar",
        "E:\\Distributives\\mook\\ConfiguratorCmdClient-1.5.1.jar",
        "-ch",
        "10.100.105.9",
        "-f",
        "E:\\Distributives\\mook\\server.txt",
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding="utf-8",  # Явное указание кодировки
    errors="replace",  # Обработка ошибок декодирования
)

if result.returncode == 0:
    devices = parse_configurator_output(result.stdout)
    print(f"Успешно получены данные о {len(devices)} устройствах:")
    pprint(devices)
else:
    print(f"Ошибка выполнения (код {result.returncode}):")
    print(result.stderr)


# ===============================================================


# Использование
run_configurator("abc", "qwerty")
