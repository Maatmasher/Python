    def old_get_all_nodes(
        self, max_retries: int = MAX_RETRIES_DEFAULT
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Получить состояние всех узлов с Centrum"""
        logger.info("Получение состояния всех узлов с Centrum")
        return self._execute_command(["-ch", self.centrum_host, "--all"], max_retries)