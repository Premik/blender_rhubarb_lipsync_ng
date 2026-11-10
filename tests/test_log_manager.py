import contextlib
import functools
import inspect
import io
import logging
import pathlib
import re
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
from rhubarb_lipsync.rhubarb.log_manager import CustomLogLevel, LogManager, logManager

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
        assert 'builtins.?' not in output  # Non-callables must not get a bogus symbol line
        assert '?.?' not in output

    def test_callable_module_method_is_kept(self) -> None:
        clear_trace()
        third_party = make_third_party_trace()
        logging.trace = third_party

        with contextlib.redirect_stdout(io.StringIO()) as captured:
            LogManager.ensure_trace()

        assert logging.trace is third_party  # Working third-party method is not clobbered
        assert callable(logging.getLoggerClass().trace)
        assert 'third_party_trace' in captured.getvalue()  # Culprit identification

    def test_partial_third_party_overwrite_is_not_blamed_on_us(self) -> None:
        # The addon registration is in place, then a third party overwrites only one of the two methods
        for target in ('module', 'logger'):
            with self.subTest(target=target):
                self.snapshot.restore()
                owner = logging if target == 'module' else logging.getLoggerClass()
                owner.trace = make_third_party_trace()  # type: ignore

                with contextlib.redirect_stdout(io.StringIO()) as captured:
                    LogManager.ensure_trace()

                output = captured.getvalue()
                assert 'third_party_trace' in output
                assert 'log_to_root' not in output  # Own pieces are not reported as clashes
                assert 'log_for_level' not in output
                assert 'TRACE=5' not in output

    def test_preexisting_methods_are_described_with_source(self) -> None:
        clear_trace()
        logging.trace = make_third_party_trace()
        logging.getLoggerClass().trace = make_third_party_trace()

        with contextlib.redirect_stdout(io.StringIO()) as captured:
            LogManager.ensure_trace()

        output = captured.getvalue()
        assert re.search(r'logging\.trace=\S*third_party_trace \(from .*test_log_manager\.py\)', output)
        assert re.search(r'logging\.Logger\.trace=\S*third_party_trace \(from .*test_log_manager\.py\)', output)
        assert 'logger class' not in output  # The standard logging.Logger is not worth reporting

    def test_pathological_wrapped_attributes_do_not_block_registration(self) -> None:
        class CyclicTrace:
            def __call__(self, *args, **kwargs) -> None:
                pass

        class ExplodingTrace:
            @property
            def __wrapped__(self):
                raise RuntimeError('boom')

            def __call__(self, *args, **kwargs) -> None:
                pass

        class ExplodingCode:
            @property
            def __code__(self):
                raise RuntimeError('boom')

            def __call__(self, *args, **kwargs) -> None:
                pass

        cyclic = CyclicTrace()
        cyclic.__wrapped__ = cyclic
        self.assert_trace_survives(cyclic)
        self.assert_trace_survives(ExplodingTrace())
        self.assert_trace_survives(ExplodingCode())

    def test_mixed_partial_and_wraps_cycle_does_not_hang(self) -> None:
        def wrapped(*args, **kwargs) -> None:
            pass

        cyclic_partial = functools.partial(wrapped)
        wrapped.__wrapped__ = cyclic_partial  # type: ignore

        self.assert_trace_survives(cyclic_partial)

    def assert_trace_survives(self, broken: object) -> None:
        self.snapshot.restore()
        clear_trace()
        logging.trace = broken  # type: ignore
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            LogManager.ensure_trace()  # Must not raise
        assert callable(logging.getLoggerClass().trace)
        assert type(broken).__name__ in captured.getvalue()

    def test_foreign_wrapper_around_own_method_names_both_sources(self) -> None:
        clear_trace()
        own = CustomLogLevel('TRACE', LogManager.TRACE_LEVEL).make_module_method(LogManager.TRACE_LEVEL)

        @functools.wraps(own)
        def wrapper(*args, **kwargs) -> None:
            pass

        logging.trace = wrapper

        with contextlib.redirect_stdout(io.StringIO()) as captured:
            LogManager.ensure_trace()

        output = captured.getvalue()
        assert re.search(
            r'logging\.trace=\S*log_to_root \(from .*test_log_manager\.py\) -> \S*log_to_root \(from .*log_manager\.py\)',
            output,
        )

    def test_nonstandard_logger_class_is_named(self) -> None:
        clear_trace()

        class CustomLogger(logging.Logger):
            pass

        logging.setLoggerClass(CustomLogger)
        self.addCleanup(logging.setLoggerClass, logging.Logger)
        logging.trace = make_third_party_trace()

        with contextlib.redirect_stdout(io.StringIO()) as captured:
            LogManager.ensure_trace()

        output = captured.getvalue()
        assert 'logger class:' in output
        assert 'CustomLogger' in output

    def test_partial_overwrite_rebinds_own_surviving_method(self) -> None:
        # A level change must reach whichever of the two methods the addon still defines
        for target in ('module', 'logger'):
            with self.subTest(target=target):
                self.snapshot.restore()
                foreign = make_third_party_trace()
                owner = logging if target == 'module' else logging.getLoggerClass()
                owner.trace = foreign  # type: ignore
                logging.TRACE = 3

                with contextlib.redirect_stdout(io.StringIO()):
                    LogManager.ensure_trace()

                assert owner.trace is foreign  # The foreign method is kept
                surviving = logging.getLoggerClass().trace if target == 'module' else logging.trace
                assert inspect.getclosurevars(surviving).nonlocals['level'] == 3

    def test_own_methods_are_rebound_to_the_current_level(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            LogManager.ensure_trace()
        logging.TRACE = 3  # A third party changed the level after the addon registration

        with contextlib.redirect_stdout(io.StringIO()):
            LogManager.ensure_trace()

        assert inspect.getclosurevars(logging.trace).nonlocals['level'] == 3
        assert inspect.getclosurevars(logging.getLoggerClass().trace).nonlocals['level'] == 3

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


class DescribeSymbolTest(unittest.TestCase):
    """describe_symbol() must point at the real implementation and survive odd callables."""

    def test_functools_wraps_wrapper_points_at_the_wrapped_function(self) -> None:
        namespace: dict[str, Any] = {'__name__': 'fake_third_party'}
        code = compile('def third_party_trace(*args, **kwargs): pass', 'fake_third_party.py', 'exec')
        exec(code, namespace)
        wrapped = namespace['third_party_trace']

        @functools.wraps(wrapped)
        def wrapper(*args, **kwargs) -> None:
            pass

        symbol = CustomLogLevel.describe_symbol(wrapper)
        assert symbol.startswith('fake_third_party.third_party_trace (from ')
        assert 'test_log_manager.py' in symbol  # The outer wrapper is reported
        assert symbol.endswith(' -> fake_third_party.third_party_trace (from fake_third_party.py)')

    def test_partial_layers_point_at_the_wrapped_function(self) -> None:
        def third_party_trace(*args, **kwargs) -> None:
            pass

        symbol = CustomLogLevel.describe_symbol(functools.partial(functools.partial(third_party_trace)))
        assert symbol.startswith('functools.partial -> ')
        assert '.third_party_trace (from ' in symbol

    def test_callable_instance_falls_back_to_its_class(self) -> None:
        class ThirdPartyTrace:
            def __call__(self, *args, **kwargs) -> None:
                pass

        symbol = CustomLogLevel.describe_symbol(ThirdPartyTrace())
        assert symbol == f'{__name__}.DescribeSymbolTest.test_callable_instance_falls_back_to_its_class.<locals>.ThirdPartyTrace'

    def test_foreign_wrapper_of_own_code_is_still_foreign(self) -> None:
        own = CustomLogLevel('TRACE', LogManager.TRACE_LEVEL).make_module_method(LogManager.TRACE_LEVEL)

        @functools.wraps(own)
        def wrapper(*args, **kwargs) -> None:
            pass

        assert CustomLogLevel.is_own_code(own)
        assert not CustomLogLevel.is_own_code(wrapper)  # Display-only unwrapping must not blur ownership
        symbol = CustomLogLevel.describe_symbol(wrapper)
        assert 'test_log_manager.py' in symbol  # The foreign wrapper is named
        assert 'log_manager.py' in symbol  # Alongside the own implementation it unwraps to

    def test_malformed_filename_is_not_own_code(self) -> None:
        class BadCode:
            co_filename = '\0not-a-path'

        broken = SimpleNamespace(__code__=BadCode())
        assert not CustomLogLevel.is_own_code(broken)


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
        # A mocked failing removeHandler can leave a closed handler attached to a shared logger
        for module in self.old_modules + self.new_modules:
            for handler in list(module.log.handlers):
                if isinstance(handler, logging.FileHandler):
                    module.log.removeHandler(handler)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_disable_log_file_closes_the_handler(self) -> None:
        manager = self.manager
        manager.init(self.old_modules)
        manager.log_file_path = self.tmp / 'close.log'
        manager.enable_log_file()
        handler = manager.file_handler
        assert handler is not None

        manager.disable_log_file()

        assert handler.stream is None  # Closed, so the fd and the Windows file lock are released

    def test_failed_enable_detaches_and_closes_the_handler(self) -> None:
        manager = self.manager
        manager.init(self.old_modules)
        manager.log_file_path = self.tmp / 'fail.log'
        created: list[logging.FileHandler] = []
        real_handler = logging.FileHandler

        def make_handler(*args, **kwargs) -> logging.FileHandler:
            handler = real_handler(*args, **kwargs)
            created.append(handler)
            return handler

        with mock.patch(
            'rhubarb_lipsync.rhubarb.log_manager.logging.FileHandler', side_effect=make_handler
        ), mock.patch.object(self.old_modules[1].log, 'addHandler', side_effect=RuntimeError('boom')):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
                manager.enable_log_file()

        assert manager.file_handler is None
        assert created[0].stream is None  # Closed instead of leaked on the failure path
        for module in self.old_modules:
            assert not any(isinstance(h, logging.FileHandler) for h in module.log.handlers)

    def test_failed_enable_closes_handler_even_if_detaching_fails(self) -> None:
        manager = self.manager
        manager.init(self.old_modules)
        manager.log_file_path = self.tmp / 'fail_detach.log'
        created: list[logging.FileHandler] = []
        real_handler = logging.FileHandler

        def make_handler(*args, **kwargs) -> logging.FileHandler:
            handler = real_handler(*args, **kwargs)
            created.append(handler)
            return handler

        with mock.patch(
            'rhubarb_lipsync.rhubarb.log_manager.logging.FileHandler', side_effect=make_handler
        ), mock.patch.object(self.old_modules[1].log, 'addHandler', side_effect=RuntimeError('boom')), mock.patch.object(
            self.old_modules[0].log, 'removeHandler', side_effect=RuntimeError('detach boom')
        ), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            manager.enable_log_file()

        assert manager.file_handler is None
        assert created[0].stream is None  # A failing detach must not skip the close

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
        assert old_file_handler.stream is None  # Closed after being detached, so no fd is leaked
        assert all(manager.console_handler not in log.handlers for log in old_logs)
        assert all(old_file_handler not in log.handlers for log in old_logs)

        manager.set_level(logging.WARNING)  # New set receives the console handler again
        new_logs = [m.log for m in self.new_modules]
        assert all(manager.console_handler in log.handlers for log in new_logs)
        assert all(manager.console_handler not in log.handlers for log in old_logs)


class UnregisterTest(unittest.TestCase):
    """unregister() must release the log file handler too, not only the console one."""

    def test_unregister_disables_file_logging(self) -> None:
        manager = mock.MagicMock()
        patches = mock.patch.multiple(
            rhubarb_lipsync,
            IconsManager=mock.MagicMock(),
            autoloader=mock.MagicMock(),
            DepsgraphHandler=mock.MagicMock(),
            logManager=manager,
            bpy=SimpleNamespace(types=SimpleNamespace(Scene=mock.MagicMock(), Object=mock.MagicMock())),
            create=True,
        )
        with patches, contextlib.redirect_stdout(io.StringIO()):
            rhubarb_lipsync.unregister()  # Must not raise

        manager.remove_console_handler.assert_called_once_with()
        manager.disable_log_file.assert_called_once_with()


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

    def test_switching_log_file_closes_the_previous_handler(self) -> None:
        logManager.init(self.modules)
        self.apply_pref(str(self.tmp / 'a.log'))
        first_handler = logManager.file_handler
        assert first_handler is not None

        self.apply_pref(str(self.tmp / 'b.log'))

        assert first_handler.stream is None
        assert all(first_handler not in m.log.handlers for m in self.modules)

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
