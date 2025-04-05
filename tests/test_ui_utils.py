import unittest

import sample_project
from rhubarb_lipsync import IconsManager

# def setUpModule():
#    rhubarb_lipsync.register()  # Simulate blender register call


class IconsManagerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = sample_project.SampleProject()

    @unittest.skip("Seems not working for bpy as module")
    def testGetIcon(self) -> None:
        assert IconsManager.logo_icon(), "Icon id is zero. Icons loading is probably broken."


if __name__ == '__main__':
    unittest.main()
