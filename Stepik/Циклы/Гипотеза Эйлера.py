# a ** 5 + b ** 5 + c ** 5 + d ** 5 = e ** 5
# Вычисление опровержения гипотезы Эйлера
import time
start_time = time.time()


exponent_dict = {x**5: x for x in range(151)}
for a in range(1, 151):
    for b in range(a, 151):
        for c in range(b, 151):
            for d in range(c, 151):
                sum_exponent = a**5 + b**5 + c**5 + d**5
                if sum_exponent in exponent_dict:
                    print(a, b, c, d, exponent_dict[sum_exponent])
                    print(a + b + c + d + exponent_dict[sum_exponent])
end_time = time.time()
elapsed = end_time - start_time
print(f"Duration: {int(elapsed // 60)} минут {int(elapsed % 60)} секунд")

# p = [x**5 for x in range(151)]

# pw = set(p)

# for a in range(1, 151):

#     for b in range(a, 151):

#         for c in range(b, 151):

#             for d in range(c, 151):

#                 s = p[a] + p[b] + p[c] + p[d]

#                 if s in pw:

#                     print(a, b, c, d, p.index(s))

#                     print(a + b + c + d + p.index(s))
# end_time = time.time()
# elapsed = end_time - start_time
# print(f"Duration: {int(elapsed // 60)} минут {int(elapsed % 60)} секунд")