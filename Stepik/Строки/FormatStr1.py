# 1. Используя метод format(), дополните приведённый ниже код так, чтобы он вывел текст:
# In 2010, someone paid 10k Bitcoin for two pizzas.

s = "In {0}, someone paid {1} {2} for two pizzas.".format("2010", "10k", "Bitcoin")

print(s)

# 2. Используя f-строку, дополните приведённый ниже код так, чтобы он вывел текст:
# In 2010, someone paid 10K Bitcoin for two pizzas.

s = f"In {2010}, someone paid {'10K'} {'Bitcoin'} for two pizzas."

print(s)
