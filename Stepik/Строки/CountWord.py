# Есть ли в строке слово
s = 'I learn Python language. Python - awesome!'
print(s.find('Python'))
# Найти количество слов
s = input()
words = s.split()
print(len(words))
words2 = s.count(' ') + 1
print(words2)