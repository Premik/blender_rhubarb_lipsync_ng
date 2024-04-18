import logging
import unittest

import rhubarb_lipsync.rhubarb.rhubarb_command as rhubarb_command

# import tests.sample_data
from rhubarb_lipsync.rhubarb.mouth_cues import FrameConfig, MouthCue, MouthCueFrames, duration_scale, time2frame_float, frame2time


def enableDebug() -> None:
    logging.basicConfig()
    rhubarb_command.log.setLevel(logging.DEBUG)


class TimeFrameConversionTest(unittest.TestCase):
    def setUp(self) -> None:
        enableDebug()

    def testTime2Frame(self) -> None:
        self.assertAlmostEqual(time2frame_float(2, 60), 120)

    def testTime2FrameConsistency(self) -> None:
        self.assertAlmostEqual(time2frame_float(frame2time(10, 25, 2), 25, 2), 10)

    def testDurationScaleNoScaling(self) -> None:
        # Scaling disabled
        self.assertAlmostEqual(duration_scale(10, 20, 1, 1), 10)
        self.assertAlmostEqual(duration_scale(10, 0, 1, 1), 10)

    def testDurationScaleFullScaling(self) -> None:
        # Can scale fully
        self.assertAlmostEqual(duration_scale(10, 20, 0.1, 5), 20)
        self.assertAlmostEqual(duration_scale(10, 5, 0.1, 5), 5)

    def testDurationScaleClamped(self) -> None:
        # Clamped to -+50%
        self.assertAlmostEqual(duration_scale(10, 30, 2, 2), 20)
        self.assertAlmostEqual(duration_scale(10, 0, 0.5, 5), 5)


class CueFramesTest(unittest.TestCase):
    def create_mcf_at(self, start_frame: float, duration_frames: float, key="A") -> MouthCueFrames:
        start = frame2time(start_frame, self.fcfg.fps, self.fcfg.fps_base)
        end = frame2time(start_frame + duration_frames, self.fcfg.fps, self.fcfg.fps_base)
        mc = MouthCue(key, start, end)
        return MouthCueFrames(mc, self.fcfg)

    def setUp(self) -> None:
        enableDebug()
        self.fcfg = FrameConfig(60, 1)

    def testFrameRoundingTwoFrames(self) -> None:
        # The cue starts slightly before frame 1 and ends litte bit after frame 2
        # I.e spawns slightly over 1 frame duration
        c = self.create_mcf_at(0.9, 1.2)

        self.assertEqual(c.start_frame, 1)
        self.assertEqual(c.end_frame, 2)
        self.assertEqual(c.start_frame_right, 1)
        self.assertEqual(c.end_frame_right, 3)
        self.assertEqual(c.end_frame_left, 2)
        self.assertTrue(c.intersects_frame)

    def testFrameRoundingOneFrame(self) -> None:
        # The cue starts slightly before frame 1 and ends litte bit right after it
        c = self.create_mcf_at(0.9, 0.3)

        self.assertEqual(c.start_frame, 1)
        self.assertEqual(c.end_frame, 1)
        self.assertEqual(c.start_frame_right, 1)
        self.assertEqual(c.end_frame_right, 2)
        self.assertEqual(c.end_frame_left, 1)
        self.assertTrue(c.intersects_frame)

    def testFrameRoundingNoFrame(self) -> None:
        # The cue duration is shorter than a single frame duration
        # and starts in the middle of two frames so there is no intersection
        c = self.create_mcf_at(1.1, 0.5)

        self.assertEqual(c.start_frame, 1)  # Start is closer to 1
        self.assertEqual(c.end_frame, 2)  # End time is 1.6, closer to 2
        self.assertEqual(c.start_frame_right, 2)
        self.assertEqual(c.end_frame_right, 2)
        self.assertEqual(c.end_frame_left, 1)
        self.assertFalse(c.intersects_frame)


if __name__ == '__main__':
    # unittest.main(RhubarbParserTest())
    # unittest.main(RhubarbCommandWrapperTest())
    unittest.main()
