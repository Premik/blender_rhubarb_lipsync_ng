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


class NlaTrackRef(PropertyGroup):
    """Reference to an nla track. By name and index since NLA track is a non-ID object"""

    object: PointerProperty(type=bpy.types.Object, name="Object the NLA tracks belong to")  # type: ignore

    def name_updated(self, ctx: Context) -> None:
        self.dropdown_helper.name2index()

    def items(self) -> Generator[NlaTrack | Any, Any, None]:
        o = self.object
        if not o or not o.animation_data or not o.animation_data.nla_tracks:
            return
        for t in o.animation_data.nla_tracks:
            yield t

    def search_names(self, ctx: Context, edit_text) -> Generator[str | Any, Any, None]:
        for i, t in enumerate(self.items()):
            yield f"{str(i).zfill(3)} {t.name}"

    @cached_property
    def dropdown_helper(self) -> DropdownHelper:
        return DropdownHelper(self, list(self.search_names(None, "")), DropdownHelper.NameNotFoundHandling.UNSELECT)

    name: StringProperty(name="NLA Track", description="NLA track to add actions to", search=search_names, update=name_updated)  # type: ignore
    index: IntProperty(name="Index of the selected track", default=-1)  # type: ignore

    @property
    def selected_item(self) -> Optional[NlaTrack]:
        items = list(self.items())
        if self.index < 0 or self.index >= len(items):
            return None
        # self.dropdown_helper(ctx).index2name()
        return items[self.index]


class MappingItem(PropertyGroup):
    """Mapping of a single mouth shape type to action(s)"""

    key: StringProperty("key", description="Mouth cue key symbol (A,B,C..)")  # type: ignore
    action: PointerProperty(type=bpy.types.Action, name="Action")  # type: ignore
    shapekey_action: PointerProperty(type=bpy.types.Action, name="Shape key")  # type: ignore
    # action: PointerProperty(type=bpy.types.ShapeKey, name="Action")  # type: ignore

    @cached_property
    def cue_desc(self) -> MouthShapeInfo | None:
        if not self.key:
            return None
        return MouthShapeInfos[self.key].value


class StripFitProperties(PropertyGroup):
    """Defines how to fit an action to the action strip constrained by the cue start and cue length"""

    scale_min: FloatProperty(  # type: ignore
        "Scale min",
        description="Scale down (slow down) the strip/clip up to this fraction when the action is too short. Has no effect when set to 1",
        default=0.5,
    )
    scale_max: FloatProperty(  # type: ignore
        "Scale max",
        description="Scale up (speed up) the strip/clip up to this fraction when the action is too long. Has no effect when set to 1",
        default=1.5,
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
        default=2,
    )
    # min_strip_len: IntProperty(  # type: ignore
    #     "Min strip length",
    #     description="""If there is room on the track any strip shorter than this amount of frames will be prolonged.
    #                    This is mainly to improve visibility of the strips labels.  """,
    #     default=3,
    # )

    def action_scale(self, action: bpy.types.Action, desired_len_frames: float) -> float:
        """Returns scale factor for the provided `action`. So the `action.end-frame*scale` would match the `desired_len_frames` as close as possible."""
        range = action.frame_range
        l = range[1] - range[0]
        return duration_scale_rate(l, desired_len_frames, self.scale_min, self.scale_max)


class MappingProperties(PropertyGroup):
    """Mapping of all the mouth shape types to action(s)"""

    items: CollectionProperty(type=MappingItem, name="Mapping items")  # type: ignore
    index: IntProperty(name="Selected mapping index")  # type: ignore
    # nla_track1: PointerProperty(type=bpy.types.NlaTrack, name="Tract 1")  # type: ignore
    nla_track1: PointerProperty(type=NlaTrackRef, name="Track 1")  # type: ignore
    nla_track2: PointerProperty(type=NlaTrackRef, name="Track 2")  # type: ignore
    fit: PointerProperty(type=StripFitProperties, name="Strip Fit properties")  # type: ignore

    def on_nla_map_action_update(self, ctx: Context) -> None:
        if self.nla_map_shapekey or self.nla_map_action:
            return  # Either one tick should be checked
        # Neither is selected, meaning this one has been uticked. Check the other one
        self.nla_map_shapekey = True

    def on_nla_map_shapekey_update(self, ctx: Context) -> None:
        if self.nla_map_shapekey or self.nla_map_action:
            return  # Either one tick should be checked
        # Neither is selected, meaning this one has been uticked. Check the other one
        self.nla_map_action = True

    nla_map_action: BoolProperty(default=True, name="Action", description="Map cues to regular Action", update=on_nla_map_action_update)  # type: ignore
    nla_map_shapekey: BoolProperty(default=False, name="Shape key", description="Map cues to shape-key Action", update=on_nla_map_shapekey_update)  # type: ignore

    def build_items(self, obj: bpy.types.Object) -> None:
        # log.trace("Already buil")  # type: ignore
        if len(self.items) > 0:
            return  # Already built (assume)
        log.trace("Building mapping list")  # type: ignore
        t1: NlaTrackRef = self.nla_track1
        t2: NlaTrackRef = self.nla_track2
        t1.object = obj
        t2.object = obj
        for msi in MouthShapeInfos.all():
            item: MappingItem = self.items.add()
            item.key = msi.key

    @property
    def selected_item(self) -> Optional[MappingItem]:
        if self.index < 0 or self.index >= len(self.items):
            return None
        return self.items[self.index]

    @property
    def has_any_mapping(self) -> bool:
        """Has any Action mapped at all"""
        if not self.items or len(self.items) <= 0:
            return False
        for i in self.items:
            mi: MappingItem = i
            if mi.action or mi.shapekey_action:
                return True
        return False

    @property
    def blank_keys(self) -> list[str]:
        return [mi.key for mi in self.items or [] if not mi.action]

    @property
    def blank_shapekeys(self) -> list[str]:
        return [mi.key for mi in self.items or [] if not mi.shapekey_action]

    @staticmethod
    def from_context(ctx: Context) -> Optional['MappingProperties']:
        """Get the selecrted capture properties from the current scene of the provided context"""
        # ctx.selected_editable_objects
        return MappingProperties.from_object(ctx.object)

    @staticmethod
    def from_object(obj: bpy.types.Object) -> Optional['MappingProperties']:
        if not obj:
            return None
        ret: MappingProperties = getattr(obj, 'rhubarb_lipsync_mapping')  # type: ignore
        # ret.mapping.build_items()  # Ensure cue infos are created
        return ret

    @staticmethod
    def by_object_name(obj_name: str) -> Optional['MappingProperties']:
        if not obj_name:
            return None
        obj = bpy.data.objects.get(obj_name, None)
        return MappingProperties.from_object(obj)

    @staticmethod
    def context_selection_validation(ctx: Context) -> str:
        """Validates there is an active object with the rhubarb properties in the blender context"""
        if not ctx.object:
            return "No object selected"
        if not MappingProperties.from_context(ctx):
            return "'rhubarb_lipsync' not found on the active object"
        return ""
