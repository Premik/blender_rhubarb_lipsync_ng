import logging
import textwrap

from bpy.props import BoolProperty, EnumProperty, FloatProperty
from bpy.types import PropertyGroup

log = logging.getLogger(__name__)


class StripPlacementPreferences(PropertyGroup):
    """Defines how to fit an action strip to the track constrained by the cue start and cue length"""

    scale_min: FloatProperty(  # type: ignore
        "Scale Min",
        description=textwrap.dedent(
            """\
            Scale down minimum value. Reduces the clip playback seep up to this fraction when the action is too long.
            Has no effect when set to 1. Does not affect Actions with only a single keyframe (poses).
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
            Scale up maximum value. Increases the clip playback speed up to this fraction when the action is too short.
            Has no effect when set to 1. Does not affect Actions with only a single keyframe (poses).
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

    strip_blend_type: EnumProperty(  # type: ignore
        name="Strip Blend Type",
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

    blend_inout_ratio: FloatProperty(  # type: ignore
        "Blend In-Out Ratio",
        description=textwrap.dedent(
            """\
            Ratio between blend-in and blend-out sections.
              
            For the default value of 0.5, it takes the same amount of time for a cue to fully appear as it does to disappear.  
            Lower values mean the cue appears faster but takes longer to disappear.  
            Higher values make the cue appears slower but disappears faster.
            """
        ),
        min=0,
        max=1,
        soft_min=0.1,
        soft_max=0.9,
        default=0.5,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    inout_blend_type: EnumProperty(  # type: ignore
        name="In Out Blend Type",
        description=textwrap.dedent(
            """\
            Method used for blend in/blend out strip options. I.e. how the strips influence changes over time.             
            """
        ),
        items=[
            (
                "NO_BLENDING",
                "No blending",
                textwrap.dedent(
                    """\
                    
                    Strip influence is always set to 1. Use this for 2D animations where blending is not desired"""
                ),
            ),
            (
                "BY_RATIO",
                "By ratio",
                textwrap.dedent(
                    """\
                    
                    The Blend in/out values are calculated by the addon based on the provided Blend in/out ratio value. 
                    Only strips indicating silence (Ⓧ or Ⓐ) has Auto-blend enabled."""
                ),
            ),
            (
                "ALWAYS_AUTOBLEND",
                "Always auto-blend",
                textwrap.dedent(
                    """\
                    
                    Same as for the By-Ratio option, but the Blender's inbuilt autoblending is always enabled for all Strips.
                    This should ease futher tweaking of the NLA strip ends."""
                ),
            ),
        ],
        default="BY_RATIO",
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )
