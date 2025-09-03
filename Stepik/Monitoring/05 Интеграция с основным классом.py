# В классе UnifiedServerUpdater
def _monitor_update_status_optimized(self, current_part_server: List[Dict]) -> bool:
    """Оптимизированный мониторинг статусов"""
    monitor = ConfigurableStatusMonitor(self, MONITORING_RULES)
    return monitor.monitor_with_rules(current_part_server)

# Заменяем вызов в основном методе
def update_servers_part_server(self) -> bool:
    # ... существующий код ...
    
    # Заменяем строку:
    # if not self._monitor_update_status(current_part_server):
    # На:
    if not self._monitor_update_status_optimized(current_part_server):
        return False
    
    # ... остальной код ...