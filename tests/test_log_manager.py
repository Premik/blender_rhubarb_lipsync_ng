import contextlib
import io
import logging
import pathlib
import shutil
import tempfile
import unittest
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest import mock

import bpy

import rhubarb_lipsync
from rhubarb_lipsync import init_loggers
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences
from rhubarb_lipsync.rhubarb.log_manager import LogManager, logManager

ABSENT = object()
LOGGER_PREFIX = 'rlps_test_'


def make_module(name: str) -> ModuleType:
    """Fake addon module with a logger, as expected by LogManager.init()."""
    module = ModuleType(f"{LOGGER_PREFIX}{name}")
    module.log = logging.getLogger(module.__name__)  # type: ignore
    return module


def make_third_party_trace() -> Any:
    """A trace method like another addon may have installed on the Logger class."""

    def third_party_trace(logger, message, *args, **kwargs) -> None:
        pass

    third_party_trace.__qualname__ = 'third_party_trace'
    return third_party_trace


def clear_trace() -> None:
    """Simulates a fresh interpreter where no TRACE registration exists yet."""
    for owner, name in [(logging, 'TRACE'), (logging, 'trace'), (logging.getLoggerClass(), 'trace')]:
        if hasattr(owner, name):
            delattr(owner, name)


class LoggingStateSnapshot:
    """Snapshot of the logging state pieces ensure_trace() touches, so tests can restore them."""

    def __init__(self) -> None:
        logger_class = logging.getLoggerClass()
        self.slots: list[tuple[Any, str, Any]] = [
            (logging, 'TRACE', getattr(logging, 'TRACE', ABSENT)),
            (logging, 'trace', getattr(logging, 'trace', ABSENT)),
            (logger_class, 'trace', getattr(logger_class, 'trace', ABSENT)),
        ]
        self.level_to_name = dict(logging._levelToName)
        self.name_to_level = dict(logging._nameToLevel)

    def restore(self) -> None:
        for owner, name, value in self.slots:
            if value is ABSENT:
                if hasattr(owner, name):
                    delattr(owner, name)
            else:
                setattr(owner, name, value)
        logging._levelToName.clear()
        logging._levelToName.update(self.level_to_name)
        logging._nameToLevel.clear()
        logging._nameToLevel.update(self.name_to_level)


