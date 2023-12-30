import logging
import unittest
from functools import cached_property
from pathlib import Path
from time import sleep

import rhubarb_lipsync.rhubarb.rhubarb_command as rhubarb_command

# import tests.sample_data
import sample_data
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbCommandAsyncJob, RhubarbCommandWrapper, RhubarbParser


def enableDebug() -> None:
    logging.basicConfig()
    rhubarb_command.log.setLevel(logging.DEBUG)


def wait_until_finished(r: RhubarbCommandWrapper) -> None:
    assert r.was_started
    for i in range(0, 1000):
        if r.has_finished:
            r.collect_output_sync(ignore_timeout_error=True)
            return
        sleep(0.1)
        r.lipsync_check_progress()

        # print(f"{p}%")
        # print(r.stderr)
        # print(r.stdout)
    assert False, "Seems the process in hanging up"


def wait_until_finished_async(job: RhubarbCommandAsyncJob, only_loop_times=0) -> None:
    assert job.cmd.was_started
    loops = 0
    for i in range(0, 1000):
        if job.cmd.has_finished:
            assert loops > 2, "No progress updates was provided "
            return
        sleep(0.1)
        p = job.lipsync_check_progress_async()
        if p is not None:
            loops += 1
            # print(f"{p}%")
            if only_loop_times > 0 and loops > only_loop_times:
                return
        # print(r.stderr)
        # print(r.stdout)
    assert False, "Seems the process in hanging up"


class RhubarbCommandWrapperTest(unittest.TestCase):
    def setUp(self) -> None:
        enableDebug()
        self.wrapper = RhubarbCommandWrapper(self.executable_path)

    @cached_property
    def project_dir(self) -> Path:
        return Path(__file__).parents[1]

    @cached_property
    def executable_path(self) -> Path:
        return self.project_dir / "rhubarb_lipsync" / "bin" / RhubarbCommandWrapper.executable_default_filename()

    @cached_property
    def data_short(self) -> sample_data.SampleData:
        return sample_data.snd_en_male_electricity

    @cached_property
    def data_long(self) -> sample_data.SampleData:
        return sample_data.snd_en_femal_3kittens

    def compare_cues_testdata(self, expected: sample_data.SampleData, wrapper: RhubarbCommandWrapper) -> None:
        res = expected.compare_cues_with_expected(wrapper.get_lipsync_output_cues())
        self.assertIsNone(res, res)

    def compare_testdata_with_current(self, data: sample_data.SampleData) -> None:
        self.compare_cues_testdata(data, self.wrapper)

    def testVersion(self) -> None:
        self.assertEqual(self.wrapper.get_version(), "1.13.0")
        self.assertEqual(self.wrapper.get_version(), "1.13.0")

    def testLipsync_sync(self) -> None:
        self.wrapper.lipsync_start(str(self.data_short.snd_file_path))
        wait_until_finished(self.wrapper)
        self.compare_testdata_with_current(self.data_short)

    def testLipsync_async(self) -> None:
        self.wrapper.lipsync_start(str(self.data_short.snd_file_path))
        wait_until_finished_async(RhubarbCommandAsyncJob(self.wrapper))
        assert not self.wrapper.was_started
        assert self.wrapper.has_finished
        self.compare_testdata_with_current(self.data_short)

    @unittest.skip("Takes very long. And the output differs a bit each run. Probably after multi-threadinig kicks in.")
    def testLipsync_async_long(self) -> None:
        self.wrapper.lipsync_start(str(self.data_long.snd_file_path))
        wait_until_finished_async(RhubarbCommandAsyncJob(self.wrapper))
        assert not self.wrapper.was_started
        assert self.wrapper.has_finished
        self.compare_testdata_with_current(self.data_long)

    def testLipsync_cancel(self) -> None:
        job = RhubarbCommandAsyncJob(self.wrapper)
        assert not self.wrapper.was_started
        assert not self.wrapper.has_finished
        self.wrapper.lipsync_start(str(self.data_long.snd_file_path))
        assert self.wrapper.was_started
        assert not self.wrapper.has_finished
        wait_until_finished_async(job, 4)
        assert self.wrapper.was_started
        assert not self.wrapper.has_finished
        job.cancel()
        assert not self.wrapper.was_started
        assert not self.wrapper.has_finished

        assert not self.wrapper.stdout, f"No cues expected since the process was canceled. But got\n'{self.wrapper.stdout}' "

        # self.assertEqual(len(s.fullyMatchingParts()), 2)

    def testLipsync_cancel_restat(self) -> None:
        job = RhubarbCommandAsyncJob(self.wrapper)
        assert job.status == "Stopped"
        self.wrapper.lipsync_start(str(self.data_short.snd_file_path))
        assert job.status == "Running"
        wait_until_finished_async(job, 4)
        assert job.status == "Running"
        job.cancel()
        assert job.status == "Stopped"
        # Start again resuing same cmd wrapper and job
        self.wrapper.lipsync_start(str(self.data_short.snd_file_path))
        wait_until_finished(self.wrapper)
        assert job.status == "Done"
        self.compare_testdata_with_current(self.data_short)


class RhubarbParserTest(unittest.TestCase):
    def setUp(self) -> None:
        enableDebug()

    def testVersion(self) -> None:
        self.assertFalse(RhubarbParser.parse_version_info(""))
        self.assertFalse(RhubarbParser.parse_version_info("invalid"))
        self.assertEqual(RhubarbParser.parse_version_info("\nRhubarb Lip Sync version 01.2.3 \n"), "01.2.3")

    def testStatusLine(self) -> None:
        failed = '''{ "type": "failure", "reason": "Error processing file Foo\\nBar\\n" }'''
        sts = RhubarbParser.parse_status_infos(failed)
        assert len(sts) == 1
        st = sts[0]
        assert st["type"] == "failure"

    def testParseUnparse(self) -> None:
        sample = sample_data.snd_en_male_electricity
        # Serialize the expected capture to json first
        json = RhubarbParser.unparse_mouth_cues(sample.expected_cues, sample.snd_file_path.name, "test")
        # Try to parse it back
        parsed_dict = RhubarbParser.parse_lipsync_json(json)
        parsed_cues = RhubarbParser.lipsync_json2MouthCues(parsed_dict)
        res = sample.compare_cues_with_expected(parsed_cues)
        self.assertIsNone(res, res)


if __name__ == '__main__':
    # unittest.main(RhubarbParserTest())
    # unittest.main(RhubarbCommandWrapperTest())
    unittest.main()
