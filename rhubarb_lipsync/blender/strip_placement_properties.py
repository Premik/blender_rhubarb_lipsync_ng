import logging
import textwrap

from bpy.props import BoolProperty, EnumProperty, FloatProperty
from bpy.types import PropertyGroup

log = logging.getLogger(__name__)


class StripPlacementProperties(PropertyGroup):
    """Defines how to fit an action strip to the track constrained by the cue start and cue length"""

    scale_min: FloatProperty(  # type: ignore
        "Scale Min",
        description=textwrap.dedent(
            """\
            Scale down minimal value. Slow down the clip playback speed up to this fraction when the action is too short. 
            Has no effect when set to 1. Has no effect on Actions with a single keyframe only (aka poses). 
            """
        ),
        min=0.01,
        soft_min=0.4,
        max=1,
        soft_max=1,
        default=0.8,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )
    scale_max: FloatProperty(  # type: ignore
        "Scale Max",
        description=textwrap.dedent(
            """\
            Scale up maximal value. Speed up the clip playback speed up to this fraction when the action is too long. 
            Has no effect when set to 1. Has no effect on Actions with a single keyframe only (aka poses). 
            """
        ),
        min=1,
        soft_min=1,
        max=10,
        soft_max=2,
        default=1.4,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )
    offset_start: FloatProperty(  # type: ignore
        "Offset Start",
        description=textwrap.dedent(
            """\
            The start frame of the strip is shifted by this number of frames. 
            The strip can for example start earlier (negative value) than the actual cue-start
            making the action fully visible at the correct time when the strip is blended with the previous strip. 
            """
        ),
        default=-0.5,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )
    offset_end: FloatProperty(  # type: ignore
        "Offset End",
        description=textwrap.dedent(
            """\
            The end frame of the strip is shifted by this number of frames. 
            The strip can for example end after (positive value) the following cue-start.
            """
        ),
        default=1,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    blend_type: EnumProperty(  # type: ignore
        name="Blend Type",
        description=textwrap.dedent(
            """\
            Method used for combining the strip's result with accumulated result.
            Value used for the newly created strips"""
        ),
        items=[
            (
                "REPLACE",
                "Replace",
                textwrap.dedent(
                    """\
                    
                     The strip values replace the accumulated results by amount specified by influence"""
                ),
            ),
            (
                "COMBINE",
                "Combine",
                textwrap.dedent(
                    """\
                     
                     The strip values are combined with accumulated results by appropriately using 
                     addition, multiplication, or quaternion math, based on channel type."""
                ),
            ),
        ],
        default="REPLACE",
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
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
                "Nothing",
                textwrap.dedent(
                    """\
                    
                     The strip has no influence past its extents."""
                ),
            ),
            (
                "HOLD",
                "Hold",
                textwrap.dedent(
                    """\
                     
                     Hold the first frame if no previous strips in track, and always hold last frame."""
                ),
            ),
            (
                "HOLD_FORWARD",
                "Hold Forward",
                textwrap.dedent(
                    """\
                     
                     Hold Forward -- Only hold last frame."""
                ),
            ),
        ],
        default="NOTHING",
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    use_sync_length: BoolProperty(  # type: ignore
        default=False,
        description='Update range of frames referenced from action after tweaking strip and its keyframes',
        name="Sync Length",
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    blend_in_frames: FloatProperty(  # type: ignore
        "Blend In Frames",
        description="Number of frames at start of strip to fade in the influence",
        min=0,
        soft_max=10,
        default=1,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )
    use_auto_blend: BoolProperty(  # type: ignore
        default=False,
        description="Number of frames for Blending In/Out is automatically determined from overlapping strips",
        name="Auto Blend In/Out",
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
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
    #    options={'LIBRARY_EDITABLE'},
    #    override={'LIBRARY_OVERRIDABLE'},
    # )
