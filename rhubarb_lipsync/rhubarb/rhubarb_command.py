import functools
import json
import logging
import os
import pathlib
import platform
import re
import traceback
from collections import defaultdict
from queue import Empty, SimpleQueue
from subprocess import PIPE, Popen, TimeoutExpired
from threading import Event, Thread
from time import sleep
from typing import Any, Dict, List, Optional

from rhubarb_lipsync.rhubarb.mouth_cues import MouthCue

log = logging.getLogger(__name__)


def thread_loop(func):
    @functools.wraps(func)
    def wrapper(self):
        log.trace(f"Entered {func.__name__} reader thread")  # type: ignore
        while True:
            try:
                if self.cmd.has_finished:
                    log.trace("Process finished")  # type: ignore
                    break
                if self.stop_event.is_set():
                    log.trace("Stop event received")  # type: ignore
                    break  # Cancelled
                func(self)
            except Exception as e:
                log.error(f"Unexpected error in the {func.__name__} thread {e}")
                self.last_exception = e
                traceback.print_exc()
                self.queue.put(("EXCEPTION", e))
                raise
        log.debug(f"{func.__name__} thread exit")

    return wrapper  # Apply staticmethod here


class RhubarbParser:
    version_info_rx = re.compile(r"version\s+(?P<ver>\d+\.\d+\.\d+)")

    LOG_LEVELS_MAP: dict[str, int] = defaultdict(lambda: logging.TRACE)  # type: ignore
    LOG_LEVELS_MAP.update(
        {
            "Fatal": logging.CRITICAL,  # TODO Verify
            "Error": logging.ERROR,
            "Info": logging.INFO,
        }
    )

    @staticmethod
    def parse_version_info(stdout: str) -> str:
        m = re.search(RhubarbParser.version_info_rx, stdout)
        if m is None:
            return ""
        return m.groupdict()["ver"]

    @staticmethod
    def parse_status_infos(stderr: str) -> list[Dict]:
        """Parses the one-line json(s) produced by rhubarb binary.
        Each report is a json on separate line"""
        if not stderr:
            return []
        return [RhubarbParser.parse_status_info_line(l) for l in stderr.splitlines()]

    @staticmethod
    def parse_status_info_line(stderr_line: str) -> Dict[str, Any]:
        if not stderr_line:
            return {}
        try:
            return json.loads(stderr_line)
            # { "type":"start", "file":"1.ogg", "log":{"level":"Info","message": "Application startup." } }
            # { "type": "failure", "reason": ...
            # { "type": "progress", "value": 0.17,
        except json.JSONDecodeError:
            log.exception(f"Failed to parse status line '{stderr_line[:100]}'")
            return {}

    @staticmethod
    def parse_lipsync_json(stdout: str) -> List[Dict]:
        """Parses the main lipsync output json. Return only the list of mouthCues"""
        # { "metadata": { "soundFile": "1.ogg", "duration": 5.68},
        #   "mouthCues": [ { "start": 0.00, "end": 0.28, "value": "X" } ... ] }

        if not stdout:
            return []
        try:
            j = json.loads(stdout)
            if "mouthCues" not in j:
                log.error(f"The json format is unexpected. Missing `mouthCues` key. '{stdout[:200]}...'")
                return []
            return j["mouthCues"]
        except json.JSONDecodeError:
            log.exception(f"Failed to parse main rhubarb output json. '{stdout[:200]}...'")
            return []

    @staticmethod
    def lipsync_json2MouthCues(cues_json: List[Dict]) -> List[MouthCue]:
        return [MouthCue.of_json(c_json) for c_json in cues_json]

    @staticmethod
    def lipsync_json_metadata(sound_file: str, duration: float, version=None) -> Dict[str, Any]:
        """Generate json-dict for the ruharb metadata section"""
        ret = {
            "metadata": {
                "soundFile": sound_file,
                "duration": f"{duration:.2f}",
            }
        }
        if version:
            ret['metadata']['version'] = version
        return ret

    @staticmethod
    def mouth_cues2lipsync_json(cues: List[MouthCue], sound_file="export.ogg", version=None) -> Dict[str, Any]:
        """Unparse the parsed cue list to json-dict"""
        if not cues:
            return RhubarbParser.lipsync_json_metadata(sound_file, 0, version)
        last_cue = cues[-1]
        ret = RhubarbParser.lipsync_json_metadata(sound_file, last_cue.end, version)
        ret['mouthCues'] = [c.to_json() for c in cues]
        return ret

    @staticmethod
    def unparse_mouth_cues(cues: List[MouthCue], sound_file="export.ogg", version=None) -> str:
        json_dic = RhubarbParser.mouth_cues2lipsync_json(cues, sound_file, version)
        return json.dumps(json_dic, indent=2)


