import logging

import bpy
from bpy.props import EnumProperty, StringProperty
from bpy.types import Context

from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences
from rhubarb_lipsync.rhubarb.log_manager import logManager
import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, ResultLogListProperties, ResultLogItemProperties
from rhubarb_lipsync import bl_info
import json
from urllib import request
import traceback
import re

log = logging.getLogger(__name__)

def current_version()->tuple[int, int, int]:
    return bl_info['version'] #type: ignore

def version_str(ver:tuple[int, int, int])->str:
    return f"{ver[0]}.{ver[1]}.{ver[2]}"



github_tag_pattern = re.compile(r"v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)")


def parse_github_tag(tag: str) -> tuple[int, int, int]:
    """ Parses a GitHub tag string into a tuple of integers representing the version.    
        Assumes the tag is in semantic versioning format (e.g., 'v1.0.1'). """
    
    match = github_tag_pattern.match(tag)
    if not match:
        raise ValueError(f"Failed to parse {tag} tag to capture the version number.")
    
    major = int(match.group('major'))
    minor = int(match.group('minor'))
    patch = int(match.group('patch'))
    return major, minor, patch


class CheckForUpdates(bpy.types.Operator):
    """Bake the selected objects to nla tracks"""

    bl_idname = "rhubarb.check_for_updates"
    bl_label = "Check for updates"
    github_owner: StringProperty(name="Github repo owner", default="Premik")  # type: ignore
    github_repo: StringProperty(name="Github repo name", default="blender_rhubarb_lipsync_ng")  # type: ignore

    avail_version_cached=(0,0,0)
    last_error=""

    @classmethod
    def has_checked(csl)->bool:
        return csl.avail_version_cached != (0,0,0) or bool(csl.last_error)
        

    @classmethod
    def description(csl, context: Context, self: 'CheckForUpdates') -> str:
        return csl.cached_status_description()


    @classmethod
    def cached_status_description(csl) -> str:
        cv = current_version()
        av = CheckForUpdates.avail_version_cached
        if not CheckForUpdates.has_checked():
            return "Check now."
        if CheckForUpdates.last_error:
            return CheckForUpdates.last_error
        if av > cv:
            return f"There is new version {version_str(av)} available."
        if av < cv:
            return f"Your version {version_str(cv)} is actually newer than the one released {version_str(av)}."
        return f"You are using the latest {version_str(av)} version."

    def get_latest_release_info_from_github(self)->str|None:
        url = f"https://api.github.com/repos/{self.github_owner}/{self.github_repo}/releases/latest"
        log.info(f"Opening: {url}")
        try:
            with request.urlopen(url) as response:
                if response.status != 200:
                    CheckForUpdates.last_error= "Received {response.status} http code."
                    log.error(f"{CheckForUpdates.last_error} Url: {url}.")
                    log.debug(str(response))                    
                    return None 
                data = json.loads(response.read().decode())
                return data['tag_name']
                    
        except Exception as e:
            CheckForUpdates.last_error=f"Error fetching the release details from github {str(e)}"
            log.error(f"{CheckForUpdates.last_error} Url: {url}.")
            log.debug(traceback.format_exc())
            return None

    
    
    def execute(self, ctx: Context) -> set[str]:
        last_tag = self.get_latest_release_info_from_github()
        if last_tag is None: 
            return {'CANCELLED'}
        
        CheckForUpdates.last_error=""
        CheckForUpdates.avail_version_cached= parse_github_tag(last_tag)
                
        
        return {'FINISHED'}



class SetLogLevel(bpy.types.Operator):
    """Enable/disable more verbose logging to console"""

    bl_idname = "rhubarb.set_log_level"
    bl_label = "Log level"
    bl_options = {'UNDO', 'REGISTER'}

    level: EnumProperty(  # type: ignore
        name="Log Level",
        items=[
            (str(logging.FATAL), 'FATAL', ""),
            (str(logging.ERROR), 'ERROR', ""),
            (str(logging.WARNING), 'WARNING', ""),
            (str(logging.INFO), 'INFO', ""),
            (str(logging.DEBUG), 'DEBUG', ""),
            (str(logging.TRACE), 'TRACE', ""),
            (str(logging.NOTSET), 'DEFAULT', ""),
        ],
        default=str(logging.INFO),
    )

    def execute(self, context: Context) -> set[str]:
        level = int(self.level)
        logManager.set_level(level)
        prefs = RhubarbAddonPreferences.from_context(context)
        # Save to prefs so the same level can get recoveret on restart/register
        prefs.log_level = level

        self.report({'INFO'}, f"Set log level '{logManager.level2name(level)}' for {len(logManager.logs)} loggers")

        return {'FINISHED'}


class ShowResultLogDetails(bpy.types.Operator):
    """Bake the selected objects to nla tracks"""

    bl_idname = "rhubarb.show_result_log"
    bl_label = "Show result details"

    def draw(self, ctx: Context) -> None:
        rll: ResultLogListProperties = CaptureListProperties.from_context(ctx).last_resut_log
        box = self.layout.box()
        for _i in rll.items:
            log: ResultLogItemProperties = _i
            row = box.row()
            row = row.split(factor=0.3)
            row.label(text=log.trace)
            icon = 'ERROR'
            if log.level == "ERROR":
                row.alert = True
            else:
                box.alert = False
            if log.level == "INFO":
                icon = "INFO"
            row.label(text=log.msg, icon=icon)

    def invoke(self, context: Context, event: bpy.types.Event) -> set[int] | set[str]:
        return context.window_manager.invoke_props_dialog(self, width=1000)

    def execute(self, ctx: Context) -> set[str]:
        rll: ResultLogListProperties = CaptureListProperties.from_context(ctx).last_resut_log
        rll.items.clear()
        ui_utils.redraw_3dviews(ctx)
        return {'FINISHED'}

