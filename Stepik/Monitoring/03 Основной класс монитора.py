class StatusMonitor:
    """Монитор статусов обновления"""
    
    def __init__(self, updater_instance):
        self.updater = updater_instance
        self.handlers: List[StatusHandler] = []
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Настройка обработчиков статусов"""
        self.handlers = [
            ErrorStatusHandler(),
            RestartRequiredHandler(ServerStatus.CCM_RESTART, FILES["ccm_restart_commands"]),
            RestartRequiredHandler(ServerStatus.UNZIP, FILES["unzip_restart_commands"]),
            StuckStatusHandler(ServerStatus.UPDATE, max_stable_iterations=2),
            StuckStatusHandler(ServerStatus.UNAVAILABLE, max_stable_iterations=2),
            SuccessStatusHandler()
        ]
        # Сортируем по приоритету
        self.handlers.sort(key=lambda h: h.get_priority())
    
    def monitor_update_progress(self, current_servers: List[Dict]) -> bool:
        """Основной метод мониторинга"""
        context = MonitoringContext(current_servers=current_servers)
        
        while context.state not in [MonitoringState.SUCCESS, MonitoringState.FAILED]:
            logger.info(f"Проверка статуса (итерация {context.iteration_count + 1})")
            
            # Получаем текущее состояние
            self.updater.get_nodes_from_file()
            self.updater.save_status_lists(prefix=FILES["status_prefix"])
            
            # Обрабатываем каждый статус
            context.state = self._process_all_statuses(context)
            
            if context.state == MonitoringState.REQUIRES_ACTION:
                # После выполнения действий продолжаем мониторинг
                context.state = MonitoringState.MONITORING
            
            if context.state == MonitoringState.MONITORING:
                context.iteration_count += 1
                logger.info(f"Ожидание {STATUS_CHECK_INTERVAL // 60} минут...")
                time.sleep(STATUS_CHECK_INTERVAL)
        
        return context.state == MonitoringState.SUCCESS
    
    def _process_all_statuses(self, context: MonitoringContext) -> MonitoringState:
        """Обработка всех статусов по приоритету"""
        status_files = {
            ServerStatus.ERROR: FILES["error_tp"],
            ServerStatus.UPDATE: FILES["update_tp"],
            ServerStatus.CCM_RESTART: FILES["ccm_tp"],
            ServerStatus.UNZIP: FILES["unzip_tp"],
            ServerStatus.UNAVAILABLE: FILES["unavailable_tp"],
            ServerStatus.WORK: FILES["work_tp"],
        }
        
        for handler in self.handlers:
            for status, filename in status_files.items():
                if not handler.can_handle(status):
                    continue
                
                servers = self._read_status_file(filename)
                result_state = handler.process(context, servers)
                
                # Если обработчик вернул не MONITORING, возвращаем результат
                if result_state != MonitoringState.MONITORING:
                    return result_state
        
        return MonitoringState.MONITORING
    
    def _read_status_file(self, filename: str) -> List[str]:
        """Чтение файла статуса"""
        full_filename = FILES["status_prefix"] + filename
        if self.updater.check_file_exists(full_filename):
            return self.updater.read_file_lines(full_filename)
        return []