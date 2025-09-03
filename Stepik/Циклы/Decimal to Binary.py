n = int(input())
binar = ""
while n > 0:
    binar = binar + str(n % 2)
    n //= 2
for i in range(-1, -(len(binar) + 1), -1):
    print(binar[i], end="")
