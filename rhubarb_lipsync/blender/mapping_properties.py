import logging
from functools import cached_property
from typing import Any, Optional, Generator

import bpy
import bpy.utils.previews
from bpy.props import BoolProperty, CollectionProperty, IntProperty, PointerProperty, StringProperty, FloatProperty
from bpy.types import Context, PropertyGroup, NlaTrack

from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthShapeInfo, MouthShapeInfos
from rhubarb_lipsync.blender.strip_placement_properties import StripPlacementProperties
from rhubarb_lipsync.blender.ui_utils import DropdownHelper
import rhubarb_lipsync.blender.mapping_utils as mapping_utils

log = logging.getLogger(__name__)


class NlaTrackRef(PropertyGroup):
    """Reference to an nla track. By name and index since NLA track is a non-ID object"""

    object: PointerProperty(  # type: ignore
        type=bpy.types.Object,
        name="Object the NLA tracks belong to",
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    def name_updated(self, ctx: Context) -> None:
        self.dropdown_helper.name2index()

    def items(self) -> Generator[NlaTrack | Any, Any, None]:
        o = self.object
        if not o:
            return
        # For mesh provide shape-key actions only. But only if the object has any shape-keys created
        if mapping_utils.does_object_support_shapekey_actions(o):
            if not o.data or not o.data.shape_keys or not o.data.shape_keys.animation_data:
                return
            for t in o.data.shape_keys.animation_data.nla_tracks:
                yield t
            return

        if not o.animation_data or not o.animation_data.nla_tracks:
            return
        for t in o.animation_data.nla_tracks:
            yield t

    def search_names(self, ctx: Context, edit_text) -> Generator[str | Any, Any, None]:
        for i, t in enumerate(self.items()):
            yield f"{str(i).zfill(3)} {t.name}"

    @cached_property
    def dropdown_helper(self) -> DropdownHelper:
        return DropdownHelper(self, list(self.search_names(None, "")), DropdownHelper.NameNotFoundHandling.UNSELECT)

    name: StringProperty(  # type: ignore
        name="NLA Track",
        description="NLA track to add actions to",
        search=search_names,
        update=name_updated,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )
    index: IntProperty(  # type: ignore
        name="Index of the selected track",
        default=-1,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    @property
    def selected_item(self) -> Optional[NlaTrack]:
        items = list(self.items())
        if self.index < 0 or self.index >= len(items):
            return None
        # self.dropdown_helper(ctx).index2name()
        return items[self.index]


class MappingItem(PropertyGroup):
    """Mapping of a single mouth shape type to action(s)"""

    key: StringProperty(  # type: ignore
        name="key",
        description="Mouth cue key symbol (A,B,C..)",
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )
    action: PointerProperty(  # type: ignore
        type=bpy.types.Action,
        name="Action",
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    frame_start: FloatProperty(  # type: ignore
        name="Frame Start",
        description="TBD",
        default=1,
        soft_min=1,
        soft_max=100,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    frame_count: FloatProperty(  # type: ignore
        name="Frames count",
        description="TBD",
        default=0,
        min=0,
        soft_min=1,
        soft_max=100,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    custom_frame_ranage: BoolProperty(  # type: ignore
        name="Custom Frame Range",
        description="Whether references a custom range of frames from the Action",
        default=False,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    @property
    def frame_end(self) -> float:
        """Last frame from the Action"""
        if self.custom_frame_ranage:
            return self.frame_start + self.frame_count
        if not self.action:
            return 0
        a: bpy.types.Action = self.action
        return a.frame_end

    @property
    def frame_range(self) -> tuple[float, float]:
        if not self.custom_frame_ranage:
            if not self.action:
                return 0.0, 0.0
            a: bpy.types.Action = self.action
            return tuple(a.frame_range)  # type: ignore
        return self.frame_start, self.frame_start + self.frame_count

    @property
    def frame_range_str(self) -> str:
        def c(f: float) -> str:  # Hide decimal digits when close to whole numbers
            if abs(f - round(f)) < 0.00001:
                # return f"{int(round(f)):03d}"
                return str(int(round(f)))
            else:
                # return f"{f:06.2f}"
                return f"{f:.2f}"

        return f"[{c(self.frame_range[0])}]...[{c(self.frame_range[1])}]"

    @cached_property
    def cue_info(self) -> MouthShapeInfo | None:
        if not self.key:
            return None
        return MouthShapeInfos[self.key].value

    @property
    def action_str(self) -> str:
        if not self.action:
            return " "
        return self.action.name


class MappingProperties(PropertyGroup):
    """Mapping of all the mouth shape types to action(s)"""

    items: CollectionProperty(  # type: ignore
        type=MappingItem,
        name="Mapping items",
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE', 'USE_INSERTION'},
    )
    index: IntProperty(name="Selected mapping index")  # type: ignore
    # nla_track1: PointerProperty(type=bpy.types.NlaTrack, name="Tract 1")  # type: ignore
    nla_track1: PointerProperty(  # type: ignore
        type=NlaTrackRef,
        name="Track 1",
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )
    nla_track2: PointerProperty(  # type: ignore
        type=NlaTrackRef,
        name="Track 2",
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    only_shapekeys: BoolProperty(  # type: ignore
        name="Only shape-key Actions",
        description="Switch between normal Actions and shape-key Actions. Use normal Actions for Armature and shape-key Actions for Mesh.",
        default=False,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    only_valid_actions: BoolProperty(  # type: ignore
        name="Only Valid Actions",
        description="When enabled Actions with invalid f-curve keys are filtered out",
        default=True,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    only_asset_actions: BoolProperty(  # type: ignore
        name="Only Asset Actions",
        description="When enabled only Actions marked as an Asset (aka poses) are listed",
        default=False,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    strip_placement: PointerProperty(  # type: ignore
        type=StripPlacementProperties,
        name="Strip timing properties",
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    def build_items(self, obj: bpy.types.Object) -> None:
        # log.trace("Already built")  # type: ignore
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
        # self.only_shapekeys=ui_utils.does_object_support_shapekey_actions(obj)
        # Assume any mesh would use shape-keys by default (even when there are no shape-keys created yet)
        self.only_shapekeys = bool(obj.type == "MESH")

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
            if mi.action:
                return True
        return False

    @property
    def blank_keys(self) -> list[str]:
        return [mi.key for mi in self.items or [] if not mi.action]

    @staticmethod
    def from_context(ctx: Context) -> Optional['MappingProperties']:
        """Get the selected capture properties from the current scene of the provided context"""
        # ctx.selected_editable_objects
        return MappingProperties.from_object(ctx.object)

    @staticmethod
    def from_object(obj: bpy.types.Object) -> Optional["MappingProperties"]:
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
