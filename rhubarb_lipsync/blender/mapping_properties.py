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
