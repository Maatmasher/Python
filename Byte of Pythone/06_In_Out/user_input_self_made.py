#! /usr/bin/env python3
import re

def reverse(text):
    return text[::-1]

def is_palindrome(text):
    return text == reverse(text)

something = input('Введите текст: ')
letters_only = re.sub(r'[^a-zA-ZА-Яа-я]', '', something) # Удаляем знаки пунктуации и пробелы
print(letters_only)
palindrome = letters_only.lower() # Приводим к нижнему регистру
print(palindrome)
if (is_palindrome(palindrome)):
    print("Да, это палиндром")
else:
    print("Нет, это не палиндром")