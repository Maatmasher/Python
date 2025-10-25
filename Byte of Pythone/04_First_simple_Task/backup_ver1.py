#!/usr/bin/env python3

import os
import time
# 1. Файлы и каталоги, которые необходимо скопировать, собираются в список.
if os.name == 'nt':
    source = ['C:\\Users\\Coldfear\\Documents\\"SQUARE ENIX"', 'C:\\Users\\Coldfear\\Documents\\py']
elif os.name == 'posix':
    source = ['"/home/maatmasher/Downloads/Telegram Desktop/"', '/home/maatmasher/Documents/py/']
else:
    print('Неизвестная  OS для скрипта, остановка')
    exit
# Заметьте, что для имён, содержащих пробелы, необходимо использовать
# двойные кавычки внутри строки.

# 2. Резервные копии должны храниться в основном каталоге резерва.
# Подставьте тот путь, который вы будете использовать.
if os.name == 'nt':
    target_dir = 'D:\\PythonScript' 
elif os.name == 'posix':
    target_dir = '/media/maatmasher/Data/PythonScript/'
else:
    print('Неизвестная  OS для скрипта, остановка')
    exit

# 3. Файлы помещаются в zip-архив.
# 4. Именем для zip-архива служит текущая дата и время.
target = target_dir + os.sep + time.strftime('%Y%m%d%H%M%S') + '.zip'
# 5. Используем команду "zip" для помещения файлов в zip-архив
zip_command = "zip -qr {0} {1}".format(target, ' '.join(source)) 
print(zip_command)
# Запускаем создание резервной копии
if os.system(zip_command) == 0:
    print('Резервная копия успешно создана в', target)
else:
    print('Создание резервной копии НЕ УДАЛОСЬ')