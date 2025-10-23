import keyring
import psycopg2
from getpass import getpass


def _init_db_password(db_service_name) -> str:
    """Инициализирует пароль для базы данных"""
    try:
        db_password = keyring.get_password(db_service_name, db_user)
        # Если пароль есть в keyring, проверяем его валидность
        if db_password is not None:
            if _test_db_connection(db_password):
                return db_password

        # Если пароля нет или он невалидный — запрашиваем новый
        db_password = getpass(
            f"Введите пароль для базы данных (пользователь {db_user}): "
        )
        # Проверяем новый пароль
        if _test_db_connection(db_password):
            keyring.set_password(
                db_service_name,
                db_user,
                db_password,
            )
            return db_password
        else:
            raise ValueError("Неверный пароль для базы данных")
    except Exception as e:
        raise RuntimeError("Не удалось инициализировать пароль БД") from e


def _test_db_connection(password: str) -> bool:
    """Проверяет подключение к базе данных"""
    try:
        conn = psycopg2.connect(
            host=db_host_check,
            port=5432,
            database="catalog",
            user=db_user,
            password=password,
            connect_timeout=5,
        )
        conn.close()
        return True
    except psycopg2.Error:
        return False
    except Exception:
        return False

# cash
db_service_cash_less_17 = "cash_db_pass_less_17"
db_service_cash_more_17 = "cash_db_pass_more_17"
db_user = "postgres"
db_host_check = ""

fill_keyring = _init_db_password(db_service_cash_less_17)
