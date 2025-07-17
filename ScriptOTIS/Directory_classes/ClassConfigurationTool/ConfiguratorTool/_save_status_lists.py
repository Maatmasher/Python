def save_status_lists(self, prefix: str = ""):
    """Сохраняет все списки статусов в отдельные файлы"""
    lists_to_save = {
        "work_tp": self.work_tp,
        "error_tp": self.error_tp,
        "update_tp": self.update_tp,
        "ccm_tp": self.ccm_tp,
        "unzip_tp": self.unzip_tp,
        "no_update_needed_tp": self.no_update_needed_tp,
    }

    # Удаляем старые файлы
    for list_name in lists_to_save:
        filename = f"{prefix}{list_name}.txt" if prefix else f"{list_name}.txt"
        filepath = self.config_dir / filename
        if filepath.is_file():
            filepath.unlink()

    for list_name, data in lists_to_save.items():
        if not data:  # Пустой список не формируем
            continue
        filename = f"{prefix}{list_name}.txt" if prefix else f"{list_name}.txt"
        filepath = self.config_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(data))
        logging.info(f"Список {list_name} сохранен в {filepath}")
