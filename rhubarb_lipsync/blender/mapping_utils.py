import logging
from typing import Iterator

import bpy
from bpy.types import Object

from . import mapping_properties

log = logging.getLogger(__name__)


def objects_with_mapping(objects: Iterator[Object]) -> Iterator[Object]:
    """Filter all objects which non-blank mapping properties"""

    for o in objects or []:
        mp = mapping_properties.MappingProperties.from_object(o)
        if mp and mp.has_any_mapping:
            yield o


def is_fcurve_for_shapekey(fcurve: bpy.types.FCurve) -> bool:
    """Determine if an fcurve is for a shape-key action."""
    return fcurve.data_path.startswith("key_blocks[")  # There doesn't seems to be a better way that check the data path


def is_action_shape_key_action(action: bpy.types.Action) -> bool:
    """Determine whether an action is a shape-key action or a regular one."""
    if not action:
        return False
    if not action.fcurves:
        return False  # This is not strictly correct, but seems there is not way to know if a blank action is a shape-key one
    # return any(is_fcurve_for_shapekey(fcurve) for fcurve in action.fcurves)
    return is_fcurve_for_shapekey(action.fcurves[0])  # Should be enought to check the first one only


def does_object_support_shapekey_actions(o: bpy.types.Object) -> bool:
    """Whether it is currently possible to assign a shape-key action to the provided object.
    Object has to be a Mesh with some shape-keys already created"""
    if not o:
        return False
    if o.type != "MESH":
        return False
    return bool(o.data and o.data.shape_keys)


def does_action_fit_object(o: bpy.types.Object, action: bpy.types.Action) -> bool:
    """Check if all action's F-Curves paths are valid for the provided object."""
    if not action.fcurves:  # Blank actions are considered invalid (#8)
        return False
    for fcurve in action.fcurves:
        try:
            if is_fcurve_for_shapekey(fcurve):
                if not does_object_support_shapekey_actions(o):
                    return False  # Shape-key action can't fit an object with no shape-key blocks (no-mesh) in the first place
                # fcurve Action paths are based on the shape_keys data block
                o.data.shape_keys.path_resolve(fcurve.data_path)
            else:  # Normal action, fcurves are based on the Object
                o.path_resolve(fcurve.data_path)
            # Sucessfully accessed the property using the F-Curve's data path.
            # TODO Check the index too
            # if not hasattr(prop, fcurve.array_index):
            #    return False
        except ValueError:
            # The data path does not exist on the object
            return False

    return True


def filtered_actions(o: bpy.types.Object, mp: "mapping_properties.MappingProperties") -> Iterator[bpy.types.Action]:
    """Yields all Actions of the current Blender project while applying various filters when enabled in the provided mapping properties"""
    if not mp:
        return
    for action in bpy.data.actions:
        if not does_action_fit_object(o, action):  # An invalid action
            if not mp.only_valid_actions:
                yield action  # Show-invalid-actions take precedence
            continue
        # The Only-shape-key is a switch
        if mp.only_shapekeys != is_action_shape_key_action(action):
            continue
        if mp.only_asset_actions and not action.asset_data:
            continue
        yield action


def filtered_actions_for_current_object(ctx: bpy.types.Context) -> Iterator[bpy.types.Action]:
    o: bpy.types.Object = ctx.object
    mprops = mapping_properties.MappingProperties.from_object(o)
    yield from filtered_actions(o, mprops)


def is_mapping_item_active(ctx: bpy.types.Context, mi: 'mapping_properties.MappingItem', on_object: Object) -> bool:
    """Indicates whether the provided mapping item's Action is active on the provided Object."""
    if (not mi) or (not mi.action) or (not object):
        return False
    active_object_action: Action
    if mi.maps_to_shapekey:  # There is a shape-key Action on the mapping item
        shape_keys = on_object.data.shape_keys
        if (not shape_keys) or (not shape_keys.animation_data):
            return False  # Shape-key Action can't be active on an object without any shape-keys
        active_object_action = shape_keys.animation_data.action
    else:  # Target is a non-mesh object
        if not bool(on_object.animation_data):
            return False
        active_object_action = on_object.animation_data.action
    if not active_object_action:  # No Action active
        return False
    if mi.action != active_object_action:
        return False  # Object has an Active action but it is not the one mapped
    if not mi.custom_frame_ranage:
        return True  # When not custom framerange and actions match, any timeline position is cosidered active
    f = ctx.scene.frame_current  # Only active when the timeline position is within the frame sub-range
    return mi.frame_range[0] <= f < mi.frame_range[1]


def activate_mapping_item(ctx: bpy.types.Context, mi: 'mapping_properties.MappingItem', on_object: Object) -> None:
    """Make sure the provided object has the provided Action active and current timeline is at the mapped frame-range"""
    if not mi or not mi.action:
        return
    f = ctx.scene.frame_current
    if not (mi.frame_range[0] <= f < mi.frame_range[1]):
        # Unless already within the Action's frame subrange set timeline to the begening of the frame (sub)range
        ctx.scene.frame_set(frame=int(mi.frame_range[0]), subframe=0)

    if mi.maps_to_shapekey:  # There is a shape-key Action on the mapping item
        if not does_object_support_shapekey_actions(on_object):
            return  # Object is not mesh or doesn't have any shape-keys
        shape_keys = on_object.data.shape_keys
        # Shapekeys action are nested onto the shape_keys animation data
        if not bool(shape_keys.animation_data):
            shape_keys.animation_data_create()
        shape_keys.animation_data.action = mi.action
        return
    # The Action of the mi is a normal Action
    if on_object.type == 'ARMATURE':  # Ensure Armature is not in the rest pose
        on_object.data.pose_position = 'POSE'

    if not bool(on_object.animation_data):
        on_object.animation_data_create()  # Ensure the object has animation data
    on_object.animation_data.action = mi.action
    # TODO - mute the RLPS (or any track?) which affects the object


def deactivate_mapping_item(ctx: bpy.types.Context, on_object: Object) -> None:
    if getattr(ctx.screen, 'is_animation_playing', False):
        bpy.ops.screen.animation_cancel()
    if bool(on_object.animation_data):
        on_object.animation_data.action = None
    if does_object_support_shapekey_actions(on_object):
        shape_keys = on_object.data.shape_keys
        if shape_keys and bool(shape_keys.animation_data):
            shape_keys.animation_data.action = None


def list_nla_tracks_of_object(o: bpy.types.Object) -> Iterator[bpy.types.NlaTrack]:
    if not o:
        return
    # For mesh provide shape-key tracks only. But only if the object has any shape-keys created
    if does_object_support_shapekey_actions(o):
        if not o.data or not o.data.shape_keys or not o.data.shape_keys.animation_data:
            return
        for t in o.data.shape_keys.animation_data.nla_tracks:
            yield t
        return

    if not o.animation_data or not o.animation_data.nla_tracks:
        return
    for t in o.animation_data.nla_tracks:
        yield t
