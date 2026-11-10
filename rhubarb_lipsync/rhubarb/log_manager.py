import logging
import pathlib
import sys
from dataclasses import dataclass, field
from functools import cached_property
from types import ModuleType
from typing import Callable, Optional


@dataclass
class RegistrationReport:
    """Which pieces of a custom log level were reused and which were force-fixed."""

    preexisting: list[str] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)


@dataclass
class CustomLogLevel:
    """Registers a custom logging level, reusing valid existing definitions and fixing broken ones."""

    name: str
    default_level: int

    @property
    def method_name(self) -> str:
        return self.name.lower()

    @property
    def existing_level(self) -> object:
        """The raw pre-existing level attribute, without any validation."""
        return getattr(logging, self.name, None)

    @property
    def level(self) -> int:
        """The pre-existing level if it is a valid int, otherwise the default."""
        raw = self.existing_level
        return raw if type(raw) is int else self.default_level

    @property
    def logger_class(self) -> type[logging.Logger]:
        return logging.getLoggerClass()

    @property
    def logger_method(self) -> Optional[Callable]:
        return getattr(self.logger_class, self.method_name, None)

    @property
    def module_method(self) -> Optional[Callable]:
        return getattr(logging, self.method_name, None)

    @property
    def is_our_registration(self) -> bool:
        """Whether the level was already registered by this module, e.g. after a scripts reload."""
        return self.is_our_code(self.module_method) and self.is_our_code(self.logger_method)

    @staticmethod
    def describe_symbol(obj: object) -> str:
        """Best-effort identification of where a class or function was defined."""
        module = getattr(obj, '__module__', '?')
        qualname = getattr(obj, '__qualname__', '?')
        filename = getattr(getattr(obj, '__code__', None), 'co_filename', None)
        if not filename:
            return f"{module}.{qualname}"
        return f"{module}.{qualname} (from {filename})"

    @staticmethod
    def is_our_code(obj: object) -> bool:
        filename = getattr(getattr(obj, '__code__', None), 'co_filename', None)
        if not filename:
            return False
        return pathlib.Path(filename).resolve() == pathlib.Path(__file__).resolve()

    def make_logger_method(self, level: int) -> Callable:
        def log_for_level(logger, message, *args, **kwargs) -> None:
            if logger.isEnabledFor(level):
                logger._log(level, message, args, **kwargs)

        return log_for_level

    def make_module_method(self, level: int) -> Callable:
        def log_to_root(message, *args, **kwargs) -> None:
            logging.log(level, message, *args, **kwargs)

        return log_to_root

    def register_missing(self) -> RegistrationReport:
        """Registers missing pieces and replaces invalid ones."""
        report = RegistrationReport()
        self.ensure_level(report)
        self.ensure_level_name(report)
        self.ensure_module_method(report)
        self.ensure_logger_method(report)
        return report

    def ensure_level(self, report: RegistrationReport) -> None:
        if not hasattr(logging, self.name):
            setattr(logging, self.name, self.default_level)
            return
        raw = self.existing_level
        if type(raw) is int:
            report.preexisting.append(f"{self.name}={raw}")
            return
        setattr(logging, self.name, self.default_level)
        report.replaced.append(f"{self.name}={raw!r} ({type(raw).__name__}) -> {self.default_level}")

    def ensure_level_name(self, report: RegistrationReport) -> None:
        level = self.level
        forward = logging.getLevelName(level)  # level -> name
        backward = logging.getLevelName(self.name)  # name -> level
        if forward == self.name and backward == level:
            return
        if forward not in (f"Level {level}", self.name):
            report.replaced.append(f"level {level} name={forward!r} -> {self.name!r}")
        if backward not in (level, f"Level {self.name}"):
            report.replaced.append(f"name {self.name!r} level={backward!r} -> {level}")
        logging.addLevelName(level, self.name)

    def ensure_module_method(self, report: RegistrationReport) -> None:
        if not hasattr(logging, self.method_name):
            setattr(logging, self.method_name, self.make_module_method(self.level))
            return
        existing = self.module_method
        if callable(existing):
            report.preexisting.append(self.method_name)
            return
        setattr(logging, self.method_name, self.make_module_method(self.level))
        report.replaced.append(f"logging.{self.method_name}={existing!r} (not callable) -> addon implementation")

    def ensure_logger_method(self, report: RegistrationReport) -> None:
        owner = self.logger_class
        if not hasattr(owner, self.method_name):
            setattr(owner, self.method_name, self.make_logger_method(self.level))
            return
        existing = self.logger_method
        if callable(existing):
            report.preexisting.append(f"{self.describe_symbol(owner)}.{self.method_name}")
            return
        setattr(owner, self.method_name, self.make_logger_method(self.level))
        report.replaced.append(f"{self.describe_symbol(owner)}.{self.method_name}={existing!r} (not callable) -> addon implementation")

    def ensure(self) -> None:
        own = self.is_our_registration
        trace_before = self.logger_method
        report = self.register_missing()

        if report.replaced:
            print(
                f"RLPS: Warning: {self.name} logging had invalid definitions "
                f"({', '.join(report.replaced)}). Overwritten with addon defaults."
            )
        reused = bool(report.preexisting) and not own
        if reused:
            print(
                f"RLPS: Warning: {self.name} logging was already (partially) defined before this addon loaded "
                f"({', '.join(report.preexisting)}). Reusing the existing definitions."
            )
        if not (report.replaced or reused):
            return

        print(f"RLPS: {self.name} logger class: {self.describe_symbol(self.logger_class)}")
        if trace_before is not None:
            print(f"RLPS: {self.name} logger method: {self.describe_symbol(trace_before)}")


