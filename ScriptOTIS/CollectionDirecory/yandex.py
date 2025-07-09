import pandas as pd
import requests
from time import sleep

API_KEY = "7ce8ab1a-0ee9-4e2d-abc2-53bb3e6a6532"  # Замените на реальный ключ
INPUT_FILE = r"C:\Users\iakushin.n\Documents\GitHub\Python\ScriptOTIS\CollectionDirecory\yandex.xlsx"
OUTPUT_FILE = r"C:\Users\iakushin.n\Documents\GitHub\Python\ScriptOTIS\CollectionDirecory\coordinates_output.xlsx"

def geocode_yandex(address):
    url = "https://geocode-maps.yandex.ru/1.x/"
    params = {
        "apikey": API_KEY,
        "geocode": address,
        "format": "json",
    }
    try:
        # Отключаем проверку SSL (только для теста!)
        response = requests.get(url, params=params, verify=False)
        data = response.json()
        pos = data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["Point"]["pos"]
        lon, lat = pos.split(" ")
        return lat, lon
    except Exception as e:
        print(f"Ошибка: {address} – {e}")
        return None, None

# Чтение файла
df = pd.read_excel(INPUT_FILE, header=None, names=["address"])
df["latitude"] = None
df["longitude"] = None

# Обработка адресов
for index, row in df.iterrows():
    lat, lon = geocode_yandex(row["address"])
    df.at[index, "latitude"] = lat
    df.at[index, "longitude"] = lon
    sleep(0.3)  # Задержка для API

# Сохранение
df.to_excel(OUTPUT_FILE, index=False)
print("Готово! Результат сохранен в", OUTPUT_FILE)