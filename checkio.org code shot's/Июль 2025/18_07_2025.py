"""код вычисляет факториал числа с помощью итеративного подхода."""


def checkio(n: int) -> int:

    res = 1
    for i in range(2, n + 1):
        res *= i

    return res
