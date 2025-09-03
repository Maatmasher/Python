from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, Set, Optional, Callable
from abc import ABC, abstractmethod

class ServerStatus(Enum):
    WORK = "work"
    ERROR = "error" 
    UPDATE = "update"
    CCM_RESTART = "ccm"
    UNZIP = "unzip"
    NO_UPDATE_NEEDED = "no_update_needed"
    UNAVAILABLE = "unavailable"

class MonitoringState(Enum):
    STARTING = auto()
    MONITORING = auto()
    SUCCESS = auto()
    FAILED = auto()
    REQUIRES_ACTION = auto()

@dataclass
class StatusTracker:
    """Отслеживание состояния для конкретного статуса"""
    current_servers: Set[str] = field(default_factory=set)
    previous_servers: Set[str] = field(default_factory=set)
    counter: int = 0
    max_retries: int = 2
    is_stable: bool = False
    
    def update(self, servers: Set[str]) -> bool:
        """Обновляет состояние и возвращает True если состояние стабильно"""
        if servers == self.previous_servers:
            self.counter += 1
        else:
            self.counter = 0
            self.previous_servers = servers.copy()
        
        self.current_servers = servers
        self.is_stable = self.counter >= self.max_retries
        return self.is_stable

@dataclass 
class MonitoringContext:
    """Контекст мониторинга для хранения состояния"""
    current_servers: List[Dict] = field(default_factory=list)
    trackers: Dict[ServerStatus, StatusTracker] = field(default_factory=dict)
    state: MonitoringState = MonitoringState.STARTING
    iteration_count: int = 0
    
    def __post_init__(self):
        # Инициализация трекеров для каждого статуса
        for status in ServerStatus:
            self.trackers[status] = StatusTracker()