checkio = lambda: (lambda x: x + str((x,)))(
    "quine = lambda: (lambda x: x+str((x,)))",
)
"""Этот код представляет собой квин-функцию (quine) - программу, которая выводит свой собственный исходный код."""
result = checkio()
print(result)
