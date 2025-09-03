# На приёмник ему поступает nn различных последовательностей
# только в сообщениях Оди содержится число 11, причём минимум 3 раза
count_message = 0
num_str = int(input())
while num_str > 0:
    morze_message = input()
    if morze_message.count("11") >= 3:
        count_message +=1
    num_str -=1
print(count_message)