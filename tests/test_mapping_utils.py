import unittest

import bpy

import rhubarb_lipsync.blender.mapping_utils as mapping_utils
import sample_project


class BakingContextTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = sample_project.SampleProject()
        self.anrmal = self.project.action_single
        self.aasset = self.project.action_10
        self.ashpky = self.project.action_shapekey1
        self.ainvld = self.project.action_invalid
        self.project.sphere1

    def list_action(self, shapekeys: bool, valid: bool, assets: bool) -> list[bpy.types.Action]:
        self.project.mprops.only_shapekeys = shapekeys
        self.project.mprops.only_asset_actions = assets
        self.project.mprops.only_valid_actions = valid
        return list(mapping_utils.filtered_actions_for_current_object(bpy.context))

    def testNoShapeKeys(self) -> None:
        actions = self.list_action(False, False, False)
        assert self.anrmal in actions
        assert self.aasset in actions
        assert self.ashpky not in actions
        assert self.ainvld in actions

    def testShapeKeyOnly(self) -> None:
        actions = self.list_action(True, False, False)
        assert self.anrmal not in actions
        assert self.aasset not in actions
        assert self.ashpky in actions
        assert self.ainvld not in actions

    def testValidOnly(self) -> None:
        actions = self.list_action(False, True, False)
        assert self.anrmal in actions
        assert self.aasset in actions
        assert self.ashpky not in actions  # Shape key has invalid key on the sphere1
        assert self.ainvld not in actions

    def testAssetsOnly(self) -> None:
        actions = self.list_action(False, False, True)
        assert self.anrmal not in actions
        assert self.aasset in actions
        assert self.ashpky not in actions
        assert self.ainvld not in actions
