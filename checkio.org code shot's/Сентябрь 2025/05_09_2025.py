from unittest import result

# Этот код находит последний общий элемент в двух списках, начиная сравнение с конца.


def checkio(a: list[int], b: list[int]):
    result = None

    for i, j in zip(a[::-1], b[::-1]):
        if i == j:
            result = i
        else:
            break

    return result


result = checkio([1, 2, 3, 4, 5], [6, 7, 3, 4, 5])
print(result)
