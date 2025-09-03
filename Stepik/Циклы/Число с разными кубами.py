# n = a ** 3 + b **3 = c ** 3 + d ** 3
# Вычисление числа у которого сумма двух кубов двумя разными способами
# считаем с наименьшего по словам математика
n = 1729
count_num = 0
while count_num < 5:
    y = 0
    max_num = int(n ** (1 / 3)) + 2
    for a in range(1, max_num):
        b_cub = n - a**3
        if b_cub > 0:
            b = round(b_cub ** (1 / 3))
            if (b**3) == b_cub and b >= a:
                y += 1
    if y > 1:
        print(n)
        count_num += 1
    n += 1
