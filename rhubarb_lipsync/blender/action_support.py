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
    # action_type: str = action.id_type
    # D.actions[0].id_root
    if not action.fcurves:
        return False  # This is not strictly correct, but seems there is not way to know if a blank action is a shape-key one
    # return any(is_fcurve_for_shapekey(fcurve) for fcurve in action.fcurves)
    return is_fcurve_for_shapekey(action.fcurves[0])  # Should be enought to check the first one only
