import logging
import unittest

import pytest
from pytest import approx

import rhubarb_lipsync.rhubarb.rhubarb_command as rhubarb_command
from rhubarb_lipsync.rhubarb.cue_processor import CueProcessor

# import tests.sample_data
from rhubarb_lipsync.rhubarb.mouth_cues import FrameConfig, MouthCue, MouthCueFrames, duration_scale, frame2time, time2frame_float


def enableDebug() -> None:
    logging.basicConfig()
    rhubarb_command.log.setLevel(logging.DEBUG)


@pytest.mark.parametrize(
    "fcfg",
    [
        FrameConfig(60, 1, 0),
        FrameConfig(60, 1, 10),
        FrameConfig(2997, 100, -2),
        FrameConfig(5, 1, 0),
    ],
    ids=[
        "60fps no offset",
        "60fps +10 frames shift",
        "29.97fps -2 frames offset",
        "5fps no offset",
    ],
)
class TestCueFrames:
    def create_mcf_at(self, start_frame: float, duration_frames: float, fcfg: FrameConfig, key="A") -> MouthCueFrames:
        start = frame2time(start_frame, fcfg.fps, fcfg.fps_base)
        end = frame2time(start_frame + duration_frames, fcfg.fps, fcfg.fps_base)
        mc = MouthCue(key, start, end)
        return MouthCueFrames(mc, fcfg)

    # @pytest.fixture()
    # def fcfg(self) -> FrameConfig:
    #     return FrameConfig(60, 1, 0)

    @pytest.fixture(autouse=True)
    def setup_debug(self) -> None:
        enableDebug()

    def test_frame_rounding_two_frames(self, fcfg: FrameConfig) -> None:
        # The cue starts slightly before frame 1 and ends little bit after frame 2
        # I.e. spawns slightly over 1 frame duration
        c = self.create_mcf_at(0.9, 1.2, fcfg)
        o = fcfg.offset

        assert c.start_frame == approx(1 + o)
        assert c.end_frame == approx(2 + o)
        assert c.start_frame_right == approx(1 + o)
        assert c.end_frame_right == approx(3 + o)
        assert c.end_frame_left == approx(2 + o)
        assert c.intersects_frame

    def test_frame_rounding_one_frame(self, fcfg: FrameConfig) -> None:
        # # The cue starts slightly before frame 1 and ends litte bit right after it
        c = self.create_mcf_at(0.9, 0.3, fcfg)
        o = fcfg.offset

        assert c.start_frame == approx(1 + o)
        assert c.end_frame == approx(1 + o)
        assert c.start_frame_right == approx(1 + o)
        assert c.end_frame_right == approx(2 + o)
        assert c.end_frame_left == approx(1 + o)
        assert c.intersects_frame

    def test_frame_rounding_no_frame(self, fcfg: FrameConfig) -> None:
        # The cue duration is shorter than a single frame duration
        # and starts in the middle of two frames so there is no intersection
        c = self.create_mcf_at(1.1, 0.5, fcfg)
        o = fcfg.offset

        assert c.start_frame == approx(1 + o)  # Start is closer to 1 + o
        assert c.end_frame == approx(2 + o)  # End time is 1.6 + o, closer to 2 + o
        assert c.start_frame_right == approx(2 + o)
        assert c.end_frame_right == approx(2 + o)
        assert c.end_frame_left == approx(1 + o)
        assert not c.intersects_frame

    def create_cue_processor(self, fcfg: FrameConfig, *frames: float) -> CueProcessor:
        mcfs = []
        for i in range(len(frames) - 1):
            duration = frames[i + 1] - frames[i]
            mcfs.append(self.create_mcf_at(frames[i], duration, fcfg))
        return CueProcessor(fcfg, mcfs)

    def test_cue_processor_trim(self, fcfg: FrameConfig) -> None:
        # Two cues, first got trimmed, second doesn't
        cp = self.create_cue_processor(fcfg, 2, 7, 8)

        assert cp.cue_frames[0].duration_frames == approx(5)
        assert cp.cue_frames[1].duration_frames == approx(1)
        max_dur = frame2time(2, fcfg.fps, fcfg.fps_base)
        cp.trim_long_cues(max_dur, False)
        assert cp.cue_frames[0].cue.duration == approx(max_dur)
        assert cp.cue_frames[1].duration_frames == approx(1)

    def test_cue_processor_expand_short(self, fcfg: FrameConfig) -> None:
        # First cue is between frames 1 and 2, second crosses frame 2
        cp = self.create_cue_processor(fcfg, 1.1, 1.3, 2.3)
        o = fcfg.offset

        assert cp.cue_frames[0].duration_frames_float == approx(0.2)
        assert cp.cue_frames[1].duration_frames_float == approx(1)
        cp.ensure_frame_intersection()
        # First one should got expaned to left since 1.1 is closer to 1 than 1.3 is to 2
        assert cp.cue_frames[0].start_frame_float == approx(1 + o)
        assert cp.cue_frames[0].end_frame_float == approx(1.3 + o)
        assert cp.cue_frames[1].start_frame_float == approx(1.3 + o)
        assert cp.cue_frames[1].duration_frames_float == approx(1)
        assert cp.cue_frames[0].intersects_frame
        assert cp.cue_frames[1].intersects_frame

    def test_cue_processor_round_ends(self, fcfg: FrameConfig) -> None:
        # The first and second cues cross a frame but shouldn't be rounded as it is too short
        cp = self.create_cue_processor(fcfg, 1, 1.9, 2.3, 4.3)
        o = fcfg.offset

        assert cp.cue_frames[0].duration_frames_float == pytest.approx(0.9)
        cp.round_ends_down()
        assert cp.cue_frames[0].blend_out_frames == pytest.approx(0.9)
        assert cp.cue_frames[0].duration_frames_float == pytest.approx(0.9)
        assert cp.cue_frames[1].end_frame_float == pytest.approx(2.3 + o)
        assert cp.cue_frames[1].blend_out_frames == pytest.approx(0.3)
        assert cp.cue_frames[2].end_frame_float == pytest.approx(4 + o)
        assert cp.cue_frames[2].blend_out_frames == pytest.approx(1)

    @pytest.mark.parametrize('blend_in_duration_frames', [0.2, 0.5, 2])
    def test_cue_processor_blend_in(self, fcfg: FrameConfig, blend_in_duration_frames: float) -> None:
        # The first cue crosses frame 1 and ends right after that
        # so the second cue blend-in would overlap and should get shrinked
        cp = self.create_cue_processor(fcfg, 0.5, 1.1, 4)
        o = fcfg.offset

        blend_in_duration = frame2time(blend_in_duration_frames, fcfg.fps, fcfg.fps_base)
        assert cp.set_blend_in_times(blend_in_duration) == 1, "Expect exactly one cue to get blend-in section shrank"

        assert cp.cue_frames[0].blend_in == approx(blend_in_duration)  # Cue1 - blend_in unchanged
        assert cp.cue_frames[1].pre_start_float == approx(cp.frame2time(1 + o))  # Cue2 - (pre)starts at the whole frame of the previous one
