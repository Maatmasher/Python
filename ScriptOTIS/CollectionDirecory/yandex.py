import pandas as pd
import requests
from time import sleep
import certifi
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(CURRENT_DIR, "yandex.xlsx")
OUTPUT_FILE = os.path.join(CURRENT_DIR, "coordinates_output.xlsx")
API_KEY = "7ce8ab1a-0ee9-4e2d-abc2-53bb3e6a6532"  # Нужен ключ разработчика API Яндекс


def geocode_yandex(address):
    """По адресам в eXel получаем геоданные"""
    url = "https://geocode-maps.yandex.ru/1.x/"
    params = {
        "apikey": API_KEY,
        "geocode": address,
        "format": "json",
    }
    try:
        response = requests.get(url, params=params, verify=certifi.where())
        data = response.json()
        pos = data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"][
            "Point"
        ]["pos"]
        lon, lat = pos.split(" ")
        return lat, lon
    except Exception as e:
        print(f"Ошибка: {address} – {e}")
        return None, None


# Чтение и обработка файла
df = pd.read_excel(INPUT_FILE, header=None, names=["address"])
df["latitude"] = None
df["longitude"] = None

for index, row in df.iterrows():
    lat, lon = geocode_yandex(row["address"])
    df.at[index, "latitude"] = lat
    df.at[index, "longitude"] = lon
    sleep(1)  # Задержка запросов или Яндекс ключ забанит

df.to_excel(OUTPUT_FILE, index=False)
print("Готово! Результат сохранён в", OUTPUT_FILE)
