from datetime import datetime

"""''код моделирует накопление солнечной энергии в течение дня, предполагая постоянную скорость накопления 0.25 единиц в минуту в период с 06:00 до 18:00."""


def checkio(time: string): # type: ignore

    start = datetime.strptime("06:00", "%H:%M")
    end = datetime.strptime("18:00", "%H:%M")
    time = datetime.strptime(time, "%H:%M")
    diff = (time - start).seconds / 60 * 0.25

    return diff if start <= time <= end else "I don't see the sun!"


print(checkio("06:00"))  # 0.0
print(checkio("12:00"))  # 90.0
print(checkio("18:00"))  # 180.0
print(checkio("05:59"))  # "I don't see the sun!"
print(checkio("18:01"))  # "I don't see the sun!"
