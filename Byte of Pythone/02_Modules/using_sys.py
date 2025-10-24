#!/usr/bin/env python3

import sys

print('Аргументы командной строки:')
for i in sys.argv:
    print(i)

print('\n\nПеременная PythonPath содержит', sys.path, '\n')
