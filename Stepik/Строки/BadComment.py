"""Программа должна принимать на вход натуральное число n, а затем  n строк, представляющих тексты комментариев.
Для каждого комментария ваша программа должна выводить номер этого комментария (начиная с 1), затем двоеточие (:),
затем через пробел его текст или сообщение «COMMENT SHOULD BE DELETED» (без кавычек), если комментарий должен быть удалён
"""

n = int(input())

# Выводит после каждого комментария
for i in range(1, n + 1):
    comment = input()
    if comment != "" and not comment.isspace():
        print(i, ": ", comment, sep="")
    else:
        print(i, ": ", "COMMENT SHOULD BE DELETED", sep="")

# Сперва собирает все комментарии и выводит так же сразу
"""
coments = []
for i in range(n):
    comment = input()
    if comment != "" and not comment.isspace():
        coments.append(comment)
    else:
        coments.append("COMMENT SHOULD BE DELETED")
for k, v in enumerate(coments, start=1):
    print(k, ': ', v, sep='')

"""
