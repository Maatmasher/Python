#!/usr/bin/env python3

def printMax(a, b):
    if a > b:
        print(a, 'максимально')
    elif a==b:
        print(a, 'равное', b)
    else:
        print(b, 'максимально')

printMax(3, 4) #Прямая передача значений

x = 5
y = 7

printMax(x, y) # передача переменных в качестве аргументов
