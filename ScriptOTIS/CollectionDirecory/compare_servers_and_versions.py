def compare_servers_and_versions(
    self, work_servers: List[str], original_servers: List[Dict]
) -> tuple[bool, List[str]]:
    """Сравнивает серверы из work_tp с исходными и проверяет версии"""

    # Извлекаем индексы из исходных серверов
    original_indices = {server["tp_index"] for server in original_servers}

    # Извлекаем индексы из work_tp (формат: "индекс-тип-ip-версия")
    work_indices = set()
    work_versions = {}

    for server_info in work_servers:
        parts = server_info.split("-")
        if parts:
            tp_index = parts[0]
            work_indices.add(tp_index)

            # Извлекаем версию если есть
            if len(parts) >= 4:
                work_versions[tp_index] = parts[3]

    # Сравниваем множества индексов
    if original_indices != work_indices:
        logging.error(
            f"Несоответствие серверов: ожидалось {original_indices}, получено {work_indices}"
        )
        return False, []

    # Проверяем версии
    incorrect_versions = []
    for tp_index, version in work_versions.items():
        if version != self.target_version:
            incorrect_versions.append(f"{tp_index}: {version} != {self.target_version}")

    return len(incorrect_versions) == 0, incorrect_versions
