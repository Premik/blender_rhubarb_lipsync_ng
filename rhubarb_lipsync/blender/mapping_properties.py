import bisect
import logging
import math
from operator import attrgetter
import pathlib
from functools import cached_property
from typing import Any, Callable, Optional, cast

import bpy
import bpy.utils.previews
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Action, AddonPreferences, Context, PropertyGroup, Sound, UILayout

from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCue, MouthShapeInfo, MouthShapeInfos
from rhubarb_lipsync.rhubarb.rhubarb_command import RhubarbCommandAsyncJob, RhubarbCommandWrapper, RhubarbParser

log = logging.getLogger(__name__)


class MappingListItem(PropertyGroup):
    """Mapping of a single mouth shape type to action(s)"""

    key: StringProperty("key", description="Mouth cue key symbol (A,B,C..)")  # type: ignore
    action: PointerProperty(type=bpy.types.Action, name="Action")  # type: ignore

    @cached_property
    def cue_desc(self) -> MouthShapeInfo | None:
        if not self.key:
            return None
        return MouthShapeInfos[self.key].value


class MappingListProperties(PropertyGroup):
    """Mapping of all the mouth shape types to action(s)"""

    items: CollectionProperty(type=MappingListItem, name="Mapping items")  # type: ignore
    index: IntProperty(name="Selected mapping index")  # type: ignore

    def build_items(self) -> None:
        # log.trace("Already buil")  # type: ignore
        if len(self.items) > 0:
            return  # Already built (assume)
        log.trace("Building mapping list")  # type: ignore
        for msi in MouthShapeInfos.all():
            item: MappingListItem = self.items.add()
            item.key = msi.key

    @property
    def selected_item(self) -> Optional[MappingListItem]:
        if self.index < 0 or self.index >= len(self.items):
            return None
        return self.items[self.index]

    @staticmethod
    def from_context(ctx: Context) -> Optional['MappingListProperties']:
        """Get the selecrted capture properties from the current scene of the provided context"""
        # ctx.selected_editable_objects
        return MappingListProperties.from_object(ctx.object)

    @staticmethod
    def from_object(obj: bpy.types.Object) -> Optional['MappingListProperties']:
        if not obj:
            return None
        ret: CaptureProperties = getattr(obj, 'rhubarb_lipsync_mapping')  # type: ignore
        # ret.mapping.build_items()  # Ensure cue infos are created
        return ret

    @staticmethod
    def by_object_name(obj_name: str) -> Optional['MappingListProperties']:
        if not obj_name:
            return None
        obj = bpy.data.objects.get(obj_name, None)
        return MappingListProperties.from_object(obj)

    @staticmethod
    def context_selection_validation(ctx: Context) -> str:
        """Validates there is an active object with the rhubarb properties in the blender context"""
        if not ctx.object:
            return "No active object selected"
        if not MappingListProperties.from_context(ctx):
            return "'rhubarb_lipsync' not found on the active object"
        return ""
