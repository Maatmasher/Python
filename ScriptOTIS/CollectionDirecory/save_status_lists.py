def save_status_lists(self, prefix: str = ""):
    """Сохраняет все списки статусов в отдельные файлы"""
    logger.debug(f"Сохранение списков статусов с префиксом '{prefix}'")

    lists_to_save = {
        FILES["work_tp"]: self.work_tp,
        FILES["error_tp"]: self.error_tp,
        FILES["update_tp"]: self.update_tp,
        FILES["ccm_tp"]: self.ccm_tp,
        FILES["unzip_tp"]: self.unzip_tp,
        FILES["no_update_needed_tp"]: self.no_update_needed_tp,
    }

    # Удаляем старые файлы
    for filename in lists_to_save:
        # Формируем путь: добавляем префикс только к имени файла, а не ко всему пути
        filepath = self.config_dir / (prefix + filename) if prefix else self.config_dir / filename
        if filepath.is_file():
            logger.debug(f"Удаление старого файла: {filepath}")
            filepath.unlink()

    # Пишем новые файлы
    for filename, data in lists_to_save.items():
        if not data:
            logger.debug(f"Нет данных для сохранения в {filename}")
            continue

        # Формируем путь: добавляем префикс только к имени файла, а не ко всему пути
        filepath = self.config_dir / (prefix + filename) if prefix else self.config_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(data))
        logger.info(f"Список сохранен в {filepath} (записей: {len(data)})")