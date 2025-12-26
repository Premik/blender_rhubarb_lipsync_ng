import logging
from typing import Any

import bpy

log = logging.getLogger(__name__)

# OBJECT, KEY, NODETREE ?MATERIAL, ?GREASEPENCIL, ?GREASEPENCIL_V3


def is_fcurve_for_shapekey(fcurve: bpy.types.FCurve) -> bool:
    """Determine if an fcurve is for a shape-key action."""
    return fcurve.data_path.startswith("key_blocks[")  # There doesn't seems to be a better way that check the data path


def is_action_shape_key_action(action: bpy.types.Action) -> bool:
    """Determine whether an action is a shape-key action or a regular one."""
    if not action:
        return False
    types = get_target_id_types_for_action(action)
    return "KEY" in types


def slots_supported_for_action(action: bpy.types.Action) -> bool:
    """Check if the provided action supports slots. Since Blender v4.4. Mandatory in v5+"""
    return hasattr(action, "slots")


# action.slots[ActionSlots] ActionSlot.target_id_type


def get_target_id_types_for_action(action: bpy.types.Action) -> list[str]:
    if not slots_supported_for_action(action):
        return [action.id_root]
    return [slot.target_id_type for slot in action.slots]


def is_action_blank(action: bpy.types.Action) -> bool:
    if not slots_supported_for_action(action):
        return not bool(action.fcurves)
    if not bool(action.slots) or not bool(action.layers) or not bool(action.layers[0].strips):
        return True
    return False


# def get_slot_ids_by_user(user_object: bpy.types.Object, action: bpy.types.Action) -> list[str]:
#     if is_action_blank(action):
#         return []
#     return [slot.identifier for slot in action.slots if user_object in slot.users()]


def get_action_slot_keys(action: bpy.types.Action) -> list[str]:
    if is_action_blank(action):
        return []
    if not slots_supported_for_action(action):
        return [""]
    return [slot.identifier for slot in action.slots]


def get_action_fcurves(action: bpy.types.Action, slot_key: str | int = 0) -> Any:

    if is_action_blank(action):
        return []  # type: ignore
    if not slots_supported_for_action(action):
        return action.fcurves  # bpy.types.ActionFCurves
    # https://developer.blender.org/docs/release_notes/4.4/python_api/#deprecated

    first_strip: bpy.types.ActionKeyframeStrip = action.layers[0].strips[0]  # type: ignore
    bag = first_strip.channelbag(action.slots[slot_key])
    if not bag:
        return []
    return bag.fcurves  # bpy.types.ActionChannelbagFCurves
