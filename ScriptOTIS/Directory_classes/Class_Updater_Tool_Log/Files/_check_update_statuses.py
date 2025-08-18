    def _check_update_statuses_(self, current_batch: List[Dict]) -> Optional[bool]:
        """Проверяет различные статусы обновления"""
        # Проверяем необходимость перезапуска служб
        if self._handle_service_restart(FILES["ccm_tp"], FILES["ccm_restart_commands"]):
            return None
        if self._handle_service_restart(
            FILES["unzip_tp"], FILES["unzip_restart_commands"]
        ):
            return None

        # Проверяем завершение обновления
        if self.check_file_exists(FILES["status_prefix"] + FILES["work_tp"]):
            work_servers = self.read_file_lines(
                FILES["status_prefix"] + FILES["work_tp"]
            )
            servers_match, incorrect_versions = self.compare_servers_and_versions(
                work_servers, current_batch
            )
            if servers_match and not incorrect_versions:
                return True
        return None
