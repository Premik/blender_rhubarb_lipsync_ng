import logging
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import Iterator, List, Optional

import bpy
from bpy.types import Context, NlaStrip, NlaTrack, Object

import rhubarb_lipsync.blender.mapping_utils as mapping_utils
import rhubarb_lipsync.blender.ui_utils as ui_utils
from rhubarb_lipsync.blender.capture_properties import CaptureListProperties, CaptureProperties, MouthCueList, MouthCueListItem, ResultLogListProperties
from rhubarb_lipsync.blender.mapping_properties import MappingItem, MappingProperties, NlaTrackRef
from rhubarb_lipsync.blender.preferences import CueListPreferences, MappingPreferences, RhubarbAddonPreferences
from rhubarb_lipsync.blender.strip_placement_properties import StripPlacementProperties
from rhubarb_lipsync.rhubarb.cue_info import MouthShapeInfos
from rhubarb_lipsync.rhubarb.mouth_shape_data import MouthCueFrames, duration_scale_rate

log = logging.getLogger(__name__)


def objects_with_mapping(objects: Iterator[Object]) -> Iterator[Object]:
    """Filter all objects with non-blank mapping properties"""
    for o in objects or []:
        mp = MappingProperties.from_object(o)
        if mp and mp.has_any_mapping:
            yield o


def find_strip_at(track: NlaTrack, at_frame: float) -> tuple[int, NlaStrip]:
    """Finds the strip at the given frame. Effectively utilizing the fact the strips are always ordered and can't overlap"""
    if not track or not track.strips:
        return -1, None
    index = bisect_left(track.strips, at_frame, key=lambda strip: strip.frame_start)
    if index > 0:  # After the first
        index -= 1
    assert len(track.strips) > index >= 0
    strip = track.strips[index]
    # strip is now the one which starts just before (or at) the `at_frame`
    if at_frame < strip.frame_start or at_frame >= strip.frame_end:
        return -1, None  # But it ends/start before/after the `at_frame` (frame_end is exclusive/opened interval)
    return index, strip


def trim_strip_end_at(track: NlaTrack, at_frame: float) -> bool:
    """Finds if there is a strip on the provided `track` at the given `at_frame` frame.
    If so it would trim the strip end up to the `at_frame` point.
    """
    _, strip = find_strip_at(track, at_frame)
    if not strip:
        return False  # No matching strip found, no op
    strip.frame_end = at_frame  # Trim the end
    return True


def strips_on_track(track: NlaTrack, start: int, end: int) -> Iterator[NlaStrip]:
    if not track:
        return
    for strip in track.strips:
        s: NlaStrip = strip
        if s.frame_end < start or s.frame_start > end:
            continue  # Strip is not in frame range
        yield s


