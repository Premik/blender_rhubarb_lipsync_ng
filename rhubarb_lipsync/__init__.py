print("RLSP: enter __init__")
from typing import Optional

import bpy
from bpy.props import PointerProperty

from .blender.auto_load import AutoLoader
from .blender.capture_properties import CaptureListProperties
from .blender.depsgraph_handler import DepsgraphHandler
from .blender.icons_manager import IconsManager
from .blender.mapping_properties import MappingProperties
from .blender.preferences import RhubarbAddonPreferences
from .rhubarb.log_manager import logManager

bl_info = {
    'name': 'Rhubarb Lipsync NG',
    'author': 'Premysl Srubar. Inspired by the original version by Andrew Charlton. Includes Rhubarb Lip Sync by Daniel S. Wolf',
    'version': (1, 7, 0),
    'blender': (3, 3, 2),
    'location': '3d View > Sidebar',
    'description': 'Integrate Rhubarb Lipsync into Blender',
    'wiki_url': 'https://github.com/Premik/blender_rhubarb_lipsync_ng',
    'tracker_url': 'https://github.com/Premik/blender_rhubarb_lipsync_ng/issues',
    'support': 'COMMUNITY',
    'category': 'Animation',
}

autoloader: Optional[AutoLoader]


def is_blender_in_debug() -> bool:
    """Whether Blender was started with --debug or --debug-python flags"""
    return bpy.app.debug or bpy.app.debug_python


def init_loggers(prefs: Optional[RhubarbAddonPreferences]) -> None:
    global autoloader
    if is_blender_in_debug():
        print("RLPS: enter init_loggers() ")
    logManager.init(autoloader.modules)

    if is_blender_in_debug():  # If Blender is in debug, force TRACE loglevel
        logManager.set_trace()
        print(f"RLPS Set TRACE level for {len(logManager.logs)} loggers")
        logManager.ensure_console_handler()
    else:
        if hasattr(prefs, 'log_level') and prefs.log_level != 0:  # 0 default level
            logManager.set_level(prefs.log_level)


# print(f"FILE:  {__file__}")
# if is_blender_in_debug():


def register() -> None:
    global autoloader

    if is_blender_in_debug():
        print("RLPS: enter register() ")
    RhubarbAddonPreferences.bl_idname = __package__
    autoloader = AutoLoader(root_init_file=__file__, root_package_name=__package__)
    try:
        autoloader.find_classes()
        autoloader.register()
    finally:
        autoloader.trace_print_str()

    bpy.types.Scene.rhubarb_lipsync_captures = PointerProperty(type=CaptureListProperties)
    bpy.types.Object.rhubarb_lipsync_mapping = PointerProperty(
        type=MappingProperties,
        options={'LIBRARY_EDITABLE'},
        override={'LIBRARY_OVERRIDABLE'},
    )

    prefs = RhubarbAddonPreferences.from_context(bpy.context, False)
    init_loggers(prefs)
    if hasattr(prefs, 'capture_tab_name'):  # Re-set the tab names in case they differ from defaults
        prefs.capture_tab_name_updated(bpy.context)
        prefs.map_tab_name_updated(bpy.context)
    DepsgraphHandler.register()
    if is_blender_in_debug():
        print("RLPS: exit register() ")


def unregister() -> None:
    global autoloader
    IconsManager.unregister()
    # if 'logManager' in globals():
    #     global logManager
    #     del logManager
    autoloader.unregister()
    DepsgraphHandler.pending_count = 0
    DepsgraphHandler.unregister()
    logManager.remove_console_handler()
    # del log_manager.logManager
    del bpy.types.Scene.rhubarb_lipsync_captures
    del bpy.types.Object.rhubarb_lipsync_mapping


print("RLSP: exit __init__")
