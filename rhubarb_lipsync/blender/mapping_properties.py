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
from bpy.types import Action, AddonPreferences, Context, PropertyGroup, Sound, UILayout

from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue, MouthShapeInfo, MouthShapeInfos
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbCommandAsyncJob, RhubarbCommandWrapper, RhubarbParser
import re


log = logging.getLogger(__name__)


class NlaTrackRef(PropertyGroup):
    """Reference to an nla track. By name and index sincle NLA track is a non-ID object"""

    search_index_re = re.compile(r"^(?P<idx>\d+\d+\d+)\s.*")

    def on_name_update(self, ctx: Context) -> None:
        pass

        # Change selected item based on the search
        # idx = self.name_search_index
        # if idx < 0:
        #     return
        # if self.index == idx:
        #     return  # Already selected
        # self.index = idx

    @property
    def name_to_index(self) -> int:
        if not self.name:
            return -1
        m = NlaTrackRef.search_index_re.search(self.name_search)
        if m is None:
            return -1
        idx = m.groupdict()["idx"]
        if idx is None:
            return -1
        return int(idx)

    def values_to_search(self, ctx: Context, edit_text) -> Generator[str | Any, Any, None]:
        obj = ctx.active_object
        if not obj or not obj.animation_data:
            return
        for i, t in enumerate(obj.animation_data.nla_tracks or []):
            yield f"{str(i).zfill(3)} {t.name}"

    name: StringProperty(name="NLA Track", description="Name of the selected NLA track", search=values_to_search, update=on_name_update)  # type: ignore
    index: IntProperty(name="Index of the selected track")  # type: ignore


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


class MappingProperties(PropertyGroup):
    """Mapping of all the mouth shape types to action(s)"""

    items: CollectionProperty(type=MappingItem, name="Mapping items")  # type: ignore
    index: IntProperty(name="Selected mapping index")  # type: ignore
    # nla_track1: PointerProperty(type=bpy.types.NlaTrack, name="Tract 1")  # type: ignore
    nla_track1: PointerProperty(type=NlaTrackRef, name="Track 1")  # type: ignore
    nla_track2: PointerProperty(type=NlaTrackRef, name="Track 2")  # type: ignore

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

    def build_items(self) -> None:
        # log.trace("Already buil")  # type: ignore
        if len(self.items) > 0:
            return  # Already built (assume)
        log.trace("Building mapping list")  # type: ignore
        for msi in MouthShapeInfos.all():
            item: MappingItem = self.items.add()
            item.key = msi.key

    @property
    def selected_item(self) -> Optional[MappingItem]:
        if self.index < 0 or self.index >= len(self.items):
            return None
        return self.items[self.index]

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
