import logging
import textwrap

from bpy.props import BoolProperty, EnumProperty, FloatProperty
from bpy.types import PropertyGroup

log = logging.getLogger(__name__)


class StripPlacementProperties(PropertyGroup):
    """Defines how to fit an action strip to the track constrained by the cue start and cue length"""

    scale_min: FloatProperty(  # type: ignore
        "Scale Min",
        description="Scale down minimal value. Slow down the clip playback speed up to this fraction when the action is too short. Has no effect when set to 1",
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
        description="Scale up maximal value. Speed up the clip playback speed up to this fraction when the action is too long. Has no effect when set to 1",
        min=1,
        soft_min=1,
        max=3,
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

    blend_mode: EnumProperty(  # type: ignore
        name="Blend Mode",
        description=textwrap.dedent(
            """\
            How to setup blending of the Strips between cues.
            """
        ),
        items=[
            (
                "AUTOBLEND",
                "Auto blend",
                textwrap.dedent(
                    """\
                    
                    Number of frames for Blending In/Out is automatically determined from overlapping strips.
                    This is Blender inbuilt method.
                    """
                ),
            ),
            (
                "FIXED",
                "Fixed",
                textwrap.dedent(
                    """\
                     
                    Blend in/out values is set to a fixed number of frames.
                    This method was used by the older version of the lipsync plugin. 
                    """
                ),
            ),
            (
                "PROPORTIONAL",
                "Proportional",
                textwrap.dedent(
                    """\
                     
                    (Recommended) 
                    Blend in/out values are scaled proportionally to the Strip length. 
                    This method should produce more fluent animation with less "freezing" frames.  
                    Especially for longer strips and/or higher fps values. """
                ),
            ),
        ],
        default="PROPORTIONAL",
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    blend_in: FloatProperty(  # type: ignore
        "Blend In",
        description="Number of frames at start of strip to fade in influence",
        min=0,
        soft_max=10,
        default=1,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )
    blend_out: FloatProperty(  # type: ignore
        "Blend Out",
        description="Number of frames at start of strip to fade out influence",
        min=0,
        soft_max=10,
        default=1,
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
