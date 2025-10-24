from itertools import accumulate
from operator import sub

"""код решает задачу о максимальной прибыли от одной сделки с акциями."""


def checkio(stock: list[int]) -> int:
    return max(map(sub, stock, accumulate(stock, min)))
