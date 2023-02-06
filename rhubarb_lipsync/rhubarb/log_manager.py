import logging
from types import ModuleType
from functools import cached_property


class LogManager:
    """Manages loggers from the plugins modules. Allows to batch-get/set log levels"""

    def __init__(self) -> None:
        self.modules: list[ModuleType] = []

    def init(self, modules: list[ModuleType]):
        self.modules = modules

    @cached_property
    def logs(self) -> list[logging.Logger]:
        return [m.log for m in self.modules if hasattr(m, 'log')]

    @property
    def current_level(self) -> int:
        if not self.logs:
            return logging.NOTSET
        return self.logs[0].level  # The (random) first logger's level

    @property
    def current_level_name(self) -> int:
        return LogManager.level2name(self.current_level)

    @property
    def current_level_max(self) -> int:
        """The maximal (most verbose) logging level of the managed loggers curently set"""
        if not self.logs:
            return logging.NOTSET

        # Find the logger with the biggest level value
        max_level_logger = max(self.logs, key=lambda l: l.level)
        return max_level_logger.level

    @property
    def current_level_max_name(self) -> int:
        return LogManager.level2name(self.current_level_max)

    def set_level(self, level: int):
        for l in self.logs:
            try:
                l.setLevel(level)

            except Exception as e:
                print(f"Failed to set log level for '{l}': \n{e}")

    @staticmethod
    def level2name(level: int) -> str:
        return logging._levelToName.get(level, "?")


logManager = LogManager()
