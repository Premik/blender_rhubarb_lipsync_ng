import logging
from typing import Iterator

import bpy
from bpy.types import Object




log = logging.getLogger(__name__)


def objects_with_mapping(objects: Iterator[Object]) -> Iterator[Object]:
    """Filter all objects which non-blank mapping properties"""
    # Avoid circular dep. hack
    from rhubarb_lipsync.blender.mapping_properties import MappingProperties
    for o in objects or []:
        mp = MappingProperties.from_object(o)
        if mp and mp.has_any_mapping:
            yield o


def is_action_shape_key_action(action: bpy.types.Action) -> bool:
    """Determine weather an action is a shape-key action or a regular one."""
    for fcurve in action.fcurves:  # There doesn't seems to be a better way that check the data path
        if fcurve.data_path.startswith("key_blocks["):
            return True
    return False


def does_object_support_shapekey_actions(o: bpy.types.Object) -> bool:
    """Whether it is currently possible to assigne a shape-key action to the provided object.
    Object has to be a Mesh with some shape-keys already created"""
    if not o:
        return False
    if o.type != "MESH":
        return False
    return bool(o.data and o.data.shape_keys)