class EnsureTraceTest(unittest.TestCase):
    """TRACE registration must tolerate third-party state, never raise and never clobber."""

    def setUp(self) -> None:
        self.snapshot = LoggingStateSnapshot()

    def tearDown(self) -> None:
        self.snapshot.restore()

    def test_third_party_logger_method_only(self) -> None:
        # The state from the support ticket: only Logger.trace exists, the level does not
        clear_trace()
        third_party = make_third_party_trace()
        logging.getLoggerClass().trace = third_party

        with contextlib.redirect_stdout(io.StringIO()) as captured:
            LogManager.ensure_trace()  # Must not raise

        assert hasattr(logging, 'TRACE')
        assert hasattr(logging, 'trace')
        assert logging.TRACE == LogManager.TRACE_LEVEL
        assert logging.getLoggerClass().trace is third_party  # The third-party method is kept
        output = captured.getvalue()
        assert 'already (partially) defined' in output
        assert 'third_party_trace' in output  # Culprit identification

    def test_third_party_level_value_reused(self) -> None:
        # A third party registered only the level, with a non-default value
        clear_trace()
        logging.addLevelName(3, 'TRACE')
        logging.TRACE = 3

        with contextlib.redirect_stdout(io.StringIO()) as captured:
            LogManager.ensure_trace()

        assert logging.TRACE == 3  # Pre-existing value reused, not clobbered
        assert callable(logging.trace)
        assert callable(logging.getLoggerClass().trace)
        assert 'already (partially) defined' in captured.getvalue()

    def test_third_party_level_without_name_mapping(self) -> None:
        # A third party set only the TRACE attribute, without calling addLevelName()
        clear_trace()
        logging.TRACE = 3

        with contextlib.redirect_stdout(io.StringIO()) as captured:
            LogManager.ensure_trace()

        assert logging.TRACE == 3
        assert logging.getLevelName(3) == 'TRACE'  # The name mapping got fixed
        assert logging._nameToLevel['TRACE'] == 3
        assert callable(logging.trace)
        assert callable(logging.getLoggerClass().trace)
        assert 'already (partially) defined' in captured.getvalue()

    def test_own_registration_is_silent(self) -> None:
        # Our import-time registration is in place, like after a Blender scripts reload
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            LogManager.ensure_trace()
        assert captured.getvalue() == ''

    def test_invalid_level_types_are_replaced(self) -> None:
        # A non-int level attr would break isEnabledFor()/setLevel() downstream
        for bad in ('TRACE', None, True, [], 15.0):
            with self.subTest(bad=bad):
                clear_trace()
                logging.TRACE = bad
                with contextlib.redirect_stdout(io.StringIO()) as captured:
                    LogManager.ensure_trace()  # Must not raise
                assert logging.TRACE == LogManager.TRACE_LEVEL
                assert callable(logging.trace)
                assert callable(logging.getLoggerClass().trace)
                output = captured.getvalue()
                assert 'RLPS: Warning' in output
                assert 'invalid definitions' in output

    def test_invalid_methods_are_replaced(self) -> None:
        clear_trace()
        logging.trace = 'not a function'
        logging.getLoggerClass().trace = None

        with contextlib.redirect_stdout(io.StringIO()) as captured:
            LogManager.ensure_trace()

        assert callable(logging.trace)
        assert callable(logging.getLoggerClass().trace)
        output = captured.getvalue()
        assert 'invalid definitions' in output
        assert 'not callable' in output

    def test_callable_module_method_is_kept(self) -> None:
        clear_trace()
        third_party = make_third_party_trace()
        logging.trace = third_party

        with contextlib.redirect_stdout(io.StringIO()):
            LogManager.ensure_trace()

        assert logging.trace is third_party  # Working third-party method is not clobbered
        assert callable(logging.getLoggerClass().trace)

    def test_other_level_name_is_replaced(self) -> None:
        clear_trace()
        logging.addLevelName(15, 'VERBOSE')
        logging.TRACE = 15

        with contextlib.redirect_stdout(io.StringIO()) as captured:
            LogManager.ensure_trace()

        assert logging.getLevelName(15) == 'TRACE'
        assert 'invalid definitions' in captured.getvalue()

    def test_broken_reverse_level_mapping_is_fixed(self) -> None:
        # The level->name direction can look fine while name->level points elsewhere
        clear_trace()
        logging.addLevelName(15, 'TRACE')
        logging.addLevelName('BOGUS', 'TRACE')
        logging.TRACE = 15

        with contextlib.redirect_stdout(io.StringIO()) as captured:
            LogManager.ensure_trace()

        assert logging.getLevelName(15) == 'TRACE'
        assert logging.getLevelName('TRACE') == 15
        assert logging._nameToLevel['TRACE'] == 15
        assert 'invalid definitions' in captured.getvalue()


class SetTraceTest(unittest.TestCase):
    """set_trace() must not propagate an invalid TRACE attribute into Logger.setLevel()."""

    def test_set_trace_ignores_invalid_level_attr(self) -> None:
        manager = LogManager()
        modules = [make_module('set_trace')]
        manager.init(modules)
        self.addCleanup(manager.remove_console_handler)
        saved = logging.TRACE
        logging.TRACE = 'TRACE'
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                manager.set_trace()
        finally:
            logging.TRACE = saved
        assert modules[0].log.level == LogManager.TRACE_LEVEL


