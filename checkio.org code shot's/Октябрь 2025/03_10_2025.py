SeqTup = list[tuple[int, int]]
SeqTup = [(1, 3), (2, 5), (7, 9), (8, 10)]
# Функция принимает список интервалов (пар чисел) и объединяет пересекающиеся или смежные интервалы.
# Обработка временных интервалов
# Объединение периодов доступности
# Анализ данных с временными метками
# Оптимизация расписаний


def checkio(data: SeqTup) -> SeqTup:  # type: ignore

    res = []
    start = end = None
    for s, e in data:
        if not start:
            start, end = s, e
        elif s - end < 2:  # type: ignore
            end = max(end, e)  # type: ignore
        else:
            res.append((start, end))
            start, end = s, e
    if start:
        res.append((start, end))

    return res


result = checkio(SeqTup)
print(result)
