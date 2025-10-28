"""Под "тяжестью" слова будем понимать сумму кодов по таблице Unicode всех символов этого слова.
Напишите программу, которая принимает 4 слова и находит среди них самое тяжёлое слово.
Если самых тяжёлых слов будет несколько, то программа должна вывести первое из них."""

a, b, c, d = input(), input(), input(), input()
ac, bc, cc, dc = 0, 0, 0, 0
for i in a:
    ac += ord(i)
for j in b:
    bc += ord(j)
for h in c:
    cc += ord(h)
for y in d:
    dc += ord(y)
m = max(ac, bc, cc, dc)
if m == ac:
    print(a)
elif m == bc:
    print(b)
elif m == cc:
    print(c)
else:
    print(d)

# Второй вариант
# most_heavy = 0
# for _ in range(4):
#     heavy = 0
#     word = input()
#     for w in word:
#         heavy += ord(w)
#     if most_heavy < heavy:
#         most_heavy = heavy
#         most_heavy_word = word
# print(most_heavy_word) # type: ignore
