"""Сэм хочет заменить следующие английские буквы:
eyopaxcETOPAHXCBM

на соответствующие им русские буквы:
еуорахсЕТОРАНХСВМ

Тимур визуально разницу не заметит, а Сэм сможет зарабатывать больше пчёлок-coin.
На вход программе подаётся строка текста.
Требуется написать программу, которая находит стоимость старого и нового сообщений Сэма в 🐝 и выводит текст в следующем формате:

Старая стоимость: <стоимость старого сообщения>🐝
Новая стоимость: <стоимость нового сообщения>🐝"""

old_value = 0
new_value = 0
a_str = "eyopaxcETOPAHXCBM"
r_str = "еуорахсЕТОРАНХСВМ"
comment = input()

for s in comment:
    old_value += ord(s)
print(f"Старая стоимость: {old_value * 3}🐝")

for i in comment:
    check = a_str.find(i)
    if check != -1:
        comment = comment.replace(a_str[check], r_str[check])
for s in comment:
    new_value += ord(s)
print(f"Новая стоимость: {new_value * 3}🐝")
