from pathlib import Path


def split_ips_large_file(input_file, even_file, odd_file):
    """
    Разделяет IP-адреса на четные и нечетные по последнему октету
    """
    # Получаем текущую директорию
    current_dir = Path.cwd()

    # Формируем полные пути к файлам
    input_path = current_dir / input_file
    even_path = current_dir / even_file
    odd_path = current_dir / odd_file

    # Обрабатываем файлы
    with input_path.open("r") as infile, even_path.open("w") as even_out, odd_path.open(
        "w"
    ) as odd_out:

        for line in infile:
            ip = line.strip()
            if ip:
                try:
                    last_octet = int(ip.split(".")[-1])
                    if last_octet % 2 == 0:
                        even_out.write(ip + "\n")
                    else:
                        odd_out.write(ip + "\n")
                except:
                    pass  # Просто пропускаем некорректные строки


# Пример использования
split_ips_large_file("ip_list.txt", "even_ips.txt", "odd_ips.txt")
