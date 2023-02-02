from functools import cached_property
from pathlib import Path
import unittest
import rhubarb_lipsync.rhubarb.rhubarb_command_handling as rhubarb_command_handling
from rhubarb_lipsync.rhubarb.rhubarb_command_handling import RhubarbCommandWrapper, RhubarbParser
from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue
import logging
from time import sleep

# import tests.test_data
import test_data


def enableDebug():
    logging.basicConfig()
    rhubarb_command_handling.log.setLevel(logging.DEBUG)


def wait_until_finished(r: RhubarbCommandWrapper):
    assert r.was_started
    for i in range(0, 1000):
        if r.has_finished:
            return
        sleep(0.1)
        p = r.lipsync_check_progress()

        # print(f"{p}%")
        # print(r.stderr)
        # print(r.stdout)
    assert False, "Seems the process in hanging up"


def wait_until_finished_async(r: RhubarbCommandWrapper, cancel_after=0):
    assert r.was_started
    loops = 0
    for i in range(0, 1000):
        if r.has_finished:
            assert loops > 2, f"No progress updates was provided "
            return
        sleep(0.1)
        p = r.lipsync_check_progress_async()
        if p is not None:
            loops += 1
            # print(f"{p}%")
            if cancel_after > 0 and loops > cancel_after:
                r.cancel()
                return
        # print(r.stderr)
        # print(r.stdout)
    assert False, "Seems the process in hanging up"


class RhubarbCommandWrapperTest(unittest.TestCase):
    def setUp(self):
        enableDebug()
        self.wrapper = RhubarbCommandWrapper(self.executable_path)

    @cached_property
    def project_dir(self) -> Path:
        return Path(__file__).parents[1]

    @cached_property
    def executable_path(self) -> Path:
        return self.project_dir / "bin" / RhubarbCommandWrapper.executable_default_filename()

    @cached_property
    def data(self) -> test_data.SampleData:
        return test_data.snd_en_male_electricity

    def compare_cues(self, a_cues: list[MouthCue], b_cues: list[MouthCue]) -> None:
        self.assertEqual(len(a_cues), len(b_cues), f"Lengths don't match \n{a_cues}\n{b_cues}")
        for i, (a, b) in enumerate(zip(a_cues, b_cues)):
            self.assertEqual(a, b, f"Cues at position {i} don't match:\n{a}\n{b} ")

    def compare_cues_testdata(self, expected: test_data.SampleData, wrapper: RhubarbCommandWrapper) -> None:
        self.compare_cues(expected.expected_cues, wrapper.get_lipsync_output_cues())

    def compare_testdata_with_current(self) -> None:
        self.compare_cues_testdata(self.data, self.wrapper)

    def testVersion(self):
        self.assertEqual(self.wrapper.get_version(), "1.13.0")
        self.assertEqual(self.wrapper.get_version(), "1.13.0")

    def testLipsync_sync(self) -> None:
        self.wrapper.lipsync_start(str(self.data.snd_file_path))
        wait_until_finished(self.wrapper)
        self.compare_testdata_with_current()

    def testLipsync_async(self):
        self.wrapper.lipsync_start(str(self.data.snd_file_path))
        wait_until_finished_async(self.wrapper)
        self.compare_testdata_with_current()

    def testLipsync_cancel(self):
        self.wrapper.lipsync_start(str(self.data.snd_file_path))
        wait_until_finished_async(self.wrapper, 4)
        assert not self.wrapper.has_finished
        self.wrapper.close_process()
        assert not self.wrapper.stdout, f"No cues expected since the process was canceled. But got\n'{self.wrapper.stdout}' "

        # self.assertEqual(len(s.fullyMatchingParts()), 2)


class RhubarbParserTest(unittest.TestCase):
    def setUp(self):
        enableDebug()

    def testVersion(self):
        self.assertFalse(RhubarbParser.parse_version_info(""))
        self.assertFalse(RhubarbParser.parse_version_info("invalid"))
        self.assertEqual(RhubarbParser.parse_version_info("\nRhubarb Lip Sync version 01.2.3 \n"), "01.2.3")

    def testStatusLine(self):
        failed = '''{ "type": "failure", "reason": "Error processing file Foo\\nBar\\n" }'''
        sts = RhubarbParser.parse_status_infos(failed)
        assert len(sts) == 1
        st = sts[0]
        assert st["type"] == "failure"


if __name__ == '__main__':
    # unittest.main(RhubarbParserTest())
    # unittest.main(RhubarbCommandWrapperTest())
    unittest.main()
