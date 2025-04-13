#!/usr/bin/env python3

x = 50

def func():
    global x

    print('x равно', x)
    x = 2
    print('Заменяем глобальное значение х на', x)

func()
print('Значение х составляет', x)