@dataclass
class BakingContext:
    """Ease navigation and iteration over various stuff needed for baking"""

    ctx: Context
    cue_index: int = -1
    _objs: List[Object] = None
    object_index: int = -1
    track_index: int = -1
    last_object_selection_type: str = ""

    # def __post_init__(self) -> None:
    #     self.clear_obj_cache()

    @cached_property
    def prefs(self) -> RhubarbAddonPreferences:
        return RhubarbAddonPreferences.from_context(self.ctx)

    @cached_property
    def mprefs(self) -> MappingPreferences:
        return self.prefs.mapping_prefs

    def clear_obj_cache(self) -> None:
        log.debug("Clearing obj cache")
        self._objs: List[Object] = None
        self.object_index = -1
        self.track_index = -1
        self.last_object_selection_type = ""

    @property
    def objects(self) -> List[Object]:
        """All objects to bake the cues on."""
        if self.last_object_selection_type != self.mprefs.object_selection_type:
            self.clear_obj_cache()  # Selection type has changed, invalidate cache
            self.last_object_selection_type = self.mprefs.object_selection_type
        if self._objs is None:  # Rebuild obj cache
            obj_sel = self.mprefs.object_selection(self.ctx)
            self._objs = list(objects_with_mapping(obj_sel))
        return self._objs

    def object_iter(self) -> Iterator[Object]:
        """To iterate over all to-be-baked objects with for each loop.
        Note this function actually sets the current_object as a side effect so can't be used for concurrent looping."""
        for i, o in enumerate(self.objects):
            self.object_index = i
            yield o
        self.object_index = -1

    def next_object(self) -> Object:
        if not self.objects:
            self.object_index = -1
            return None
        self.object_index += 1
        return self.current_object

    @property
    def current_object(self) -> Object:
        """Current Blender Object with the mappings. It is changed as a side effect of the `object_iter`"""
        if self.object_index < 0:
            return None
        if self.object_index >= len(self.objects):
            self.object_index = -1
            return None
        return self.objects[self.object_index]

    @property
    def use_shape_keys_for_current_object(self) -> bool:
        """Whether ShapeKey-Actions should be used or just normal Actions."""
        if not self.current_object:
            return False
        if not self.current_object.type == "MESH":
            return False
        return bool(self.current_object.data.shape_keys)

    @cached_property
    def cprops(self) -> CaptureProperties:
        return CaptureListProperties.capture_from_context(self.ctx)

    @property
    def clist_props(self) -> CaptureListProperties:
        return CaptureListProperties.from_context(self.ctx)

    @property
    def rlog(self) -> ResultLogListProperties:
        return self.clist_props and self.clist_props.last_resut_log

    @property
    def current_traceback(self) -> str:
        """A string describing the "location" of baking state. `Cue`, `Object`, `Track` (where applicable).
        To help identify where warning/error occurred"""
        trace = ""
        cf = self.current_cue
        if cf:
            trace = f"{cf.start_frame_str} {cf.cue.info.key_displ}"
        if self.current_object:
            trace = f"{trace} {self.current_object.name}"
        if self.current_track:
            trace = f"{trace}.{self.current_track.name}"
        return trace

    @cached_property
    def mouth_cue_items(self) -> list[MouthCueListItem]:
        if not self.cprops or not self.cprops.cue_list:
            return []
        cl: MouthCueList = self.cprops.cue_list
        return cl.items

    @cached_property
    def cue_frames(self) -> list[MouthCueFrames]:
        """List of the detected cues wrapped in CueFrames.
        This is a copy so the list and cues can be mutated without affecting the original Capture"""
        cfg = MouthCueListItem.frame_config_from_context(self.ctx)
        return [MouthCueFrames(ci.cue, cfg) for ci in self.mouth_cue_items]

    def cue_iter(self) -> Iterator[MouthCueFrames]:
        for i, cf in enumerate(self.cue_frames):
            self.cue_index = i
            yield cf
        self.cue_index = -1

    @property
    def current_cue(self) -> Optional[MouthCueFrames]:
        """Current mouth cue - source side of the mapping"""
        if self.cue_index < 0:
            return None
        if self.cue_index >= len(self.cue_frames):
            self.cue_index = -1
            return None
        return self.cue_frames[self.cue_index]

    @property
    def the_last_cue(self) -> Optional[MouthCueFrames]:
        if not self.cue_frames:
            return None
        return self.cue_frames[-1]

    def trim_long_cues(self, max_dur: float = -1) -> int:
        if max_dur < 0:
            clp: CueListPreferences = self.prefs.cue_list_prefs
            max_dur = clp.highlight_long_cues
        trimmed = 0
        for cf in self.cue_frames:
            d = cf.cue.duration
            if d <= max_dur:
                continue
            trimmed += 1
            cf.cue.end = cf.cue.start + max_dur
        # if trimmed > 0:
        #     self.rlog.info(f"Trimmed {trimmed} Cues as they were too long.")
        return trimmed

    @cached_property
    def total_frame_range(self) -> Optional[tuple[int, int]]:
        """Frame range of the final output after all the Actions are placed"""
        if not self.the_last_cue:
            return None
        cf = self.the_last_cue
        return self.cprops.start_frame, cf.end_frame

    @property
    def strip_placement_props(self) -> StripPlacementProperties:
        return self.mprops and self.mprops.strip_placement

    @property
    def mprops(self) -> MappingProperties:
        """Mapping properties of the current Object"""
        return MappingProperties.from_object(self.current_object)

    @property
    def current_mapping_item(self) -> MappingItem:
        """Mapping item corresponding to the current Cue"""
        if not self.mprops or not self.current_cue:
            return None
        cue_index = self.current_cue.cue.key_index
        return self.mprops.items[cue_index]

    @property
    def current_mapping_action(self) -> bpy.types.Action:
        """Action of the current Mapping item.
        This is the destination part of the mapping (together with the current track)."""
        return self.current_mapping_item and self.current_mapping_item.action

    @property
    def current_mapping_action_frame_range(self) -> tuple[float, float]:
        mi = self.current_mapping_item
        if not mi:
            return 0.0, 0.0
        return mi.frame_range

    @property
    def current_mapping_action_length_frames(self) -> float:
        """Length (in frames) of the current mapping item's action"""
        range = self.current_mapping_action_frame_range
        return range[1] - range[0]

    def current_mapping_action_scale(self, desired_len_frames: float, scale_min: float = -1, scale_max: float = -1) -> float:
        """Scale factor to use on the strip so it's length matches the current mapping item action's length."""
        if scale_min < 0:
            scale_min = self.strip_placement_props.scale_min
        if scale_max < 0:
            scale_max = self.strip_placement_props.scale_max
        l = self.current_mapping_action_length_frames
        if l <= 0:  # No mapping item selected or the action has no frames
            return 1
        return duration_scale_rate(l, desired_len_frames, scale_min, scale_max)

    @property
    def track1(self) -> Optional[NlaTrack]:
        track_ref: NlaTrackRef = self.mprops and self.mprops.nla_track1
        return track_ref and track_ref.selected_item

    @property
    def track2(self) -> Optional[NlaTrack]:
        track_ref: NlaTrackRef = self.mprops and self.mprops.nla_track2
        return track_ref and track_ref.selected_item

    @property
    def tracks(self) -> List[NlaTrack]:
        """Both tracks of the current object. Some items can be None"""
        return [self.track1, self.track2]

    @property
    def has_two_tracks(self) -> bool:
        return self.track1 and self.track2

    @property
    def current_track(self) -> NlaTrack:
        if self.track_index < 0:
            return None
        return self.tracks[self.track_index % 2]

    def next_track(self) -> Object:
        """Alternates between non-null tracks. If only one track is non-null it would always be the current track"""
        self.track_index += 1
        if not self.current_track:  # Next one was None
            self.track_index += 1  # Try the other one. If None too then both are None
        return self.current_track

    def strips_on_current_track(self) -> Iterator[NlaStrip]:
        start, end = self.total_frame_range
        t = self.current_track
        yield from strips_on_track(t, start, end)

    def validate_track(self) -> list[str]:
        self.next_track()
        if not self.current_track:
            return ["no NLA track selected"]
        ret: list[str] = []
        if self.track1 == self.track2:
            ret += ["Track1 and Track2 are the same"]
        limit = 5000
        strips = 0
        t = self.next_track()
        strips += ui_utils.len_limited(self.strips_on_current_track(), limit)
        if self.next_track() != t and strips < limit:
            strips += ui_utils.len_limited(self.strips_on_current_track(), limit)

        if strips > 0:
            extra = "+" if strips >= limit else ""
            ret += [f"Clash with {strips}{extra} existing strips. Press the (Remove Strips) button"]
        return ret

    def validate_selection(self) -> str:
        """Return validation errors of `self.object`."""
        if not self.current_object:
            return "No object provided for validation"
        if not self.mprops:
            return "Object has no mapping properties"
        if not self.mprops.has_any_mapping:
            return "Object has no mapping"
        return ""

    def validate_mapping_item(self, mi: MappingItem) -> str:
        k: str = mi.key
        is_extended = bool(k in MouthShapeInfos.extended())
        if not mi.action:
            # Non-extended cues has to be mapped, as well the extended cues when used
            if not is_extended or self.prefs.use_extended_shapes:
                return "{} {} no Action mapped"
        else:  # There is an Action mapped
            if not self.prefs.use_extended_shapes:
                return "Not using extended shapes but {} {} mapping"
        if not mi.action.fcurves:
            return "{} {} Action with no keyframes"
        if mapping_utils.is_action_shape_key_action(mi.action):
            if not mapping_utils.does_object_support_shapekey_actions(self.current_object):
                return "{} {} a shape-key Action mapped while the Object has no shape-keys"
            if not self.mprops.only_shapekeys:
                return "{} {} a shape-key Action while a normal Action is expected"
        else:  # A normal action
            if self.mprops.only_shapekeys:
                return "{} {} a normal Action while a shape-key Action is expected"

        return ""

    def validate_current_object_mapping(self) -> list[str]:
        error_msg: dict[str, list[str]] = defaultdict(list)
        # Collect mapping error messages and group them by key so there are no too many lines
        for mi in self.mprops.items:
            msg = self.validate_mapping_item(mi)
            if msg:
                error_msg[msg] += [mi.key]
        return [tmpl.format(' '.join(keys), 'has' if len(keys) == 1 else 'have') for tmpl, keys in error_msg.items()]

    def validate_current_object(self) -> list[str]:
        """Return validation errors of `self.object`."""

        sel_errors = self.validate_selection()
        if sel_errors:
            return [sel_errors]
        ret: list[str] = []
        if not self.mouth_cue_items:
            ret += ["No cues in the capture"]

        ret += self.validate_current_object_mapping()
        ret += self.validate_track()
        return ret
