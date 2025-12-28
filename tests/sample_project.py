import re
from functools import cached_property
from time import sleep
from typing import Optional

import addon_utils
import bpy
from bpy.types import Object

import rhubarb_lipsync
import rhubarb_lipsync.blender.auto_load
import rhubarb_lipsync.blender.baking_utils as baking_utils
import rhubarb_lipsync.blender.rhubarb_operators as rhubarb_operators
import rhubarb_lipsync.blender.ui_utils as ui_utils
import rhubarb_lipsync.rhubarb.mouth_cues as shape_data
from rhubarb_lipsync.blender import action_support
import sample_data
from rhubarb_lipsync.blender.capture_properties import (
    CaptureListProperties,
    CaptureProperties,
    JobProperties,
    MouthCueList,
    MouthCueListItem,
    ResultLogListProperties,
)
from rhubarb_lipsync.blender.mapping_properties import MappingItem, MappingProperties, NlaTrackRef
from rhubarb_lipsync.blender.preferences import RhubarbAddonPreferences, default_executable_path
from rhubarb_lipsync.rhubarb.log_manager import logManager


class SampleProject:
    """Manages Blender test project"""

    # INFO:Baked 8 cues to 8 action strips
    bake_result_info_line = re.compile(r".*(?P<cues>\d+) cues.*?(?P<strips>\d+) action strips.*")

    registered = False

    def __init__(self) -> None:
        self.make_project_empty()
        SampleProject.ensure_registered()
        self.assert_empty_scene()

    @staticmethod
    def ensure_registered() -> None:
        if SampleProject.registered:
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("Already registered. There could be undesired side effects")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            # assert False
            addon_utils._addon_ensure(RhubarbAddonPreferences.bl_idname)
            return
        rhubarb_lipsync.register()  # Simulate blender register call
        logManager.set_trace()

        # bpy.context.preferences.addons['rhubarb_lipsync'].preferences = bpy.context.preferences.addons['rhubarb_lipsync'].preferences
        # Make sure the addon gets listed in the ctx.addons preferences. This is probably a hack
        addon_utils._addon_ensure(RhubarbAddonPreferences.bl_idname)
        SampleProject.registered = True

    def assert_empty_scene(self) -> None:
        """Make sure the default scene looks as expected and doesn't contain any left-over objects."""
        non_default_objects = [o for o in bpy.data.objects if o.name not in ["Camera", "Cube", "Light"]]
        assert not bool(non_default_objects), f"Unexpected objects in the default scene: {non_default_objects}"
        assert not bool(list(bpy.data.actions)), f"Unexpected actions in the default scene: {list(bpy.data.actions)}"
        assert not self.cprops, f"There is unexpected Capture already created {self.cprops}.  "
        for obj in bpy.data.objects:
            if obj.animation_data and obj.animation_data.nla_tracks:
                assert False, f"Unexpected NLA tracks on object {obj.name}: {[track.name for track in obj.animation_data.nla_tracks]}"

        if self.mprops:
            assert not len(self.mprops.items), f"There is unexpected mapping already created on the {bpy.context.object}."

    def make_project_empty(self) -> None:
        bpy.ops.wm.read_factory_settings(False, use_empty=True)

    @cached_property
    def sample(self) -> sample_data.SampleData:
        return sample_data.snd_en_male_electricity

    def create_capture(self) -> None:
        """Create new (black) capture in the Scene and do basic verification"""
        bpy.ops.rhubarb.create_capture_props()  # Create new capture item
        props = self.cprops
        assert props
        p1 = self.prefs.executable_path
        if not p1.exists():
            p2 = default_executable_path()
            print(f"The {p1} doesn't exist. Changed to {p2} ")
            self.prefs.executable_path_string = str(p2)

    def set_capture_sound(self, sound: Optional[bpy.types.Sound] = None) -> None:
        if sound is None:
            sound = self.sample.to_sound(bpy.context)
        self.cprops.sound = sound

    def trigger_capture(self) -> None:
        ret = bpy.ops.rhubarb.process_sound_file()
        assert 'RUNNING_MODAL' in ret

    def wait_for_capture_finish(self) -> None:
        assert self.jprops
        last = 0
        loops = 0
        while self.jprops.status == "Running":
            sleep(0.1)
            op = rhubarb_operators.ProcessSoundFile.last_op
            if not op:
                break

            op.modal(bpy.context, None)
            if self.jprops.progress > last:
                loops = 0
            loops += 1
            assert loops < 50, f"Got not progress update after 5 secs {last}"
        assert self.jprops.status == "Done", f"Capture failed {self.jprops.status} {self.jprops.error}"

    @property
    def clist_props(self) -> CaptureListProperties:
        return CaptureListProperties.from_context(bpy.context)

    @property
    def last_result(self) -> ResultLogListProperties:
        """Result from the last Capture (if any)"""
        return self.clist_props and self.clist_props.last_resut_log

    def parse_last_bake_result_details(self) -> tuple[int, int]:
        """Parse number of cues processed and strips created from the info-log message"""
        if not self.last_result or not list(self.last_result.infos):
            return 0, 0
        infos = list(self.last_result.infos)
        assert len(infos) >= 1, infos
        for info in infos:
            m = SampleProject.bake_result_info_line.search(info.msg)
            if m is None:
                continue
            cues = int(m.groupdict()["cues"])
            strips = int(m.groupdict()["strips"])
            return cues, strips
        assert m is not None, f"{info} not matching {SampleProject.bake_result_info_line}"
        return None

    @property
    def cprops(self) -> CaptureProperties:
        """Selected Capture properties in the active Scene"""
        return CaptureListProperties.capture_from_context(bpy.context)

    @property
    def mprops(self) -> MappingProperties:
        """Mapping properties of the active object"""
        return MappingProperties.from_context(bpy.context)

    @property
    def prefs(self) -> RhubarbAddonPreferences:
        return RhubarbAddonPreferences.from_context(bpy.context)

    @property
    def jprops(self) -> JobProperties:
        return self.cprops and self.cprops.job

    @property
    def cue_list(self) -> MouthCueList:
        """Cues (PropertGroup) of the Capture selected in the active Scene"""
        return self.cprops and self.cprops.cue_list

    @property
    def cue_items(self) -> list[MouthCueListItem]:
        return self.cue_list and self.cue_list.items or []

    @property
    def mouth_cues(self) -> list[shape_data.MouthCue]:
        return [ci.cue for ci in self.cue_items]

    def assert_cues_matches_sample(self) -> None:
        res = self.sample.compare_cues_with_expected(self.mouth_cues)
        assert res is None, res

    def capture(self) -> None:
        """Orchestrate the full capture process from sound to cue list"""
        self.create_capture()
        self.set_capture_sound()
        self.trigger_capture()
        self.wait_for_capture_finish()
        self.assert_cues_matches_sample()

    def capture_load_json(self) -> None:
        self.create_capture()
        json_path = str(self.sample.expected_json_path)
        ui_utils.assert_op_ret(bpy.ops.rhubarb.import_json_cue_list(filepath=json_path))

    def ensure_action(self, name: str) -> tuple[bool, bpy.types.Action]:
        """Get or create Action with the given name and adds a simply key frame."""
        if name in bpy.data.actions.keys():
            return False, bpy.data.actions[name]
        a = bpy.data.actions.new(name)
        assert a.name == name, f"Name clash. Got '{a.name}' name instead of '{name}'"
        return True, a

    @property
    def action_single(self) -> bpy.types.Action:
        """Action with single keyframe `location.x@1=1`"""
        created, a = self.ensure_action("action_single")
        if not created:
            return a
        fc = a.fcurves.new("location", index=0)
        fc.keyframe_points.insert(1, 1)
        return a

    @property
    def action_10(self) -> bpy.types.Action:
        """Action 10 frames long. With two keyframes: `location.x@1=1` `location.x@10=10`. Marked as an asset"""
        created, a = self.ensure_action("action_10")
        if not created:
            return a
        a.asset_mark()
        fc = a.fcurves.new("location", index=0)
        fc.keyframe_points.insert(1, 1)
        fc.keyframe_points.insert(10, 10)
        return a

    @property
    def action_invalid(self) -> bpy.types.Action:
        """Action with a non-existing key"""
        created, a = self.ensure_action("action_invalid")
        if not created:
            return a
        fc = a.fcurves.new('pose.bones["InvalidBone"].location', index=0)
        fc.keyframe_points.insert(1, 1)
        return a

    @property
    def action_shapekey1(self) -> bpy.types.Action:
        """Shape-key Action on `ShapeKey1` sets value1@=1"""
        created, a = self.ensure_action("action_shapekey1")
        if not created:
            return a
        a.id_root = 'KEY' 
        fc = a.fcurves.new('key_blocks["ShapeKey1"].value', index=0)
        fc.keyframe_points.insert(1, 1)
        return a

    @property
    def action_sheet(self) -> bpy.types.Action:
        """Action with 2x10 keyframes for 'location.y'. Mimicking faceit layout"""
        created, a = self.ensure_action("action_sheet")
        if not created:
            return a
        fc = a.fcurves.new("location", index=1)  # 'index=1' for Y location
        for k in range(1, 11):  # Looping from 1 to 10
            kf = fc.keyframe_points.insert(10 * k, k / 10)  # The actual "shape"
            kf.interpolation = 'CONSTANT'
            kf = fc.keyframe_points.insert(10 * (k - 1) + 1, 0)  # Reset to "default" shape
            kf.interpolation = 'CONSTANT'
        return a

    @property
    def sphere1(self) -> bpy.types.Object:
        """Ensure Object (mesh) with `Sphere` name exists in the scene"""
        if "Sphere" in bpy.data.objects.keys():
            ret = bpy.data.objects["Sphere"]
            self.make_object_active(ret)
            return ret

        ui_utils.assert_op_ret(bpy.ops.mesh.primitive_uv_sphere_add())
        ret = bpy.context.active_object
        assert ret.name == "Sphere"
        # Add Shape-key
        ret.shape_key_add(name="Basis", from_mix=False)
        ret.shape_key_add(name="ShapeKey1", from_mix=False)
        return ret

    @property
    def armature1(self) -> bpy.types.Object:
        """Ensure Armature Object with `Armature` name exists in the scene"""
        if "Armature" in bpy.data.objects.keys():
            ret = bpy.data.objects["Armature"]
            self.make_object_active(ret)
            return ret

        ui_utils.assert_op_ret(bpy.ops.object.armature_add())
        ret = bpy.context.active_object
        assert ret.name == "Armature"
        return ret

    def initialize_mapping(self, obj: bpy.types.Object) -> None:
        """Make the provided Object active and initialize blank Mapping on it."""
        bpy.context.view_layer.objects.active = obj  # Make the obj active
        assert self.mprops
        ui_utils.assert_op_ret(bpy.ops.rhubarb.build_cueinfo_uilist())  # Populate the cue-type list

    def create_mapping(self, actions: list[bpy.types.Action]) -> None:
        """Populate all the cue mappings using the actions from the list.
        Repeat the actions from the list if needed."""
        assert actions
        assert self.mprops
        alen = len(actions)
        for i, _item in enumerate(self.mprops.items):
            mi: MappingItem = _item
            mi.action = actions[i % alen]
            mi.migrate_to_slots()

    def create_baking_context(self) -> baking_utils.BakingContext:
        bc = baking_utils.BakingContext(bpy.context)
        assert len(bc.objects) > 0, f"No object with mapping in the selection {bc.objects}"
        bc.next_object()
        assert bc.current_object, f"No object selected from the {bc.objects}"
        return bc

    def create_mapping_1action_on_armature(self) -> baking_utils.BakingContext:
        self.initialize_mapping(self.armature1)  # Armature object becomes active
        self.create_mapping([self.action_single])
        return self.create_baking_context()

    def create_mapping_2actions_on_armature(self) -> baking_utils.BakingContext:
        self.initialize_mapping(self.armature1)  # Armature object becomes active
        self.create_mapping([self.action_single, self.action_10])
        return self.create_baking_context()

    def create_mapping_1action_on_mesh(self) -> baking_utils.BakingContext:
        self.initialize_mapping(self.sphere1)  # Sphere object becomes active
        self.create_mapping([self.action_shapekey1])
        return self.create_baking_context()

    def create_mapping_two_objects(self) -> baking_utils.BakingContext:
        self.initialize_mapping(self.sphere1)  # Sphere object becomes active
        self.create_mapping([self.action_shapekey1])
        self.initialize_mapping(self.armature1)  # Armature object becomes active
        self.create_mapping([self.action_single, self.action_10])
        return self.create_baking_context()

    def create_mapping_sheet(self) -> baking_utils.BakingContext:
        self.initialize_mapping(self.armature1)  # Armature object becomes active
        action = self.action_sheet
        for i, _item in enumerate(self.mprops.items):
            mi: MappingItem = _item
            mi.action = action
            mi.custom_frame_ranage = True
            mi.frame_start = i * 10
            mi.frame_count = 1

        return self.create_baking_context()

    def add_track(self, t: NlaTrackRef, track_index: int) -> NlaTrackRef:
        """Add a new NLA Track and return the updated reference to it"""
        name = f"RLPS Track {track_index}"
        field_name = f"nla_track{track_index}"
        ui_utils.assert_op_ret(bpy.ops.rhubarb.new_nla_track(name=name, track_field_name=field_name))
        assert len(list(t.items())) > 0, "After a track was created there is still selectable track"
        assert t.name.endswith(name), f"Create track '{name}' but the selected track name is '{t.name}'"
        return t

    def add_track1(self) -> NlaTrackRef:
        return self.add_track(self.mprops.nla_track1, 1)

    def add_track2(self) -> NlaTrackRef:
        return self.add_track(self.mprops.nla_track2, 2)

    def make_object_active(self, o: Object) -> None:
        bpy.context.view_layer.objects.active = o

    def save_blend_file(self, trg: str) -> None:
        bpy.ops.wm.save_as_mainfile(filepath=trg)
