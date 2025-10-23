import os
import shutil
import re

class DirectoryCleaner:
    def __init__(self, base_path):
        self.base_path = base_path
    
    def _is_valid_ip(self, ip_string):
        """Проверяет, является ли строка валидным IP-адресом"""
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(ip_pattern, ip_string):
            return False
        
        # Проверяем, что каждый октет в диапазоне 0-255
        parts = ip_string.split('.')
        for part in parts:
            if not 0 <= int(part) <= 255:
                return False
        return True

    def remove_ip_directories(self, dry_run=False):
        """
        Удаляет поддиректории, имена которых являются IP-адресами
        
        Args:
            dry_run (bool): Если True, только показывает что будет удалено, но не удаляет
            
        Returns:
            dict: Статистика операции {'removed': int, 'errors': int, 'total_found': int}
        """
        if not os.path.exists(self.base_path):
            raise FileNotFoundError(f"Директория '{self.base_path}' не существует")
        
        if not os.path.isdir(self.base_path):
            raise NotADirectoryError(f"'{self.base_path}' не является директорией")
        
        print(f"Поиск директорий с IP-адресами в: {self.base_path}")
        if dry_run:
            print("РЕЖИМ ПРОСМОТРА - файлы не будут удалены")
        
        stats = {
            'removed': 0,
            'errors': 0,
            'total_found': 0
        }
        
        try:
            for item in os.listdir(self.base_path):
                item_path = os.path.join(self.base_path, item)
                
                if os.path.isdir(item_path) and self._is_valid_ip(item):
                    stats['total_found'] += 1
                    try:
                        if dry_run:
                            print(f"[ПРОСМОТР] Будет удалено: {item_path}")
                        else:
                            shutil.rmtree(item_path)
                            print(f"[УДАЛЕНО] {item_path}")
                        stats['removed'] += 1
                    except Exception as e:
                        print(f"Ошибка при удалении {item_path}: {e}")
                        stats['errors'] += 1
        
        except PermissionError:
            raise PermissionError(f"Нет прав доступа к директории {self.base_path}")
        except Exception as e:
            raise RuntimeError(f"Неожиданная ошибка: {e}")
        
        # Выводим итоги
        print("\n" + "="*50)
        if dry_run:
            print(f"РЕЖИМ ПРОСМОТРА: найдено {stats['total_found']} директорий для удаления")
        else:
            print(f"Удалено директорий: {stats['removed']}")
            if stats['errors'] > 0:
                print(f"Ошибок при удалении: {stats['errors']}")
        
        return stats

    def get_ip_directories_list(self):
        """Возвращает список найденных директорий с IP-адресами"""
        if not os.path.exists(self.base_path):
            return []
        
        ip_dirs = []
        for item in os.listdir(self.base_path):
            item_path = os.path.join(self.base_path, item)
            if os.path.isdir(item_path) and self._is_valid_ip(item):
                ip_dirs.append(item_path)
        
        return ip_dirs
if __name__ == "__main__":
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    WORKING_DIR = os.getcwd()
    # Создание экземпляра класса
    cleaner = DirectoryCleaner(f"{WORKING_DIR}")

    # Получить список директорий которые будут удалены
    ip_directories = cleaner.get_ip_directories_list()
    print("Найдены директории:", ip_directories)

    # Просмотр что будет удалено (без фактического удаления)
    # stats = cleaner.remove_ip_directories(dry_run=True)

    # Фактическое удаление
    stats = cleaner.remove_ip_directories(dry_run=False)
    print("Статистика:", stats)