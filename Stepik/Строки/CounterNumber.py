# подсчитывает количество цифр в данной строке
str_text = input()
count_num = 0
for i in range(10):
    # count_num += str_text.count(f"{i}")
    count_num += str_text.count(str(i))
print(count_num)