class RhubarbCommandWrapper:
    """Wraps low level operations related to the lipsync executable."""

    thread_wait_timeout = 5

    def __init__(self, executable_path: pathlib.Path, recognizer="pocketSphinx", extended=True, extra_args=[]) -> None:
        self.executable_path = executable_path
        self.recognizer = recognizer
        self.use_extended = extended
        self.process: Optional[Popen] = None
        self.stdout = ""
        self.stderr = ""
        self.last_exit_code: Optional[int] = None
        self.extra_args = extra_args

    @staticmethod
    def executable_default_filename() -> str:
        return "rhubarb.exe" if platform.system() == "Windows" else "rhubarb"

    def config_errors(self) -> Optional[str]:
        if not self.executable_path:
            return "Configure the Rhubarb lipsync executable file path in the addon preferences. "

        if not self.executable_path.exists():
            return f"The '{self.executable_path}' doesn't exist."
        if not self.executable_path.is_file():
            return f"The '{self.executable_path}' is not a valid file."
        # Zip doesn't maintain file flags, set as executable
        os.chmod(self.executable_path, 0o744)
        return None

    def build_lipsync_args(self, input_file: str, dialog_file: Optional[str] = None) -> list[str]:
        dialog = ["--dialogFile", dialog_file] if dialog_file else []
        extended = ["--extendedShapes", "GHX" if self.use_extended else ""]
        return [
            str(self.executable_path),
            "-f",
            "json",
            "--machineReadable",
            *extended,
            "-r",
            self.recognizer,
            *dialog,
            input_file,
        ]

    def build_version_args(self) -> list[str]:
        return [str(self.executable_path), "--version"]

    def open_process(self, cmd_args: List[str]) -> None:
        assert not self.was_started
        assert not self.config_errors(), self.config_errors()
        self.stdout = ""
        self.stderr = ""
        self.last_exit_code = None
        log.info(f"Starting process\n{cmd_args}")
        # universal_newlines forces text mode
        self.process = Popen(self.extra_args + cmd_args, stdout=PIPE, stderr=PIPE, universal_newlines=True)

    def close_process(self) -> None:
        if self.was_started:
            log.debug(f"Terminating the process {self.process}")
            self.process.terminate()
            self.process.wait(RhubarbCommandWrapper.thread_wait_timeout)
            # Consume any reminding output, this would also close the process io streams
            self.process.communicate(timeout=5)
            log.debug("Process terminated")
        self.process = None

    def get_version(self) -> str:
        """Execute `lipsync --version` to get the current version of the binary. Synchroinous call."""
        self.close_process()
        args = self.build_version_args()
        self.open_process(args)
        self.collect_output_sync(ignore_timeout_error=False)
        return RhubarbParser.parse_version_info(self.stdout)

    def log_status_line(self, log_json: dict) -> None:
        # {'log': {'level': 'Info', 'message': 'Msg'}}]
        if not log_json or "log" not in log_json:
            return  # Not log key included in the progress line
        level = log_json["log"]["level"]
        msg = log_json["log"]["message"]

        log.log(RhubarbParser.LOG_LEVELS_MAP[level], f"Rhubarb: {msg}")

    def lipsync_start(self, input_file: str, dialog_file: Optional[str] = None) -> None:
        """Start the main lipsync command. Process runs in background"""
        self.close_process()
        args = self.build_lipsync_args(input_file, dialog_file)
        self.open_process(args)

    def lipsync_check_progress(self) -> Optional[int]:
        """Reads the stderr of the lipsync command where the progress and status in being reported.
        Note this call blocks until there is status update available on stderr.
        The rhubarb binary provides the status update few times per seconds typically.
        """
        assert self.was_started, "Process not started. Can't check progress"
        if self.has_finished:  # Has already finished earlier, assume outputs has been collected and release process
            self.close_process()
            return 100
        if self.check_process_has_finished():
            return 100  # Has just finished (since last check). Outputs have to be collected now
        self.stderr = ""

        self.read_process_stderr_line()
        if not self.stderr:
            return None
        status_lines = RhubarbParser.parse_status_infos(self.stderr)
        if not status_lines:
            return None
        for s in status_lines:
            self.log_status_line(s)
        by_type = {j["type"]: j for j in status_lines if j}
        if "failure" in by_type:
            raise RuntimeError(f"Rhubarb binary failed:\n{by_type['failure']['reason']}")
        if "progress" not in by_type:
            return None
        v = by_type["progress"]["value"]
        return int(v * 100)

    @property
    def was_started(self) -> bool:
        """Whether the process has been triggered already. Might be still running running or have finished"""
        return self.process is not None

    @property
    def has_finished(self) -> bool:
        """
        Whether the process has finished. Either sucessfully or with an error.
        When True the process is not running and the last_out and the last_error are complete
        """
        # if not self.was_started:
        #    return False
        return self.last_exit_code is not None

    @property
    def is_running(self) -> bool:
        return self.was_started and not self.has_finished

    def get_lipsync_output_json(self) -> list[dict]:
        """Json - parsed output of the lipsync capture process"""
        assert self.has_finished, "Output is not available since the process has not finisehd"
        return RhubarbParser.parse_lipsync_json(self.stdout)

    def get_lipsync_output_cues(self) -> list[MouthCue]:
        """Json - parsed output of the lipsync capture process"""
        json = self.get_lipsync_output_json()
        return RhubarbParser.lipsync_json2MouthCues(json)

    def collect_output_sync(self, ignore_timeout_error=True, timeout=1) -> None:
        """
        Waits (with a timeout) for the process to finish. Then collects its std out and std error
        """
        assert self.was_started
        try:
            (stdout, stderr) = self.process.communicate(timeout=timeout)  # Consume any reminding output
            self.stderr += stderr
            self.stdout += stdout
        except TimeoutExpired:
            log.warn("Timed out while waiting for process to finalize outputs")
            if not ignore_timeout_error:
                raise
        self.close_process()

    def check_process_has_finished(self) -> bool:
        exit_code = self.process.poll()
        if exit_code is None:
            return False
        self.last_exit_code = exit_code
        if exit_code != 0:
            raise RuntimeError(f"Rhubarb binary exited with a non-zero exit code {exit_code}")
        return True

    def read_process_stderr_line(self) -> None:
        """Reads one line from the process stderror. This method eventually blocks"""
        assert self.was_started
        if self.has_finished:
            return
        try:
            # Rhubarb binary is reporting progress on the stderr. Read next line.
            # This would eventually block.
            n = next(self.process.stderr)  # type: ignore
            self.stderr += n
        except StopIteration:
            log.debug("EOF reached while reading the stderr")  # Process has just terminated

    def read_process_stdout(self) -> None:
        """Reads and collects the process stdout. This method blocks."""
        assert self.was_started
        # log.trace("About to read stding")  # type: ignore
        o = self.process.stdout.readlines()
        if len(o) > 0:
            self.stdout += ' '.join(o)
            log.debug(f"Consumed stdout. Read {len(o)} lines.")  # type: ignore
        # else:
        #    log.trace("Empty newline in stdout")  # type: ignore


