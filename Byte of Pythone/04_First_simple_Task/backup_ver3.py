#! /usr/bin/env python3

import os
import time

# 1. Файлы и каталоги, которые необходимо скопировать, собираются в список.
if os.name == 'nt':
    source = ['"C:\\Users\\Coldfear\\Documents\\SQUARE ENIX"', 'C:\\Users\\Coldfear\\Documents\\py']
elif os.name == 'posix':
    source = ['"/home/maatmasher/Downloads/Telegram Desktop/"', '/home/maatmasher/Documents/py/']
else:
    print('Неизвестная  OS для скрипта, остановка')
    exit
# Заметьте, что для имён, содержащих пробелы, необходимо использовать
# двойные кавычки внутри строки.
# 2. Резервные копии должны храниться в основном каталоге резерва.
if os.name == 'nt':
    target_dir = 'D:\\PythonScript' 
elif os.name == 'posix':
    target_dir = '/media/maatmasher/Data/PythonScript/'
else:
    print('Неизвестная  OS для скрипта, остановка')
    exit
# 3. Файлы помещаются в zip-архив.
# 4. Текущая дата служит именем подкаталога в основном каталоге
today = target_dir + os.sep + time.strftime('%Y%m%d')
# Текущее время служит именем zip-архива
now = time.strftime('%H%M%S')
# Запрашиваем комментарий пользователя для имени файла
comment = input('Введите комментарий --> ')
if len(comment) == 0: # проверяем, введён ли комментарий
    target = today + os.sep + now + '.zip'
else:
    target = today + os.sep + now + '_' +\
comment.replace(' ', '_') + '.zip'
# Создаём каталог, если его ещё нет
if not os.path.exists(today):
    os.mkdir(today) # создание каталога
print('Каталог успешно создан', today)
# 5. Используем команду "zip" для помещения файлов в zip-архив
zip_command = "zip -qr {0} {1}".format(target, ' '.join(source))
# Запускаем создание резервной копии
if os.system(zip_command) == 0:
    print('Резервная копия успешно создана в', target)
else:
    print('Создание резервной копии НЕ УДАЛОСЬ')