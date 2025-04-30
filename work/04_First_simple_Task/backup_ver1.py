#!/usr/bin/env python3

import os
import time
# 1. Файлы и каталоги, которые необходимо скопировать, собираются в список.
source = ['C:\\Users\Coldfear\Documents\\"SQUARE ENIX"', 'C:\\Users\Coldfear\Documents\py']
# Заметьте, что для имён, содержащих пробелы, необходимо использовать
# двойные кавычки внутри строки.
# 2. Резервные копии должны храниться в основном каталоге резерва.
target_dir = 'D:\\PythonScript' # Подставьте тот путь, который вы будете использовать.
# 3. Файлы помещаются в zip-архив.
# 4. Именем для zip-архива служит текущая дата и время.
target = target_dir + os.sep + time.strftime('%Y%m%d%H%M%S') + '.zip'
# 5. Используем команду "zip" для помещения файлов в zip-архив
zip_command = "7z a {0} {1}".format(target, ' '.join(source)) 
print(zip_command)
# Запускаем создание резервной копии
if os.system(zip_command) == 0:
    print('Резервная копия успешно создана в', target)
else:
    print('Создание резервной копии НЕ УДАЛОСЬ')