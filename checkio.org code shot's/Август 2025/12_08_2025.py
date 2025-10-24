from typing import Iterable
from itertools import groupby

"""код решает задачу удаления последовательных дубликатов"""


def checkio(items: list[int]) -> Iterable[int]:

    yield from (val for val, _ in groupby(items))


print(list(checkio([1, 1, 2, 2, 3, 3])))  # [1, 2, 3]
print(list(checkio([1, 2, 3, 4, 5])))  # [1, 2, 3, 4, 5]
print(list(checkio([1, 1, 1, 1])))  # [1]
print(list(checkio([1, 2, 1, 2, 1, 2])))  # [1, 2, 1, 2, 1, 2]
print(list(checkio([])))  # []
