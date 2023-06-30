import bisect
import logging
import math
from operator import attrgetter
import pathlib
from functools import cached_property
from typing import Any, Callable, Optional, cast, Generator

import bpy
import bpy.utils.previews
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Action, AddonPreferences, Context, PropertyGroup, Sound, UILayout, NlaTrack

from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue, MouthShapeInfo, MouthShapeInfos, duration_scale_rate
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbCommandAsyncJob, RhubarbCommandWrapper, RhubarbParser
from rhubarb_lipsync.blender import ui_utils
from rhubarb_lipsync.blender.ui_utils import DropdownHelper
import textwrap

log = logging.getLogger(__name__)


class StripPlacementProperties(PropertyGroup):
    """Defines how to fit an action strip to the track constrained by the cue start and cue length"""

    scale_min: FloatProperty(  # type: ignore
        "Scale min",
        description="Scale down (slow down) the strip/clip up to this fraction when the action is too short. Has no effect when set to 1",
        min=0.01,
        soft_min=0.4,
        max=1,
        soft_max=1,
        default=0.8,
    )
    scale_max: FloatProperty(  # type: ignore
        "Scale max",
        description="Scale up (speed up) the strip/clip up to this fraction when the action is too long. Has no effect when set to 1",
        min=1,
        soft_min=1,
        max=3,
        soft_max=2,
        default=1.4,
    )
    offset_start: FloatProperty(  # type: ignore
        "Offset start",
        description=textwrap.dedent(
            """\
            The start frame of the strip is shifted by this number of frames. 
            The strip can for example start earlier (negative value) than the actual cue-start
            making the action fully visible at the correct time when the strip is blended with the previous strip. 
            """
        ),
        default=-1,
    )
    offset_end: FloatProperty(  # type: ignore
        "Offset end",
        description=textwrap.dedent(
            """\
            The end frame of the strip is shifted by this number of frames. 
            The strip can for example end after (positive value) the following cue-start.
            """
        ),
        default=1,
    )

    blend_type: EnumProperty(  # type: ignore
        name="Blend type",
        description=textwrap.dedent(
            """\
            Method used for combining the strip's result with accumulated result.
            Value used for the newly created strips"""
        ),
        items=[
            (
                "REPLACE",
                "REPLACE",
                textwrap.dedent(
                    """\
                    
                     The strip values replace the accumulated results by amount specified by influence"""
                ),
            ),
            (
                "COMBINE",
                "COMBINE",
                textwrap.dedent(
                    """\
                     
                     The strip values are combined with accumulated results by appropriately using 
                     addition, multiplication, or quaternion math, based on channel type."""
                ),
            ),
        ],
        default="REPLACE",
    )

    extrapolation: EnumProperty(  # type: ignore
        name="Extrapolation",
        description=textwrap.dedent(
            """\
            How to handle the gaps past the strip extents.
            Value used for the newly created strips"""
        ),
        items=[
            (
                "NOTHING",
                "NOTHING",
                textwrap.dedent(
                    """\
                    
                     The strip has no influence past its extents."""
                ),
            ),
            (
                "HOLD",
                "HOLD",
                textwrap.dedent(
                    """\
                     
                     Hold the first frame if no previous strips in track, and always hold last frame."""
                ),
            ),
            (
                "HOLD_FORWARD",
                "HOLD_FORWARD",
                textwrap.dedent(
                    """\
                     
                     Hold Forward -- Only hold last frame."""
                ),
            ),
        ],
        default="NOTHING",
    )

    use_sync_length: BoolProperty(  # type: ignore
        default=False,
        description='Update range of frames referenced from action after tweaking strip and its keyframes',
        name="End (frames)",
    )

    @property
    def overlap_length(self) -> float:
        """Number of frames the two consecutive strips overlap because of the start/end offsets"""
        return self.offset_end - self.offset_start

    # min_strip_len: IntProperty(  # type: ignore
    #     "Min strip length",
    #     description="""If there is room on the track any strip shorter than this amount of frames will be prolonged.
    #                    This is mainly to improve visibility of the strips labels.  """,
    #     default=3,
    # )
