def update_cash_devices(
        self,
        cash_type: str,
        version: str = None,
        filename: Union[Path, None] = None,
        no_backup: bool = DEFAULT_NO_BACKUP,
        auto_restart: bool = DEFAULT_AUTO_RESTART,
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Запустить обновление касс по типу"""
        if version is None:
            version = self.target_version
        if filename is None:
            filename = Path(FILES["server_cash_list"])
        filepath = self.config_dir / filename

        logger.info(
            f"Запуск обновления касс типа {cash_type} из файла {filepath} до версии {version}"
        )

        args = [
            "-ch",
            self.centrum_host,
            "-f",
            str(filepath),
            "-sv",
            version,
            "-cv",
            f"{cash_type}:{version}",
        ]
        if no_backup:
            args.append("-nb")
            logger.debug("Используется флаг no_backup (-nb)")
        if auto_restart:
            args.append("-ar")
            logger.debug("Используется флаг auto_restart (-ar)")

        return self._execute_command(args, MAX_RETRIES_SINGLE)
