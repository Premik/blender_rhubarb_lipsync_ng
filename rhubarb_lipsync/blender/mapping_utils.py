import logging
from typing import Iterator

import bpy
from bpy.types import Object
import rhubarb_lipsync.blender.mapping_properties as mapping_properties



log = logging.getLogger(__name__)


def objects_with_mapping(objects: Iterator[Object]) -> Iterator[Object]:
    """Filter all objects which non-blank mapping properties"""
    
    for o in objects or []:
        mp = mapping_properties.MappingProperties.from_object(o)
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

def does_action_fit_object(o: bpy.types.Object, action: bpy.types.Action) -> bool:
    """ Check if all action's F-Curves paths are valid for the provided object.  """
    for fcurve in action.fcurves:
        try:
            # Attempt to access the property using the F-Curve's data path.
            prop = o.path_resolve(fcurve.data_path)
            if not hasattr(prop, fcurve.array_index):
                return False
        except ValueError:
            # The data path does not exist on the object
            return False

    return True

def filtered_actions( o: bpy.types.Object, mp : 'mapping_properties.MappingProperties') -> Iterator[bpy.types.Action]:
    """Yields all Actions of the current Blender project while applying various filters when enabled in the provided mapping properties """
    for action in bpy.data.actions:
        if mp.only_shapekeys and not is_action_shape_key_action(action):
            continue
        if mp.only_valid_actions and not does_action_fit_object(o, action):
            continue
        if mp.only_asset_actions and not action.asset_data:
            continue
        yield action

def filtered_actions_for_current_object(ctx: bpy.types.Context) -> Iterator[bpy.types.Action]:
    o:bpy.types.Object = ctx.object
    mprops = mapping_properties.MappingProperties.from_object(o)
    if not mprops: 
        return
    yield from filtered_actions(o, mprops)