class ReInitTest(unittest.TestCase):
    """Re-init with a new module set must not leave handlers attached to stale loggers."""

    def setUp(self) -> None:
        self.manager = LogManager()
        self.old_modules = [make_module('reinit_old_a'), make_module('reinit_old_b')]
        self.new_modules = [make_module('reinit_new_a'), make_module('reinit_new_b')]
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix=LOGGER_PREFIX))
        self.addCleanup(self.cleanup)

    def cleanup(self) -> None:
        self.manager.remove_console_handler()
        self.manager.disable_log_file()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_first_init_is_silent(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            self.manager.init(self.old_modules)
        assert captured.getvalue() == ''

    def test_reinit_detaches_handlers_and_serves_the_new_set(self) -> None:
        manager = self.manager
        manager.init(self.old_modules)
        manager.set_level(logging.INFO)  # Attaches the console handler
        manager.log_file_path = self.tmp / 'old.log'
        manager.enable_log_file()
        old_file_handler = manager.file_handler
        assert old_file_handler is not None
        old_logs = [m.log for m in self.old_modules]
        assert all(manager.console_handler in log.handlers for log in old_logs)
        assert all(old_file_handler in log.handlers for log in old_logs)

        with contextlib.redirect_stdout(io.StringIO()) as captured:
            manager.init(self.new_modules)  # Swap the module set
        assert 'Removed console handler from 2 loggers' in captured.getvalue()

        assert manager.file_handler is None
        assert all(manager.console_handler not in log.handlers for log in old_logs)
        assert all(old_file_handler not in log.handlers for log in old_logs)

        manager.set_level(logging.WARNING)  # New set receives the console handler again
        new_logs = [m.log for m in self.new_modules]
        assert all(manager.console_handler in log.handlers for log in new_logs)
        assert all(manager.console_handler not in log.handlers for log in old_logs)


class LogFilePrefTest(unittest.TestCase):
    """The saved log_file pref must (re-)apply to the current logger set, like init_loggers() does."""

    def setUp(self) -> None:
        self.saved_modules = logManager.modules
        self.first_modules = [make_module('pref_first')]
        self.modules = [make_module('pref_a'), make_module('pref_b')]
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix=LOGGER_PREFIX))
        self.addCleanup(self.cleanup)

    def cleanup(self) -> None:
        logManager.disable_log_file()
        logManager.remove_console_handler()
        logManager.log_file_path = None
        logManager.init(self.saved_modules)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def apply_pref(self, log_file: str) -> None:
        """Applies the pref via the real update callback, the way init_loggers() does."""
        prefs = SimpleNamespace(log_file=log_file)
        RhubarbAddonPreferences.log_file_updated(prefs, None)

    def test_pref_reapplied_after_reinit(self) -> None:
        logManager.init(self.first_modules)
        self.apply_pref(str(self.tmp / 'first.log'))
        first_handler = logManager.file_handler
        assert first_handler is not None

        logManager.init(self.modules)  # Swap the logger set, like a re-registration
        assert logManager.file_handler is None
        assert all(first_handler not in m.log.handlers for m in self.first_modules)

        self.apply_pref(str(self.tmp / 'new.log'))  # What init_loggers() does after init()

        file_handler = logManager.file_handler
        assert file_handler is not None
        assert file_handler is not first_handler  # A new handler for the new set
        assert all(m.log.handlers.count(file_handler) == 1 for m in self.modules)  # Attached exactly once
        assert all(file_handler not in m.log.handlers for m in self.first_modules)  # Old loggers unaffected

    def test_empty_pref_disables_file_logging(self) -> None:
        logManager.init(self.modules)
        logManager.log_file_path = self.tmp / 'stale.log'  # Left over from before
        self.apply_pref('')
        assert logManager.log_file_path is None
        assert logManager.file_handler is None

    def test_invalid_pref_is_contained(self) -> None:
        logManager.init(self.modules)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.apply_pref(str(self.tmp))  # A directory, not a file
        assert logManager.file_handler is None  # register() must not fail on a broken saved pref


class InitLoggersTest(unittest.TestCase):
    """init_loggers() must (re-)apply the log_file pref after re-initializing the loggers."""

    def test_log_file_pref_applied_after_logger_init(self) -> None:
        modules = [make_module('initloggers_a')]
        calls: list[Any] = []
        manager = mock.MagicMock()
        manager.init.side_effect = lambda mods: calls.append('init')
        prefs = SimpleNamespace(log_file='/dev/null/rlps_test.log', log_file_updated=lambda ctx: calls.append(ctx))

        saved_autoloader = getattr(rhubarb_lipsync, 'autoloader', ABSENT)
        saved_manager = rhubarb_lipsync.logManager
        rhubarb_lipsync.autoloader = SimpleNamespace(modules=modules)
        rhubarb_lipsync.logManager = manager
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                init_loggers(prefs)
        finally:
            rhubarb_lipsync.logManager = saved_manager
            if saved_autoloader is ABSENT:
                del rhubarb_lipsync.autoloader
            else:
                rhubarb_lipsync.autoloader = saved_autoloader

        manager.init.assert_called_once_with(modules)
        assert calls[0] == 'init'  # The logger set is swapped before the pref is applied
        assert calls[1] is bpy.context  # The real update callback receives the context


if __name__ == '__main__':
    unittest.main()
