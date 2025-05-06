#!/usr/bin/env python3
def func(a, b=5, c=10):
    """_summary_

    Args:
        a (_type_): _description_
        b (int, optional): _description_. Defaults to 5.
        c (int, optional): _description_. Defaults to 10.
    """
    print('а равно', a,', b равно', b, ', а c равно', c)

func(3, 7)
func(25, c=24)
func(c=50, a=100)