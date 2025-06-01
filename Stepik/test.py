#! /usr/bin/env python
n = 0
while n < 10:
    n += 2
    if n == 7:
        break
    print(n)
else:
    print('Цикл завершен.')