class LogManager:
    """Manages loggers from the plugins modules. Allows to batch-get/set log levels"""

    TRACE_LEVEL = logging.DEBUG - 5

    def __init__(self) -> None:
        self.modules: list[ModuleType] = []
        self.file_handler: Optional[logging.FileHandler] = None
        self.log_file_path: Optional[pathlib.Path] = None

    def init(self, modules: list[ModuleType]) -> None:
        if self.modules:  # Detach handlers while self.logs still refers to the previous logger set
            self.remove_console_handler()
            self.disable_log_file()
        self.modules = modules

    @property
    def logs(self) -> list[logging.Logger]:
        """Freshly derived from self.modules so re-init() can never serve stale loggers."""
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
        try:
            self.ensure_console_handler()
        except Exception as e:
            print(f"Failed enable console handlers: \n{e}")

    def set_debug(self) -> None:
        self.set_level(logging.DEBUG)

    def set_trace(self) -> None:
        self.set_level(CustomLogLevel('TRACE', LogManager.TRACE_LEVEL).level)

    def validate_log_file(self) -> str:
        p = self.log_file_path
        if not p:
            # return "Log file not specified"
            return ""
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            msg = f"Failed to create parent folders {p.parents}."
            print(f"{msg}\n{e}")
            return msg
        if p.is_dir():
            return f"The '{p}' is not a file"
        return ""

    def enable_log_file(self) -> None:
        err = self.validate_log_file()
        if err:
            raise RuntimeError(f"Invalid log file. {err}")
        fmt = logging.Formatter(logging.BASIC_FORMAT, None, '%')
        self.file_handler = logging.FileHandler(self.log_file_path, encoding="UTF-8")  # type: ignore
        self.file_handler.formatter = fmt
        self.file_handler.setLevel(1)  # All
        try:
            for l in self.logs:
                l.addHandler(self.file_handler)

        except Exception as e:
            msg = "Failed to add log file hander"
            self.file_handler = None
            print(f"{msg}\n{e}")
            raise
        print(f"Set {self.log_file_path} file handler on {len(self.logs)} loggers")

    def disable_log_file(self) -> None:
        if not self.file_handler:
            return
        try:
            for l in self.logs:
                l.removeHandler(self.file_handler)
        except Exception as e:
            print(f"Failed to remove log file handler\n{e}")
        finally:
            self.file_handler = None

    @property
    def log_file_status(self) -> str:
        if not self.log_file_path:
            return "DISABLED"
        errors = self.validate_log_file()
        if errors:
            return "ERROR"
        if self.file_handler is not None:
            return "ENABLED"
        return "FAILED"

    @cached_property
    def console_handler(self) -> logging.StreamHandler:
        console_formatter = logging.Formatter(logging.BASIC_FORMAT)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(1)  # All
        return console_handler

    def ensure_console_handler(self) -> None:
        added = 0
        for logger in self.logs:
            if not any(handler == self.console_handler for handler in logger.handlers):
                logger.addHandler(self.console_handler)
                added += 1
        print(f"Added console handler on {added} loggers.")

    def remove_console_handler(self) -> None:
        """Removes the console handler from all loggers."""
        removed = 0
        for logger in self.logs:
            if any(handler == self.console_handler for handler in logger.handlers):
                logger.removeHandler(self.console_handler)
                removed += 1
        print(f"Removed console handler from {removed} loggers.")

    @staticmethod
    def level2name(level: int) -> str:
        return logging._levelToName.get(level, "?")

    @staticmethod
    def ensure_trace() -> None:
        CustomLogLevel('TRACE', LogManager.TRACE_LEVEL).ensure()


logManager = LogManager()
logManager.ensure_trace()
