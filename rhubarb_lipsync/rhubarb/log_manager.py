import logging
from functools import cached_property
from types import ModuleType


# https://stackoverflow.com/questions/2183233/how-to-add-a-custom-loglevel-to-pythons-logging-facility/35804945#35804945
def addLoggingLevel(levelName, levelNum, methodName=None) -> None:
    """
    Comprehensively adds a new logging level to the `logging` module and the
    currently configured logging class.

    `levelName` becomes an attribute of the `logging` module with the value
    `levelNum`. `methodName` becomes a convenience method for both `logging`
    itself and the class returned by `logging.getLoggerClass()` (usually just
    `logging.Logger`). If `methodName` is not specified, `levelName.lower()` is
    used.

    To avoid accidental clobberings of existing attributes, this method will
    raise an `AttributeError` if the level name is already an attribute of the
    `logging` module or if the method name is already present

    Example
    -------
    >>> addLoggingLevel('TRACE', logging.DEBUG - 5)
    >>> logging.getLogger(__name__).setLevel("TRACE")
    >>> logging.getLogger(__name__).trace('that worked')
    >>> logging.trace('so did this')
    >>> logging.TRACE
    5

    """
    if not methodName:
        methodName = levelName.lower()

    if hasattr(logging, levelName):
        raise AttributeError('{} already defined in logging module'.format(levelName))
    if hasattr(logging, methodName):
        raise AttributeError('{} already defined in logging module'.format(methodName))
    if hasattr(logging.getLoggerClass(), methodName):
        raise AttributeError('{} already defined in logger class'.format(methodName))

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def logForLevel(self, message, *args, **kwargs) -> None:
        if self.isEnabledFor(levelNum):
            self._log(levelNum, message, args, **kwargs)

    def logToRoot(message, *args, **kwargs) -> None:
        logging.log(levelNum, message, *args, **kwargs)

    logging.addLevelName(levelNum, levelName)
    setattr(logging, levelName, levelNum)
    setattr(logging.getLoggerClass(), methodName, logForLevel)
    setattr(logging, methodName, logToRoot)


class LogManager:
    """Manages loggers from the plugins modules. Allows to batch-get/set log levels"""

    TRACE_LEVEL = logging.DEBUG - 5

    def __init__(self) -> None:
        self.modules: list[ModuleType] = []

    def init(self, modules: list[ModuleType]) -> None:
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
    def current_level_name(self) -> str:
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
    def current_level_max_name(self) -> str:
        return LogManager.level2name(self.current_level_max)

    def set_level(self, level: int) -> None:
        for l in self.logs:
            try:
                l.setLevel(level)

            except Exception as e:
                print(f"Failed to set log level for '{l}': \n{e}")

    def set_debug(self) -> None:
        self.set_level(logging.DEBUG)

    @staticmethod
    def level2name(level: int) -> str:
        return logging._levelToName.get(level, "?")

    @staticmethod
    def ensure_trace() -> None:
        if not hasattr(logging, 'TRACE'):
            addLoggingLevel('TRACE', LogManager.TRACE_LEVEL)


logManager = LogManager()
logManager.ensure_trace()
