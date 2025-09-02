def get_all_nodes(
    self, max_retries: int = MAX_RETRIES_DEFAULT
) -> Dict[str, Dict[str, Optional[str]]]:
    """Получить состояние всех узлов с Centrum по частям из файла node_list.txt"""
    logger.info("Получение состояния всех узлов с Centrum из файла node_list.txt")

    # Читаем список всех узлов из файла
    node_list_path = Path(FILES_DIR) / "node_list.txt"
    if not node_list_path.exists():
        logger.error(f"Файл node_list.txt не найден: {node_list_path}")
        return {"error": {"message": f"Файл node_list.txt не найден: {node_list_path}"}}

    # Читаем все номера серверов
    with open(node_list_path, "r", encoding="utf-8") as f:
        all_nodes = [line.strip() for line in f if line.strip()]

    if not all_nodes:
        logger.warning("Файл node_list.txt пуст")
        return {}

    logger.info(f"Найдено {len(all_nodes)} узлов в файле node_list.txt")

    # Разбиваем на группы по 10 серверов
    all_results: Dict[str, Dict[str, Optional[str]]] = {}
    chunk_size = 10

    for i in range(0, len(all_nodes), chunk_size):
        chunk = all_nodes[i : i + chunk_size]
        logger.info(
            f"Обработка группы {i//chunk_size + 1}/{(len(all_nodes)-1)//chunk_size + 1}: {chunk}"
        )

        # Записываем текущую группу в server.txt
        server_list_path = self.config_dir / FILES["server_list"]
        with open(server_list_path, "w", encoding="utf-8") as f:
            f.write("\n".join(chunk))

        # Получаем состояние для текущей группы
        for _ in range(max_retries):
            chunk_result = self.get_nodes_from_file()

            # Проверяем на ошибки
            if "error" in chunk_result:
                logger.error(
                    f"Ошибка при получении состояния для группы {chunk}: {chunk_result['error']}"
                )
                # Продолжаем с следующей группой, но записываем ошибку
                for node in chunk:
                    all_results[node] = {
                        "tp": node,
                        "status": "ERROR",
                        "message": f"Ошибка получения состояния: {chunk_result['error'].get('message', 'Unknown error')}",
                        "type": None,
                        "cv": None,
                        "pv": None,
                        "online": None,
                        "ip": None,
                        "ut": None,
                        "local patches": None,
                    }
            else:
                # Добавляем результаты текущей группы
                all_results.update(chunk_result)

        # Пауза 10 секунд между группами
        if i + chunk_size < len(all_nodes):  # Не ждем после последней группы
            logger.info("Ожидание 10 секунд перед следующей группой...")
            time.sleep(3)

    all_results = {
        ip: node_data
        for ip, node_data in all_results.items()
        if node_data.get("type") is not None
    }

    logger.info(f"Все группы обработаны. Всего получено состояний: {len(all_results)}")

    # Сохраняем объединенный результат
    self.node_result = all_results
    return all_results
