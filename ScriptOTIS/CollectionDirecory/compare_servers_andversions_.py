def compare_servers_and_versions(
    self, work_servers: List[str], original_servers: List[Dict]
) -> tuple[bool, List[str]]:
    """Сравнивает серверы из work_tp с исходными и проверяет версии"""
    # Получаем актуальные данные серверов
    current_nodes = self.configurator.get_nodes_from_file()

    # Сравниваем количество и индексы
    original_indices = {server["tp_index"] for server in original_servers}
    work_indices = set()

    for server_info in work_servers:
        # Извлекаем индекс из строки формата "индекс-тип-ip-версия"
        tp_index = server_info.split("-")[0]
        work_indices.add(tp_index)

    if original_indices != work_indices:
        logging.error(
            f"Несоответствие серверов: ожидалось {original_indices}, получено {work_indices}"
        )
        return False, []

    # Проверяем версии
    incorrect_versions = []
    for server_info in work_servers:
        parts = server_info.split("-")
        if len(parts) >= 4:
            server_version = parts[3]
            if server_version != self.target_version:
                incorrect_versions.append(server_info)

    if incorrect_versions:
        logging.error(f"Серверы с неправильными версиями: {incorrect_versions}")
        return False, incorrect_versions

    return True, []
