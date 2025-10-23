from PIL import Image
from pathlib import Path
import time


def validate_and_rename_images():
    """
    Проверяет и переименовывает файлы изображений по следующим критериям:
    1. Имена файлов, состоящие только из чисел, должны быть 7-значными с ведущими нулями
    2. Форматы: JPG (JPEG) или PNG
    3. Минимальный размер: 512x512 px
    """
    current_dir = Path(__file__).resolve().parent
    folder_path = current_dir / "image"

    if not folder_path.exists():
        print(f"Папка {folder_path} не существует!")
        return

    # Поддерживаемые форматы
    supported_formats = {".jpg", ".jpeg", ".png"}

    # Счетчики
    processed_count = 0
    renamed_count = 0
    invalid_size_count = 0
    invalid_format_count = 0
    skipped_count = 0

    for file_path in folder_path.iterdir():
        if file_path.is_file():
            print(f"\nОбработка файла: {file_path.name}")

            # Проверяем формат файла
            if file_path.suffix.lower() not in supported_formats:
                print(f"Неподдерживаемый формат: {file_path.suffix}")
                invalid_format_count += 1
                continue

            try:
                # Открываем изображение
                with Image.open(file_path) as img:
                    width, height = img.size

                    # Проверяем размер
                    if width < 201 or height < 145:
                        print(f"Размер {width}x{height} меньше минимального 512x512")
                        invalid_size_count += 1
                        img.close()
                        time.sleep(0.1)
                        continue

                    print(f"Размер: {width}x{height}")
                    img.close()
                    time.sleep(0.1)

                    # Проверяем, состоит ли имя файла только из чисел
                    filename_without_ext = file_path.stem
                    if filename_without_ext.isdigit():
                        # Проверяем длину числа
                        if len(filename_without_ext) != 7:
                            # Переименовываем с ведущими нулями
                            new_filename = f"{int(filename_without_ext):07d}{file_path.suffix.lower()}"
                            new_file_path = file_path.parent / new_filename

                            # Проверяем, не существует ли уже файл с таким именем
                            if new_file_path.exists() and new_file_path != file_path:
                                print(f"Файл {new_filename} уже существует, пропускаем")
                                skipped_count += 1
                                continue

                            # Переименовываем файл
                            file_path.rename(new_file_path)
                            print(f"Переименован: {file_path.name} -> {new_filename}")
                            renamed_count += 1
                        else:
                            print(
                                f"Имя файла уже соответствует требованиям: {file_path.name}"
                            )
                            processed_count += 1
                    else:
                        print(
                            f"Имя файла не состоит из чисел, оставляем как есть: {file_path.name}"
                        )
                        processed_count += 1

            except Exception as e:
                print(f"Ошибка при обработке файла {file_path.name}: {e}")
                invalid_format_count += 1

    # Вывод статистики
    print("\n" + "=" * 50)
    print("СТАТИСТИКА ОБРАБОТКИ:")
    print(f"Обработано корректных файлов: {processed_count}")
    print(f"Переименовано файлов: {renamed_count}")
    print(f"Файлов с недопустимым размером: {invalid_size_count}")
    print(f"Файлов с недопустимым форматом: {invalid_format_count}")
    print(f"Пропущено файлов: {skipped_count}")
    print(
        f"Всего файлов: {processed_count + renamed_count + invalid_size_count + invalid_format_count + skipped_count}"
    )
    print("=" * 50)


def check_image_compliance():
    """
    Только проверяет файлы без переименования
    """
    current_dir: Path = Path(__file__).resolve().parent
    folder_path: Path = current_dir / "image"

    if not folder_path.exists():
        print(f"Папка {folder_path} не существует!")
        return

    supported_formats = {".jpg", ".jpeg", ".png"}

    compliant_files = []
    non_compliant_files = []

    for file_path in folder_path.iterdir():
        if file_path.is_file():
            file_info = {
                "name": file_path.name,
                "valid_format": False,
                "valid_size": False,
                "valid_name": False,
                "issues": [],
            }

            # Проверяем формат
            if file_path.suffix.lower() in supported_formats:
                file_info["valid_format"] = True
            else:
                file_info["issues"].append(
                    f"Неподдерживаемый формат: {file_path.suffix}"
                )

            try:
                with Image.open(file_path) as img:
                    width, height = img.size
                    if width >= 512 and height >= 512:
                        file_info["valid_size"] = True
                    else:
                        file_info["issues"].append(
                            f"Маленький размер: {width}x{height}"
                        )

                    # Проверяем имя файла
                    filename_without_ext = file_path.stem
                    if filename_without_ext.isdigit():
                        if len(filename_without_ext) == 7:
                            file_info["valid_name"] = True
                        else:
                            file_info["issues"].append(
                                f"Неправильная длина числового имени: {len(filename_without_ext)}"
                            )
                    else:
                        file_info["valid_name"] = (
                            True  # Имя не числовое, считаем допустимым
                        )

            except Exception as e:
                file_info["issues"].append(f"Ошибка открытия изображения: {e}")

            # Проверяем, все ли требования выполнены
            if (
                file_info["valid_format"]
                and file_info["valid_size"]
                and file_info["valid_name"]
            ):
                compliant_files.append(file_info)
            else:
                non_compliant_files.append(file_info)

    # Вывод результатов
    print(f"\nНайдено {len(compliant_files)} файлов, соответствующих требованиям:")
    for file_info in compliant_files:
        print(f"{file_info['name']}")

    print(
        f"\nНайдено {len(non_compliant_files)} файлов, НЕ соответствующих требованиям:"
    )
    for file_info in non_compliant_files:
        print(f"{file_info['name']} - {', '.join(file_info['issues'])}")


def main():
    print("Выберите режим работы:")
    print("1 - Проверить и переименовать файлы")
    print("2 - Только проверить файлы")

    choice = input("Ваш выбор (1 или 2): ").strip()

    if choice == "1":
        validate_and_rename_images()
    elif choice == "2":
        check_image_compliance()
    else:
        print("Неверный выбор!")


if __name__ == "__main__":
    # Убедитесь, что Pillow установлен: pip install Pillow
    main()
