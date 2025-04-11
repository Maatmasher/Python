#! /usr/bin/env python3

x = 50

def func(x):
    print('х равен', x)
    x = 2
    print('Замена локального х на', x)

func(x)
print('х по прежнему х', x)
