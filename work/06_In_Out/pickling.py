#! /usr/bin/env python3

import pickle

# Имя файла, в котором сохраним объект
shoplistfile = 'shoplist.data'
# Список покупок
shoplist = ['яблоки', 'манго', 'морковь']

# Запись в файл
f = open(shoplistfile, 'wb')
pickle.dump(shoplist, f) # Помещаем объект в файл