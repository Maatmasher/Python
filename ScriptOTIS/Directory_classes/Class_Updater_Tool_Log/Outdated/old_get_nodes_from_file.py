def old_get_nodes_from_file(
    self, filename: Union[Path, None] = None
) -> Dict[str, Dict[str, Optional[str]]]:
    """Получить состояние узлов перечисленных в файле"""
    if filename is None:
        filename = Path(FILES["server_list"])
    filepath: Path = self.config.get("config_dir") / filename
    self.logger.info(f"Получение состояния узлов из файла {filepath}")
    return self._execute_command(
        ["-ch", self.centrum_host, "-f", str(filepath)],
        MAX_RETRIES_SINGLE,
    )
