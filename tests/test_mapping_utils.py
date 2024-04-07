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

    def list_action(self, shapekeys: bool, valid: bool, assets: bool) -> list[bpy.types.Action]:
        self.project.mprops.only_shapekeys = shapekeys
        self.project.mprops.only_asset_actions = assets
        self.project.mprops.only_valid_actions = valid
        return list(mapping_utils.filtered_actions_for_current_object(bpy.context))

    def testWithouShapeKeys(self) -> None:
        self.project.armature1
        actions = self.list_action(False, True, False)
        self.assertIn(self.anrmal, actions)
        self.assertIn(self.aasset, actions)
        self.assertNotIn(self.ashpky, actions)
        self.assertNotIn(self.ainvld, actions)

    def testValidShapeKeysOnly(self) -> None:
        self.project.sphere1
        actions = self.list_action(True, True, False)
        self.assertNotIn(self.anrmal, actions)
        self.assertNotIn(self.aasset, actions)
        self.assertIn(self.ashpky, actions)
        self.assertNotIn(self.ainvld, actions)

    def testValidOnly(self) -> None:
        self.project.armature1
        actions = self.list_action(False, True, False)
        self.assertIn(self.anrmal, actions)
        self.assertIn(self.aasset, actions)
        self.assertNotIn(self.ashpky, actions)  # Shape key has invalid key on the sphere1
        self.assertNotIn(self.ainvld, actions)

    def testValidAssetsOnly(self) -> None:
        self.project.armature1
        actions = self.list_action(False, True, True)
        self.assertNotIn(self.anrmal, actions)
        self.assertIn(self.aasset, actions)
        self.assertNotIn(self.ashpky, actions)
        self.assertNotIn(self.ainvld, actions)
