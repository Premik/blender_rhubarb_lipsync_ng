import logging
import unittest
from functools import cached_property
from pathlib import Path
from time import sleep

import rhubarb_lipsync.rhubarb.rhubarb_command as rhubarb_command

# import tests.sample_data
import sample_data
from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbCommandAsyncJob, RhubarbCommandWrapper, RhubarbParser
from rhubarb_lipsync.rhubarb.mouth_shape_data import time2frame_float, duration_scale_rate, duration_scale


def enableDebug() -> None:
    logging.basicConfig()
    rhubarb_command.log.setLevel(logging.DEBUG)


class TimeFrameConversionTest(unittest.TestCase):
    def setUp(self) -> None:
        enableDebug()

    def testTim2Frame(self) -> None:
        self.assertAlmostEqual(time2frame_float(2, 60), 120)

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


if __name__ == '__main__':
    # unittest.main(RhubarbParserTest())
    # unittest.main(RhubarbCommandWrapperTest())
    unittest.main()
