import keyring
import sys

# Данные для сохранения (замените на ваши значения)
SERVICE_NAME = "service"
USERNAME = "login"
PASSWORD = "password"

def save_credentials(service_name, username, password):
    """
    Сохраняет учетные данные в keyring
    """
    try:
        keyring.set_password(service_name, username, password)
        print(f"Учетные данные успешно сохранены в keyring!")
        print(f"Сервис: {service_name}")
        print(f"Пользователь: {username}")
        return True
    except Exception as e:
        print(f"Ошибка при сохранении: {e}")
        return False

def verify_credentials(service_name, username, expected_password):
    """
    Проверяет, что учетные данные были сохранены правильно
    """
    try:
        saved_password = keyring.get_password(service_name, username)
        if saved_password == expected_password:
            print("✓ Проверка: учетные данные сохранены корректно")
            return True
        else:
            print("✗ Ошибка: сохраненный пароль не совпадает")
            return False
    except Exception as e:
        print(f"Ошибка при проверке: {e}")
        return False

if __name__ == "__main__":
    # Сохраняем учетные данные
    success = save_credentials(SERVICE_NAME, USERNAME, PASSWORD)
    
    if success:
        # Проверяем сохранение
        verify_credentials(SERVICE_NAME, USERNAME, PASSWORD)
    
    # Дополнительная информация
    print(f"\nДля получения пароля используйте:")
    print(f"keyring.get_password('{SERVICE_NAME}', '{USERNAME}')")