import logging

import bpy

log = logging.getLogger(__name__)


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


def get_action_slot_keys(action: bpy.types.Action, target_id_type: str = None) -> list[str]:
    if is_action_blank(action):
        return []
    if not slots_supported_for_action(action):
        return [""]
    if not target_id_type:
        return [slot.identifier for slot in action.slots]
    return [slot.identifier for slot in action.slots if slot.target_id_type == target_id_type]


def get_animdata_slot_key(ad: bpy.types.AnimData) -> str:
    if not ad:
        return ""
    if not hasattr(ad, "action_slot"):
        return ""  # Old Blender without slots
    if not ad.action_slot:
        return ""
    return ad.action_slot.identifier


def set_animdata_slot_key(ad: bpy.types.AnimData, slot_key: str) -> None:
    if not ad:
        return
    if not hasattr(ad, "action_slot"):
        return
    if not ad.action:
        return
    if not slot_key:
        slot = ad.action.slots[0]  # The first legacy slot
    else:
        slot = ad.action.slots[slot_key]
    ad.action_slot = slot


def get_action_fcurves(action: bpy.types.Action, slot_key: str | int = 0) -> bpy.types.bpy_prop_collection:

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


def ensure_action_fcurves(action: bpy.types.Action, slot_name: str, slot_type='OBJECT') -> bpy.types.bpy_prop_collection:
    if not slots_supported_for_action(action):
        action.id_root = slot_type
        return action.fcurves
    layer = action.layers[0] if action.layers else action.layers.new("Layer1")
    strip = layer.strips[0] if layer.strips else layer.strips.new(type='KEYFRAME')
    slot = action.slots.new(id_type=slot_type, name=slot_name)
    return strip.channelbag(slot, ensure=True).fcurves
