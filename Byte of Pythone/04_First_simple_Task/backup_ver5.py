#!/usr/bin/env python3

import os
import time
import zipfile

# 1. Определяем файлы для копирования в зависимости от ОС
if os.name == 'nt':
    source = [
        r"C:\Users\Coldfear\Documents\SQUARE ENIX", # символ r перед строкой означает "сырая строка" (raw string), отключает экранирование, и \ воспринимается буквально
        r"C:\Users\Coldfear\Documents\py" #В конце сырой строки нельзя ставить неэкранированный \
    ]
elif os.name == 'posix':
    source = [
        "/home/maatmasher/Downloads/Telegram Desktop/",
        "/home/maatmasher/Documents/py/"
    ]
else:
    print('Неизвестная OS для скрипта, остановка')
    exit(1)

# 2. Каталог для резервных копий
if os.name == 'nt':
    target_dir = r'D:\PythonScript'
elif os.name == 'posix':
    target_dir = '/media/maatmasher/Data/PythonScript/'

# 3. Создаем путь для архива с датой и временем
today = os.path.join(target_dir, time.strftime('%Y%m%d'))
now = time.strftime('%H%M%S')

# 4. Запрашиваем комментарий для имени файла
comment = input('Введите комментарий --> ').strip() # Метод .strip() у строки удаляет пробелы и переносы строк с начала и конца строки.
if comment:
    zip_name = f"{now}_{comment.replace(' ', '_')}.zip" # В Python символ f перед кавычками означает f-строку (форматированную строку, от англ. formatted string). Это позволяет встраивать выражения и переменные прямо в строку с помощью { }
else:
    zip_name = f"{now}.zip"  # Cимвол f перед кавычками короче и читаемее, чем конкатенация (+) или .format(). (требуется Python 3.6+)

target = os.path.join(today, zip_name)

# 5. Создаем каталог, если его нет
os.makedirs(today, exist_ok=True) #Может создавать вложенные директории за один вызов, exist_ok=True если папка уже существует → не будет ошибки(папка естественно не будет создана заного)
print(f'Каталог успешно создан: {today}')

# 6. Создаем ZIP-архив с помощью zipfile
try:
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as zipf:
# ZipFile(target, 'w', ...) — создаёт новый ZIP-архив:
# target — путь к архиву 
# 'w' — режим записи (перезаписывает архив, если он уже существует).
#zipfile.ZIP_DEFLATED — сжатие данных.
        for src in source:
# source — список файлов/папок для архивации.
# Для каждого элемента (src) проверяется, это файл или папка.
            if os.path.isdir(src): # если это папка
                for root, dirs, files in os.walk(src):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, start=os.path.dirname(src))
                        zipf.write(file_path, arcname)
# os.walk(src) — рекурсивно обходит все файлы и подпапки в src.
# root — текущая папка (например, /home/user/Documents/project).
# files — список файлов в этой папке.
# file_path — полный путь к файлу (например, /home/user/Documents/project/readme.md).
# arcname — относительный путь файла внутри архива:
# os.path.dirname(src) — родительская папка исходной папки (чтобы не включать её в архив).
# os.path.relpath(...) — преобразует file_path в путь относительно src.
# zipf.write(file_path, arcname) — добавляет файл в архив с указанным именем.
            else:  # если это файл, а не папка
                zipf.write(src, os.path.basename(src))
# os.path.basename(src) — оставляет только имя файла (без пути).

    print(f'Резервная копия успешно создана: {target}')
except Exception as e:
    print(f'Ошибка при создании резервной копии: {e}')