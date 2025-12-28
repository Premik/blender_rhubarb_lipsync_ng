import logging
from functools import cached_property
from typing import TYPE_CHECKING, Any, Generator, Optional

import bpy
import bpy.utils.previews
from bpy.props import BoolProperty, CollectionProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Context, NlaTrack, PropertyGroup

from ..rhubarb.mouth_shape_info import MouthShapeInfo, MouthShapeInfos
from . import mapping_utils
from . import action_support
from .dropdown_helper import DropdownHelper
from .action_support import is_action_shape_key_action


log = logging.getLogger(__name__)


if TYPE_CHECKING:
    try:
        from bpy.types import ActionSlot
    except ImportError:  # Blender <v4.4
        ActionSlot = Any  # type: ignore
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
        _, _ = self.dropdown_helper.detect_item_changes()  # Just to capture the item's length

    def items(self) -> Generator[NlaTrack, Any, None]:
        yield from mapping_utils.list_nla_tracks_of_object(self.object)

    def search_names(self, ctx: Context, edit_text) -> Generator[str, Any, None]:
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
    last_length: IntProperty(  # type: ignore
        name="Last known length of the items",
        default=-1,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    @property
    def selected_item(self) -> Optional[NlaTrack]:
        if not hasattr(self, 'index'):
            return None
        items = list(self.items())
        if self.index < 0 or self.index >= len(items):
            return None
        # self.dropdown_helper(ctx).index2name()
        return items[self.index]

    def __str__(self) -> str:
        d = self.dropdown_helper
        items_count = len(d.names)
        obj_name = self.object.name if self.object and hasattr(self.object, 'name') else ""
        return f"NlaTrackRef(name='{d.name}', index={d.index}, last_length={d.last_length}, items_count={items_count}, object='{obj_name}')"


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
    slot_key: StringProperty(  # type: ignore
        name="Slot",
        description="Action Slot to use",
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    frame_start: FloatProperty(  # type: ignore
        name="Frame Start",
        description="Start frame of the Action used to create the Action Clip",
        step=100,
        default=1,
        soft_min=1,
        soft_max=100,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    frame_count: FloatProperty(  # type: ignore
        name="Frames count",
        description="Number of frames of the Action used to create the Action Clip",
        step=100,
        default=1,
        min=0,
        soft_min=1,
        soft_max=100,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    custom_frame_ranage: BoolProperty(  # type: ignore
        name="Custom Frame Range",
        description="Whether use a custom (sub)range of frames of the Action or whole frame range when creating the Action Clip",
        default=False,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    @property
    def slot(self) -> "ActionSlot":
        if not self.slot_key:
            return None
        if not action_support.slots_supported_for_action(self.action):
            return None
        return self.action.slots.get(self.slot_key)
    def migrate_to_slots(self) -> bool:
        """Set the slot key/name for this mapping item where not set yet, by simply taking first compatible slot.
        But only if Blender version used supports slots. This would set the slot key/name to the Legacy Slot when an older .blend file is loaded.
        """
        if not self.action:
            return False
        slot_keys = action_support.get_action_slot_keys(self.action, self.target_id_type)
        if not slot_keys:
            return False
        if self.slot_key in slot_keys:
            return False  # Already done
        if len(slot_keys) > 1:
            log.warning(
                f"Found {len(slot_keys)}  matching slots when migrating mapping item {self} to slotted Action. Only a ingle match was expected. Taking first one."
            )
        self.slot_key = slot_keys[0]
        return True

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
        if not self.custom_frame_ranage:  # When not custom (sub)range, take range from the Action
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
    def cue_info(self) -> Optional[MouthShapeInfo]:
        if not self.key:
            return None
        return MouthShapeInfos[self.key].value

    @property
    def action_str(self) -> str:
        if not self.action:
            return " "
        if self.slot_key:
            if len(self.slot_key) > 2:
                sk = self.slot_key[2:]
            else:
                sk = self.slot_key

            slot_str = f" / {sk}"
        else:
            slot_str = ""
        return f"{self.action.name}{slot_str}"

    @property
    def target_id_type(self) -> str:
        # TODO: NODETREE ?MATERIAL, ?GREASEPENCIL, ?GREASEPENCIL_V3
        if self.maps_to_shapekey:
            return "KEY"
        return "OBJECT"

    @property
    def maps_to_shapekey(self) -> bool:
        return is_action_shape_key_action(self.action)

    @staticmethod
    def from_object(obj: bpy.types.Object, cue_index: int) -> Optional["MappingItem"]:
        if not obj:
            return None
        mprops: MappingProperties = MappingProperties.from_object(obj)
        return mprops[cue_index]


class MappingProperties(PropertyGroup):
    """Mapping of all the mouth shape types to action(s)"""

    items: CollectionProperty(  # type: ignore
        type=MappingItem,
        name="Mapping items",
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE', 'USE_INSERTION', 'NO_PROPERTY_NAME'},
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

    # target_id_types # OBJECT, KEY, NODETREE

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

    def migrate_to_slots(self) -> None:
        """Ensures the slot key/name is set for each mapping item, when Blender vresion supports slots"""
        if len(self.items) == 0:
            log.error(f"No mapping item creted when slot migration was attempted. Slotted action migration skiped.")
            return
        migrated_count = 0
        for _item in self.items:
            item: MappingItem = _item
            if item.migrate_to_slots():
                migrated_count += 1
        if migrated_count > 0:
            log.info(f"An action slot was automatically assigned to {migrated_count} mapping items. ")

    @property
    def selected_item(self) -> Optional[MappingItem]:
        return self[self.index]

    def __getitem__(self, index) -> Optional[MappingItem]:
        if index < 0 or index >= len(self.items):
            return None
        return self.items[index]

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
    def has_NLA_track_selected(self) -> bool:
        def has_it(t: NlaTrackRef) -> bool:
            return bool(t.selected_item)

        return has_it(self.nla_track1) or has_it(self.nla_track2)

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