class RhubarbCommandAsyncJob:
    """Additional wrapper over the RhubarbCommandWrapper which handles asynchronious progress-updates."""

    thread_wait_timeout = 5

    def __init__(self, cmd: RhubarbCommandWrapper) -> None:
        assert cmd
        self.cmd = cmd
        self.stdout_thread: Optional[Thread] = None
        self.stderr_thread: Optional[Thread] = None
        self.queue: SimpleQueue[tuple[str, Any]] = SimpleQueue()
        self.last_progress = 0
        self.last_exception: Optional[Exception] = None
        self.last_cues: list[MouthCue] = []
        self.stop_event = Event()

    @thread_loop
    def _stderr_thread_run(self) -> None:
        """Stderror reader. Runs on a separate thread, pushing progress message via Q"""
        progress = self.cmd.lipsync_check_progress()

        if progress is None:
            sleep(0.1)
        else:
            self.last_progress = progress
            self.queue.put(("PROGRESS", progress))

    @thread_loop
    def _stdout_thread_run(self) -> None:
        """Stdout reader. Runs on a separate thread to co be able to consume the cli-command output
        while the command might be still runnig. In case the stdoutput is big (bigger that pipe buffers) the command won't
        terminate unless the stdout is consumed.
        """
        self.cmd.read_process_stdout()

    def _join_thread(self, t: Optional[Thread]) -> None:
        if not t:
            return

        log.debug(f"Joining thread {t}")
        try:
            t.join(RhubarbCommandWrapper.thread_wait_timeout)
            if t.is_alive():
                log.error(f"Failed to join the {t} thread after waiting for {RhubarbCommandWrapper.thread_wait_timeout} seconds.")
        except:
            log.error(f"Failed to join the {t} thread")
            traceback.print_exc()

    def join_threads(self) -> None:
        self._join_thread(self.stdout_thread)
        self._join_thread(self.stderr_thread)
        self.queue = SimpleQueue()
        self.stdout_thread = None
        self.stderr_thread = None

    def lipsync_check_progress_async(self) -> Optional[int]:
        if self.cmd.has_finished:  # Finished, do some auto-cleanup a process output
            self.join_threads()
            self.cmd.collect_output_sync(ignore_timeout_error=True)
            self.cmd.close_process()
            return 100
        if not self.stderr_thread:
            log.debug("Creating reader threads")
            self.stop_event.clear()
            self.stdout_thread = Thread(target=self._stdout_thread_run, name="StdOut", daemon=True)
            self.stderr_thread = Thread(target=self._stderr_thread_run, name="StdError-StatusCheck", daemon=True)
            self.stdout_thread.start()
            self.stderr_thread.start()

        try:
            (msg, obj) = self.queue.get_nowait()
            log.trace(f"Received {msg}={obj}")  # type: ignore
            if msg == 'PROGRESS':
                return int(obj)
            if msg == 'EXCEPTION':
                raise obj  # Propagate exception from the thread
            assert False, f"Received unknown message {msg}"
        except Empty:
            return None

    def cancel(self) -> None:
        log.info("Cancel request. Stopping the process and the status thread.")
        self.stop_event.set()
        self.join_threads()
        self.cmd.close_process()

    def get_lipsync_output_cues(self) -> list[MouthCue]:
        if self.last_cues:  # Cached
            return self.last_cues
        if not self.cmd.has_finished:  # Still in progress (rhubarb bin can't deliver partial results)
            return []
        if not self.cmd.stdout:  # No output, probably failed
            return []
        self.last_cues = self.cmd.get_lipsync_output_cues()  # Cache the result
        return self.last_cues

    @property
    def failed(self) -> bool:
        if self.last_exception:
            return True
        if self.cmd.has_finished:
            if self.cmd.last_exit_code != 0:
                return True
        return False

    @property
    def status(self) -> str:
        if not self.cmd.was_started and not self.cmd.has_finished:
            # Not started yet. Or cancelled
            return "Failed" if self.failed else "Stopped"
        if self.cmd.has_finished:
            return "Done" if self.get_lipsync_output_cues() else "No data"
        return "Running"
