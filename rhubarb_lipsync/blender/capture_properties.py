import bisect
import logging
import pathlib
from contextlib import contextmanager
from functools import cached_property
from operator import attrgetter
from typing import Any, Callable, Generator, Iterable, Optional

import bpy
import bpy.utils.previews
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Context, PropertyGroup, Sound

from ..rhubarb.mouth_cues import FrameConfig, MouthCue, MouthCueFrames
from ..rhubarb.rhubarb_command import RhubarbCommandAsyncJob
from . import ui_utils
from .dropdown_helper import DropdownHelper
from .preferences import RhubarbAddonPreferences

try:
    from bpy.types import Strip  # Since v4.4
except ImportError:  # Fall back to old API
    from bpy.types import SoundSequence as Strip

log = logging.getLogger(__name__)


class MouthCueListItem(PropertyGroup):
    """A captured mouth cue."""

    key: StringProperty(  # type: ignore
        "key",
        description="Mouth cue key symbol (A,B,C..)",
        # get=lambda s: s.cue.key,
        # get=lambda s: s['key'],
        # set=lambda s, v: setattr(s.cue.key, v),
        # set=lambda s, v: s.gg(v),
    )
    start: FloatProperty(  # type: ignore
        name="start",
        description="Start time of the cue",
    )
    end: FloatProperty(name="end", description="End time of the cue (usually matches start of the previous cue")  # type: ignore

    @cached_property
    def cue(self) -> MouthCue:
        return MouthCue(self.key, self.start, self.end)
        # print("New")
        # return MouthCue(self['key'], self['start'], self['end'])

    @staticmethod
    def frame_config_from_context(ctx: Context) -> FrameConfig:
        props = CaptureListProperties.capture_from_context(ctx)
        sf = props.start_frame if props else 1
        return FrameConfig(ctx.scene.render.fps, ctx.scene.render.fps_base, sf, ctx.scene.show_subframe)

    def cue_frames(self, ctx: Context) -> MouthCueFrames:
        """Wraps the cue to provide additional frame-related calculation"""
        frame_cfg = MouthCueListItem.frame_config_from_context(ctx)
        return MouthCueFrames(self.cue, frame_cfg)

    def set_from_cue(self, cue: MouthCue) -> None:
        self.key = cue.key
        self.start = cue.start
        self.end = cue.end


class MouthCueList(PropertyGroup):
    """List of the captured mouth cues."""

    items: CollectionProperty(type=MouthCueListItem, name="Cue items")  # type: ignore

    # Autoload would fail in the typing reflection because of the 'MouthCueList' being unknown
    # index_changed: Callable[['MouthCueList', Context, MouthCueListItem], None]
    index_changed: Callable[[PropertyGroup, Context, MouthCueListItem], None]

    def add_cues(self, cues: list[MouthCue]) -> None:
        for cue in cues:
            item: MouthCueListItem = self.items.add()
            item.set_from_cue(cue)

    @property
    def index_within_bounds(self) -> int:
        l = len(self.items)
        if l == 0:
            return -1  # Empty list
        if self.index < 0:  # Befor the first
            return 0
        if self.index >= l:  # After the last
            return l - 1
        return self.index

    def ensure_index_bounds(self) -> None:
        new = self.index_within_bounds
        if self.index != new:
            self.index = new

    @property
    def selected_item(self) -> Optional[MouthCueListItem]:
        if self.index < 0 or self.index >= len(self.items):
            return None
        return self.items[self.index]

    @property
    def last_item(self) -> Optional[MouthCueListItem]:
        if not self.items or len(self.items) < 1:
            return None
        return self.items[-1]

    def find_index_by_time(self, time: float) -> int:
        return bisect.bisect_right(self.items, time, key=attrgetter('start'))

    def find_cue_by_time(self, time: float) -> Optional[MouthCueListItem]:
        idx = self.find_index_by_time(time)
        if idx < 0 or idx >= len(self.items):
            return None
        return self.items[idx]

    def on_index_changed(self, context: Context) -> None:
        if not getattr(MouthCueList, 'index_changed', None):
            return
        self.ensure_index_bounds()
        i = self.selected_item
        if not i:
            return
        # prefs = RhubarbAddonPreferences.from_context(self.ctx)
        MouthCueList.index_changed(self, context, i)

        # context.scene.frame_float = i.frame_float

    index: IntProperty(name="Selected cue index", update=on_index_changed)  # type: ignore
    # index: IntProperty(name="Selected cue index")  # type: ignore


