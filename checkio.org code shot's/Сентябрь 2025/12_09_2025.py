from itertools import pairwise

"""код эффективно проверяет наличие "долин" в последовательности, используя минимальную память и выполняя поиск за один проход. Алгоритм находит первую же долину и сразу возвращает результат."""


def checkio(heights):
    changePoint = False
    for h1, h2 in pairwise(heights):
        if changePoint and h1 < h2:
            return True
        changePoint = h2 < h1

    return False


print(checkio([5, 3, 6]))  # True  - долина
print(checkio([1, 2, 3]))  # False - только рост
print(checkio([3, 2, 1]))  # False - только падение
print(checkio([1, 2, 1, 2]))  # True  - долина
print(checkio([1, 1, 1]))  # False - плато
