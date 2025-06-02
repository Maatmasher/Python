import json


def convert_v2_to_v3(v2_path, v3_path):
    # Загружаем данные из V2.json
    with open(v2_path, "r", encoding="utf-8") as f:
        v2_data = json.load(f)

    # Создаем структуру для V3.json
    v3_template = {
        "templateType": "PERMANENT",
        "templateName": "Шаблон CSI",
        "templateGuid": 75370,
        "cashTemplates": [73526],
        "menuTemplates": [
            {
                "menuName": "шаблон",
                "shopNumbers": [1654, 1655, 1656, 1657, 1658],
                "cashType": "CSI_K",
                "dateFrom": "2022-05-09",
                "content": json.dumps(v2_data, ensure_ascii=False),
            }
        ],
    }

    # Сохраняем результат в V3.json
    with open(v3_path, "w", encoding="utf-8") as f:
        json.dump(v3_template, f, ensure_ascii=False, indent=4)


# Пример использования
convert_v2_to_v3("V2.json", "V3_output.json")
