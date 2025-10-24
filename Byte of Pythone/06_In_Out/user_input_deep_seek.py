#!/usr/bin/env python3

import string

def clean_text(text):
    # Удаляем знаки пунктуации
    text = text.translate(str.maketrans('', '', string.punctuation))
    # Удаляем пробелы
    text = text.replace(' ', '')
    # Приводим к нижнему регистру
    return text.lower()

def reverse(text):
    return text[::-1]

def is_palindrome(text):
    cleaned_text = clean_text(text)
    return cleaned_text == reverse(cleaned_text)

something = input('Введите текст: ')
if is_palindrome(something):
    print("Да, это палиндром")
else:
    print("Нет, это не палиндром")