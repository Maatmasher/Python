def checkio(values: list[int]) -> list[int]:
    """Возвращает неубывающую подпоследовательность исходного списка"""
    if not values:
        return []
    res = [values[0]]
    for i in values[1:]:
        if i >= res[-1]:
            res.append(i)

    return res
