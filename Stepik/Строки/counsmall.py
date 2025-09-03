# Подсчёт маленьких букв
s = "gggggggg1212321ABDCEFCE"
ln = len(s)
cnt = 0
for i in range(ln):
    if s[i] != s[i].upper():
        cnt += 1
print(cnt)
