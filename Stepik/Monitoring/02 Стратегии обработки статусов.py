class StatusHandler(ABC):
    """Базовый класс для обработки статусов"""
    
    @abstractmethod
    def can_handle(self, status: ServerStatus) -> bool:
        pass
    
    @abstractmethod
    def process(self, context: MonitoringContext, servers: List[str]) -> MonitoringState:
        pass
    
    @abstractmethod
    def get_priority(self) -> int:
        """Приоритет обработки (меньше = выше приоритет)"""
        pass

class ErrorStatusHandler(StatusHandler):
    """Обработчик статуса ERROR - высший приоритет"""
    
    def can_handle(self, status: ServerStatus) -> bool:
        return status == ServerStatus.ERROR
    
    def process(self, context: MonitoringContext, servers: List[str]) -> MonitoringState:
        if servers:
            logger.error(f"Обнаружены серверы с ошибками: {servers}")
            return MonitoringState.FAILED
        return MonitoringState.MONITORING
    
    def get_priority(self) -> int:
        return 1

class RestartRequiredHandler(StatusHandler):
    """Обработчик для статусов, требующих перезапуска служб"""
    
    def __init__(self, status: ServerStatus, commands_file: str):
        self.status = status
        self.commands_file = commands_file
    
    def can_handle(self, status: ServerStatus) -> bool:
        return status == self.status
    
    def process(self, context: MonitoringContext, servers: List[str]) -> MonitoringState:
        if servers:
            logger.info(f"Перезапуск служб для статуса {self.status.value}: {servers}")
            # Здесь должен быть вызов перезапуска служб
            return MonitoringState.REQUIRES_ACTION
        return MonitoringState.MONITORING
    
    def get_priority(self) -> int:
        return 2

class StuckStatusHandler(StatusHandler):
    """Обработчик для статусов, которые могут "застрять" """
    
    def __init__(self, status: ServerStatus, max_stable_iterations: int = 2):
        self.status = status
        self.max_stable_iterations = max_stable_iterations
    
    def can_handle(self, status: ServerStatus) -> bool:
        return status in [ServerStatus.UPDATE, ServerStatus.UNAVAILABLE]
    
    def process(self, context: MonitoringContext, servers: List[str]) -> MonitoringState:
        if not servers:
            return MonitoringState.MONITORING
            
        tracker = context.trackers[self.status]
        servers_set = set(servers)
        
        if tracker.update(servers_set):
            logger.error(f"Серверы застряли в статусе {self.status.value}: {servers}")
            return MonitoringState.FAILED
        
        logger.debug(f"Серверы в статусе {self.status.value}: {servers} (попытка {tracker.counter + 1})")
        return MonitoringState.MONITORING
    
    def get_priority(self) -> int:
        return 3

class SuccessStatusHandler(StatusHandler):
    """Обработчик успешного завершения"""
    
    def can_handle(self, status: ServerStatus) -> bool:
        return status == ServerStatus.WORK
    
    def process(self, context: MonitoringContext, servers: List[str]) -> MonitoringState:
        if servers:
            # Проверяем соответствие с ожидаемыми серверами
            original_indices = {s['tp_index'] for s in context.current_servers}
            work_indices = {s.split('-')[0] for s in servers if s.split('-')[0] != '0'}
            
            if original_indices == work_indices:
                logger.info("Обновление успешно завершено для всех серверов")
                return MonitoringState.SUCCESS
        
        return MonitoringState.MONITORING
    
    def get_priority(self) -> int:
        return 4