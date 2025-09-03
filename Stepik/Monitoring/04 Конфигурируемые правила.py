@dataclass
class MonitoringRule:
    """Правило мониторинга"""
    status: ServerStatus
    max_stable_iterations: int = 2
    timeout_minutes: int = 60
    action_required: bool = False
    action_commands_file: Optional[str] = None
    is_terminal_failure: bool = False
    
# Конфигурация правил
MONITORING_RULES = {
    ServerStatus.ERROR: MonitoringRule(
        status=ServerStatus.ERROR,
        is_terminal_failure=True,
        max_stable_iterations=1
    ),
    ServerStatus.UPDATE: MonitoringRule(
        status=ServerStatus.UPDATE,
        max_stable_iterations=3,
        timeout_minutes=120
    ),
    ServerStatus.CCM_RESTART: MonitoringRule(
        status=ServerStatus.CCM_RESTART,
        action_required=True,
        action_commands_file=FILES["ccm_restart_commands"],
        max_stable_iterations=1
    ),
    # ... остальные правила
}

class ConfigurableStatusMonitor:
    """Монитор с конфигурируемыми правилами"""
    
    def __init__(self, updater_instance, rules: Dict[ServerStatus, MonitoringRule]):
        self.updater = updater_instance
        self.rules = rules
        self.context = None
    
    def monitor_with_rules(self, current_servers: List[Dict]) -> bool:
        """Мониторинг с использованием правил"""
        self.context = MonitoringContext(current_servers=current_servers)
        
        while self.context.state not in [MonitoringState.SUCCESS, MonitoringState.FAILED]:
            self._check_all_statuses()
            
            if self.context.state == MonitoringState.MONITORING:
                time.sleep(STATUS_CHECK_INTERVAL)
        
        return self.context.state == MonitoringState.SUCCESS
    
    def _check_all_statuses(self):
        """Проверка всех статусов по правилам"""
        # Получаем текущее состояние
        self.updater.get_nodes_from_file()
        self.updater.save_status_lists(prefix=FILES["status_prefix"])
        
        for status, rule in self.rules.items():
            servers = self._get_servers_for_status(status)
            if self._process_status_by_rule(status, servers, rule):
                break  # Если статус изменился, прерываем проверку
    
    def _process_status_by_rule(self, status: ServerStatus, servers: List[str], rule: MonitoringRule) -> bool:
        """Обработка статуса по правилу"""
        if not servers:
            return False
        
        if rule.is_terminal_failure:
            logger.error(f"Критическая ошибка для статуса {status.value}: {servers}")
            self.context.state = MonitoringState.FAILED
            return True
        
        tracker = self.context.trackers[status]
        if tracker.update(set(servers)):
            if rule.action_required:
                logger.info(f"Выполнение действий для статуса {status.value}")
                # Выполняем действие
                return False  # Продолжаем мониторинг
            else:
                logger.error(f"Таймаут для статуса {status.value}: {servers}")
                self.context.state = MonitoringState.FAILED
                return True
        
        return False