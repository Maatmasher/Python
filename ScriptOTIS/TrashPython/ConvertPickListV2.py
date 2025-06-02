import json
import psycopg2
from psycopg2 import sql


def get_db_connection():
    return psycopg2.connect(
        dbname="set",
        user="postgres",
        password="postgres",
        host="10.21.11.45",
        port="5432",
    )


def process_barcode(barcode):
    # Если barcode начинается на 21, 22 или 23 и длиннее 7 символов
    if barcode and barcode[:2] in ("21", "22", "23") and len(barcode) > 7:
        return barcode[:7]
    return barcode


def get_sku_from_db(barcode):
    processed_barcode = process_barcode(barcode)
    if not processed_barcode:
        return None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = sql.SQL("SELECT product_marking FROM un_cg_barcode WHERE code = %s")
        cursor.execute(query, (processed_barcode,))
        result = cursor.fetchone()

        return result[0] if result else None
    except Exception as e:
        print(f"Error fetching SKU for barcode {barcode}: {e}")
        return None
    finally:
        if conn: # type: ignore
            conn.close()


def enhance_v2_data(v2_data):
    for page in v2_data.get("pages", []):
        for tile in page.get("tiles", []):
            # Обрабатываем вложенные страницы (категории)
            if "pages" in tile:
                for sub_page in tile["pages"]:
                    for sub_tile in sub_page.get("tiles", []):
                        if "barcode" in sub_tile and "sku" not in sub_tile:
                            sku = get_sku_from_db(sub_tile["barcode"])
                            if sku:
                                sub_tile["sku"] = sku
            # Обрабатываем обычные товары
            elif "barcode" in tile and "sku" not in tile:
                sku = get_sku_from_db(tile["barcode"])
                if sku:
                    tile["sku"] = sku
    return v2_data


def convert_v2_to_v3(v2_path, v3_path):
    # Загружаем данные из V2.json
    with open(v2_path, "r", encoding="utf-8") as f:
        v2_data = json.load(f)

    # Улучшаем данные, добавляя недостающие SKU
    enhanced_data = enhance_v2_data(v2_data)

    # Создаем структуру для V3.json
    v3_template = {
        "templateType": "PERMANENT",
        "templateName": "Пик-лист SCO V3",
        "templateGuid": 657413,
        "cashTemplates": [225577],
        "menuTemplates": [
            {
                "menuName": "Пик-Лист 98989",
                "shopNumbers": [98989],
                "cashType": "CSI_K",
                "dateFrom": "2025-06-02",
                "content": json.dumps(enhanced_data, ensure_ascii=False),
            }
        ],
    }

    # Сохраняем результат в V3.json
    with open(v3_path, "w", encoding="utf-8") as f:
        json.dump(v3_template, f, ensure_ascii=False, indent=4)


# Пример использования
convert_v2_to_v3("V2.json", "V3_output.json")
