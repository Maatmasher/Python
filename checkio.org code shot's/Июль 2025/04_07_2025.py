from collections import Counter

"""код проверяет, являются ли две строки анаграммами"""


def stats(string: str):
    return Counter(string.lower().replace(" ", ""))


# Подсчитывает количество каждого символа при помощи Counter и возвращает в виде коллекции


def checkio(first: str, second: str) -> bool:
    return stats(first) == stats(second)


# Сравнивает две коллекции

print(checkio("Listen", "Silent"))  # True
print(checkio("Hello", "World"))  # False
print(checkio("God", "Dog"))  # True
print(checkio("a B c", "c b a"))  # True
