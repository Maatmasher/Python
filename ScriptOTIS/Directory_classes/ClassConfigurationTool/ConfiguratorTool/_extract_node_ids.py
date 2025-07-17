def _extract_node_ids(self, output: str) -> List[str]:
    """Извлекает все ID узлов из вывода"""
    node_ids = []
    for line in output.splitlines():
        if (
            "успешно запланировано" in line
            or "недоступен" in line
            or "не требуется" in line
        ):
            parts = line.split()
            for part in parts:
                if part.replace(".", "").isdigit() and len(part.split(".")) >= 3:
                    if part.split(".")[3] == "0":
                        node_ids.append(part.split(".")[2])
                    else:
                        node_ids.append(f"{part.split('.')[2]}.{part.split('.')[3]}")
    return node_ids
