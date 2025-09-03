# выводит на экран символ, который появляется наиболее часто.
s = input().strip()
if not s:
    print("")
else:
    max_count = 0
    max_char = s[-1]  # по умолчанию последний символ (если все встречаются 1 раз)

    for i in range(len(s)):
        current_count = 0
        for j in range(len(s)):
            if s[i] == s[j]:
                current_count += 1
        # Если текущий символ встречается не реже предыдущего максимума, обновляем
        if current_count >= max_count:
            max_count = current_count
            max_char = s[i]

    print(max_char)