class JobProperties(PropertyGroup):
    """Describes current state of the capture-process"""

    progress: IntProperty("Progress", default=-1, min=0, max=100)  # type: ignore
    status: StringProperty("Capture status")  # type: ignore
    error: StringProperty("Error message")  # type: ignore
    cancel_request: BoolProperty(default=False, name="Cancel requested")  # type: ignore

    @property
    def running(self) -> bool:
        return self.progress > 0 and self.progress != 100

    def update_from_async_job(self, job: RhubarbCommandAsyncJob) -> None:
        self.progress = job.last_progress
        self.status = job.status
        if not job.last_exception:
            self.error = ""
        else:
            self.error = f"{type(job.last_exception).__name__}\n{' '.join(job.last_exception.args)}"


class CaptureProperties(PropertyGroup):
    """Capture setup and list of captured cues"""

    def on_sound_update(self, ctx: Context) -> None:
        # ctx.area.tag_redraw()
        rootProps = CaptureListProperties.from_context(ctx)
        rootProps.name = self.short_desc(rootProps.index)

    sound: PointerProperty(type=bpy.types.Sound, name="Sound", update=on_sound_update)  # type: ignore

    def get_strip(self, ctx: Context) -> Optional[Strip]:
        strips = ui_utils.find_sound_strips_by_sound(ctx, self.sound)
        if not strips:
            return None
        return strips[0]

    def on_start_frame_update(self, ctx: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(ctx)
        if not prefs.sync_with_sequencer:
            return False
        # Set the strip start frame based on the Capture start_frame
        strip = self.get_strip(ctx)
        if strip.frame_start == self.start_frame:
            return
        strip.frame_start = self.start_frame

    def on_channel_update(self, ctx: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(ctx)
        if not prefs.sync_with_sequencer:
            return False
        # Set the strip start frame based on the Capture start_frame
        strip = self.get_strip(ctx)
        if strip.channel == self.channel_number:
            return
        strip.channel = self.channel_number

    def sync_from_strip(self, strip: Strip) -> bool:
        changed = False
        if strip.frame_start != self.start_frame:
            self.start_frame = int(strip.frame_start)
            changed = True
        if strip.channel != self.channel_number:
            self.channel_number = strip.channel
            changed = True
        return changed

    def on_strip_update(self, ctx: Context) -> bool:
        prefs = RhubarbAddonPreferences.from_context(ctx)
        if not prefs.sync_with_sequencer:
            return False
        # Set the strip start frame based on the Capture start_frame
        strips = ui_utils.find_sound_strips_by_sound(ctx, self.sound)
        if not strips:
            return False
        return self.sync_from_strip(strips[0])

    start_frame: IntProperty(  # type: ignore
        name="Start Frame",
        description="The start frame of the sound strip corresponding to the frame where the sound is placed in the Video Sequencer. Also used as start frame of the NLA strip when baking to the NLA.",
        default=1,
        update=on_start_frame_update,
    )
    channel_number: IntProperty(  # type: ignore
        name="Channel",
        description="The channel number of the sound Strip in the sequencer.",
        default=1,
        update=on_channel_update,
    )

    dialog_file: StringProperty(  # type: ignore
        name="Dialog file",
        description="Additional plain-text file with transcription of the sound file to improve accuracy. Works for english only",
        subtype='FILE_PATH',
    )
    job: PointerProperty(type=JobProperties, name="Job")  # type: ignore
    cue_list: PointerProperty(type=MouthCueList, name="Cues")  # type: ignore
    # mapping: PointerProperty(type=MappingList, name="Mapping")  # type: ignore

    @staticmethod
    def sound_selection_validation(context: Context, required_unpack=True, require_sound=True) -> str:
        # selection_error = MappingProperties.context_selection_validation(context)
        # if selection_error:
        #    return selection_error
        props = CaptureListProperties.capture_from_context(context)
        if not props:
            return "No capture selected"
        if not props.sound and require_sound:
            return "Capture has no sound selected"
        sound: Sound = props.sound
        if required_unpack and sound.packed_file:
            return "Please unpack the sound first."
        return ""

    @property
    def end_frame_time(self) -> Optional[float]:
        cl: MouthCueList = self.cue_list
        if not cl or not cl.last_item:
            return None
        return cl.last_item.end

    @property
    def sound_file_path(self) -> Optional[pathlib.Path]:
        s: Sound = self.sound
        if not s or not s.filepath or s.packed_file:
            return None
        return pathlib.Path(self.sound.filepath)

    @property
    def sound_file_extension(self) -> str:
        p = self.sound_file_path
        if not p:
            return ""
        sfx = p.suffix.lower()
        if not sfx:
            return ""
        if not sfx.startswith("."):
            return sfx
        return sfx[1:]  # Drop the trailing dot

    @property
    def sound_file_basename(self) -> str:
        """Name of the current Sound file without extension"""
        p = self.sound_file_path
        if not p:
            return ""
        return p.stem

    @property
    def sound_file_folder(self) -> str:
        """Parent folder of the current Sound file"""
        p = self.sound_file_path
        if not p:
            return ""
        return str(p.parent)

    def is_sound_format_supported(self) -> bool:
        return self.sound_file_extension in ["ogg", "wav"]

    def get_sound_name_with_new_extension(self, new_ext: str) -> str:
        p = self.sound_file_basename
        assert p, "Can't change extension while sound file is not set"
        assert new_ext is not None
        return f"{p}.{new_ext.lower()}"

    def short_desc(self, indx: int) -> str:
        # jprops: JobProperties = self.job
        # if jprops and jprops.status:
        #     status = f" ({jprops.status})"
        # else:
        #     status = ""

        if self.sound:
            fn = f"C:{self.channel_number:02} F:{self.start_frame:03} {self.sound_file_basename}.{self.sound_file_extension}"
        else:
            fn = "<No sound selected>"
        # return f"{fn}{status}.{str(indx).zfill(3)}"
        return f"{str(indx).zfill(3)} {fn}"


class ResultLogItemProperties(PropertyGroup):
    msg: StringProperty("Message", description="Result log message")  # type: ignore
    level: EnumProperty(  # type: ignore
        name="Severity of the message",
        items=[
            ('ERROR', 'FATAL', ""),
            ('WARNING', 'FATAL', ""),
            ('INFO', 'INFO', ""),
        ],
        default='ERROR',
    )
    trace: StringProperty("trace", description="Where the log even happend (object, frame..)")  # type: ignore

    def __repr__(self) -> str:
        return f"{self.level}:{self.msg}\n{self.trace}"


class ResultLogListProperties(PropertyGroup):
    """List of log-messages (errors/warnings) related to baking. So they can be shown and inspect afterwards"""

    max_entries = 40

    items: CollectionProperty(type=ResultLogItemProperties, name="Log entries")  # type: ignore

    @cached_property
    def should_deduplicate(self) -> list[bool]:
        return [False]

    @contextmanager
    def check_dups(self):
        try:
            self.should_deduplicate[0] = True
            yield self
        finally:
            self.should_deduplicate[0] = False

    def all_messages(self) -> Iterable[str]:
        return (it.msg for it in self.items)

    def items_by_level(self, level: str) -> Iterable[ResultLogItemProperties]:
        return (m for m in self.items if m.level == level)

    @property
    def errors(self) -> Iterable[ResultLogItemProperties]:
        return self.items_by_level("ERROR")

    @property
    def has_any_errors_or_warnings(self) -> bool:
        return any(self.warnings) or any(self.errors)

    @property
    def warnings(self) -> Iterable[ResultLogItemProperties]:
        return self.items_by_level("WARNING")

    @property
    def infos(self) -> Iterable[ResultLogItemProperties]:
        return self.items_by_level("INFO")

    def log(self, msg: str, level: str, trace: str = "") -> ResultLogItemProperties:
        l = len(self.items)
        mx = ResultLogListProperties.max_entries
        if l > mx:  # Drop messages if the limit has been reached
            return None  # type: ignore
        if self.should_deduplicate[0]:
            if any(msg in m for m in self.all_messages()):
                return None  # Drop as duplicate

        if l == mx:  # Add warning as the limit is about the be reached
            msg = f"There were more log messages but they were dropped since the limit ({mx}) has been reached."
            level = "WARNING"
            trace = ""

        ret = self.items.add()
        ret.msg = msg
        ret.level = level
        ret.trace = trace
        return ret

    def error(self, msg: str, trace: str = "") -> None:
        self.log(msg, "ERROR", trace)
        log.error(f"{trace}: {msg}")

    def warning(self, msg: str, trace: str = "") -> None:
        self.log(msg, "WARNING", trace)
        log.warning(f"{trace}: {msg}")

    def info(self, msg: str, trace: str = "") -> None:
        self.log(msg, "INFO", trace)
        log.info(f"{trace}: {msg}")

    def clear(self) -> None:
        self.items.clear()


class CaptureListProperties(PropertyGroup):
    """List of captures (setup and cues). Hooked to Blender scene"""

    last_resut_log: PointerProperty(type=ResultLogListProperties, name="Last result", description="Log messages of the last bake")  # type: ignore
    items: CollectionProperty(type=CaptureProperties, name="Captures")  # type: ignore
    index: IntProperty(name="Selected capture index", default=-1)  # type: ignore

    def search_names(self, ctx: Context, edit_text) -> Generator[str, Any, None]:
        for i, p in enumerate(self.items):
            yield p.short_desc(i)
            # yield (p.short_desc, str(i))
        # return [(m, str(i)) for i, m in enumerate(materials)]

    def dropdown_helper(self, ctx: Context) -> DropdownHelper:
        return DropdownHelper(self, list(self.search_names(ctx, "")), DropdownHelper.NameNotFoundHandling.SELECT_ANY)

    def capture_changed(self, ctx: Context) -> None:
        self.dropdown_helper(ctx).name2index()
        capture = self.selected_item
        if not capture:
            return
        # Select the sound Strip in the Sequencer coresponding to the selected Capture
        prefs = RhubarbAddonPreferences.from_context(ctx)
        if not prefs.sync_with_sequencer:
            return False
        strip = capture.get_strip(ctx)
        if not strip:
            return
        if ctx.scene.sequence_editor.active_strip == strip:
            return
        ctx.scene.sequence_editor.active_strip = strip

    def find_capture_by_strip(self, strip: Strip) -> Optional['CaptureProperties']:
        '''Finds a capture that corresponds to the specified sound strip.'''
        if not strip or not hasattr(strip, "sound") or strip.sound is None:
            return None

        ret = None
        for _capture in self.items:
            capture: CaptureProperties = _capture
            if not capture.sound:
                continue
            if capture.sound == strip.sound:
                return capture  # Matched exactly by id
            if bpy.path.abspath(capture.sound.filepath) == bpy.path.abspath(strip.sound.filepath):
                ret = capture  # Save as the second best candidate
        return ret

    def sync_selection_from_active_strip(self, ctx: Context) -> None:
        prefs = RhubarbAddonPreferences.from_context(ctx)
        if not prefs.sync_with_sequencer:
            return False

        active_strip = ctx.scene.sequence_editor.active_strip
        capture = self.find_capture_by_strip(active_strip)
        if not capture:
            return
        self.selected_item = capture

    name: StringProperty(name="name", description="Selected capture", search=search_names, update=capture_changed)  # type: ignore

    @property
    def selected_item(self) -> Optional[CaptureProperties]:
        if self.index < 0 or self.index >= len(self.items):
            return None
        return self.items[self.index]

    @selected_item.setter
    def selected_item(self, capture: Optional[CaptureProperties]) -> None:
        if capture is None:
            self.index = -1
            return

        # Find index of the capture in the collection
        for i, item in enumerate(self.items):
            if item == capture:
                self.index = i
                return

        # If not found
        self.index = -1

    @staticmethod
    def from_context(ctx: Context) -> Optional['CaptureListProperties']:
        """Get the  properties from the current scene of the provided context"""

        if not ctx.scene:
            return None
        ret: CaptureListProperties = getattr(ctx.scene, 'rhubarb_lipsync_captures')  # type: ignore
        return ret

    @staticmethod
    def capture_from_context(ctx: Context) -> Optional['CaptureProperties']:
        cl = CaptureListProperties.from_context(ctx)
        if not cl:
            return None
        return cl.selected_item
